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
    const ids = await p.locator('#task-explorer tbody tr[data-row]').evaluateAll(trs => trs.map(tr => Number(tr.dataset.row)).sort((a, b) => a - b));
    assert.deepEqual(ids, expected);
    await p.locator('.drill-close').click();
  }
  const card = p => p.locator('.dev').filter({ has: p.locator('h3', { hasText: /^X$/ }) });
  try {
    await check('removed rows cannot leak into pool sections, hours, AI or lists', 'scope', async p => {
      assert.equal(await p.locator('#k-total').innerText(), '2');
      assert.equal(await p.locator('#k-cve').innerText(), '2');
      assert.equal(await p.locator('#k-comp').innerText(), '1');
      assert.equal(await p.locator('#removed-count').innerText(), '4');
      assert.equal(await p.locator('#p-open').innerText(), '1');
      assert.equal(await p.locator('#p-in').innerText(), '0,5');
      assert.equal(await p.locator('#p-out').innerText(), '0,5');
      assert.equal(await p.locator('#p-net').innerText(), '+1');
      assert.equal(await p.locator('#close-sub b').innerText(), '0');
      assert.equal(await p.locator('#anom-n').innerText(), '0');
      assert.equal(await p.locator('#sevrows .k[data-key="Critical"]').count(), 0);
      assert.equal(await p.locator('#measrows .k[data-key="Убранная мера"]').count(), 0);
      assert.equal(await p.locator('#devstatus .k[data-key="Убрано из эпика"]').count(), 1);
      assert.equal(await p.locator('#components .lab').innerText(), 'kept');
      assert.equal(await p.locator('.dev').count(), 3);
      assert.equal(await p.locator('.dev-info-only').count(), 2);
      assert.equal(await card(p).locator('.big').innerText(), '2задач назначено');
      assert.equal(await card(p).locator('.speed .v').first().innerText(), '16');
      assert.equal(await p.locator('#ai-total .n').innerText(), '0');
      assert.match(await p.locator('#ai-total .s').innerText(), /из 2/);
      assert.match(await p.locator('#period').innerText(), /02\.11\.2026 — 02\.11\.2026/);
      const leaks = await p.evaluate(() => {
        const leaks = [];
        for (const node of document.querySelectorAll('[data-drill]')) {
          if (node.closest('#removed, #hero-state [data-role="removed"], #weeks [data-chart-segment="removed"], #devstatus [data-status="removed"], .dev [data-role="removed"], .dev .pbar [data-segment="removed"]')) continue;
          node.dispatchEvent(new MouseEvent('click', { bubbles: true }));
          const ids = [...document.querySelectorAll('#drill-body tr[data-row]')].map(tr => Number(tr.dataset.row));
          if (ids.some(id => id !== 2 && id !== 3)) leaks.push({ label: node.getAttribute('aria-label'), ids });
          document.querySelector('#task-explorer').close();
        }
        return leaks;
      });
      assert.deepEqual(leaks, []);
      assert.equal(await card(p).locator('.dstat [data-role="removed"] b').innerText(), '2');
      await list(p, card(p).locator('.pbar [data-segment="removed"]'), [4, 7]);
      await list(p, card(p).locator('.dstat [data-role="removed"]'), [4, 7], true);
      assert.match(await card(p).locator('.pbar [data-segment="removed"]').evaluate(n => getComputedStyle(n).backgroundImage), /repeating-linear-gradient/);
      const ghost = p.locator('.dev').filter({ has: p.locator('h3', { hasText: /^Ghost$/ }) });
      assert.equal(await ghost.locator('.big').innerText(), '0задач назначено');
      assert.equal(await ghost.locator('.speed, .dev-tl').count(), 0);
      await list(p, ghost.locator('.pbar [data-segment="removed"]'), [5]);
      assert.doesNotMatch(await p.locator('#burnleg').innerText(), /Ghost|SecOps/);
      await list(p, p.locator('#removed-count'), [4, 5, 6, 7]);
      for (const cls of ['k', 'b', 'n']) await list(p, p.locator('#devstatus > .' + cls + '[data-status="removed"]').first(), [4, 5, 6, 7]);
      assert.deepEqual(await p.locator('#devstatus > .p:not([data-status="removed"])').allTextContents(), ['50%', '50%']);
      assert.equal(await p.locator('#devstatus > .p[data-status="removed"]').innerText(), '—');
      const info = p.locator('#devstatus > [data-status="removed"]');
      assert.deepEqual(await info.allTextContents(), ['Убрано из эпика', '', '4', '—', '3', '—', '—']);
      assert.match(await p.locator('#devstatus .b[data-status="removed"] > span > span').evaluate(n => getComputedStyle(n).backgroundImage), /repeating-linear-gradient/);
      await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(250);
      await list(p, p.locator('#devstatus > .b[data-status="removed"]'), [4, 5, 6, 7], true);
      await list(p, card(p).locator('.pbar [data-segment="removed"]'), [4, 7]);
    });
    await check('inflow shows hatched removed history without changing pool calculations', 'inflow', async p => {
      const calculations = () => p.locator('#k-total, #k-cve, #k-comp, #period, #hero-risk, #p-in, #p-out, #p-net, #p-open, #pace-note').allTextContents();
      const before = await calculations();
      assert.equal(await p.locator('#k-total').innerText(), '2');
      assert.match(await p.locator('#weekleg').innerText(), /Убрано из эпика/);
      const day = date => Date.parse(date + 'T00:00:00Z') / 864e5;
      const col = date => p.locator('#weeks [data-chart-day="' + day(date) + '"]');
      for (const [mode, early, expectedPool] of [['week', '2026-10-12', [2, 3]], ['day', '2026-10-18', [2]]]) {
        await p.locator('#inflow-by [data-by="' + mode + '"]').click();
        const removed = p.locator('#weeks [data-chart-segment="removed"]');
        assert.equal(await removed.count(), 2);
        assert.equal(await removed.evaluateAll(ns => ns.reduce((sum, n) => sum + Number(n.dataset.chartCount), 0)), 3);
        const current = col('2026-11-02'), hatched = current.locator('[data-chart-segment="removed"]');
        assert.match(await hatched.getAttribute('fill'), /^url\(#/);
        const patternId = (await hatched.getAttribute('fill')).slice(5, -1);
        assert.equal(await p.locator('#' + patternId + ' rect').count(), 2);
        assert.equal(await p.locator('#' + patternId + ' rect').first().getAttribute('fill'), 'var(--st-removed)');
        assert.match(await current.locator('[data-tip]').first().getAttribute('data-tip'), new RegExp('поступило ' + expectedPool.length));
        await list(p, current, expectedPool, true);
        await list(p, hatched, [5, 6]);
        await list(p, col(early).locator('[data-chart-segment="removed"]'), [4], true);
        await list(p, col(early), [], true);
        assert.deepEqual(await calculations(), before);
      }
      await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(250);
      await list(p, col('2026-11-02').locator('[data-chart-segment="removed"]'), [5, 6]);
      await p.locator('#inflow').screenshot({ path: path.join(base, 'inflow-removed-mobile.png') });
      await p.goto(pathToFileURL(path.join(base, 'inflow-no-dates.html')).href);
      assert.deepEqual(await calculations(), before);
      assert.equal(await p.locator('#weeks [data-chart-segment="removed"]').count(), 0);
    });
    await check('removed-only inflow renders and preserves zero pool totals', 'only', async p => {
      assert.equal(await p.locator('#k-total').innerText(), '0');
      assert.equal(await p.locator('#p-in').innerText(), '0');
      const removed = p.locator('#weeks [data-chart-segment="removed"]');
      assert.equal(await removed.count(), 1);
      assert.equal(await removed.getAttribute('data-chart-count'), '2');
      await list(p, removed, [2, 3]);
      await list(p, p.locator('#weeks [data-chart-day]'), [], true);
    });
    await check('completed removed developer work remains only in speed', 'speed-only', async p => {
      assert.equal(await p.locator('#k-total').innerText(), '0');
      assert.equal(await p.locator('#k-cve').innerText(), '0');
      assert.equal(await p.locator('#p-open').innerText(), '0');
      assert.equal(await p.locator('#p-in').innerText(), '0');
      assert.equal(await p.locator('#p-out').innerText(), '0,3');
      assert.equal(await p.locator('#p-net').innerText(), '0');
      assert.equal(await p.locator('.dev').count(), 3);
      assert.equal(await card(p).locator('.big').innerText(), '0задач назначено');
      assert.equal(await card(p).locator('.speed .v').nth(1).innerText(), '0,3');
      assert.deepEqual(await parts(card(p).locator('.pbar > span')), [['removed', 1]]);
      await list(p, card(p).locator('.dstat [data-role="removed"]'), [2]);
    });
    for (const [file, done, rest] of [['mixed', [3], [2, 4, 5, 6]], ['only', [], [2, 3]], ['ten', [8, 9], []], ['ordinary', [], []], ['empty', [], []]]) {
      await check('removed block: ' + file, file, async p => {
        const expected = [...done, ...rest].sort((a, b) => a - b);
        assert.equal(await p.locator('#removed-count').innerText(), String(expected.length));
        assert.equal(await p.locator('#removed-bar > span').count(), Number(done.length > 0) + Number(rest.length > 0));
        for (const [key, label, rows, id] of [['done', 'Готово', done, 'removed-done-count'], ['removed', 'Убрано', rest, 'removed-rest-count']]) {
          assert.equal(await p.locator('#' + id).innerText(), String(rows.length));
          await list(p, p.locator('#' + id), rows);
          if (rows.length) {
            const bar = p.locator('#removed-bar > span[data-group="' + key + '"]');
            assert.equal(await bar.innerText(), String(rows.length));
            const cap = p.locator('#removed-groups .cap[data-segment="' + key + '"]');
            assert.match(await cap.innerText(), new RegExp(label));
            const groupBox = await cap.locator('..').boundingBox(), barBox = await bar.boundingBox();
            assert.ok(Math.abs(groupBox.x - barBox.x) < 1 && Math.abs(groupBox.width - barBox.width) < 1);
            await list(p, bar, rows, true);
            await list(p, cap, rows);
          }
        }
        await list(p, p.locator('#removed-count'), expected);
        await p.setViewportSize({ width: 390, height: 844 });
        const bounds = await p.locator('#removed-bar').boundingBox();
        assert.ok(bounds.width > 0 && bounds.x >= 0 && bounds.x + bounds.width <= 390);
        await list(p, p.locator('#removed-done-count'), done, true);
        await p.locator('#removed').screenshot({ path: path.join(base, file + '-removed-mobile.png') });
      });
    }
    await check('narrow segment caption moves to the legend and still opens the exact list', 'unbalanced', async p => {
      await p.setViewportSize({ width: 390, height: 844 });
      const fallback = p.locator('#removed-leg [data-segment="done"]');
      await fallback.waitFor({ state: 'visible' });
      assert.match(await fallback.innerText(), /Готово/);
      await list(p, fallback, [2], true);
    });
    await check('completed removed segments, mini bars and lists follow accepted measures', 'measures', async p => {
      const expected = [['Патч из апстрима', [4, 5]], ['Импорт новой версии', [6]], ['Своя "мера"', [8]], ['не указана', [7]]];
      assert.equal(await p.locator('#removed-count').innerText(), '7');
      assert.equal(await p.locator('#removed-done-count').innerText(), '5');
      assert.equal(await p.locator('#removed-rest-count').innerText(), '2');
      assert.equal(await p.locator('#removed-bar > span').count(), 5);
      assert.deepEqual(await p.locator('#measrows .k').allTextContents(), ['Патч из апстрима', 'Импорт новой версии']);
      for (const width of [1440, 390]) {
        await p.setViewportSize({ width, height: 1000 });
        await p.waitForTimeout(250); // resize rebuilds the report after 150 ms
        assert.deepEqual(await p.locator('#removed-rows > .k').allTextContents(), ['Готово', 'Убрано']);
        assert.equal(await p.locator('#removed-rows > .b[data-segment="done"] > span > span').count(), expected.length);
        const mini = p.locator('#removed-rows > .b[data-segment="done"] > span > span');
        const componentGap = await p.locator('#components .track > span').first().evaluate(n => parseFloat(getComputedStyle(n).gap));
        const gaps = await mini.evaluateAll(nodes => nodes.slice(1).map((n, i) => n.getBoundingClientRect().left - nodes[i].getBoundingClientRect().right));
        assert.ok(gaps.every(gap => Math.abs(gap - componentGap) < 0.1));
        await mini.first().hover();
        await p.waitForFunction(() => {
          const nodes = [...document.querySelectorAll('#removed-rows .track > span > span')];
          return getComputedStyle(nodes[0]).opacity === '1' && nodes.slice(1).every(n => Math.abs(Number(getComputedStyle(n).opacity) - 0.45) < 0.01);
        });
        assert.equal(await p.locator('#removed-rows > .dim').count(), 0);
        const bars = p.locator('#removed-bar > [data-group="done"]');
        const first = await bars.first().boundingBox(), last = await bars.last().boundingBox();
        const bracket = await p.locator('#removed-groups .cap[data-segment="done"]').locator('..').boundingBox();
        assert.ok(Math.abs(bracket.x - first.x) < 1 && Math.abs(bracket.width - (last.x + last.width - first.x)) < 1);
        for (let i = 0; i < expected.length; i++) {
          const [label, ids] = expected[i], key = 'done-measure-' + i;
          const bar = p.locator('#removed-bar > [data-segment="' + key + '"]');
          assert.match(await bar.getAttribute('data-tip'), new RegExp(label));
          const bg = await bar.evaluate(n => getComputedStyle(n).backgroundColor);
          assert.notEqual(bg, 'rgba(0, 0, 0, 0)');
          if (i < 2) {
            const poolBg = await p.locator('#measstrip > span').nth(i).evaluate(n => getComputedStyle(n).backgroundColor);
            assert.equal(bg, poolBg);
          }
          await list(p, bar, ids, width === 390);
          const miniSegment = p.locator('#removed-rows > .b[data-segment="done"] [data-segment="' + key + '"]');
          assert.equal(await miniSegment.getAttribute('data-tip'), label + ': ' + ids.length);
          assert.equal(await miniSegment.evaluate(n => getComputedStyle(n).backgroundColor), bg);
          await list(p, miniSegment, ids, width === 390);
        }
        await list(p, p.locator('#removed-groups .cap[data-segment="done"]'), [4, 5, 6, 7, 8]);
        await list(p, p.locator('#removed-done-count'), [4, 5, 6, 7, 8]);
        await list(p, p.locator('#removed-rest-count'), [9, 10]);
        await p.locator('#removed').screenshot({ path: path.join(base, 'measures-' + width + '.png') });
      }
    });
    await check('removed remainder has three disjoint AI segments with exact task lists', 'ai', async p => {
      const expected = [['maybe', 'Возможно затронуто', [5, 6, 7]], ['no', 'Не затронуто', [8, 9, 10]], ['none', 'Не прогнано', [11, 12]]];
      assert.equal(await p.locator('#k-total').innerText(), '2');
      assert.equal(await p.locator('#ai-total .n').innerText(), '2');
      await list(p, p.locator('#ai-groups .cap').first(), [3]);
      await list(p, p.locator('#ai-groups .cap').nth(1), [2]);
      assert.equal(await p.locator('#removed-count').innerText(), '9');
      assert.equal(await p.locator('#removed-done-count').innerText(), '1');
      assert.equal(await p.locator('#removed-rest-count').innerText(), '8');
      for (const width of [1440, 390]) {
        await p.setViewportSize({ width, height: 1000 }); await p.waitForTimeout(250);
        assert.deepEqual(await p.locator('#removed-rows > .k').allTextContents(), ['Готово', 'Убрано']);
        const bars = p.locator('#removed-bar > [data-group="removed"]');
        assert.equal(await bars.count(), 3);
        const first = await bars.first().boundingBox(), last = await bars.last().boundingBox();
        const cap = p.locator('#removed-groups .cap[data-segment="removed"]');
        const bracket = await cap.locator('..').boundingBox();
        assert.ok(Math.abs(bracket.x - first.x) < 1 && Math.abs(bracket.width - (last.x + last.width - first.x)) < 1);
        const miniParts = p.locator('#removed-rows .track[data-segment="removed"] > span > span');
        assert.equal(await miniParts.count(), 3);
        const gaps = await miniParts.evaluateAll(nodes => nodes.slice(1).map((n, i) => n.getBoundingClientRect().left - nodes[i].getBoundingClientRect().right));
        assert.ok(gaps.every(gap => Math.abs(gap - 2) < 0.1));
        await miniParts.first().hover();
        await p.waitForFunction(() => {
          const nodes = [...document.querySelectorAll('#removed-rows .track[data-segment="removed"] > span > span')];
          return getComputedStyle(nodes[0]).opacity === '1' && nodes.slice(1).every(n => Math.abs(Number(getComputedStyle(n).opacity) - 0.45) < 0.01);
        });
        for (const [key, label, ids] of expected) {
          const bar = p.locator('#removed-bar > [data-segment="removed-ai-' + key + '"]');
          const mini = p.locator('#removed-rows .track[data-segment="removed"] [data-segment="removed-ai-' + key + '"]');
          assert.match(await bar.getAttribute('data-tip'), new RegExp(label + ': ' + ids.length));
          assert.equal(await mini.getAttribute('data-tip'), label + ': ' + ids.length);
          const bg = await mini.evaluate(n => getComputedStyle(n).backgroundColor);
          assert.notEqual(bg, 'rgba(0, 0, 0, 0)');
          assert.equal(await bar.evaluate(n => getComputedStyle(n).backgroundColor), bg);
          await list(p, bar, ids, width === 390);
          await list(p, mini, ids, width === 390);
        }
        await list(p, cap, [5, 6, 7, 8, 9, 10, 11, 12]);
        await list(p, p.locator('#removed-rest-count'), [5, 6, 7, 8, 9, 10, 11, 12]);
        await list(p, p.locator('#removed-done-count'), [4]);
        await p.locator('#removed').screenshot({ path: path.join(base, 'ai-' + width + '.png') });
      }
    });
    await check('missing AI column keeps removed tasks in not-run segment', 'missing-ai', async p => {
      assert.equal(await p.locator('#removed-bar > span').count(), 1);
      await list(p, p.locator('#removed-bar > [data-segment="removed-ai-none"]'), [2]);
      await list(p, p.locator('#removed-rows .track [data-segment="removed-ai-none"]'), [2]);
    });
    await check('ten-task bars and exact lists', 'ten', async p => {
      assert.deepEqual(await parts(p.locator('#hero-bar > span')), [['done', 6], ['work', 2]]);
      assert.equal(await p.locator('#k-total').innerText(), '8');
      assert.equal(await p.locator('#hero-bar [data-segment="done"]').innerText(), '75%');
      assert.equal(await p.locator('#hero-bar [data-segment="work"]').innerText(), '25%');
      assert.match(await p.locator('#hero-groups [data-group="done"] .cap').getAttribute('data-tip'), /75% от всех задач/);
      assert.equal(await p.locator('#hero-groups [data-group="removed"], #hero-leg [data-group="removed"]').count(), 0);
      assert.deepEqual(await parts(card(p).locator('.pbar > span')), [['done', 6], ['work', 2], ['removed', 2]]);
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '2');
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '6');
      assert.equal(await p.locator('#hero-state .removed-subset').count(), 0);
      const headerTips = await p.locator('#hero-groups [data-tip], #hero-bar [data-tip]').evaluateAll(nodes => nodes.map(n => n.dataset.tip));
      assert.ok(headerTips.every(t => !t.includes('без убранных')));
      assert.doesNotMatch(await p.locator('#hero-groups').innerText(), /без убранных/);
      assert.equal(await p.locator('#p-open').innerText(), '2');
      assert.equal(await p.locator('#p-out').innerText(), '2');
      assert.equal(await card(p).locator('.dstat [data-role="done"] > b').innerText(), '6');
      await list(p, p.locator('#k-total'), [2, 3, 4, 5, 6, 7, 10, 11], true);
      await list(p, p.locator('#hero-bar [data-segment="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-bar [data-segment="work"]'), [10, 11]);
      await list(p, p.locator('#hero-state [data-role="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [8, 9], true);
      assert.equal(await card(p).locator('.removed-subset').count(), 0);
      await list(p, card(p).locator('.dstat [data-role="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, card(p).locator('.pbar [data-segment="done"]'), [2, 3, 4, 5, 6, 7]);
      await list(p, p.locator('#hero-groups [data-group="done"] .cap'), [2, 3, 4, 5, 6, 7]);
      await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(250);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [8, 9]);
      await list(p, p.locator('#k-total'), [2, 3, 4, 5, 6, 7, 10, 11]);
      await p.screenshot({ path: path.join(base, 'ten-mobile.png'), fullPage: true });
    });
    await check('mixed role counters, triage, forecast and closure dates', 'mixed', async p => {
      const notRun = p.locator('#removed-bar > span[data-segment="removed-ai-none"]');
      assert.equal(await p.locator('#k-total').innerText(), '2');
      assert.deepEqual(await parts(p.locator('#hero-bar > span')), [['done', 1], ['work', 1]]);
      assert.equal(await p.locator('#hero-bar [data-segment="done"]').evaluate(n => n.style.getPropertyValue('--triaged')), '100%');
      assert.equal(await p.locator('#hero-bar [data-segment="done"]').innerText(), '50%');
      assert.match(await notRun.getAttribute('data-tip'), /Убрано · Не прогнано: 4 из 5/);
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '5');
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '1');
      assert.equal(await p.locator('#hero-state [data-role="work"] > b').innerText(), '1');
      assert.equal(await p.locator('#hero-state [data-role="none"] > b').innerText(), '0');
      assert.equal(await p.locator('#hero-state > div > b').evaluateAll(nodes => nodes.reduce((n, el) => n + Number(el.textContent), 0)), 7);
      assert.equal(await p.locator('#p-open').innerText(), '1');
      assert.equal(await p.locator('#p-out').innerText(), '0,5');
      assert.match(await p.locator('#pace-note').innerText(), /Убрано из эпика/);
      await list(p, p.locator('#hero-state [data-role="work"]'), [7]);
      await list(p, p.locator('#hero-state [data-role="done"]'), [8]);
      await list(p, p.locator('#hero-state [data-role="removed"]'), [2, 3, 4, 5, 6]);
      await list(p, p.locator('#k-total'), [7, 8]);
      assert.equal(await card(p).locator('.removed-subset').count(), 0);
      await list(p, p.locator('#close-sub b'), []);
      await list(p, notRun, [2, 4, 5, 6]);
      for (const theme of ['light', 'dark']) {
        await p.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
        const bg = await notRun.evaluate(n => getComputedStyle(n).backgroundColor);
        assert.notEqual(bg, 'rgba(0, 0, 0, 0)');
        assert.equal(bg, await p.locator('#removed-rows .track [data-segment="removed-ai-none"]').evaluate(n => getComputedStyle(n).backgroundColor));
        await p.screenshot({ path: path.join(base, 'mixed-' + theme + '.png'), fullPage: true });
      }
    });
    await check('only removed data renders', 'only', async p => {
      assert.deepEqual(await parts(p.locator('#hero-bar > span')), []);
      assert.equal(await p.locator('#hero-groups > div').count(), 0);
      assert.equal(await p.locator('#k-total').innerText(), '0');
      assert.equal(await p.locator('#hero-state [data-role="done"] > b').innerText(), '0');
      assert.equal(await p.locator('#hero-state [data-role="removed"] > b').innerText(), '2');
      assert.equal(await p.locator('#p-open').innerText(), '0');
      assert.equal(await p.locator('#k-cve').innerText(), '0');
      assert.equal(await p.locator('#k-comp').innerText(), '0');
      assert.equal(await p.locator('.dev').count(), 2);
      assert.equal(await p.locator('.dev-info-only').count(), 2);
      assert.equal(await p.locator('.dev .speed, .dev .dev-tl').count(), 0);
      await list(p, card(p).locator('.big'), []);
      await list(p, card(p).locator('.pbar [data-segment="removed"]'), [3]);
      assert.equal(await p.locator('#devstatus .k').innerText(), 'Убрано из эпика');
      assert.equal(await p.locator('#devstatus .p').innerText(), '—');
      await list(p, p.locator('#devstatus .b'), [2, 3]);
      await list(p, p.locator('#k-total'), []);
      await list(p, p.locator('#removed-bar > span'), [2, 3]);
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
      assert.equal(await secops.count(), 1);
      assert.equal(await secops.locator('.speed, .dev-tl').count(), 0);
      await list(p, secops.locator('.dstat [data-role="removed"]'), [3]);
      assert.equal(await p.locator('#anom-n').innerText(), '0');
    });
    await check('unique representatives and AI exclude removed pairs and verdicts', 'pairs', async p => {
      assert.equal(await p.locator('#k-total').innerText(), '1');
      await list(p, p.locator('#k-total'), [3]);
      assert.equal(await p.locator('#k-cve').innerText(), '1');
      await list(p, p.locator('#k-cve'), [3]);
      assert.equal(await p.locator('#close-sub b').innerText(), '0');
      await list(p, p.locator('#removed-count'), [2, 4, 5]);
      assert.equal(await p.locator('#ai-total .n').innerText(), '0');
      await list(p, p.locator('#aistrip [data-drill]').first(), [3]);
      const csv = await p.evaluate(() => window.CS.drilldown.csv(JSON.parse(document.getElementById('data').textContent).rows));
      assert.match(csv, /Убрано из эпика/);
    });
    assert.deepEqual(errors, []);
    assert.equal(failures.length, 0, failures.join('\n\n'));
    console.log(JSON.stringify({ artifacts: base, checks, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
