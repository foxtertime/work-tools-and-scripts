'use strict';
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-calendar-'));
const fixture = spawnSync('python3', [path.join(__dirname, 'calendar_fixtures.py'), base], {
  cwd: root, env: { ...process.env, PYTHONPATH: root }, encoding: 'utf8',
});
assert.equal(fixture.status, 0, fixture.stderr);

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.CVESUMMARY_CHROMIUM ? { executablePath: process.env.CVESUMMARY_CHROMIUM } : {}) });
  const errors = []; let checks = 0;
  try {
    const p = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    p.on('pageerror', e => errors.push(e.message));
    await p.route('https://**', r => r.abort());
    const card = name => p.locator('.dev').filter({ has: p.locator('h3', { hasText: name }) });
    const speed = name => card(name).locator('.speed .v').nth(1).innerText();
    const open = async name => {
      await p.goto(pathToFileURL(path.join(base, name + '.html')).href);
      await p.evaluate(() => localStorage.clear());
      await p.reload();
    };
    await open('holiday-week');
    assert.equal(await p.locator('#p-out').innerText(), '1');
    assert.equal(await speed('Алиса'), '1');
    assert.match(await p.locator('#pace-sub').innerText(), /4 рабочих дня/);
    assert.match(await p.locator('#calendar-note').innerText(), /Календарь РФ: 2026, 2027/);
    assert.match(await p.locator('#calendar-note').innerText(), /Для остальных лет — Пн–Пт/); checks++;
    const holiday = p.locator('#pace-chart .wkend [data-date="2026-11-04"]');
    assert.equal(await holiday.count(), 1);
    assert.match(await holiday.getAttribute('data-tip'), /День народного единства/);
    await p.locator('#pace-chart rect[data-i="2"]').hover({ position: { x: 3, y: 160 } });
    assert.match(await p.locator('#tip').innerText(), /04.11.2026.*День народного единства/); checks++;
    assert.equal(await card('Алиса').locator('.wkend [data-date="2026-11-04"]').count(), 1);
    await card('Алиса').screenshot({ path: path.join(base, 'holiday-week.png') }); checks++;
    await p.setViewportSize({ width: 390, height: 844 });
    await p.emulateMedia({ colorScheme: 'dark' });
    await p.waitForTimeout(250);
    assert.equal(await speed('Алиса'), '1');
    assert.equal(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await card('Алиса').screenshot({ path: path.join(base, 'holiday-week-mobile.png') }); checks++;
    await p.setViewportSize({ width: 1440, height: 1000 });
    await p.emulateMedia({ colorScheme: 'light' });
    await open('holiday-work');
    assert.equal(await speed('Борис'), '0,5');
    assert.equal(await speed('Алиса'), '0');
    assert.equal(await p.locator('#p-out').innerText(), '1');
    const borisTip = await card('Борис').locator('.speed > div').nth(1).getAttribute('data-tip');
    assert.match(borisTip, /1 задач за 2 рабочих дней/);
    await card('Борис').screenshot({ path: path.join(base, 'holiday-work.png') }); checks++;
    await open('working-saturday');
    assert.match(await p.locator('#pace-sub').innerText(), /3 рабочих дня/);
    assert.equal(await p.locator('#pace-chart .wkend [data-date="2025-11-01"]').count(), 0);
    assert.equal(await p.locator('#pace-chart .wkend [data-date="2025-11-03"]').count(), 1); checks++;
    await open('holiday-forecast');
    await p.locator('#stop-date').fill('2026-11-04');
    await p.locator('#stop-date').dispatchEvent('change');
    assert.match(await p.locator('#forecast .fc-cell .d').first().innerText(), /05\.11/); checks++;
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
