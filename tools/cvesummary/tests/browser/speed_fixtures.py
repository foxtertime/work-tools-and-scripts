"""Regression fixtures for zero rates, selected windows and plan defaults."""
from pathlib import Path
import sys

from cvesummary import page

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)


def task(start="2026-11-02", end="", dev="X"):
    return dict(dev=dev, status="Готов" if end else "В работе", start=start,
                end=end, tdate=start, comp="demo", sev="Important", rstate="Affected",
                measure="Патч из апстрима", bad=[], p="", d="", ai_verdict="", ai_rem="")


fixtures = {
    "review": ("2026-11-05", [task(end="2026-11-03"),
               dict(task(end="2026-11-04"), status="Ожидает ревью"),
               dict(task(), status="Ожидает ревью"),
               dict(task(end="2026-11-06"), status="Ожидает ревью")]),
    "zero": ("2026-11-05", [task()]),
    "weekend": ("2026-11-08", [task("2026-11-07", "2026-11-07")]),
    "plan": ("2026-11-05", [task("2026-10-23")]
             + [task("2026-11-05", "2026-11-05") for _ in range(7)]),
    "five-day": ("2026-11-09", [task("2026-11-02", "2026-11-02") for _ in range(5)]
                 + [task(dev="Y")]),
}
fixtures["review-no-end"] = (fixtures["review"][0], [
    dict(r, end="") if i == 1 else dict(r) for i, r in enumerate(fixtures["review"][1])
])
fixtures["review-ready"] = ("2026-11-05", [
    dict(task(end="2026-11-04"), status="Ожидает ревью", p="+"),
    dict(task(), p="+"), task(),
])
for name, (as_of, rows) in fixtures.items():
    for i, row in enumerate(rows):
        row.update(row=i + 2, cve="CVE-2026-%d" % (8000 + i), task="TASK-%d" % i)
    meta = dict(version="test", source="speed", as_of=as_of, skipped=0, bad_dates=0, missing=[])
    (out / (name + ".html")).write_text(page.render(dict(meta=meta, rows=rows)), encoding="utf-8")
