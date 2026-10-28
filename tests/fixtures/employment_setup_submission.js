const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  try {
    const {scenario, elements: attributes, javascript, year: YEAR} = JSON.parse(input);
    const day = (month, date, year = YEAR) => `${year}-${String(month).padStart(2, '0')}-${String(date).padStart(2, '0')}`;
    const focused = [];
    const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, {
      id, value: attrs.value ?? (id === 'holiday-weeks' ? '4' : ''),
      hidden: Object.hasOwn(attrs, 'hidden'), disabled: Object.hasOwn(attrs, 'disabled'),
      textContent: '', children: [], listeners: {}, open: false,
      showModal() { this.open = true; },
      close() { this.open = false; },
      setCustomValidity(message) { this.validationMessage = message; },
      setAttribute(name, value) { this[name] = value; },
      addEventListener(event, callback) { this.listeners[event] = callback; },
      focus() { focused.push(id); },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      set innerHTML(value) { throw new Error('Unsafe HTML rendering'); }
    }]));
    const employer = {id: 1, name: 'Anna', address: 'Basel', ahv_number: '756.1234.5678.97', contact_info: 'anna@example.ch'};
    const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body});
    const posts = [];
    let gets = 0;
    let csrfGets = 0;
    const redirects = [];
    let releasePost, releaseLookup, abortPost;
    const success = {message: 'Employment set up successfully', employer_id: 1, employee_id: 1, employment_id: 1};
    const attack = '<img src=x onerror=alert(1)>';
    const context = {
      document: {
        getElementById: id => { assert.ok(elements[id], id); return elements[id]; },
        createElement: tag => ({textContent: '', tag, addEventListener() {}})
      },
      window: {location: {replace(url) { redirects.push(url); }, assign(url) { redirects.push(url); }}},
      AbortController,
      setTimeout: (callback, delay) => {
        if (scenario === 'timeout' && delay === 15000) { abortPost = callback; return -1; }
        return setTimeout(callback, delay);
      },
      clearTimeout: timer => { if (timer !== -1) clearTimeout(timer); },
      fetch: async (url, options = {}) => {
        if (url === '/api/v1/auth/csrf') {
          csrfGets++;
          return response(200, {csrf_token: 'test-csrf-token'});
        }
        if (url === '/api/v1/employer') {
          gets++;
          if (scenario === 'loading') await new Promise(resolve => releaseLookup = resolve);
          if (scenario === 'lookup-network' || (scenario === 'refresh-failure' && gets > 1)) throw new Error('offline');
          if (scenario === 'lookup-401') return response(401, {detail: 'Authentication required.'});
          if (scenario === 'lookup-500') return response(500, {});
          if (scenario === 'lookup-malformed') return response(200, {name: 'Anna'});
          if (scenario === 'lookup-id') return response(200, {...employer, id: '1'});
          if (scenario === 'lookup-404') return response(404, {detail: 'Wrong endpoint'});
          return response(200, employer);
        }
        assert.equal(url, '/api/v1/setup');
        assert.equal(options.method, 'POST');
        assert.equal(options.headers['Content-Type'], 'application/json');
        assert.equal(options.headers['X-CSRF-Token'], 'test-csrf-token');
        posts.push(JSON.parse(options.body));
        if (scenario === 'duplicate') await new Promise(resolve => releasePost = resolve);
        if (scenario === 'timeout') await new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('timeout'))));
        if (scenario === '200') return response(200, success);
        if (scenario === 'network') throw new Error('offline');
        if (scenario === 'invalid-json') return {status: 201, json: async () => {throw new Error('json');}};
        if (scenario === 'malformed-success') return response(201, {...success, employment_id: '1'});
        if (['400', '409', '500'].includes(scenario)) return response(Number(scenario), {detail: attack});
        if (scenario === '401') return response(401, {detail: 'Authentication required.'});
        if (scenario === '403') return response(403, {detail: 'Invalid CSRF token.'});
        if (scenario === '422') return response(422, {detail: [{loc: ['body', 'employee', 'name'], msg: attack}]});
        return response(201, success);
      }
    };
    vm.runInNewContext(javascript, context);
    const settle = async () => { for (let i = 0; i < 15; i++) await Promise.resolve(); };
    await settle();
    assert.equal(csrfGets, 1);
    const set = (id, value) => {
      elements[id].value = value;
      const handler = elements[id].listeners[id === 'holiday-weeks' ? 'change' : 'input'];
      assert.ok(handler, id); handler();
    };
    const values = {
      'employer-name': 'Anna', 'employer-address': 'Basel', 'employer-ahv': '756.1234.5678.97', 'employer-contact': 'anna@example.ch',
      'employee-name': 'Maria', 'employee-address': 'Basel', 'employee-ahv': '756.9876.5432.10', 'employee-nationality': 'Italy',
      'start-date': day(3, 1), 'hourly-wage': '28.50', 'weekly-hours': '6:30', 'holiday-weeks': '4'
    };
    const submit = () => elements['setup-form'].listeners.submit({preventDefault() {}});
    const dialog = () => elements['add-employment-dialog'];
    const confirmAdd = () => elements['add-employment-confirm'].listeners.click();
    const escape = () => ({prevented: false, preventDefault() { this.prevented = true; }});
    if (scenario === 'required-empty') {
      const required = [
        'employee-name', 'employee-address', 'employee-ahv', 'employee-nationality',
        'start-date', 'hourly-wage', 'weekly-hours'
      ];
      assert.equal(elements['save-setup'].disabled, false);
      for (const id of required) assert.equal(elements[`${id}-error`].hidden, true, id);
      await submit();
      assert.equal(posts.length, 0);
      assert.equal(dialog().open, false);
      for (const id of required) {
        assert.equal(elements[`${id}-error`].hidden, false, id);
        assert.notEqual(elements[`${id}-error`].textContent, '', id);
        assert.equal(elements[id]['aria-invalid'], 'true', id);
      }
      assert.deepEqual(focused, ['employee-name']);
      assert.equal(elements['save-setup'].disabled, false);
    } else if (scenario.startsWith('lookup-') || scenario === 'loading') {
      assert.equal(elements['save-setup'].disabled, true);
      await submit(); assert.equal(posts.length, 0);
      if (releaseLookup) {releaseLookup(); await settle();}
      if (scenario === 'lookup-401') {
        assert.match(elements['employer-error'].textContent, /session has expired/i);
        assert.doesNotMatch(elements['employer-error'].textContent, /connection/i);
        assert.equal(elements['employer-error'].children.length, 1);
        assert.equal(elements['employer-error'].children[0].tag, 'button');
      }
    } else {
      for (const [id, value] of Object.entries(values)) set(id, value);
      if (scenario === 'invalid') {
        for (const [id, bad] of [['weekly-hours', '0:00'], ['hourly-wage', '22.19'], ['start-date', day(1, 1, YEAR + 1)], ['employee-ahv', '7561234567897'], ['employee-name', '   '], ['holiday-weeks', '20']]) {
          set(id, bad); assert.equal(elements['save-setup'].disabled, false); await submit();
          assert.equal(posts.length, 0); assert.equal(dialog().open, false); set(id, values[id]);
        }
      } else if (scenario === 'cancel') {
        await submit();
        assert.equal(dialog().open, true);
        assert.match(elements['add-employment-summary'].textContent, /Maria/);
        assert.match(elements['add-employment-summary'].textContent, new RegExp(day(3, 1)));
        const idle = escape();
        dialog().listeners.cancel(idle);
        assert.equal(idle.prevented, false);
        elements['add-employment-cancel'].listeners.click();
        assert.equal(dialog().open, false);
        assert.equal(posts.length, 0);
        assert.equal(elements['save-setup'].disabled, false);
        await settle();
        assert.equal(posts.length, 0);
      } else {
        assert.equal(elements['save-setup'].disabled, false);
        if (scenario === 'end-date') set('end-date', day(8, 31, YEAR + 1));
        if (scenario === 'holiday-five') set('holiday-weeks', '5');
        await submit();
        assert.equal(dialog().open, true);
        assert.equal(posts.length, 0);
        assert.match(elements['add-employment-summary'].textContent, /Maria/);
        const pending = confirmAdd();
        if (scenario === 'timeout') abortPost();
        if (scenario === 'duplicate') {
          assert.equal(elements['save-setup'].disabled, true);
          assert.equal(elements['add-employment-confirm'].disabled, true);
          assert.equal(elements['add-employment-cancel'].disabled, true);
          const saving = escape();
          dialog().listeners.cancel(saving);
          assert.equal(saving.prevented, true);
          await confirmAdd(); await submit(); assert.equal(posts.length, 1); releasePost();
        }
        await pending; await settle();
        assert.equal(posts.length, 1);
        assert.equal(dialog().open, false);
        assert.equal(elements['add-employment-confirm'].disabled, false);
        const expected = {
          employee: {name: 'Maria', address: 'Basel', ahv_number: '756.9876.5432.10', nationality: 'Italy', tax_status: 'ordinary'},
          employment: {start_date: day(3, 1), end_date: scenario === 'end-date' ? day(8, 31, YEAR + 1) : null, hourly_wage: '28.50', weekly_hours: '6:30', holiday_weeks: scenario === 'holiday-five' ? 5 : 4}
        };
        assert.deepEqual(posts[0], expected);
        for (const [id, value] of Object.entries(values)) assert.equal(elements[id].value, scenario === 'holiday-five' && id === 'holiday-weeks' ? '5' : value);
        if (['400', '409', '422'].includes(scenario)) {
          assert.equal(elements['setup-error'].hidden, false);
          assert.ok(elements['setup-error'].textContent.includes(attack));
          assert.equal(elements['save-setup'].disabled, false);
        } else if (['401', '403'].includes(scenario)) {
          assert.match(elements['setup-error'].textContent, /request was rejected/i);
          assert.match(elements['setup-error'].textContent, /log in again/i);
          assert.doesNotMatch(elements['setup-error'].textContent, /may have been saved/i);
          assert.equal(elements['setup-error'].children.length, 1);
          assert.equal(elements['setup-error'].children[0].tag, 'button');
          assert.equal(elements['save-setup'].disabled, false);
          await settle(); assert.equal(posts.length, 1, 'Authentication rejection must not retry');
        } else if (['network', 'timeout', '200', '500', 'malformed-success', 'invalid-json'].includes(scenario)) {
          assert.match(elements['setup-error'].textContent, /may have been saved/);
          assert.equal(elements['save-setup'].disabled, true);
          await submit(); assert.equal(posts.length, 1);
        } else {
          assert.deepEqual(redirects, ['/home']);
          assert.equal(gets, 1);
          assert.equal(elements['save-setup'].disabled, true);
          await submit(); assert.equal(posts.length, 1);
        }
      }
    }
    process.stdout.write(JSON.stringify(posts));
  } catch (error) { console.error(error); process.exitCode = 1; }
});
