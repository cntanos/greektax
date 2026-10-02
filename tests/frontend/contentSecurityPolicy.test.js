import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const __dirname = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(resolve(__dirname, '../../src/frontend/index.html'), 'utf8');

const metaMatch = html.match(
  /<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]+)"\s*\/?>/,
);

function directives() {
  const policy = new Map();
  for (const part of metaMatch[1].split(';')) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (name) {
      policy.set(name, values);
    }
  }
  return policy;
}

test('index.html declares a Content-Security-Policy before loading anything', () => {
  assert.ok(metaMatch, 'Expected a CSP meta tag in index.html');
  const cspIndex = html.indexOf('http-equiv="Content-Security-Policy"');
  for (const marker of ['<link', '<script']) {
    const index = html.indexOf(marker);
    assert.ok(index === -1 || cspIndex < index, `CSP must come before the first ${marker}`);
  }
});

test('the policy keeps scripts, connections and forms locked down', () => {
  const policy = directives();
  assert.deepEqual(policy.get('default-src'), ["'self'"]);
  assert.deepEqual(policy.get('script-src'), ["'self'", 'https://cdn.plot.ly']);
  // Inputs never leave the device: no fetch/XHR/beacon anywhere.
  assert.deepEqual(policy.get('connect-src'), ["'none'"]);
  assert.deepEqual(policy.get('form-action'), ["'none'"]);
  assert.deepEqual(policy.get('object-src'), ["'none'"]);
  assert.deepEqual(policy.get('base-uri'), ["'self'"]);
  for (const [name, values] of policy) {
    assert.ok(!values.includes("'unsafe-eval'"), `${name} must not allow eval`);
    if (name !== 'style-src') {
      assert.ok(!values.includes("'unsafe-inline'"), `${name} must not allow inline code`);
    }
  }
});

test('every external script in index.html is allowed by script-src', () => {
  const allowed = directives().get('script-src');
  const sources = [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(sources.length > 0);
  for (const src of sources) {
    if (src.startsWith('./') || src.startsWith('/')) {
      continue;
    }
    const origin = new URL(src).origin;
    assert.ok(allowed.includes(origin), `${src} is not allowed by script-src`);
  }
});
