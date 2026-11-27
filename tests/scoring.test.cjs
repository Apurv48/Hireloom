const test = require('node:test');
const assert = require('node:assert/strict');
const {atsScoreForProfile,workModePenalty,jdMatch} = require('../public/scoring.js');

test('the same synchronized profile always has the same ATS score', () => {
  const profile = {
    name:'Apurv Kumar', email:'apurv@example.com', phone:'+91 90000 00000',
    experience:[{title:'Analyst',company:'Example',detail:'Built reports'}],
    educationEntries:[{qualification:'MBA',institution:'Example University'}],
    skills:['Excel','SQL','Communication'],
  };
  const browserOne = JSON.parse(JSON.stringify(profile));
  const browserTwo = structuredClone(profile);
  assert.equal(atsScoreForProfile(browserOne),98);
  assert.equal(atsScoreForProfile(browserTwo),98);
});

test('duplicate or blank skills do not inflate the score', () => {
  const profile={skills:['Excel',' excel ','']};
  assert.equal(atsScoreForProfile(profile),67);
});

test('unknown or flexible job modes are not penalized', () => {
  assert.equal(workModePenalty(['Remote'],'Not listed'),0);
  assert.equal(workModePenalty(['Remote'],'Flexible'),0);
  assert.equal(workModePenalty(['Remote'],'Remote'),0);
  assert.equal(workModePenalty(['Remote'],'Onsite'),-6);
  assert.equal(workModePenalty([],'Onsite'),0);
});

test('a JD score can be reconstructed from applicable points and bonus', () => {
  const job={title:'Data Analyst',jdSignals:{requiredSkills:['SQL','Python'],preferredSkills:['Tableau'],
    minYears:2,credentials:['CPA'],degrees:[{level:'bachelor',field:'Statistics'}],languages:['Hindi']}};
  const profile={skills:['Tableau'],experience:[{title:'Data Analyst',dates:'Jan 2023 - Dec 2023',detail:'Built SQL models'}],
    educationEntries:[{qualification:'B.Sc. in Statistics'}],languageEntries:[{name:'Hindi',proficiency:'Fluent'}]};
  const match=jdMatch(job,profile);
  assert.equal(match.total,100);
  assert.equal(match.earned,62.5); // 20 skill + 20 title + 12.5 experience + 10 qualifications
  assert.equal(match.score,68);
  assert.equal(jdMatch(job,{...profile,skills:[]}).score,63);
  assert.equal(jdMatch(job,{...profile,name:'Another person',location:'Tokyo'}).score,68);
});

test('overlapping jobs count once and relevant skill tenure uses role-level evidence',()=>{
  const job={title:'Analyst',jdSignals:{minYears:2,experienceSkills:['SQL']}};
  const profile={experience:[
    {title:'Analyst',dates:'Jan 2023 - Dec 2023',detail:'Used SQL'},
    {title:'Analyst',dates:'Jul 2023 - Dec 2023',detail:'Wrote SQL'},
    {title:'Analyst',dates:'Jan 2019 - Dec 2021',detail:'Accounting'}]};
  assert.equal(jdMatch(job,profile).rows.find(r=>r.label.startsWith('Relevant')).fraction,0.5);
});

test('freshers, missing evidence, optional criteria and older snapshots',()=>{
  const fresh={title:'Graduate Analyst',jdSignals:{minYears:0,requiredSkills:['Python'],preferredSkills:['Excel']}};
  assert.equal(jdMatch(fresh,{skills:['Python']}).score,100);
  assert.equal(jdMatch(fresh,{}).score,null);
  assert.equal(jdMatch({}, {skills:['SQL']}).score,null);
  const old=jdMatch({title:'Analyst',skills:['Java'],match:65},{skills:['JavaScript']});
  assert.equal(old.score,0);
  assert.equal(old.legacy,true);
  const duties=jdMatch({jdSignals:{},jdRequirements:{responsibilities:['Build regional sales forecasts']}},
    {achievements:['Built regional sales forecasts for six teams']});
  assert.equal(duties.score,100);
});
