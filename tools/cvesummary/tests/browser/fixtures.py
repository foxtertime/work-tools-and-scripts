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
