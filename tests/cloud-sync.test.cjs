const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('a stale second session cannot revert a saved profile by navigating', async () => {
  const writes=[];
  const {cloud,setRemote}=workspace(async row=>{writes.push(row);return {};});
  setRemote({state:{phone:'old'},updated_at:'2026-01-01T00:00:00Z'});
  const stale=await cloud.pull('first');
  setRemote({state:{phone:'new'},updated_at:'2026-01-02T00:00:00Z'});
  cloud.queuePush(()=>({...stale,view:'tracker'}),'first');
  await assert.rejects(cloud.flush(),/Another session/);
  assert.equal(writes.length,0);
});

function workspace(write) {
  let owner = 'first';
  let remoteRow = null;
  let signedOut = false;
  const values = new Map();
  const localStorage = {
    getItem:key => values.has(key) ? values.get(key) : null,
    setItem:(key,value) => values.set(key,String(value)),
    removeItem:key => values.delete(key),
  };
  function mutation(row, expected) {
    return {select:()=>({maybeSingle:async()=>{
      if ((remoteRow?.updated_at || null) !== expected) return {data:null};
      const result = await write(row);
      if(result.error)return result;
      remoteRow=structuredClone(row);
      return {data:{updated_at:row.updated_at}};
    }})};
  }
  const sb = {
    auth: {
      onAuthStateChange(){},
      getSession: async () => ({data:{session:{user:{id:owner},access_token:'fixture-'+owner}}}),
      signOut: async () => {signedOut=true;return {};},
    },
    from: () => ({
      insert: row => mutation(row, null),
      update: row => ({eq: () => ({eq: (_, expected) => mutation(row, expected)})}),
      select: () => ({eq: () => ({maybeSingle: async () => ({data:remoteRow})})}),
    })
  };
  const window = {
    HIRELOOM_SUPABASE:{url:'test', anonKey:'test'},
    supabase:{createClient:()=>sb}, addEventListener(){}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/cloud.js'),'utf8'),
    {window,document:{addEventListener(){}},localStorage,setTimeout,clearTimeout,structuredClone});
  return {cloud:window.HireloomCloud,switchUser:id=>{owner=id;},localStorage,wasSignedOut:()=>signedOut,setRemote:value=>{remoteRow=value;}};
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

test('recovers an interrupted pending snapshot on the next pull', async () => {
  let fail=true;
  const writes=[];
  const {cloud}=workspace(async row=>{
    if(fail) return {error:new Error('Offline')};
    writes.push(row.state);return {};
  });
  cloud.queuePush(()=>({value:7}),'first');
  await assert.rejects(cloud.flush(), /Offline/);
  const recovered=await cloud.pull('first');
  assert.equal(recovered.value,7);
  fail=false;
  await cloud.flush();
  assert.equal(JSON.stringify(writes),JSON.stringify([{value:7}]));
});

test('newer cloud data wins over a stale pending browser snapshot', async () => {
  const writes=[];
  const {cloud,localStorage,setRemote}=workspace(async row=>{writes.push(row.state);return {};});
  cloud.queuePush(()=>({value:'stale'}),'first');
  const local=JSON.parse(localStorage.getItem('hireloom-cloud-pending:first'));
  setRemote({state:{value:'current'},updated_at:new Date(local.savedAt+1000).toISOString()});
  const pulled=await cloud.pull('first');
  assert.equal(pulled.value,'current');
  assert.equal(localStorage.getItem('hireloom-cloud-pending:first'),null);
  await cloud.flush();
  assert.equal(writes.length,0);
});

test('CV upload checks the owner of the token after reading the file', async () => {
  const {cloud,switchUser} = workspace(async () => ({}));
  const file = {name:'cv.pdf',size:5,slice:()=>({
    arrayBuffer:async()=>{switchUser('second');return Uint8Array.from(Buffer.from('%PDF-')).buffer;}
  })};
  await assert.rejects(cloud.uploadCv(file,'first'), /Account changed/);
});

test('account deletion rejects a different account or email before touching storage', async () => {
  const {cloud}=workspace(async()=>({}));
  cloud.getUser=async()=>({id:'first',email:'Person@example.com'});
  await assert.rejects(cloud.deleteAccount('second','person@example.com'), /Account changed/);
  await assert.rejects(cloud.deleteAccount('first','other@example.com'), /email address/);
});

test('a failed Auth deletion leaves the stored CV untouched', async () => {
  let removals=0;
  const sb={
    auth:{onAuthStateChange(){},getSession:async()=>({data:{session:{user:{id:'first',email:'person@example.com'}}}})},
    storage:{from:()=>({list:async()=>({data:[{name:'cv.pdf'}]}),remove:async()=>{removals++;return {};}})},
    rpc:async()=>({error:new Error('Auth deletion failed')}),
  };
  const window={HIRELOOM_SUPABASE:{url:'test',anonKey:'test'},supabase:{createClient:()=>sb},addEventListener(){}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/cloud.js'),'utf8'),
    {window,document:{addEventListener(){}},setTimeout,clearTimeout});
  await assert.rejects(window.HireloomCloud.deleteAccount('first','person@example.com'),/Auth deletion failed/);
  assert.equal(removals,0);
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

test('logout waits for an in-flight save and any edit queued behind it', async () => {
  const writes=[];
  let release;
  let started;
  const waiting=new Promise(resolve=>{started=resolve;});
  const {cloud,wasSignedOut}=workspace(async row=>{
    writes.push(row.state.value);
    if(writes.length===1){started();await new Promise(resolve=>{release=resolve;});}
    return {};
  });
  cloud.queuePush(()=>({value:1}),'first');
  const saving=cloud.flush();
  await waiting;
  cloud.queuePush(()=>({value:2}),'first');
  const logout=cloud.signOut();
  assert.equal(wasSignedOut(),false);
  release();
  await Promise.all([saving,logout]);
  assert.deepEqual(writes,[1,2]);
  assert.equal(wasSignedOut(),true);
});
