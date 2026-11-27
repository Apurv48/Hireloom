const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public', 'app.js'), 'utf8');

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} not found in app.js`);
  const next = source.indexOf('\nfunction ', start + 1);
  return source.slice(start, next === -1 ? undefined : next);
}

// resolveFollowup only reaches queryLocationTerms for place follow-ups, which these cases do not use.
const context = vm.createContext({ queryLocationTerms: () => [] });
vm.runInContext(extractFunction('resolveFollowup'), context);
const follow = (prompt, previous) => context.resolveFollowup(prompt, previous);

test('a new experience level replaces the earlier one instead of adding to it', () => {
  assert.equal(
    follow('5 years experience', 'Remote Python jobs, English, 2+ years experience'),
    'Remote Python jobs, English, 5 years experience',
  );
  assert.equal(
    follow('with 3-5 years', 'Data engineer, 2+ years experience in India'),
    'Data engineer, in India 3-5 years experience',
  );
});

test('a new seniority replaces the earlier one and keeps the years', () => {
  assert.equal(follow('senior only', 'junior data analyst in India'), 'data analyst in India senior');
  assert.equal(
    follow('entry-level', 'Senior product manager, 4 years experience'),
    'product manager, 4 years experience entry-level',
  );
});

test('other follow-ups still resolve as before', () => {
  assert.equal(follow('remote', 'Data engineer in India'), 'Data engineer in India remote');
  assert.equal(follow('Python jobs', 'Data engineer in India'), 'Python jobs');
});
