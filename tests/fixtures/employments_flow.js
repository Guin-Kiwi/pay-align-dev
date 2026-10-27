const assert = require("node:assert/strict");
const vm = require("node:vm");

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => input += chunk);
process.stdin.on("end", async () => {
  try {
    const {scenario, elements: attributes, javascript} = JSON.parse(input);
    const calls = [];
    const redirects = [];
    let releasePayroll;

    function makeElement(tag = "div", attrs = {}) {
      let text = "";
      return {
        tag, id: attrs.id, value: attrs.value ?? "", hidden: Object.hasOwn(attrs, "hidden"),
        disabled: Object.hasOwn(attrs, "disabled"), children: [], listeners: {},
        validationMessage: "", dataset: {},
        get textContent() { return text + this.children.map(child => child.textContent ?? "").join(""); },
        set textContent(value) { text = String(value); this.children = []; },
        addEventListener(event, callback) { this.listeners[event] = callback; },
        setAttribute(name, value) { this[name] = value; },
        setCustomValidity(message) { this.validationMessage = message; },
        append(...children) { this.children.push(...children); },
        replaceChildren(...children) { this.children = children; },
        focus() { this.focused = true; },
        set innerHTML(_) { throw new Error("Unsafe HTML rendering"); }
      };
    }

    const elements = Object.fromEntries(
      Object.entries(attributes).map(([id, attrs]) => [id, makeElement("existing", {id, ...attrs})])
    );
    const response = (status, body) => ({
      status,
      json: async () => body,
    });
    const payslip = {
      monthly_record_id: 11,
      gross_wage: "741.00",
      ahv_deduction: "39.27",
      alv_deduction: "8.15",
      tax_deduction: "33.35",
      nbu_deduction: "3.70",
      net_payout: "656.53",
      employer_ahv: "39.27",
      employer_alv: "8.15",
      employer_fak: "12.60",
      employer_bu: "2.96",
      admin_charge: "1.96",
      total_employer_cost: "806.94",
      holiday_balance_minutes: 31,
    };
    const context = {
      document: {
        getElementById(id) { assert.ok(elements[id], id); return elements[id]; },
        createElement(tag) { return makeElement(tag); },
      },
      window: {location: {replace(url) { redirects.push(url); }}},
      AbortController,
      setTimeout,
      clearTimeout,
      async fetch(url, options = {}) {
        calls.push({url, method: options.method ?? "GET", headers: options.headers ?? {}, body: options.body});
        if (url === "/api/v1/auth/csrf") return response(200, {csrf_token: "csrf-token"});
        if (url === "/api/v1/employments") {
          if (scenario === "list-401") return response(401, {detail: "Authentication required."});
          return response(200, scenario === "empty" ? [] : [
            {id: 7, employee_name: "Lea Beispiel", start_date: "2026-01-05", end_date: null},
          ]);
        }
        if (url === "/api/v1/employments/7/months") {
          if (scenario === "months-401") return response(401, {detail: "Authentication required."});
          return response(200, {
          months: [{monthly_record_id: 11, year: 2026, month: 1}],
          next_month: {year: 2026, month: 2},
          });
        }
        if (url === "/api/v1/employments/7/months/2026/1" ||
            url === "/api/v1/employments/7/months/2026/2") {
          if (scenario === "payslip-401") return response(401, {detail: "Authentication required."});
          return response(200, payslip);
        }
        if (url === "/api/v1/monthly-payroll") {
          assert.equal(options.method, "POST");
          if (scenario === "duplicate-submit") await new Promise(resolve => releasePayroll = resolve);
          if (scenario === "payroll-network") throw new Error("offline");
          if (scenario === "payroll-401") return response(401, {detail: "Authentication required."});
          if (scenario === "payroll-403") return response(403, {detail: "Invalid CSRF token."});
          return response(201, {monthly_record_id: 11, gross_wage: "741.00", net_payout: "656.53"});
        }
        if (url === "/api/v1/auth/logout") {
          assert.equal(options.method, "POST");
          if (scenario === "logout-403") return response(403, {detail: "Invalid CSRF token."});
          return response(204, null);
        }
        throw new Error(`Unexpected request ${url}`);
      },
    };

    vm.runInNewContext(javascript, context);
    const settle = async () => { for (let index = 0; index < 20; index++) await Promise.resolve(); };
    await settle();

    function buttons(node) {
      const found = [];
      for (const child of node.children) {
        if (child.tag === "button") found.push(child);
        found.push(...buttons(child));
      }
      return found;
    }
    const click = async target => { const result = target.listeners.click?.({preventDefault() {}}); await result; await settle(); };
    const selectEmployment = async () => click(buttons(elements["employment-list"])[0]);
    const openEntry = async () => {
      await selectEmployment();
      await click(elements["open-month-entry"]);
    };
    const fillEntry = () => {
      elements["work-date"].value = "2026-02-03";
      elements["work-category"].value = "worked";
      elements["start-time"].value = "08:00";
      elements["end-time"].value = "14:30";
      elements["unpaid-break-minutes"].value = "0";
      elements["paid-minutes"].value = "";
      elements["cash-bonus"].value = "50.00";
      elements["expense-reimbursements"].value = "12.40";
    };
    const submit = () => elements["payroll-form"].listeners.submit({preventDefault() {}});

    assert.equal(calls[0].url, "/api/v1/auth/csrf");
    assert.equal(calls[1].url, "/api/v1/employments");
    if (scenario === "empty") {
      assert.equal(elements["employment-empty"].hidden, false);
      assert.equal(buttons(elements["employment-list"]).length, 0);
    } else if (scenario === "list-401") {
      assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
      assert.equal(elements["page-error"].children[0].href, "/login");
      assert.equal(elements["page-status"].textContent, "");
    } else if (scenario === "list") {
      assert.equal(buttons(elements["employment-list"]).length, 1);
      assert.match(buttons(elements["employment-list"])[0].textContent, /Lea Beispiel/);
      await selectEmployment();
      assert.equal(elements["months-section"].hidden, false);
      assert.match(elements["next-month"].textContent, /February 2026/);
    } else if (scenario === "completed-month") {
      await selectEmployment();
      const completed = buttons(elements["month-list"]);
      assert.equal(completed.length, 1);
      assert.match(completed[0].textContent, /January 2026/);
      await click(completed[0]);
      assert.equal(elements["payslip-section"].hidden, false);
      assert.match(elements["payslip-details"].textContent, /741\.00/);
      assert.doesNotMatch(elements["payslip-details"].textContent, /delete|edit/i);
    } else if (scenario === "months-401") {
      await selectEmployment();
      assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
      assert.equal(elements["page-status"].textContent, "");
    } else if (scenario === "payslip-401") {
      await selectEmployment();
      await click(buttons(elements["month-list"])[0]);
      assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
      assert.equal(elements["page-status"].textContent, "");
    } else if (["submit-month", "duplicate-submit", "payroll-401", "payroll-403", "payroll-network"].includes(scenario)) {
      await openEntry();
      fillEntry();
      const pending = submit();
      await settle();
      if (scenario === "duplicate-submit") {
        assert.equal(elements["save-payroll"].disabled, true);
        await submit();
        assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 1);
        releasePayroll();
      }
      await pending;
      await settle();
      const posts = calls.filter(call => call.url === "/api/v1/monthly-payroll");
      assert.equal(posts.length, 1);
      assert.equal(posts[0].headers["X-CSRF-Token"], "csrf-token");
      assert.deepEqual(JSON.parse(posts[0].body), {
        employment_id: 7,
        year: 2026,
        month: 2,
        cash_bonus: "50.00",
        expense_reimbursements: "12.40",
        work_entries: [{
          work_date: "2026-02-03",
          category: "worked",
          start_time: "08:00",
          end_time: "14:30",
          unpaid_break_minutes: 0,
        }],
      });
      assert.equal(elements["work-date"].value, "2026-02-03");
      if (["payroll-401", "payroll-403"].includes(scenario)) {
        assert.match(elements["page-error"].textContent, /request was rejected/i);
        assert.match(elements["page-error"].textContent, /log in again/i);
        assert.doesNotMatch(elements["page-error"].textContent, /may have been saved/i);
        assert.equal(elements["save-payroll"].disabled, false);
      } else if (scenario === "payroll-network") {
        assert.match(elements["page-error"].textContent, /may have been saved/i);
        assert.equal(elements["save-payroll"].disabled, true);
        await submit();
        assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 1);
      } else {
        assert.equal(elements["payslip-section"].hidden, false);
        assert.match(elements["payslip-details"].textContent, /656\.53/);
      }
    } else if (scenario === "logout" || scenario === "logout-403") {
      await click(elements["logout-button"]);
      const logout = calls.filter(call => call.url === "/api/v1/auth/logout");
      assert.equal(logout.length, 1);
      assert.equal(logout[0].headers["X-CSRF-Token"], "csrf-token");
      if (scenario === "logout") assert.deepEqual(redirects, ["/login"]);
      else {
        assert.deepEqual(redirects, []);
        assert.match(elements["page-error"].textContent, /request was rejected/i);
      }
    }
    process.stdout.write("ok");
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
});
