"""Небольшие таблицы с проверяемой вручную историей разработчиков."""
from datetime import date, timedelta
from pathlib import Path
import sys

from cvesummary import page

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
start = date(2026, 11, 2)


def task(dev, offset, end=None, status="Готов"):
    return dict(dev=dev, status=status, start=(start + timedelta(days=offset)).isoformat(),
                end="" if end is None else (start + timedelta(days=end)).isoformat(),
                tdate=start.isoformat(), comp="demo", sev="Important", rstate="Affected",
                measure="Патч из апстрима", bad=[], p="", d="", ai_verdict="", ai_rem="")


for name, day in [("short", 3), ("away", 8), ("returned", 9), ("open", 8), ("all-away", 8)]:
    rows = [task("Алиса", 0, 0) for _ in range(5)]
    if name != "all-away":
        for dev in ("Борис", "Вера"):
            rows.append(task(dev, 0, status="В работе"))
            rows += [task(dev, d, d) for d in range(day + 1)
                     if (start + timedelta(days=d)).weekday() < 5]
    if name == "returned":
        rows += [task("Алиса", day, day) for _ in range(3)]
    if name == "open":
        rows.append(task("Алиса", 0, status="В работе"))
    if name == "all-away":
        rows.append(dict(task("Алиса", 0, status="В работе"), start=""))
    for i, row in enumerate(rows):
        row.update(row=i + 2, cve="CVE-2026-%d" % (9000 + i), task="TASK-%d" % i)
    data = dict(meta=dict(version="test", source="activity", as_of=(start + timedelta(days=day)).isoformat(),
                          skipped=0, bad_dates=0, missing=[]), rows=rows)
    (out / (name + ".html")).write_text(page.render(data), encoding="utf-8")
