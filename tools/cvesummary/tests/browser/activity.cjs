'use strict';
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-activity-'));
const fixture = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'activity_fixtures.py'), base], {
  cwd: root, env: { ...process.env, PYTHONPATH: root }, encoding: 'utf8',
});
assert.equal(fixture.status, 0, fixture.stderr);

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CVESUMMARY_CHROMIUM ? { executablePath: process.env.CVESUMMARY_CHROMIUM } : {}) });
  let checks = 0;
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('https://**', r => r.abort());
    const card = name => page.locator('.dev').filter({ has: page.locator('h3', { hasText: name }) });
    const speed = name => card(name).locator('.speed .v').nth(1);
    async function open(name) { await page.goto(pathToFileURL(path.join(base, name + '.html')).href); }
    async function window(from, to) {
      await page.locator('#pace-from').fill(from); await page.locator('#pace-to').fill(to);
      await page.locator('#pace-to').dispatchEvent('change');
      await page.waitForTimeout(60);
    }
    await open('short');
    assert.equal(await speed('Алиса').innerText(), '1,3'); checks++;
    await window('2026-11-03', '2026-11-05');
    assert.equal(await speed('Алиса').innerText(), '0'); checks++;
    await page.evaluate(() => localStorage.clear());
    await open('away');
    assert.equal(await speed('Алиса').innerText(), '5'); checks++;
    assert.match(await card('Алиса').locator('.dnow').innerText(), /перерыв/i);
    assert.match(await page.locator('#pace-sub').innerText(), /прогноз: 2 из 3.*2 задач/i); checks++;
    const own = card('Алиса').locator('.personal-brk');
    assert.equal(await own.count(), 1);
    assert.equal(await card('Борис').locator('.personal-brk').count(), 0);
    assert.equal(await page.locator('#weeks .personal-brk, #burn .personal-brk, #pace-chart .personal-brk').count(), 0); checks++;
    assert.equal(await own.locator('pattern').getAttribute('patternTransform'), 'rotate(-45)');
    assert.equal(await own.locator('pattern rect').getAttribute('fill'), 'var(--personal-hatch)');
    assert.match(await card('Алиса').locator('.dev-break-legend').innerText(), /личный перерыв/i); checks++;
    assert.equal(await own.locator('rect[data-from]').getAttribute('data-from'), String(Date.UTC(2026, 10, 3) / 864e5)); checks++;
    const oldColor = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--personal-hatch'));
    await card('Алиса').screenshot({ path: path.join(base, 'personal-break-light.png') });
    await page.emulateMedia({ colorScheme: 'dark' });
    const darkColor = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--personal-hatch'));
    assert.notEqual(oldColor, darkColor); checks++;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    assert.equal(await own.count(), 1);
    assert.deepEqual(errors, []); checks++;
    await card('Алиса').screenshot({ path: path.join(base, 'personal-break-dark.png') });
    await window('2026-11-04', '2026-11-06');
    assert.equal(await speed('Алиса').innerText(), '—'); checks++;
    await page.evaluate(() => localStorage.clear());
    await open('returned');
    assert.equal(await speed('Алиса').innerText(), '4');
    assert.match(await page.locator('#pace-sub').innerText(), /прогноз: 3 из 3.*6 задач/i); checks++;
    await page.evaluate(() => localStorage.clear());
    await open('open');
    assert.equal(await card('Алиса').locator('.personal-brk').count(), 0);
    assert.equal(await speed('Алиса').innerText(), '0,7');
    assert.match(await page.locator('#pace-sub').innerText(), /прогноз: 3 из 3/i); checks++;
    await page.evaluate(() => localStorage.clear());
    await open('all-away');
    assert.match(await page.locator('#pace-sub').innerText(), /прогноз: 0 из 1.*0 задач/i);
    assert.equal(await page.locator('#p-open').innerText(), '1');
    await page.locator('#stop-date').fill('2026-11-11');
    await page.locator('#stop-date').dispatchEvent('change');
    assert.equal(await page.locator('#forecast .fc-cell .d').first().innerText(), 'нет закрытий');
    assert.equal(await card('Алиса').locator('.personal-brk').count(), 1);
    assert.equal(await card('Алиса').locator('.common-brk').count(), 1);
    assert.match(await card('Алиса').locator('.common-brk pattern').getAttribute('patternTransform'), /rotate\(45\)/); checks++;
    const overlap = card('Алиса');
    assert.equal(await overlap.locator('.personal-brk pattern').getAttribute('patternTransform'), 'rotate(-45)');
    assert.equal(await overlap.locator('.personal-brk rect[data-from]').getAttribute('data-from'),
      await overlap.locator('.common-brk rect[data-from]').getAttribute('data-from'));
    const labelPositions = await overlap.locator('.brk-lab').evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.textContent, n.getAttribute('y')])));
    assert.notEqual(labelPositions['перерыв'], labelPositions['личный перерыв']);
    const legend = await overlap.locator('.dev-break-legend').innerText();
    assert.match(legend, /личный перерыв/); assert.match(legend, /перерыв в работе/);
    await overlap.screenshot({ path: path.join(base, 'overlapping-breaks-dark.png') });
    await page.emulateMedia({ colorScheme: 'light' });
    await overlap.screenshot({ path: path.join(base, 'overlapping-breaks-light.png') });
    assert.equal(await page.locator('#weeks .personal-brk, #burn .personal-brk, #pace-chart .personal-brk').count(), 0); checks++;
    await page.locator('#pace-mode [data-by="plan"]').click();
    assert.ok(await page.locator('#forecast-plan').isVisible());
    assert.deepEqual(errors, []); checks++;
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
