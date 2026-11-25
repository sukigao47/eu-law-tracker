const PAGE_SIZE = 20;
const TYPE_LABELS = { R: "条例 / Regulation", L: "指令 / Directive", D: "决定 / Decision" };
const STATUS_LABELS = { active: "现行有效", pending: "尚未适用 / 待生效", inactive: "非现行", unknown: "未标注" };
const SUBJECT_LABELS = new Map(Object.entries({
  agriculture:"农业","common agricultural policy":"共同农业政策","common commercial policy":"共同商业政策",
  "common foreign and security policy":"共同外交与安全政策",competition:"竞争", "consumer protection":"消费者保护",
  "customs union":"关税同盟",energy:"能源",environment:"环境",fisheries:"渔业",
  "free movement of goods":"货物自由流通","free movement of persons":"人员自由流动",
  "internal market":"内部市场","international agreements":"国际协定","public health":"公共卫生",
  "social policy":"社会政策",taxation:"税收",transport:"交通运输"
}));
const dateParts = new Intl.DateTimeFormat("en-CA", {timeZone:"Europe/Brussels",year:"numeric",month:"2-digit",day:"2-digit"});
const chinaTime = new Intl.DateTimeFormat("zh-CN", {timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
const collator = new Intl.Collator("zh-CN");
const numbers = new Intl.NumberFormat("zh-CN");
const ui = Object.fromEntries(Array.from(document.querySelectorAll("[id]"), el => [el.id,el]));
let snapshot = null, records = [], taxonomy = {departments:[],crossCutting:[]}, zhTitles = {}, sourceRegistry = {categories:[]};
let page = 1, refreshError = false, refreshing = false;

function todayInBrussels() {
  const p = Object.fromEntries(dateParts.formatToParts(new Date()).map(x=>[x.type,x.value]));
  return [p.year,p.month,p.day].join("-");
}
function normalize(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("zh-CN").replace(/[\u200B-\u200D\uFEFF]/g," ").replace(/\s+/g," ").trim();
}
function statusFor(record,today) {
  if (record.inForce === true) return "active";
  if (record.entry && record.entry > today) return "pending";
  return record.inForce === false ? "inactive" : "unknown";
}
function labelSubject(subject) { return SUBJECT_LABELS.get(String(subject).toLowerCase()) ?? subject; }
function departmentIdsFor(doc) {
  if (Array.isArray(doc.departments)) return doc.departments;
  const ids = new Set(doc.businessTopics ?? []);
  return taxonomy.departments.filter(d=>d.topics.some(t=>ids.has(t))).map(d=>d.id);
}
function topicLabelsFor(doc) {
  const ids = doc.businessTopics ?? [];
  const labels = new Map((snapshot?.profile?.topics ?? []).map(t=>[t.id,t.label]));
  return ids.map(id=>labels.get(id) ?? id);
}
function setSelectOptions(select, items, placeholder) {
  const selected=select.value;
  select.replaceChildren(new Option(placeholder,""),...items.map(item=>new Option(item.label,item.id)));
  if (items.some(item=>item.id===selected)) select.value=selected;
}
function buildSourceDirectory() {
  const grid=document.createDocumentFragment();
  for (const category of sourceRegistry.categories ?? []) {
    const section=document.createElement("article");
    section.className="source-card";
    const heading=document.createElement("h3");heading.textContent=category.label;
    const description=document.createElement("p");description.textContent=category.description;
    section.append(heading,description);
    if(category.coverage){const coverage=document.createElement("p");coverage.className="source-coverage";coverage.textContent=category.coverage;section.append(coverage);}
    const list=document.createElement("ul");
    for (const source of category.sources ?? []) {
      const item=document.createElement("li");
      const link=document.createElement("a");
      link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";
      link.textContent=source.name;
      const note=document.createElement("p");note.textContent=source.purpose;
      item.append(link,note);list.append(item);
    }
    section.append(list);
    const status=document.createElement("span");status.className="source-status";
    status.textContent=category.status==="reference_only"?"官方入口 · 尚未自动收录":category.status==="automated_partial"?"自动采集 · 有范围限制":"数据源";
    section.append(status);grid.append(section);
  }
  ui["source-grid"].replaceChildren(grid);
}
function buildTaxonomyUI() {
  setSelectOptions(ui.department,taxonomy.departments,"全部业务部门");
  setSelectOptions(ui["cross-topic"],taxonomy.crossCutting,"全部跨部门专题");
  setSelectOptions(ui.topic,snapshot.profile?.topics ?? [],"全部法规主题");
  const grid=document.createDocumentFragment();
  taxonomy.departments.forEach(d=>{
    const button=document.createElement("button");
    button.type="button"; button.className="department-card"; button.dataset.department=d.id;
    const name=document.createElement("strong"); name.textContent=d.label;
    const en=document.createElement("span"); en.textContent=d.labelEn;
    button.append(name,en);
    button.addEventListener("click",()=>{ui.department.value=d.id;page=1;render();ui.catalog.scrollIntoView({behavior:"smooth",block:"start"});});
    grid.append(button);
  });
  ui["department-grid"].replaceChildren(grid);
  const cross=document.createDocumentFragment();
  taxonomy.crossCutting.forEach(t=>{
    const button=document.createElement("button");button.type="button";button.className="cross-chip";
    button.textContent=t.label;button.addEventListener("click",()=>{ui["cross-topic"].value=t.id;page=1;render();ui.catalog.scrollIntoView({behavior:"smooth",block:"start"});});
    cross.append(button);
  });
  ui["crosscutting-list"].replaceChildren(cross);
}
function makeSearchText(record) {
  const deptNames=departmentIdsFor(record).map(id=>taxonomy.departments.find(d=>d.id===id)?.label ?? id);
  const topicNames=topicLabelsFor(record);
  return normalize([
    record.id,record.ecli,record.caseNumber,record.parties,record.court,record.work,record.title,record.titleZh,zhTitles[record.id],
    record.legalType,record.instrumentClass,record.bindingNature,record.dateType,record.sourceCategory,...(record.caseLawDigest??[]),...(record.sourceCollections??[]),TYPE_LABELS[record.id?.[5]],record.published,record.entry,
    ...(record.subjects??[]),...(record.keywords??[]),...topicNames,...deptNames
  ].join(" "));
}
function renderNotice() {
  let message="";
  if(refreshError) message=snapshot?"暂时无法读取最新数据，仍显示上次成功载入的快照。":"法规数据暂不可用，请稍后重试或到 EUR-Lex 核对。";
  else if(snapshot && Date.now()-Date.parse(snapshot.checkedAt)>36*60*60*1000) message="法规数据超过 36 小时未同步；如需确认最新发布，请到官方公报核对。";
  ui.notice.textContent=message;ui.notice.hidden=!message;
}
async function loadSnapshot(manual=false) {
  if(refreshing)return;refreshing=true;ui["recent-button"].disabled=true;ui["recent-button"].textContent="正在读取";
  try {
    const base=new URL("./",import.meta.url);
    const [catalogResponse,taxonomyResponse,zhResponse,sourceResponse,relatedResponse,caseLawResponse]=await Promise.all([
      fetch(new URL("./data/catalog.json",base),{cache:manual?"no-cache":"default"}),
      fetch(new URL("./data/business-taxonomy.json",base),{cache:"no-cache"}),
      fetch(new URL("./data/titles-zh.json",base),{cache:"no-cache"}),
      fetch(new URL("./data/source-registry.json",base),{cache:"no-cache"}),
      fetch(new URL("./data/related-materials.json",base),{cache:manual?"no-cache":"default"}).catch(()=>null),
      fetch(new URL("./data/case-law.json",base),{cache:manual?"no-cache":"default"}).catch(()=>null)
    ]);
    if(!catalogResponse.ok)throw new Error("Catalogue HTTP "+catalogResponse.status);
    const data=await catalogResponse.json();
    if(data.version!==1||!Array.isArray(data.documents)||!Number.isFinite(Date.parse(data.checkedAt)))throw new Error("Invalid catalogue payload");
    if(taxonomyResponse.ok)taxonomy=await taxonomyResponse.json();
    if(zhResponse.ok)zhTitles=await zhResponse.json();
    if(sourceResponse.ok)sourceRegistry=await sourceResponse.json();
    let relatedData={documents:[],checkedAt:null},caseLawData={documents:[],checkedAt:null};
    if(relatedResponse?.ok)relatedData=await relatedResponse.json();
    if(caseLawResponse?.ok)caseLawData=await caseLawResponse.json();
    snapshot=data;
    records=[...data.documents,...(relatedData.documents??[]),...(caseLawData.documents??[])].map(doc=>{
      const enriched={...doc,titleZh:doc.titleZh||zhTitles[doc.id]||"",departments:departmentIdsFor(doc),legalTypeCode:doc.sourceCategory==="EU_LEGISLATION"?(doc.id?.[5]??""):""};
      enriched.crossCuttingTopics=Array.isArray(doc.crossCuttingTopics)?doc.crossCuttingTopics:
        taxonomy.crossCutting.filter(t=>t.topics.some(topic=>(doc.businessTopics??[]).includes(topic))).map(t=>t.id);
      enriched.topicNames=topicLabelsFor(enriched);
      enriched.searchText=makeSearchText(enriched);
      return enriched;
    });
    buildTaxonomyUI();
    buildSourceDirectory();
    const checkedAt=[data.checkedAt,relatedData.checkedAt,caseLawData.checkedAt].filter(Boolean).sort().at(-1)??data.checkedAt;
    ui["sync-time"].dateTime=checkedAt;ui["sync-time"].textContent=chinaTime.format(new Date(checkedAt));
    ui["sync-note"].textContent="北京时间 · 公报数据截至 "+(data.through??"未标注");
    ui["catalog-scope"].textContent="当前收录 "+numbers.format(records.length)+" 条法律及相关官方资料";
    refreshError=false;
  } catch(error) {
    console.warn("Unable to load EU law catalogue:",error);refreshError=true;
    if(!snapshot)ui["sync-time"].textContent="暂不可用";
  } finally {
    refreshing=false;ui["recent-button"].disabled=false;ui["recent-button"].textContent="查看最新收录";
    renderNotice();render();
  }
}
function materialStatus(record,today) {
  if(record.sourceCategory==="EU_LEGISLATION")return STATUS_LABELS[statusFor(record,today)];
  if(record.sourceCategory==="CASE_LAW")return ({judicial_decision:"司法裁判文书",advocate_general_opinion:"总法律顾问意见",court_opinion:"法院意见",case_law_reference_material:"判例参考资料",judicial_document_type_unverified:"法院文件（类型待核验）"})[record.bindingNature]??"法院文件";
  return ({
    non_binding_instrument:"非约束性文件",
    generally_non_binding_instrument:"通常不具约束力",
    non_legislative_document:"非立法文件",
    not_determined_from_series:"未根据C系列判断效力",
    not_assessed:"性质待核验"
  })[record.bindingNature]??"性质待核验";
}
function tag(text,className) { const el=document.createElement("span");el.className="tag "+className;el.textContent=text;return el; }
function resultRow(record,today) {
  const row=document.createElement("tr"),code=record.id?.[5]??"",status=statusFor(record,today);
  const kindCell=row.insertCell();
  kindCell.append(tag(record.instrumentClass??TYPE_LABELS[code]??record.legalType??"其他","type-"+code));
  if(record.sourceCategory==="CASE_LAW")kindCell.append(tag("欧盟法院判例","material-case-law"));
  else if(record.sourceCategory==="EU_SOFT_LAW")kindCell.append(tag(["non_binding_instrument","generally_non_binding_instrument"].includes(record.bindingNature)?"软法":"非立法文件","material-soft"));
  else if(record.sourceCategory==="OJ_C_SERIES"||record.sourceCollections?.includes("OJ_C_SERIES"))kindCell.append(tag("OJ C系列","material-ojc"));
  else if(record.sourceCategory==="EU_LEGISLATION")kindCell.append(tag("法律文件","material-law"));
  const zh=document.createElement("td");zh.className="title-zh";
  zh.textContent=record.titleZh||(record.sourceCategory==="CASE_LAW"?"暂未维护中文案名":"暂未维护中文标题");
  row.append(zh);
  const en=document.createElement("td");en.className="title-en";
  const link=document.createElement("a");link.className="act-title";link.href=record.officialUrl||("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"+encodeURIComponent(record.id));
  link.target="_blank";link.rel="noopener noreferrer";link.lang="en";link.textContent=record.title||(record.sourceCategory==="CASE_LAW"?"Open official CURIA case record":"Open official EUR-Lex record");
  const celex=document.createElement("span");celex.className="celex";
  celex.textContent=record.sourceCategory==="CASE_LAW"?(record.ecli?"ECLI "+record.ecli:record.caseNumber?"案件号 "+record.caseNumber:"CELLAR "+record.work):"CELEX "+record.id;
  en.append(link,celex);
  if(record.sourceCategory==="CASE_LAW"){
    const caseMeta=document.createElement("small");caseMeta.className="case-meta";
    caseMeta.textContent=[record.caseNumber&&record.ecli?"案件号 "+record.caseNumber:"",record.court,record.parties].filter(Boolean).join(" · ");
    if(caseMeta.textContent)en.append(caseMeta);
  }
  row.append(en);
  const deptCell=row.insertCell();deptCell.className="topics";
  const deptNames=record.departments.map(id=>taxonomy.departments.find(d=>d.id===id)?.label??id);
  deptCell.textContent=deptNames.join("、")||"未分类";
  const topics=row.insertCell();topics.className="topics";
  topics.textContent=(record.topicNames??[]).join("、")||"未标注";
  const date=row.insertCell();date.className="pub-date";date.textContent=record.published||"未标注";
  if(record.dateType){const dateNote=document.createElement("small");dateNote.className="date-type";dateNote.textContent=record.dateType==="OJ publication date"?"公报发布日期":record.dateType==="CELLAR document date"?"文书日期":record.dateType.startsWith("CELLAR record")?"数据库记录日期（需核验）":"文件日期";date.append(dateNote);}
  row.insertCell().append(tag(materialStatus(record,today),"status-"+(record.sourceCategory==="EU_LEGISLATION"?status:"unknown")));
  return row;
}
function matches(record,today,terms) {
  return (!ui.department.value||record.departments.includes(ui.department.value))
    &&(!ui["cross-topic"].value||(record.crossCuttingTopics??[]).includes(ui["cross-topic"].value))
    &&(!ui.topic.value||(record.businessTopics??[]).includes(ui.topic.value))
    &&(!ui.material.value||(ui.material.value==="legislation"&&record.sourceCategory==="EU_LEGISLATION")||(ui.material.value==="soft_law"&&(record.sourceCategory==="EU_SOFT_LAW"||record.sourceCollections?.includes("EU_SOFT_LAW")))||(ui.material.value==="oj_c_series"&&(record.sourceCategory==="OJ_C_SERIES"||record.sourceCollections?.includes("OJ_C_SERIES")))||(ui.material.value==="case_law"&&record.sourceCategory==="CASE_LAW"))
    &&(!ui.type.value||record.legalTypeCode===ui.type.value)
    &&(!ui.status.value||record.sourceCategory!=="EU_LEGISLATION"||statusFor(record,today)===ui.status.value)
    &&terms.every(term=>record.searchText.includes(term));
}
function render() {
  if(!snapshot){ui["result-table"].hidden=true;ui.pagination.hidden=true;ui.empty.hidden=true;ui["result-count"].textContent=refreshError?"法规数据暂不可用":"正在载入法规数据";return;}
  const today=todayInBrussels(),terms=normalize(ui.search.value).split(" ").filter(Boolean);
  const filtered=records.filter(record=>matches(record,today,terms));
  filtered.sort((a,b)=>ui.sort.value==="oldest"?(a.published??"").localeCompare(b.published??""):(b.published??"").localeCompare(a.published??"")||b.id.localeCompare(a.id));
  const lastPage=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));page=Math.min(page,lastPage);
  const start=(page-1)*PAGE_SIZE,visible=filtered.slice(start,start+PAGE_SIZE);
  ui["result-rows"].replaceChildren(...visible.map(record=>resultRow(record,today)));
  ui["result-table"].hidden=!visible.length;ui.empty.hidden=!!visible.length;
  ui["empty-title"].textContent="没有符合条件的资料";
  ui["empty-detail"].textContent="请尝试其他名称或编号关键词，或调整资料类别、业务部门及主题。";
  ui.pagination.hidden=lastPage<=1;ui["result-count"].textContent="匹配 "+numbers.format(filtered.length)+" 项 · 当前目录 "+numbers.format(records.length)+" 项";
  ui["page-count"].textContent="第 "+page+" / "+numbers.format(lastPage)+" 页";
  ui.previous.disabled=page===1;ui.next.disabled=page===lastPage;
}
ui.filters.addEventListener("submit",event=>event.preventDefault());
ui.filters.addEventListener("input",()=>{page=1;render();});
ui.filters.addEventListener("change",()=>{page=1;render();});
ui.sort.addEventListener("change",()=>{page=1;render();});
ui["clear-button"].addEventListener("click",()=>{ui.filters.reset();ui.sort.value="newest";page=1;render();ui.search.focus();});
ui["recent-button"].addEventListener("click",async()=>{ui.filters.reset();ui.sort.value="newest";page=1;await loadSnapshot(true);ui.catalog.scrollIntoView({behavior:"smooth",block:"start"});});
ui.previous.addEventListener("click",()=>{page=Math.max(1,page-1);render();});
ui.next.addEventListener("click",()=>{page+=1;render();});
loadSnapshot();
