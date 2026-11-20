const test = require('node:test');
const assert = require('node:assert/strict');
const {atsScoreForProfile,workModePenalty} = require('../public/scoring.js');

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
