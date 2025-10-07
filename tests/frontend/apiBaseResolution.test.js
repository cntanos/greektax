import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function loadResolver() {
  const sourcePath = resolve(
    __dirname,
    '../../src/frontend/assets/scripts/main.js',
  );
  const source = readFileSync(sourcePath, 'utf8');

  const remoteLine = source.match(/const REMOTE_API_BASE = .*?;/);
  const localLine = source.match(/const LOCAL_API_BASE = .*?;/);
  const resolverMatch = source.match(
    /function resolveApiBase\(\) {[\s\S]*?}\n\nconst API_BASE =/,
  );

  if (!remoteLine || !localLine || !resolverMatch) {
    throw new Error('Unable to load resolveApiBase from main.js');
  }

  const resolverSource = resolverMatch[0]
    .replace(/\n\nconst API_BASE =[\s\S]*/, '\n');

  const factory = new Function(
    `${remoteLine[0]}\n${localLine[0]}\n${resolverSource}\nreturn { resolveApiBase, LOCAL_API_BASE, REMOTE_API_BASE };`,
  );

  return factory();
}

test('resolveApiBase falls back to local when running on localhost', () => {
  const { resolveApiBase, LOCAL_API_BASE, REMOTE_API_BASE } = loadResolver();

  global.window = {
    location: { hostname: 'localhost', protocol: 'http:' },
  };

  const resolved = resolveApiBase();

  assert.equal(resolved, LOCAL_API_BASE);
  assert.notEqual(resolved, REMOTE_API_BASE);

  delete global.window;
});
