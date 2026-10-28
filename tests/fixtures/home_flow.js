const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const INPUT = JSON.parse(fs.readFileSync(0, 'utf8'));
const YEAR = INPUT.year;
const pad = number => String(number).padStart(2, '0');
const day = (month, date, year = YEAR) => `${year}-${pad(month)}-${pad(date)}`;
const payslipPage = (month, id) => `/payslips?employment_id=${id}&year=${YEAR}&month=${month}`;
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const label = month => `${MONTH_NAMES[month - 1]} ${YEAR}`;
const ordinal = number => `${number}${[11, 12, 13].includes(number % 100) ? 'th' : {1: 'st', 2: 'nd', 3: 'rd'}[number % 10] ?? 'th'}`;
const long = (month, date) => `${ordinal(date)} ${MONTH_NAMES[month - 1]} ${YEAR}`;
const range = (first, last) => Array.from({length: last - first + 1}, (_, index) => first + index);
// Date.UTC takes a zero-based month, so 9 is October.
const OCTOBER_27 = [YEAR, 9, 27];

const SESSION_EXPIRED = {detail: 'Authentication required.'};
const employment = (id, name, start, end = null) => ({id, employee_name: name, start_date: start, end_date: end});
const LEA = employment(7, 'Lea Beispiel', day(1, 5), day(6, 30));
const LEA_AGAIN = employment(8, 'Lea Beispiel', day(8, 1));
const MARCO = employment(9, 'Marco Probe', day(3, 2));
const NORA = employment(10, 'Nora Fertig', day(1, 5), day(2, 28));
const JAN = employment(11, 'Jan Neu', day(10, 27));
const SAM = employment(12, 'Sam Spaet', day(3, 2));
const EVA = employment(13, 'Eva Eins', day(3, 2));
const HISTORIES = {
  7: {saved: [1, 2], next: 3},
  8: {saved: [8, 9, 10], next: 11},
  9: {saved: range(3, 9), next: 10},
  10: {saved: [1, 2], next: null},
  11: {saved: [], next: 10},
  12: {saved: [3], next: 4},
  13: {saved: range(3, 8), next: 9}
};
const PAYSLIP = {
  net_payout: '900.00', total_employer_cost: '1105.00', holiday_balance_minutes: 600, ahv_deduction: '50.00',
  alv_deduction: '20.00', tax_deduction: '50.00', nbu_deduction: '0.00', employer_ahv: '50.00', employer_alv: '10.00',
  employer_fak: '10.00', employer_bu: '10.00', admin_charge: '5.00'
};
const taskPerson = (id, name, employmentId, due, next) => ({
  id, name, employments: [{id: employmentId, start_date: day(1, 5), end_date: null, months_due: due, next_month: next ? {year: YEAR, month: next} : null}]
});
const HOUSEHOLD = {used: '15000.00', limit: '60480.00', remaining: '45480.00'};
const response = (status, body) => ({status, json: async () => body});

function makeElement(tag = 'div', attrs = {}) {
  let text = '';
  return {
    tag, id: attrs.id, value: attrs.value ?? '', hidden: Object.hasOwn(attrs, 'hidden'),
    disabled: Object.hasOwn(attrs, 'disabled'), children: [], listeners: {}, dataset: {},
    get textContent() { return text + this.children.map(child => child.textContent ?? '').join(''); },
    set textContent(value) { text = String(value); this.children = []; },
    addEventListener(event, callback) { this.listeners[event] = callback; },
    setAttribute(name, value) { this[name] = value; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    focus() { this.focused = true; },
    set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  };
}

function makeBrowser(spec, attributes) {
  const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, makeElement('existing', {id, ...attrs})]));
  const calls = [];
  const redirects = [];
  const today = new Date(Date.UTC(...(spec.today ?? OCTOBER_27)));
  class FixedDate extends Date {
    constructor(...args) { if (args.length === 0) super(today.getTime()); else super(...args); }
    static now() { return today.getTime(); }
  }
  const histories = spec.histories ?? HISTORIES;
  const context = {
    document: {
      getElementById(id) { assert.ok(elements[id], `The page has no element #${id}`); return elements[id]; },
      createElement(tag) { return makeElement(tag); }
    },
    window: {listeners: {}, addEventListener(type, listener) { this.listeners[type] = listener; }, location: {replace(url) { redirects.push(url); }, assign(url) { redirects.push(url); }}},
    Date: FixedDate, AbortController, setTimeout, clearTimeout,
    async fetch(url, options = {}) {
      calls.push({url, method: options.method ?? 'GET', headers: options.headers ?? {}, body: options.body});
      if (url === '/api/v1/auth/csrf') return response(200, {csrf_token: 'csrf-token'});
      if (url === '/api/v1/employer') {
        return spec.noEmployer
          ? response(404, {detail: 'No employer is set up yet.'})
          : response(200, {id: 1, name: 'Anna', address: 'Basel', ahv_number: '756.1234.5678.97', contact_info: 'a@example.ch'});
      }
      if (url === '/api/v1/employees') {
        return spec.employeesStatus
          ? response(spec.employeesStatus, {detail: 'boom'})
          : response(200, {employees: spec.people ?? [], household: spec.household ?? null});
      }
      if (url === '/api/v1/employments') {
        return spec.listStatus ? response(spec.listStatus, SESSION_EXPIRED) : response(200, spec.employments ?? [LEA]);
      }
      const history = /^\/api\/v1\/employments\/(\d+)\/months$/.exec(url);
      if (history) {
        const id = Number(history[1]);
        if (spec.failingHistory === id) return response(500, {detail: 'boom'});
        const {saved, next} = histories[id];
        return response(200, {
          months: saved.map(month => ({monthly_record_id: month, year: YEAR, month})),
          next_month: next ? {year: YEAR, month: next} : null
        });
      }
      if (url.startsWith('/api/v1/payroll-overview?')) {
        const first = (spec.employments ?? [LEA])[0];
        return response(200, spec.overview ?? {
          eligible_count: 2, saved_count: 1, payout_due: '900.00', estimated_set_aside: '205.00', employer_cost: '1105.00',
          employments: [{employment: {id: first.id, employee_name: first.employee_name}, next_month: {year: YEAR, month: 3}, payslip: PAYSLIP}]
        });
      }
      if (url === '/api/v1/auth/logout') {
        assert.equal(options.method, 'POST');
        return spec.logoutRejected ? response(403, {detail: 'Invalid CSRF token.'}) : response(204);
      }
      throw new Error(`Unexpected request ${url}`);
    }
  };
  return {elements, calls, redirects, context};
}

function makePage({elements, calls, redirects, context}) {
  const settle = async () => { for (let index = 0; index < 100; index++) await Promise.resolve(); };
  const buttons = node => node.children.flatMap(child => [...(child.tag === 'button' ? [child] : []), ...buttons(child)]);
  const click = async target => { const result = target.listeners.click?.({preventDefault() {}}); await result; await settle(); };
  const el = id => elements[id];
  return {
    el, calls, redirects, settle, buttons, click, events: context.window.listeners,
    row: index => el('employment-list').children[index],
    named: (node, name) => buttons(node).find(button => button.textContent === name),
    rowsOf: card => {
      const table = card.children.find(child => child.tag === 'table');
      return table ? table.children[0].children.map(row => row.children.map(cell => cell.textContent)) : [];
    },
    overviewRequest: () => calls.find(call => call.url.startsWith('/api/v1/payroll-overview?')).url
  };
}

const scenarios = {
  'overview-refresh-after-save': {run: async p => {
    const before = p.calls.filter(call => call.url.startsWith('/api/v1/payroll-overview?')).length;
    await p.events['payalign-payroll-saved']();
    assert.equal(p.calls.filter(call => call.url.startsWith('/api/v1/payroll-overview?')).length, before + 1);
    assert.equal(p.calls.filter(call => call.url === '/api/v1/employees').length, 2);
  }},
  'cost-boxes': {employments: [LEA, MARCO], run: async p => {
    const [lea, marco] = [p.row(0), p.row(1)];
    const month = Number(p.el('overview-month').value);
    for (const card of [lea, marco]) {
      assert.equal(card.className, 'employee-card');
      assert.equal(card.children[0].tag, 'h3');
    }
    assert.equal(lea.children[0].textContent, 'Lea Beispiel');
    assert.equal(lea.children[1].textContent, `Employment started on ${long(1, 5)} · ends on ${long(6, 30)}`);
    assert.equal(marco.children[0].textContent, 'Marco Probe');
    assert.equal(marco.children[1].textContent, `Employment started on ${long(3, 2)}`);
    assert.deepEqual(p.rowsOf(lea), [
      ['Payout due', 'CHF 900.00', ''],
      ['Employer cost', 'CHF 1,105.00', ''],
      ['Holiday balance after this month', '10 h 00 min', ''],
      ['Payslip', label(month), 'View payslip']
    ]);
    assert.ok(p.named(lea, 'View payslip'));
    assert.match(marco.textContent, /Not employed in this month\./);
    assert.deepEqual(p.rowsOf(marco), []);
    for (const card of [lea, marco]) {
      assert.doesNotMatch(card.textContent, /Last saved|Enter|then |All months|from /);
      assert.equal(p.buttons(card).filter(button => button.textContent !== 'View payslip').length, 0);
    }
  }},
  'no-saved-payroll': {employments: [LEA], overview: {eligible_count: 1, saved_count: 0, payout_due: '0.00', estimated_set_aside: '0.00', employer_cost: '0.00', employments: [{employment: {id: 7, employee_name: 'Lea Beispiel'}, next_month: {year: YEAR, month: 3}, payslip: null}]}, run: async p => {
    assert.match(p.row(0).textContent, /No saved payroll for this month\./);
    assert.equal(p.buttons(p.row(0)).length, 0);
  }},
  'months-unavailable': {employments: [LEA, MARCO], failingHistory: 7, run: async p => {
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.el('overview-month').value, '9');
    assert.match(p.row(0).textContent, /Lea Beispiel/);
  }},
  'default-month-latest-saved': {employments: [MARCO], histories: {9: {saved: range(3, 8), next: 9}}, run: async p => {
    assert.equal(p.el('overview-month').value, '8');
    assert.match(p.overviewRequest(), new RegExp(`year=${YEAR}&month=8$`));
  }},
  'default-month-across-employments': {employments: [LEA, LEA_AGAIN], run: async p => {
    assert.equal(p.el('overview-month').value, '10');
  }},
  'default-month-nothing-saved': {employments: [JAN], run: async p => {
    assert.equal(p.el('overview-month').value, '10');
  }},
  'default-month-after-the-year': {employments: [JAN], today: [YEAR + 1, 2, 3], run: async p => {
    assert.equal(p.el('overview-month').value, '12');
  }},
  'overview': {employments: [LEA, MARCO], run: async p => {
    assert.match(p.el('overview-cost').textContent, /1,105\.00/);
    assert.match(p.el('overview-payout').textContent, /900\.00/);
    assert.match(p.el('overview-reserve').textContent, /205\.00/);
    assert.match(p.el('overview-completeness').textContent, /1 of 2/);
  }},
  'overview-view-payslip': {run: async p => {
    const month = Number(p.el('overview-month').value);
    await p.click(p.named(p.row(0), 'View payslip'));
    assert.equal(p.redirects.at(-1), payslipPage(month, 7));
  }},
  'empty': {employments: [], run: async p => {
    assert.equal(p.el('employment-empty').hidden, false);
    assert.equal(p.el('employment-list').children.length, 0);
  }},
  'actions-in-the-boxes': {employments: [LEA, MARCO], people: [taskPerson(1, 'Lea Beispiel', 7, 2, 3), taskPerson(2, 'Marco Probe', 9, 0, 10)], run: async p => {
    const [lea, marco] = [p.row(0), p.row(1)];
    assert.equal(lea.children[2].textContent, '2 actions pending');
    assert.equal(lea.children[2].className, 'tasks pending');
    assert.equal(lea.className, 'employee-card pending');
    assert.deepEqual(p.rowsOf(lea).at(-1), ['Timesheet', `${label(3)} (2 months behind)`, 'Enter']);
    await p.click(p.named(lea, 'Enter'));
    assert.equal(p.redirects.at(-1), '/timesheets?employment_id=7');
    assert.equal(marco.children[2].textContent, 'All actions completed');
    assert.equal(marco.children[2].className, 'tasks done');
    assert.equal(marco.className, 'employee-card');
    assert.deepEqual(p.rowsOf(marco), []);
    assert.equal(p.named(marco, 'Enter'), undefined);
  }},
  'one-action-is-singular': {employments: [MARCO], people: [taskPerson(2, 'Marco Probe', 9, 1, 10)], run: async p => {
    assert.equal(p.row(0).children[2].textContent, '1 action pending');
    assert.deepEqual(p.rowsOf(p.row(0)).at(-1), ['Timesheet', label(10), 'Enter']);
  }},
  'household-strip': {household: HOUSEHOLD, people: [taskPerson(1, 'Lea Beispiel', 7, 0, 3)], run: async p => {
    assert.equal(p.el('household-status').textContent, '');
    const [line, bar] = p.el('household-rows').children;
    assert.equal(line.textContent, 'CHF 15,000.00 of CHF 60,480.00 used · CHF 45,480.00 remaining');
    assert.equal(bar.tag, 'progress');
    assert.equal(bar.className, 'limit-bar');
    assert.deepEqual([bar.max, bar.value], [60480, 15000]);
    assert.equal(p.el('household-note').hidden, false);
    assert.match(p.el('household-note').textContent, /simplified procedure only applies while the wages you pay in a year stay within CHF 60,480\.00/);
    assert.match(p.el('household-note').textContent, /If you pay more than this, it no longer applies/);
  }},
  'household-none': {people: [], run: async p => {
    assert.equal(p.el('household-status').textContent, 'No employees yet.');
    assert.equal(p.el('household-note').hidden, true);
    assert.equal(p.el('household-rows').children.length, 0);
  }},
  'household-unavailable': {employeesStatus: 500, run: async p => {
    assert.match(p.el('household-status').textContent, /could not be loaded/i);
    assert.equal(p.el('page-error').hidden, true);
    assert.match(p.row(0).textContent, /Lea Beispiel/);
    assert.equal(p.row(0).children[2].hidden, true);
  }},
  'no-employer': {noEmployer: true, run: async p => {
    assert.equal(p.el('add-employment').disabled, true);
    assert.match(p.el('employer-status').textContent, /enter your account details/i);
    assert.equal(p.el('employer-status').className, 'attention');
  }},
  'account-buttons': {run: async p => {
    assert.equal(p.el('add-employment').disabled, false);
    assert.equal(p.el('employer-status').textContent, '');
    await p.click(p.el('add-employment'));
    assert.equal(p.redirects.at(-1), '/employment-setup');
    await p.click(p.el('employer-details-button'));
    assert.equal(p.redirects.at(-1), '/account-details');
  }},
  'many': {employments: [LEA, LEA_AGAIN, MARCO, NORA], run: async p => {
    assert.equal(p.el('employment-list').children.length, 4);
    assert.equal(p.row(3).hidden, true);
    assert.equal(p.el('show-employments').hidden, false);
    await p.click(p.el('show-employments'));
    assert.equal(p.row(3).hidden, false);
    assert.equal(p.el('show-employments')['aria-expanded'], 'true');
  }},
  'list-401': {listStatus: 401, run: async p => {
    assert.match(p.el('page-error').textContent, /session.*expired|log in again/i);
    assert.equal(p.buttons(p.el('page-error')).length, 1);
    assert.equal(p.el('page-status').textContent, '');
  }},
  'logout': {run: async p => {
    await p.click(p.el('logout-button'));
    const logout = p.calls.filter(call => call.url === '/api/v1/auth/logout');
    assert.equal(logout.length, 1);
    assert.equal(logout[0].headers['X-CSRF-Token'], 'csrf-token');
    assert.deepEqual(p.redirects, ['/login']);
  }},
  'logout-403': {logoutRejected: true, run: async p => {
    await p.click(p.el('logout-button'));
    assert.equal(p.calls.filter(call => call.url === '/api/v1/auth/logout').length, 1);
    assert.deepEqual(p.redirects, []);
    assert.match(p.el('page-error').textContent, /request was rejected/i);
  }}
};

async function run({scenario, elements: attributes, javascript}) {
  const spec = scenarios[scenario];
  assert.ok(spec, `Unknown scenario ${scenario}`);
  const browser = makeBrowser(spec, attributes);
  vm.runInNewContext(javascript, browser.context);
  const page = makePage(browser);
  await page.settle();
  await spec.run(page);
}

run(INPUT).then(() => process.stdout.write('ok')).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
