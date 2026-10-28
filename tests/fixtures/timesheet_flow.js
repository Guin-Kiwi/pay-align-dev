const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const INPUT = JSON.parse(fs.readFileSync(0, 'utf8'));
const YEAR = INPUT.year;
const HOLIDAYS = INPUT.holidays;
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const pad = number => String(number).padStart(2, '0');
const day = (month, date) => `${YEAR}-${pad(month)}-${pad(date)}`;
const range = (first, last) => Array.from({length: Math.max(0, last - first + 1)}, (_, index) => first + index);
const daysIn = month => new Date(Date.UTC(YEAR, month, 0)).getUTCDate();
const weekdayOf = date => new Date(`${date}T00:00:00Z`).getUTCDay();
const monthOf = date => Number(date.slice(5, 7));
const label = month => `${MONTH_NAMES[month - 1]} ${YEAR}`;
const ordinal = number => `${number}${[11, 12, 13].includes(number % 100) ? 'th' : {1: 'st', 2: 'nd', 3: 'rd'}[number % 10] ?? 'th'}`;
const long = (month, date) => `${ordinal(date)} ${MONTH_NAMES[month - 1]} ${YEAR}`;
const occurrences = (month, weekday) => range(1, daysIn(month)).filter(date => weekdayOf(day(month, date)) === weekday).length;

// The holiday and plain months come from the constants the test was given, never from literals.
const HOLIDAY_MONTHS = [...new Set(HOLIDAYS.map(monthOf))];
const HOLIDAY_MONTH = HOLIDAY_MONTHS.find(month => month > 1);
const PLAIN_MONTH = range(2, 12).find(month => !HOLIDAY_MONTHS.includes(month));
const MONTH_HOLIDAYS = HOLIDAYS.filter(date => monthOf(date) === HOLIDAY_MONTH);
assert.ok(HOLIDAY_MONTH && PLAIN_MONTH && MONTH_HOLIDAYS.length >= 2, 'the constants need a plain month and a month with two holidays');
const FIRST_HOLIDAY = MONTH_HOLIDAYS[0];
const SECOND_HOLIDAY = MONTH_HOLIDAYS[1];
const NORMAL_DAYS = range(1, 28).map(date => day(HOLIDAY_MONTH, date)).filter(date => !HOLIDAYS.includes(date));

const SESSION_EXPIRED = {detail: 'Authentication required.'};
const SAVED_500 = 'The payroll was saved, but its confirmation could not be loaded. Check the saved month before retrying.';
const employment = (id, name, start, end = null) => ({id, employee_name: name, start_date: start, end_date: end});
const LEA = employment(7, 'Lea Beispiel', day(1, 5));
const MARCO = employment(8, 'Marco Probe', day(3, 2));
const NORA = employment(9, 'Nora Fertig', day(1, 5), day(2, 28));

const payslipPage = (month, id = 7) => `/payslips?employment_id=${id}&year=${YEAR}&month=${month}`;
const monthsRead = id => `GET /api/v1/employments/${id}/months`;
const balanceRead = (id, month) => `GET /api/v1/employments/${id}/months/${YEAR}/${month}`;
const HOLIDAY_READ = `GET /api/v1/public-holidays?year=${YEAR}`;
const LOAD = ['GET /api/v1/auth/csrf', 'GET /api/v1/employments'];
const SAVE = 'POST /api/v1/monthly-payroll';
const response = (status, body) => ({status, json: async () => body});

const DATE = 0, TYPE = 1, START = 2, END = 3, BREAK = 4, PAID = 5, HOLIDAY = 6, ACTIONS = 7;

function historyFor(id, spec) {
  if (spec.histories?.[id]) return spec.histories[id];
  const month = spec.month ?? PLAIN_MONTH;
  return {7: {saved: range(1, month - 1), next: month}, 8: {saved: [], next: 3}, 9: {saved: [1, 2], next: null}}[id];
}

function makeElement(tag = 'div', attrs = {}) {
  let text = '';
  return {
    tag, id: attrs.id, value: attrs.value ?? '', hidden: Object.hasOwn(attrs, 'hidden'),
    disabled: Object.hasOwn(attrs, 'disabled'), checked: false, open: false, min: '', max: '', className: attrs.class ?? '',
    children: [], listeners: {}, dataset: {},
    get textContent() { return text + this.children.map(child => child.textContent ?? '').join(''); },
    set textContent(value) { text = String(value); this.children = []; },
    addEventListener(event, callback) { this.listeners[event] = callback; },
    setAttribute(name, value) { this[name] = value; },
    setCustomValidity(message) { this.validationMessage = message; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    focus() { this.focused = true; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  };
}

function makeBrowser(spec, attributes) {
  const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, makeElement('existing', {id, ...attrs})]));
  const calls = [];
  const redirects = [];
  const confirms = [];
  const control = {};
  const context = {
    document: {
      getElementById(id) { assert.ok(elements[id], `The page has no element #${id}`); return elements[id]; },
      createElement(tag) { return makeElement(tag); }
    },
    window: {
      location: {search: spec.search ?? '', replace(url) { redirects.push(url); }, assign(url) { redirects.push(url); }},
      confirm(message) { confirms.push(message); return spec.confirm ?? true; },
      sessionStorage: {setItem() {}}
    },
    AbortController, URLSearchParams, setTimeout, clearTimeout,
    async fetch(url, options = {}) {
      calls.push({url, method: options.method ?? 'GET', headers: options.headers ?? {}, body: options.body});
      if (url === '/api/v1/auth/csrf') return response(200, {csrf_token: 'csrf-token'});
      if (url === '/api/v1/employments') return spec.listStatus ? response(spec.listStatus, SESSION_EXPIRED) : response(200, spec.employments ?? [LEA]);
      const history = /^\/api\/v1\/employments\/(\d+)\/months$/.exec(url);
      if (history) {
        const id = Number(history[1]);
        if (spec.monthsStatus) return response(spec.monthsStatus, SESSION_EXPIRED);
        if (spec.failingHistory === id) return response(500, {detail: 'boom'});
        const {saved, next} = historyFor(id, spec);
        return response(200, {months: saved.map(month => ({monthly_record_id: month, year: YEAR, month})), next_month: next ? {year: YEAR, month: next} : null});
      }
      if (/^\/api\/v1\/employments\/\d+\/months\/\d+\/\d+$/.test(url)) {
        return spec.balanceFails ? response(500, {detail: 'boom'}) : response(200, {holiday_balance_minutes: 605});
      }
      if (url === `/api/v1/public-holidays?year=${YEAR}`) {
        return spec.holidaysStatus ? response(spec.holidaysStatus, SESSION_EXPIRED) : response(200, HOLIDAYS);
      }
      if (url === '/api/v1/monthly-payroll') {
        assert.equal(options.method, 'POST');
        if (spec.hold) await new Promise(resolve => { control.release = resolve; });
        if (spec.postFails) throw new Error('offline');
        if (spec.postStatus) return response(spec.postStatus, spec.postStatus === 500 ? {detail: SAVED_500} : {detail: 'Invalid CSRF token.'});
        return response(201, {monthly_record_id: 11, message: 'Payroll processed successfully.'});
      }
      throw new Error(`Unexpected request ${url}`);
    }
  };
  return {elements, calls, redirects, confirms, control, context};
}

function makePage({elements, calls, redirects, confirms, control, context}) {
  const settle = async () => { for (let index = 0; index < 100; index++) await Promise.resolve(); };
  const buttons = node => node.children.flatMap(child => [...(child.tag === 'button' ? [child] : []), ...buttons(child)]);
  const click = async target => { const result = target.listeners.click?.({preventDefault() {}}); await result; await settle(); };
  const el = id => elements[id];
  const rows = () => el('entry-list').children;
  const field = (row, index) => row.children[index].children[0];
  const page = {
    el, calls, redirects, confirms, control, settle, buttons, click, rows, field,
    urls: () => calls.map(call => `${call.method} ${call.url}`),
    posts: () => calls.filter(call => call.url === '/api/v1/monthly-payroll'),
    dialog: () => el('timesheet-dialog'),
    named: (node, name) => buttons(node).find(button => button.textContent === name),
    rowsOf: card => {
      const table = card.children.find(child => child.tag === 'table');
      return table ? table.children[0].children.map(row => row.children.map(cell => cell.textContent)) : [];
    },
    escape: () => ({prevented: false, preventDefault() { this.prevented = true; }}),
    submit: () => el('payroll-form').listeners.submit({preventDefault() {}}),
    type: async (id, value) => { el(id).value = value; el(id).listeners.input?.(); await settle(); },
    pattern: (weekday, start = '08:00', end = '14:30', pause = '30') => {
      el(`weekday-${weekday}`).checked = true;
      el('pattern-start').value = start;
      el('pattern-end').value = end;
      el('pattern-break').value = pause;
      for (const id of ['pattern-start', 'pattern-end', 'pattern-break']) el(id).listeners.input?.();
    },
    fill: () => click(el('fill-month')),
    addDay: async date => { el('extra-date').value = date; await click(el('add-day')); },
    addHoliday: async (date, hours) => { el('holiday-date').value = date; if (hours !== undefined) el('holiday-hours').value = hours; await click(el('add-holiday')); },
    setCell: (row, index, value) => { const input = field(row, index); input.value = value; input.listeners.input?.(); },
    pickType: async (row, value) => { const select = field(row, TYPE); select.value = value; await select.listeners.change?.(); await settle(); },
    choose: async (row, which) => {
      const box = row.children[HOLIDAY].children[which === 'worked' ? 0 : 1].children[0];
      box.checked = true;
      await box.listeners.change?.();
      await settle();
    },
    workedRow: async (date, start = '08:00', end = '14:30', pause = '30') => {
      await page.addDay(date);
      const row = rows().find(item => item.children[DATE].textContent === date && field(item, START)?.value === '');
      page.setCell(row, START, start);
      page.setCell(row, END, end);
      page.setCell(row, BREAK, pause);
      return row;
    },
    bonuses: async () => { await page.type('cash-bonus', '50.00'); await page.type('expense-reimbursements', '12.40'); await click(el('add-bonus')); },
    leaveWarning: () => context.window.leaveWarning?.() ?? '',
    review: async () => {
      await page.submit();
      assert.equal(page.dialog().open, true);
      assert.equal(page.posts().length, 0);
    },
    confirmSave: () => el('timesheet-confirm').listeners.click(),
    payload: () => JSON.parse(page.posts()[0].body)
  };
  return page;
}

async function saveAndCheck(p, categories) {
  await p.review();
  assert.equal(p.el('timesheet-confirm').textContent, `Yes, confirm and save ${label(p.month ?? PLAIN_MONTH)}`);
  const pending = p.confirmSave();
  await p.settle();
  if (p.holdCheck) {
    assert.equal(p.el('save-payroll').disabled, true);
    assert.equal(p.el('timesheet-confirm').disabled, true);
    assert.equal(p.el('timesheet-cancel').disabled, true);
    const saving = p.escape();
    p.dialog().listeners.cancel(saving);
    assert.equal(saving.prevented, true);
    await p.submit();
    await p.confirmSave();
    assert.equal(p.posts().length, 1);
    p.control.release();
  }
  await pending;
  await p.settle();
  assert.equal(p.posts().length, 1);
  assert.equal(p.posts()[0].headers['X-CSRF-Token'], 'csrf-token');
  assert.equal(p.dialog().open, false);
  assert.deepEqual(p.payload().work_entries.map(entry => entry.category), categories);
  assert.equal(p.payload().employment_id, 7);
}

async function saved(p, categories = ['worked'], prepare = async () => { await p.workedRow(day(PLAIN_MONTH, 3)); }) {
  await prepare();
  await saveAndCheck(p, categories);
  assert.match(p.el('save-message').textContent, /Payroll processed successfully/);
  assert.equal(p.el('save-confirmation').hidden, false);
  assert.equal(p.el('entry-section').hidden, true);
  await p.click(p.el('view-saved-payslip'));
  assert.equal(p.redirects.at(-1), payslipPage(PLAIN_MONTH));
  await p.click(p.el('back-to-timesheets'));
  assert.equal(p.redirects.at(-1), '/timesheets');
}

async function rejected(p) {
  await p.workedRow(day(PLAIN_MONTH, 3));
  await saveAndCheck(p, ['worked']);
  assert.match(p.el('save-error').textContent, /request was rejected/i);
  assert.match(p.el('save-error').textContent, /log in again/i);
  assert.doesNotMatch(p.el('save-error').textContent, /may have been saved/i);
  assert.equal(p.el('page-error').hidden, true);
  assert.equal(p.el('save-payroll').disabled, false);
}

const OPEN = (id = 7, month = PLAIN_MONTH) => [...LOAD, monthsRead(id), ...(id === 7 && month > 1 ? [balanceRead(7, month - 1)] : []), HOLIDAY_READ];
const ENTRY = {search: '?employment_id=7'};
const HOLIDAY_ENTRY = {...ENTRY, month: HOLIDAY_MONTH};

const scenarios = {
  // ---- landing: one bound box per employee, last saved and next to enter only
  'landing-boxes': {employments: [LEA, MARCO, NORA], run: async p => {
    assert.deepEqual(p.urls(), [...LOAD, monthsRead(7), monthsRead(8), monthsRead(9)]);
    assert.equal(p.el('landing-section').hidden, false);
    assert.equal(p.el('entry-section').hidden, true);
    const boxes = p.el('timesheet-list').children;
    assert.equal(boxes.length, 3);
    assert.deepEqual(boxes.map(box => box.className), Array(3).fill('employee-card'));
    const [lea, marco, nora] = boxes;
    for (const box of boxes) assert.equal(box.children[0].tag, 'h3');
    assert.deepEqual(boxes.map(box => box.children[0].textContent), ['Lea Beispiel', 'Marco Probe', 'Nora Fertig']);
    assert.equal(lea.children[1].className, 'subheading');
    assert.equal(lea.children[1].textContent, `Employment started on ${long(1, 5)}`);
    assert.equal(nora.children[1].textContent, `Employment started on ${long(1, 5)} · ends on ${long(2, 28)}`);
    const names = months => `${months.map(month => label(month).replace(` ${YEAR}`, '')).join(', ')} ${YEAR}`;
    assert.deepEqual(p.rowsOf(lea), [['Saved', names(range(1, PLAIN_MONTH - 1)), 'View payslip'], ['Next month', label(PLAIN_MONTH), 'Enter']]);
    assert.deepEqual(p.rowsOf(marco), [['Saved', 'No saved months yet', ''], ['Next month', label(3), 'Enter']]);
    assert.deepEqual(p.rowsOf(nora), [['Saved', names([1, 2]), 'View payslip'], ['Next month', 'All months entered', '']]);
    await p.click(p.named(lea, 'View payslip'));
    assert.equal(p.redirects.at(-1), payslipPage(PLAIN_MONTH - 1, 7));
    await p.click(p.named(lea, 'Enter'));
    assert.equal(p.redirects.at(-1), '/timesheets?employment_id=7');
    assert.equal(p.named(marco, 'View payslip'), undefined);
    await p.click(p.named(marco, 'Enter'));
    assert.equal(p.redirects.at(-1), '/timesheets?employment_id=8');
    assert.equal(p.named(nora, 'Enter'), undefined);
    for (const box of boxes) assert.doesNotMatch(box.textContent, /then |from /);
  }},
  'landing-empty': {employments: [], run: async p => {
    assert.equal(p.el('no-employments').hidden, false);
    assert.equal(p.el('timesheet-list').children.length, 0);
  }},
  'landing-401': {listStatus: 401, run: async p => {
    assert.match(p.el('page-error').textContent, /session.*expired|log in again/i);
    assert.equal(p.buttons(p.el('page-error')).length, 1);
    assert.equal(p.el('page-status').textContent, '');
  }},
  'landing-month-failure': {employments: [LEA, MARCO], failingHistory: 8, run: async p => {
    assert.match(p.el('timesheet-list').children[1].textContent, /Months unavailable/);
    assert.equal(p.named(p.el('timesheet-list').children[1], 'Enter'), undefined);
    assert.ok(p.named(p.el('timesheet-list').children[0], 'Enter'));
    assert.equal(p.el('page-error').hidden, true);
  }},

  // ---- entry page: opening it
  'entry-opens': {...ENTRY, run: async p => {
    assert.deepEqual(p.urls(), OPEN());
    assert.equal(p.el('landing-section').hidden, true);
    assert.equal(p.el('entry-section').hidden, false);
    assert.match(p.el('entry-month').textContent, new RegExp(`Lea Beispiel · ${label(PLAIN_MONTH)}`));
    assert.equal(p.el('holiday-balance').textContent, 'Remaining balance: 10 h 05 min');
    assert.equal(p.el('entry-table').hidden, false);
    assert.equal(p.el('entry-empty').hidden, false);
    assert.equal(p.el('save-payroll').disabled, false);
    assert.equal(p.el('extra-date').min, day(PLAIN_MONTH, 1));
    assert.equal(p.el('extra-date').max, day(PLAIN_MONTH, daysIn(PLAIN_MONTH)));
    assert.equal(p.el('holiday-date').min, day(PLAIN_MONTH, 1));
  }},
  'entry-first-month': {employments: [MARCO], search: '?employment_id=8', run: async p => {
    assert.deepEqual(p.urls(), [...LOAD, monthsRead(8), HOLIDAY_READ]);
    assert.equal(p.el('holiday-balance').textContent, 'Remaining balance: —');
    assert.match(p.el('entry-month').textContent, new RegExp(label(3)));
  }},
  'entry-balance-unavailable': {...ENTRY, balanceFails: true, run: async p => {
    assert.equal(p.el('holiday-balance').textContent, 'Remaining balance: —');
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.el('entry-section').hidden, false);
  }},
  'entry-unknown-employment': {employments: [LEA, MARCO], search: '?employment_id=99', run: async p => {
    assert.match(p.el('page-error').textContent, /could not be found/i);
    assert.equal(p.el('entry-section').hidden, true);
    assert.equal(p.el('landing-section').hidden, false);
  }},
  'entry-none-left': {employments: [NORA], search: '?employment_id=9', run: async p => {
    assert.equal(p.el('entry-section').hidden, true);
    assert.equal(p.el('landing-section').hidden, false);
    assert.equal(p.el('no-month').hidden, false);
    assert.match(p.el('no-month').textContent, /Nora Fertig/);
  }},
  'entry-months-401': {...ENTRY, monthsStatus: 401, run: async p => {
    assert.match(p.el('page-error').textContent, /session.*expired|log in again/i);
    assert.equal(p.el('entry-section').hidden, true);
    assert.equal(p.el('page-status').textContent, '');
  }},
  'entry-holidays-401': {...ENTRY, holidaysStatus: 401, run: async p => {
    assert.deepEqual(p.urls(), OPEN());
    assert.match(p.el('page-error').textContent, /session.*expired|log in again/i);
    assert.equal(p.el('page-status').textContent, '');
    assert.equal(p.el('entry-section').hidden, true);
    assert.equal(p.posts().length, 0);
    const login = p.named(p.el('page-error'), 'Open the login page');
    assert.ok(login);
    await p.click(login);
    assert.equal(p.redirects.at(-1), '/login');
  }},
  'cancel-entry': {...ENTRY, run: async p => {
    await p.click(p.el('cancel-entry'));
    assert.equal(p.confirms.length, 0);
    assert.equal(p.redirects.at(-1), '/timesheets');
  }},
  'cancel-entry-with-rows': {...ENTRY, confirm: false, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.click(p.el('cancel-entry'));
    assert.equal(p.confirms.length, 1);
    assert.match(p.confirms[0], /discard/i);
    assert.deepEqual(p.redirects, []);
    assert.equal(p.rows().length, 1);
  }},
  'cancel-entry-discards': {...ENTRY, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.click(p.el('cancel-entry'));
    assert.equal(p.confirms.length, 1);
    assert.equal(p.redirects.at(-1), '/timesheets');
  }},

  // ---- left: regular work schedule
  'fill-pattern': {...ENTRY, run: async p => {
    const weekday = weekdayOf(day(PLAIN_MONTH, 3));
    const count = occurrences(PLAIN_MONTH, weekday);
    p.pattern(weekday);
    await p.fill();
    assert.equal(p.rows().length, count);
    assert.equal(p.el('entry-empty').hidden, true);
    assert.match(p.el('entry-totals').textContent, new RegExp(`Worked: ${count * 360} min`));
    assert.match(p.el('pattern-message').textContent, new RegExp(`${count} entries added`));
    p.setCell(p.rows()[0], START, '09:00');
    await p.addHoliday(day(PLAIN_MONTH, 4), '6:00');
    await p.fill();
    assert.equal(p.rows().length, count + 1);
    assert.equal(p.rows().find(row => row.children[DATE].textContent === day(PLAIN_MONTH, 4)).children[PAID].children[0].value, '360');
    assert.match(p.el('pattern-message').textContent, new RegExp(`${count} date\\(s\\) already had entries and were left unchanged`));
    assert.equal(p.el('page-error').hidden, true);
    const first = p.rows()[0];
    assert.equal(first.tag, 'tr');
    assert.deepEqual(first.children.map(cell => cell.tag), Array(8).fill('td'));
    assert.equal(first.children[DATE].textContent, day(PLAIN_MONTH, 3));
    assert.equal(p.field(first, TYPE).value, 'worked');
    assert.equal(p.field(first, START).value, '09:00');
    assert.equal(p.field(first, END).value, '14:30');
    assert.equal(p.field(first, BREAK).value, '30');
    assert.equal(first.children[PAID].textContent, '300');
    assert.match(p.field(first, START)['aria-label'], new RegExp(`Start time.*${day(PLAIN_MONTH, 3)}`));
    assert.equal(first.className, '');
  }},
  'fill-pattern-problem': {...ENTRY, run: async p => {
    await p.fill();
    assert.match(p.el('pattern-message').textContent, /Choose weekdays/);
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.rows().length, 0);
  }},
  'fill-stays-inside-the-employment': {employments: [{...LEA, start_date: day(PLAIN_MONTH, 10), end_date: day(PLAIN_MONTH, 20)}], ...ENTRY, run: async p => {
    p.pattern(weekdayOf(day(PLAIN_MONTH, 10)), '08:00', '12:00', '0');
    await p.fill();
    assert.deepEqual(p.rows().map(row => row.children[DATE].textContent), [day(PLAIN_MONTH, 10), day(PLAIN_MONTH, 17)]);
  }},
  'edit-in-the-table': {...ENTRY, run: async p => {
    const weekday = weekdayOf(day(PLAIN_MONTH, 3));
    const count = occurrences(PLAIN_MONTH, weekday);
    p.pattern(weekday);
    await p.fill();
    const first = p.rows()[0];
    p.setCell(first, END, '15:30');
    assert.equal(first.children[PAID].textContent, '420');
    assert.match(p.el('entry-totals').textContent, new RegExp(`Worked: ${420 + (count - 1) * 360} min`));
    await p.click(p.buttons(first).at(-1));
    assert.equal(p.rows().length, count - 1);
    while (p.rows().length) await p.click(p.buttons(p.rows()[0]).at(-1));
    assert.equal(p.rows().length, 0);
    assert.equal(p.el('entry-empty').hidden, false);
    assert.equal(p.el('entry-table').hidden, false);
  }},

  // ---- left: add extra day (a date, nothing else)
  'add-extra-day': {...ENTRY, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 20));
    await p.addDay(day(PLAIN_MONTH, 4));
    assert.equal(p.rows().length, 2);
    const [first, second] = p.rows();
    assert.equal(first.children[DATE].textContent, day(PLAIN_MONTH, 4));
    assert.equal(second.children[DATE].textContent, day(PLAIN_MONTH, 20));
    assert.equal(p.field(first, TYPE).value, 'worked');
    assert.equal(p.field(first, START).value, '');
    assert.equal(p.field(first, END).value, '');
    assert.equal(first.children[PAID].textContent, '—');
    assert.equal(p.el('extra-date').value, '');
    assert.equal(p.el('extra-error').hidden, true);
    p.setCell(first, START, '08:00');
    p.setCell(first, END, '12:00');
    p.setCell(first, BREAK, '0');
    assert.equal(first.children[PAID].textContent, '240');
    assert.match(p.el('entry-totals').textContent, /Worked: 240 min/);
  }},
  'extra-day-problems': {employments: [{...LEA, end_date: day(PLAIN_MONTH, 10)}], ...ENTRY, run: async p => {
    await p.addDay('');
    assert.match(p.el('extra-error').textContent, /Enter a date in the selected month/);
    assert.equal(p.el('extra-error').hidden, false);
    await p.addDay(day(PLAIN_MONTH + 1, 3));
    assert.match(p.el('extra-error').textContent, /selected month/);
    await p.addDay(day(PLAIN_MONTH, 20));
    assert.match(p.el('extra-error').textContent, /outside the employment/);
    assert.equal(p.rows().length, 0);
    await p.addDay(day(PLAIN_MONTH, 5));
    assert.equal(p.el('extra-error').hidden, true);
    assert.equal(p.rows().length, 1);
    assert.equal(p.el('holiday-error').hidden, true);
    assert.equal(p.el('page-error').hidden, true);
  }},
  'second-visit-on-one-day': {...ENTRY, run: async p => {
    await p.workedRow(day(PLAIN_MONTH, 3), '08:00', '10:00', '0');
    await p.addDay(day(PLAIN_MONTH, 3));
    assert.equal(p.rows().length, 2);
    assert.equal(p.el('extra-error').hidden, true);
  }},

  // ---- left: annual holidays
  'annual-holiday': {...ENTRY, run: async p => {
    p.pattern(weekdayOf(day(PLAIN_MONTH, 3)));
    assert.equal(p.el('holiday-hours').value, '6:00');
    await p.addHoliday(day(PLAIN_MONTH, 4), '6:30');
    assert.equal(p.rows().length, 1);
    const row = p.rows()[0];
    assert.equal(row.children[DATE].textContent, day(PLAIN_MONTH, 4));
    assert.equal(p.field(row, TYPE).value, 'annual');
    assert.equal(p.field(row, PAID).value, '390');
    assert.deepEqual([START, END, BREAK].map(index => row.children[index].textContent), ['—', '—', '—']);
    assert.equal(p.el('holiday-date').value, '');
    assert.equal(p.el('holiday-error').hidden, true);
    assert.equal(p.el('extra-error').hidden, true);
    assert.match(p.el('entry-totals').textContent, /Annual holiday: 390 min/);
    assert.equal(p.el('holiday-balance').textContent, 'Remaining balance: 10 h 05 min');
  }},
  'annual-holiday-problems': {...ENTRY, run: async p => {
    await p.addHoliday('', '6:00');
    assert.match(p.el('holiday-error').textContent, /Enter a date in the selected month/);
    await p.addHoliday(day(PLAIN_MONTH, 4), '25:99');
    assert.match(p.el('holiday-error').textContent, /H:MM/);
    await p.addHoliday(day(PLAIN_MONTH, 4), '');
    assert.match(p.el('holiday-error').textContent, /H:MM/);
    assert.equal(p.rows().length, 0);
    assert.equal(p.el('extra-error').hidden, true);
  }},
  'annual-and-work-never-share-a-day': {...ENTRY, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.addHoliday(day(PLAIN_MONTH, 3), '6:00');
    assert.match(p.el('holiday-error').textContent, /Remove the work entry for this date/);
    await p.addHoliday(day(PLAIN_MONTH, 4), '6:00');
    await p.addDay(day(PLAIN_MONTH, 4));
    assert.match(p.el('extra-error').textContent, /Remove the annual holiday row for this date/);
    assert.equal(p.rows().length, 2);
  }},
  'annual-holiday-once-per-day': {...ENTRY, run: async p => {
    await p.addHoliday(day(PLAIN_MONTH, 4), '6:00');
    await p.addHoliday(day(PLAIN_MONTH, 4), '6:00');
    assert.match(p.el('holiday-error').textContent, /already has an annual holiday row/);
    assert.equal(p.rows().length, 1);
  }},
  'switch-type-in-the-table': {...ENTRY, run: async p => {
    p.pattern(weekdayOf(day(PLAIN_MONTH, 3)));
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.pickType(p.rows()[0], 'annual');
    const annual = p.rows()[0];
    assert.equal(p.field(annual, TYPE).value, 'annual');
    assert.equal(p.field(annual, PAID).value, '360');
    assert.equal(annual.children[START].textContent, '—');
    await p.pickType(annual, 'worked');
    const worked = p.rows()[0];
    assert.equal(p.field(worked, TYPE).value, 'worked');
    assert.equal(p.field(worked, START).value, '08:00');
    assert.equal(p.field(worked, END).value, '14:30');
  }},
  'switch-type-needs-the-day-to-itself': {...ENTRY, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.pickType(p.rows()[0], 'annual');
    assert.match(p.el('table-message').textContent, /another entry/i);
    assert.equal(p.el('table-message').hidden, false);
    assert.equal(p.field(p.rows()[0], TYPE).value, 'worked');
  }},

  // ---- public holidays come from the constants and are decided by the user in the table
  'month-without-holidays': {...ENTRY, run: async p => {
    for (let weekday = 1; weekday <= 5; weekday++) p.pattern(weekday);
    await p.fill();
    assert.ok(p.rows().length >= 20);
    for (const row of p.rows()) {
      assert.doesNotMatch(row.className, /holiday|undecided/);
      assert.equal(row.children[HOLIDAY].children.length, 0);
    }
  }},
  'holiday-row-asks-worked-or-taken': {...HOLIDAY_ENTRY, run: async p => {
    p.pattern(weekdayOf(FIRST_HOLIDAY));
    await p.fill();
    const holiday = p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY));
    const plain = p.rows().find(row => !HOLIDAYS.some(date => row.children[DATE].textContent.startsWith(date)));
    assert.match(holiday.className, /holiday/);
    assert.match(holiday.className, /undecided/);
    assert.equal(holiday.children[DATE].textContent, FIRST_HOLIDAY);
    assert.match(holiday.children[TYPE].textContent, /Public holiday/);
    assert.match(holiday.children[HOLIDAY].textContent, /Worked or taken\?/);
    assert.equal(holiday.children[HOLIDAY].children[0].children[0].checked, false);
    assert.equal(holiday.children[HOLIDAY].children[1].children[0].checked, false);
    assert.equal(plain.className, '');
    assert.equal(plain.children[HOLIDAY].children.length, 0);
    assert.match(p.el('entry-totals').textContent, /1 public holiday to decide/);
    await p.submit();
    assert.match(p.el('save-error').textContent, /Choose worked or taken for the public holiday/);
    assert.equal(p.dialog().open, false);
    assert.equal(p.posts().length, 0);
  }},
  'holiday-worked': {...HOLIDAY_ENTRY, run: async p => {
    p.pattern(weekdayOf(FIRST_HOLIDAY));
    await p.fill();
    await p.choose(p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY)), 'worked');
    const holiday = p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY));
    assert.doesNotMatch(holiday.className, /undecided/);
    assert.match(holiday.className, /holiday/);
    assert.equal(holiday.children[HOLIDAY].children[0].children[0].checked, true);
    assert.equal(holiday.children[HOLIDAY].children[1].children[0].checked, false);
    assert.equal(p.field(holiday, START).value, '08:00');
    assert.match(p.el('entry-totals').textContent, /Public holiday work: 360 min/);
    await p.review();
    await p.confirmSave();
    await p.settle();
    const entry = p.payload().work_entries.find(item => item.work_date === FIRST_HOLIDAY);
    assert.deepEqual(entry, {work_date: FIRST_HOLIDAY, category: 'worked', start_time: '08:00', end_time: '14:30', unpaid_break_minutes: 30});
  }},
  'holiday-taken': {...HOLIDAY_ENTRY, run: async p => {
    p.pattern(weekdayOf(FIRST_HOLIDAY));
    await p.fill();
    await p.choose(p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY)), 'taken');
    let holiday = p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY));
    assert.doesNotMatch(holiday.className, /undecided/);
    assert.equal(holiday.children[HOLIDAY].children[1].children[0].checked, true);
    assert.equal(holiday.children[HOLIDAY].children[0].children[0].checked, false);
    assert.deepEqual([START, END, BREAK].map(index => holiday.children[index].textContent), ['—', '—', '—']);
    assert.equal(p.field(holiday, PAID).value, '360');
    assert.match(p.el('entry-totals').textContent, /Paid public holiday: 360 min/);
    await p.choose(holiday, 'worked');
    holiday = p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY));
    assert.equal(holiday.children[HOLIDAY].children[0].children[0].checked, true);
    assert.equal(holiday.children[HOLIDAY].children[1].children[0].checked, false);
    assert.equal(p.field(holiday, START).value, '08:00');
    await p.choose(holiday, 'taken');
    await p.review();
    await p.confirmSave();
    await p.settle();
    assert.deepEqual(p.payload().work_entries.find(item => item.work_date === FIRST_HOLIDAY), {work_date: FIRST_HOLIDAY, category: 'public_holiday_taken', paid_minutes: 360});
  }},
  'holiday-by-extra-day': {...HOLIDAY_ENTRY, run: async p => {
    await p.addDay(FIRST_HOLIDAY);
    const holiday = p.rows()[0];
    assert.match(holiday.className, /undecided/);
    assert.equal(p.field(holiday, TYPE), undefined);
    assert.match(holiday.children[TYPE].textContent, /Public holiday/);
    await p.choose(holiday, 'worked');
    p.setCell(p.rows()[0], START, '09:00');
    p.setCell(p.rows()[0], END, '12:00');
    await p.review();
    await p.confirmSave();
    await p.settle();
    assert.equal(p.payload().work_entries[0].category, 'worked');
  }},
  'annual-holiday-refused-on-a-public-holiday': {...HOLIDAY_ENTRY, run: async p => {
    await p.addHoliday(FIRST_HOLIDAY, '6:00');
    assert.match(p.el('holiday-error').textContent, /public holiday/);
    assert.equal(p.rows().length, 0);
  }},
  'public-holiday-taken-once-per-day': {...HOLIDAY_ENTRY, run: async p => {
    p.pattern(weekdayOf(FIRST_HOLIDAY));
    await p.addDay(FIRST_HOLIDAY);
    await p.addDay(FIRST_HOLIDAY);
    for (const row of p.rows()) await p.choose(row, 'taken');
    await p.submit();
    assert.match(p.el('save-error').textContent, new RegExp(`Entries on ${FIRST_HOLIDAY} overlap`));
    assert.equal(p.dialog().open, false);
    assert.equal(p.posts().length, 0);
  }},

  // ---- checks before saving
  'overlap-blocked': {...ENTRY, run: async p => {
    await p.workedRow(day(PLAIN_MONTH, 3), '08:00', '12:00', '0');
    await p.workedRow(day(PLAIN_MONTH, 3), '11:00', '14:00', '0');
    await p.submit();
    assert.match(p.el('save-error').textContent, new RegExp(`Entries on ${day(PLAIN_MONTH, 3)} overlap`));
    assert.equal(p.dialog().open, false);
    const second = p.rows().find(row => p.field(row, START).value === '11:00');
    p.setCell(second, START, '12:00');
    await p.submit();
    assert.equal(p.dialog().open, true);
    await p.confirmSave();
    assert.deepEqual(p.payload().work_entries, [
      {work_date: day(PLAIN_MONTH, 3), category: 'worked', start_time: '08:00', end_time: '12:00', unpaid_break_minutes: 0},
      {work_date: day(PLAIN_MONTH, 3), category: 'worked', start_time: '12:00', end_time: '14:00', unpaid_break_minutes: 0},
    ]);
  }},
  'worked-row-needs-times': {...ENTRY, run: async p => {
    await p.addDay(day(PLAIN_MONTH, 3));
    await p.submit();
    assert.match(p.el('save-error').textContent, new RegExp(`Check the hours and break for ${day(PLAIN_MONTH, 3)}`));
    assert.equal(p.dialog().open, false);
  }},
  'unfinished-date': {...ENTRY, run: async p => {
    p.el('extra-date').value = day(PLAIN_MONTH, 3);
    await p.submit();
    assert.match(p.el('save-error').textContent, /unfinished entry/i);
    assert.equal(p.el('save-error').hidden, false);
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.dialog().open, false);
  }},
  'summary-shows-bonus-and-expenses': {...ENTRY, run: async p => {
    assert.match(p.el('entry-extras').textContent, /Cash bonus: CHF 0\.00 · Expenses: CHF 0\.00/);
    await p.type('cash-bonus', '50');
    await p.type('expense-reimbursements', '12.4');
    assert.match(p.el('entry-extras').textContent, /Cash bonus: CHF 0\.00/);
    await p.click(p.el('add-bonus'));
    assert.match(p.el('entry-extras').textContent, /Cash bonus: CHF 50\.00/);
    assert.match(p.el('entry-extras').textContent, /Expenses: CHF 12\.40/);
    assert.equal(p.el('cash-bonus').value, '50.00');
    assert.equal(p.el('expense-reimbursements').value, '12.40');
    assert.equal(p.el('bonus-error').hidden, true);
  }},
  'bonus-add-problems': {...ENTRY, run: async p => {
    await p.type('cash-bonus', '-5');
    await p.click(p.el('add-bonus'));
    assert.match(p.el('bonus-error').textContent, /amounts in CHF/i);
    assert.equal(p.el('bonus-error').hidden, false);
    await p.type('cash-bonus', '5.123');
    await p.click(p.el('add-bonus'));
    assert.equal(p.el('bonus-error').hidden, false);
    assert.match(p.el('entry-extras').textContent, /Cash bonus: CHF 0\.00/);
    await p.type('cash-bonus', '');
    await p.click(p.el('add-bonus'));
    assert.equal(p.el('bonus-error').hidden, true);
    assert.equal(p.el('cash-bonus').value, '0.00');
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.el('extra-error').hidden, true);
  }},
  'bonus-needs-add-before-saving': {...ENTRY, run: async p => {
    await p.type('cash-bonus', '50.00');
    await p.submit();
    assert.match(p.el('save-error').textContent, /Press Add for the bonus and expenses/);
    assert.equal(p.dialog().open, false);
    await p.click(p.el('add-bonus'));
    await p.review();
    assert.match(p.el('timesheet-summary').textContent, /Cash bonus: CHF 50\.00/);
    await p.confirmSave();
    await p.settle();
    assert.equal(p.payload().cash_bonus, '50.00');
    assert.equal(p.payload().expense_reimbursements, '0.00');
  }},
  'leave-warning': {...ENTRY, run: async p => {
    assert.equal(p.leaveWarning(), '');
    await p.addDay(day(PLAIN_MONTH, 3));
    assert.match(p.leaveWarning(), /discard/i);
    await p.click(p.buttons(p.rows()[0]).at(-1));
    assert.equal(p.leaveWarning(), '');
    await p.type('cash-bonus', '5.00');
    assert.match(p.leaveWarning(), /discard/i);
    await p.type('cash-bonus', '0.00');
    assert.equal(p.leaveWarning(), '');
    await p.workedRow(day(PLAIN_MONTH, 3));
    await saveAndCheck(p, ['worked']);
    assert.equal(p.leaveWarning(), '');
  }},
  'leave-warning-on-the-landing': {employments: [LEA], run: async p => {
    assert.equal(p.leaveWarning(), '');
  }},

  // ---- saving
  'cancel-dialog': {...ENTRY, run: async p => {
    await p.workedRow(day(PLAIN_MONTH, 3));
    await p.bonuses();
    await p.review();
    const summary = p.el('timesheet-summary').textContent;
    assert.match(summary, /Lea Beispiel/);
    assert.match(summary, new RegExp(label(PLAIN_MONTH)));
    assert.match(summary, /1 entry/);
    assert.match(summary, /Cash bonus: CHF 50\.00/);
    assert.match(summary, /Expenses: CHF 12\.40/);
    const idle = p.escape();
    p.dialog().listeners.cancel(idle);
    assert.equal(idle.prevented, false);
    await p.click(p.el('timesheet-cancel'));
    assert.equal(p.dialog().open, false);
    assert.equal(p.posts().length, 0);
    assert.equal(p.rows().length, 1);
    assert.equal(p.el('save-payroll').disabled, false);
  }},
  'empty-month': {...ENTRY, run: async p => {
    await p.review();
    assert.match(p.el('timesheet-summary').textContent, /No entries/);
    await p.confirmSave();
    await p.settle();
    assert.deepEqual(p.payload().work_entries, []);
  }},
  'submit-month': {...ENTRY, run: async p => saved(p)},
  'all-row-kinds': {...HOLIDAY_ENTRY, run: async p => {
    p.month = HOLIDAY_MONTH;
    await p.workedRow(NORMAL_DAYS[0]);
    p.pattern(1);
    await p.addHoliday(NORMAL_DAYS[1], '6:00');
    await p.addDay(FIRST_HOLIDAY);
    await p.addDay(SECOND_HOLIDAY);
    await p.choose(p.rows().find(row => row.children[DATE].textContent.startsWith(FIRST_HOLIDAY)), 'taken');
    await p.choose(p.rows().find(row => row.children[DATE].textContent.startsWith(SECOND_HOLIDAY)), 'worked');
    p.setCell(p.rows().find(row => row.children[DATE].textContent.startsWith(SECOND_HOLIDAY)), START, '09:00');
    p.setCell(p.rows().find(row => row.children[DATE].textContent.startsWith(SECOND_HOLIDAY)), END, '12:00');
    await saveAndCheck(p, ['worked', 'annual_holiday_taken', 'public_holiday_taken', 'worked']);
  }},
  'duplicate-submit': {...ENTRY, hold: true, run: async p => { p.holdCheck = true; await saved(p); }},
  'payroll-401': {...ENTRY, postStatus: 401, run: async p => rejected(p)},
  'payroll-403': {...ENTRY, postStatus: 403, run: async p => rejected(p)},
  'payroll-network': {...ENTRY, postFails: true, run: async p => {
    await p.workedRow(day(PLAIN_MONTH, 3));
    await saveAndCheck(p, ['worked']);
    assert.match(p.el('save-error').textContent, /may have been saved/i);
    assert.equal(p.el('page-error').hidden, true);
    assert.equal(p.el('save-payroll').disabled, true);
    await p.submit();
    assert.equal(p.posts().length, 1);
    assert.equal(p.dialog().open, false);
  }},
  'payroll-saved-500': {...ENTRY, postStatus: 500, run: async p => {
    await p.workedRow(day(PLAIN_MONTH, 3));
    await saveAndCheck(p, ['worked']);
    assert.match(p.el('save-message').textContent, /payroll was saved/i);
    assert.equal(p.el('save-confirmation').hidden, false);
    await p.click(p.el('view-saved-payslip'));
    assert.equal(p.redirects.at(-1), payslipPage(PLAIN_MONTH));
    assert.equal(p.el('save-payroll').disabled, true);
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
