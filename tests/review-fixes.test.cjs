const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public', 'app.js'), 'utf8');

// Pull one top-level function out of app.js so it can be run with stubbed state.
function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} not found in app.js`);
  const next = source.indexOf('\nfunction ', start + 1);
  return source.slice(start, next === -1 ? undefined : next);
}

test('tracker offers only the statuses the app records', () => {
  const context = vm.createContext({
    state: { applications: [], trackerFilter: 'All' },
    esc: (value) => String(value ?? ''),
    getJob: () => null,
  });
  vm.runInContext(extractFunction('renderTracker'), context);
  const html = context.renderTracker();
  const labels = [...html.matchAll(/data-tracker-filter="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(labels, ['All', 'Applied', 'Not applied', 'External follow-up']);
});

test('German job words are replaced only as whole words', () => {
  const context = vm.createContext({ voiceLanguage: 'en-US' });
  vm.runInContext(extractFunction('normalizeVoiceQuery'), context);
  assert.equal(context.normalizeVoiceQuery('Stellenangebote Entwickler in München'), 'jobs developer in Munich');
  assert.equal(context.normalizeVoiceQuery('Ich möchte vorstellen Python'), 'Ich möchte vorstellen Python');
});

test('a saved tracker filter that no longer exists falls back to All', () => {
  const context = vm.createContext({
    state: { applications: [], trackerFilter: 'Interview' },
    esc: (value) => String(value ?? ''),
    getJob: () => null,
  });
  vm.runInContext(extractFunction('renderTracker'), context);
  const html = context.renderTracker();
  assert.equal(context.state.trackerFilter, 'All');
  assert.match(html, /class="tracker-filter active" data-tracker-filter="All"/);
});
