const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function element(extra = {}) {
  return {dataset: {}, listeners: {}, attributes: {}, hidden: true, disabled: false, textContent: '',
    addEventListener(type, callback) { this.listeners[type] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; }, ...extra};
}

function run({historyLength = 1, withBack = true, warning = '', answer = true, logoutStatus = 204}) {
  const home = element({dataset: {route: '/home', home: ''}});
  const employees = element({dataset: {route: '/employees'}});
  const navigation = element({dataset: {currentRoute: '/employees'}, querySelector: selector => (selector === '[data-home]' ? home : null)});
  const back = element();
  const logout = element();
  const status = element();
  const seen = {back: 0, assigned: [], replaced: [], confirms: [], fetches: 0, requests: []};
  const byId = {'back-button': withBack ? back : null, 'logout-button': logout, 'navigation-status': status};
  const context = {
    document: {
      cookie: 'csrf_token=abc',
      querySelector: selector => (selector === '.app-navigation' ? navigation : null),
      querySelectorAll: () => [home, employees],
      getElementById: id => byId[id] ?? null
    },
    window: {
      history: {length: historyLength, back() { seen.back++; }},
      location: {assign(url) { seen.assigned.push(url); }, replace(url) { seen.replaced.push(url); }},
      confirm(message) { seen.confirms.push(message); return answer; },
      leaveWarning: warning === null ? undefined : () => warning
    },
    fetch: async (url, options) => { seen.fetches++; seen.requests.push({url, options}); return {status: logoutStatus}; }
  };
  vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), context);
  return {back, logout, employees, status, seen};
}

const settle = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  // Back goes back, or home when there is no earlier page
  const earlier = run({historyLength: 3});
  earlier.back.listeners.click();
  assert.equal(earlier.seen.back, 1);
  assert.deepEqual(earlier.seen.assigned, []);
  assert.deepEqual(earlier.seen.confirms, []);

  const first = run({historyLength: 1});
  first.back.listeners.click();
  assert.equal(first.seen.back, 0);
  assert.deepEqual(first.seen.assigned, ['/home']);

  const home = run({withBack: false});
  home.employees.listeners.click();
  assert.deepEqual(home.seen.assigned, ['/employees']);

  // a page without a warning function never asks
  const unaware = run({historyLength: 3, warning: null});
  unaware.back.listeners.click();
  assert.equal(unaware.seen.back, 1);
  assert.deepEqual(unaware.seen.confirms, []);

  // unsaved work: declining stays, accepting leaves, for Back, the menu and Log out
  const warning = 'Discard the entries and leave this page?';
  const declined = run({historyLength: 3, warning, answer: false});
  declined.back.listeners.click();
  declined.employees.listeners.click();
  declined.logout.listeners.click();
  await settle();
  assert.deepEqual(declined.seen.confirms, [warning, warning, warning]);
  assert.equal(declined.seen.back, 0);
  assert.deepEqual(declined.seen.assigned, []);
  assert.equal(declined.seen.fetches, 0);
  assert.deepEqual(declined.seen.replaced, []);

  const accepted = run({historyLength: 3, warning, answer: true});
  accepted.back.listeners.click();
  accepted.employees.listeners.click();
  accepted.logout.listeners.click();
  await settle();
  assert.equal(accepted.seen.back, 1);
  assert.deepEqual(accepted.seen.assigned, ['/employees']);
  assert.equal(accepted.seen.fetches, 1);
  assert.deepEqual(accepted.seen.replaced, ['/login']);

  // A rejected logout does not claim the session ended or redirect to login.
  const rejected = run({logoutStatus: 403});
  await rejected.logout.listeners.click();
  assert.equal(rejected.seen.fetches, 1);
  assert.equal(rejected.seen.requests[0].url, '/api/v1/auth/logout');
  assert.equal(rejected.seen.requests[0].options.method, 'POST');
  assert.equal(rejected.seen.requests[0].options.headers['X-CSRF-Token'], 'abc');
  assert.deepEqual(rejected.seen.replaced, []);
  assert.equal(rejected.status.hidden, false);
  assert.match(rejected.status.textContent, /could not confirm logout/i);
  assert.equal(rejected.logout.disabled, false);
  process.stdout.write('ok');
})().catch(error => { console.error(error); process.exitCode = 1; });
