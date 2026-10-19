/* Отрисовка сводки: данные — из блока #data, считают модули dates, roles,
   hours, pace и timeline; здесь только DOM. */
(function () {
  'use strict';
  const DATA = JSON.parse(document.getElementById('data').textContent);
  document.getElementById('k-total').textContent = DATA.rows.length;
}());
