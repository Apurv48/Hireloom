const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('a truncated employer preview ends at the last complete sentence or word', () => {
  const run=browserLogic();
  assert.equal(run("jobDescriptionPreview({isLive:true,description:'x'.repeat(1170)+'. '+ 'w'.repeat(28)})"),
    'x'.repeat(1170)+'.');
  assert.equal(run("jobDescriptionPreview({isLive:true,description:'x'.repeat(1190)+' unfinishe'})"),
    'x'.repeat(1190)+'…');
});

function browserLogic() {
  const context = vm.createContext({window:{HireloomScoring:require('../public/scoring')},
    document:{addEventListener(){}}, localStorage:{getItem:()=>null,setItem(){}},
    crypto:require('node:crypto'), structuredClone, TextEncoder});
  const source = fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8');
  vm.runInContext(source.slice(0,source.lastIndexOf('\nrender();')),context);
  return code => vm.runInContext(code,context);
}

test('new profiles and conversational locations', () => {
  const run=browserLogic();
  assert.equal(run("newWorkspace('A','a@example.com').profile.languageEntries.length"),0);
  assert.equal(run("newWorkspace('A','a@example.com').profile.educationEntries.length"),0);
  assert.equal(run("queryLocationTerms('help us build a global brand').length"),0);
  assert.equal(run("queryLocationTerms('analyst in the US').includes('us')"),true);
});

test('experience and seniority follow-ups retain the role, location and work mode', () => {
  const run=browserLogic();
  assert.equal(run("resolveFollowup('I have 3 years of experience', 'Senior analyst in India remote with 5 years experience')"),
    'Senior analyst in India remote with 3 years experience');
  assert.equal(run("resolveFollowup('Only junior roles', 'Senior analyst in India remote')"),
    'analyst in India remote junior');
});

test('cloud sign-in saves a new workspace and retains existing profile edits', async () => {
  const run = browserLogic();
  await run(`const user={id:'user-1',name:'Signup Name',email:'account@example.com'};
    const saves=[];
    cloud.enabled=true;
    cloud.pull=async()=>null;
    cloud.queuePush=(snapshot,owner)=>saves.push({state:snapshot(),owner});
    render=()=>{};
    toast=()=>{};
    (async()=>{
      await enterCloudWorkspace(user);
      cloud.pull=async()=>({...saves[0].state,profile:{...saves[0].state.profile,name:'Edited Name'}});
      await enterCloudWorkspace(user);
    })()`);
  assert.equal(run('saves.length'), 1);
  assert.equal(run('saves[0].owner'), 'user-1');
  assert.equal(run('saves[0].state.profile.name'), 'Signup Name');
  assert.equal(run('saves[0].state.profile.email'), 'account@example.com');
  assert.equal(run('state.profile.name'), 'Edited Name');
});

test('editing an ancestor recomputes dependent turns and preserves independent searches', () => {
  const run=browserLogic();
  const result=run(`cancelVoiceSearch=()=>{}; const refreshed=[];
    startLiveSearch=(chat,force,id)=>refreshed.push(id);
    const chat={turns:[{id:'a',query:'Python in India',searchQuery:'Python in India'},
      {id:'b',query:'only remote ones',searchQuery:'Python in India remote'},
      {id:'c',query:'chef',searchQuery:'chef'}]};
    editPromptInPlace(chat,chat.turns[0],'Java in Berlin');
    [chat.turns[1].searchQuery,refreshed.sort().join(',')]`);
  assert.deepEqual(Array.from(result),['Java in Berlin remote','a,b']);
});

test('a combined follow-up keeps the title and replaces work mode and location', () => {
  const run=browserLogic();
  assert.equal(run("resolveFollowup('Only remote ones in Germany','Data analyst in India hybrid with 3 years experience')"),
    'Data analyst with 3 years experience in Germany remote');
});

test('a fresher follow-up replaces prior seniority and experience', () => {
  const run=browserLogic();
  assert.equal(run("resolveFollowup('for freshers','Senior data analyst in India with 5 years experience')"),
    'data analyst in India freshers');
});

test('voice matches whole words, posting age uses publication time, and CV evidence can come from a later role', () => {
  const run = browserLogic();
  assert.equal(run("normalizeVoiceQuery('Stellen erstellen Ölstellen')"), 'jobs erstellen Ölstellen');
  assert.equal(run("postingAge({published:Date.now()/1000-3*86400,posted:'Today'})"), '3 days ago');
  assert.equal(run("new Set(Array.from({length:100},()=>makeSearchTurn('jobs').id)).size"), 100);
  assert.equal(run(`state.profile.experience=[{detail:'Maintained reports'},{detail:'Used Python daily'}];
    tailorContent({skills:['Python']}).experienceIndex`), 1);
  assert.equal(run(`state.profile.experience=[{title:'Operations Manager',detail:'Maintained reports'},{title:'Accountant',detail:'Prepared statements'}];
    tailorContent({title:'Accountant',skills:[]}).experienceIndex`), 1);
  assert.equal(run("atsScoreForProfile({skills:['Excel',{},null]})"),67);
});
