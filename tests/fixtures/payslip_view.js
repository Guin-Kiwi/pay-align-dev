const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const YEAR = Number(process.env.RULES_YEAR);
assert.ok(Number.isInteger(YEAR), 'RULES_YEAR must be set');
const PAGE = '/payslips';
const QUERY = `?employment_id=7&year=${YEAR}&month=4`;

class Element {
  constructor() { this.value = ''; this.textContent = ''; this.hidden = true; this.disabled = false; this.options = []; this.handlers = {}; }
  addEventListener(type, handler) { this.handlers[type] = handler; }
  replaceChildren(...children) { this.options = children; this.value = children[0]?.value || ''; }
  append(child) { this.options.push(child); }
}

const detail = {
  hourly_wage: '28.50', cash_bonus: '100.00', gross_wage: '256.75',
  ahv_deduction: '13.61', alv_deduction: '2.82', tax_deduction: '12.84',
  nbu_deduction: '0.00', expense_reimbursements: '50.00', net_payout: '277.48',
  employer_ahv: '13.61', employer_alv: '2.82', employer_fak: '4.24',
  employer_bu: '1.30', admin_charge: '1.36', total_employer_cost: '330.08',
  worked_minutes: 120, public_holiday_worked_minutes: 60,
  annual_holiday_taken_minutes: 30, public_holiday_taken_minutes: 90,
  holiday_balance_minutes: 605,
};

async function scenario(failure) {
  const elements = new Map();
  const el = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const requests = [];
  const assigned = [];
  let prints = 0;
  const fetch = async url => {
    requests.push(url);
    if (failure === 'session') return {status: 401, ok: false};
    if (url === '/api/v1/employer') return {status: 200, ok: true, json: async () => ({name: '<Employer>', ahv_number: '756.9876.5432.17'})};
    if (url === '/api/v1/employments') return {status: 200, ok: true, json: async () => [
      {id: 7, employee_name: '<Employee>', start_date: `${YEAR}-04-01`, end_date: `${YEAR}-09-30`},
      {id: 8, employee_name: '<Employee>', start_date: `${YEAR}-10-01`, end_date: null}]};
    if (url === '/api/v1/employments/7') return {status: 200, ok: true, json: async () => ({id: 7, employee_name: '<Employee>', employee_ahv_number: '756.1234.5678.97'})};
    if (url === '/api/v1/employments/7/months') return {status: 200, ok: true, json: async () => ({months: [{year: YEAR, month: 4}], next_month: failure === 'finished' ? null : {year: YEAR, month: 5}})};
    if (failure === 'detail') return {status: 500, ok: false};
    return {status: 200, ok: true, json: async () => detail};
  };
  const context = {document: {getElementById: el, createElement: () => new Element()}, fetch,
    window: {location: {pathname: PAGE, search: QUERY, assign: url => { assigned.push(url); }}, print: () => { prints++; },
      sessionStorage: {getItem: () => JSON.stringify({url: `${PAGE}${QUERY}`, message: 'Payroll processed successfully.'}), removeItem: () => {}}},
    URLSearchParams, Intl, Date, Number, BigInt, Object, String, Error};
  vm.runInNewContext(process.argv.slice(2).map(path => fs.readFileSync(path, 'utf8')).join('\n'), context);
  for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(el('save-confirmation').textContent, 'Payroll processed successfully.');
  assert.equal(el('save-confirmation').hidden, false);
  if (failure === 'session') {
    assert.match(el('error').textContent, /session has expired/);
    assert.equal(el('payslip').hidden, true);
  } else if (failure === 'detail') {
    assert.equal(el('payslip').hidden, true);
    assert.equal(el('employer-costs').hidden, true);
    assert.equal(el('retry').hidden, false);
    assert.match(el('error').textContent, /could not be loaded/);
  } else {
    assert.equal(el('payslip').hidden, false);
    assert.equal(el('employer-costs').hidden, false);
    assert.deepEqual(el('employment').options.slice(1).map(item => item.textContent),
      [`<Employee> · from ${YEAR}-04-01 to ${YEAR}-09-30`, `<Employee> · from ${YEAR}-10-01`]);
    assert.equal(el('employer-total').textContent, 'CHF 330.08');
    assert.equal(el('employee-name').textContent, '<Employee>');
    assert.equal(el('employer-name').textContent, '<Employer>');
    assert.equal(el('employee-ahv-number').textContent, '756.1234.5678.97');
    assert.equal(el('period').textContent, `April ${YEAR}`);
    assert.equal(el('hourly-pay').textContent, 'CHF 156.75');
    assert.equal(el('deductions').textContent, 'CHF 29.27');
    assert.equal(el('expenses').textContent, 'CHF 50.00');
    assert.equal(el('net').textContent, 'CHF 277.48');
    assert.equal(el('public-worked').textContent, '1 h 00 min');
    assert.equal(el('holiday-balance').textContent, '10 h 05 min');
    assert.ok(requests.includes(`/api/v1/employments/7/months/${YEAR}/4`));
    el('print').handlers.click();
    assert.equal(prints, 1);
    if (failure === 'finished') {
      assert.equal(el('enter-timesheet').hidden, true);
    } else {
      assert.equal(el('enter-timesheet').hidden, false);
      assert.equal(el('enter-timesheet').textContent, `Enter timesheet for May ${YEAR}`);
      el('enter-timesheet').handlers.click();
      assert.equal(assigned.length, 1);
      assert.equal(assigned[0], '/timesheets?employment_id=7');
    }
  }
}

(async () => { await scenario(); await scenario('finished'); await scenario('detail'); await scenario('session'); })().catch(error => { console.error(error); process.exitCode = 1; });
