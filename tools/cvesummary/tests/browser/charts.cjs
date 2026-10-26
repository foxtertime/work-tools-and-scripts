'use strict';
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const toolRoot = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-charts-'));
const generated = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'fixtures.py'), base], {
  cwd: toolRoot, env: { ...process.env, PYTHONPATH: toolRoot, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8',
});
assert.equal(generated.status, 0, generated.stderr);

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CVESUMMARY_CHROMIUM ? { executablePath: process.env.CVESUMMARY_CHROMIUM } : {}) });
  let checks = 0;
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/fonts.googleapis.com/**', r => r.abort());
    await page.route('**/fonts.gstatic.com/**', r => r.abort());
    await page.goto(pathToFileURL(path.join(base, 'charts.html')).href);
    const dialog = page.locator('#task-explorer');
    const column = (host, when) => page.locator(host).locator('.hl').filter({ has: page.locator(`[data-tip^="${when}:"]`) });
    const numbers = () => page.locator('#drill-body tr[data-row]').evaluateAll(nodes => nodes.map(n => +n.dataset.row).sort((a, b) => a - b));
    const close = () => page.keyboard.press('Escape');
    async function open(host, when, expected, method = 'click') {
      const col = column(host, when);
      if (method === 'click') await col.click();
      else { await col.focus(); await page.keyboard.press(method); }
      await page.waitForFunction(() => document.querySelector('#task-explorer').open, null, { timeout: 1500 });
      assert.deepEqual(await numbers(), expected);
      assert.equal(Number((await page.locator('#drill-count').innerText()).match(/\d+/)[0]), expected.length);
      assert.match(await page.locator('#drill-title').innerText(), new RegExp(when.replace('Неделя с ', '').replaceAll('.', '\\.')));
      checks++;
      return col;
    }
    const alice = '.dev:has(h3:text-is("Алиса")) .dev-tl';
    const extraRows = [15, 16, 17, 18, 19, 20, 21, 22, 23];
    await open('#weeks', 'Неделя с 12.10.2026', [4, 5, 14]); await close();
    await open('#weeks', 'Неделя с 19.10.2026', [6, 7, 8, 9, 10, ...extraRows]); await close();
    await page.locator('#inflow-by [data-by="day"]').click();
    await open('#weeks', '19.10.2026', [6, 7]); await close();
    await open('#weeks', '18.10.2026', [5, 14]); await close();
    await open('#weeks', '10.10.2026', []);
    assert.ok(await page.locator('.drill-export').isDisabled()); await close(); checks++;
    await open('#burn', 'Неделя с 12.10.2026', [3, 4, 14]); await close();
    await open('#burn', 'Неделя с 19.10.2026', [5, 6, 7, 8, ...extraRows]); await close();
    await page.locator('#burn-by [data-by="day"]').click();
    await open('#burn', '19.10.2026', [5, 7]); await close();
    await open('#burn', '20.10.2026', [8, ...extraRows]); await close();
    await open(alice, '18.10.2026', [4, 14]);
    assert.match(await page.locator('#drill-title').innerText(), /Алиса/); await close(); checks++;
    const trigger = await open(alice, '19.10.2026', [5], 'Enter'); await close();
    assert.ok(await trigger.evaluate(n => document.activeElement === n)); checks++;
    await open(alice, '21.10.2026', [6], 'Space');
    // Search and export continue to use the period's rows.
    await page.locator('#drill-search').fill('Алиса');
    const downloadPromise = page.waitForEvent('download');
    await page.locator('.drill-export').click();
    const download = await downloadPromise;
    await download.saveAs(path.join(base, 'day.csv'));
    const csv = fs.readFileSync(path.join(base, 'day.csv'), 'utf8');
    assert.match(csv, /CVE-2026-3003/);
    assert.doesNotMatch(csv, /CVE-2026-3008/); await close(); checks++;
    // Modal remains correct and focus is restored to a replacement SVG node after resize.
    await open(alice, '19.10.2026', [5]);
    const old = await column(alice, '19.10.2026').elementHandle();
    await page.setViewportSize({ width: 900, height: 850 });
    await page.waitForFunction(n => !n.isConnected, old);
    await page.waitForFunction(() => document.querySelector('.dev-tl [data-drill]'));
    await close();
    assert.equal(await page.evaluate(() => document.activeElement.dataset.tip || document.activeElement.querySelector('[data-tip]')?.dataset.tip),
      '19.10.2026: закрыто 1 · Импорт новой версии 1'); checks++;
    await page.locator('#pace-to').fill('2026-10-20'); await page.locator('#pace-to').dispatchEvent('change');
    await open('#burn', '19.10.2026', [5, 7]); await close();
    // Real mouse drag must scroll, without opening a selection on pointerup.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(350);
    const box = page.locator('#weeks .tl-scroll');
    await box.scrollIntoViewIfNeeded();
    await box.evaluate(n => { n.scrollLeft = 0; });
    const bounds = await box.boundingBox();
    await page.mouse.move(bounds.x + bounds.width - 35, bounds.y + 90);
    await page.mouse.down(); await page.mouse.move(bounds.x + 45, bounds.y + 90, { steps: 10 }); await page.mouse.up();
    assert.ok(await box.evaluate(n => n.scrollLeft > 0));
    assert.ok(!(await dialog.evaluate(n => n.open))); checks++;
    await open('#weeks', '19.10.2026', [6, 7]); await close();
    await page.locator('#inflow-by [data-by="week"]').click();
    await open('#weeks', 'Неделя с 12.10.2026', [4, 5, 14]); await close();
    assert.deepEqual(errors, []); checks++;
    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await mobile.route('**/fonts.googleapis.com/**', r => r.abort());
    await mobile.route('**/fonts.gstatic.com/**', r => r.abort());
    mobile.on('pageerror', e => errors.push(e.message));
    await mobile.goto(pathToFileURL(path.join(base, 'charts.html')).href);
    await mobile.locator('#weeks .hl').filter({ has: mobile.locator('[data-tip^="Неделя с 19.10.2026:"]') }).tap();
    assert.ok(await mobile.locator('#task-explorer').evaluate(n => n.open));
    assert.equal(await mobile.locator('#drill-body tr[data-row]').count(), 14);
    assert.deepEqual(errors, []); checks++;
    await mobile.screenshot({ path: path.join(base, 'mobile.png') });
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
