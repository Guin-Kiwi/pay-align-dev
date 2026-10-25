const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  try {
    const {scenario, elements: attributes, javascript, credentials, signup, samples} = JSON.parse(input);
    const found = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, {
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
    const elements = new Proxy(found, {
      get(target, id) { assert.ok(Object.hasOwn(target, id), `The page has no element #${String(id)}`); return target[id]; }
    });
    const account = {id: 1, email: 'anna@example.ch', first_name: 'Anna', last_name: 'Muster'};
    const attack = '<img src=x onerror=alert(1)>';
    const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body});
    const calls = [];
    const assigned = [];
    let releaseMe, releasePost, abortTimer, rules;
    const context = {
      document: {getElementById: id => { assert.ok(elements[id], id); return elements[id]; }},
      window: {location: {assign: url => assigned.push(url), hash: scenario.startsWith('link-') ? '#signup' : ''}},
      AbortController,
      setTimeout: (callback, delay) => {
        if (scenario === 'me-timeout' && delay === 10000) { abortTimer = callback; return -1; }
        if (scenario.endsWith('-timeout') && !scenario.startsWith('me') && delay === 15000) { abortTimer = callback; return -1; }
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
          if (scenario === 'me-500' || scenario === 'link-me-500') return response(500, {detail: 'boom'});
          if (scenario === 'me-malformed') return response(200, {email: 'anna@example.ch'});
          if (scenario === 'signed-in' || scenario === 'link-signed-in') return response(200, {...account, first_name: attack});
          return response(401, {detail: 'Authentication required.'});
        }
        if (url === '/api/v1/auth/csrf') {
          if (scenario.endsWith('-csrf-failure')) return response(500, {detail: 'boom'});
          return response(200, {csrf_token: 'csrf-token-1'});
        }
        const registering = url === '/api/v1/auth/register';
        assert.ok(registering || url === '/api/v1/auth/login', url);
        assert.equal(options.method, 'POST');
        assert.equal(registering, scenario.startsWith('register'));
        if (scenario.endsWith('-duplicate')) await new Promise(resolve => releasePost = resolve);
        if (scenario.endsWith('-timeout')) await hang();
        if (scenario.endsWith('-network')) throw new Error('offline');
        if (scenario.endsWith('-malformed')) return response(registering ? 201 : 200, {email: 'anna@example.ch'});
        if (scenario.endsWith('-401')) return response(401, {detail: 'Invalid email or password.'});
        if (scenario.endsWith('-403')) return response(403, {detail: 'Invalid CSRF token.'});
        if (scenario.endsWith('-409')) return response(409, {detail: 'An account already uses this email.'});
        if (scenario.endsWith('-422')) {
          return response(422, {detail: registering ? attack : [{loc: ['body', 'email'], msg: attack}]});
        }
        if (scenario.endsWith('-500')) return response(500, {detail: attack});
        return response(registering ? 201 : 200, {...account, csrf_token: 'rotated-token'});
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
    const signupIds = {
      first_name: 'signup-first-name', last_name: 'signup-last-name',
      email: 'signup-email', password: 'signup-password'
    };
    const met = () => ['requirement-length', 'requirement-number', 'requirement-special'].map(id => elements[id]['data-met']);
    const blur = id => { assert.ok(elements[id].listeners.blur, `${id} has no blur handler`); elements[id].listeners.blur({}); };
    const openSignup = () => elements['open-signup'].listeners.click();
    const submitSignup = () => elements['signup-form'].listeners.submit({preventDefault() {}});
    const fillSignup = () => { for (const [key, id] of Object.entries(signupIds)) set(id, signup[key]); };
    const lockedControls = () => {
      for (const id of ['login-submit', 'open-signup', 'signup-submit']) assert.equal(elements[id].disabled, true, id);
    };

    if (scenario === 'loading') {
      lockedControls();
      assert.match(elements['account-status'].textContent, /Checking/);
      fill(); await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      releaseMe(); await settle();
      assert.equal(elements['login-submit'].disabled, false);
      assert.equal(elements['open-signup'].disabled, false);
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
      lockedControls();
      fill(); await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'signed-out') {
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signed-in'].hidden, true);
      assert.equal(elements['login-panel'].hidden, false);
      assert.equal(elements['account-error'].hidden, true);
      assert.equal(elements['account-status'].textContent, '');
      assert.equal(elements['login-submit'].disabled, false);
      assert.equal(elements['open-signup'].disabled, false);
      assert.equal(elements['signup-dialog'].open, false);
      assert.deepEqual(assigned, []);
    } else if (scenario === 'login-empty') {
      await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      for (const id of ['login-email', 'login-password']) {
        assert.equal(elements[`${id}-error`].textContent, 'This field is required.');
        assert.equal(elements[id]['aria-invalid'], 'true');
      }
      set('login-email', credentials.email);
      assert.equal(elements['login-email-error'].textContent, '');
      assert.equal(elements['login-email']['aria-invalid'], 'false');
      assert.equal(elements['login-password-error'].textContent, 'This field is required.');
    } else if (scenario === 'login-duplicate') {
      fill();
      const pending = submitLogin();
      await settle();
      lockedControls();
      await submitLogin();
      releasePost(); await pending; await settle();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/login']);
      assert.deepEqual(assigned, ['/setup']);
    } else if (scenario === 'rules') {
      rules = {
        passwords: samples.passwords.map(password => context.passwordRules(password).every(Boolean)),
        emails: samples.emails.map(email => context.isEmailAddress(email))
      };
    } else if (scenario === 'login-invalid-email') {
      set('login-email', 'asdasd'); set('login-password', credentials.password);
      await submitLogin();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['login-email-error'].textContent, 'Enter an email address in the form name@example.ch.');
      assert.equal(elements['login-email']['aria-invalid'], 'true');
      assert.equal(elements['login-password-error'].textContent, '');
      set('login-email', credentials.email);
      assert.equal(elements['login-email-error'].textContent, '');
    } else if (scenario === 'signup-invalid') {
      openSignup();
      set('signup-first-name', 'a'); set('signup-email', 'asdasd'); set('signup-password', 'abc');
      await submitSignup();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signup-dialog'].open, true);
      assert.equal(elements['signup-first-name-error'].textContent, '');
      assert.equal(elements['signup-last-name-error'].textContent, 'This field is required.');
      assert.equal(elements['signup-email-error'].textContent, 'Enter an email address in the form name@example.ch.');
      assert.equal(elements['signup-password-error'].textContent, '');
      assert.deepEqual(met(), ['false', 'false', 'false']);
      for (const id of ['signup-last-name', 'signup-email', 'signup-password']) {
        assert.equal(elements[id]['aria-invalid'], 'true', id);
      }
      assert.equal(elements['signup-error'].hidden, true);
      assert.equal(elements['signup-submit'].disabled, false);
      set('signup-email', signup.email);
      assert.equal(elements['signup-email-error'].textContent, '');
      assert.equal(elements['signup-password']['aria-invalid'], 'true');
    } else if (scenario === 'signup-password-rules') {
      openSignup();
      set('signup-first-name', signup.first_name); set('signup-last-name', signup.last_name); set('signup-email', signup.email);
      const needs = {
        abc: ['false', 'false', 'false'],
        abcdefgh: ['true', 'false', 'false'],
        abcdefg1: ['true', 'true', 'false'],
        'abcdefg!': ['true', 'false', 'true'],
        'Abcde1!': ['false', 'true', 'true'],
        'abcdefg 1': ['true', 'true', 'false'],
        'a1😀😀😀😀😀': ['false', 'true', 'true']
      };
      for (const [password, expected] of Object.entries(needs)) {
        set('signup-password', password);
        assert.deepEqual(met(), expected, password);
        await submitSignup();
        assert.equal(elements['signup-password']['aria-invalid'], 'true', password);
        assert.equal(elements['signup-password-error'].textContent, '', password);
        assert.deepEqual(met(), expected, password);
      }
      set('signup-password', 'Abcdef1!');
      assert.deepEqual(met(), ['true', 'true', 'true']);
      assert.equal(elements['signup-password']['aria-invalid'], 'false');
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'blur-validation') {
      const note = id => elements[`${id}-error`].textContent;
      const flag = id => elements[id]['aria-invalid'];
      const fieldIds = [...Object.values(signupIds), 'login-email', 'login-password'];
      const reserved = () => {
        for (const id of fieldIds) {
          assert.equal(elements[`${id}-error`].hidden, false, `${id}: the space for the note is never display:none`);
        }
      };
      const act = step => { step(); reserved(); };
      reserved();
      for (const id of fieldIds) assert.equal(note(id), '', id);
      act(() => openSignup());
      act(() => set('signup-email', 'asdasd'));
      assert.equal(note('signup-email'), '');
      assert.notEqual(flag('signup-email'), 'true');
      act(() => blur('signup-email'));
      assert.equal(note('signup-email'), 'Enter an email address in the form name@example.ch.');
      assert.equal(flag('signup-email'), 'true');
      act(() => set('signup-email', 'asdasd@example.ch'));
      assert.equal(note('signup-email'), '');
      assert.equal(flag('signup-email'), 'false');
      act(() => blur('signup-first-name'));
      assert.equal(note('signup-first-name'), 'This field is required.');
      assert.equal(flag('signup-first-name'), 'true');
      act(() => set('signup-first-name', 'Anna'));
      assert.equal(note('signup-first-name'), '');
      act(() => blur('signup-first-name'));
      assert.equal(note('signup-first-name'), '');
      assert.equal(flag('signup-first-name'), 'false');
      act(() => set('signup-password', 'abc'));
      assert.deepEqual(met(), ['false', 'false', 'false']);
      assert.notEqual(flag('signup-password'), 'true');
      act(() => blur('signup-password'));
      assert.equal(flag('signup-password'), 'true');
      assert.equal(note('signup-password'), '');
      assert.deepEqual(met(), ['false', 'false', 'false']);
      act(() => set('signup-password', 'abc12'));
      assert.deepEqual(met(), ['false', 'true', 'false']);
      assert.equal(flag('signup-password'), 'true');
      act(() => set('signup-password', 'abc123!!'));
      assert.deepEqual(met(), ['true', 'true', 'true']);
      assert.equal(flag('signup-password'), 'false');
      act(() => set('login-email', 'asdasd'));
      act(() => blur('login-email'));
      assert.equal(note('login-email'), 'Enter an email address in the form name@example.ch.');
      act(() => blur('login-password'));
      assert.equal(note('login-password'), 'This field is required.');
      assert.equal(note('signup-email'), '');
      act(() => elements['signup-cancel'].listeners.click());
      for (const id of Object.values(signupIds)) {
        assert.equal(note(id), '', id);
        assert.equal(flag(id), 'false', id);
      }
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'link-signup') {
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signup-dialog'].open, true);
      assert.equal(elements['signup-submit'].disabled, false);
      assert.equal(elements['signup-cancel'].disabled, false);
      for (const id of Object.values(signupIds)) assert.equal(elements[id].value, '', id);
      elements['signup-cancel'].listeners.click();
      assert.equal(elements['signup-dialog'].open, false);
      assert.equal(elements['login-submit'].disabled, false);
    } else if (scenario === 'link-signed-in' || scenario === 'link-me-500') {
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signup-dialog'].open, false);
      assert.equal(elements['signup-submit'].disabled, true);
    } else if (scenario === 'signup-open') {
      openSignup();
      assert.equal(elements['signup-dialog'].open, true);
      for (const id of Object.values(signupIds)) assert.equal(elements[id].value, '', id);
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'signup-cancel') {
      openSignup();
      set('signup-first-name', signup.first_name);
      await submitSignup();
      assert.equal(elements['signup-last-name-error'].textContent, 'This field is required.');
      fillSignup();
      assert.deepEqual(met(), ['true', 'true', 'true']);
      elements['signup-cancel'].listeners.click();
      assert.equal(elements['signup-dialog'].open, false);
      assert.deepEqual(met(), ['false', 'false', 'false']);
      for (const id of Object.values(signupIds)) {
        assert.equal(elements[id].value, '', id);
        assert.equal(elements[`${id}-error`].textContent, '', id);
        assert.equal(elements[id]['aria-invalid'], 'false', id);
      }
      assert.equal(elements['signup-error'].hidden, true);
      openSignup();
      assert.equal(elements['signup-dialog'].open, true);
      assert.equal(elements['signup-password'].value, '');
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
    } else if (scenario === 'signup-empty') {
      openSignup();
      await submitSignup();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me']);
      assert.equal(elements['signup-dialog'].open, true);
      for (const id of Object.values(signupIds)) {
        assert.equal(elements[`${id}-error`].textContent, 'This field is required.');
        assert.equal(elements[id]['aria-invalid'], 'true');
      }
      set('signup-password', signup.password);
      assert.equal(elements['signup-password-error'].textContent, '');
      assert.equal(elements['signup-email-error'].textContent, 'This field is required.');
    } else if (scenario === 'register-duplicate') {
      openSignup(); fillSignup();
      const pending = submitSignup();
      await settle();
      lockedControls();
      assert.equal(elements['signup-cancel'].disabled, true);
      let prevented = false;
      elements['signup-dialog'].listeners.cancel({preventDefault() { prevented = true; }});
      assert.equal(prevented, true);
      await submitSignup();
      releasePost(); await pending; await settle();
      assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/register']);
      assert.deepEqual(assigned, ['/setup']);
    } else if (scenario.startsWith('register')) {
      openSignup(); fillSignup();
      const pending = submitSignup();
      if (scenario === 'register-timeout') { await settle(); abortTimer(); }
      await pending; await settle();
      if (scenario === 'register') {
        assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/register']);
        assert.deepEqual(calls[2].headers, {
          'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': 'csrf-token-1'
        });
        assert.deepEqual(JSON.parse(calls[2].body), signup);
        assert.deepEqual(assigned, ['/setup']);
        assert.equal(elements['signup-submit'].disabled, true);
        assert.equal(elements['signup-cancel'].disabled, true);
        assert.equal(elements['signup-error'].hidden, true);
      } else {
        assert.deepEqual(assigned, []);
        assert.equal(elements['signup-dialog'].open, true);
        assert.equal(elements['signup-submit'].disabled, false);
        assert.equal(elements['signup-cancel'].disabled, false);
        for (const [key, id] of Object.entries(signupIds)) assert.equal(elements[id].value, signup[key], id);
        const unsure = /account may already have been created/;
        if (scenario === 'register-409') {
          assert.match(elements['signup-email-error'].textContent, /An account already uses this email\./);
          assert.match(elements['signup-email-error'].textContent, /Log in/);
          assert.equal(elements['signup-email']['aria-invalid'], 'true');
          assert.equal(elements['signup-error'].hidden, true);
        } else {
          assert.equal(elements['signup-error'].hidden, false);
          const expected = {
            'register-422': new RegExp(escaped(attack)),
            'register-403': /Reload the page and try again/,
            'register-500': unsure,
            'register-network': unsure,
            'register-timeout': unsure,
            'register-malformed': unsure,
            'register-csrf-failure': /Nothing was sent/
          }[scenario];
          assert.match(elements['signup-error'].textContent, expected);
          if (scenario === 'register-500') assert.match(elements['signup-error'].textContent, /status 500/);
          if (scenario === 'register-csrf-failure') {
            assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf']);
          }
        }
      }
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
          'login-422': new RegExp(escaped(attack)),
          'login-500': /try again/i,
          'login-network': /try again/i,
          'login-timeout': /try again/i,
          'login-csrf-failure': /Nothing was sent/,
          'login-malformed': /try again/i
        }[scenario];
        assert.match(elements['login-error'].textContent, expected);
        assert.doesNotMatch(elements['login-error'].textContent, /already been created/);
        if (scenario === 'login-csrf-failure') {
          assert.deepEqual(urls(), ['GET /api/v1/auth/me', 'GET /api/v1/auth/csrf']);
        }
      }
    }
    process.stdout.write(JSON.stringify({calls, assigned, rules}));
  } catch (error) { console.error(error); process.exitCode = 1; }
});
