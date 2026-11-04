'use strict';
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-speed-'));
const fixture = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'speed_fixtures.py'), base], {
  cwd: root, env: { ...process.env, PYTHONPATH: root }, encoding: 'utf8',
});
assert.equal(fixture.status, 0, fixture.stderr);

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CVESUMMARY_CHROMIUM ? { executablePath: process.env.CVESUMMARY_CHROMIUM } : {}) });
  const failures = [], errors = []; let checks = 0;
  async function check(name, file, run) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', e => errors.push(e.message));
    await page.route('https://**', r => r.abort());
    try {
      await page.goto(pathToFileURL(path.join(base, file + '.html')).href);
      await run(page); checks++;
    } catch (error) { failures.push(name + ': ' + error.stack); }
    finally { await page.close(); }
  }
  const window = async (p, from, to) => {
    await p.locator('#pace-from').fill(from); await p.locator('#pace-to').fill(to);
    await p.locator('#pace-to').dispatchEvent('change');
  };
  const planValues = p => p.evaluate(() => [document.getElementById('plan-devs').value, document.getElementById('plan-rate').value]);
  try {
    await check('zero is known', 'zero', async p => {
      assert.equal(await p.locator('#hero-risk > div').filter({ hasText: /^Задач в день/ }).locator('b').innerText(), '0');
      assert.equal(await p.locator('#p-out').innerText(), '0');
      assert.equal(await p.locator('.speed .v').nth(1).innerText(), '0');
    });
    await check('weekend calendar basis', 'weekend', async p => {
      assert.equal(await p.locator('#p-out').innerText(), '0,5');
      assert.match(await p.locator('#p-out-l').innerText(), /календарный/);
      const tips = await p.locator('#hero-risk > div').filter({ hasText: /^Задач в день/ }).getAttribute('data-tip');
      assert.match(tips, /2 календарных/);
      const cells = await p.locator('#scenario-body tr').evaluateAll(rows => rows.map(r => r.children[2].textContent));
      assert.ok(cells.every(t => t.startsWith('0,5') && t.includes('календ. день')));
      assert.match(await p.locator('#scenario-body').innerText(), /календарн/);
    });
    await check('empty historical window', 'zero', async p => {
      await window(p, '2026-10-15', '2026-10-20');
      assert.match(await p.locator('#pace-sub').innerText(), /не пересекается/);
      assert.equal(await p.locator('#p-in').innerText(), '—');
      assert.equal(await p.locator('#p-out').innerText(), '—');
      assert.equal(await p.locator('#p-open').innerText(), '1');
      assert.equal(await p.locator('#forecast .d').first().innerText(), '—');
      assert.equal(await p.locator('.speed .v').nth(1).innerText(), '—');
      assert.match(await p.locator('#forecast-target').innerText(), /не пересекается/);
      assert.ok((await p.locator('#scenario-body tr').allInnerTexts()).every(t => /не пересекается/.test(t)));
      await p.locator('#pace-mode [data-by="plan"]').click();
      assert.equal(await p.locator('#forecast-plan .d').first().innerText(), '—');
      await p.locator('#pace-mode [data-by="fact"]').click();
      await window(p, '2026-11-02', '2026-11-05');
      assert.equal(await p.locator('#p-out').innerText(), '0');
      assert.doesNotMatch(await p.locator('#pace-sub').innerText(), /не пересекается/);
    });
    await check('auto versus manual plan', 'plan', async p => {
      assert.deepEqual(await planValues(p), ['1', '0.7']);
      await window(p, '2026-11-05', '2026-11-05');
      assert.deepEqual(await planValues(p), ['1', '7']);
      await p.reload();
      assert.deepEqual(await planValues(p), ['1', '7']);
      await p.locator('#pace-mode [data-by="plan"]').click();
      await p.locator('#plan-rate').fill('3.25'); await p.locator('#plan-rate').dispatchEvent('change');
      await p.locator('#pace-mode [data-by="fact"]').click();
      await window(p, '2026-10-23', '2026-11-05');
      assert.deepEqual(await planValues(p), ['1', '3.25']);
      await p.locator('#pace-mode [data-by="plan"]').click();
      assert.match(await p.locator('#pace-sub-plan').innerText(), /ручн/i);
      await p.locator('#plan-devs').fill('3'); await p.locator('#plan-devs').dispatchEvent('change');
      await p.setViewportSize({ width: 390, height: 844 });
      await p.waitForTimeout(250); await p.reload();
      assert.deepEqual(await planValues(p), ['3', '3.25']);
      await p.locator('#plan-rate').fill(''); await p.locator('#plan-rate').dispatchEvent('change');
      assert.deepEqual(await planValues(p), ['3', '0.7']);
      await p.locator('#plan-auto').click();
      assert.deepEqual(await planValues(p), ['1', '0.7']);
      assert.match(await p.locator('#pace-sub-plan').innerText(), /по текущим данным/);
      await p.reload(); assert.deepEqual(await planValues(p), ['1', '0.7']);
      await p.evaluate(() => {
        localStorage.removeItem('cve.planOverrides');
        localStorage.setItem('cve.planDevs', '99'); localStorage.setItem('cve.planRate', '99');
      });
      await p.reload(); assert.deepEqual(await planValues(p), ['1', '0.7']);
    });
    await check('draft survives resize before blur', 'plan', async p => {
      await p.locator('#pace-mode [data-by="plan"]').click();
      await p.locator('#plan-rate').fill('3.25');
      await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(300);
      assert.equal(await p.locator('#plan-rate').inputValue(), '3.25');
      await p.locator('#plan-devs').focus();
      await p.reload(); assert.equal(await p.locator('#plan-rate').inputValue(), '3.25');
    });
    await check('five idle weekdays', 'five-day', async p => {
      const card = p.locator('.dev').filter({ has: p.locator('h3', { hasText: /^X$/ }) });
      assert.match(await card.locator('.dnow').innerText(), /личный перерыв/);
      assert.equal(await card.locator('.personal-brk').count(), 1);
      assert.equal(await card.locator('.speed .v').nth(1).innerText(), '5');
      assert.match(await p.locator('#pace-note').innerText(), /Личный перерыв: 5/);
    });
    assert.deepEqual(errors, []);
    assert.equal(failures.length, 0, failures.join('\n\n'));
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
