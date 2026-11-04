"""Removed-from-epic roles, disjoint segments and exact drilldown lists."""
from pathlib import Path
import sys
from cvesummary import page

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)


def task(status="Готов", **extra):
    return dict(dict(dev="X", status=status, start="2026-11-02", end="2026-11-05",
                     tdate="2026-11-02", comp="demo", sev="Important", rstate="Affected",
                     measure="Патч из апстрима", bad=[], p="", d="", ai_verdict="", ai_rem=""), **extra)


removed = "Убрано из эпика"
fixtures = {
    "ten": [task() for _ in range(6)] + [task(removed) for _ in range(2)]
           + [task("В работе", end="") for _ in range(2)],
    "mixed": [task(removed, dev="SecOps", start="", end=""), task(removed),
              task(removed, end="", p="+"), task(removed, dev="", start="", end="", exec="УА"),
              task(removed, dev="", start="", end=""), task("В работе", end=""), task()],
    "only": [task(removed, dev="SecOps", start="", end=""), task(removed, end="")],
    "pairs": [task(removed, dev="SecOps", start="", end="", cve="CVE-2026-1"),
              task("В работе", end="", cve="CVE-2026-1"),
              task(removed, cve="CVE-2026-2", ai_verdict="affected"),
              task(removed, cve="CVE-2026-2", ai_verdict="not affected", ai_run="2026-11-05")],
    "invalid-end": [task("В работе", start="2026-03-02", end="", tdate="2026-03-02"),
                    task(removed, dev="SecOps", start="", end="2026-02-30", tdate="2026-03-02", bad=["end"])],
}
for name, rows in fixtures.items():
    for i, row in enumerate(rows):
        row.update(row=i + 2, cve=row.get("cve", "CVE-2026-%d" % (9000 + i)), task="TASK-%d" % i)
    meta = dict(version="test", source="removed", as_of="2026-11-05", skipped=0, bad_dates=0, missing=[])
    (out / (name + ".html")).write_text(page.render(dict(meta=meta, rows=rows)), encoding="utf-8")
