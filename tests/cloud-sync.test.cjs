const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function workspace(write) {
  let owner = 'first';
  const sb = {
    auth: {onAuthStateChange(){},getSession: async () => ({data:{session:{user:{id:owner}}}})},
    from: () => ({upsert: write})
  };
  const window = {
    HIRELOOM_SUPABASE:{url:'test', anonKey:'test'},
    supabase:{createClient:()=>sb}, addEventListener(){}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/cloud.js'),'utf8'),
    {window,document:{addEventListener(){}},setTimeout,clearTimeout,structuredClone});
  return {cloud:window.HireloomCloud,switchUser:id=>{owner=id;}};
}

test('saves finish in edit order, including edits made during a write', async () => {
  const writes=[];
  let release;
  let started;
  const waiting=new Promise(resolve=>{started=resolve;});
  const {cloud}=workspace(async row=>{
    writes.push(row.state.value);
    if(writes.length===1){started();await new Promise(resolve=>{release=resolve;});}
    return {};
  });
  cloud.queuePush(()=>({value:1}),'first');
  const saving=cloud.flush();
  await waiting;
  cloud.queuePush(()=>({value:2}),'first');
  const draining=cloud.flush();
  release();
  await Promise.all([saving,draining]);
  assert.deepEqual(writes,[1,2]);
});

test('failed writes stay available for retry and cannot go to another user', async () => {
  let fail=true;
  const writes=[];
  const {cloud,switchUser}=workspace(async row=>{
    if(fail)throw Error('Offline');
    writes.push(row);return {};
  });
  const original={value:1};
  cloud.queuePush(()=>original,'first');
  original.value=9;
  await assert.rejects(cloud.flush(), /Offline/);
  fail=false;switchUser('second');
  await assert.rejects(cloud.flush(), /owner changed/);
  switchUser('first');
  await cloud.flush();
  assert.equal(writes.length,1);
  assert.equal(writes[0].user_id,'first');
  assert.equal(writes[0].state.value,1);
});
