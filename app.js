const STORAGE_KEY = 'hireloom-mvp-v1';
const AUTH_KEY = 'hireloom-local-accounts-v1';
const VOICE_LANGUAGE_KEY = 'hireloom-voice-language-v1';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value = '') => String(value).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const toList = (value) => String(value || '').split(',').map((part) => part.trim()).filter(Boolean);

const jobs = [
  { id:'python', title:'Senior Python Developer', company:'Northstar Labs', location:'Berlin, Germany', mode:'Remote', eligible:['Germany','European Union'], languages:['English'], source:'Native', route:'Apply on Hireloom', posted:'2 days ago', years:'3+ years', match:86, skills:['Python','SQL','REST APIs','AWS'], description:'Build reliable Python services and data integrations with a distributed product team. Work from Germany with a remote-first group across Europe.', highlights:['Own backend services and API integrations','Partner with product and data teams','Improve observability and deployment workflows'], reason:'Your Python and SQL background maps closely to the core stack. The role is remote from Germany and uses English day to day.' },
  { id:'backend', title:'Backend Engineer (Python)', company:'Juniper Systems', location:'Munich, Germany', mode:'Hybrid', eligible:['Germany'], languages:['English','German'], source:'Native', route:'Apply on Hireloom', posted:'4 days ago', years:'2+ years', match:81, skills:['Python','SQL','Docker','APIs'], description:'Join a small platform team building services for a growing European marketplace. The team meets in Munich twice a week.', highlights:['Ship Python backend features','Work with Docker based services','Collaborate in English and German'], reason:'Strong overlap in Python and SQL with a good match to your experience. Hybrid work is available in Munich.' },
  { id:'platform', title:'Data Platform Engineer', company:'Mosaic Cloud', location:'Remote (EU)', mode:'Remote', eligible:['Germany','Netherlands','France','Spain','European Union'], languages:['English'], source:'External', route:'Assisted apply', posted:'1 week ago', years:'3+ years', match:78, skills:['Python','SQL','Airflow','AWS'], description:'Help operate the data platform behind a suite of B2B products. This remote role is open to candidates based in Germany and the EU.', highlights:['Maintain batch and streaming pipelines','Improve data quality checks','Work with analytics and engineering'], reason:'Your Python and SQL experience fits the platform work. Airflow is a gap to review, and Germany is an eligible remote location.' },
  { id:'analytics', title:'Analytics Engineer', company:'Kindred Market', location:'Berlin, Germany', mode:'Hybrid', eligible:['Germany'], languages:['English','German'], source:'External', route:'Assisted apply', posted:'1 week ago', years:'2+ years', match:76, skills:['SQL','dbt','Python','Looker'], description:'Turn product and operations data into dependable models and dashboards. Berlin based with a flexible hybrid schedule.', highlights:['Develop analytics models in SQL','Partner on metric definitions','Maintain reporting dashboards'], reason:'Your SQL and Python skills cover important parts of the role. dbt and Looker are listed as gaps.' },
  { id:'data-python', title:'Python Data Developer', company:'Orbit Commerce', location:'Remote (Germany)', mode:'Remote', eligible:['Germany'], languages:['English'], source:'Native', route:'Apply on Hireloom', posted:'2 weeks ago', years:'2+ years', match:74, skills:['Python','SQL','ETL','Data pipelines'], description:'Create and maintain data utilities for a commerce analytics team. Remote within Germany with asynchronous collaboration.', highlights:['Write maintainable Python jobs','Improve existing data pipelines','Document and monitor data quality'], reason:'Your Python and SQL experience aligns well with the core requirements. The role is remote within Germany.' },
  { id:'ml-pipeline', title:'ML Pipeline Engineer', company:'Sonder AI', location:'Munich, Germany', mode:'Onsite', eligible:['Germany'], languages:['English','German'], source:'External', route:'Assisted apply', posted:'2 weeks ago', years:'3+ years', match:69, skills:['Python','Machine learning','Kubernetes','MLflow'], description:'Build repeatable pipelines for model training and deployment. The team works from its Munich office.', highlights:['Build Python model pipelines','Support model deployment','Partner with applied research'], reason:'Python experience is relevant, while MLflow and Kubernetes are gaps. This position is onsite in Munich.' },
  { id:'data-analyst', title:'Product Data Analyst', company:'Common Ground', location:'Berlin, Germany', mode:'Hybrid', eligible:['Germany'], languages:['English'], source:'Native', route:'Apply on Hireloom', posted:'3 days ago', years:'2+ years', match:73, skills:['SQL','Product analytics','Tableau','Python'], description:'Help product teams understand activation and retention through trusted analysis. Berlin office with two shared days a week.', highlights:['Explore product usage patterns','Build clear analyses for decision makers','Maintain self-serve dashboards'], reason:'Your SQL and Python foundation transfers well. Product analytics and Tableau experience would strengthen the fit.' },
  { id:'junior-ml', title:'Junior Machine Learning Analyst', company:'Linden Research', location:'Remote (EU)', mode:'Remote', eligible:['Germany','European Union'], languages:['English'], source:'External', route:'Assisted apply', posted:'5 days ago', years:'1+ years', match:71, skills:['Python','Machine learning','SQL','Jupyter'], description:'Support experimentation and data preparation for a small applied machine learning group. Remote within the EU.', highlights:['Prepare datasets for model experiments','Analyze results with Python','Share findings with the team'], reason:'Python and SQL are a useful base for this early-career role. Machine learning experience is a gap to review.' }
];

const defaultProfile = () => ({
  name:'Arjun Mehta', email:'arjun@example.com', phone:'+91 98765 43210', location:'Bengaluru, India', gender:'', dob:'',
  title:'Data Engineer', summary:'Data engineer with three years of experience building reporting pipelines.',
  education:'B.Tech, Computer Science · 2021–2025', experience:[{ title:'Data Engineer', company:'Company A', dates:'2023 to now', detail:'Built Python jobs and SQL reporting pipelines.' }],
  skills:['Python','SQL','Data pipelines'], achievements:[], certifications:[], roles:['Data Engineer','Analytics Engineer'], interestedLocation:'Berlin, Munich, Remote in Germany',
  workModes:['Remote','Hybrid'], scope:'Both', languages:'English (Fluent), German (Intermediate)', relocation:'Open to relocation within Germany',
  salary:'70,000 EUR / year', currentSalary:'60,000 EUR / year', cvName:'Arjun_Mehta_CV.pdf', cvStatus:'Profile confirmed · demo CV',
  answers:{}, cvVersion:1
});

function makeSearchTurn(query,id=`turn-${Date.now()}`) {
  return {id,query,status:'unloaded',response:'',jobs:[],sources:[],totalResults:0,resultsCaptured:false,createdAt:new Date().toISOString()};
}

function initialState() {
  const profile = defaultProfile();
  return {
    profile,
    chats:[
      { id:'seed-remote', title:'Remote Python jobs', date:'Today', query:'Remote Python jobs, English, 2+ years experience', hasSearch:true, turns:[makeSearchTurn('Remote Python jobs, English, 2+ years experience','seed-remote-turn-1')] },
      { id:'seed-analyst', title:'Data analyst, hybrid, Berlin', date:'Yesterday', query:'Data analyst, hybrid, Berlin', hasSearch:true, turns:[makeSearchTurn('Data analyst, hybrid, Berlin','seed-analyst-turn-1')] },
      { id:'seed-ml', title:'Junior ML roles, English speaking', date:'Last week', query:'Junior ML roles, English speaking', hasSearch:true, turns:[makeSearchTurn('Junior ML roles, English speaking','seed-ml-turn-1')] }
    ],
    activeChatId:'seed-remote', view:'login', selectedJobId:null, profileTab:'about', settingsTab:'account', trackerFilter:'All',
    applications:[], savedJobs:[], cvVersions:[], settings:{newMatches:true, reminders:true, autoApply:false},
    tailoringJobId:null, tailoredEdits:null, sidebarOpen:false, loggedOut:true
  };
}

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!parsed || !parsed.profile || !Array.isArray(parsed.chats)) return initialState();
    const chats=parsed.chats.map((stored)=>{
      const chat=stored.id==='seed-remote'&&stored.query==='Remote Python jobs in Germany, English, 2+ years experience'?{...stored,title:'Remote Python jobs',query:'Remote Python jobs, English, 2+ years experience'}:stored;
      const turns=Array.isArray(chat.turns)&&chat.turns.length?chat.turns.map((turn,index)=>({...makeSearchTurn(turn.query||'',turn.id||`${chat.id}-turn-${index+1}`),...turn,status:turn.resultsCaptured?(turn.status==='error'?'error':'ready'):'unloaded',jobs:Array.isArray(turn.jobs)?turn.jobs:[],sources:Array.isArray(turn.sources)?turn.sources:[]})):(chat.hasSearch&&chat.query?[makeSearchTurn(chat.query,`${chat.id}-turn-1`)]:[]);
      const latest=turns[turns.length-1];
      return {...chat,turns,query:latest?.query||chat.query||'',hasSearch:turns.length>0};
    });
    return { ...initialState(), ...parsed, chats, view:'login', loggedOut:true, profile:{ ...defaultProfile(), ...parsed.profile }, settings:{ ...initialState().settings, ...(parsed.settings || {}) } };
  } catch { return initialState(); }
}
let state = loadState();
let session=false;
function loadAuth() {
  try {
    const value=JSON.parse(localStorage.getItem(AUTH_KEY));
    return value&&Array.isArray(value.accounts)?value:{accounts:[],lastEmail:''};
  } catch { return {accounts:[],lastEmail:''}; }
}
let authData=loadAuth(), authMode='login', authMessage='', authDraft={name:'',email:''};
let liveSearch={chatId:null,turnId:null,query:'',status:'idle',jobs:[],sources:[]};
let pendingDeleteChatId=null;
const liveSearchByTurn=new Map();
const liveSearchRequestByTurn=new Map();
let liveSearchSequence=0;
const voiceLanguageOptions=[
  ['en-IN','English (India)'],['en-GB','English (UK)'],['en-US','English (US)'],
  ['de-DE','German (Germany)'],['hi-IN','Hindi (India)'],['en-IN-mixed','English + Hindi (best effort)']
];
let voiceLanguage=(()=>{try{return voiceLanguageOptions.some(([value])=>value===localStorage.getItem(VOICE_LANGUAGE_KEY))?localStorage.getItem(VOICE_LANGUAGE_KEY):'en-IN';}catch{return 'en-IN';}})();
let voiceState={status:'idle',recognition:null,transcript:'',interim:'',message:'',queryDraft:'',lowConfidence:false};

function saveAuth() { localStorage.setItem(AUTH_KEY,JSON.stringify(authData)); }
function normalizeEmail(value) { return String(value||'').trim().toLowerCase(); }
function toHex(bytes) { return [...new Uint8Array(bytes)].map(value=>value.toString(16).padStart(2,'0')).join(''); }
function fromHex(value) { return new Uint8Array(String(value).match(/.{2}/g).map(pair=>parseInt(pair,16))); }
async function passwordHash(password,salt,iterations=210000) {
  if(!globalThis.crypto?.subtle)throw new Error('Password setup needs a secure HTTPS connection or the local Hireloom server.');
  const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits']);
  const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations,hash:'SHA-256'},material,256);
  return toHex(bits);
}
function sameHash(a,b) {
  if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;
  let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0;
}

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  catch { toast('Could not save this change in your browser storage.', 'error'); }
}
function getChat() { return state.chats.find((chat) => chat.id === state.activeChatId) || state.chats[0]; }
function getJob(id) { return jobs.find((job) => job.id === id) || liveSearch.jobs.find((job) => job.id === id) || [...liveSearchByTurn.values()].flatMap((search) => search.jobs || []).find((job) => job.id === id) || state.chats.flatMap((chat)=>chat.turns||[]).flatMap((turn)=>turn.jobs||[]).find((job)=>job.id===id); }
function normalizeSkill(skill) {
  const aliases = { js:'JavaScript', javascript:'JavaScript', 'data pipelines':'Data pipelines', 'rest apis':'REST APIs', api:'APIs', 'machine learning':'Machine learning', ml:'Machine learning', 'product analytics':'Product analytics' };
  return aliases[String(skill).trim().toLowerCase()] || String(skill).trim();
}
function matchingSkills(job) {
  const mine = state.profile.skills.map((skill) => normalizeSkill(skill).toLowerCase());
  return job.skills.filter((skill) => mine.includes(normalizeSkill(skill).toLowerCase()));
}
function missingSkills(job) { const matched = matchingSkills(job); return job.skills.filter((skill) => !matched.includes(skill)); }
const locationAliases = [
  ['United States',['united states','usa','us','new york','san francisco','los angeles','seattle','austin','boston','chicago','denver','atlanta','portland']],['United Kingdom',['united kingdom','uk','britain','england','london','manchester','edinburgh','birmingham','bristol','glasgow']],
  ['Germany',['germany','berlin','munich','münchen','hamburg','frankfurt','cologne','köln','stuttgart','dusseldorf','düsseldorf']],
  ['India',['india','bengaluru','bangalore','mumbai','delhi','new delhi','hyderabad','chennai','pune','kolkata','ahmedabad','jaipur','indore','kochi','noida','gurgaon','gurugram','lucknow','chandigarh','coimbatore']],
  ['Canada',['canada','toronto','vancouver','montreal','ottawa','calgary']],['Australia',['australia','sydney','melbourne','brisbane','perth']],
  ['Netherlands',['netherlands','amsterdam','rotterdam','utrecht']],['France',['france','paris','lyon','marseille']],
  ['Spain',['spain','madrid','barcelona','valencia']],['Ireland',['ireland','dublin']],['Italy',['italy','rome','milan']],
  ['Singapore',['singapore']],['Sweden',['sweden','stockholm']],['Denmark',['denmark','copenhagen']],
  ['Norway',['norway','oslo']],['Poland',['poland','warsaw','krakow']],['Portugal',['portugal','lisbon','porto']],
  ['Belgium',['belgium','brussels']],['Austria',['austria','vienna']],['Switzerland',['switzerland','zurich','geneva']],
  ['United Arab Emirates',['united arab emirates','uae','dubai','abu dhabi']],['Argentina',['argentina','buenos aires']],['Brazil',['brazil','sao paulo','são paulo','rio de janeiro']],
  ['Bangladesh',['bangladesh','dhaka']],['Bahrain',['bahrain','manama']],['Bulgaria',['bulgaria','sofia']],['China',['china','beijing','shanghai','shenzhen','guangzhou']],
  ['Colombia',['colombia','bogota','bogotá','medellin']],['Costa Rica',['costa rica','san jose','san josé']],['Czechia',['czechia','czech republic','prague']],
  ['Egypt',['egypt','cairo']],['Finland',['finland','helsinki']],['Ghana',['ghana','accra']],['Greece',['greece','athens']],['Hong Kong',['hong kong']],
  ['Hungary',['hungary','budapest']],['Indonesia',['indonesia','jakarta']],['Israel',['israel','tel aviv','jerusalem']],['Japan',['japan','tokyo','osaka','kyoto']],
  ['Kenya',['kenya','nairobi']],['South Korea',['south korea','korea','seoul']],['Kuwait',['kuwait','kuwait city']],['Sri Lanka',['sri lanka','colombo']],
  ['Lithuania',['lithuania','vilnius']],['Luxembourg',['luxembourg','luxembourg city']],['Latvia',['latvia','riga']],['Morocco',['morocco','casablanca','rabat']],
  ['Mexico',['mexico','mexico city','guadalajara']],['Malaysia',['malaysia','kuala lumpur']],['Nigeria',['nigeria','lagos','abuja']],['Nepal',['nepal','kathmandu']],
  ['New Zealand',['new zealand','auckland','wellington']],['Oman',['oman','muscat']],['Peru',['peru','lima']],['Philippines',['philippines','manila']],
  ['Pakistan',['pakistan','karachi','lahore','islamabad']],['Qatar',['qatar','doha']],['Romania',['romania','bucharest']],['Russia',['russia','moscow']],
  ['Saudi Arabia',['saudi arabia','riyadh','jeddah']],['South Africa',['south africa','cape town','johannesburg','durban']],['Slovenia',['slovenia','ljubljana']],
  ['Slovakia',['slovakia','bratislava']],['Thailand',['thailand','bangkok']],['Tunisia',['tunisia','tunis']],['Türkiye',['türkiye','turkey','istanbul','ankara']],
  ['Taiwan',['taiwan','taipei']],['Ukraine',['ukraine','kyiv','kiev']],['Chile',['chile','santiago']],['Ecuador',['ecuador','quito']],['Estonia',['estonia','tallinn']],
  ['Croatia',['croatia','zagreb']],['Iceland',['iceland','reykjavik']],['Iraq',['iraq','baghdad']],['Uruguay',['uruguay','montevideo']],
  ['Venezuela',['venezuela','caracas']],['Vietnam',['vietnam','hanoi','ho chi minh city','saigon']],['Zambia',['zambia','lusaka']],['Zimbabwe',['zimbabwe','harare']],
  ['European Union',['european union','eu']],['Europe',['europe']],['Worldwide',['worldwide','anywhere','global']]
];
const countryTermAliases={'united states':['usa','us'],'united kingdom':['uk','britain','england'],'european union':['eu']};
const locationNoiseWords = /\b(?:remote|hybrid|onsite|on-site|in-office|jobs?|roles?|positions?|work|opportunities|opening|openings|for|with|that|paying|salary|experience|years?|yrs?)\b/i;
function cleanLocationTerm(value) {
  return String(value||'').replace(/^\s*(?:remote\s+)?(?:in|near|around)\s+/i,'').replace(/^remote\s+/i,'').trim().replace(/[.!?]+$/,'');
}
function splitLocationTerms(value) {
  return String(value||'').split(/[,;|/]|\s+(?:or|and)\s+/i).map(cleanLocationTerm).filter(Boolean);
}
function queryLocationTerms(query) {
  const q=` ${normalizedLocation(query)} `;
  const recognized=locationAliases.flatMap(([,aliases])=>aliases.filter(alias=>q.includes(` ${normalizedLocation(alias)} `)));
  const match=String(query||'').match(/\b(?:in|near|around|based\s+in|located\s+in)\s+(.+?)(?=\s+\b(?:remote|hybrid|onsite|on-site|english|german|french|spanish|hindi|junior|senior|for|with|jobs?|roles?|positions?|experience|years?)\b|[,;.!?]|$)/i);
  let explicit=[];
  if(match){const candidate=cleanLocationTerm(match[1]);const refersToProfile=/^(?:me|here|my\s+(?:current\s+)?location|my\s+area|where\s+i\s+am)$/i.test(candidate);if(candidate&&!refersToProfile&&!locationNoiseWords.test(candidate)&&!/\b(?:software|data|product|backend|front[- ]?end|engineering|analytics|design|marketing|finance|machine learning|ai|cybersecurity|developer|engineer|analyst)\b/i.test(candidate))explicit=splitLocationTerms(candidate);}
  return [...new Set([...explicit,...recognized])];
}
function profileLocationTerms() {
  const preferred=splitLocationTerms(state.profile.interestedLocation||'');
  const current=splitLocationTerms(state.profile.location||'');
  return [...new Set([...preferred,...current])];
}
function effectiveLocationTerms(query) {
  return queryLocationTerms(query).length?queryLocationTerms(query):profileLocationTerms();
}
function normalizedLocation(value) { return String(value||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim(); }
function locationMatches(job, terms) {
  if(!terms?.length)return true;
  const location=normalizedLocation(job.location), eligible=(job.eligible||[]).map(normalizedLocation);
  const contains=(text,term)=>Boolean(text&&term&&` ${text} `.includes(` ${term} `));
  return terms.some((term)=>{
    const wanted=normalizedLocation(term);
    if(!wanted)return false;
    if(job.mode==='Remote'&&eligible.includes('worldwide'))return true;
    if(contains(location,wanted)||eligible.some((item)=>contains(item,wanted)))return true;
    const country=locationAliases.find(([,aliases])=>aliases.some((alias)=>normalizedLocation(alias)===wanted))?.[0];
    if(!country)return false;
    const normalizedCountry=normalizedLocation(country);
    const isCountryTerm=wanted===normalizedCountry||(countryTermAliases[normalizedCountry]||[]).some((alias)=>normalizedLocation(alias)===wanted);
    const europeCountries=['germany','netherlands','france','spain','italy','ireland','sweden','denmark','norway','poland','portugal','belgium','austria'];
    return eligible.some((item)=>{
      if(item==='worldwide'&&job.mode==='Remote')return true;
      if(item===normalizedCountry&&(isCountryTerm||job.mode==='Remote'))return true;
      if(isCountryTerm&&(normalizedCountry==='european union'||normalizedCountry==='europe')&&item===normalizedCountry)return true;
      if(!isCountryTerm&&job.mode!=='Remote')return false;
      return (item==='europe'&&europeCountries.includes(normalizedCountry))||(item==='european union'&&europeCountries.includes(normalizedCountry));
    });
  });
}
function profileAllowsJob(job, locationTerms) {
  const p=state.profile;
  if(p.workModes?.length && job.mode!=='Flexible' && !p.workModes.includes(job.mode))return false;
  if(!locationMatches(job,locationTerms))return false;
  const languages=(String(p.languages||'').match(/English|German|French|Spanish|Hindi|Italian|Dutch/gi)||[]).map((value)=>value.toLowerCase());
  if(languages.length && job.languages?.length && !job.languages.some((language)=>languages.includes(language.toLowerCase())))return false;
  return true;
}
function matchScore(job) {
  const coverage = job.skills.length ? matchingSkills(job).length / job.skills.length : 0;
  const skillShift = Math.round((coverage - .5) * 8);
  const mode = state.profile.workModes.includes(job.mode) || state.profile.workModes.length === 0 ? 0 : -6;
  return Math.min(97, Math.max(48, job.match + skillShift + mode));
}
function atsScore() {
  let score = 67;
  if (state.profile.name) score += 4;
  if (state.profile.email) score += 4;
  if (state.profile.phone) score += 3;
  if (state.profile.experience?.length) score += 8;
  if (state.profile.education) score += 5;
  if (state.profile.skills?.length >= 3) score += 7;
  return Math.min(98, score);
}
function tokensForSearch(query) { return String(query).toLowerCase().replace(/\b\d+\+?\s*(years?|yrs?)\b/g,' ').match(/[a-z][a-z0-9+#.-]*/g) || []; }
function jobsForQuery(query,catalogOverride) {
  const q = String(query || '').toLowerCase();
  const catalog=Array.isArray(catalogOverride)?catalogOverride:jobs;
  const mode = q.includes('remote') ? 'Remote' : q.includes('hybrid') ? 'Hybrid' : q.includes('onsite') || q.includes('on-site') ? 'Onsite' : null;
  const locations=effectiveLocationTerms(query);
  const language = ['german','english','french','spanish'].find((lang) => q.includes(lang));
  const locationTokens=new Set(locations.flatMap(tokensForSearch));
  let tokens = tokensForSearch(query).filter((word) => !locationTokens.has(word) && !['remote','hybrid','onsite','on','site','in','the','and','with','jobs','job','roles','role','years','year','english','german','french','spanish','speaking','junior','senior'].includes(word));
  if (q.includes('junior')) tokens.push('junior');
  if (q.includes('senior')) tokens.push('senior');
  const ranked = catalog.map((job) => {
    if (!profileAllowsJob(job,locations)) return { job, score:-1 };
    if (mode && job.mode !== mode) return { job, score:-1 };
    if (language && job.languages?.length && !job.languages.some((value) => value.toLowerCase() === language)) return { job, score:-1 };
    const haystack = `${job.title} ${job.company} ${job.skills.join(' ')} ${job.description}`.toLowerCase();
    const keywordScore = tokens.reduce((score, token) => score + (haystack.includes(token) ? 2 : 0), 0);
    const roleBonus = q.includes('data analyst') && /analyst/i.test(job.title) ? 4 : 0;
    const mlBonus = q.includes('ml') && /machine learning|ml/i.test(`${job.title} ${job.skills.join(' ')}`) ? 5 : 0;
    return { job, score:keywordScore + roleBonus + mlBonus + matchScore(job) / 100 };
  });
  return ranked.filter((entry) => entry.score >= 0).sort((a,b) => b.score-a.score).map((entry) => entry.job);
}
function snapshotJob(job) {
  return {...job,fitScore:matchScore(job),description:String(job.description||'').slice(0,900),highlights:(job.highlights||[]).slice(0,3).map((value)=>String(value).slice(0,220)),skills:(job.skills||[]).slice(0,12)};
}
function latestTurn(chat=getChat()) { return chat?.turns?.[chat.turns.length-1]||null; }
function latestQuery() { return getChat()?.query || ''; }
function formatDate(iso) { try { return new Date(iso).toLocaleDateString(undefined,{day:'numeric',month:'short'}); } catch { return iso; } }
function initials(name) { return String(name || 'You').trim().split(/\s+/).slice(0,2).map((part) => part[0]).join('').toUpperCase() || 'Y'; }
function updateShell() {
  const p = state.profile;
  $('#sidebar-name').textContent = p.name || 'Your profile';
  $('#sidebar-avatar').textContent = initials(p.name);
  $('#menu-name').textContent = p.name || 'Your profile';
  $('#menu-email').textContent = p.email || 'No email added';
  $('#avatar-menu-button').textContent = initials(p.name);
  $('#tracker-count').textContent = state.applications.length;
  $$('.nav-link').forEach((button) => button.classList.toggle('active', (state.view === 'tracker' && button.dataset.nav === 'tracker') || (state.view !== 'tracker' && button.dataset.nav === 'chat')));
  $('#account-menu').classList.add('hidden');
  $$('.chat-item').forEach((button) => button.classList.toggle('active', button.dataset.chatId === state.activeChatId));
  $('#chat-list').innerHTML = state.chats.map((chat) => `<div class="chat-row"><button class="chat-item ${chat.id === state.activeChatId ? 'active' : ''}" data-chat-id="${esc(chat.id)}" title="${esc(chat.title)}">${esc(chat.title)}<small>${esc(chat.date || 'Today')}</small></button><button class="chat-delete-button" data-action="delete-chat" data-id="${esc(chat.id)}" aria-label="Delete chat: ${esc(chat.title)}" title="Delete chat">×</button></div>`).join('');
  $('#sidebar').classList.toggle('open', state.sidebarOpen);
}
function render() {
  updateShell();
  const loggedOut=state.view==='login';
  $('.app-shell').classList.toggle('logged-out',loggedOut);
  const content = $('#content'); content.innerHTML = renderView(); attachViewEvents();
}

function renderView() {
  switch (state.view) {
    case 'chat': return renderChat();
    case 'job': return renderJobDetail();
    case 'profile': return renderProfile();
    case 'tailor': return renderTailoring();
    case 'tracker': return renderTracker();
    case 'settings': return renderSettings();
    case 'plans': return renderPlans();
    case 'login': return authMode==='signup'?renderSignup():renderLogin();
    default: return renderChat();
  }
}

function renderLogin() {
  return `<section class="logged-out-wrap"><a class="brand logged-out-brand" href="#"><span class="brand-mark"><span></span><span></span><span></span><span></span></span><span>hireloom</span></a><div class="card logged-out-card"><span class="eyebrow">Your next role, on your terms</span><h1>Welcome back</h1><p class="subhead">Log in to your Hireloom workspace.</p>${authMessage?`<p class="auth-message">${esc(authMessage)}</p>`:''}<form id="login-form" class="login-form"><div class="field"><label for="login-email">Email</label><input id="login-email" name="email" type="email" value="${esc(authData.lastEmail)}" placeholder="you@example.com" autocomplete="email" required /></div><div class="field"><label for="login-password">Password</label><div class="password-input"><input id="login-password" name="password" type="password" autocomplete="current-password" required /><button type="button" data-action="toggle-password" data-id="login-password">Show</button></div></div><button class="primary-button login-submit">Log in</button></form><p class="login-switch">New to Hireloom? <button class="text-button" data-action="show-signup">Create an account</button></p><p class="login-note"><strong>Local demo account:</strong> your email and salted password hash stay in this browser. No data is sent to an auth service.</p></div><p class="logged-out-note">Your profile and tracker remain saved in this browser between sessions.</p></section>`;
}

function renderSignup() {
  return `<section class="logged-out-wrap"><a class="brand logged-out-brand" href="#"><span class="brand-mark"><span></span><span></span><span></span><span></span></span><span>hireloom</span></a><div class="card logged-out-card"><span class="eyebrow">Start your search</span><h1>Create your account</h1><p class="subhead">Set up a local Hireloom demo account.</p>${authMessage?`<p class="auth-message">${esc(authMessage)}</p>`:''}<form id="signup-form" class="login-form"><div class="field"><label for="signup-name">Full name</label><input id="signup-name" name="name" value="${esc(authDraft.name)}" autocomplete="name" required /></div><div class="field"><label for="signup-email">Email</label><input id="signup-email" name="email" type="email" value="${esc(authDraft.email||authData.lastEmail)}" placeholder="you@example.com" autocomplete="email" required /></div><div class="field"><label for="signup-password">Password</label><div class="password-input"><input id="signup-password" name="password" type="password" minlength="8" autocomplete="new-password" required /><button type="button" data-action="toggle-password" data-id="signup-password">Show</button></div><small>Use at least 8 characters.</small></div><div class="field"><label for="signup-confirm">Confirm password</label><div class="password-input"><input id="signup-confirm" name="confirm" type="password" minlength="8" autocomplete="new-password" required /><button type="button" data-action="toggle-password" data-id="signup-confirm">Show</button></div></div><label class="consent-row"><input type="checkbox" name="localConsent" required /> <span>I understand this demo saves my profile and a password hash in this browser.</span></label><button class="primary-button login-submit">Create account</button></form><p class="login-switch">Already have an account? <button class="text-button" data-action="show-login">Log in</button></p><p class="login-note">This creates a local demo account only. There is no email verification or account recovery.</p></div></section>`;
}

function renderJobCard(job,scoreOverride) {
  const score = Number.isFinite(scoreOverride)?scoreOverride:Number.isFinite(job.fitScore)?job.fitScore:matchScore(job);
  const saved = state.savedJobs.includes(job.id);
  return `<article class="job-card">
    <div class="job-card-top"><div><button class="job-title-button" data-job="${job.id}">${esc(job.title)}</button><div class="company-line">${esc(job.company)} <span>·</span> ${esc(job.location)}</div></div><div class="fit-badge"><strong>${score}</strong><small>FIT</small></div></div>
    <div class="job-card-bottom"><div class="tag-row"><span class="tag ${job.mode==='Remote'?'green':''}">${esc(job.mode)}</span>${job.isLive?`<a class="tag" href="${esc(job.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(job.source)}</a>`:`<span class="tag">${esc(job.source)}</span>`}<span class="tag">Posted ${esc(job.posted)}</span></div><div class="job-actions"><button class="save-job ${saved?'saved':''}" data-action="save-job" data-id="${job.id}" aria-label="${saved?'Remove saved job':'Save job'}">${saved?'♥':'♡'}</button><button class="text-button" data-job="${job.id}">View job <span>↗</span></button></div></div>
  </article>`;
}

function renderVoicePanel() {
  if(voiceState.status==='idle')return '';
  const listening=voiceState.status==='listening';
  const transcript=[voiceState.transcript,voiceState.interim].filter(Boolean).join(' ').trim();
  const copy=listening?'Listening now. Speak naturally, then stop when you’re done.':voiceState.message;
  const content=listening?(transcript||'Listening for speech…'):voiceState.status==='review'?(voiceState.transcript||voiceState.queryDraft):'Type your search or try voice input again.';
  return `<div class="voice-panel ${listening?'listening':voiceState.status==='error'?'error':'review'}" id="voice-panel" role="status" aria-live="polite"><div class="voice-panel-heading"><span class="voice-indicator ${listening?'active':''}"></span><strong>${listening?'Listening':voiceState.status==='review'?'Review your transcript':'Voice search'}</strong></div><p class="voice-panel-copy" id="voice-message">${esc(copy)}</p><p class="voice-transcript" id="voice-transcript">${esc(content)}</p><div class="voice-panel-actions">${listening?'<button class="secondary-button" type="button" data-action="voice-stop">Stop listening</button>':voiceState.status==='error'?'<button class="secondary-button" type="button" data-action="voice-retry">Try again</button>':''}<button class="text-button" type="button" data-action="voice-cancel">${listening?'Cancel':'Dismiss'}</button></div></div>`;
}

function renderConversationTurn(turn,index,count) {
  const search=liveSearchByTurn.get(turn.id),status=search?.status||turn.status;
  const searching=status==='loading'||status==='unloaded';
  const liveReady=status==='ready',feedFailed=status==='error';
  const results=turn.resultsCaptured?turn.jobs:(liveReady?jobsForQuery(turn.query,search?.jobs||[]):[]);
  const feedNames=(turn.sources?.length?turn.sources:search?.sources||[]).filter((source)=>source.ok).map((source)=>source.name);
  const latest=index===count-1;
  const response=turn.response||(liveReady?'Here are the closest matching roles I found.':feedFailed?'I couldn’t reach the live job feeds for this search. You can retry it.':'I’m searching current listings for this request.');
  return `<section class="conversation-turn"><div class="message-row user"><div class="message-bubble">${esc(turn.query)}</div></div><div class="message-row assistant"><div class="assistant-response"><span class="assistant-name">Hireloom</span><div class="message-bubble assistant-bubble">${searching?'<span class="typing-indicator">Searching current listings…</span>':esc(response)}</div></div></div>
    ${searching?`<div class="empty-state turn-loading"><div class="empty-icon">⌕</div><h3>Finding roles for this prompt…</h3><p>Checking current listings while keeping your earlier messages here.</p></div>`:`<div class="result-head"><span><strong>${Number(turn.totalResults??results.length)} ${Number(turn.totalResults??results.length)===1?'role':'roles'}</strong> ${liveReady?`from live feeds${feedNames.length?` · ${esc(feedNames.join(' + '))}`:''}, ranked by fit`:feedFailed?'live feeds unavailable':'matching roles'}</span><div>${latest?`<button class="text-button" data-action="edit-search">Refine with a new prompt</button>${feedFailed?` <button class="text-button" data-action="rerun-search">Retry</button>`:''}`:''}</div></div>
    ${results.length?`<div class="result-list">${results.map((job)=>renderJobCard(job,job.fitScore)).join('')}</div>`:`<div class="empty-state"><div class="empty-icon">⌕</div><h3>${feedFailed?'Live job feeds are unavailable':liveReady?'No live listings matched this prompt':'No roles matched this prompt'}</h3><p>${feedFailed?'Check your internet connection and retry this prompt.':'Try another title, location, or work mode in a follow-up prompt.'}</p>${liveReady?'<span class="assistant-caption">Listings can change. Confirm details on the original source before applying.</span>':''}</div>`}`}
  </section>`;
}

function renderChat() {
  const chat=getChat(),turns=chat?.turns||[],hasSearch=turns.length>0,query=chat?.query||'';
  const filters=[];
  if(/remote/i.test(query))filters.push('Remote');else if(/hybrid/i.test(query))filters.push('Hybrid');
  if(/germany/i.test(query))filters.push('Germany');else if(/berlin/i.test(query))filters.push('Berlin');
  if(/english/i.test(query))filters.push('English');
  return `<div class="chat-layout"><section class="chat-main">
    <div class="chat-heading"><span class="eyebrow">A calmer way to find your next role</span><h1>Good work starts with a good fit.</h1><p>Tell me what you’re looking for. I’ll bring the right roles into one place.</p></div>
    <div class="conversation">
      ${hasSearch?turns.map((turn,index)=>renderConversationTurn(turn,index,turns.length)).join(''):`<div class="assistant-intro"><div class="empty-icon">✳</div><h2>What job should we look for?</h2><p>Type a search in your own words, or start with one of these.</p><div class="suggestion-list"><button class="suggestion-chip" data-query="Remote Python jobs in Germany, English, 2+ years experience">Remote Python jobs in Germany</button><button class="suggestion-chip" data-query="Data analyst, hybrid, Berlin">Data analyst, hybrid, Berlin</button><button class="suggestion-chip" data-query="Junior ML roles, English speaking">Junior ML roles, English speaking</button></div><span class="assistant-caption">Your confirmed profile helps make the matches more useful.</span></div>`}
    </div>
    <div class="composer-wrap"><div class="filters-row">${(filters.length?filters:['Work mode','Location','Language']).map((filter)=>`<button class="filter-pill" data-action="filter-chip" data-filter="${esc(filter)}">${esc(filter)}${filter==='Work mode'||filter==='Location'||filter==='Language'?' ▾':''}</button>`).join('')}<button class="filter-pill" data-action="more-filters">＋ More filters</button><label class="voice-language-control"><span>Voice</span><select id="voice-language" aria-label="Voice search language">${voiceLanguageOptions.map(([value,label])=>`<option value="${value}" ${voiceLanguage===value?'selected':''}>${esc(label)}</option>`).join('')}</select></label></div>
      ${renderVoicePanel()}
      <form class="composer" id="search-form"><input id="search-query" name="query" value="${esc(voiceState.status==='review'?voiceState.queryDraft:voiceState.baseQuery||'')}" aria-label="Describe the job you want" placeholder="Ask a follow-up or search another role" autocomplete="off" /><button class="secondary-button voice-button ${voiceState.status==='listening'?'is-listening':''}" type="button" data-action="voice-search" aria-label="${voiceState.status==='listening'?'Listening; tap to stop':'Start voice search'}" aria-pressed="${voiceState.status==='listening'}">◉ <span>${voiceState.status==='listening'?'Listening':'Speak'}</span></button><button class="primary-button" type="submit">Send <span>↗</span></button></form>
      <p class="assistant-caption">Search text and location are sent to Hireloom for matching, but not to job providers. Profile data is not sent to job providers. Uploaded CVs are sent to the Hireloom server for in-memory parsing and are not retained. Your browser may use its speech service to transcribe voice; Hireloom does not save audio.</p>
    </div>
  </section></div>`;
}

function renderJobDetail() {
  const job = getJob(state.selectedJobId);
  if (!job) { state.view='chat'; return renderChat(); }
  const matched = matchingSkills(job), missing = missingSkills(job), score = matchScore(job), readiness = atsScore();
  const approved = state.cvVersions.find((version) => version.jobId === job.id && version.approved);
  const history = state.applications.find((app) => app.jobId === job.id);
  return `<button class="back-link" data-action="back-jobs">← Back to jobs</button>
    <div class="page-head"><div class="page-head-copy"><span class="eyebrow">${esc(job.source)} listing · ${job.isLive?'Apply on the source site':job.source==='Native'?'Apply on Hireloom':'Assisted apply'}</span><h1>${esc(job.title)}</h1><div class="detail-company">${esc(job.company)} <span class="dot">·</span> ${esc(job.location)} <span class="dot">·</span> Posted ${esc(job.posted)}</div><div class="tag-row detail-tags"><span class="tag primary">${esc(job.source)}</span><span class="tag ${job.mode==='Remote'?'green':''}">${esc(job.mode)}</span><span class="tag">${esc(job.years)}</span><span class="tag">Open to ${esc(job.eligible.join(', '))}</span></div></div><div class="page-head-actions"><button class="secondary-button" data-action="save-job" data-id="${job.id}">${state.savedJobs.includes(job.id)?'♥ Saved':'♡ Save job'}</button></div></div>
    <div class="job-detail-grid"><article class="card job-detail-main"><div class="section-title"><h3>About this role</h3><span class="muted small">${esc(job.languages?.length?job.languages.join(' · '):'Language not listed')}</span></div><p class="subhead">${esc(job.description)}</p><div class="job-description"><h3>What you’ll work on</h3><ul>${job.highlights.map((item)=>`<li>${esc(item)}</li>`).join('')}</ul><h3>Why this may fit</h3><p>${esc(job.reason)}</p><div class="detail-summary">${job.isLive?`Found via <a href="${esc(job.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(job.source)}</a>. Verify the details and apply on the <a href="${esc(job.url)}" target="_blank" rel="noopener noreferrer">original listing</a>.`:`<strong>Application route:</strong> ${job.source==='Native'?'A demo application is saved to your Hireloom tracker. No application is sent to this company.':'Assisted apply is represented as a tracked handoff in this demo; no company site is opened.'}`}</div></div></article>
      <aside class="score-column"><div class="card score-card"><div class="score-card-head"><span>ATS readiness</span><strong>${readiness}<small>/100</small></strong></div><div class="score-meter"><span style="width:${readiness}%"></span></div><div class="breakdown"><div class="breakdown-row"><span>Contact details</span><strong>${state.profile.email&&state.profile.phone?'Complete':'Check profile'}</strong></div><div class="breakdown-row"><span>Standard sections</span><strong>${state.profile.experience?.length?'Present':'Add experience'}</strong></div><div class="breakdown-row"><span>Skill evidence</span><strong>${state.profile.skills.length} skills</strong></div></div></div>
      <div class="card score-card"><div class="score-card-head"><span>Match with this job</span><strong>${score}<small>/100</small></strong></div><div class="score-meter"><span style="width:${score}%"></span></div><div class="breakdown"><div class="breakdown-row"><span>Experience level</span><strong>${esc(job.years)}</strong></div><div class="breakdown-row"><span>Work mode</span><strong>${esc(job.mode)}</strong></div><div class="breakdown-row"><span>Remote eligibility</span><strong>${esc(job.eligible.slice(0,2).join(', '))}</strong></div></div>
        <div class="skills-block"><h4>Skills in your profile</h4><div class="tag-row">${matched.length?matched.map((skill)=>`<span class="tag green">✓ ${esc(skill)}</span>`).join(''):'<span class="tag">No direct overlap yet</span>'}</div></div>
        <div class="skills-block"><h4>Skills to review</h4><div class="tag-row">${missing.length?missing.slice(0,4).map((skill)=>`<span class="tag">${esc(skill)}</span>`).join(''):'<span class="tag green">No listed gaps</span>'}</div></div>
        ${missing.length?`<div class="fix-note">Only add a missing skill if you have evidence for it. Gaps stay visible in the tailored CV.</div>`:''}
      </div>
      <div class="detail-cta">${job.isLive?`${approved?`<div class="saved-label">✓ Tailored CV v${approved.version} approved</div><button class="secondary-button" data-action="download-cv" data-id="${job.id}">Download approved CV (.docx)</button>`:''}<a class="primary-button" href="${esc(job.url)}" target="_blank" rel="noopener noreferrer">Open original listing ↗</a>`:approved?`<div class="saved-label">✓ Tailored CV v${approved.version} approved</div><button class="secondary-button" data-action="download-cv" data-id="${job.id}">Download approved CV (.docx)</button><button class="primary-button" data-action="apply-job" data-id="${job.id}">${job.source==='Native'?'Apply on Hireloom':'Record assisted apply'}</button>`:`<button class="primary-button" data-action="tailor-job" data-id="${job.id}">Tailor CV for this job</button><button class="secondary-button" data-action="apply-job" data-id="${job.id}">Apply with current CV</button>`}${history?`<button class="text-button" data-action="go-tracker">View application in tracker</button>`:''}<p class="route-note">${job.isLive?'Hireloom opens the provider listing; applications are submitted on that site.':'You review every CV and application. Auto-apply is off.'}</p></div></aside></div>`;
}

function renderProfile() {
  const p = state.profile, tab = state.profileTab, cvDraft = state.pendingCvDraft;
  const tabs = [['about','About you'],['career','Career'],['preferences','Job preferences']];
  const experiences = (p.experience || []).length ? p.experience : [{}];
  const experienceRows = `<input type="hidden" name="experienceCount" value="${experiences.length}" />` + experiences.map((exp,index)=>`<div class="profile-form-grid"><div class="field"><label for="p-exp-title-${index}">Role</label><input id="p-exp-title-${index}" name="experienceTitle${index}" value="${esc(exp.title||'')}" /></div><div class="field"><label for="p-exp-company-${index}">Company</label><input id="p-exp-company-${index}" name="experienceCompany${index}" value="${esc(exp.company||'')}" /></div><div class="field"><label for="p-exp-dates-${index}">Dates</label><input id="p-exp-dates-${index}" name="experienceDates${index}" value="${esc(exp.dates||'')}" /></div><div class="field span-2"><label for="p-exp-detail-${index}">What you did</label><textarea id="p-exp-detail-${index}" name="experienceDetail${index}">${esc(exp.detail||'')}</textarea></div></div>`).join('');
  return `<div class="page-head"><div class="page-head-copy"><span class="eyebrow">Your Hireloom profile</span><h1>Profile</h1><p class="subhead">Review and correct the details used to find and tailor roles for you.</p></div><button class="secondary-button" data-action="open-settings">Settings <span>↗</span></button></div>
  <div class="profile-tabs">${tabs.map(([id,label])=>`<button class="profile-tab ${tab===id?'active':''}" data-profile-tab="${id}">${label}</button>`).join('')}</div>
  <form id="profile-form">
  ${tab==='about'?`<div class="profile-panels"><section class="card section-card"><div class="section-title"><h3>About you</h3><span class="tag green">Profile confirmed</span></div><div class="profile-form-grid"><div class="field"><label for="p-name">Full name</label><input id="p-name" name="name" value="${esc(p.name)}" required /></div><div class="field"><label for="p-gender">Gender <span class="muted">· optional</span></label><select id="p-gender" name="gender"><option value="">Not specified</option>${['Woman','Man','Non-binary','Self describe','Prefer not to say'].map((value)=>`<option ${p.gender===value?'selected':''}>${value}</option>`).join('')}</select></div><div class="field"><label for="p-dob">Date of birth <span class="muted">· optional</span></label><input id="p-dob" name="dob" type="date" value="${esc(p.dob)}" /></div><div class="field"><label for="p-email">Email</label><input id="p-email" name="email" type="email" value="${esc(p.email)}" required /><small>Demo account email</small></div><div class="field"><label for="p-phone">Phone number</label><input id="p-phone" name="phone" value="${esc(p.phone)}" /></div><div class="field"><label for="p-location">Current location</label><input id="p-location" name="location" value="${esc(p.location)}" /></div><div class="field span-2"><label for="p-summary">Profile summary</label><textarea id="p-summary" name="summary">${esc(p.summary)}</textarea><small>Use facts you can support from your experience.</small></div></div></section>
  <section class="card section-card"><div class="section-title"><h3>Your CV</h3><span class="tag">Processed by Hireloom server</span></div><div class="file-card"><div class="file-card-copy"><span class="file-icon">CV</span><span><strong id="cv-file-name">${esc(cvDraft?.fileName || p.cvName || 'No CV uploaded yet')}</strong><small>PDF or DOCX · up to 5 MB</small></span></div><label class="secondary-button" for="cv-upload" style="cursor:pointer">${p.cvName?'Replace':'Upload CV'}</label></div><input id="cv-upload" type="file" accept=".pdf,.docx" hidden /><div class="file-status" id="cv-status">${esc(cvDraft?'Review the extracted draft before saving.':p.cvStatus || 'Add a CV to create a confirmed profile.')}</div>${cvDraft?'<button type="button" class="text-button" data-action="review-cv-draft">Review extracted details</button>':''}<p class="upload-note">The CV is uploaded to Hireloom for in-memory parsing and is discarded after processing. Only the filename and details you confirm are saved in this browser.</p><div class="confidence-note">Your profile is the source of truth. Review parsed details before using them in matching or a tailored CV.</div></section></div>`
  :tab==='career'?`<div class="profile-panels"><section class="card section-card"><div class="section-title"><h3>Career</h3><span class="muted small">Edit what matches your CV</span></div><div class="form-section"><h4>Education</h4><div class="field"><label for="p-education">Degree, focus and dates</label><input id="p-education" name="education" value="${esc(p.education)}" /></div></div><div class="form-section"><h4>Experience</h4>${experienceRows}<p class="upload-note">Confirm experience details against your CV before tailoring it.</p></div><div class="form-section"><h4>Skills and evidence</h4><div class="skill-list" id="skill-list">${p.skills.map((skill,index)=>`<button class="removable-tag" type="button" data-action="remove-skill" data-index="${index}">${esc(skill)} <span>×</span></button>`).join('')}</div><div class="inline-add"><input id="new-skill" placeholder="Add a skill you can evidence" /><button class="secondary-button" type="button" data-action="add-skill">＋ Add</button></div><div class="profile-form-grid" style="margin-top:12px"><div class="field"><label for="p-achievements">Achievements <span class="muted">· comma separated</span></label><textarea id="p-achievements" name="achievements">${esc((p.achievements||[]).join(', '))}</textarea></div><div class="field"><label for="p-certifications">Certifications <span class="muted">· comma separated</span></label><textarea id="p-certifications" name="certifications">${esc((p.certifications||[]).join(', '))}</textarea></div></div><small class="upload-note">Only skills you confirm here are used as matches. A tailored CV never adds a gap as a skill.</small></div></section>
  <section class="card section-card"><div class="section-title"><h3>Roles to explore</h3></div><div class="field"><label for="p-title">Current / target role</label><input id="p-title" name="title" value="${esc(p.title)}" /></div><div class="field" style="margin-top:12px"><label for="p-roles">Interested roles <span class="muted">· comma separated</span></label><textarea id="p-roles" name="roles">${esc(p.roles.join(', '))}</textarea></div><div class="field" style="margin-top:12px"><label for="p-languages">Languages and proficiency</label><input id="p-languages" name="languages" value="${esc(p.languages)}" /><small>Example: English (Fluent), German (Intermediate)</small></div><div class="confidence-note">Low confidence? Check dates and role descriptions against your CV before applying.</div></section></div>`
  :`<div class="profile-panels"><section class="card section-card"><div class="section-title"><h3>Job preferences</h3></div><div class="field"><label for="p-locations">Interested locations</label><input id="p-locations" name="interestedLocation" value="${esc(p.interestedLocation)}" /><small>Countries where you can work remotely are considered too.</small></div><div class="form-section" style="margin-top:16px"><h4>Work mode</h4><div class="checkbox-row">${['Onsite','Remote','Hybrid'].map((mode)=>`<label class="choice-chip"><input type="checkbox" name="workModes" value="${mode}" ${p.workModes.includes(mode)?'checked':''}/> ${mode}</label>`).join('')}</div></div><div class="field"><label for="p-scope">Search scope</label><select id="p-scope" name="scope">${['National','International','Both'].map((value)=>`<option ${p.scope===value?'selected':''}>${value}</option>`).join('')}</select></div><div class="field" style="margin-top:12px"><label for="p-relocation">Relocation preferences</label><input id="p-relocation" name="relocation" value="${esc(p.relocation)}" /></div></section>
  <section class="card section-card"><div class="section-title"><h3>Compensation</h3><span class="muted small">Optional</span></div><div class="field"><label for="p-salary">Expected salary</label><input id="p-salary" name="salary" value="${esc(p.salary)}" placeholder="e.g. 70,000 EUR / year" /></div><div class="field" style="margin-top:12px"><label for="p-current-salary">Current salary</label><input id="p-current-salary" name="currentSalary" value="${esc(p.currentSalary)}" /></div><div class="confidence-note">Authorization, salary and notice period are never filled in automatically.</div></section></div>`}
  <div class="profile-actions"><span class="saved-label hidden" id="profile-saved">Saved in this browser</span><button class="primary-button" type="submit">Save profile</button></div></form>`;
}

function tailorContent(job) {
  const p = state.profile;
  const evidence = (p.experience || []).map((exp)=>exp.detail).filter(Boolean);
  const skills = matchingSkills(job);
  const summary = state.tailoredEdits?.summary || p.summary || `${p.title} with experience in ${skills.join(', ')}.`;
  const bullet = state.tailoredEdits?.bullet || evidence[0] || 'Add a confirmed experience bullet from your CV.';
  return { summary, bullet, skills };
}
function renderTailoring() {
  const job = getJob(state.tailoringJobId);
  if (!job) { state.view='chat'; return renderChat(); }
  const tailored = tailorContent(job), experience = state.profile.experience?.[0];
  const missing = missingSkills(job);
  return `<div class="page-head"><div class="page-head-copy"><button class="back-link" data-action="back-job">← Back to ${esc(job.title)}</button><span class="eyebrow">CV review · ${esc(job.company)}</span><h1>Tailored CV for ${esc(job.title)}</h1><p class="subhead">Only confirmed skills and experience from your profile are used. Nothing new is added.</p></div><div class="page-head-actions"><button class="secondary-button" data-action="edit-tailored">Edit draft</button><button class="danger-button" data-action="reject-tailored">Reject</button><button class="primary-button" data-action="approve-tailored">Approve this CV</button></div></div>
    <div class="tailor-banner">✳ &nbsp; This draft reorders and rephrases your existing profile. Review each line before approval.</div>
    <div class="tailor-columns"><section class="card section-card"><div class="tailor-col-title">Your master profile <span>Source</span></div><div class="tailor-col"><div class="compare-box"><h4>Summary</h4><p>${esc(state.profile.summary)}</p></div><div class="compare-box"><h4>Experience · ${esc(experience?.title || 'Profile')}</h4><p>${esc(experience?.detail || 'No confirmed role details yet.')}</p></div><div class="compare-box"><h4>Skills on your profile</h4><div class="tag-row">${state.profile.skills.map((skill)=>`<span class="tag">${esc(skill)}</span>`).join('')}</div></div></div></section>
      <section class="card section-card"><div class="tailor-col-title">Tailored for this job <span class="tag primary">Draft</span></div><div class="tailor-col"><div class="compare-box changed"><h4>Summary · reordered</h4><p>${esc(tailored.summary)}</p></div><div class="compare-box changed"><h4>Experience · selected from your profile</h4><p>${esc(tailored.bullet)}</p></div><div class="compare-box gap-card"><h4>Gap · not added</h4><p>${missing.length?`${esc(missing.join(', '))} ${missing.length===1?'is':'are'} listed in the job, but not in your profile. Add evidence if you have it.`:'No required skill gaps are listed for this demo role.'}</p></div></div></section></div>`;
}

function renderTracker() {
  const filters = ['All','Applied','Viewed','Shortlisted','Interview','Offer','Rejected','External follow-up'];
  const visible = state.applications.filter((app) => state.trackerFilter==='All' || (state.trackerFilter==='External follow-up'?app.source==='External'&&['Opened','Not sure'].includes(app.status):app.status===state.trackerFilter));
  const counts = Object.fromEntries(filters.map((filter)=>[filter,filter==='All'?state.applications.length:filter==='External follow-up'?state.applications.filter((a)=>a.source==='External'&&['Opened','Not sure'].includes(a.status)).length:state.applications.filter((a)=>a.status===filter).length]));
  return `<div class="page-head"><div class="page-head-copy"><span class="eyebrow">Your search, kept in one place</span><h1>Applications</h1><p class="subhead">See each role, the CV version you used and the latest status you recorded.</p></div><button class="secondary-button" data-nav="chat">Find more jobs <span>↗</span></button></div>
    <div class="tracker-summary">${filters.map((filter)=>`<button class="tracker-filter ${state.trackerFilter===filter?'active':''}" data-tracker-filter="${esc(filter)}">${esc(filter)}<strong>${counts[filter]}</strong></button>`).join('')}</div>
    ${visible.length?`<div class="card table-wrap"><table class="tracker-table"><thead><tr><th>Job</th><th>Source</th><th>CV</th><th>Status</th><th>Date</th><th>Action</th></tr></thead><tbody>${visible.map((app)=>{const job=getJob(app.jobId);return `<tr><td><button class="table-job" data-job="${app.jobId}">${esc(job?.title||app.title)} · ${esc(job?.company||app.company)}</button><div class="application-history">${(app.history||[]).map((h)=>`${esc(h.status)} · ${esc(formatDate(h.date))}`).join('　›　')}</div></td><td>${esc(app.source)}</td><td>v${app.cvVersion}</td><td><span class="status-pill ${app.status.toLowerCase().replace(/\s+/g,'-')}">${esc(app.status)}</span></td><td>${esc(formatDate(app.createdAt))}</td><td><div class="table-actions">${app.source==='External'&&['Opened','Not sure'].includes(app.status)?`<button data-action="external-answer" data-id="${app.id}" data-answer="Applied">Yes, applied</button><button data-action="external-answer" data-id="${app.id}" data-answer="Not applied">No</button>`:`<select data-status-id="${app.id}" aria-label="Update ${esc(job?.title||'application')} status">${['Applied','Viewed','Shortlisted','Interview','Offer','Rejected','Withdrawn'].map((status)=>`<option ${app.status===status?'selected':''}>${status}</option>`).join('')}</select>`}</div></td></tr>`}).join('')}</tbody></table></div>`:`<div class="empty-state card"><div class="empty-icon">✓</div><h3>${state.applications.length?'No applications in this view yet':'Your tracker is ready'}</h3><p>${state.applications.length?'Choose another status to see your applications.':'Apply to a role to save it here. This demo stores applications in this browser only.'}</p><button class="primary-button" data-nav="chat">Explore matched roles</button></div>`}
    <p class="upload-note" style="margin-top:12px">Application status is updated by you in this demo. External job handoffs are not sent to a company site.</p>`;
}

function renderSettings() {
  const tabs = [['account','Account'],['notifications','Notifications'],['privacy','Privacy'],['language','Language'],['help','Help and terms']];
  const p=state.profile;
  let body='';
  if (state.settingsTab==='account') body=`<h3>Account</h3><div class="setting-row"><div class="setting-row-copy"><strong>Email and phone number</strong><small>${esc(p.email)} · ${esc(p.phone)}</small></div><button class="text-button" data-action="open-profile">Edit profile ›</button></div><div class="setting-row"><div class="setting-row-copy"><strong>Demo workspace</strong><small>Your profile, chats and tracker are saved in this browser.</small></div><span class="tag">Local</span></div>`;
  if (state.settingsTab==='notifications') body=`<h3>Notifications</h3><div class="setting-row"><div class="setting-row-copy"><strong>New matches</strong><small>Get a reminder when new roles fit your preferences.</small></div><button class="switch ${state.settings.newMatches?'on':''}" data-action="toggle-setting" data-setting="newMatches" aria-label="Toggle new matches"></button></div><div class="setting-row"><div class="setting-row-copy"><strong>Application reminders</strong><small>Remind me to update an external application status.</small></div><button class="switch ${state.settings.reminders?'on':''}" data-action="toggle-setting" data-setting="reminders" aria-label="Toggle application reminders"></button></div><div class="setting-row"><div class="setting-row-copy"><strong>Automatic applications</strong><small>Not implemented in this demo. It remains off.</small></div><button class="switch" disabled aria-label="Automatic applications off"></button></div>`;
  if (state.settingsTab==='privacy') body=`<h3>Privacy</h3><div class="setting-row"><div class="setting-row-copy"><strong>Export my data</strong><small>Download your profile, saved roles and tracker as JSON.</small></div><button class="secondary-button" data-action="export-data">Export data</button></div><div class="setting-row"><div class="setting-row-copy"><strong>Delete local demo data</strong><small>Remove saved profile, chats, CV filename and applications from this browser.</small></div><button class="danger-button" data-action="delete-data">Delete data</button></div><div class="setting-row"><div class="setting-row-copy"><strong>CV handling</strong><small>Uploaded CVs are sent to the Hireloom server, parsed in memory and not retained by the app.</small></div><span class="tag green">In-memory processing</span></div>`;
  if (state.settingsTab==='language') body=`<h3>Language</h3><div class="setting-row"><div class="setting-row-copy"><strong>Interface language</strong><small>Choose the language used in Hireloom.</small></div><select class="settings-select" disabled><option>English</option></select></div>`;
  if (state.settingsTab==='help') body=`<h3>Help and terms</h3><div class="setting-row"><div class="setting-row-copy"><strong>About this MVP</strong><small>Live listings come from Arbeitnow, Remotive, Jobicy, Himalayas and Remote OK. Global remote listings are matched to your profile or the location in your chat; match scores use local heuristics.</small></div><span class="tag">Demo</span></div><div class="setting-row"><div class="setting-row-copy"><strong>Human review</strong><small>You review your profile, CV edits and application status. Authorization and salary answers are never generated.</small></div></div>`;
  return `<div class="page-head"><div class="page-head-copy"><span class="eyebrow">Account controls</span><h1>Settings</h1><p class="subhead">Manage notifications, privacy and your local demo account.</p></div></div><div class="settings-layout"><nav class="card settings-nav">${tabs.map(([id,label])=>`<button class="${state.settingsTab===id?'active':''}" data-settings-tab="${id}">${label}</button>`).join('')}</nav><section class="card settings-content">${body}</section></div>`;
}

function renderPlans() {
  const plans=[['Free','Chat search and matches','Tailored CV for each job','Application tracker','You apply yourself'],['One-click apply','Everything in Free','Answers from your saved profile','One-click apply','Review before every submission'],['Agent apply','Everything in One-click apply','Automatic applications for eligible native jobs','Status updates in the tracker','Explicit consent and pause switch']];
  return `<div class="page-head"><div class="page-head-copy"><span class="eyebrow">Plans</span><h1>Simple plans, built around your control</h1><p class="subhead">Pricing is not set for this MVP. Paid plan selection is a prototype and does not charge you.</p></div></div><div class="plans-grid">${plans.map((plan,index)=>`<section class="card plan-card ${index===0?'current':''}"><h3>${plan[0]}</h3><span class="plan-price">Price to be decided</span><ul>${plan.slice(1).map((item)=>`<li>${esc(item)}</li>`).join('')}</ul>${index===0?'<span class="plan-label">Current plan</span>':`<button class="secondary-button" data-action="plan-select" data-plan="${esc(plan[0])}">Choose plan</button>`}</section>`).join('')}</div>`;
}

function attachViewEvents() {
  const loginForm=$('#login-form');
  if(loginForm) loginForm.addEventListener('submit',(event)=>{event.preventDefault();loginUser(new FormData(loginForm));});
  const signupForm=$('#signup-form');
  if(signupForm) signupForm.addEventListener('submit',(event)=>{event.preventDefault();createAccount(new FormData(signupForm));});
  const searchForm=$('#search-form');
  if(searchForm) searchForm.addEventListener('submit',(event)=>{event.preventDefault();if(voiceState.status==='listening'){toast('Stop listening and review the transcript before searching.','error');return;}const raw=String(new FormData(searchForm).get('query')||'').trim();if(!raw)return;const fromVoice=voiceState.status==='review';const query=fromVoice?normalizeVoiceQuery(raw):raw;if(fromVoice&&query!==raw)toast('Common Hindi and German job-search terms were normalized for matching.','success');runSearch(query);});
  const languageSelect=$('#voice-language');
  if(languageSelect) languageSelect.addEventListener('change',()=>{voiceLanguage=languageSelect.value;try{localStorage.setItem(VOICE_LANGUAGE_KEY,voiceLanguage);}catch{};});
  const searchInput=$('#search-query');
  if(searchInput) searchInput.addEventListener('input',()=>{if(voiceState.status==='review'){voiceState.queryDraft=searchInput.value;const transcript=$('#voice-transcript');if(transcript)transcript.textContent=voiceState.transcript||searchInput.value;}});
  const profileForm=$('#profile-form');
  if(profileForm) profileForm.addEventListener('submit',(event)=>{event.preventDefault();saveProfile(new FormData(profileForm));});
  const upload=$('#cv-upload');
  if(upload) upload.addEventListener('change',()=>handleUpload(upload.files?.[0]));
}

function normalizeVoiceQuery(value) {
  let query=String(value||'');
  const replacements=[
    [/softwareentwickler(?:in)?|software-entwickler(?:in)?/gi,'software developer'],
    [/dateningenieur(?:in)?/gi,'data engineer'],[/datenanalyst(?:in)?|datenanalytiker(?:in)?/gi,'data analyst'],
    [/entwickler(?:in)?/gi,'developer'],[/münchen/gi,'Munich'],[/deutschland/gi,'Germany'],[/englisch/gi,'English'],[/deutsch/gi,'German'],[/stellenangebote|arbeitsplätze|stellen/gi,'jobs'],[/im homeoffice|aus dem homeoffice|von zu hause/gi,'remote'],[/mindestens drei jahre/gi,'3 years'],[/zwei jahre/gi,'2 years'],[/hybrid/gi,'hybrid'],
    [/डेटा\s*इंजीनियर/gu,'data engineer'],[/डेटा\s*(?:एनालिस्ट|विश्लेषक)/gu,'data analyst'],[/सॉफ्टवेयर\s*इंजीनियर/gu,'software engineer'],[/इंजीनियर/gu,'engineer'],[/डेवलपर/gu,'developer'],[/बर्लिन/gu,'Berlin'],[/म्यूनिख/gu,'Munich'],[/जर्मनी/gu,'Germany'],[/भारत/gu,'India'],[/रिमोट|घर\s*से/gu,'remote'],[/हाइब्रिड/gu,'hybrid'],[/अंग्रेज़ी|अंग्रेजी/gu,'English'],[/जर्मन/gu,'German'],[/नौकरी|जॉब|काम/gu,'jobs'],[/तीन\s*साल/gu,'3 years'],[/दो\s*साल/gu,'2 years'],
    [/\bnaukri\b/gi,'jobs'],[/\bkaam\b/gi,'jobs'],[/\bberlin mein\b/gi,'Berlin'],[/\bmunich mein\b/gi,'Munich'],[/\bjarmani\b|\bgermany mein\b/gi,'Germany'],[/\bghar se\b/gi,'remote'],[/\bteen saal\b/gi,'3 years'],[/\bdo saal\b/gi,'2 years']
  ];
  for(const [pattern,replacement] of replacements)query=query.replace(pattern,replacement);
  return query.replace(/\s+/g,' ').trim();
}

function startVoiceSearch() {
  const baseQuery=$('#search-query')?.value.trim()||'';
  const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SpeechRecognition){voiceState={status:'error',recognition:null,transcript:'',interim:'',message:'Voice input is not supported in this browser. Type your search instead.',queryDraft:'',baseQuery,lowConfidence:false};render();return;}
  cancelVoiceSearch(false);
  const recognition=new SpeechRecognition();
  voiceState={status:'listening',recognition,transcript:'',interim:'',message:'',queryDraft:baseQuery,baseQuery,lowConfidence:false};
  recognition.lang=voiceLanguage==='en-IN-mixed'?'en-IN':voiceLanguage;
  recognition.continuous=true;recognition.interimResults=true;recognition.maxAlternatives=3;
  recognition.onresult=(event)=>{
    if(voiceState.recognition!==recognition)return;
    const finalParts=[],interimParts=[];let lowConfidence=false;
    for(let i=0;i<event.results.length;i++){
      const result=event.results[i],alternative=result[0];
      if(!alternative)continue;
      if(result.isFinal){finalParts.push(alternative.transcript.trim());if(alternative.confidence>0&&alternative.confidence<0.55)lowConfidence=true;}
      else interimParts.push(alternative.transcript.trim());
    }
    voiceState.transcript=finalParts.join(' ').trim();voiceState.interim=interimParts.join(' ').trim();voiceState.lowConfidence=lowConfidence;
    const input=$('#search-query');
    if(input&&voiceState.transcript)input.value=[voiceState.baseQuery,voiceState.transcript].filter(Boolean).join(' ');
    const output=$('#voice-transcript');if(output)output.textContent=[voiceState.transcript,voiceState.interim].filter(Boolean).join(' ')||'Listening for speech…';
  };
  recognition.onerror=(event)=>{
    if(voiceState.recognition!==recognition)return;
    const messages={
      'not-allowed':'Microphone permission is blocked. Enable it in your browser or type your search.',
      'service-not-allowed':'Speech recognition is blocked by the browser. Type your search instead.',
      'no-speech':'I didn’t catch any speech. Try again or type your search.',
      'audio-capture':'No microphone was found. Connect a microphone or type your search.',
      'network':'The browser speech service is unavailable. Check your connection or type your search.',
      'language-not-supported':'This browser does not support the selected voice language. Choose another language or type your search.'
    };
    voiceState.recognition=null;voiceState.status='error';voiceState.interim='';voiceState.message=messages[event.error]||'Voice input stopped. Try again or type your search.';
    if(state.view==='chat')render();
  };
  recognition.onend=()=>{
    if(voiceState.recognition!==recognition)return;
    voiceState.recognition=null;voiceState.interim='';
    if(voiceState.transcript.trim()){
      voiceState.status='review';voiceState.queryDraft=[voiceState.baseQuery,voiceState.transcript.trim()].filter(Boolean).join(' ');
      voiceState.message=voiceState.lowConfidence?'Some words may be uncertain. Review the transcript before searching.':'Review the transcript before searching.';
    }else{
      voiceState.status='error';voiceState.message='I didn’t catch any speech. Try again or type your search.';
    }
    if(state.view==='chat')render();
  };
  try{recognition.start();render();}
  catch{voiceState.recognition=null;voiceState.status='error';voiceState.message='Could not start voice input. Check microphone permission or type your search.';render();}
}

function stopVoiceSearch() {
  if(!voiceState.recognition)return;
  voiceState.message='Finishing the transcript…';
  const message=$('#voice-message');if(message)message.textContent=voiceState.message;
  try{voiceState.recognition.stop();}catch{voiceState.status='error';voiceState.message='Could not stop voice input. Type your search instead.';render();}
}

function cancelVoiceSearch(shouldRender=true,preserveInput=false) {
  const recognition=voiceState.recognition;
  const queryToKeep=preserveInput?($('#search-query')?.value||voiceState.queryDraft||voiceState.baseQuery||''):'';
  voiceState.recognition=null;
  if(recognition){try{recognition.abort();}catch{}}
  voiceState={status:'idle',recognition:null,transcript:'',interim:'',message:'',queryDraft:'',baseQuery:queryToKeep,lowConfidence:false};
  if(shouldRender&&state.view==='chat')render();
}

function finishLogin(account) {
  authData.lastEmail=account.email;saveAuth();state.profile.email=account.email;state.loggedOut=false;state.view='chat';persist();session=true;authMode='login';authMessage='';if(getChat()?.hasSearch)startChatSearches(getChat());else render();toast('Welcome to your Hireloom workspace.','success');
}
async function loginUser(formData) {
  const email=normalizeEmail(formData.get('email')), password=String(formData.get('password')||'');
  authData.lastEmail=email;saveAuth();
  const account=authData.accounts.find(value=>value.email===email);
  if(!account){authMessage='No local account exists for that email. Create an account first.';render();return;}
  try {
    const hash=await passwordHash(password,fromHex(account.salt),account.iterations);
    if(!sameHash(hash,account.hash)){authMessage='That password does not match this local account.';render();return;}
    finishLogin(account);
  } catch(error) { authMessage=error.message||'Could not verify this password in the current browser.';render(); }
}
async function createAccount(formData) {
  const name=String(formData.get('name')||'').trim(),email=normalizeEmail(formData.get('email'));
  const password=String(formData.get('password')||''),confirm=String(formData.get('confirm')||'');
  authDraft={name,email};
  if(!formData.get('localConsent')){authMessage='Confirm that you understand this local demo stores account data in this browser.';render();return;}
  if(password.length<8){authMessage='Use a password with at least 8 characters.';render();return;}
  if(password!==confirm){authMessage='The passwords do not match.';render();return;}
  if(authData.accounts.some(value=>value.email===email)){authMessage='An account for this email already exists. Log in instead.';render();return;}
  try {
    const salt=crypto.getRandomValues(new Uint8Array(16)),iterations=210000;
    const account={name,email,salt:toHex(salt),hash:await passwordHash(password,salt,iterations),iterations,createdAt:new Date().toISOString()};
    authData.accounts.push(account);authData.lastEmail=email;saveAuth();
    state.profile.name=name;state.profile.email=email;state.loggedOut=false;state.view='chat';persist();session=true;authMode='login';authMessage='';if(getChat()?.hasSearch)startChatSearches(getChat());else render();toast('Local demo account created.','success');
  } catch(error) { authMessage=error.message||'Could not create the local account.';render(); }
}

function runSearch(query) {
  cancelVoiceSearch(false);
  let chat=getChat();
  if(!chat) {
    chat={id:`chat-${Date.now()}`,title:'New search',date:'Today',query:'',hasSearch:false,turns:[]};
    state.chats.unshift(chat);state.activeChatId=chat.id;
  }
  chat.turns=Array.isArray(chat.turns)?chat.turns:[];
  const turn=makeSearchTurn(query,`turn-${Date.now()}-${Math.random().toString(36).slice(2,7)}`);
  turn.status='loading';chat.turns.push(turn);chat.query=query;
  if(chat.turns.length===1)chat.title=query.length>33?`${query.slice(0,32)}…`:query;
  chat.date='Today';chat.hasSearch=true;state.view='chat';persist();startLiveSearch(chat,false,turn.id);
}
function startChatSearches(chat) {
  if(!chat?.turns?.length)return;
  for(const turn of chat.turns){if(!turn.resultsCaptured)startLiveSearch(chat,false,turn.id);}
  const latest=latestTurn(chat),cached=latest&&liveSearchByTurn.get(latest.id);
  liveSearch=cached||{chatId:chat.id,turnId:latest?.id||null,query:latest?.query||'',status:latest?.status||'idle',jobs:latest?.jobs||[],sources:latest?.sources||[]};
  if(state.view==='chat')render();
}
function startLiveSearch(chat,force=false,turnId=null) {
  const turn=chat?.turns?.find((item)=>item.id===turnId)||latestTurn(chat);
  if(!chat||!turn)return;
  if(!force&&turn.resultsCaptured){
    const saved=liveSearchByTurn.get(turn.id);
    if(saved)liveSearch=saved;
    if(state.view==='chat')render();
    return;
  }
  const cached=liveSearchByTurn.get(turn.id);
  if(!force&&cached?.status==='loading'){liveSearch=cached;if(state.view==='chat')render();return;}
  const requestId=++liveSearchSequence;
  liveSearchRequestByTurn.set(turn.id,requestId);
  turn.status='loading';turn.response='';turn.resultsCaptured=false;turn.jobs=[];turn.totalResults=0;
  const entry={chatId:chat.id,turnId:turn.id,query:turn.query,status:'loading',jobs:[],sources:[]};
  liveSearchByTurn.set(turn.id,entry);liveSearch=entry;persist();
  if(state.activeChatId===chat.id&&state.view==='chat')render();
  const location=effectiveLocationTerms(turn.query).join(', ');
  fetch(`/api/search-jobs?q=${encodeURIComponent(turn.query)}&location=${encodeURIComponent(location)}`)
    .then(async(response)=>{const body=await response.json();if(!response.ok)throw new Error(body.error||'Live job search failed.');return body;})
    .then((body)=>{
      if(liveSearchRequestByTurn.get(turn.id)!==requestId)return;
      entry.sources=Array.isArray(body.sources)?body.sources:[];
      const hasSource=entry.sources.some((source)=>source.ok);
      entry.jobs=hasSource&&Array.isArray(body.jobs)?body.jobs:[];entry.status=hasSource?'ready':'error';
      turn.sources=entry.sources;turn.status=entry.status;turn.resultsCaptured=true;
      if(hasSource){const ranked=jobsForQuery(turn.query,entry.jobs);turn.totalResults=ranked.length;turn.jobs=ranked.map(snapshotJob);turn.response=ranked.length?`I found ${ranked.length} matching ${ranked.length===1?'role':'roles'}, ranked by fit.`:'I couldn’t find live listings that matched this prompt. Try another title, location, or work mode.';}
      else{turn.totalResults=0;turn.jobs=[];turn.response='I couldn’t reach the live job feeds for this prompt. You can retry it.';}
      liveSearchByTurn.set(turn.id,entry);persist();
      if(state.activeChatId===chat.id){liveSearch=entry;if(state.view==='chat')render();}
    })
    .catch(()=>{
      if(liveSearchRequestByTurn.get(turn.id)!==requestId)return;
      entry.status='error';entry.jobs=[];entry.sources=['Arbeitnow','Remotive','Jobicy','Himalayas','Remote OK'].map((name)=>({name,ok:false}));
      turn.status='error';turn.resultsCaptured=true;turn.jobs=[];turn.sources=entry.sources;turn.totalResults=0;turn.response='I couldn’t reach the live job feeds for this prompt. You can retry it.';
      liveSearchByTurn.set(turn.id,entry);persist();
      if(state.activeChatId===chat.id){liveSearch=entry;if(state.view==='chat')render();}
    });
}
function toast(message,type='') {
  const region=$('#toast-region'), item=document.createElement('div');
  item.className=`toast ${type}`;item.textContent=message;region.append(item);setTimeout(()=>item.remove(),3000);
}
function openModal(markup) { $('#modal-root').innerHTML=`<div class="modal" role="dialog" aria-modal="true">${markup}</div>`; }
function closeModal() { $('#modal-root').innerHTML=''; }
function showSearchEdit() {
  const query=latestQuery();
  openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Continue this conversation</span><h2>Refine with a new prompt</h2><p class="modal-copy">This adds a follow-up prompt and response. Earlier messages and results stay in the conversation.</p><form id="edit-search-form"><div class="field" style="margin-top:14px"><label for="edit-query">Follow-up prompt</label><textarea id="edit-query" name="query" required>${esc(query)}</textarea></div><div class="modal-actions"><button type="button" class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button">Send follow-up</button></div></form>`);
  $('#edit-search-form').addEventListener('submit',(event)=>{event.preventDefault();const q=new FormData(event.currentTarget).get('query');closeModal();runSearch(q);});
}
function showMoreFilters() {
  const query=latestQuery();
  const mode=/remote/i.test(query)?'Remote':/hybrid/i.test(query)?'Hybrid':/onsite/i.test(query)?'Onsite':'';
  const location=(queryLocationTerms(query).length?queryLocationTerms(query):profileLocationTerms()).join(', ');
  const language=['English','German','French','Spanish'].find((value)=>query.toLowerCase().includes(value.toLowerCase()))||'';
  openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Search preferences</span><h2>More filters</h2><p class="modal-copy">These apply only to this search. Remote roles are checked against the countries they allow.</p><form id="filters-form"><div class="field" style="margin-top:15px"><label>Work mode</label><select name="mode"><option value="">Any mode</option>${['Remote','Hybrid','Onsite'].map((v)=>`<option ${mode===v?'selected':''}>${v}</option>`).join('')}</select></div><div class="field" style="margin-top:11px"><label for="filter-location">City, country or region</label><input id="filter-location" name="location" value="${esc(location)}" placeholder="e.g., Bengaluru, India or London"></div><div class="field" style="margin-top:11px"><label>Working language</label><select name="language"><option value="">Any language</option>${['English','German','French','Spanish'].map((v)=>`<option ${language===v?'selected':''}>${v}</option>`).join('')}</select></div><div class="modal-actions"><button type="button" class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button">Apply filters</button></div></form>`);
  $('#filters-form').addEventListener('submit',(event)=>{event.preventDefault();const values=new FormData(event.currentTarget);const locationTokens=new Set([...queryLocationTerms(query),...profileLocationTerms()].flatMap(tokensForSearch));const base=tokensForSearch(query).filter((word)=>!locationTokens.has(word)&&!['remote','hybrid','onsite','english','german','french','spanish'].includes(word)).join(' ');const location=String(values.get('location')||'').trim();const q=[base,values.get('mode'),values.get('language'),location?`in ${location}`:''].filter(Boolean).join(' ');closeModal();runSearch(q||'Data jobs');});
}

function openApply(job) {
  const approved=state.cvVersions.find((version)=>version.jobId===job.id&&version.approved);
  const cvVersion=approved?.version||state.profile.cvVersion||1;
  if(job.source==='External') {
    openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Assisted apply</span><h2>Record an external handoff</h2><p class="modal-copy">${esc(job.title)} · ${esc(job.company)}</p><div class="modal-section"><h4>CV version</h4><p>Hireloom CV v${cvVersion}</p></div><div class="modal-section"><h4>External listing</h4><p>This demo records a handoff locally. It does not open the company site or submit your details.</p></div><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button" data-action="record-handoff" data-id="${job.id}">Record handoff</button></div>`);return;
  }
  const country=job.location.includes('Germany')||job.eligible.includes('Germany')?'Germany':job.eligible[0];
  openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Review and submit</span><h2>Confirm your application</h2><p class="modal-copy">${esc(job.title)} · ${esc(job.company)}</p><div class="modal-section"><h4>CV version used</h4><p>Hireloom CV v${cvVersion}${approved?' · tailored and approved':' · current profile version'}</p></div><div class="modal-section"><h4>Work authorization · ${esc(country)}</h4><div class="field" style="margin-top:7px"><label for="work-auth">Select your answer for this application</label><select id="work-auth" required><option value="">Choose an answer</option><option>I am authorized to work</option><option>I need sponsorship</option><option>I prefer to answer with the company</option></select></div><p style="margin-top:8px">You choose this answer yourself. Hireloom never fills it in automatically.</p></div><div class="modal-section"><h4>Demo submission</h4><p>The application will be added to your local tracker. This seeded role is not connected to the company, so nothing is sent externally.</p></div><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button" data-action="submit-application" data-id="${job.id}">Save application</button></div>`);
}

function addHistory(app,status) { app.status=status;app.history.push({status,date:new Date().toISOString()}); }
function submitApplication(jobId) {
  const job=getJob(jobId), answer=$('#work-auth')?.value;
  if(!answer){toast('Choose your work authorization answer or prefer to answer with the company.','error');return;}
  const approved=state.cvVersions.find((version)=>version.jobId===job.id&&version.approved);
  const existing=state.applications.find((app)=>app.jobId===job.id);
  if(existing){addHistory(existing,'Applied');existing.workAuthorization=answer;}
  else state.applications.unshift({id:`app-${Date.now()}`,jobId:job.id,title:job.title,company:job.company,source:job.source,cvVersion:approved?.version||state.profile.cvVersion||1,status:'Applied',createdAt:new Date().toISOString(),workAuthorization:answer,history:[{status:'Applied',date:new Date().toISOString()}]});
  persist();closeModal();state.view='tracker';state.trackerFilter='All';render();toast('Application saved to your local tracker.','success');
}
function recordHandoff(jobId) {
  const job=getJob(jobId), approved=state.cvVersions.find((version)=>version.jobId===job.id&&version.approved);
  if(!state.applications.some((app)=>app.jobId===jobId)) state.applications.unshift({id:`app-${Date.now()}`,jobId,title:job.title,company:job.company,source:'External',cvVersion:approved?.version||state.profile.cvVersion||1,status:'Opened',createdAt:new Date().toISOString(),history:[{status:'Opened',date:new Date().toISOString()}]});
  persist();closeModal();render();openExternalFollowup(jobId);
}
function openExternalFollowup(jobId) {
  const job=getJob(jobId), app=state.applications.find((item)=>item.jobId===jobId);
  openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Application tracker</span><h2>Did you apply?</h2><p class="modal-copy">${esc(job.title)} · ${esc(job.company)}</p><p class="modal-copy">The external listing handoff has been recorded. Update the status whenever you know.</p><div class="modal-actions" style="justify-content:flex-start"><button class="secondary-button" data-action="external-answer" data-id="${app.id}" data-answer="Not applied">No</button><button class="secondary-button" data-action="close-modal">Later</button><button class="primary-button" data-action="external-answer" data-id="${app.id}" data-answer="Applied">Yes, I applied</button></div>`);
}
function updateExternalAnswer(appId,answer) {
  const app=state.applications.find((item)=>item.id===appId);if(!app)return;
  addHistory(app,answer==='Applied'?'Applied':'Not applied');persist();closeModal();render();toast(answer==='Applied'?'Application status updated.':'Saved. You can update this later.','success');
}

function saveProfile(formData) {
  const p=state.profile;
  ['name','email','phone','location','gender','dob','summary','education','title','languages','interestedLocation','scope','relocation','salary','currentSalary'].forEach((key)=>{if(formData.has(key))p[key]=String(formData.get(key)).trim();});
  if(formData.has('roles'))p.roles=toList(formData.get('roles'));
  if(formData.has('achievements'))p.achievements=toList(formData.get('achievements'));
  if(formData.has('certifications'))p.certifications=toList(formData.get('certifications'));
  if(formData.has('experienceCount')){const count=Math.min(20,Math.max(0,Number(formData.get('experienceCount'))||0));p.experience=Array.from({length:count},(_,index)=>({title:String(formData.get(`experienceTitle${index}`)||'').trim(),company:String(formData.get(`experienceCompany${index}`)||'').trim(),dates:String(formData.get(`experienceDates${index}`)||'').trim(),detail:String(formData.get(`experienceDetail${index}`)||'').trim()})).filter((experience)=>Object.values(experience).some(Boolean));}
  if($('#profile-form input[name="workModes"]'))p.workModes=formData.getAll('workModes');
  persist();render();const saved=$('#profile-saved');if(saved)saved.classList.remove('hidden');toast('Profile saved in this browser.','success');
}
function handleUpload(file) {
  if(!file)return;
  if(file.size>5*1024*1024){toast('That file is over the 5 MB limit.','error');return;}
  const ext=file.name.split('.').pop().toLowerCase();
  if(!['pdf','docx'].includes(ext)){toast('Choose a PDF or DOCX CV.','error');return;}
  $('#cv-file-name').textContent=file.name;$('#cv-status').textContent='Uploading your CV for in-memory parsing…';
  const form=new FormData();form.append('file',file);
  fetch('/api/parse-cv',{method:'POST',body:form}).then(async(response)=>{const body=await response.json();if(!response.ok)throw new Error(body.error||'CV parsing failed.');return body;}).then((draft)=>{
    state.pendingCvDraft={fileName:file.name,draft};
    render();showCvDraftReview();
  }).catch((error)=>{ $('#cv-status').textContent=`${file.name} · ${error.message}`;toast(error.message,'error'); });
}
function showCvDraftReview() {
  const pending=state.pendingCvDraft;if(!pending)return;
  const d=pending.draft;
  const groups=[
    ['About you',[
      ['name','Full name',d.name],['email','Email',d.email],['phone','Phone number',d.phone],['location','Current location',d.location],
      ['gender','Gender',d.gender],['dob','Date of birth',d.dob],['summary','Profile summary',d.summary]
    ]],
    ['Career',[
      ['title','Current / target role',d.title],['roles','Interested roles',d.roles],['languages','Languages and proficiency',d.languages],
      ['education','Education',d.education],['skills','Skills',d.skills],['achievements','Achievements',d.achievements],['certifications','Certifications',d.certifications]
    ]],
    ['Job preferences',[
      ['interestedLocation','Interested locations',d.interestedLocation],['workModes','Work modes',d.workModes],['scope','Search scope',d.scope],
      ['relocation','Relocation preferences',d.relocation],['salary','Expected salary',d.salary],['currentSalary','Current salary',d.currentSalary]
    ]]
  ];
  const hasValue=(value)=>Array.isArray(value)?value.length>0:String(value??'').trim().length>0;
  const displayValue=(value)=>Array.isArray(value)?value.join(', '):String(value??'');
  const inputFor=(key,value)=>{
    const safe=displayValue(value);
    if(key==='gender'||key==='scope'){
      const options=key==='gender'?['Woman','Man','Non-binary','Self describe','Prefer not to say']:['National','International','Both'];
      return `<select name="value-${key}"><option value="">${hasValue(value)?'Select':'Not found in CV'}</option>${options.map((option)=>`<option value="${esc(option)}" ${safe===option?'selected':''}>${esc(option)}</option>`).join('')}</select>`;
    }
    if(key==='workModes')return `<div class="cv-mode-options">${['Remote','Hybrid','Onsite'].map((mode)=>`<label><input type="checkbox" name="value-workModes" value="${mode}" ${(Array.isArray(value)?value:[]).includes(mode)?'checked':''}/> ${mode}</label>`).join('')}</div>`;
    if(key==='dob')return `<input type="date" name="value-${key}" value="${esc(safe)}" />`;
    if(['summary','education','skills','achievements','certifications','roles'].includes(key))return `<textarea name="value-${key}" rows="${key==='summary'||key==='education'?3:2}">${esc(safe)}</textarea>`;
    return `<input name="value-${key}" value="${esc(safe)}" />`;
  };
  const fieldRow=([key,label,value])=>`<div class="draft-row"><input aria-label="Update ${esc(label)} from CV" type="checkbox" name="fields" value="${key}" ${hasValue(value)?'checked':''} /><div class="draft-edit"><strong>${esc(label)}</strong>${inputFor(key,value)}<small>${hasValue(value)?'Detected in CV':'Not found in CV; this field stays unchanged unless you enter and select a value.'}</small></div></div>`;
  const parsedExperiences=Array.isArray(d.experience)?d.experience.slice(0,20):[];
  const experienceRows=parsedExperiences.length?parsedExperiences:[{}];
  const hasExperience=parsedExperiences.some((experience)=>Object.values(experience||{}).some(hasValue));
  const experienceEditor=`<div class="draft-row"><input aria-label="Update work experience from CV" type="checkbox" name="fields" value="experience" ${hasExperience?'checked':''} /><div class="draft-edit"><strong>Work experience</strong><input type="hidden" name="experience-count" value="${experienceRows.length}" />${experienceRows.map((experience,index)=>`<div class="cv-experience-entry"><strong>${parsedExperiences.length?`Experience ${index+1}`:'No experience detected'}</strong><input aria-label="Experience role" name="experience-title-${index}" placeholder="Role" value="${esc(experience.title||'')}" /><input aria-label="Experience company" name="experience-company-${index}" placeholder="Company" value="${esc(experience.company||'')}" /><input aria-label="Experience dates" name="experience-dates-${index}" placeholder="Dates" value="${esc(experience.dates||'')}" /><textarea aria-label="Experience details" name="experience-detail-${index}" rows="3" placeholder="What you did">${esc(experience.detail||'')}</textarea></div>`).join('')}<small>${hasExperience?'Detected in CV':'Not found in CV; your current experience stays unchanged unless you select this field.'}</small></div></div>`;
  const groupHtml=groups.map(([title,fields])=>`<div class="modal-section"><h4>${esc(title)}</h4>${fields.map(fieldRow).join('')}${title==='Career'?experienceEditor:''}</div>`).join('');
  const foundAny=groups.some(([,fields])=>fields.some((field)=>hasValue(field[2])))||hasExperience;
  openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">CV parsed by Hireloom</span><h2>Update your profile from this CV</h2><p class="modal-copy">Review all profile fields. Detected values are selected; fields missing from the CV remain unchanged unless you enter and select them. Nothing is saved until you confirm.</p><form id="cv-draft-form"><div class="modal-section"><h4>${esc(pending.fileName)} · ${d.pageCount?`${d.pageCount} pages · `:''}profile details</h4>${foundAny?'<p>Check extracted fields for accuracy before updating your profile.</p>':'<p>No profile values were detected. Review the blank fields below and add only details you can confirm.</p>'}${d.warning?`<p class="cv-warning">${esc(d.warning)}</p>`:''}</div>${groupHtml}<div class="modal-actions"><button type="button" class="secondary-button" data-action="discard-cv-draft">Discard draft</button><button class="primary-button">Update profile</button></div></form>`);
  $('#cv-draft-form').addEventListener('submit',(event)=>{
    event.preventDefault();
    const form=new FormData(event.currentTarget),selected=new Set(form.getAll('fields')),draft=state.pendingCvDraft.draft,p=state.profile;
    const scalarFields=['name','email','phone','location','gender','dob','title','summary','languages','education','interestedLocation','scope','relocation','salary','currentSalary'];
    for(const key of scalarFields){
      if(!selected.has(key)||!form.has(`value-${key}`))continue;
      const value=String(form.get(`value-${key}`)||'').trim();
      if((key==='name'||key==='email')&&!value)continue;
      p[key]=key==='summary'?value.slice(0,1200):value;
    }
    for(const key of ['skills','achievements','certifications','roles'])if(selected.has(key))p[key]=toList(form.get(`value-${key}`));
    if(selected.has('workModes'))p.workModes=form.getAll('value-workModes');
    if(selected.has('experience')){
      const count=Math.min(20,Math.max(0,Number(form.get('experience-count'))||0));
      p.experience=Array.from({length:count},(_,index)=>({title:String(form.get(`experience-title-${index}`)||'').trim(),company:String(form.get(`experience-company-${index}`)||'').trim(),dates:String(form.get(`experience-dates-${index}`)||'').trim(),detail:String(form.get(`experience-detail-${index}`)||'').trim()})).filter((experience)=>Object.values(experience).some(Boolean));
    }
    p.cvName=state.pendingCvDraft.fileName;p.cvStatus=`Parsed by Hireloom · ${draft.pageCount?`${draft.pageCount} pages · `:''}profile updated`;state.pendingCvDraft=null;persist();closeModal();render();toast('Your profile was updated from the CV.','success');
  });
}
function setView(view) { cancelVoiceSearch(false);state.view=view;state.sidebarOpen=false;persist();render();window.scrollTo({top:0,behavior:'smooth'}); }
function downloadData() {
  const blob=new Blob([JSON.stringify({exportedAt:new Date().toISOString(),profile:state.profile,chats:state.chats,applications:state.applications,savedJobs:state.savedJobs,settings:state.settings},null,2)],{type:'application/json'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='hireloom-demo-data.json';link.click();URL.revokeObjectURL(link.href);toast('Your local data export is ready.','success');
}
function downloadApprovedCv(jobId) {
  const job=getJob(jobId), version=state.cvVersions.find((item)=>item.jobId===jobId&&item.approved);
  if(!job||!version){toast('Approve a tailored CV before downloading it.','error');return;}
  fetch('/api/render-cv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:{title:job.title,company:job.company},version})})
    .then(async(response)=>{if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.error||'Could not create the CV file.');}return response.blob();})
    .then((blob)=>{const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`Hireloom_CV_v${version.version}.docx`;link.click();URL.revokeObjectURL(link.href);toast('Approved CV downloaded.','success');})
    .catch((error)=>toast(error.message,'error'));
}

document.addEventListener('click',(event)=>{
  const nav=event.target.closest('[data-nav]');if(nav){cancelVoiceSearch(false);state.view=nav.dataset.nav==='tracker'?'tracker':'chat';state.sidebarOpen=false;persist();if(state.view==='chat'&&getChat()?.hasSearch)startChatSearches(getChat());else render();return;}
  const chatButton=event.target.closest('[data-chat-id]');if(chatButton){cancelVoiceSearch(false);state.activeChatId=chatButton.dataset.chatId;state.view='chat';state.sidebarOpen=false;persist();if(getChat()?.hasSearch)startChatSearches(getChat());else render();return;}
  const jobButton=event.target.closest('[data-job]');if(jobButton){cancelVoiceSearch(false);state.selectedJobId=jobButton.dataset.job;state.view='job';state.sidebarOpen=false;persist();render();return;}
  const tab=event.target.closest('[data-profile-tab]');if(tab){state.profileTab=tab.dataset.profileTab;render();return;}
  const settingTab=event.target.closest('[data-settings-tab]');if(settingTab){state.settingsTab=settingTab.dataset.settingsTab;render();return;}
  const trackerFilter=event.target.closest('[data-tracker-filter]');if(trackerFilter){state.trackerFilter=trackerFilter.dataset.trackerFilter;render();return;}
  const suggestion=event.target.closest('[data-query]');if(suggestion){runSearch(suggestion.dataset.query);return;}
  const action=event.target.closest('[data-action]');if(!action)return;
  const id=action.dataset.id;
  switch(action.dataset.action){
    case 'show-signup':authDraft={name:'',email:$('#login-email')?.value||authData.lastEmail};authMode='signup';authMessage='';render();break;
    case 'show-login':authData.lastEmail=$('#signup-email')?.value||authData.lastEmail;saveAuth();authMode='login';authMessage='';render();break;
    case 'toggle-password':{const input=document.getElementById(id);if(input){input.type=input.type==='password'?'text':'password';action.textContent=input.type==='password'?'Show':'Hide';}break;}
    case 'delete-chat':{const chat=state.chats.find((item)=>item.id===id);if(!chat)break;pendingDeleteChatId=id;openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Your searches</span><h2>Delete this chat?</h2><p class="modal-copy">“${esc(chat.title)}” and its saved search will be removed from this browser.</p><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="danger-button" data-action="confirm-delete-chat">Delete chat</button></div>`);break;}
    case 'confirm-delete-chat':{const chatId=pendingDeleteChatId;if(!chatId)break;const removingActive=state.activeChatId===chatId,removed=state.chats.find((chat)=>chat.id===chatId);for(const turn of removed?.turns||[]){liveSearchByTurn.delete(turn.id);liveSearchRequestByTurn.delete(turn.id);}state.chats=state.chats.filter((chat)=>chat.id!==chatId);pendingDeleteChatId=null;if(removingActive){if(!state.chats.length)state.chats.push({id:`chat-${Date.now()}`,title:'New search',date:'Today',query:'',hasSearch:false,turns:[]});state.activeChatId=state.chats[0].id;state.view='chat';state.selectedJobId=null;liveSearch={chatId:state.activeChatId,turnId:null,query:'',status:'idle',jobs:[],sources:[]};}persist();closeModal();render();if(removingActive&&getChat()?.hasSearch)startChatSearches(getChat());toast('Chat deleted.','success');break;}
    case 'new-chat':{cancelVoiceSearch(false);const chat={id:`chat-${Date.now()}`,title:'New search',date:'Today',query:'',hasSearch:false,turns:[]};state.chats.unshift(chat);state.activeChatId=chat.id;state.view='chat';persist();render();break;}
    case 'toggle-sidebar':state.sidebarOpen=!state.sidebarOpen;updateShell();break;
    case 'toggle-menu':$('#account-menu').classList.toggle('hidden');break;
    case 'open-profile':state.profileTab='about';setView('profile');break;
    case 'open-settings':state.settingsTab='account';setView('settings');break;
    case 'open-plans':setView('plans');break;
    case 'edit-search':showSearchEdit();break;
    case 'clear-search':runSearch('Data jobs');break;
    case 'copy-search':navigator.clipboard?.writeText(latestQuery()).then(()=>toast('Search copied.','success')).catch(()=>toast('Copy the search text from the message.'));break;
    case 'rerun-search':startLiveSearch(getChat(),true,latestTurn()?.id);toast('Latest response refreshed.','success');break;
    case 'voice-search':if(voiceState.status==='listening')stopVoiceSearch();else startVoiceSearch();break;
    case 'voice-stop':stopVoiceSearch();break;
    case 'voice-cancel':cancelVoiceSearch(true,true);break;
    case 'voice-retry':startVoiceSearch();break;
    case 'more-filters':showMoreFilters();break;
    case 'filter-chip':if(['Remote','Hybrid','Onsite'].includes(action.dataset.filter))runSearch(`${latestQuery()} ${action.dataset.filter}`,true);else if(['Germany','Berlin','Munich'].includes(action.dataset.filter))runSearch(`${latestQuery()} ${action.dataset.filter}`,true);else showMoreFilters();break;
    case 'save-job':{const saved=state.savedJobs.includes(id);state.savedJobs=saved?state.savedJobs.filter((jobId)=>jobId!==id):[...state.savedJobs,id];persist();render();toast(saved?'Removed from saved jobs.':'Job saved.','success');break;}
    case 'back-jobs':state.view='chat';render();break;
    case 'tailor-job':state.tailoringJobId=id;state.tailoredEdits=null;state.view='tailor';render();break;
    case 'back-job':state.view='job';render();break;
    case 'edit-tailored':{
      const job=getJob(state.tailoringJobId),draft=tailorContent(job);
      openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Edit tailored CV</span><h2>Review the wording</h2><p class="modal-copy">Use facts you have confirmed in your profile. This demo does not generate new experience or skills.</p><form id="tailor-edit-form"><div class="field" style="margin-top:14px"><label for="tailor-summary">Summary</label><textarea id="tailor-summary" name="summary" required>${esc(draft.summary)}</textarea></div><div class="field" style="margin-top:11px"><label for="tailor-bullet">Experience bullet</label><textarea id="tailor-bullet" name="bullet" required>${esc(draft.bullet)}</textarea></div><div class="modal-actions"><button type="button" class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button">Save edits</button></div></form>`);
      $('#tailor-edit-form').addEventListener('submit',(e)=>{e.preventDefault();const fd=new FormData(e.currentTarget);state.tailoredEdits={summary:fd.get('summary'),bullet:fd.get('bullet')};persist();closeModal();render();toast('CV draft updated. Review it before approval.','success');});break;
    }
    case 'approve-tailored':{const job=getJob(state.tailoringJobId),version=(state.profile.cvVersion||1)+state.cvVersions.filter((item)=>item.approved).length,draft=tailorContent(job);state.cvVersions=state.cvVersions.filter((item)=>item.jobId!==job.id);state.cvVersions.push({jobId:job.id,version,approved:true,approvedAt:new Date().toISOString(),summary:draft.summary,bullet:draft.bullet,skills:draft.skills,profile:{name:state.profile.name,email:state.profile.email,phone:state.profile.phone,location:state.profile.location,education:state.profile.education,title:state.profile.title}});persist();state.view='job';state.selectedJobId=job.id;render();toast(`Tailored CV v${version} approved for ${job.title}.`,'success');break;}
    case 'download-cv':downloadApprovedCv(id);break;
    case 'reject-tailored':state.view='job';render();toast('Draft rejected. Your profile has not changed.');break;
    case 'apply-job':openApply(getJob(id));break;
    case 'submit-application':submitApplication(id);break;
    case 'record-handoff':recordHandoff(id);break;
    case 'external-answer':updateExternalAnswer(id,action.dataset.answer);break;
    case 'go-tracker':setView('tracker');break;
    case 'remove-skill':state.profile.skills.splice(Number(action.dataset.index),1);persist();render();break;
    case 'add-skill':{const input=$('#new-skill'),skill=input?.value.trim();if(!skill){toast('Add a skill name first.');break;}if(!state.profile.skills.some((value)=>value.toLowerCase()===skill.toLowerCase()))state.profile.skills.push(skill);persist();render();toast('Skill added to your profile.','success');break;}
    case 'toggle-setting':state.settings[action.dataset.setting]=!state.settings[action.dataset.setting];persist();render();break;
    case 'export-data':downloadData();break;
    case 'delete-data':openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Privacy</span><h2>Delete local demo data?</h2><p class="modal-copy">This removes your saved profile, conversations, CV filename and tracker entries from this browser. This action cannot be undone.</p><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="danger-button" data-action="confirm-delete">Delete data</button></div>`);break;
    case 'confirm-delete':cancelVoiceSearch(false);localStorage.removeItem(STORAGE_KEY);localStorage.removeItem(AUTH_KEY);state=initialState();authData={accounts:[],lastEmail:''};liveSearchByTurn.clear();liveSearchRequestByTurn.clear();liveSearch={chatId:null,turnId:null,query:'',status:'idle',jobs:[],sources:[]};authMode='login';authMessage='';session=false;closeModal();render();toast('Local demo data deleted.','success');break;
    case 'reset-demo':openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Reset demo</span><h2>Restore the sample workspace?</h2><p class="modal-copy">This resets your local profile, searches and applications to the sample data.</p><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button" data-action="confirm-reset">Restore demo</button></div>`);break;
    case 'confirm-reset':cancelVoiceSearch(false);state=initialState();liveSearchByTurn.clear();liveSearchRequestByTurn.clear();liveSearch={chatId:null,turnId:null,query:'',status:'idle',jobs:[],sources:[]};persist();closeModal();render();toast('Sample workspace restored.','success');break;
    case 'logout':openModal(`<button class="modal-close" data-action="close-modal" aria-label="Close">×</button><span class="eyebrow">Account</span><h2>Log out of Hireloom?</h2><p class="modal-copy">This ends the current demo session. Your local profile and tracker data will remain saved in this browser.</p><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancel</button><button class="primary-button" data-action="confirm-logout">Log out</button></div>`);break;
    case 'confirm-logout':cancelVoiceSearch(false);session=false;state.loggedOut=true;state.view='login';liveSearchByTurn.clear();liveSearchRequestByTurn.clear();liveSearch={chatId:null,turnId:null,query:'',status:'idle',jobs:[],sources:[]};persist();closeModal();render();break;
    case 'continue-demo':state.loggedOut=false;state.view='chat';persist();if(getChat()?.hasSearch)startChatSearches(getChat());else render();toast('Returned to your saved demo workspace.','success');break;
    case 'plan-select':toast(`${action.dataset.plan} is a prototype plan. No payment is collected.`);break;
    case 'close-modal':pendingDeleteChatId=null;closeModal();break;
    case 'review-cv-draft':showCvDraftReview();break;
    case 'discard-cv-draft':state.pendingCvDraft=null;closeModal();render();toast('CV draft discarded.');break;
  }
});

document.addEventListener('change',(event)=>{
  const select=event.target.closest('[data-status-id]');if(!select)return;
  const app=state.applications.find((item)=>item.id===select.dataset.statusId);if(app){addHistory(app,select.value);persist();render();toast('Application status updated.','success');}
});
document.addEventListener('click',(event)=>{
  if(event.target.id==='modal-root')closeModal();
  if(!event.target.closest('#account-menu')&&!event.target.closest('#avatar-menu-button'))$('#account-menu').classList.add('hidden');
});
document.addEventListener('keydown',(event)=>{if(event.key==='Escape'){pendingDeleteChatId=null;closeModal();$('#account-menu').classList.add('hidden');state.sidebarOpen=false;updateShell();}});

render();

