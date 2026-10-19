/* Подписи на частях полос состава: доля или число — только на частях не
   уже порога, иначе текст не влезет. Цвет подписи — под яркость фона части:
   фон задан токенами темы, поэтому его берут из вычисленного стиля. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CS = root.CS || {};
    root.CS.strips = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DARK = '#0F1D29', LIGHT = '#FFFFFF';
  const BRIGHT = 150;  // яркость 0–255, выше — фон светлый

  /* counts — размеры частей; how: 'pct' — доля в процентах, 'n' — само число */
  function labels(counts, min, how) {
    const tot = counts.reduce((a, n) => a + n, 0);
    return counts.map(n => (tot && n / tot >= min ? (how === 'pct' ? Math.round(n / tot * 100) + '%' : String(n)) : ''));
  }

  /* rgb()/rgba() — каналы 0–255; color-mix браузер отдаёт как color(srgb 0…1) */
  function ink(color) {
    const m = /^(rgba?|color)\((?:srgb\s+)?([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(color || '');
    if (!m) return LIGHT;
    const k = m[1] === 'color' ? 255 : 1;
    const y = (0.299 * m[2] + 0.587 * m[3] + 0.114 * m[4]) * k;
    return y > BRIGHT ? DARK : LIGHT;
  }

  return { labels, ink, DARK, LIGHT };
}));
