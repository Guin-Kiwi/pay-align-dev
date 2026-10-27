const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load(fetchImpl, registry = {}) {
  const timers = [];
  const assigned = [];
  const context = {
    fetch: fetchImpl, AbortController, timers,
    setTimeout: (callback, delay) => { timers.push({callback, delay}); return timers.length; },
    clearTimeout: () => {},
    window: {location: {assign: url => assigned.push(url)}},
    document: {
      getElementById: id => registry[id] ?? ({id}),
      createElement: tag => ({
        tag, children: [], className: '', attributes: {}, text: '',
        get textContent() { return this.text + this.children.map(child => child.textContent).join(''); },
        set textContent(value) { this.text = String(value); this.children = []; },
        append(...children) { this.children.push(...children); },
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(type, callback) { this.listeners = {...this.listeners, [type]: callback}; }
      })
    },
  };
  const source = fs.readFileSync(process.argv[2], 'utf8');
  vm.runInNewContext(`${source}\nthis.helpers = {element, call, fetchCsrfToken, wireWarningDialog, monthNames, monthLabel, longDate, employmentSubheading, employeeCard, cardRows, cardNote, formatMoney, formatDuration, todoRows, limitText, limitBar};`, context);
  return {...context.helpers, timers, assigned};
}

const same = (actual, expected) => assert.equal(JSON.stringify(actual), JSON.stringify(expected));
const reply = (status, body) => ({status, json: async () => { if (body === undefined) throw new Error('no body'); return body; }});

(async () => {
  same(load(async () => reply(200, {})).element('save'), {id: 'save'});

  let seen;
  const { call, timers } = load(async (url, options) => { seen = {url, options}; return reply(200, {ok: true}); });
  same(await call('/x', {method: 'POST', headers: {A: 'b'}}), {status: 200, body: {ok: true}});
  assert.equal(seen.url, '/x');
  assert.equal(seen.options.method, 'POST');
  same(seen.options.headers, {A: 'b'});
  assert.equal(timers[0].delay, 10000);
  assert.equal(seen.options.signal.aborted, false);
  timers[0].callback();
  assert.equal(seen.options.signal.aborted, true);

  const custom = load(async () => reply(200, {}));
  await custom.call('/x', {}, 15000);
  assert.equal(custom.timers[0].delay, 15000);

  same(await load(async () => reply(204)).call('/x'), {status: 204, body: null});

  let csrf;
  const ok = load(async (url, options) => { csrf = {url, options}; return reply(200, {csrf_token: 'token-1'}); });
  assert.equal(await ok.fetchCsrfToken(), 'token-1');
  assert.equal(csrf.url, '/api/v1/auth/csrf');
  same(csrf.options.headers, {Accept: 'application/json'});
  assert.equal(csrf.options.cache, 'no-store');

  let csrfRequests = 0;
  const shared = load(async () => { csrfRequests++; return reply(200, {csrf_token: 'shared-token'}); });
  same(await Promise.all([shared.fetchCsrfToken(), shared.fetchCsrfToken()]), ['shared-token', 'shared-token']);
  assert.equal(csrfRequests, 1);

  for (const [status, body] of [[500, {detail: 'boom'}], [200, {}], [200, {csrf_token: ''}], [200, {csrf_token: 7}]]) {
    await assert.rejects(load(async () => reply(status, body)).fetchCsrfToken());
  }
  const control = () => ({listeners: {}, closed: 0, addEventListener(type, fn) { this.listeners[type] = fn; }, close() { this.closed++; }});
  const dialog = control(), yes = control(), no = control();
  let busy = false, confirmed = 0;
  const { wireWarningDialog } = load(async () => reply(200, {}), {d: dialog, y: yes, n: no});
  wireWarningDialog({dialogId: 'd', confirmId: 'y', cancelId: 'n', onConfirm: () => { confirmed++; }, isBusy: () => busy});
  yes.listeners.click();
  assert.equal(confirmed, 1);
  no.listeners.click();
  assert.equal(dialog.closed, 1);
  const escape = () => ({prevented: false, preventDefault() { this.prevented = true; }});
  const idle = escape();
  dialog.listeners.cancel(idle);
  assert.equal(idle.prevented, false);
  busy = true;
  yes.listeners.click();
  no.listeners.click();
  assert.equal(confirmed, 1);
  assert.equal(dialog.closed, 1);
  const saving = escape();
  dialog.listeners.cancel(saving);
  assert.equal(saving.prevented, true);
  const helpers = load(async () => reply(200, {}));
  assert.equal(helpers.monthNames.length, 12);
  assert.equal(helpers.monthLabel(2026, 3), 'March 2026');
  for (const [iso, text] of [
    ['2026-01-01', '1st January 2026'], ['2026-02-02', '2nd February 2026'], ['2026-03-03', '3rd March 2026'],
    ['2026-04-04', '4th April 2026'], ['2026-05-11', '11th May 2026'], ['2026-06-12', '12th June 2026'],
    ['2026-07-13', '13th July 2026'], ['2026-08-21', '21st August 2026'], ['2026-09-22', '22nd September 2026'],
    ['2026-10-23', '23rd October 2026'], ['2026-11-30', '30th November 2026'], ['2026-12-31', '31st December 2026']
  ]) assert.equal(helpers.longDate(iso), text);
  assert.equal(helpers.longDate('not a date'), 'not a date');
  assert.equal(helpers.employmentSubheading({start_date: '2026-10-01', end_date: null}), 'Employment started on 1st October 2026');
  assert.equal(helpers.employmentSubheading({start_date: '2026-01-05', end_date: '2026-06-30'}), 'Employment started on 5th January 2026 · ends on 30th June 2026');

  const card = helpers.employeeCard({employee_name: 'Lea Beispiel', start_date: '2026-10-01', end_date: null});
  assert.equal(card.tag, 'li');
  assert.equal(card.className, 'employee-card');
  assert.equal(card.children[0].tag, 'h3');
  assert.equal(card.children[0].textContent, 'Lea Beispiel');
  assert.equal(card.children[1].className, 'subheading');
  assert.equal(card.children[1].textContent, 'Employment started on 1st October 2026');

  const button = {tag: 'button', children: [], textContent: 'Enter'};
  const table = helpers.cardRows([{label: 'Next to enter', value: 'March 2026', action: button}, {label: 'Last saved', value: 'None'}]);
  assert.equal(table.tag, 'table');
  assert.equal(table.className, 'card-rows');
  const rows = table.children[0].children;
  same(rows.map(row => row.children.map(cell => cell.tag)), [['th', 'td', 'td'], ['th', 'td', 'td']]);
  assert.equal(rows[0].children[0].attributes.scope, 'row');
  same(rows.map(row => row.children.map(cell => cell.textContent)), [['Next to enter', 'March 2026', 'Enter'], ['Last saved', 'None', '']]);
  assert.equal(rows[0].children[2].className, 'action');
  assert.equal(rows[0].children[2].children[0], button);
  const picker = {tag: 'select', children: [], textContent: ''};
  const withControl = helpers.cardRows([{label: 'Payslip', value: picker, action: button}]).children[0].children[0].children;
  assert.equal(withControl[1].children[0], picker);
  assert.equal(withControl[1].text, '');
  for (const [value, text] of [['0.00', 'CHF 0.00'], ['5.50', 'CHF 5.50'], ['1105.00', 'CHF 1,105.00'], ['9970.80', 'CHF 9,970.80'], ['1234567.89', 'CHF 1,234,567.89']]) {
    assert.equal(helpers.formatMoney(value), text);
  }
  for (const bad of ['12', '12.5', 'abc', '', undefined]) assert.throws(() => helpers.formatMoney(bad));
  for (const [minutes, text] of [[0, '0 h 00 min'], [65, '1 h 05 min'], [360, '6 h 00 min'], [750, '12 h 30 min']]) {
    assert.equal(helpers.formatDuration(minutes), text);
  }
  for (const bad of [-150, 1.5, '60', NaN, undefined]) assert.throws(() => helpers.formatDuration(bad));
  const lea = {name: 'Lea Beispiel', employments: [{id: 7, start_date: '2026-01-05', months_due: 2, next_month: {year: 2026, month: 3}}]};
  const todo = helpers.todoRows(lea);
  same(todo.map(row => [row.label, row.value]), [['Timesheet', 'Enter March 2026 (2 months behind)']]);
  assert.equal(todo[0].action.textContent, 'Enter');
  assert.equal(todo[0].action.attributes['aria-label'], 'Enter March 2026 for Lea Beispiel');
  todo[0].action.listeners.click();
  same(helpers.assigned, ['/timesheets?employment_id=7']);
  same(helpers.todoRows(lea, true).map(row => row.label), ['Lea Beispiel']);
  same(helpers.todoRows({...lea, employments: [{...lea.employments[0], months_due: 1}]}).map(row => row.value), ['Enter March 2026']);
  same(helpers.todoRows({...lea, employments: [{...lea.employments[0], months_due: 0}, {id: 8, start_date: '2026-08-01', months_due: 1, next_month: null}]}), []);
  const two = {name: 'Nora Doppelt', employments: [lea.employments[0], {id: 11, start_date: '2026-08-01', months_due: 1, next_month: {year: 2026, month: 9}}]};
  same(helpers.todoRows(two).map(row => row.label), ['Timesheet · employment from 5th January 2026', 'Timesheet · employment from 1st August 2026']);
  const limit = {used: '9000.00', limit: '22680.00', remaining: '13680.00'};
  assert.equal(helpers.limitText(limit), 'CHF 9,000.00 of CHF 22,680.00 used · CHF 13,680.00 remaining');
  const bar = helpers.limitBar(limit, 'This employee');
  assert.deepEqual([bar.tag, bar.className, bar.max, bar.value], ['progress', 'limit-bar', 22680, 9000]);
  assert.equal(bar.attributes['aria-label'], 'This employee: wage limit used');
  const note = helpers.cardNote('Not employed in this month.');
  assert.equal(note.tag, 'p');
  assert.equal(note.className, 'note');
  assert.equal(note.textContent, 'Not employed in this month.');
  process.stdout.write('ok');
})().catch(error => { console.error(error); process.exitCode = 1; });
