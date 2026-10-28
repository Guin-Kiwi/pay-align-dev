const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function run(scenario) {
  const elements = new Map();
  const el = id => {
    if (!elements.has(id)) elements.set(id, {value: '', textContent: '', hidden: true, disabled: true, handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; }, reportValidity() { return true; }});
    return elements.get(id);
  };
  const redirects = [], posts = [];
  const response = (status, body) => ({status, json: async () => body});
  const context = {
    document: {getElementById: el},
    window: {location: {replace: url => redirects.push(url), assign: url => redirects.push(url)}},
    fetch: async (url, options = {}) => {
      if (url === '/api/v1/auth/csrf') return response(200, {csrf_token: 'token'});
      if (!options.method) return scenario === 'existing' ? response(200, {id: 1, name: 'Anna', address: 'Basel', ahv_number: '756.1234.5678.97', contact_info: 'anna@example.ch'}) : response(404, {detail: 'No employer is set up yet.'});
      posts.push({url, method: options.method, headers: options.headers, body: JSON.parse(options.body)});
      if (scenario === 'network') throw new Error('offline');
      if (scenario === 'invalid') return response(400, {detail: 'Employer: invalid'});
      return response(scenario === 'existing' ? 200 : 201, {id: 1});
    }
  };
  vm.runInNewContext(process.argv.slice(2).map(path => fs.readFileSync(path, 'utf8')).join('\n'), context);
  for (let i = 0; i < 20; i++) await Promise.resolve();
  if (scenario === 'existing') assert.equal(el('name').value, 'Anna');
  assert.equal(el('save').disabled, false);
  Object.assign(el('name'), {value: 'Anna'});
  Object.assign(el('address'), {value: 'Basel'});
  Object.assign(el('ahv-number'), {value: '756.1234.5678.97'});
  Object.assign(el('contact-info'), {value: 'anna@example.ch'});
  await el('employer-form').handlers.submit({preventDefault() {}});
  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, '/api/v1/employer');
  assert.equal(posts[0].method, scenario === 'existing' ? 'PUT' : 'POST');
  assert.equal(posts[0].headers['X-CSRF-Token'], 'token');
  assert.deepEqual(posts[0].body, {name: 'Anna', address: 'Basel', ahv_number: '756.1234.5678.97', contact_info: 'anna@example.ch'});
  if (scenario === 'success' || scenario === 'existing') assert.deepEqual(redirects, ['/home']);
  if (scenario === 'invalid') { assert.match(el('error').textContent, /invalid/); assert.equal(el('save').disabled, false); }
  if (scenario === 'network') {
    assert.match(el('error').textContent, /could not be confirmed/i);
    assert.equal(el('save').disabled, true);
    await el('employer-form').handlers.submit({preventDefault() {}});
    assert.equal(posts.length, 1);
  }
}

(async () => { for (const scenario of ['success', 'existing', 'invalid', 'network']) await run(scenario); })().catch(error => { console.error(error); process.exitCode = 1; });
