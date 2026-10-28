'use strict';
var test = require('node:test');
var assert = require('node:assert');
var dates = require('../../cvesummary/assets/js/dates.js');
var pace = require('../../cvesummary/assets/js/pace.js');

var D = 20731;
var iso = dates.isoOf;
function r(tdate, status, end) { return { tdate: iso(tdate), status: status || '', end: end === undefined ? '' : iso(end) }; }

/* D — понедельник 05.10.2026. Поступление — на календарный день (новые
   приходят и в выходные), закрытие — на рабочий день Пн–Пт */
test('rates: поступление на календарный день, закрытие на рабочий, баланс за неделю', function () {
  var rows = [r(D), r(D + 1), r(D + 6, 'Готов', D + 6), r(D + 6, 'Готов', D + 3), r(D - 1), r(D + 9)];
  var got = pace.rates(rows, D + 6, 7);
  assert.strictEqual(got.inR, 4 / 7);   // окно Пн–Вс; D-1 вне окна, D+9 после даты отчёта
  assert.strictEqual(got.outR, 2 / 5);  // 5 рабочих дней в окне
  assert.strictEqual(got.open, 4);
  assert.strictEqual(got.net, 2 / 5 * 5 - 4 / 7 * 7);  // за неделю: закрыто 5 рабочих дней, пришло 7 календарных
});

test('rates без закрытых и без дат — нули, не NaN', function () {
  var got = pace.rates([{ tdate: '', status: '', end: '' }], D, 14);
  assert.deepStrictEqual(got, { inR: 0, outR: 0, net: 0, open: 1, days: 14, work: 10, cut: 0, closed: 0, closedTotal: 0 });
});

/* дни работы: D (Пн) … D + 4 (Пт), потом две недели пусто, с D + 21 (Пн) снова */
function active(list) { return new Set(list); }
var WEEK1 = [D, D + 1, D + 2, D + 3, D + 4], WEEK4 = [D + 21, D + 22, D + 23];

test('breaks: пять рабочих дней подряд без работы — перерыв, со своими выходными', function () {
  var got = pace.breaks(active(WEEK1.concat(WEEK4)), D, D + 23);
  assert.deepStrictEqual(got, [{ from: D + 5, to: D + 20, work: 10 }]);
});

test('breaks: короткий простой — не перерыв, порог — ровно пять рабочих дней', function () {
  // Вт–Пт пусто: 4 рабочих дня
  assert.deepStrictEqual(pace.breaks(active([D, D + 7]), D, D + 7), []);
  // Вт–Пн пусто: 5 рабочих дней
  assert.deepStrictEqual(pace.breaks(active([D, D + 8]), D, D + 8), [{ from: D + 1, to: D + 7, work: 5 }]);
  // работа в выходной (взял или закрыл) рвёт отрезок
  assert.deepStrictEqual(pace.breaks(active([D, D + 5, D + 9]), D, D + 9), []);
});

test('breaks: хвост перед датой отчёта и пустое начало — по тому же правилу', function () {
  assert.deepStrictEqual(pace.breaks(active(WEEK1), D, D + 13), [{ from: D + 5, to: D + 13, work: 5 }]);
  assert.deepStrictEqual(pace.breaks(active(WEEK1), D, D + 10), []);
  assert.deepStrictEqual(pace.breaks(active(WEEK4), D, D + 23), [{ from: D, to: D + 20, work: 15 }]);
});

test('breaks: нет начала работы или ни одного дня работы — перерывов нет', function () {
  assert.deepStrictEqual(pace.breaks(active(WEEK1), null, D + 30), []);
  assert.deepStrictEqual(pace.breaks(active([]), D, D + 30), []);
});

test('rates с перерывами: рабочие дни перерыва и закрытия в нём не считаются, поступление — как было', function () {
  var gaps = [{ from: D + 5, to: D + 20, work: 10 }];
  // 2 закрыты в первую неделю, 1 — в перерыве (SecOps), 3 — в четвёртую
  var rows = [r(D, 'Готов', D + 1), r(D, 'Готов', D + 2), r(D + 9, 'Готов', D + 10),
    r(D + 21, 'Готов', D + 21), r(D + 21, 'Готов', D + 22), r(D + 22, 'Готов', D + 23)];
  var plain = pace.rates(rows, D + 23, Infinity, D);
  var got = pace.rates(rows, D + 23, Infinity, D, undefined, gaps);
  assert.strictEqual(plain.work, 18);
  assert.strictEqual(plain.outR, 6 / 18);
  assert.strictEqual(got.work, 8);
  assert.strictEqual(got.cut, 10);
  assert.strictEqual(got.closed, 5);
  assert.strictEqual(got.closedTotal, 6);  // баланс очереди — по всем закрытым
  assert.strictEqual(got.outR, 5 / 8);
  assert.strictEqual(got.inR, plain.inR);
  assert.strictEqual(got.days, plain.days);
});

test('rates с перерывом, задетым окном частично, и сценарии с ним', function () {
  var gaps = [{ from: D + 5, to: D + 20, work: 10 }];
  var rows = [r(D + 21, 'Готов', D + 21), r(D + 21, 'Готов', D + 22), r(D + 9, 'Готов', D + 10)];
  // окно 14 дней до D + 23: (D + 9, D + 23] — из перерыва в нём 7 рабочих дней
  var got = pace.rates(rows, D + 23, 14, D, undefined, gaps);
  assert.strictEqual(got.cut, 7);
  assert.strictEqual(got.work, 3);
  assert.strictEqual(got.closed, 2);
  var sc = pace.scenarios(rows, D + 23, D, null, null, undefined, gaps);
  assert.deepStrictEqual(sc.map(function (x) { return [x.closed, x.rates.work]; }), [[2, 3], [2, 3], [2, 8]]);
});

test('simulate — приходят каждый день, закрываем по рабочим; результат — календарный сдвиг', function () {
  assert.strictEqual(pace.simulate(0, 1, 1, D), null);
  assert.strictEqual(pace.simulate(5, 0, 0, D), null);           // не закрываем
  assert.strictEqual(pace.simulate(10, 0, 2, D, null), 7);       // Вт–Пт и Пн: понедельник следующей недели
  assert.strictEqual(pace.simulate(10, 2, 2.8, D), null);        // за неделю 14 приходит, 14 закрываем
  assert.strictEqual(pace.simulate(4, 1, 2, D, D + 3), 3);       // сканфриз в четверг
  assert.strictEqual(pace.simulate(3, 1, 3, D + 4, D + 8), 4);   // в выходные приходят, закрываем с понедельника
  assert.strictEqual(pace.simulate(1, 0, 1, D + 4, null), 3);    // из пятницы — в понедельник
  assert.strictEqual(pace.simulate(1, 0, 0.1, D, null), 14);     // 10 рабочих дней, без ошибки округления
});

test('need — в рабочий день до целевой даты, новые — по календарным дням', function () {
  assert.strictEqual(pace.need(10, 1, D, null, D), null);
  assert.deepStrictEqual(pace.need(10, 1, D, null, D + 14), { perDay: 3, left: 10, incoming: 14 });
  assert.deepStrictEqual(pace.need(10, 1, D, D + 5, D + 14), { perDay: 1.4, left: 10, incoming: 4 });
  assert.deepStrictEqual(pace.need(10, 1, D + 4, null, D + 6), { perDay: Infinity, left: 0, incoming: 2 });
});

test('daily: по дням и среднее за 7', function () {
  var got = pace.daily([r(D), r(D), r(D + 1, 'Готов', D + 1)], D, D + 1);
  assert.deepStrictEqual(got.map(function (s) { return [s.day, s.i, s.o]; }), [[D, 2, 0], [D + 1, 1, 1]]);
  assert.strictEqual(got[1].ia, 1.5);
  assert.strictEqual(got[1].oa, 0.5);
  assert.deepStrictEqual(pace.daily([], D + 1, D), []);
});

/* Накопительные ряды для burn-up и burn-down: по дням from..to — всего
   поступило, всего закрыто, открыто. Без Task date задача в бэклоге с
   начала; «Готов» без End date закрыт сразу, как поступил; закрытие не
   раньше поступления. */
test('cumulative: поступило, закрыто, открыто по дням', function () {
  var rows = [r(D), r(D + 1, 'Готов', D + 2), r(D + 2), { tdate: '', status: '', end: '' },
    { tdate: iso(D + 1), status: 'Готов', end: '' }, r(D + 3, 'Готов', D + 1)];
  var got = pace.cumulative(rows, D, D + 3);
  assert.deepStrictEqual(got.map(function (s) { return [s.day - D, s.inc, s.out, s.open]; }),
    [[0, 2, 0, 2], [1, 4, 1, 3], [2, 5, 2, 3], [3, 6, 3, 3]]);
  assert.deepStrictEqual(pace.cumulative(rows, D + 1, D), []);
});

test('project: прогноз остатка по дням до нуля — тот же шаг, что simulate', function () {
  // из пятницы, 3 открыто, приходит 1 в день до вторника (сканфриз), закрываем 3 в рабочий день
  var got = pace.project(3, 1, 3, D + 4, D + 8, 365);
  assert.deepStrictEqual(got.map(function (s) { return [s.day - D - 4, s.inc, s.out, s.open]; }),
    [[1, 1, 0, 4], [2, 2, 0, 5], [3, 3, 3, 3], [4, 3, 6, 0]]);
  assert.strictEqual(got.length, pace.simulate(3, 1, 3, D + 4, D + 8));
  // закрытие на последнем шаге не уходит ниже нуля
  var last = pace.project(1, 0, 3, D, null, 365);
  assert.deepStrictEqual(last.map(function (s) { return [s.day - D, s.out, s.open]; }), [[1, 1, 0]]);
  // не сходится — обрывается на горизонте
  assert.strictEqual(pace.project(5, 2, 2, D, undefined, 30).length, 30);
  assert.strictEqual(pace.project(0, 1, 1, D, undefined, 30).length, 30);
});

test('cumulative: даты позже конца ряда прижимаются к нему — остаток равен rates().open', function () {
  var rows = [r(D), r(D + 3), r(D, 'Готов', D + 3), r(D + 2, 'Готов', D + 1), { tdate: iso(D), status: 'Готов', end: '' }];
  var got = pace.cumulative(rows, D - 1, D);
  var last = got[got.length - 1];
  assert.strictEqual(last.open, pace.rates(rows, D, 7).open);
  assert.deepStrictEqual([last.inc, last.out, last.open], [5, 3, 2]);
});

/* Начало работы — самая ранняя Start date у взятых задач; окно темпа не
   уходит раньше него, «весь период» — от него до даты отчёта */
test('workStart: самая ранняя Start date взятой задачи, не позже даты отчёта', function () {
  var rows = [{ dev: 'A', start: iso(D + 2) }, { dev: '', start: iso(D) }, { dev: 'B', start: iso(D + 1) }, { dev: 'C', start: iso(D + 9) }, { dev: 'D', start: '' }];
  assert.strictEqual(pace.workStart(rows, D + 5), D + 1);
  assert.strictEqual(pace.workStart([{ dev: '', start: iso(D) }], D), null);
});

test('rates: окно обрезается по началу работы, «весь период» — от него', function () {
  // задачи шли две недели, разработчики начали в пятницу D+4, отчёт тоже D+4
  var rows = [r(D - 10), r(D - 3), r(D + 4), r(D + 4, 'Готов', D + 4), r(D + 4, 'Готов', D + 4)];
  var got = pace.rates(rows, D + 4, 7, D + 4);
  assert.deepStrictEqual([got.days, got.work, got.inR, got.outR], [1, 1, 3, 2]);
  var all = pace.rates(rows, D + 4, Infinity, D);
  assert.deepStrictEqual([all.days, all.work], [5, 5]);
  assert.strictEqual(all.inR, 3 / 5);
  var plain = pace.rates(rows, D + 4, 7);   // без начала работы — как раньше
  assert.deepStrictEqual([plain.days, plain.work], [7, 5]);
});

test('rates: окно может кончаться раньше даты отчёта; конец позже — прижимается', function () {
  var rows = [r(D), r(D + 1), r(D + 2, 'Готов', D + 2), r(D + 8), r(D + 9, 'Готов', D + 9)];
  // период Пн–Ср первой недели, отчёт через неделю
  var got = pace.rates(rows, D + 9, 3, null, D + 2);
  assert.deepStrictEqual([got.days, got.work, got.inR, got.outR, got.open], [3, 3, 1, 1 / 3, 3]);
  var late = pace.rates(rows, D + 9, 3, null, D + 30);   // конец после отчёта — как отчёт
  assert.deepStrictEqual([late.days, late.inR], [3, 2 / 3]);
});

test('simulate со стартом: до него задачи только копятся, закрываем с даты старта', function () {
  assert.strictEqual(pace.simulate(10, 0, 5, D, null, D + 3), 4);  // чт и пт
  assert.strictEqual(pace.simulate(5, 0, 5, D, null, D + 5), 7);   // старт в субботу — закрываем с понедельника
  assert.strictEqual(pace.simulate(2, 1, 5, D, D + 4, D + 3), 3);  // до старта пришло 3, в чт закрыли 5
  assert.strictEqual(pace.simulate(10, 0, 2, D, null, D + 1), pace.simulate(10, 0, 2, D, null));
});

test('project со стартом: до старта out не растёт', function () {
  var got = pace.project(2, 1, 5, D, D + 4, 365, D + 3);
  assert.deepStrictEqual(got.map(function (s) { return [s.day - D, s.inc, s.out, s.open]; }),
    [[1, 1, 0, 3], [2, 2, 0, 4], [3, 3, 5, 0]]);
});

test('latestStart: самая поздняя дата старта, чтобы закончить к цели', function () {
  assert.strictEqual(pace.latestStart(10, 0, 5, D, null, D + 4), D + 3);     // чт и пт
  assert.strictEqual(pace.latestStart(10, 0, 5, D, null, D + 7), D + 4);     // пт и пн: выходные не в счёт
  assert.strictEqual(pace.latestStart(4, 1, 5, D, D + 3, D + 4), D + 3);     // +2 новых до сканфриза
  assert.strictEqual(pace.latestStart(4, 1, 5, D, null, D + 4), null);      // без сканфриза завершение всего объёма неизвестно
  assert.strictEqual(pace.latestStart(4, 1, 5, D, D + 2, D + 4), D + 4);     // сканфриз в среду — 1 новая, 5 за пт
  assert.strictEqual(pace.latestStart(100, 0, 5, D, null, D + 4), null);     // не успеть и со стартом завтра
  assert.strictEqual(pace.latestStart(10, 0, 0, D, null, D + 4), null);      // темп нулевой
  assert.strictEqual(pace.latestStart(10, 0, 5, D, null, D), null);          // цель не позже даты отчёта
  assert.strictEqual(pace.latestStart(0, 1, 5, D, null, D + 4), null);      // нулевой остаток не отменяет будущие поступления
});

test('devsNeeded: сколько людей, чтобы со старта завтра успеть к цели', function () {
  assert.strictEqual(pace.devsNeeded(10, 0, 1, D, null, D + 4), 3);          // 4 рабочих дня, 10 задач
  assert.strictEqual(pace.devsNeeded(10, 1, 1, D, null, D + 4), null);          // и 4 новых
  assert.strictEqual(pace.devsNeeded(0, 0, 1, D, null, D + 4), 0);           // делать нечего
  assert.strictEqual(pace.devsNeeded(10, 0, 0, D, null, D + 4), null);       // темп на одного нулевой
  assert.strictEqual(pace.devsNeeded(10, 0, 1, D + 4, null, D + 6), null);   // до цели одни выходные
  assert.strictEqual(pace.devsNeeded(10, 0, 1, D, null, D), null);
});

test('devsNeeded: цель в выходной — считаем по пятнице, людей не больше нужного', function () {
  // отчёт в пн, цель в вс: закрываем вт–пт, новые 5 в день приходят до пятницы
  assert.strictEqual(pace.devsNeeded(10, 5, 1, D, D + 5, D + 6), 8);
  assert.strictEqual(pace.latestStart(10, 5, 8, D, D + 5, D + 6), D + 1);
});

test('latestStart: дальняя цель — тот же ответ, без перебора каждого дня', function () {
  var target = D + 4000, s = pace.latestStart(10, 0, 5, D, null, target);
  assert.ok(s > D + pace.HORIZON, 'старт за горизонтом симуляции: ' + (s - D));
  assert.ok(D + pace.simulate(10, 0, 5, D, null, s) <= target);
  assert.ok(D + pace.simulate(10, 0, 5, D, null, s + 1) > target);
  var t0 = Date.now();
  pace.latestStart(1e6, 1, 1, D, null, D + 20 * 365);               // не успеть — сразу
  assert.ok(Date.now() - t0 < 200, 'долго: ' + (Date.now() - t0) + ' мс');
});


test('simulate: временный ноль не завершает работу до последних поступлений', function () {
  assert.strictEqual(pace.simulate(5, 1, 3, D, D + 30), 29);
  var series = pace.project(5, 1, 3, D, D + 30, 365);
  assert.strictEqual(series[2].open, 0); // четверг: первая пустая очередь
  assert.strictEqual(series[5].open, 2); // воскресенье: работа снова накопилась
  assert.deepStrictEqual(series.at(-1), { day: D + 29, inc: 29, out: 34, open: 0 });
});

test('project: свободную мощность до выходных нельзя потратить на будущие задачи', function () {
  var series = pace.project(1, 1, 3, D, D + 9, 30);
  assert.strictEqual(series[0].out, 2);
  assert.strictEqual(series[5].open, 2);
  assert.deepStrictEqual(series.at(-1), { day: D + 8, inc: 8, out: 9, open: 0 });
});

test('simulate: нулевой остаток с будущими поступлениями не означает завершение', function () {
  assert.strictEqual(pace.simulate(0, 1, 3, D, D + 9), 8);
  assert.strictEqual(pace.simulate(0, 1, 0, D, D + 9), null);
  assert.strictEqual(pace.simulate(0, 0, 0, D), 0);
  assert.strictEqual(pace.simulate(0, 1, 0, D, D + 1), 0);
  assert.strictEqual(pace.devsNeeded(0, 1, 1, D, D + 3, D + 4), 1);
});

test('simulate/project: без сканфриза завершение неизвестно даже при быстром закрытии', function () {
  for (var stop of [null, undefined]) {
    assert.strictEqual(pace.simulate(1, 1, 100, D, stop), null);
    assert.strictEqual(pace.project(1, 1, 100, D, stop, 30).length, 30);
    assert.strictEqual(pace.latestStart(1, 1, 100, D, stop, D + 10), null);
    assert.strictEqual(pace.devsNeeded(1, 1, 100, D, stop, D + 10), null);
  }
});

test('план: никакое число людей не завершит весь объём до последних поступлений', function () {
  assert.strictEqual(pace.latestStart(5, 1, 100, D, D + 30, D + 10), null);
  assert.strictEqual(pace.devsNeeded(5, 1, 100, D, D + 30, D + 10), null);
  assert.strictEqual(pace.devsNeeded(5, 1, 1, D, D + 9, D + 10), 2);
});

test('need: поступления в последние выходные делают нулевой остаток недостижимым', function () {
  assert.deepStrictEqual(pace.need(10, 5, D, null, D + 6), { perDay: Infinity, left: 4, incoming: 30 });
  assert.strictEqual(pace.devsNeeded(10, 5, 1, D, D + 7, D + 6), null);
});

test('forecast: остаток к цели и запас считаются по дневной модели', function () {
  assert.deepStrictEqual(pace.forecast(10, 0, 2, D, null, D + 4),
    { days: 7, remaining: 2, margin: -1, state: 'dated' });
  assert.deepStrictEqual(pace.forecast(10, 0, 5, D, null, D + 4),
    { days: 2, remaining: 0, margin: 2, state: 'dated' });
  assert.deepStrictEqual(pace.forecast(0, 1, 100, D, null, D + 6),
    { days: null, remaining: 2, margin: null, state: 'open-ended' });
  assert.strictEqual(pace.forecast(5, 0, 0, D, null, D + 4).remaining, 5);
  assert.strictEqual(pace.forecast(5, 0, 0, D, null, D + 4).state, 'stalled');
});

test('forecast: цель отсутствует, прошла или слишком далеко — остаток неизвестен', function () {
  for (var target of [null, D - 1, D + pace.HORIZON + 1]) {
    var got = pace.forecast(1, 0, 1, D, null, target);
    assert.strictEqual(got.remaining, null);
    assert.strictEqual(got.margin, null);
  }
  assert.strictEqual(pace.forecast(1, 0, 0.00001, D, null, D + 1).state, 'horizon');
});

test('scenarios: окна 7/14/30 используют свои поступления и закрытия', function () {
  var rows = [r(D + 29, 'Готов', D + 29), r(D + 23), r(D + 16), r(D)];
  var got = pace.scenarios(rows, D + 29, D, null, D + 35, D + 29);
  assert.deepStrictEqual(got.map(x => [x.window, x.from, x.to, x.rates.inR, x.rates.outR]),
    [[7, D + 23, D + 29, 2 / 7, 1 / 5], [14, D + 16, D + 29, 3 / 14, 1 / 10],
      [30, D, D + 29, 4 / 30, 1 / 22]]);
  assert.ok(got.every(x => x.forecast.state === 'open-ended'));
  var clipped = pace.scenarios(rows, D + 29, D + 28, null, D + 35, D + 29);
  assert.ok(clipped.every(x => x.from === D + 28 && x.rates.days === 2));
  var empty = pace.scenarios([], D, null, null, D + 7, D);
  assert.ok(empty.every(x => x.forecast.days === 0 && x.forecast.remaining === 0));
});

test('scenarios: число закрытых сохраняется и в окне только из выходных', function () {
  var rows = [r(D + 5, 'Готов', D + 6)];
  var got = pace.scenarios(rows, D + 7, D + 5, null, D + 14, D + 6);
  assert.deepStrictEqual(got.map(x => [x.closed, x.rates.work, x.rates.outR]),
    [[1, 0, 0], [1, 0, 0], [1, 0, 0]]);
});
