import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const htmlPath = resolve(__dirname, '../../src/frontend/index.html');
const entrypointPath = resolve(__dirname, '../../src/frontend/assets/scripts/main.js');
const appPath = resolve(__dirname, '../../src/frontend/assets/scripts/ui/app.js');

test('index declares Plotly with pinned SRI and crossorigin', () => {
  const html = readFileSync(htmlPath, 'utf8');
  const plotlyScriptPattern = /<script\s+[^>]*src="https:\/\/cdn\.plot\.ly\/plotly-2\.35\.3\.min\.js"[^>]*>/;
  const match = html.match(plotlyScriptPattern);

  assert.ok(match, 'Expected a static Plotly script tag in index.html');
  const tag = match[0];

  assert.match(
    tag,
    /integrity="sha384-MqL7Cy3itNqCI1Wlc926K0XhyRKJ\/NMqTaytIIEB\+QIdInOploxqRIHRKLlhPykM"/,
    'Expected Plotly script tag to include the pinned SHA-384 integrity hash',
  );
  assert.match(
    tag,
    /crossorigin="anonymous"/,
    'Expected Plotly script tag to include crossorigin="anonymous"',
  );
});

test('runtime scripts do not dynamically inject Plotly script URLs', () => {
  const sources = [readFileSync(entrypointPath, 'utf8'), readFileSync(appPath, 'utf8')];

  sources.forEach((source) => {
    assert.equal(
      source.includes('cdn.plot.ly/plotly-2.35.3.min.js'),
      false,
      'Runtime script source should not be hardcoded in runtime modules',
    );
    assert.equal(
      source.includes('data-plotly-sdk'),
      false,
      'Runtime modules should not use marker attributes for dynamic Plotly injection',
    );
  });
});
