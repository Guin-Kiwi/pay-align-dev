const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const INPUT = JSON.parse(fs.readFileSync(0, 'utf8'));
const YEAR = INPUT.year;
const pad = number => String(number).padStart(2, '0');
const day = (month, date) => `${YEAR}-${pad(month)}-${pad(date)}`;
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const label = month => `${MONTH_NAMES[month - 1]} ${YEAR}`;
const ordinal = number => `${number}${[11, 12, 13].includes(number % 100) ? 'th' : {1: 'st', 2: 'nd', 3: 'rd'}[number % 10] ?? 'th'}`;
const long = (month, date) => `${ordinal(date)} ${MONTH_NAMES[month - 1]} ${YEAR}`;
const SESSION_EXPIRED = {detail: 'Authentication required.'};
const response = (status, body) => ({status, json: async () => body});

const TOTALS = {
  saved_months: 2, gross_wage: '9000.00', net_payout: '8100.00', cash_bonus: '100.00', expense_reimbursements: '24.80',
  employer_ahv: '477.00', employer_alv: '198.00', employer_fak: '120.00', employer_bu: '30.00', admin_charge: '45.00',
  total_employer_cost: '9970.80', worked_minutes: 750, annual_holiday_taken_minutes: 120, public_holiday_taken_minutes: 60
};
const NO_TOTALS = Object.fromEntries(Object.entries(TOTALS).map(([key, value]) => [key, typeof value === 'string' ? '0.00' : 0]));
const terms = (id, start, saved, next, due, extra = {}) => ({
  id, start_date: start, end_date: null, hourly_wage: '28.50', weekly_minutes: 360, holiday_weeks: 4,
  saved_months: saved, next_month: next ? {year: YEAR, month: next} : null, months_due: due, ...extra
});
const person = (id, name, employments, extra = {}) => ({
  id, name, employments, totals: TOTALS, holiday_balance_minutes: 600,
  months_due: employments.reduce((sum, item) => sum + item.months_due, 0),
  wage_limit: {used: '9000.00', limit: '22680.00', remaining: '13680.00'}, ...extra
});
const HOUSEHOLD = {used: '15000.00', limit: '60480.00', remaining: '45480.00'};
const LEA = person(1, 'Lea Beispiel', [terms(7, day(1, 5), 2, 3, 8)]);
const MARCO = person(2, 'Marco Probe', [terms(9, day(3, 2), 7, 10, 0)], {months_due: 0});
const NORA = person(3, 'Nora Doppelt', [terms(10, day(1, 5), 2, 3, 2, {end_date: day(6, 30)}), terms(11, day(8, 1), 1, 9, 1)]);
const SAVED = {7: [1, 2], 9: [3, 4, 5, 6, 7, 8, 9], 10: [1, 2], 11: [8]};
const DETAILS = {
  1: {id: 1, name: 'Lea Beispiel', address: 'Clarastrasse 10, 4058 Basel', ahv_number: '756.9876.5432.10', nationality: 'Italy', tax_status: 'Source tax'}
};

function makeElement(tag = 'div', attrs = {}) {
  let text = '';
  return {
    tag, id: attrs.id, value: attrs.value ?? '', hidden: Object.hasOwn(attrs, 'hidden'),
    disabled: Object.hasOwn(attrs, 'disabled'), className: attrs.class ?? '', children: [], listeners: {}, dataset: {},
    get textContent() { return text + this.children.map(child => child.textContent ?? '').join(''); },
    set textContent(value) { text = String(value); this.children = []; },
    addEventListener(event, callback) { this.listeners[event] = callback; },
    setAttribute(name, value) { this[name] = value; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    showModal() { this.opened = true; },
    close() { this.opened = false; },
    focus() { this.focused = true; },
    set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  };
}

function makeBrowser(spec, attributes) {
  const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, makeElement('existing', {id, ...attrs})]));
  const calls = [];
  const redirects = [];
  const context = {
    document: {
      getElementById(id) { assert.ok(elements[id], `The page has no element #${id}`); return elements[id]; },
      createElement(tag) { return makeElement(tag); }
    },
    window: {location: {replace(url) { redirects.push(url); }, assign(url) { redirects.push(url); }}},
    AbortController, setTimeout, clearTimeout,
    async fetch(url, options = {}) {
      calls.push({url, method: options.method ?? 'GET'});
      if (url === '/api/v1/employees') {
        return spec.listStatus
          ? response(spec.listStatus, SESSION_EXPIRED)
          : response(200, {employees: spec.employees ?? [LEA], household: spec.household === undefined ? HOUSEHOLD : spec.household});
      }
      const months = /^\/api\/v1\/employments\/(\d+)\/months$/.exec(url);
      if (months) {
        const id = Number(months[1]);
        if (spec.failingMonths === id) return response(500, {detail: 'boom'});
        const saved = (spec.saved ?? SAVED)[id] ?? [];
        return response(200, {months: saved.map(month => ({monthly_record_id: month, year: YEAR, month})), next_month: null});
      }
      const details = /^\/api\/v1\/employees\/(\d+)$/.exec(url);
      if (details) {
        return spec.detailsStatus ? response(spec.detailsStatus, {detail: 'Employee not found.'}) : response(200, DETAILS[Number(details[1])]);
      }
      throw new Error(`Unexpected request ${url}`);
    }
  };
  return {elements, calls, redirects, context};
}

function makePage({elements, calls, redirects}) {
  const settle = async () => { for (let index = 0; index < 100; index++) await Promise.resolve(); };
  const descendants = node => node.children.flatMap(child => [child, ...descendants(child)]);
  const click = async target => { const result = target.listeners.click?.({preventDefault() {}}); await result; await settle(); };
  const el = id => elements[id];
  const cards = () => el('employee-list').children;
  const box = (card, kind) => descendants(card).find(node => node.className === `person-box ${kind}`);
  const rowsOf = node => descendants(node).filter(child => child.tag === 'table')
    .flatMap(table => table.children[0].children.map(row => row.children.map(cell => cell.textContent)));
  const buttons = node => descendants(node).filter(child => child.tag === 'button');
  const named = (node, name) => buttons(node).find(button => button.textContent === name);
  const select = card => descendants(card).find(node => node.tag === 'select');
  return {el, calls, redirects, settle, click, cards, box, rowsOf, buttons, named, select, descendants};
}

const scenarios = {
  'person-boxes': {employees: [LEA, MARCO], run: async p => {
    assert.equal(p.cards().length, 2);
    for (const [card, name, started] of [[p.cards()[0], 'Lea Beispiel', long(1, 5)], [p.cards()[1], 'Marco Probe', long(3, 2)]]) {
      assert.equal(card.className, 'person-card');
      assert.equal(card.children[0].tag, 'h3');
      assert.equal(card.children[0].textContent, name);
      assert.equal(card.children[1].textContent, `Employed since ${started}`);
      const grid = card.children[2];
      assert.equal(grid.className, 'person-grid');
      const [left, right] = grid.children;
      assert.equal(left.className, 'person-left');
      assert.deepEqual(left.children.map(child => child.className), ['person-box agreement', 'person-box todo']);
      assert.equal(right.className, 'person-box numbers');
    }
    assert.equal(p.el('page-status').textContent, '');
    assert.equal(p.el('no-employees').hidden, true);
  }},
  'agreement': {employees: [NORA], run: async p => {
    const card = p.cards()[0];
    assert.equal(card.children[1].textContent, `Employed since ${long(1, 5)} · 2 employments`);
    const agreement = p.box(card, 'agreement');
    assert.equal(agreement.children[0].textContent, 'Agreement');
    assert.match(agreement.textContent, new RegExp(`Employment started on ${long(1, 5)} · ends on ${long(6, 30)}`));
    assert.match(agreement.textContent, new RegExp(`Employment started on ${long(8, 1)}`));
    const rows = p.rowsOf(agreement).filter(row => ['Hourly wage', 'Weekly hours', 'Holiday weeks'].includes(row[0]));
    assert.deepEqual(rows, [
      ['Hourly wage', 'CHF 28.50', ''], ['Weekly hours', '6 h 00 min', ''], ['Holiday weeks', '4', ''],
      ['Hourly wage', 'CHF 28.50', ''], ['Weekly hours', '6 h 00 min', ''], ['Holiday weeks', '4', '']
    ]);
  }},
  'payslip-picker': {run: async p => {
    const picker = p.select(p.cards()[0]);
    assert.deepEqual(picker.children.map(option => option.textContent), [label(2), label(1)]);
    assert.equal(picker.value, `7:${YEAR}-2`);
    assert.equal(picker.disabled, false);
    picker.value = `7:${YEAR}-1`;
    await p.click(p.named(p.box(p.cards()[0], 'agreement'), 'View payslip'));
    assert.equal(p.redirects.at(-1), `/payslips?employment_id=7&year=${YEAR}&month=1`);
  }},
  'payslip-picker-names-the-employment': {employees: [NORA], run: async p => {
    const picker = p.select(p.cards()[0]);
    assert.deepEqual(picker.children.map(option => option.textContent), [
      `${label(8)} · employment from ${long(8, 1)}`,
      `${label(2)} · employment from ${long(1, 5)}`,
      `${label(1)} · employment from ${long(1, 5)}`
    ]);
    await p.click(p.named(p.box(p.cards()[0], 'agreement'), 'View payslip'));
    assert.equal(p.redirects.at(-1), `/payslips?employment_id=11&year=${YEAR}&month=8`);
  }},
  'no-saved-months': {saved: {}, run: async p => {
    const picker = p.select(p.cards()[0]);
    assert.deepEqual(picker.children.map(option => option.textContent), ['No saved months yet']);
    assert.equal(picker.disabled, true);
    assert.equal(p.named(p.box(p.cards()[0], 'agreement'), 'View payslip').disabled, true);
  }},
  'months-unavailable': {failingMonths: 7, run: async p => {
    const picker = p.select(p.cards()[0]);
    assert.deepEqual(picker.children.map(option => option.textContent), ['The months could not be loaded']);
    assert.equal(picker.disabled, true);
    assert.match(p.cards()[0].textContent, /Lea Beispiel/);
    assert.equal(p.el('page-error').hidden, true);
  }},
  'details-on-request': {run: async p => {
    const card = p.cards()[0];
    assert.doesNotMatch(card.textContent, /Clarastrasse|756\.9876/);
    assert.deepEqual(p.calls.map(call => call.url).filter(url => url.startsWith('/api/v1/employees/')), []);
    await p.click(p.named(p.box(card, 'agreement'), 'Employee details'));
    assert.deepEqual(p.calls.map(call => call.url).filter(url => url.startsWith('/api/v1/employees/')), ['/api/v1/employees/1']);
    assert.equal(p.el('details-dialog').opened, true);
    assert.equal(p.el('details-title').textContent, 'Lea Beispiel');
    assert.deepEqual(p.rowsOf(p.el('details-rows')), [
      ['Address', 'Clarastrasse 10, 4058 Basel', ''], ['AHV number', '756.9876.5432.10', ''],
      ['Nationality', 'Italy', ''], ['Tax status', 'Source tax', '']
    ]);
    assert.equal(p.el('details-status').textContent, '');
    await p.click(p.el('details-close'));
    assert.equal(p.el('details-dialog').opened, false);
  }},
  'details-failure': {detailsStatus: 404, run: async p => {
    await p.click(p.named(p.box(p.cards()[0], 'agreement'), 'Employee details'));
    assert.equal(p.el('details-dialog').opened, true);
    assert.match(p.el('details-status').textContent, /could not be loaded/i);
    assert.deepEqual(p.rowsOf(p.el('details-rows')), []);
  }},
  'todo-months-due': {employees: [LEA, NORA], run: async p => {
    const lea = p.box(p.cards()[0], 'todo');
    assert.equal(lea.children[0].textContent, 'To do');
    assert.deepEqual(p.rowsOf(lea), [['Timesheet', `Enter ${label(3)} (8 months behind)`, 'Enter']]);
    await p.click(p.named(lea, 'Enter'));
    assert.equal(p.redirects.at(-1), '/timesheets?employment_id=7');
    const nora = p.box(p.cards()[1], 'todo');
    assert.deepEqual(p.rowsOf(nora), [
      [`Timesheet · employment from ${long(1, 5)}`, `Enter ${label(3)} (2 months behind)`, 'Enter'],
      [`Timesheet · employment from ${long(8, 1)}`, `Enter ${label(9)}`, 'Enter']
    ]);
    await p.click(p.buttons(nora)[1]);
    assert.equal(p.redirects.at(-1), '/timesheets?employment_id=11');
  }},
  'todo-nothing': {employees: [MARCO], run: async p => {
    const todo = p.box(p.cards()[0], 'todo');
    assert.match(todo.textContent, /Nothing to do/);
    assert.deepEqual(p.rowsOf(todo), []);
    assert.equal(p.buttons(todo).length, 0);
  }},
  'wage-limit-is-never-a-to-do': {employees: [person(1, 'Lea Beispiel', [terms(7, day(1, 5), 2, 3, 0)], {wage_limit: {used: '22000.00', limit: '22680.00', remaining: '680.00'}})], run: async p => {
    assert.match(p.box(p.cards()[0], 'todo').textContent, /Nothing to do/);
  }},
  'numbers': {run: async p => {
    const numbers = p.box(p.cards()[0], 'numbers');
    assert.equal(numbers.children[0].textContent, 'The year so far');
    assert.deepEqual(p.rowsOf(numbers), [
      ['Gross wage', 'CHF 9,000.00', ''], ['Net payout', 'CHF 8,100.00', ''], ['Cash bonus', 'CHF 100.00', ''],
      ['Expense reimbursements', 'CHF 24.80', ''],
      ['AHV / IV / EO', 'CHF 477.00', ''], ['ALV', 'CHF 198.00', ''], ['Family allowance (FAK)', 'CHF 120.00', ''],
      ['Occupational accident insurance (BU)', 'CHF 30.00', ''], ['Administration charge', 'CHF 45.00', ''],
      ['Total employer cost', 'CHF 9,970.80', ''],
      ['Hours worked', '12 h 30 min', ''], ['Annual holiday taken', '2 h 00 min', ''], ['Paid public holidays', '1 h 00 min', ''],
      ['Holiday balance', '10 h 00 min', ''],
      ['This employee', 'CHF 9,000.00 of CHF 22,680.00 used · CHF 13,680.00 remaining', '']
    ]);
    assert.deepEqual(p.descendants(numbers).filter(node => node.tag === 'h5').map(node => node.textContent),
      ['Pay so far', 'Employer cost', 'Hours and leave', 'Wage limit']);
  }},
  'wage-limit-bars': {run: async p => {
    const bars = p.descendants(p.box(p.cards()[0], 'numbers')).filter(node => node.tag === 'progress');
    assert.deepEqual(bars.map(bar => [bar.max, bar.value]), [[22680, 9000]]);
  }},
  'nothing-saved-yet': {employees: [person(1, 'Lea Beispiel', [terms(7, day(1, 5), 0, 1, 0)], {totals: NO_TOTALS, holiday_balance_minutes: null, wage_limit: {used: '0.00', limit: '22680.00', remaining: '22680.00'}})], household: null, saved: {}, run: async p => {
    const rows = p.rowsOf(p.box(p.cards()[0], 'numbers'));
    assert.deepEqual(rows.find(row => row[0] === 'Gross wage'), ['Gross wage', 'CHF 0.00', '']);
    assert.deepEqual(rows.find(row => row[0] === 'Holiday balance'), ['Holiday balance', 'No month saved yet', '']);
  }},
  'empty': {employees: [], household: null, run: async p => {
    assert.equal(p.el('no-employees').hidden, false);
    assert.equal(p.cards().length, 0);
    assert.equal(p.el('page-status').textContent, '');
  }},
  'list-401': {listStatus: 401, run: async p => {
    assert.match(p.el('page-error').textContent, /session.*expired|log in again/i);
    assert.equal(p.buttons(p.el('page-error')).length, 1);
    await p.click(p.buttons(p.el('page-error'))[0]);
    assert.equal(p.redirects.at(-1), '/login');
  }},
  'list-500': {listStatus: 500, run: async p => {
    assert.match(p.el('page-error').textContent, /could not load/i);
    assert.equal(p.el('page-error').hidden, false);
    assert.equal(p.el('page-status').textContent, '');
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
