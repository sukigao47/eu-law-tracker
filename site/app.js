
const PAGE_SIZE = 15;
const STATUS_LABELS = { active:"现行有效", pending:"尚未生效", inactive:"非现行", unknown:"未标注" };
const EFFECT_LABELS = {
  binding:"具有约束力", "non-binding":"不具有约束力",
  preparatory:"立法准备文件", informational:"信息或说明文件", judicial:"司法裁判文件", uncertain:"需个案核验"
};
const TYPE_LABELS = {
  R:"条例（Regulation）", L:"指令（Directive）", D:"决定（Decision）",
  H:"建议（Recommendation）", A:"意见（Opinion）", O:"欧洲央行指导方针",
  G:"决议（Resolution）", X:"《官方公报》L系列其他文件", Y:"《官方公报》C系列其他文件",
  PC:"立法提案", DC:"委员会通信、报告或政策文件", SC:"工作人员工作文件",
  JC:"联合文件", XC:"委员会其他文件", AP:"欧洲议会立法决议",
  IP:"欧洲议会决议或声明", CJ:"欧盟法院判决", CC:"总法律顾问意见", CO:"欧盟法院命令"
};
const SUBJECT_LABELS = new Map(Object.entries({
  agriculture:"农业", "common agricultural policy":"共同农业政策",
  "common commercial policy":"共同商业政策",
  "common foreign and security policy":"共同外交与安全政策",
  competition:"竞争", "consumer protection":"消费者保护",
  "customs union":"关税同盟", energy:"能源", environment:"环境",
  fisheries:"渔业", "free movement of goods":"货物自由流通",
  "free movement of persons":"人员自由流动", "internal market":"内部市场",
  "international agreements":"国际协定", "public health":"公共卫生",
  "social policy":"社会政策", taxation:"税收", transport:"交通运输"
}));
const dateParts = new Intl.DateTimeFormat("en-CA", {
  timeZone:"Europe/Brussels", year:"numeric", month:"2-digit", day:"2-digit"
});
const chinaTimeParts = new Intl.DateTimeFormat("zh-CN", {
  timeZone:"Asia/Shanghai", year:"numeric", month:"2-digit", day:"2-digit",
  hour:"2-digit", minute:"2-digit", hourCycle:"h23"
});
const BUSINESS_BOARDS = {
  consumer:{label:"产品准入、安全与合规",topics:["devices","conformity"]},
  privacy:{label:"网络安全、数据与人工智能",topics:["digital"]},
  commercial:{label:"消费者权益、销售与广告",topics:["retail","advertising"]},
  trade:{label:"海关、贸易与出口管制",topics:["trade"]},
  ip:{label:"知识产权与技术标准",topics:["design-ip"]},
  telecom:{label:"无线电、频谱与连接",topics:["conformity"]},
  sustainability:{label:"生态设计、材料与循环经济",topics:["ecodesign","materials","circular"]},
  supply:{label:"供应链、ESG与生产责任",topics:["sourcing","factory"]},
  service:{label:"维修、售后与产品召回",topics:["service"]},
  all:{label:"全部相关文件",topics:[]}
};
const collator = new Intl.Collator("zh-CN");
const numbers = new Intl.NumberFormat("zh-CN");
const ui = Object.fromEntries(Array.from(document.querySelectorAll("[id]"),el=>[el.id,el]));
let snapshot=null, records=[], page=1, refreshError=false, refreshing=false, activeBoard="";

function todayInBrussels(){
  const p=Object.fromEntries(dateParts.formatToParts(new Date()).map(x=>[x.type,x.value]));
  return p.year+"-"+p.month+"-"+p.day;
}
function formatDateZh(value){
  if(!value||!/^\d{4}-\d{2}-\d{2}$/.test(value))return value||"未标注";
  const p=value.split("-");return p[0]+"年"+p[1]+"月"+p[2]+"日";
}
function formatBeijingDateTime(value){
  const p=Object.fromEntries(chinaTimeParts.formatToParts(new Date(value)).map(x=>[x.type,x.value]));
  return p.year+"年"+p.month+"月"+p.day+"日 "+p.hour+":"+p.minute;
}
function labelSubject(value){return SUBJECT_LABELS.get(String(value).toLowerCase())||value;}
function inferDocumentType(record){
  const m=String(record.id||"").match(/^([0-9C])(\d{4})([A-Z]{1,3})/);
  const sector=m?m[1]:"", code=m?m[3]:"";
  let label=record.documentTypeLabel||TYPE_LABELS[code]||"其他欧盟文件";
  let effect=record.legalEffect||"uncertain";
  if(!record.legalEffect){
    if(sector==="3"&&["R","L","D","O"].includes(code))effect="binding";
    else if(sector==="3"&&["A","H"].includes(code))effect="non-binding";
    else if(sector==="5")effect="preparatory";
    else if(sector==="C")effect="informational";
  }
  return {...record,documentTypeCode:record.documentTypeCode||code||"OTHER",
    documentTypeLabel:label,legalEffect:effect};
}
function shortName(record){
  const title=record.titleEn||record.title||"";
  const m=title.match(/\b(Regulation|Directive|Decision|Recommendation|Opinion|Guideline|Resolution)\s+(?:\((?:EU|EC|EEC|Euratom|CFSP)\)\s*)?(?:No\.?\s*)?(\d{1,4}\/\d{1,5})/i);
  if(m){
    const labels={Regulation:"条例",Directive:"指令",Decision:"决定",
      Recommendation:"建议",Opinion:"意见",Guideline:"指导方针",Resolution:"决议"};
    return "欧盟"+labels[m[1]]+" "+m[2];
  }
  return record.shortTitleZh||"CELEX "+record.id;
}
function statusFor(record,today){
  if(record.inForce===true)return "active";
  if(record.entry&&record.entry>today)return "pending";
  return record.inForce===false?"inactive":"unknown";
}
function loadTopics(){
  const selected=ui.topic.value;
  const options=snapshot.profile
    ?snapshot.profile.topics.map(x=>new Option(x.label,x.id))
    :Array.from(new Set(records.flatMap(x=>x.subjects||[])),x=>new Option(labelSubject(x),x));
  options.sort((a,b)=>collator.compare(a.text,b.text));
  ui.topic.replaceChildren(new Option("全部主题",""),...options);
  ui.topic.value=Array.from(ui.topic.options).some(x=>x.value===selected)?selected:"";
}
function loadDocumentTypes(){
  const selected=ui.type.value, options=new Map();
  records.forEach(r=>{
    const key=r.documentTypeCode||"OTHER";
    if(!options.has(key))options.set(key,r.documentTypeLabel||TYPE_LABELS[key]||"其他文件");
  });
  const sorted=Array.from(options.entries()).sort((a,b)=>collator.compare(a[1],b[1]));
  ui.type.replaceChildren(new Option("全部文件类型",""),...sorted.map(x=>new Option(x[1],x[0])));
  ui.type.value=Array.from(ui.type.options).some(x=>x.value===selected)?selected:"";
}
function renderNotice(){
  let message="";
  if(refreshError)message=snapshot
    ?"暂时无法读取最新目录；当前仍显示上次成功载入的数据。"
    :"法规目录暂不可用，请稍后重试，或通过 EUR-Lex 官方入口核对。";
  else if(snapshot&&Date.now()-Date.parse(snapshot.checkedAt)>36*60*60*1000)
    message="目录已超过 36 小时未更新；请留意数据核验时间。";
  ui.notice.textContent=message;ui.notice.hidden=!message;
}
async function loadSnapshot(manual=false){
  if(refreshing)return;
  refreshing=true;
  ui["recent-button"].disabled=true;
  ui["recent-button"].textContent=manual?"正在核验":"查看最新发布";
  try{
    const url=new URL("./data/catalog.json",import.meta.url);
    const response=await fetch(url,{cache:manual?"no-cache":"default"});
    if(!response.ok)throw new Error("Catalogue HTTP "+response.status);
    const data=await response.json();
    if(!Array.isArray(data.documents)||!Number.isFinite(Date.parse(data.checkedAt)))
      throw new Error("法规目录数据结构不完整");
    if(!snapshot||data.checkedAt>=snapshot.checkedAt){
      snapshot=data;
      const topicLabels=new Map((data.profile?.topics||[]).map(x=>[x.id,x.label]));
      records=data.documents.map(raw=>{
        const r=inferDocumentType(raw);
        const topicIds=data.profile?(r.businessTopics||[]):(r.subjects||[]);
        const topicNames=data.profile?topicIds.map(id=>topicLabels.get(id)||id):(r.subjects||[]).map(labelSubject);
        const titleEn=r.titleEn||r.title||"",titleZh=r.titleZh||r.shortTitleZh||"";
        const searchText=[r.id,titleEn,r.title,titleZh,r.documentTypeLabel,r.documentTypeCode,
          r.legalEffect,r.issuer,...(r.subjects||[]),...(r.keywords||[]),...topicNames]
          .filter(Boolean).join(" ").normalize("NFKC").toLocaleLowerCase();
        return {...r,titleEn,titleZh,topicIds,topicNames,searchText};
      });
      loadTopics();loadDocumentTypes();updateOverview();renderLatest();
      ui["sync-time"].dateTime=data.checkedAt;
      ui["sync-time"].textContent=formatBeijingDateTime(data.checkedAt);
      ui["sync-note"].textContent="北京时间 · 数据截至 "+formatDateZh(data.through);
      ui["catalog-scope"].textContent=(data.profile?.label||"智能终端出海相关文件")+" · "+numbers.format(records.length)+" 项收录文件";
    }
    refreshError=false;
  }catch(error){
    console.error("EULaw Watch catalogue load failed:",error);
    refreshError=true;
    if(!snapshot)ui["sync-time"].textContent="暂不可用";
  }finally{
    refreshing=false;ui["recent-button"].disabled=false;ui["recent-button"].textContent="查看最新发布";
    renderNotice();render();
  }
}
function updateOverview(){
  const today=todayInBrussels(),total=records.length;
  const active=records.filter(r=>statusFor(r,today)==="active").length;
  const cutoff=new Date(today+"T00:00:00Z");cutoff.setUTCDate(cutoff.getUTCDate()-89);
  const since=cutoff.toISOString().slice(0,10);
  const recent=records.filter(r=>r.published&&r.published>=since&&r.published<=today).length;
  ui["stat-total"].textContent=numbers.format(total);
  ui["stat-active"].textContent=numbers.format(active);
  ui["stat-recent"].textContent=numbers.format(recent);
  ui["stat-topics"].textContent=numbers.format(snapshot?.profile?.topics?.length||0);
  for(const [id,board] of Object.entries(BUSINESS_BOARDS)){
    const count=id==="all"?total:records.filter(r=>r.topicIds.some(t=>board.topics.includes(t))).length;
    const target=document.querySelector('[data-board-count="'+id+'"]');
    if(target)target.textContent=numbers.format(count);
  }
}
function renderLatest(){
  const box=ui["latest-list"];if(!box)return;
  const latest=records.filter(r=>r.published).sort(newestFirst).slice(0,5);
  if(!latest.length){const p=document.createElement("p");p.className="latest-placeholder";p.textContent="当前目录暂无可展示的近期发布文件。";box.replaceChildren(p);return;}
  box.replaceChildren(...latest.map(r=>{
    const article=document.createElement("article");article.className="latest-item";
    const main=document.createElement("div");main.className="latest-item-main";
    const a=document.createElement("a");a.href=r.eurlexUrl||("https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A"+encodeURIComponent(r.id));
    a.target="_blank";a.rel="noopener";a.lang="en";a.textContent=r.titleEn||r.title||shortName(r);
    const meta=document.createElement("p");meta.className="latest-meta";meta.textContent=(r.documentTypeLabel||"欧盟文件")+" · CELEX "+r.id;
    main.append(a,meta);
    const date=document.createElement("time");date.className="latest-date";date.dateTime=r.published;date.textContent=formatDateZh(r.published);
    article.append(main,date);return article;
  }));
}
function applyBoard(id,clearTopic=true){
  activeBoard=id;if(clearTopic)ui.topic.value="";
  const board=BUSINESS_BOARDS[id];ui["active-board"].hidden=!id;
  if(id)ui["active-board-label"].textContent="当前板块："+board.label;
  document.querySelectorAll("[data-board-id]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.boardId===id)));
  page=1;render();
}
function tag(text,cls){const e=document.createElement("span");e.className="tag "+cls;e.textContent=text;return e;}
function resultRow(r,today){
  const row=document.createElement("tr");
  row.insertCell().append(tag(r.documentTypeLabel||"其他文件","type-other"));
  const short=row.insertCell(),name=document.createElement("span"),celex=document.createElement("span");
  name.className="act-title";name.textContent=shortName(r);
  celex.className="celex";celex.textContent="CELEX "+r.id;short.append(name,celex);
  const en=row.insertCell(),link=document.createElement("a");link.className="act-title";
  link.href=r.eurlexUrl||("https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A"+encodeURIComponent(r.id));
  link.target="_blank";link.rel="noopener";link.lang="en";link.textContent=r.titleEn||r.title||"暂无英文名称元数据";en.append(link);
  const topics=row.insertCell();topics.className="topics";topics.textContent=r.topicNames.slice(0,2).join(" · ")||"未标注";
  if(r.topicNames.length>2){topics.textContent+=" +"+(r.topicNames.length-2);topics.title=r.topicNames.join(" · ");}
  const date=row.insertCell();date.className="pub-date";
  if(r.published){const t=document.createElement("time");t.dateTime=r.published;t.textContent=formatDateZh(r.published);date.append(t);}else date.textContent="未标注";
  const effect=r.legalEffect||"uncertain";row.insertCell().append(tag(EFFECT_LABELS[effect]||"需个案核验","effect-"+effect));
  const status=statusFor(r,today);row.insertCell().append(tag(STATUS_LABELS[status],"status-"+status));
  return row;
}
function matches(r,today,terms){
  const topicMatch=activeBoard?(activeBoard==="all"||r.topicIds.some(t=>BUSINESS_BOARDS[activeBoard].topics.includes(t)))
    :(!ui.topic.value||(ui.topic.value==="__unlabelled"?r.topicIds.length===0:r.topicIds.includes(ui.topic.value)));
  const typeMatch=!ui.type.value||(r.documentTypeCode||"OTHER")===ui.type.value;
  return typeMatch&&(!ui.effect.value||r.legalEffect===ui.effect.value)
    &&(!ui.status.value||statusFor(r,today)===ui.status.value)
    &&topicMatch&&terms.every(term=>r.searchText.includes(term));
}
function newestFirst(a,b){if(a.published===b.published)return String(b.id).localeCompare(String(a.id));return (b.published||"").localeCompare(a.published||"");}
function render(){
  if(!snapshot){ui["result-table"].hidden=true;ui.pagination.hidden=true;ui.empty.hidden=true;ui["result-count"].textContent=refreshError?"法规目录暂不可用":"正在载入法规数据";return;}
  const today=todayInBrussels();
  const terms=ui.search.value.trim().normalize("NFKC").toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const filtered=records.filter(r=>matches(r,today,terms));
  if(ui.sort.value==="oldest")filtered.sort((a,b)=>{if(Boolean(a.published)!==Boolean(b.published))return a.published?-1:1;return newestFirst(b,a);});
  const pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));page=Math.min(page,pages);
  const visible=filtered.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE);
  ui["result-rows"].replaceChildren(...visible.map(r=>resultRow(r,today)));
  ui["result-table"].hidden=!visible.length;ui.empty.hidden=!!visible.length;
  ui["empty-title"].textContent="没有符合条件的文件";
  ui["empty-detail"].textContent="请尝试其他关键词，或调整文件类型、法律效力及业务主题。";
  ui.pagination.hidden=pages===1;
  ui["result-count"].textContent="匹配 "+numbers.format(filtered.length)+" 项 · 全库 "+numbers.format(records.length)+" 项";
  ui["page-count"].textContent="第 "+page+" / "+numbers.format(pages)+" 页";
  ui.previous.disabled=page===1;ui.next.disabled=page===pages;
}
ui.filters.addEventListener("submit",e=>e.preventDefault());
ui.filters.addEventListener("input",e=>{if(e.target.matches('input[type="search"]')){page=1;render();}});
ui.type.addEventListener("change",()=>{page=1;render();});
ui.effect.addEventListener("change",()=>{page=1;render();});
ui.status.addEventListener("change",()=>{page=1;render();});
ui.topic.addEventListener("change",()=>{if(ui.topic.value)applyBoard("",false);else{page=1;render();}});
ui.sort.addEventListener("change",()=>{page=1;render();});
ui["clear-button"].addEventListener("click",()=>{ui.filters.reset();applyBoard("");page=1;render();ui.search.focus();});
document.querySelectorAll("[data-board-id]").forEach(b=>b.addEventListener("click",()=>{applyBoard(b.dataset.boardId===activeBoard?"":b.dataset.boardId);ui.catalog.scrollIntoView({block:"start",behavior:"smooth"});}));
ui["clear-board"].addEventListener("click",()=>applyBoard(""));
ui["recent-button"].addEventListener("click",async()=>{ui.search.value="";ui.sort.value="newest";applyBoard("");ui.latest.scrollIntoView({block:"start",behavior:"smooth"});await loadSnapshot(true);});
ui.previous.addEventListener("click",()=>{page--;render();ui["result-count"].scrollIntoView({block:"nearest"});});
ui.next.addEventListener("click",()=>{page++;render();ui["result-count"].scrollIntoView({block:"nearest"});});
loadSnapshot();
