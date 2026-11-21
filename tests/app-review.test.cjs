const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function browserLogic() {
  const context = vm.createContext({window:{HireloomScoring:require('../public/scoring')},
    document:{addEventListener(){}}, crypto:require('node:crypto'), structuredClone});
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
