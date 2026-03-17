import { strict as assert } from 'node:assert';
import test from 'node:test';

import {
  LOCAL_API_BASE,
  REMOTE_API_BASE,
  resolveApiBase,
} from '../../src/frontend/assets/scripts/api/endpoints.js';

test('resolveApiBase uses same-origin default when no config exists', () => {
  global.window = {
    location: { hostname: 'tax.example', protocol: 'https:' },
  };

  const resolved = resolveApiBase();

  assert.equal(resolved, LOCAL_API_BASE);
  assert.equal(resolved, REMOTE_API_BASE);

  delete global.window;
});

test('resolveApiBase falls back to local when running on localhost', () => {
  global.window = {
    location: { hostname: 'localhost', protocol: 'http:' },
  };

  const resolved = resolveApiBase();

  assert.equal(resolved, LOCAL_API_BASE);

  delete global.window;
});

test('resolveApiBase uses explicit window override for cross-origin deployments', () => {
  global.window = {
    GREEKTAX_API_BASE: 'https://api.tax.example/api/v1',
    location: { hostname: 'tax.example', protocol: 'https:' },
  };

  const resolved = resolveApiBase();

  assert.equal(resolved, 'https://api.tax.example/api/v1');

  delete global.window;
});

test('resolveApiBase uses explicit meta override when window override is absent', () => {
  global.window = {
    document: {
      querySelector: () => ({ dataset: { apiBase: 'https://meta.tax.example/api/v1' } }),
    },
    location: { hostname: 'tax.example', protocol: 'https:' },
  };

  const resolved = resolveApiBase();

  assert.equal(resolved, 'https://meta.tax.example/api/v1');

  delete global.window;
});
