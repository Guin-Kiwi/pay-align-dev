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
    const assigned = [];
    const storage = new Map();
    const events = [];
    const confirmations = [];
    let releasePayroll;
    let confirmResult = false;

    function makeElement(tag = "div", attrs = {}) {
      let text = "";
      return {
        tag, id: attrs.id, type: attrs.type, value: attrs.value ?? "",
        checked: Object.hasOwn(attrs, "checked"),
        hidden: Object.hasOwn(attrs, "hidden"), disabled: Object.hasOwn(attrs, "disabled"),
        children: [], listeners: {}, dataset: {}, className: attrs.class ?? "",
        get textContent() { return text + this.children.map(child => child.textContent ?? "").join(""); },
        set textContent(value) { text = String(value); this.children = []; },
        addEventListener(event, callback) { this.listeners[event] = callback; },
        setAttribute(name, value) { this[name] = value; },
        append(...children) { this.children.push(...children); },
        replaceChildren(...children) { this.children = children; },
        focus() { this.focused = true; },
        set innerHTML(_) { throw new Error("Unsafe HTML rendering"); },
      };
    }

    const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, makeElement("existing", {id, ...attrs})]));
    const response = (status, body) => ({status, json: async () => body});
    const publicHolidayScenario = scenario === "public-holiday";
    const month = publicHolidayScenario ? 5 : 2;
    const employment = {
      id: 7, employee_name: "Lea Beispiel",
      start_date: scenario === "fill-boundaries" ? "2026-02-05" : "2026-01-05",
      end_date: scenario === "fill-boundaries" ? "2026-02-18" : null,
    };
    const context = {
      document: {
        getElementById(id) { id = id.replace(/^workspace-/, ""); assert.ok(elements[id], id); return elements[id]; },
        createElement(tag) { return makeElement(tag); },
      },
      window: {
        location: {replace(url) { redirects.push(url); }, assign(url) { assigned.push(url); }},
        sessionStorage: {
          getItem(key) { return storage.has(key) ? storage.get(key) : null; },
          setItem(key, value) { storage.set(key, String(value)); },
          removeItem(key) { storage.delete(key); },
        },
        confirm(message) { confirmations.push(message); return confirmResult; },
        dispatchEvent(event) { events.push(event.type); },
      },
      Event: class { constructor(type) { this.type = type; } },
      AbortController, Date, Set, Map, Object, Number, String, Array,
      setTimeout, clearTimeout,
      async fetch(url, options = {}) {
        calls.push({url, method: options.method ?? "GET", headers: options.headers ?? {}, body: options.body});
        if (url === "/api/v1/auth/csrf") return response(200, {csrf_token: "csrf-token"});
        if (url === "/api/v1/public-holidays/2026") {
          if (scenario === "holidays-401") return response(401, {detail: "Authentication required."});
          return response(200, {year: 2026, dates: ["2026-01-01", "2026-04-03", "2026-04-06", "2026-05-01", "2026-05-14", "2026-05-25", "2026-08-01", "2026-12-25", "2026-12-26"]});
        }
        if (url === "/api/v1/employments") {
          if (scenario === "list-401") return response(401, {detail: "Authentication required."});
          return response(200, scenario === "empty" ? [] : [employment]);
        }
        if (url === "/api/v1/employments/7/months") {
          if (scenario === "months-401") return response(401, {detail: "Authentication required."});
          return response(200, {months: [{monthly_record_id: 11, year: 2026, month: 1}], next_month: {year: 2026, month}});
        }
        if (url === "/api/v1/monthly-payroll") {
          assert.equal(options.method, "POST");
          if (scenario === "duplicate-submit") await new Promise(resolve => releasePayroll = resolve);
          if (scenario === "payroll-network") throw new Error("offline");
          if (scenario === "payroll-401") return response(401, {detail: "Authentication required."});
          if (scenario === "payroll-403") return response(403, {detail: "Invalid CSRF token."});
          return response(201, {message: "Payroll processed successfully.", monthly_record_id: 11, gross_wage: "741.00", net_payout: "656.53"});
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
    const settle = async () => { for (let index = 0; index < 30; index += 1) await Promise.resolve(); };
    await settle();

    function walk(node, predicate, found = []) {
      for (const child of node.children) {
        if (predicate(child)) found.push(child);
        walk(child, predicate, found);
      }
      return found;
    }
    const buttons = node => walk(node, child => child.tag === "button");
    const inputs = node => walk(node, child => child.tag === "input" || child.tag === "select");
    const labelled = (node, fragment) => inputs(node).find(child => String(child["aria-label"] ?? "").includes(fragment));
    const click = async target => { const result = target.listeners.click?.({preventDefault() {}}); await result; await settle(); };
    const change = async target => { const result = target.listeners.change?.({preventDefault() {}}); await result; await settle(); };
    const submitReview = async () => { await elements["payroll-form"].listeners.submit({preventDefault() {}}); await settle(); };
    const selectEmployment = async () => click(buttons(elements["employment-list"])[0]);
    const openEntry = async () => { await selectEmployment(); await click(elements["open-month-entry"]); };
    const setPattern = (day, start = "08:00", end = "12:00", breakMinutes = "30") => {
      elements[`pattern-${day}`].checked = true;
      elements[`pattern-${day}-start`].value = start;
      elements[`pattern-${day}-end`].value = end;
      elements[`pattern-${day}-break`].value = breakMinutes;
    };
    const fillMondays = async () => { setPattern("monday"); await click(elements["fill-month"]); };
    const reviewAndConfirm = async () => { await submitReview(); assert.equal(elements["review-section"].hidden, false); return click(elements["confirm-payroll"]); };

    assert.equal(calls[0].url, "/api/v1/auth/csrf");
    assert.equal(calls[1].url, "/api/v1/public-holidays/2026");
    if (scenario === "holidays-401") {
      assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
      assert.equal(elements["page-error"].children[0].href, "/login");
      assert.equal(calls.some(call => call.url === "/api/v1/employments"), false);
    } else if (scenario === "empty") {
      assert.equal(elements["employment-empty"].hidden, false);
      assert.equal(buttons(elements["employment-list"]).length, 0);
    } else if (scenario === "list-401") {
      assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
      assert.equal(elements["page-error"].children[0].href, "/login");
    } else if (scenario === "list") {
      assert.equal(buttons(elements["employment-list"]).length, 1);
      await selectEmployment();
      assert.equal(elements["months-section"].hidden, false);
      assert.match(elements["next-month"].textContent, /February 2026/);
    } else if (scenario === "completed-month") {
      await selectEmployment();
      const completed = buttons(elements["month-list"]); assert.equal(completed.length, 1);
      await click(completed[0]);
      assert.deepEqual(assigned, ["/payslips?employment_id=7&year=2026&month=1"]);
      assert.equal(calls.some(call => call.url.includes("/months/2026/")), false);
    } else if (scenario === "months-401") {
      await selectEmployment(); assert.match(elements["page-error"].textContent, /session.*expired|log in again/i);
    } else if (scenario === "fill-month" || scenario === "fill-boundaries") {
      await openEntry(); await fillMondays();
      const rows = elements["work-entries-body"].children;
      const expectedDates = scenario === "fill-boundaries" ? ["2026-02-09", "2026-02-16"] : ["2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23"];
      assert.deepEqual(rows.map(row => labelled(row, "Entry date").value), expectedDates);
      assert.equal(labelled(rows[0], "Entry date").max, scenario === "fill-boundaries" ? "2026-02-18" : "2026-02-28");
      if (scenario === "fill-month") {
        const edited = labelled(rows[0], "Start time"); edited.value = "09:00"; await change(edited);
        assert.equal(labelled(elements["work-entries-body"].children[0], "Start time").value, "09:00");
        await click(buttons(elements["work-entries-body"].children[0]).at(-1));
        assert.equal(elements["work-entries-body"].children.length, 3);
      }
    } else if (scenario === "public-holiday") {
      await openEntry(); setPattern("friday"); await click(elements["fill-month"]);
      const first = elements["work-entries-body"].children[0];
      assert.equal(labelled(first, "Entry date").value, "2026-05-01");
      assert.equal(first.className, "public-holiday-row");
      assert.equal(inputs(first).find(control => control.tag === "select").value, "public_holiday_taken");
      assert.equal(labelled(first, "Paid minutes").value, 210);
      elements["annual-holiday-date"].value = "2026-05-01"; elements["annual-holiday-minutes"].value = "210";
      await click(elements["add-annual-holiday"]); assert.match(elements["entry-error"].textContent, /public holiday/i);
      elements["cash-bonus"].value = "0.00"; elements["expense-reimbursements"].value = "0.00";
      await reviewAndConfirm();
      const posted = JSON.parse(calls.find(call => call.url === "/api/v1/monthly-payroll").body);
      assert.deepEqual(posted.work_entries[0], {work_date: "2026-05-01", category: "public_holiday_taken", paid_minutes: 210});
    } else if (scenario === "annual-holiday") {
      await openEntry(); await fillMondays();
      elements["annual-holiday-date"].value = "2026-02-09"; await change(elements["annual-holiday-date"]);
      assert.equal(elements["annual-holiday-minutes"].value, "210");
      await click(elements["add-annual-holiday"]);
      assert.equal(elements["work-entries-body"].children.length, 3);
      assert.equal(elements["holiday-entries-body"].children.length, 1);
      assert.match(elements["entry-totals"].textContent, /Annual holiday210 minutes/);
      confirmResult = true; await click(elements["fill-month"]);
      assert.equal(elements["work-entries-body"].children.length, 3);
      assert.equal(elements["holiday-entries-body"].children.length, 1);
    } else if (scenario === "split-shift") {
      await openEntry();
      elements["work-entry-date"].value = "2026-02-10"; await click(elements["add-workday"]); await click(elements["add-workday"]);
      let rows = elements["work-entries-body"].children;
      labelled(rows[0], "Start time").value = "08:00"; await change(labelled(rows[0], "Start time"));
      rows = elements["work-entries-body"].children; let row = rows.find(candidate => labelled(candidate, "Start time").value === "08:00"); labelled(row, "End time").value = "10:00"; await change(labelled(row, "End time"));
      rows = elements["work-entries-body"].children; row = rows.find(candidate => labelled(candidate, "Start time").value === ""); labelled(row, "Start time").value = "09:30"; await change(labelled(row, "Start time"));
      rows = elements["work-entries-body"].children; row = rows.find(candidate => labelled(candidate, "Start time").value === "09:30"); labelled(row, "End time").value = "12:00"; await change(labelled(row, "End time"));
      await submitReview(); assert.match(elements["entry-error"].textContent, /overlap/i);
      rows = elements["work-entries-body"].children; row = rows.find(candidate => labelled(candidate, "Start time").value === "09:30"); labelled(row, "Start time").value = "10:00"; await change(labelled(row, "Start time"));
      await submitReview(); assert.equal(elements["review-section"].hidden, false);
    } else if (scenario === "regenerate-warning") {
      await openEntry(); await fillMondays();
      let first = elements["work-entries-body"].children[0]; labelled(first, "Start time").value = "09:00"; await change(labelled(first, "Start time"));
      await click(elements["fill-month"]); assert.equal(confirmations.length, 1);
      assert.equal(labelled(elements["work-entries-body"].children[0], "Start time").value, "09:00");
      confirmResult = true; await click(elements["fill-month"]);
      assert.equal(labelled(elements["work-entries-body"].children[0], "Start time").value, "08:00");
    } else if (scenario === "leave-warning") {
      await openEntry();
      assert.equal(context.window.leaveWarning(), "");
      await fillMondays();
      assert.match(context.window.leaveWarning(), /discard/i);
      await selectEmployment();
      assert.equal(confirmations.length, 1);
      assert.equal(elements["entry-section"].hidden, false);
      assert.equal(elements["work-entries-body"].children.length, 4);
    } else if (["submit-month", "duplicate-submit", "payroll-401", "payroll-403", "payroll-network"].includes(scenario)) {
      await openEntry(); await fillMondays();
      elements["annual-holiday-date"].value = "2026-02-09"; await change(elements["annual-holiday-date"]); await click(elements["add-annual-holiday"]);
      elements["cash-bonus"].value = "50.00"; elements["expense-reimbursements"].value = "12.40";
      await submitReview();
      assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 0);
      if (scenario === "submit-month") {
        elements["cash-bonus"].value = "60.00";
        await elements["cash-bonus"].listeners.input(); await settle();
        assert.equal(elements["review-section"].hidden, true);
        await click(elements["confirm-payroll"]);
        assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 0);
        await submitReview();
      }
      const pending = click(elements["confirm-payroll"]); await settle();
      if (scenario === "duplicate-submit") {
        assert.equal(elements["confirm-payroll"].disabled, true); await click(elements["confirm-payroll"]);
        assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 1); releasePayroll();
      }
      await pending; await settle();
      const posts = calls.filter(call => call.url === "/api/v1/monthly-payroll"); assert.equal(posts.length, 1);
      assert.equal(posts[0].headers["X-CSRF-Token"], "csrf-token");
      const payload = JSON.parse(posts[0].body);
      assert.equal(payload.work_entries.length, 4);
      assert.equal(payload.work_entries.filter(entry => entry.category === "worked").length, 3);
      assert.deepEqual(payload.work_entries.find(entry => entry.category === "annual_holiday_taken"), {work_date: "2026-02-09", category: "annual_holiday_taken", paid_minutes: 210});
      if (["payroll-401", "payroll-403"].includes(scenario)) {
        assert.deepEqual(events, []);
        assert.match(elements["page-error"].textContent, /request was rejected/i); assert.match(elements["page-error"].textContent, /log in again/i);
        assert.doesNotMatch(elements["page-error"].textContent, /may have been saved/i); assert.equal(elements["save-payroll"].disabled, false);
      } else if (scenario === "payroll-network") {
        assert.deepEqual(events, []);
        assert.match(elements["page-error"].textContent, /may have been saved/i); assert.equal(elements["save-payroll"].disabled, true);
        await click(elements["confirm-payroll"]); assert.equal(calls.filter(call => call.url === "/api/v1/monthly-payroll").length, 1);
      } else {
        assert.deepEqual(assigned, ["/payslips?employment_id=7&year=2026&month=2"]);
        assert.deepEqual(JSON.parse(storage.get("payalign-saved-confirmation")), {url: "/payslips?employment_id=7&year=2026&month=2", message: "Payroll processed successfully."});
        assert.equal(calls.some(call => call.url.includes("/months/2026/")), false);
        assert.deepEqual(events, ["payalign-payroll-saved"]);
      }
    } else if (scenario === "logout" || scenario === "logout-403") {
      await click(elements["logout-button"]); const logout = calls.filter(call => call.url === "/api/v1/auth/logout");
      assert.equal(logout.length, 1); assert.equal(logout[0].headers["X-CSRF-Token"], "csrf-token");
      if (scenario === "logout") assert.deepEqual(redirects, ["/login"]);
      else { assert.deepEqual(redirects, []); assert.match(elements["page-error"].textContent, /request was rejected/i); }
    }
    process.stdout.write("ok");
  } catch (error) { console.error(error); process.exitCode = 1; }
});
