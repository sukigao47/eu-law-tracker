const PAGE_SIZE = 20;
const LAW_ALIASES = {
"32024R1689":["人工智能法案","人工智能条例","人工智能法规","AI Act","Artificial Intelligence Act","欧盟人工智能法案","AI法案"],
"32016R0679":["通用数据保护条例","一般数据保护条例","GDPR","General Data Protection Regulation"],
"32024R2847":["网络韧性法案","网络弹性法案","网络复原力法案","CRA","Cyber Resilience Act"],
"32023R2854":["数据法案","Data Act"],
"32022R2065":["数字服务法案","DSA","Digital Services Act"],
"32022R1925":["数字市场法案","DMA","Digital Markets Act"],
"32023R0988":["通用产品安全条例","通用产品安全法规","GPSR","General Product Safety Regulation"],
"32024R1781":["可持续产品生态设计条例","ESPR","Ecodesign for Sustainable Products Regulation"],
"32023R1542":["电池法案","电池法规","电池和废电池条例","Batteries Regulation"],
"32023R1669":["能效标签","能源标签","智能手机能效标签","Energy Labelling"],
"32023R1670":["智能手机生态设计","生态设计","Ecodesign"],
"32014L0053":["无线电设备指令","RED","Radio Equipment Directive"],
"32011L0065":["RoHS","有害物质限制指令"],
"32006R1907":["REACH","化学品注册评估授权和限制法规"],
"52022XC0629(04)":["欧盟蓝皮书","蓝皮书","欧盟产品规则实施蓝皮书","Blue Guide","2022 Blue Guide","2022/C 247/01"],
"52022XC0629(04)R(02)":["欧盟蓝皮书勘误","蓝皮书勘误","Blue Guide corrigendum","C/2026/90070"]
};
function aliasesFor(record){return LAW_ALIASES[record.id]||[];}
function searchRank(record,query){
 if(!query)return 0;
 const exact=[record.id,referenceNumber(record.id),...aliasesFor(record),zhTitles[record.id],record.titleZh].map(normalize);
 if(exact.includes(query))return 3;
 if(exact.some(x=>x.includes(query)))return 2;
 if(normalize(record.title).includes(query))return 1;
 return 0;
}

const TYPE_LABELS = { R: "条例 / Regulation", L: "指令 / Directive", D: "决定 / Decision" };
const STATUS_LABELS = { active: "现行有效且已实施（适用）", not_applied: "现行有效尚未实施（适用）", partial: "现行有效·分阶段适用", pending: "尚未生效", inactive: "已失效", active_unknown: "现行有效", unknown: "其他状态", na: "已发布" };
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
let snapshot = null, records = [], taxonomy = {departments:[],legalFields:[]}, zhTitles = {}, sourceRegistry = {categories:[]};
let page = 1, refreshError = false, refreshing = false;
const params = new URLSearchParams(location.search);
let departmentView = params.get("department") || "";
let favoritesView = params.get("view") === "favorites";
const HOME = new URL("./", document.baseURI);
let activeView=departmentView?"laws":favoritesView?"favorites":params.get("view")==="laws"?"laws":(["#catalog","#search"].includes(location.hash)?"laws":location.hash==="#departments"||location.hash==="#laws"?"laws":location.hash==="#favorites"?"favorites":"home");
let homeView=activeView==="home";
function showModule(view,department="",reset=true){
 activeView=view;homeView=view==="home";favoritesView=view==="favorites";departmentView=department;
 ui["home-view"].hidden=!homeView;
 ui.catalog.hidden=homeView;
 ui.departments.hidden=view!=="laws"||!!departmentView;
 ui["official-sources"].hidden=view!=="laws"||!!departmentView;
 ui["coverage-note"].hidden=homeView;
 ui["favorites-panel"].hidden=!favoritesView;
 ui.department.disabled=false;
 if(reset){ui.filters.reset();ui.department.value=departmentView;sortExplicit=false;ui.sort.value=defaultSort();page=1;}
 ui["page-title"].textContent="欧盟法规实施跟踪沙盘";
 ui["catalog-title"].textContent=view==="favorites"?"收藏法规":"高级检索";
 for(const link of document.querySelectorAll(".topbar-links [data-view]")){
  if(link.dataset.view===view)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");
 }
 ui["recent-button"].textContent=homeView?"进入法规库":"查看最新收录";
 if(snapshot){applyView();render();}
}
function navigateModule(view,department=""){
 const url=new URL(HOME);url.hash=department?"laws/"+department:view;
 history.pushState(null,"",url);showModule(view,department);
 window.scrollTo({top:0});
}
function restoreModule(){
 const hash=location.hash.slice(1);
 if(hash.startsWith("laws/"))showModule("laws",hash.slice(5));
 else if(["home","laws","favorites"].includes(hash))showModule(hash);
 else if(hash==="search")showModule("laws");
 else if(hash==="catalog")showModule("laws");
 else if(hash==="departments")showModule("laws");
 else {const query=new URLSearchParams(location.search);showModule(query.get("department")?"laws":query.get("view")==="favorites"?"favorites":query.get("view")==="laws"?"laws":"home",query.get("department")||"");}
}
document.addEventListener("click",event=>{
 const link=event.target.closest("a[data-view],a.department-card");
 if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button!==0)return;
 event.preventDefault();
 navigateModule(link.dataset.view||"laws",link.dataset.department||"");
});
window.addEventListener("popstate",restoreModule);
window.addEventListener("hashchange",restoreModule);
function readStorage(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
let favorites = readStorage("eu-law-favorites-v1", {});
let folders = readStorage("eu-law-folders-v1", ["默认收藏"]);
let selectedRecord = null;
function persist() { try { localStorage.setItem("eu-law-favorites-v1",JSON.stringify(favorites));localStorage.setItem("eu-law-folders-v1",JSON.stringify(folders));return true; } catch { alert("无法保存收藏：浏览器存储不可用。");return false; } }
function folderOptions() {
  setSelectOptions(ui["folder-select"],folders.map(x=>({id:x,label:x})),"选择收藏文件夹");
  ui["record-folder"].replaceChildren(...folders.map(x=>new Option(x,x)));
}
function openRecord(record) {
  selectedRecord=record;
  ui["record-name"].textContent=record.titleZh;
  ui["record-en"].textContent=record.title;
  ui["record-depts"].textContent="关联业务："+record.departments.map(id=>taxonomy.departments.find(d=>d.id===id)?.label??id).join("、");
  folderOptions();ui["record-folder"].value=favorites[record.id]?.folder||folders[0];
  ui["record-note"].value=favorites[record.id]?.note||"";
  ui["record-dialog"].showModal();
}
function renderHome(){
 const list=ui["latest-list"];list.replaceChildren();
 const latest=records.filter(r=>r.sourceCategory==="EU_LEGISLATION"&&/^\d{4}-\d{2}-\d{2}$/.test(r.published||"")).sort((a,b)=>b.published.localeCompare(a.published)||b.id.localeCompare(a.id)).slice(0,2);
 ui["home-update"].textContent=latest.length?"数据截至 "+(snapshot?.through||snapshot?.checkedAt?.slice(0,10)||"未标注")+" · 仅展示本库业务范围内已收录文件":"暂无可核验的发布日期记录，请查看欧盟官方公报。";
 for(const r of latest){const item=document.createElement("article");item.className="latest-item";item.dataset.published=r.published;const date=document.createElement("time");date.dateTime=r.published;date.textContent=r.published;const body=document.createElement("div");const name=document.createElement("a");name.href=r.officialUrl||"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"+encodeURIComponent(r.id);name.target="_blank";name.rel="noopener noreferrer";name.textContent=r.titleZh||r.title;const en=document.createElement("p");en.textContent=r.title;const id=document.createElement("small");id.textContent="CELEX "+r.id;body.append(name,en,id);item.append(date,body);list.append(item);}
}
function applyView() {
  if(departmentView && taxonomy.departments.some(d=>d.id===departmentView)){
    const name=taxonomy.departments.find(d=>d.id===departmentView).label;
    ui["page-title"].textContent=name+"法规实施跟踪";
    ui["catalog-title"].textContent=name+"法规一览";
    ui.sort.value="relevance";
    ui.departments.hidden=true;ui.department.value=departmentView;ui.department.disabled=true;
  } else if(favoritesView){
    ui["page-title"].textContent="我的收藏夹";
    ui["catalog-title"].textContent="收藏法规";
    ui.departments.hidden=true;ui["favorites-panel"].hidden=false;
  }
  folderOptions();
}

function todayInBrussels() {
  const p = Object.fromEntries(dateParts.formatToParts(new Date()).map(x=>[x.type,x.value]));
  return [p.year,p.month,p.day].join("-");
}
function asList(value){return Array.isArray(value)?value:value==null?[]:[value];}
function normalize(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("zh-CN").replace(/[\u200B-\u200D\uFEFF]/g," ").replace(/\s+/g," ").trim();
}
function statusFor(record,today) {
  if (record.entry && record.entry > today) return "pending";
  if (record.inForce === false) return "inactive";
  if (record.inForce !== true) return "unknown";
  const dates=asList(record.applicationDates).filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
  if(!dates.length)return "active_unknown";
  if(dates[0]>today)return "not_applied";
  if(dates[dates.length-1]>today)return "partial";
  return "active";
}
function labelSubject(subject) { return SUBJECT_LABELS.get(String(subject).toLowerCase()) ?? subject; }
function departmentIdsFor(doc) {
  const existing = asList(doc.departments);
  const ids = new Set(doc.businessTopics ?? []);
  return [...new Set([...existing,...taxonomy.departments.filter(d=>d.topics.some(t=>ids.has(t))).map(d=>d.id),...Object.keys(DEPARTMENT_CORE).filter(id=>DEPARTMENT_CORE[id].includes(doc.id))])];
}
function legalFieldIdsFor(doc) {
  const subjects=new Set(asList(doc.subjects??doc.subject).map(x=>normalize(x)));
  const searchable=normalize([doc.title,doc.titleZh,...asList(doc.keywords)].filter(Boolean).join(" "));
  return (taxonomy.legalFields??[]).filter(field=>
    asList(field.subjects).some(subject=>subjects.has(normalize(subject))) ||
    asList(field.keywords).some(term=>searchable.includes(normalize(term)))
  ).map(field=>field.id);
}
function topicLabelsFor(doc) {
  const ids = doc.businessTopics ?? [];
  const labels = new Map((snapshot?.profile?.topics ?? []).map(t=>[t.id,t.label]));
  return ids.filter(id=>id!=="devices").map(id=>labels.get(id) ?? id);
}
function setSelectOptions(select, items, placeholder) {
  const selected=select.value;
  select.replaceChildren(new Option(placeholder,""),...items.map(item=>new Option(item.label,item.id)));
  if (items.some(item=>item.id===selected)) select.value=selected;
}
function buildHomepageSourceDirectory() {
  const grid=document.createDocumentFragment();
  for (const category of sourceRegistry.homepageCategories ?? []) {
    const button=document.createElement("button");
    button.type="button";
    button.className="source-category-card";
    button.dataset.sourceCategory=category.id;
    button.setAttribute("aria-label",category.label+"，"+category.sources.length+"个推荐网址");
    const heading=document.createElement("strong");heading.textContent=category.label;
    const description=document.createElement("span");description.textContent=category.description;
    const count=document.createElement("small");count.textContent=category.sources.length+" 个推荐网址 · 查看清单 →";
    button.append(heading,description,count);
    grid.append(button);
  }
  ui["source-category-grid"].replaceChildren(grid);
  showSourceCategoryGrid();
}
function showSourceCategoryGrid() {
  ui["source-category-grid"].hidden=false;
  ui["source-category-detail"].hidden=true;
}
function openSourceCategory(categoryId) {
  const category=(sourceRegistry.homepageCategories??[]).find(item=>item.id===categoryId);
  if(!category)return;
  ui["source-detail-title"].textContent=category.label;
  ui["source-detail-description"].textContent=category.description;
  const list=document.createDocumentFragment();
  for(const source of category.sources??[]){
    const item=document.createElement("li");item.className="source-recommendation";
    const head=document.createElement("div");head.className="source-recommendation-head";
    const link=document.createElement("a");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";link.textContent=source.name;
    const owner=document.createElement("span");owner.className="source-owner";owner.textContent=source.owner;
    head.append(link,owner);
    const purpose=document.createElement("p");purpose.textContent=source.purpose;
    item.append(head,purpose);list.append(item);
  }
  ui["source-recommendations"].replaceChildren(list);
  ui["source-category-grid"].hidden=true;
  ui["source-category-detail"].hidden=false;
}
ui["source-category-grid"].addEventListener("click",event=>{
  const button=event.target.closest("button[data-source-category]");
  if(button)openSourceCategory(button.dataset.sourceCategory);
});
ui["source-back"].addEventListener("click",showSourceCategoryGrid);

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
  setSelectOptions(ui.department,[...taxonomy.departments,{id:"other",label:"其他／通用法规"}],"选择业务部门");
  setSelectOptions(ui["cross-topic"],taxonomy.legalFields??[],"选择法律领域部门");
  const grid=document.createDocumentFragment();
  taxonomy.departments.forEach(d=>{
    const button=document.createElement("a");
    button.className="department-card"; button.dataset.department=d.id; const target=new URL(HOME);target.hash="laws/"+d.id;button.href=target.href;
    const name=document.createElement("strong"); name.textContent=d.label;
    const en=document.createElement("span"); en.textContent=d.labelEn;
    button.append(name,en);
    
    grid.append(button);
  });
  ui["department-grid"].replaceChildren(grid);
}
function referenceNumber(id){const m=/^3(\d{4})[RLD](\d+)$/.exec(id);return m?m[1]+"/"+Number(m[2]):"";}
const ACT_FORM_OPTIONS = {
 legislative: [["R","Regulation"],["L","Directive"],["D","Decision"]],
 delegated: [["delegated-regulation","Delegated Regulation"],["delegated-directive","Delegated Directive"],["delegated-decision","Delegated Decision"]],
 implementing: [["implementing-regulation","Implementing Regulation"],["implementing-decision","Implementing Decision"]]
};
function updateActSubtypeOptions(){
 const select=ui["type-subtype"], options=ACT_FORM_OPTIONS[ui.type.value]??[];
 select.replaceChildren(new Option("Select act form",""),...options.map(([value,label])=>new Option(label,value)));
 select.hidden=options.length===0;
 select.disabled=options.length===0;
 if(!options.length)select.value="";
}
function selectedTypeFilter(){
 const parent=ui.type.value, child=ui["type-subtype"].value;
 if(parent==="legislative")return child;
 // Delegated and implementing subforms retain the existing parent-level filter;
 // no catalogue metadata or result-classification rules are changed here.
 if(parent==="delegated")return child?"delegated":"";
 if(parent==="implementing")return child?"implementing":"";
 return parent;
}
function matchesType(record,value){
 if(!value)return true;
 const title=String(record.title??"").toLowerCase(), kind=String(record.instrumentClass??"").toLowerCase();
 if(value==="delegated"||value==="implementing")return kind.includes(value)||title.startsWith("commission "+value);
 if(value==="guidance")return record.sourceCategory!=="EU_LEGISLATION"&&(record.bindingNature==="interpretative_guidance_non_binding"||/guidance|guidelines|guideline|interpretative notice|blue guide/.test(title)||/guidance/i.test(String(record.instrumentClass??record.legalType??"")));
 if(value==="standards")return /harmonised standard|harmonized standard|common specification/.test(title);
 return record.sourceCategory==="EU_LEGISLATION"&&record.legalTypeCode===value;
}
function makeSearchText(record) {
  const deptNames=departmentIdsFor(record).map(id=>taxonomy.departments.find(d=>d.id===id)?.label ?? id);
  const topicNames=topicLabelsFor(record);
  return normalize([
    ...aliasesFor(record),record.id,record.ecli,record.caseCelex,record.caseNumber,record.parties,record.court,record.work,record.title,record.titleZh,record.titleZhFull,zhTitles[record.id],referenceNumber(record.id),record.titleZh?.replace(/能源/g,"能效"),/eco[- ]?design|energy labell?ing|energy efficiency/i.test(record.title??"")?"能效 能源标签 生态设计":"",...asList(record.interpretedActs),...asList(record.citedDocuments),...asList(record.caseSubjects),
    record.legalType,record.instrumentClass,record.bindingNature,record.dateType,record.sourceCategory,record.ojCitation,record.officialCitation,...asList(record.caseLawDigest),...asList(record.sourceCollections),TYPE_LABELS[record.id?.[5]],record.published,record.entry,
    ...asList(record.subjects),...asList(record.keywords),...topicNames,...deptNames
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
    const base=new URL("./",document.baseURI);
    async function read(name,required=false){
      try {const response=await fetch(new URL("data/"+name,base),{cache:"no-cache"});if(!response.ok)throw Error("HTTP "+response.status);return await response.json();}
      catch(error){if(required)throw error;console.warn(name,error);return null;}
    }
    const [data,tax,translations,registry,relatedData]=await Promise.all([
      read("catalog.json",true),read("business-taxonomy.json"),read("titles-zh.json"),read("source-registry.json"),read("related-materials.json")
    ]);
    if(!Array.isArray(data.documents))throw Error("Invalid catalogue");
    taxonomy=tax??{departments:data.profile?.departments??[],legalFields:[]};
    zhTitles=translations??{};sourceRegistry=registry??{categories:[]};
    snapshot=data;
    const unique=new Map();
    for(const doc of [...data.documents,...asList(relatedData?.documents)]){
      if(!doc?.id||unique.has(doc.id))continue;
      const id=String(doc.id).toUpperCase();
      const curated=zhTitles[id]||doc.titleZhFull||doc.titleZh||"";
      const enriched={...doc,id,sourceCategory:doc.sourceCategory||"EU_LEGISLATION",titleZh:curated,departments:departmentIdsFor(doc),legalTypeCode:id[5]??""};
      enriched.legalFields=legalFieldIdsFor(enriched);
      enriched.topicNames=topicLabelsFor(enriched);
      enriched.searchText=makeSearchText(enriched);
      unique.set(id,enriched);
    }
    records=[...unique.values()];
    buildTaxonomyUI();
    applyView();
    buildSourceDirectory();
    buildHomepageSourceDirectory();
    renderHome();
    const checkedAt=data.checkedAt;
    ui["sync-time"].dateTime=checkedAt;ui["sync-time"].textContent=Number.isFinite(Date.parse(checkedAt))?chinaTime.format(new Date(checkedAt)):"未标注";
    ui["sync-note"].textContent="北京时间 · 公报数据截至 "+(data.through??"未标注");
    ui["catalog-scope"].textContent=departmentView?"默认优先展示本业务核心法规，其次为相关有效法规、配套文件及参考资料；排序不代表法律效力等级或具体适用性结论。":"当前收录 "+numbers.format(records.length)+" 条法律及相关官方资料";
    refreshError=false;
  } catch(error) {
    console.warn("Unable to load EU law catalogue:",error);refreshError=true;
    if(!snapshot){ui["sync-time"].textContent="暂不可用";ui["home-update"].textContent="暂时无法读取法规数据，请查看欧盟官方公报。";}
  } finally {
    refreshing=false;ui["recent-button"].disabled=false;ui["recent-button"].textContent=homeView?"进入法规库":"查看最新收录";
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
const KEY_TERMS = /\b(?:eco[- ]?design|energy labell?ing|energy efficiency|smartphones?|slate tablets?|cybersecurity|cyber resilience|artificial intelligence|data protection|digital services|digital markets|digital product passports?|radio equipment|harmoni[sz]ed standards?|electromagnetic compatibility|batter(?:y|ies)|waste batteries|consumer protection|product safety|market surveillance|due diligence|forced labour|right to repair|packaging|persistent organic pollutants|customs|intellectual property|accessibility|dual-use items|personal data|recycling|repair|recall|charging|USB Type-C)\b/gi;
function resultRow(record,today,terms=[]) {
  const row=document.createElement("tr"),code=record.id?.[5]??"",status=statusFor(record,today);
  row.dataset.published=record.published||"";row.dataset.celex=record.id;
  const favoriteCell=row.insertCell();const star=document.createElement("button");star.type="button";star.className="favorite-star";star.textContent=favorites[record.id]?"★":"☆";star.setAttribute("aria-label",favorites[record.id]?"取消收藏":"收藏法规");star.addEventListener("click",()=>{if(favorites[record.id])delete favorites[record.id];else favorites[record.id]={folder:folders[0],note:""};persist();render();});favoriteCell.append(star);
  const kindCell=row.insertCell();
  kindCell.append(tag(record.instrumentClass??TYPE_LABELS[code]??record.legalType??"其他","type-"+code));
  const zh=document.createElement("td");zh.className="title-zh";
  zh.textContent=record.titleZh||"暂无中文参考译名"; if(record.titleZh){const note=document.createElement("small");note.className="date-type";note.textContent="非官方参考译名";zh.append(note);}
  const detail=document.createElement("button");detail.type="button";detail.className="text-button record-detail";detail.textContent="详情与备注";detail.addEventListener("click",()=>openRecord(record));zh.append(detail);row.append(zh);
  const en=document.createElement("td");en.className="title-en";
  const link=document.createElement("a");link.className="act-title";link.href=record.officialUrl||("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"+encodeURIComponent(record.id));
  link.target="_blank";link.rel="noopener noreferrer";link.lang="en";link.textContent=record.title||"Open official EUR-Lex record";
  const celex=document.createElement("span");celex.className="celex";
  // The identifier column intentionally exposes CELEX only; do not repeat
  // the act number, CELLAR work UUID, ECLI or other secondary identifiers.
  celex.textContent=record.id?"CELEX "+record.id:"CELEX编号待核验";
  en.append(link,celex);
  row.append(en);
  row.insertCell().textContent=record.entry&&record.entry>="1952-01-01"?record.entry:"-";
  row.insertCell().append(tag(record.sourceCategory==="EU_LEGISLATION"?STATUS_LABELS[status]:"不适用","status-"+(record.sourceCategory==="EU_LEGISLATION"?status:"unknown")));
  return row;
}
function advancedMatch(record,terms) {
  const officialEn=normalize(record.title),en=normalize([record.title,...aliasesFor(record).filter(x=>/[a-z]/i.test(x)&&!/[\u3400-\u9fff]/.test(x))].join(" ")),zh=normalize([record.titleZh,record.titleZhFull,zhTitles[record.id],...aliasesFor(record).filter(x=>/[\u3400-\u9fff]/.test(x))].join(" "));
  const hay=record.searchText;
  const words=id=>normalize(ui[id].value).split(" ").filter(Boolean);
  const any=words("any-terms"),excluded=words("exclude-terms"),phrase=normalize(ui["exact-phrase"].value);
  const number=normalize(ui["act-number"].value).match(/\d{4}\s*\/\s*\d+/)?.[0].replace(/\s/g,"")||normalize(ui["act-number"].value);
  const author=/^commission\b/.test(officialEn)?"commission":/^council\b/.test(officialEn)?"council":/european parliament and (?:of )?the council/.test(officialEn)?"parliament":"other";
  return terms.every(t=>hay.includes(t))&&(!any.length||any.some(t=>hay.includes(t)))&&excluded.every(t=>!hay.includes(t))&&(!phrase||hay.includes(phrase))
    &&zh.includes(normalize(ui["zh-name"].value))&&en.includes(normalize(ui["en-name"].value))
    &&(!number||referenceNumber(record.id)===number)&&(!ui["celex-number"].value.trim()||normalize(record.id)===normalize(ui["celex-number"].value))
    &&(!ui.author.value||author===ui.author.value);
}
function matches(record,today,terms) {
  return (!departmentView||record.departments.includes(departmentView))&&(!favoritesView||(!!favorites[record.id]&&(!ui["folder-select"].value||favorites[record.id].folder===ui["folder-select"].value)))&&(!ui.department.value||(ui.department.value==="other"?!record.departments.length:record.departments.includes(ui.department.value)))
    &&(!ui["cross-topic"].value||(record.legalFields??[]).includes(ui["cross-topic"].value))
    &&matchesType(record,selectedTypeFilter())
    &&(!ui.status.value||((record.sourceCategory==="EU_LEGISLATION"?statusFor(record,today):"na")===ui.status.value))
    &&advancedMatch(record,terms);
}

// Editorial priority lists: operational relevance, not a formal hierarchy of EU legal norms.
const DEPARTMENT_CORE = {
 smartphone:["32023R1670","32023R1669","32023R1542","32014L0053","32022L2380","32024R1781","32017R1369","32023R0988","32024R2847","32011L0065","32012L0019","32024L1799","32019L0882","32016R0679","32024R1689","32019R1020","32025R0040","32006R1907"],
 wearables:["32014L0053","32023R1542","32023R0988","32024R2847","32011L0065","32016R0679","32024R1689","32024R1781","32012L0019","32017R0745","32019R1020"],
 "tablet-pc":["32023R1670","32023R1669","32023R1542","32014L0053","32022L2380","32024R1781","32017R1369","32024R2847","32011L0065","32012L0019","32023R0988","32019L0882"],
 "marketing-services":["32005L0029","32006L0114","32011L0083","32016R0679","32024R1689","32022R2065","32024L0825","32019L0770","32019L0771","32024L1799","32023R0988","32019L0882","32017R1369"],
 iot:["32014L0053","32024R2847","32023R2854","32023R0988","32023R1542","32011L0065","32014L0030","32014L0035","32024R1781","32016R0679","32024R1689","32012L0019"],
 "smart-vehicle":["32018R0858","32019R2144","32023R1542","32023R1804","32016R0679","32024R1689","32023R2854","32014L0053","32019R1020"],
 "integrated-delivery":["32019R1020","32013R0608","32024L1760","32024R3015","32023R1542","32025R0040","32024R1157","32006R1907","32012L0019","32023R0988","32024L1799","32016R0679"],
 "hardware-engineering":["32014L0053","32014L0030","32014L0035","32023R1670","32023R1669","32023R1542","32011L0065","32024R1781","32023R0988","32019R1020","32006R1907","32012L0019","32024R2847"],
 "software-engineering":["32024R2847","32016R0679","32024R1689","32023R2854","32022L2555","32019R0881","32019L0882","32019L0770","32022R2065","32022R1925","32009L0024"]
};
const DEPARTMENT_TERMS = {
 smartphone:/smartphones?|mobile phones?|slate tablets?|energy labell?ing|ecodesign|batter(?:y|ies)|radio equipment|charging|usb type.c/i,
 wearables:/wearables?|smart watch|radio equipment|batter(?:y|ies)|wireless communication|medical devices|cyber resilience/i,
 "tablet-pc":/slate tablets?|computers?|notebooks?|displays?|ecodesign|energy labell?ing|charging|batter(?:y|ies)/i,
 "marketing-services":/consumer rights|unfair commercial|advertising|consumer protection|digital services|online platform|recall|repair|sales contracts/i,
 iot:/internet of things|connected products?|radio equipment|cyber resilience|data act|smart devices|networked standby/i,
 "smart-vehicle":/motor vehicles?|vehicle type.approval|automotive|vehicles? and their trailers|alternative fuels|traction batter/i,
 "integrated-delivery":/customs code|customs formalities|due diligence|forced labour|supply chain|waste shipments|packaging|market surveillance/i,
 "hardware-engineering":/radio equipment|electromagnetic compatibility|low voltage|ecodesign|batter(?:y|ies)|charging|hazardous substances|harmoni[sz]ed standards/i,
 "software-engineering":/cybersecurity|cyber resilience|artificial intelligence|data protection|personal data|software|digital content|data act|accessibility/i
};
function departmentRank(record,today,department=departmentView){
 const core=DEPARTMENT_CORE[department]||[];
 const i=core.indexOf(record.id);
 const status=statusFor(record,today);
 const valid=status!=="inactive";
 const law=record.sourceCategory==="EU_LEGISLATION";
 const title=record.title||"";
 const direct=DEPARTMENT_TERMS[department]?.test(title);
 const linked=core.some(id=>{const n=referenceNumber(id);return n&&title.includes(n);});
 const subordinate=/^(?:commission )?(?:delegated|implementing)\b/i.test(title);
 const minor=/\b(?:report|opinion|communication|recommendation|appointing|setting up|work programme)\b/i.test(title);
 if(law&&valid&&i>=0)return 10000-i*10;
 if(law&&valid&&(direct||linked))return (subordinate?650:800)+(linked?120:0)-(minor?150:0);
 if(law&&valid)return subordinate?350:450;
 if(law)return 100+(direct?30:0);
 return direct||linked?60:0;
}

function businessRank(record,today){
 const selected=departmentView||ui.department.value;
 if(selected&&DEPARTMENT_CORE[selected])return departmentRank(record,today,selected);
 return Math.max(0,...Object.keys(DEPARTMENT_CORE).map(id=>departmentRank(record,today,id)));
}
let sortExplicit=false;
function defaultSort(){return "relevance";}
function render() {
  if(!snapshot){ui["result-table"].hidden=true;ui.pagination.hidden=true;ui.empty.hidden=true;ui["result-count"].textContent=refreshError?"法规数据暂不可用":"正在载入法规数据";return;}
  const today=todayInBrussels(),terms=normalize(ui.search.value).split(" ").filter(Boolean);
  const filtered=records.filter(record=>matches(record,today,terms));
  filtered.sort((a,b)=>(ui.sort.value==="relevance"?searchRank(b,normalize(ui.search.value))-searchRank(a,normalize(ui.search.value))||(businessRank(b,today)-businessRank(a,today)):0)||(ui.sort.value==="oldest"?(a.published??"").localeCompare(b.published??""):(b.published??"").localeCompare(a.published??"")||b.id.localeCompare(a.id)));
  const lastPage=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));page=Math.min(page,lastPage);
  const start=(page-1)*PAGE_SIZE,visible=filtered.slice(start,start+PAGE_SIZE);
  ui["result-rows"].replaceChildren(...visible.map(record=>resultRow(record,today,[...terms,...normalize(ui["any-terms"].value).split(" ").filter(Boolean),...normalize(ui["exact-phrase"].value).split(" ").filter(Boolean)])));
  ui["result-table"].hidden=!visible.length;ui.empty.hidden=!!visible.length;
  ui["empty-title"].textContent="没有符合条件的资料";
  ui["empty-detail"].textContent="请尝试其他名称或编号关键词，或调整效力层级、业务部门及法律领域部门。";
  ui.pagination.hidden=lastPage<=1;ui["result-count"].textContent="匹配 "+numbers.format(filtered.length)+" 项 · 当前目录 "+numbers.format(records.length)+" 项";
  ui["page-count"].textContent="第 "+page+" / "+numbers.format(lastPage)+" 页";
  ui.previous.disabled=page===1;ui.next.disabled=page===lastPage;
}
ui.filters.addEventListener("submit",event=>{event.preventDefault();page=1;render();});
ui.type.addEventListener("change",()=>{updateActSubtypeOptions();page=1;render();});
ui.filters.addEventListener("reset",()=>{queueMicrotask(()=>{updateActSubtypeOptions();page=1;render();});});
updateActSubtypeOptions();
ui.search.addEventListener("input",()=>{if(!sortExplicit)ui.sort.value=defaultSort();page=1;render();});
ui.filters.addEventListener("input",()=>{page=1;render();});
ui.filters.addEventListener("change",()=>{page=1;render();});
ui.sort.addEventListener("change",()=>{sortExplicit=true;page=1;render();});
ui["clear-button"].addEventListener("click",()=>{ui.filters.reset();if(departmentView)ui.department.value=departmentView;sortExplicit=false;ui.sort.value=defaultSort();page=1;render();ui.search.focus();});
ui["recent-button"].addEventListener("click",async()=>{if(homeView){navigateModule("laws");return;}ui.filters.reset();if(departmentView)ui.department.value=departmentView;sortExplicit=false;ui.sort.value=defaultSort();page=1;await loadSnapshot(true);ui.catalog.scrollIntoView({behavior:"smooth",block:"start"});});
ui.previous.addEventListener("click",()=>{page=Math.max(1,page-1);render();});
ui.next.addEventListener("click",()=>{page+=1;render();});
ui["folder-select"].addEventListener("change",()=>{page=1;render();});
ui["new-folder"].addEventListener("click",()=>{const name=prompt("收藏文件夹名称")?.trim();if(name&&!folders.includes(name)){folders.push(name);persist();folderOptions();}});
ui["save-note"].addEventListener("click",()=>{if(!selectedRecord)return;favorites[selectedRecord.id]={folder:ui["record-folder"].value||folders[0],note:ui["record-note"].value};if(persist()){ui["record-dialog"].close();render();}});
showModule(activeView,departmentView,false);
loadSnapshot();
