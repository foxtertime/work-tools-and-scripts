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
    async function labels(host) {
      const results = await host.evaluate(node => {
        const plot = node.querySelector('.tl-plot'), out = [];
        for (const [kind, caption] of [['common', 'перерыв'], ['personal', 'личный перерыв']]) {
          const rects = [...plot.querySelectorAll(`.${kind}-brk rect[data-from]`)];
          const texts = [...plot.querySelectorAll('.brk-lab')].filter(t => t.textContent === caption);
          out.push({ kind, rects: rects.length, texts: texts.length, positions: rects.map((rect, i) => {
            const r = rect.getBoundingClientRect(), t = texts[i]?.getBoundingClientRect();
            const dayWidth = r.width / (Number(rect.dataset.to) - Number(rect.dataset.from) + 1);
            return { dayWidth, x: r.x, top: r.y, bottom: r.bottom,
              label: t ? { center: t.x + t.width / 2, width: t.width, height: t.height, top: t.top, bottom: t.bottom } : null };
          }) });
        }
        return out;
      });
      for (const result of results) {
        assert.equal(result.texts, result.rects, `${result.kind}: every break must have a label, including narrow breaks`);
        for (const p of result.positions) {
          assert.ok(p.label.height > p.label.width * 2, 'Break label must be vertical');
          assert.ok(p.label.center >= p.x - 1 && p.label.center <= p.x + p.dayWidth + 1, 'Label must stay in the first day of the break');
          assert.ok(p.label.top >= p.top - 2 && p.label.bottom <= p.bottom + 2, 'Vertical label must fit in the plot');
        }
      }
      checks++;
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
    await labels(card('Алиса').locator('.dev-tl'));
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
    assert.equal(await card('Алиса').locator('.personal-brk').count(), 0);
    assert.equal(await card('Алиса').locator('.common-brk').count(), 1);
    assert.match(await card('Алиса').locator('.common-brk pattern').getAttribute('patternTransform'), /rotate\(45\)/); checks++;
    const commonOnly = card('Алиса');
    const legend = await commonOnly.locator('.dev-break-legend').innerText();
    assert.doesNotMatch(legend, /личный перерыв/); assert.match(legend, /перерыв в работе/);
    for (const [width, colorScheme] of [[1440, 'light'], [390, 'dark']]) {
      await page.setViewportSize({ width, height: 1000 }); await page.emulateMedia({ colorScheme });
      await page.waitForTimeout(300);
      await labels(commonOnly.locator('.dev-tl'));
      for (const by of ['day', 'week']) {
        await page.locator(`#burn-by [data-by="${by}"]`).click(); await labels(page.locator('#burn'));
      }
      await labels(page.locator('#weeks'));
      for (const by of ['flow', 'up', 'down']) {
        await page.locator(`#pace-by [data-by="${by}"]`).click(); await labels(page.locator('#pace-chart'));
      }
      await commonOnly.screenshot({ path: path.join(base, `common-only-${width}.png`) });
    }
    assert.equal(await page.locator('#weeks .personal-brk, #burn .personal-brk, #pace-chart .personal-brk').count(), 0); checks++;
    await page.locator('#pace-mode [data-by="plan"]').click();
    assert.ok(await page.locator('#forecast-plan').isVisible());
    assert.deepEqual(errors, []); checks++;
    const D = Date.UTC(2026, 10, 2) / 864e5;
    for (const [name, day, ownRanges, rate, forecast] of [
      ['priority-common', 20, [[D + 1, D + 7]], '5', /прогноз: 0 из 2.*0 задач/],
      ['priority-fourth', 24, [[D + 1, D + 7]], '1', /прогноз: 2 из 2.*1,1 задач/],
      ['priority-fifth', 25, [[D + 1, D + 7], [D + 21, D + 25]], '5', /прогноз: 1 из 2.*0,1 задач/],
    ]) {
      await page.evaluate(() => localStorage.clear()); await open(name);
      const end = new Date((D + day) * 864e5).toISOString().slice(0, 10);
      await window('2026-11-02', end);
      assert.equal(await speed('Алиса').innerText(), rate);
      assert.match(await page.locator('#pace-sub').innerText(), forecast);
      const ranges = kind => card('Алиса').locator(`.${kind}-brk rect[data-from]`).evaluateAll(nodes => nodes.map(n => [+n.dataset.from, +n.dataset.to]));
      assert.deepEqual(await ranges('common'), [[D + 8, D + 20]]);
      assert.deepEqual(await ranges('personal'), ownRanges);
      for (const [from, to] of ownRanges) assert.ok(to < D + 8 || from > D + 20);
      await labels(card('Алиса').locator('.dev-tl'));
      await card('Алиса').screenshot({ path: path.join(base, `${name}.png`) }); checks++;
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
