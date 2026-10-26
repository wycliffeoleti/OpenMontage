const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

test('Poppins loads all five original weights from real bundled WOFF2 files, with no remote URLs', async () => {
  const faces = [];
  const fontDir = path.resolve(__dirname, '../src/lib');
  const source = fs.readFileSync(path.join(fontDir, 'localFonts.ts'), 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true}}).outputText;
  const exports = {};
  const context = {
    exports, queueMicrotask,
    require: (id) => {
      if (id === 'remotion') return {delayRender: () => 1, continueRender: () => {}, cancelRender: (err) => {throw err;}};
      const local = path.resolve(fontDir, id);
      assert.equal(fs.readFileSync(local).subarray(0, 4).toString(), 'wOF2');
      return '/bundled/' + path.basename(local);
    },
    FontFace: class {
      constructor(family, url, options) { this.family = family; this.url = url; this.options = options; }
      load() { faces.push(this); return Promise.resolve(this); }
    },
    document: {fonts: {add: () => {}}},
  };
  vm.runInNewContext(js, context);
  assert.equal(typeof exports.loadPoppins, 'function', 'bundled Poppins loader must exist');
  assert.equal(exports.loadPoppins(['400', '500', '600', '700', '800']).fontFamily, 'Poppins');
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(faces.map((f) => f.options.weight), ['400', '500', '600', '700', '800']);
  for (const face of faces) {
    assert.equal(face.family, 'Poppins');
    assert.equal(face.options.style, 'normal');
    assert.match(face.url, /^url\(\/bundled\/Poppins-(400|500|600|700|800)-latin\.woff2\) format\('woff2'\)$/);
  }
});
