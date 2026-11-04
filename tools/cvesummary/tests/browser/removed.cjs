'use strict';
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-removed-'));
const fixture = spawnSync('python3', [path.join(__dirname, 'removed_fixtures.py'), base], {
  cwd: root, env: { ...process.env, PYTHONPATH: root }, encoding: 'utf8',
});
assert.equal(fixture.status, 0, fixture.stderr);
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CVESUMMARY_CHROMIUM || '/usr/bin/google-chrome' });
  const failures = [], errors = []; let checks = 0;
  async function check(name, file, run) {
    const p = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    p.setDefaultTimeout(4000);
    p.on('pageerror', e => errors.push(e.message));
    await p.route('https://**', r => r.abort());
    try { await p.goto(pathToFileURL(path.join(base, file + '.html')).href); await run(p); checks++; }
    catch (e) { failures.push(name + ': ' + e.stack); }
    finally { await p.close(); }
  }
  const parts = locator => locator.evaluateAll(nodes => nodes.map(n => [n.dataset.segment, Number(n.style.flexGrow || n.dataset.count)]));
  async function list(p, loc, expected, keyboard = false) {
    if (keyboard) { await loc.focus(); await loc.press('Enter'); } else await loc.click();
    await p.locator('#task-explorer').waitFor({ state: 'visible' });
    const ids = await p.locator('#task-explorer tbody tr').evaluateAll(trs => trs.map(tr => Number(tr.firstElementChild.textContent)).sort((a, b) => a - b));
    assert.deepEqual(ids, expected);
    await p.locator('.drill-close').click();
  }
  const card = p => p.locator('.dev').filter({ has: p.locator('h3', { hasText: /^X$/ }) });
  try {
    await check('ten-task bars and exact lists', 'ten', async p => {
      assert.deepEqual(await parts(p.locator('#hero-bar > span')), [['removed', 2], ['done', 6], ['none', 2]]);
      assert.deepEqual(await parts(card(p).locator('.pbar > span')), [['removed', 2], ['done', 6], ['work', 2]]);
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '2');
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '6');
      assert.equal(await p.locator('#hero-state .removed-subset').count(), 0);
      const headerTips = await p.locator('#hero-groups [data-tip], #hero-bar [data-tip]').evaluateAll(nodes => nodes.map(n => n.dataset.tip));
      assert.ok(headerTips.every(t => !t.includes('без убранных')));
      assert.doesNotMatch(await p.locator('#hero-groups').innerText(), /без убранных/);
      assert.equal(await p.locator('#p-open').innerText(), '2');
      assert.equal(await p.locator('#p-out').innerText(), '2');
      assert.equal(await card(p).locator('.dstat [data-role="done"] > b').innerText(), '8');
      await list(p, p.locator('#hero-bar [data-segment="removed"]'), [8, 9], true);
      await list(p, p.locator('#hero-bar [data-segment="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-state [data-role="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [8, 9], true);
      await list(p, card(p).locator('.pbar [data-segment="removed"]'), [8, 9]);
      await list(p, card(p).locator('.dstat [data-role="done"]'), [2, 3, 4, 5, 6, 7, 8, 9]);
      await list(p, card(p).locator('.removed-subset'), [8, 9], true);
      await list(p, card(p).locator('.pbar [data-segment="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-groups [data-group="done"] .cap'), [2, 3, 4, 5, 6, 7]);
      await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(250);
      await list(p, p.locator('#hero-bar [data-segment="removed"]'), [8, 9]);
      await p.screenshot({ path: path.join(base, 'ten-mobile.png'), fullPage: true });
    });
    await check('mixed role counters, triage, forecast and closure dates', 'mixed', async p => {
      const graphite = p.locator('#hero-bar [data-segment="removed"]');
      assert.equal(await graphite.evaluate(n => n.style.getPropertyValue('--triaged')), '80%');
      assert.match(await graphite.getAttribute('data-tip'), /закрыто 2.*открыто 3/);
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '5');
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '1');
      assert.equal(await p.locator('#hero-state [data-role="work"] > b').innerText(), '1');
      assert.equal(await p.locator('#hero-state [data-role="none"] > b').innerText(), '0');
      assert.equal(await p.locator('#hero-state > div > b').evaluateAll(nodes => nodes.reduce((n, el) => n + Number(el.textContent), 0)), 7);
      assert.equal(await p.locator('#p-open').innerText(), '4');
      assert.equal(await p.locator('#p-out').innerText(), '0,5');
      assert.match(await p.locator('#pace-note').innerText(), /Убрано из эпика/);
      await list(p, p.locator('#hero-state [data-role="work"]'), [7]);
      await list(p, p.locator('#hero-state [data-role="done"]'), [8]);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [2, 3, 4, 5, 6]);
      await list(p, card(p).locator('.dstat [data-role="work"] .removed-subset'), [4]);
      await list(p, p.locator('#close-sub b'), [4]);
      await list(p, graphite, [2, 3, 4, 5, 6]);
      for (const theme of ['light', 'dark']) {
        await p.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
        const colors = await graphite.evaluate(n => ({ bg: getComputedStyle(n).backgroundColor, fg: getComputedStyle(n).color,
          hatch: getComputedStyle(n, '::before').backgroundImage }));
        assert.equal(colors.fg, 'rgb(255, 255, 255)'); assert.match(colors.hatch, /255, 255, 255/);
        await p.screenshot({ path: path.join(base, 'mixed-' + theme + '.png'), fullPage: true });
      }
    });
    await check('only removed data renders', 'only', async p => {
      assert.deepEqual(await parts(p.locator('#hero-bar > span')), [['removed', 2]]);
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '0');
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '2');
      assert.equal(await p.locator('#p-open').innerText(), '1');
      await list(p, p.locator('#hero-groups [data-group="removed"] .cap'), [2, 3]);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [2, 3]);
    });
    await check('invalid SecOps End never invents a dated closure or chart selection', 'invalid-end', async p => {
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '0');
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '1');
      assert.equal(await p.locator('#p-open').innerText(), '1');
      await p.locator('#pace-from').fill('2026-03-02');
      await p.locator('#pace-to').fill('2026-03-05');
      await p.locator('#pace-to').dispatchEvent('change');
      assert.equal(await p.locator('#p-out').innerText(), '0');
      await p.locator('#burn-by [data-by="day"]').click();
      const col = p.locator('#burn [data-chart-day]').filter({ has: p.locator('[data-tip^="02.03.2026:"]') });
      assert.match(await col.getAttribute('aria-label'), /0 строк/);
      assert.match(await col.locator('[data-tip]').getAttribute('data-tip'), /закрыто 0/);
      await col.click();
      assert.match(await p.locator('#drill-count').innerText(), /^0 строк/);
      await p.locator('.drill-close').click();
      const secops = p.locator('.dev').filter({ has: p.locator('h3', { hasText: /^SecOps$/ }) });
      assert.equal(await secops.locator('.dev-tl .bar-day').count(), 0);
    });
    await check('unique representatives and AI include removed pairs', 'pairs', async p => {
      assert.equal(await p.locator('#k-total').innerText(), '4');
      assert.equal(await p.locator('#k-cve').innerText(), '2');
      await list(p, p.locator('#k-cve'), [3, 4]);
      assert.equal(await p.locator('#close-sub b').innerText(), '0');
      await list(p, p.locator('#hero-bar [data-segment="removed"]'), [2, 4, 5]);
      // AI has its own newest-verdict representative, independent of ordinary duplicate selection.
      await list(p, p.locator('#aistrip [data-drill]').first(), [5]);
      await list(p, p.locator('#aistrip [data-drill]').last(), [2]);
      const csv = await p.evaluate(() => window.CS.drilldown.csv(JSON.parse(document.getElementById('data').textContent).rows));
      assert.match(csv, /Убрано из эпика/);
    });
    assert.deepEqual(errors, []);
    assert.equal(failures.length, 0, failures.join('\n\n'));
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
