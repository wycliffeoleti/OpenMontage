// Browser QA for setup fixtures: local requests only, deterministic seeks and real camera motion.
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const require = createRequire(new URL('../node_modules/hyperframes/package.json', import.meta.url));
const puppeteer = require('puppeteer-core');
const [url, directory] = process.argv.slice(2);
await mkdir(directory, {recursive: true});
const external = [], errors = [], responses = [];
const browser = await puppeteer.launch({
  executablePath: process.env.HYPERFRAMES_BROWSER_PATH,
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
         '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
try {
  const page = await browser.newPage();
  await page.setViewport({width: 854, height: 480, deviceScaleFactor: 1});
  await page.setRequestInterception(true);
  page.on('request', request => {
    const target = request.url();
    if (target.startsWith(url) || target.startsWith('data:') || target.startsWith('blob:')) {
      request.continue();
    } else {
      external.push(target);
      request.abort();
    }
  });
  page.on('pageerror', error => errors.push(String(error)));
  page.on('response', response => {
    if (response.status() >= 400) responses.push(`${response.status()} ${response.url()}`);
  });
  await page.goto(url, {waitUntil: 'networkidle0', timeout: 30000});
  await page.waitForFunction(() => window.__worldReady || window.__worldError, {timeout: 15000});
  const worldError = await page.evaluate(() => window.__worldError);
  if (worldError) throw new Error(worldError);
  const samples = [];
  for (const [index, time] of [0.25, 2, 3.75, 2].entries()) {
    await page.evaluate(time => {
      window.__timelines.world.pause().seek(time, false);
      window.dispatchEvent(new CustomEvent('hf-seek', {detail: {time}}));
    }, time);
    const camera = await page.evaluate(() => window.__worldGraph.camera.position.toArray());
    const bytes = await page.screenshot({path: path.join(directory, `world-${index}.png`)});
    samples.push({time, camera, sha256: createHash('sha256').update(bytes).digest('hex')});
  }
  if (external.length || errors.length || responses.length) {
    throw new Error(JSON.stringify({external, errors, responses}));
  }
  if (JSON.stringify(samples[0].camera) === JSON.stringify(samples[2].camera)) {
    throw new Error('Camera did not move');
  }
  if (samples[1].sha256 !== samples[3].sha256) throw new Error('Repeated seek was not pixel-identical');
  const report = {status: 'passed', external_requests: external, errors, samples,
                  same_time_pixels_identical: true, camera_moved: true};
  await writeFile(path.join(directory, 'offline-report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
