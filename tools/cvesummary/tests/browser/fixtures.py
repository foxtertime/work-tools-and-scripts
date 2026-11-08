"""Вымышленные таблицы для автономной браузерной проверки списков задач."""
import csv
import json
import sys
from pathlib import Path

from cvesummary import csvfile, page, table
from tests import example

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
with (out / "example.csv").open("w", encoding="utf-8", newline="") as handle:
    csv.writer(handle, delimiter=";").writerows(example.rows())
found = table.build(csvfile.read(str(out / "example.csv")).sheet)
data = {
    "meta": {
        "version": "test", "source": "example.csv", "sheet": None,
        "header_row": found.header_row, "as_of": "2026-10-19",
        "release": "Браузерная проверка", "skipped": found.skipped,
        "missing": found.missing, "bad_dates": found.bad_dates,
    },
    "rows": found.rows,
}
(out / "index.html").write_text(page.render(data), encoding="utf-8")
for name,rows,missing in [('empty',[],data['meta']['missing']),('no-ai',data['rows'],['ai_verdict','ai_remediation','ai_confidence','ai_run'])]:
 fixture={'meta':dict(data['meta'],missing=missing),'rows':[dict(r) for r in rows]}
 if name=='no-ai':
  for r in fixture['rows']:
   for k in ['ai_verdict','ai_rem','ai_conf','ai_run']: r[k]=''
 (out/f'{name}.html').write_text(page.render(fixture), encoding="utf-8")
fixture={'meta':dict(data['meta'],missing=[]),'rows':[]}
for i,(cve,comp,verdict,conf,rem,run) in enumerate([
 ('CVE-2026-1001','openssl','affected','low','manual remediation required','2026-10-10'),
 ('CVE-2026-1001','openssl','not affected','high','not required','2026-10-18'),
 ('CVE-2026-1002','curl','affected','medium','pending','2026-10-18'),
 ('CVE-2026-1003','git','not affected','high','pending','2026-10-18'),
 ('CVE-2026-1004','bash','not processed','','','2026-10-18'),
 ('CVE-2026-1005','kernel','','','',''),
 ('CVE-2026-1006','','unclear','low','','2026-10-18'),
 ('CVE-2026-1006','','unclear','low','','2026-10-18'),
]):
 r=dict(data['rows'][0],row=i+3,cve=cve,comp=comp,ai_verdict=verdict,ai_conf=conf,ai_rem=rem,ai_run=run,
        status='В работе',dev='Dev',start='2026-10-10',end='',tdate='2026-10-01',rstate='Affected',p='',d='',bad=[])
 fixture['rows'].append(r)
fixture['rows'][0]['task']='=1+1'
fixture['rows'][0]['comment']='<img src=x onerror=alert(1)>; \"проверка\"\\nновая строка'
fixture['rows'][0]['link']='javascript:alert(1)'
(out/'edge.html').write_text(page.render(fixture), encoding="utf-8")

# Literal unknown values may have the same text as a missing-value label.
placeholders = {"meta": dict(data["meta"], missing=[]), "rows": []}
for i, (verdict, remediation) in enumerate([
    ("не прогнано", "не прогнано"), ("", ""),
    ("affected", "не указана"), ("affected", ""),
]):
    placeholders["rows"].append(dict(
        data["rows"][0], row=i + 3, cve="CVE-2026-%d" % (2000 + i),
        comp="openssl", ai_verdict=verdict, ai_rem=remediation,
        ai_run="2026-10-18", bad=[],
    ))
(out / "placeholders.html").write_text(page.render(placeholders), encoding="utf-8")

# Hand-checked dates across Sunday/Monday and the partial report week.
charts = {"meta": dict(data["meta"], as_of="2026-10-21", missing=[]), "rows": []}
events = [
    ("Алиса", "Готов", "2026-10-11", "2026-09-21", "2026-10-12"),
    ("Алиса", "Готов", "2026-10-12", "2026-10-12", "2026-10-18"),
    ("Алиса", "Готов", "2026-10-18", "2026-10-17", "2026-10-19"),
    ("Алиса", "Готов", "2026-10-19", "2026-10-19", "2026-10-21"),
    ("Борис", "Готов", "2026-10-19", "2026-10-18", "2026-10-19"),
    ("Вера", "Готов", "2026-10-20", "2026-10-19", "2026-10-20"),
    ("Алиса", "В работе", "2026-10-21", "2026-10-19", "2026-10-20"),
    ("", "Готов", "2026-10-21", "2026-10-19", "2026-10-19"),
    ("Алиса", "Готов", "2026-10-22", "2026-10-21", "2026-10-22"),
    ("Борис", "Готов", "ошибка", "2026-10-19", "ошибка"),
    ("Борис", "Готов", "", "2026-10-19", ""),
    ("Алиса", "Готов", "2026-10-18", "2026-10-17", "2026-10-18"),
] + [("Разработчик %d" % i, "Готов", "2026-10-20", "2026-10-19", "2026-10-20")
     for i in range(9)]
for i, (dev, status, tdate, start, end) in enumerate(events):
    charts["rows"].append(dict(
        data["rows"][0], row=i + 3, cve="CVE-2026-%d" % (3000 + i),
        comp="openssl", dev=dev, status=status, tdate=tdate, start=start, end=end,
        sev="Critical" if i % 2 else "Low",
        measure="Патч из апстрима" if i % 2 else "Импорт новой версии",
        bad=["tdate", "end"] if tdate == "ошибка" else [],
    ))
charts["rows"][11]["cve"] = charts["rows"][1]["cve"]
(out / "charts.html").write_text(page.render(charts), encoding="utf-8")

task_links = {"meta": dict(data["meta"]), "rows": [
    dict(data["rows"][0], row=3, cve="CVE-2026-9001", comp="openssl", dev="Dev",
         status="Готов", start="2026-10-10", end="2026-10-18", bad=[],
         task="HTTPS://portal.works.prod.sbt/swtr/units/current/unit/TASKID-9001"),
    dict(data["rows"][0], row=4, cve="CVE-2026-9001", comp="openssl", dev="Dev",
         status="В работе", start="2026-10-10", end="", bad=[], task="TASKID-9002"),
]}
(out / "task-links.html").write_text(page.render(task_links), encoding="utf-8")

review_charts = {"meta": dict(data["meta"], as_of="2026-11-05", missing=[]), "rows": []}
for i, (dev, status, end, measure, bad) in enumerate([
    ("X", "Готов", "2026-11-03", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "2026-11-03", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "2026-11-04", "Импорт новой версии", []),
    ("Y", "Ожидает ревью", "2026-11-03", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "2026-11-06", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "2026-02-30", "Патч из апстрима", ["end"]),
    ("X", "В работе", "2026-11-03", "Патч из апстрима", []),
    ("", "Ожидает ревью", "2026-11-03", "Патч из апстрима", []),
    ("X", "Убрано из эпика", "2026-11-03", "Патч из апстрима", []),
    ("X", "Ожидает ревью", "2026-11-03", "Патч из апстрима", ["end"]),
] + [("D%d" % i, "Ожидает ревью" if i >= 6 else "Готов", "2026-11-03", "Патч из апстрима", []) for i in range(8)]):
    review_charts["rows"].append(dict(data["rows"][0], row=i + 2, cve="CVE-2026-%d" % (9500 + i),
        dev=dev, status=status, start="2026-11-02", end=end, tdate="2026-11-02",
        measure=measure, bad=bad, p="", d="", rstate="Affected"))
(out / "review-charts.html").write_text(page.render(review_charts), encoding="utf-8")
review_only = {"meta": review_charts["meta"], "rows": [dict(review_charts["rows"][2], start="")]}
(out / "review-only-chart.html").write_text(page.render(review_only), encoding="utf-8")

header_done = {"meta": dict(data["meta"], as_of="2026-11-05", missing=[]), "rows": []}
for i, (dev, status) in enumerate([
    ("SecOps", "Готов"), (" secOPS ", "Готов"), ("Алиса", "Готов"),
    ("Борис", "Готов"), ("", "Готов"), ("SecOps", "Ожидает ревью"),
    ("Алиса", "В работе"), ("SecOps", "Убрано из эпика"),
    ("Алиса", "Убрано из эпика"), ("", ""),
]):
    header_done["rows"].append(dict(data["rows"][0], row=i + 2, cve="CVE-2026-%d" % (9800 + i),
        dev=dev, status=status, start="2026-11-02" if dev else "", end="2026-11-05" if dev else "",
        tdate="2026-11-02", measure="Закрыто SecOps" if i == 3 else "Патч из апстрима",
        bad=[], p="", d="", rstate="Affected"))
(out / "header-done.html").write_text(page.render(header_done), encoding="utf-8")
