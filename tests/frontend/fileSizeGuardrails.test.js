import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const guardrails = [
  { path: '../../src/frontend/assets/scripts/main.js', maxLines: 40 },
  { path: '../../src/frontend/assets/scripts/api/endpoints.js', maxLines: 120 },
  { path: '../../src/frontend/assets/scripts/charts/distribution.js', maxLines: 220 },
  { path: '../../src/frontend/assets/scripts/i18n/catalog.js', maxLines: 60 },
  { path: '../../src/frontend/assets/scripts/ui/app.js', maxLines: 5600 },
];

test('frontend script files stay within size guardrails', () => {
  guardrails.forEach(({ path, maxLines }) => {
    const source = readFileSync(resolve(__dirname, path), 'utf8');
    const lineCount = source.split('\n').length;

    assert.ok(
      lineCount <= maxLines,
      `${path} exceeded size guardrail (${lineCount} > ${maxLines})`,
    );
  });
});
