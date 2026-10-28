const assert = require('node:assert/strict');
const vm = require('node:vm');

const ACCOUNT = {id: 1, email: 'anna@example.ch', first_name: 'Anna', last_name: 'Muster'};
const EMPLOYER = {id: 1, name: 'Anna', address: 'Basel', ahv_number: '756.1234.5678.97', contact_info: 'anna@example.ch'};
const ATTACK = '<img src=x onerror=alert(1)>';
const REQUIRED = 'This field is required.';
const EMAIL_NOTE = 'Enter an email address in the form name@example.ch.';
const LOGIN_FIELDS = ['login-email', 'login-password'];
const SIGNUP_FIELDS = ['signup-first-name', 'signup-last-name', 'signup-email', 'signup-password'];
const START = ['GET /api/v1/auth/me'];
const CSRF = [...START, 'GET /api/v1/auth/csrf'];
const LOOKUP = [...START, 'GET /api/v1/employer'];
const POST = action => [...CSRF, `POST /api/v1/auth/${action}`];
const AUTH = action => [...POST(action), 'GET /api/v1/employer'];

const authCases = {
  login: {action: 'login', result: 'success'},
  'login-with-employer': {action: 'login', result: 'success'},
  'login-lookup-error': {action: 'login', result: 'lookup'},
  'login-401': {action: 'login', message: /Invalid email or password\./},
  'login-403': {action: 'login', message: /Reload the page and try again/},
  'login-422': {action: 'login', message: /<img src=x onerror=alert\(1\)>/},
  'login-500': {action: 'login', message: /try again/i},
  'login-network': {action: 'login', message: /try again/i},
  'login-timeout': {action: 'login', message: /try again/i},
  'login-csrf-failure': {action: 'login', message: /Nothing was sent/, requests: CSRF},
  'login-again-401': {action: 'login', message: /Invalid email or password\./,
    requests: [...POST('login'), 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/login']},
  'login-malformed': {action: 'login', message: /try again/i},
  register: {action: 'register', result: 'success'},
  'register-lookup-error': {action: 'register', result: 'lookup'},
  'register-409': {action: 'register', result: 'duplicate-account'},
  'register-422': {action: 'register', message: /<img src=x onerror=alert\(1\)>/},
  'register-403': {action: 'register', message: /Reload the page and try again/},
  'register-500': {action: 'register', message: /account may already have been created/, extra: /status 500/},
  'register-network': {action: 'register', message: /account may already have been created/},
  'register-timeout': {action: 'register', message: /account may already have been created/},
  'register-csrf-failure': {action: 'register', message: /Nothing was sent/, requests: CSRF},
  'register-again-409': {action: 'register', result: 'duplicate-account',
    requests: [...POST('register'), 'GET /api/v1/auth/csrf', 'POST /api/v1/auth/register']},
  'register-malformed': {action: 'register', message: /account may already have been created/}
};

function makeElements(attributes) {
  const found = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, {
    id, value: attrs.value ?? '', hidden: Object.hasOwn(attrs, 'hidden'),
    disabled: Object.hasOwn(attrs, 'disabled'), open: false, textContent: '', listeners: {},
    setAttribute(name, value) { this[name] = value; },
    addEventListener(event, callback) { this.listeners[event] = callback; },
    showModal() { this.open = true; },
    close() { this.open = false; this.listeners.close?.(); },
    set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  }]));
  return new Proxy(found, {
    get(target, id) {
      assert.ok(Object.hasOwn(target, id), `The page has no element #${String(id)}`);
      return target[id];
    }
  });
}

function makeBrowser(scenario, elements) {
  const calls = [], assigned = [], viaHistory = [];
  let releaseMe, releasePost, abortTimer;
  const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body});
  const hang = options => new Promise((_, reject) =>
    options.signal.addEventListener('abort', () => reject(new Error('timeout'))));
  const context = {
    document: {getElementById: id => elements[id]},
    window: {location: {
      replace: url => assigned.push(url), assign: url => viaHistory.push(url),
      hash: scenario.startsWith('link-') ? '#signup' : ''
    }},
    AbortController,
    setTimeout(callback, delay) {
      if ((scenario === 'me-timeout' && delay === 10000) ||
          (scenario.endsWith('-timeout') && !scenario.startsWith('me') && delay === 15000)) {
        abortTimer = callback;
        return -1;
      }
      return setTimeout(callback, delay);
    },
    clearTimeout(timer) { if (timer !== -1) clearTimeout(timer); },
    async fetch(url, options = {}) {
      calls.push({method: options.method ?? 'GET', url, headers: {...options.headers}, body: options.body ?? null});
      if (url === '/api/v1/auth/me') {
        if (scenario === 'loading') await new Promise(resolve => { releaseMe = resolve; });
        if (scenario === 'me-timeout') await hang(options);
        if (scenario === 'me-network') throw new Error('offline');
        if (['me-500', 'link-me-500'].includes(scenario)) return response(500, {detail: 'boom'});
        if (scenario === 'me-malformed') return response(200, {email: ACCOUNT.email});
        if (/^(link-)?signed-in/.test(scenario)) return response(200, {...ACCOUNT, first_name: ATTACK});
        return response(401, {detail: 'Authentication required.'});
      }
      if (url === '/api/v1/auth/csrf') {
        return scenario.endsWith('-csrf-failure')
          ? response(500, {detail: 'boom'}) : response(200, {csrf_token: 'csrf-token-1'});
      }
      if (url === '/api/v1/employer') {
        if (scenario.includes('lookup-network')) throw new Error('offline');
        if (scenario.includes('lookup-error')) return response(500, {detail: 'boom'});
        if (scenario.includes('lookup-malformed')) return response(200, {name: 'Anna'});
        if (scenario.includes('lookup-other-404')) return response(404, {detail: 'Not Found'});
        return scenario.includes('with-employer')
          ? response(200, EMPLOYER) : response(404, {detail: 'No employer is set up yet.'});
      }
      const registering = url === '/api/v1/auth/register';
      assert.ok(registering || url === '/api/v1/auth/login', url);
      assert.equal(options.method, 'POST');
      assert.equal(registering, scenario.startsWith('register'));
      if (scenario.endsWith('-duplicate')) await new Promise(resolve => { releasePost = resolve; });
      if (scenario.endsWith('-timeout')) await hang(options);
      if (scenario.endsWith('-network')) throw new Error('offline');
      if (scenario.endsWith('-malformed')) return response(registering ? 201 : 200, {email: ACCOUNT.email});
      if (scenario.endsWith('-401')) return response(401, {detail: 'Invalid email or password.'});
      if (scenario.endsWith('-403')) return response(403, {detail: 'Invalid CSRF token.'});
      if (scenario.endsWith('-409')) return response(409, {detail: 'An account already uses this email.'});
      if (scenario.endsWith('-422')) return response(422, {
        detail: registering ? ATTACK : [{loc: ['body', 'email'], msg: ATTACK}]
      });
      if (scenario.endsWith('-500')) return response(500, {detail: ATTACK});
      return response(registering ? 201 : 200, {...ACCOUNT, csrf_token: 'rotated-token'});
    }
  };
  return {
    context, calls, assigned, viaHistory,
    releaseMe: () => releaseMe(), releasePost: () => releasePost(), abort: () => abortTimer()
  };
}

async function run({scenario, elements: attributes, javascript, credentials, signup, samples}) {
  const elements = makeElements(attributes);
  const browser = makeBrowser(scenario, elements);
  const {context, calls, assigned, viaHistory} = browser;
  vm.runInNewContext(javascript, context);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await settle();
  let rules;

  // Expected values stay in each scenario; this function only applies the checks.
  const inspect = expected => {
    if (expected.requests) assert.deepEqual(calls.map(({method, url}) => `${method} ${url}`), expected.requests);
    if (expected.redirects) assert.deepEqual(assigned, expected.redirects);
    for (const [id, disabled] of Object.entries(expected.disabled ?? {})) assert.equal(elements[id].disabled, disabled, id);
    for (const [id, value] of Object.entries(expected.values ?? {})) assert.equal(elements[id].value, value, id);
    for (const [id, value] of Object.entries(expected.text ?? {})) assert.equal(elements[id].textContent, value, id);
    for (const [id, value] of Object.entries(expected.hidden ?? {})) assert.equal(elements[id].hidden, value, id);
    for (const [id, value] of Object.entries(expected.open ?? {})) assert.equal(elements[id].open, value, id);
    for (const [id, value] of Object.entries(expected.flags ?? {})) {
      if (value === null) assert.notEqual(elements[id]['aria-invalid'], 'true', id);
      else assert.equal(elements[id]['aria-invalid'], value, id);
    }
    for (const [id, patterns] of Object.entries(expected.matches ?? {})) {
      for (const pattern of [].concat(patterns)) assert.match(elements[id].textContent, pattern, id);
    }
    for (const [id, patterns] of Object.entries(expected.excludes ?? {})) {
      for (const pattern of [].concat(patterns)) assert.doesNotMatch(elements[id].textContent, pattern, id);
    }
  };
  const locked = {'login-submit': true, 'open-signup': true, 'signup-submit': true};
  const loginValues = {'login-email': credentials.email, 'login-password': credentials.password};
  const signupIds = {first_name: 'signup-first-name', last_name: 'signup-last-name', email: 'signup-email', password: 'signup-password'};
  const signupValues = Object.fromEntries(Object.entries(signupIds).map(([key, id]) => [id, signup[key]]));
  const set = (id, value) => { elements[id].value = value; assert.ok(elements[id].listeners.input, id); elements[id].listeners.input(); };
  const fill = values => { for (const [id, value] of Object.entries(values)) set(id, value); };
  const submit = form => elements[`${form}-form`].listeners.submit({preventDefault() {}});
  const open = () => elements['open-signup'].listeners.click();
  const cancel = () => elements['signup-cancel'].listeners.click();
  const blur = id => { assert.ok(elements[id].listeners.blur, id); elements[id].listeners.blur({}); };
  const met = () => ['requirement-length', 'requirement-number', 'requirement-special'].map(id => elements[id]['data-met']);
  const expectMet = expected => assert.deepEqual(met(), expected);
  const formName = action => action === 'register' ? 'signup' : 'login';

  async function authenticate(action) {
    if (action === 'register') open();
    fill(action === 'register' ? signupValues : loginValues);
    const pending = submit(formName(action));
    if (scenario === `${action}-timeout`) { await settle(); browser.abort(); }
    await pending;
    await settle();
  }

  async function duplicateSubmit(action) {
    if (action === 'register') open();
    fill(action === 'register' ? signupValues : loginValues);
    const pending = submit(formName(action));
    await settle();
    inspect({disabled: locked});
    if (action === 'register') {
      inspect({disabled: {'signup-cancel': true}});
      let prevented = false;
      elements['signup-dialog'].listeners.cancel({preventDefault() { prevented = true; }});
      assert.equal(prevented, true);
    }
    await submit(formName(action));
    browser.releasePost();
    await pending;
    await settle();
    inspect({requests: AUTH(action), redirects: ['/home']});
  }

  function inspectAuth({action, result, message, extra, requests}) {
    const form = formName(action);
    inspect({requests: requests ?? (result === 'success' || result === 'lookup' ? AUTH(action) : POST(action))});
    if (result === 'success') {
      inspect({redirects: [scenario.includes('with-employer') ? '/home' : '/home'], disabled: {[`${form}-submit`]: true}, hidden: {[`${form}-error`]: true}});
      assert.deepEqual(calls[2].headers, {
        'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': 'csrf-token-1'
      });
      assert.deepEqual(JSON.parse(calls[2].body), action === 'register' ? signup : {
        email: credentials.email, password: credentials.password
      });
      if (action === 'register') inspect({disabled: {'signup-cancel': true}});
    } else if (result === 'lookup') {
      inspect({redirects: [], hidden: {[action === 'register' ? 'signup-error' : 'account-error']: false}});
      const id = action === 'register' ? 'signup-error' : 'account-error';
      inspect({matches: {[id]: [/signed in/i, /could not load your details/i]}});
      if (action === 'register') {
        inspect({open: {'signup-dialog': true}, hidden: {'account-error': false},
          matches: {'account-error': [/signed in/i, /could not load your details/i]}});
        cancel();
        inspect({open: {'signup-dialog': false}, hidden: {'signup-error': true, 'account-error': false},
          matches: {'account-error': [/signed in/i, /could not load your details/i]}});
      }
      else inspect({matches: {'account-error': /reload/i}, excludes: {'account-error': /employer/i},
        disabled: {'login-submit': true}, hidden: {'login-error': true}});
    } else {
      inspect({redirects: [], disabled: {[`${form}-submit`]: false},
        values: action === 'register' ? signupValues : loginValues});
      if (action === 'register') inspect({open: {'signup-dialog': true}, disabled: {'signup-cancel': false}});
      if (result === 'duplicate-account') {
        inspect({matches: {'signup-email-error': [/An account already uses this email\./, /Log in/]},
          flags: {'signup-email': 'true'}, hidden: {'signup-error': true}});
      } else {
        inspect({hidden: {[`${form}-error`]: false}, matches: {[`${form}-error`]: [message, ...(extra ? [extra] : [])]}});
        if (action === 'login') inspect({excludes: {'login-error': /already been created/}});
      }
    }
  }

  if (authCases[scenario]) {
    await authenticate(authCases[scenario].action);
    if (scenario.includes('-again-')) await authenticate(authCases[scenario].action);
    inspectAuth(authCases[scenario]);
  } else if (scenario === 'login-duplicate' || scenario === 'register-duplicate') {
    await duplicateSubmit(scenario.startsWith('register') ? 'register' : 'login');
  } else if (/^(link-)?signed-in/.test(scenario)) {
    inspect({requests: LOOKUP, disabled: locked, open: {'signup-dialog': false}});
    if (scenario.includes('lookup-')) inspect({redirects: [], hidden: {'account-error': false},
      matches: {'account-error': [/reload/i, /could not load your details/]},
      excludes: {'account-error': /employer/i}});
    else inspect({redirects: [scenario.includes('with-employer') ? '/home' : '/home']});
  } else if (scenario === 'loading') {
    inspect({disabled: locked, matches: {'account-status': /Checking/}});
    fill(loginValues);
    await submit('login');
    inspect({requests: START});
    browser.releaseMe();
    await settle();
    inspect({disabled: {'login-submit': false, 'open-signup': false}});
  } else if (scenario.startsWith('me-')) {
    if (scenario === 'me-timeout') { browser.abort(); await settle(); }
    inspect({requests: START, hidden: {'account-error': false}, matches: {'account-error': /reload/i}, disabled: locked});
    fill(loginValues);
    await submit('login');
    inspect({requests: START});
  } else if (scenario === 'signed-out') {
    inspect({requests: START, redirects: [], hidden: {'login-panel': false, 'account-error': true},
      text: {'account-status': ''}, disabled: {'login-submit': false, 'open-signup': false},
      open: {'signup-dialog': false}});
  } else if (scenario === 'rules') {
    rules = {passwords: samples.passwords.map(password => context.passwordRules(password).every(Boolean)),
      emails: samples.emails.map(email => context.isEmailAddress(email))};
  } else if (scenario === 'login-empty') {
    await submit('login');
    inspect({requests: START, text: {'login-email-error': REQUIRED, 'login-password-error': REQUIRED},
      flags: {'login-email': 'true', 'login-password': 'true'}});
    set('login-email', credentials.email);
    inspect({text: {'login-email-error': '', 'login-password-error': REQUIRED}, flags: {'login-email': 'false'}});
  } else if (scenario === 'login-invalid-email') {
    set('login-email', 'asdasd'); set('login-password', credentials.password);
    await submit('login');
    inspect({requests: START, text: {'login-email-error': EMAIL_NOTE, 'login-password-error': ''},
      flags: {'login-email': 'true'}});
    set('login-email', credentials.email);
    inspect({text: {'login-email-error': ''}});
  } else if (scenario === 'link-signup' || scenario === 'signup-open') {
    if (scenario === 'signup-open') open();
    inspect({requests: START, open: {'signup-dialog': true}, values: Object.fromEntries(SIGNUP_FIELDS.map(id => [id, '']))});
    if (scenario === 'link-signup') {
      inspect({disabled: {'signup-submit': false, 'signup-cancel': false}});
      cancel();
      inspect({open: {'signup-dialog': false}, disabled: {'login-submit': false}});
    }
  } else if (scenario === 'link-me-500') {
    inspect({requests: START, open: {'signup-dialog': false}, disabled: {'signup-submit': true}});
  } else if (scenario === 'signup-empty') {
    open(); await submit('signup');
    inspect({requests: START, open: {'signup-dialog': true},
      text: Object.fromEntries(SIGNUP_FIELDS.map(id => [`${id}-error`, REQUIRED])),
      flags: Object.fromEntries(SIGNUP_FIELDS.map(id => [id, 'true']))});
    set('signup-password', signup.password);
    inspect({text: {'signup-password-error': '', 'signup-email-error': REQUIRED}});
  } else if (scenario === 'signup-invalid') {
    open(); set('signup-first-name', 'a'); set('signup-email', 'asdasd'); set('signup-password', 'abc');
    await submit('signup');
    inspect({requests: START, open: {'signup-dialog': true},
      text: {'signup-first-name-error': '', 'signup-last-name-error': REQUIRED,
        'signup-email-error': EMAIL_NOTE, 'signup-password-error': ''},
      flags: {'signup-last-name': 'true', 'signup-email': 'true', 'signup-password': 'true'},
      hidden: {'signup-error': true}, disabled: {'signup-submit': false}});
    expectMet(['false', 'false', 'false']);
    set('signup-email', signup.email);
    inspect({text: {'signup-email-error': ''}, flags: {'signup-password': 'true'}});
  } else if (scenario === 'signup-cancel') {
    open(); set('signup-first-name', signup.first_name); await submit('signup');
    inspect({text: {'signup-last-name-error': REQUIRED}});
    fill(signupValues); expectMet(['true', 'true', 'true']);
    cancel(); expectMet(['false', 'false', 'false']);
    inspect({open: {'signup-dialog': false}, values: Object.fromEntries(SIGNUP_FIELDS.map(id => [id, ''])),
      text: Object.fromEntries(SIGNUP_FIELDS.map(id => [`${id}-error`, ''])),
      flags: Object.fromEntries(SIGNUP_FIELDS.map(id => [id, 'false'])), hidden: {'signup-error': true}});
    open();
    inspect({requests: START, open: {'signup-dialog': true}, values: {'signup-password': ''}});
  } else if (scenario === 'signup-password-rules') {
    open(); fill(Object.fromEntries(Object.entries(signupValues).filter(([id]) => id !== 'signup-password')));
    const needs = {abc: ['false', 'false', 'false'], abcdefgh: ['true', 'false', 'false'],
      abcdefg1: ['true', 'true', 'false'], 'abcdefg!': ['true', 'false', 'true'],
      'Abcde1!': ['false', 'true', 'true'], 'abcdefg 1': ['true', 'true', 'false'],
      'a1😀😀😀😀😀': ['false', 'true', 'true']};
    for (const [password, expected] of Object.entries(needs)) {
      set('signup-password', password); expectMet(expected); await submit('signup');
      inspect({flags: {'signup-password': 'true'}, text: {'signup-password-error': ''}});
      expectMet(expected);
    }
    set('signup-password', 'Abcdef1!');
    expectMet(['true', 'true', 'true']);
    inspect({requests: START, flags: {'signup-password': 'false'}});
  } else if (scenario === 'blur-validation') {
    const allFields = [...SIGNUP_FIELDS, ...LOGIN_FIELDS];
    const reserved = () => inspect({hidden: Object.fromEntries(allFields.map(id => [`${id}-error`, false]))});
    const field = (id, note, flag) => inspect({text: {[`${id}-error`]: note}, flags: {[id]: flag}});
    const step = (action, id, note, flag) => { action(); reserved(); field(id, note, flag); };
    reserved(); inspect({text: Object.fromEntries(allFields.map(id => [`${id}-error`, '']))});
    open(); reserved();
    step(() => set('signup-email', 'asdasd'), 'signup-email', '', null);
    step(() => blur('signup-email'), 'signup-email', EMAIL_NOTE, 'true');
    step(() => set('signup-email', ''), 'signup-email', '', 'false');
    step(() => blur('signup-email'), 'signup-email', '', null);
    step(() => set('signup-email', 'asdasd@example.ch'), 'signup-email', '', 'false');
    step(() => blur('signup-first-name'), 'signup-first-name', '', null);
    step(() => set('signup-first-name', 'Anna'), 'signup-first-name', '', null);
    step(() => blur('signup-first-name'), 'signup-first-name', '', 'false');
    set('signup-password', 'abc'); reserved(); expectMet(['false', 'false', 'false']);
    field('signup-password', '', null);
    step(() => blur('signup-password'), 'signup-password', '', 'true');
    expectMet(['false', 'false', 'false']);
    set('signup-password', 'abc12'); reserved(); expectMet(['false', 'true', 'false']);
    field('signup-password', '', 'true');
    set('signup-password', 'abc123!!'); reserved(); expectMet(['true', 'true', 'true']);
    field('signup-password', '', 'false');
    set('login-email', 'asdasd'); reserved(); blur('login-email'); reserved();
    field('login-email', EMAIL_NOTE, 'true');
    step(() => set('login-email', ''), 'login-email', '', 'false');
    step(() => blur('login-email'), 'login-email', '', null);
    step(() => blur('login-password'), 'login-password', '', null);
    inspect({text: {'signup-email-error': ''}});
    cancel(); reserved();
    inspect({requests: START, text: Object.fromEntries(SIGNUP_FIELDS.map(id => [`${id}-error`, ''])),
      flags: Object.fromEntries(SIGNUP_FIELDS.map(id => [id, 'false']))});
  } else {
    throw new Error(`No scenario plan for ${scenario}`);
  }

  assert.deepEqual(viaHistory, [], 'Redirects must use location.replace so Back does not return to /login');
  return {calls, assigned, rules};
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  try { process.stdout.write(JSON.stringify(await run(JSON.parse(input)))); }
  catch (error) { console.error(error); process.exitCode = 1; }
});
