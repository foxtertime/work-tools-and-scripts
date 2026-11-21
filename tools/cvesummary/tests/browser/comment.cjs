'use strict';
// «Ожидает комментарий»: отдельный пурпурный сегмент шапки, роль и раздел
// личной карточки, своя часть на таймлайнах и своя выборка по клику.
const { chromium } = require(process.env.CVESUMMARY_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const toolRoot = path.resolve(__dirname, '../..');
const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cvesummary-comment-'));
const generated = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'fixtures.py'), base], {
  cwd: toolRoot, env: { ...process.env, PYTHONPATH: toolRoot, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8',
});
assert.equal(generated.status, 0, generated.stderr);

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CVESUMMARY_CHROMIUM ? { executablePath: process.env.CVESUMMARY_CHROMIUM } : {}) });
  let checks = 0;
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/fonts.googleapis.com/**', r => r.abort());
    await page.route('**/fonts.gstatic.com/**', r => r.abort());
    await page.goto(pathToFileURL(path.join(base, 'comment-status.html')).href);
    const numbers = () => page.locator('#drill-body tr[data-row]').evaluateAll(nodes => nodes.map(n => +n.dataset.row).sort((a, b) => a - b));
    const opened = async (expected, title) => {
      await page.waitForFunction(() => document.querySelector('#task-explorer').open, null, { timeout: 1500 });
      assert.deepEqual(await numbers(), expected);
      if (title) assert.match(await page.locator('#drill-title').innerText(), title);
      await page.keyboard.press('Escape'); checks++;
    };
    const part = (host, segment, key) => page.locator(host).locator(`[data-chart-segment="${segment}"][data-chart-key="${key}"]`);
    const x = '.dev:has(h3:text-is("X"))';
    const expectedColor = { light: 'rgb(142, 63, 175)', dark: 'rgb(201, 155, 230)' };
    for (const [width, theme] of [[1440, 'light'], [390, 'dark']]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.emulateMedia({ colorScheme: theme });
      await page.waitForTimeout(300);

      assert.deepEqual(await page.locator('#hero-bar > span').evaluateAll(nodes => nodes.map(n => [n.dataset.segment, Number(n.dataset.count)])),
        [['done-dev', 1], ['review', 1], ['comment', 6], ['work', 1]]);
      const bar = page.locator('#hero-bar [data-segment="comment"]');
      assert.equal(await bar.evaluate(n => getComputedStyle(n).backgroundColor), 'rgb(201, 155, 230)', 'hero is always dark');
      assert.match(await page.locator('#hero-groups [data-group="comment"] .cap').getAttribute('data-tip'), /^комментарий: всего 6/);
      await bar.focus(); await page.keyboard.press('Enter');
      await opened([4, 5, 6, 7, 8, 9], /Комментарий/);
      assert.match(await page.locator('#hero-state [data-role="work"]').innerText(), /ревью 1 · комментарий 5 · пауза 0/);

      const card = page.locator(x);
      const role = card.locator('.dstat [data-role="comment"]');
      assert.deepEqual([await role.locator('span').innerText(), await role.locator('b').innerText()], ['комментарий', '4']);
      assert.equal(await role.locator('i').evaluate(n => getComputedStyle(n).backgroundColor), expectedColor[theme]);
      assert.equal(await card.locator('.pbar [data-segment="comment"]').evaluate(n => getComputedStyle(n).backgroundColor), expectedColor[theme]);
      const section = card.locator('[data-measure-status="comment"]');
      assert.equal(await section.locator('.cap').innerText(), 'ОЖИДАЕТ КОММЕНТАРИЙ ПО ПРИНЯТОЙ МЕРЕ · 4');
      assert.deepEqual(await section.locator('.k').allTextContents(), ['Патч из апстрима', 'Импорт новой версии']);
      assert.deepEqual(await section.locator('.n').allTextContents(), ['3', '1']);
      assert.ok((await section.boundingBox()).y > (await card.locator('[data-measure-status="review"]').boundingBox()).y);
      await section.locator('.cap').click();
      await opened([4, 5, 6, 7], /X · Ожидает комментарий по принятой мере/);

      assert.match(await page.locator('#pace-note').textContent(), /«Ожидает ревью» и «Ожидает комментарий» считаются выполненной работой/);
      assert.match(await page.locator('#pace-note').textContent(), /ревью и ожидание комментария считаются закрытыми задачами/);
      await page.locator('#burn-by [data-by="day"]').click();
      assert.match(await page.locator('#burn').getAttribute('aria-label'), /включая ревью и ожидающие комментария/);
      assert.equal(await page.locator('#burn [data-chart-segment="comment"]').count(), 3);
      for (const [key, expected] of [['X', [4]], ['Y', [8]]]) {
        await part('#burn', 'comment', key).first().click();
        await opened(expected, /Ожидает комментарий/);
      }
      await part('#burn', 'review', 'X').click();
      await opened([3], /Ожидает ревью/);
      const dot = part(`${x} .dev-tl`, 'comment', 'Патч из апстрима');
      assert.match(await dot.getAttribute('data-tip'), /ожидает комментарий/i);
      assert.equal(await dot.evaluate(n => document.getElementById(n.getAttribute('fill').slice(5, -1))
        ?.querySelector('circle')?.getAttribute('fill')), 'var(--st-comment)');
      await dot.click();
      await opened([4], /Ожидает комментарий · X/);
      await part(`${x} .dev-tl`, 'comment', 'Импорт новой версии').click();
      await opened([5]);
      assert.match(await page.locator('#burnleg').innerText(), /ожидает ревью[\s\S]*ожидает комментарий/i);
      assert.match(await card.locator('.dev-break-legend').innerText(), /ожидает комментарий/i);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('.hero').screenshot({ path: path.join(base, `comment-hero-${width}.png`) });
      await card.screenshot({ path: path.join(base, `comment-person-${width}.png`) });
      checks++;
    }
    assert.deepEqual(errors, []); checks++;
    console.log(JSON.stringify({ checks, screenshots: base }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
