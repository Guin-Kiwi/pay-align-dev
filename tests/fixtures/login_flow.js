const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  try {
    const {scenario, elements: attributes, javascript, credentials} = JSON.parse(input);
    const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, {
      id, value: attrs.value ?? '',
      hidden: Object.hasOwn(attrs, 'hidden'), disabled: Object.hasOwn(attrs, 'disabled'),
      open: false, textContent: '', children: [], listeners: {},
      setCustomValidity(message) { this.validationMessage = message; },
      setAttribute(name, value) { this[name] = value; },
      addEventListener(event, callback) { this.listeners[event] = callback; },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      showModal() { this.open = true; },
      close() { this.open = false; if (this.listeners.close) this.listeners.close(); },
      set innerHTML(value) { throw new Error('Unsafe HTML rendering'); }
    }]));
    const account = {id: 1, email: 'anna@example.ch', first_name: 'Anna', last_name: 'Muster'};
    const attack = '<img src=x onerror=alert(1)>';
    const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body});
    const calls = [];
    const assigned = [];
    let releaseMe, releasePost, abortTimer;
    const context = {
      document: {getElementById: id => { assert.ok(elements[id], id); return elements[id]; }},
      window: {location: {assign: url => assigned.push(url)}},
      AbortController,
      setTimeout: (callback, delay) => {
        if (scenario === 'me-timeout' && delay === 10000) { abortTimer = callback; return -1; }
        if (scenario === 'login-timeout' && delay === 15000) { abortTimer = callback; return -1; }
        return setTimeout(callback, delay);
      },
      clearTimeout: timer => { if (timer !== -1) clearTimeout(timer); },
      fetch: async (url, options = {}) => {
        calls.push({method: options.method ?? 'GET', url, headers: {...options.headers}, body: options.body ?? null});
        const hang = () => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('timeout'))));
        if (url === '/api/v1/auth/me') {
          if (scenario === 'loading') await new Promise(resolve => releaseMe = resolve);
          if (scenario === 'me-timeout') await hang();
          if (scenario === 'me-network') throw new Error('offline');
          if (scenario === 'me-500') return response(500, {detail: 'boom'});
          if (scenario === 'me-malformed') return response(200, {email: 'anna@example.ch'});
          if (scenario === 'signed-in') return response(200, {...account, first_name: attack});
          return response(401, {detail: 'Authentication required.'});
        }
        if (url === '/api/v1/auth/csrf') {
          if (scenario === 'login-csrf-failure') return response(500, {detail: 'boom'});
          return response(200, {csrf_token: 'csrf-token-1'});
        }
        assert.equal(url, '/api/v1/auth/login');
        assert.equal(options.method, 'POST');
        if (scenario === 'login-duplicate') await new Promise(resolve => releasePost = resolve);
        if (scenario === 'login-timeout') await hang();
        if (scenario === 'login-network') throw new Error('offline');
        if (scenario === 'login-401') return response(401, {detail: 'Invalid email or password.'});
        if (scenario === 'login-403') return response(403, {detail: 'Invalid CSRF token.'});
        if (scenario === 'login-422') return response(422, {detail: [{loc: ['body', 'email'], msg: attack}]});
        if (scenario === 'login-500') return response(500, {detail: attack});
        if (scenario === 'login-malformed') return response(200, {email: 'anna@example.ch'});
        return response(200, {...account, csrf_token: 'rotated-token'});
      }
    };
    vm.runInNewContext(javascript, context);
    const settle = () => new Promise(resolve => setImmediate(resolve));
    await settle();
    const urls = () => calls.map(call => `${call.method} ${call.url}`);
    const set = (id, value) => {
      elements[id].value = value;
      assert.ok(elements[id].listeners.input, id);
      elements[id].listeners.input();
    };
    const submitLogin = () => elements['login-form'].listeners.submit({preventDefault() {}});
    const fill = () => { set('login-email', credentials.email); set('login-password', credentials.password); };

    if (scenario === 'loading') {
      assert.equal(elements['login-submit'].disabled, true);
      assert.match(elements['account-status'].textContent, /Checking/);
      fill(); await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      releaseMe(); await settle();
      assert.equal(elements['login-submit'].disabled, false);
    } else if (scenario === 'signed-in') {
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signed-in'].hidden, false);
      assert.equal(elements['login-panel'].hidden, true);
      assert.ok(elements['signed-in-name'].textContent.includes(`${attack} Muster`));
      assert.ok(elements['signed-in-name'].textContent.includes('anna@example.ch'));
      assert.deepEqual(assigned, []);
    } else if (scenario.startsWith('me-')) {
      if (scenario === 'me-timeout') { abortTimer(); await settle(); }
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['account-error'].hidden, false);
      assert.match(elements['account-error'].textContent, /reload/i);
      assert.equal(elements['login-submit'].disabled, true);
      fill(); await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'signed-out') {
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signed-in'].hidden, true);
      assert.equal(elements['login-panel'].hidden, false);
      assert.equal(elements['account-error'].hidden, true);
      assert.equal(elements['account-status'].textContent, '');
      assert.equal(elements['login-submit'].disabled, false);
      assert.deepEqual(assigned, []);
    } else if (scenario === 'login-empty') {
      await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      for (const id of ['login-email', 'login-password']) {
        assert.equal(elements[`${id}-error`].hidden, false, id);
        assert.equal(elements[`${id}-error`].textContent, 'This field is required.');
        assert.equal(elements[id]['aria-invalid'], 'true');
      }
      set('login-email', credentials.email);
      assert.equal(elements['login-email-error'].hidden, true);
      assert.equal(elements['login-email']['aria-invalid'], 'false');
      assert.equal(elements['login-password-error'].hidden, false);
    } else if (scenario === 'login-duplicate') {
      fill();
      const pending = submitLogin();
      await settle();
      assert.equal(elements['login-submit'].disabled, true);
      await submitLogin();
      releasePost(); await pending; await settle();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/login']);
      assert.deepEqual(assigned, ['/setup']);
    } else {
      fill();
      const pending = submitLogin();
      if (scenario === 'login-timeout') { await settle(); abortTimer(); }
      await pending; await settle();
      if (scenario === 'login') {
        assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/login']);
        assert.deepEqual(calls[2].headers, {
          'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': 'csrf-token-1'
        });
        assert.deepEqual(JSON.parse(calls[2].body), {email: credentials.email, password: credentials.password});
        assert.deepEqual(assigned, ['/setup']);
        assert.equal(elements['login-submit'].disabled, true);
        assert.equal(elements['login-error'].hidden, true);
      } else {
        assert.deepEqual(assigned, []);
        assert.equal(elements['login-submit'].disabled, false);
        assert.equal(elements['login-error'].hidden, false);
        assert.equal(elements['login-email'].value, credentials.email);
        assert.equal(elements['login-password'].value, credentials.password);
        const expected = {
          'login-401': /Invalid email or password\./,
          'login-403': /Reload the page and try again/,
          'login-422': new RegExp(attack.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
          'login-500': /try again/i,
          'login-network': /try again/i,
          'login-timeout': /try again/i,
          'login-csrf-failure': /Nothing was sent/,
          'login-malformed': /try again/i
        }[scenario];
        assert.match(elements['login-error'].textContent, expected);
        if (scenario === 'login-csrf-failure') {
          assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf']);
        }
      }
    }
    process.stdout.write(JSON.stringify({calls, assigned}));
  } catch (error) { console.error(error); process.exitCode = 1; }
});
