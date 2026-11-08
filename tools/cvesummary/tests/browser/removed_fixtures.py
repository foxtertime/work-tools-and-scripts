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
    "inflow": [task("В работе", end="", sev="Low"), task(tdate="2026-11-03"),
               task(removed, dev="", start="", end="", tdate="2026-10-18"),
               task(removed, dev="SecOps", tdate="2026-11-02"), task(removed, tdate="2026-11-02"),
               task(removed, end="", tdate="2026-11-06"), task(removed, end="", tdate=""),
               task(removed, end="", tdate="2026-02-30", bad=["tdate"])],
    "ai": [task(ai_verdict="not affected", cve="CVE-2026-shared"), task(ai_verdict="affected"),
           task(removed, ai_verdict="not affected"),
           task(removed, dev="SecOps", ai_verdict=" AFFECTED ", cve="CVE-2026-shared"),
           task(removed, end="", ai_verdict="unclear", cve="CVE-2026-shared"),
           task(removed, end="", ai_verdict="custom verdict"),
           task(removed, end="", ai_verdict="Not Affected"),
           task(removed, end="", ai_verdict="invalid CVE"),
           task(removed, end="", ai_verdict="REJECTED CVE"),
           task(removed, end="", ai_verdict="not processed"), task(removed, end="")],
    "missing-ai": [task(removed, end="")],
    "measures": [task(measure="Патч из апстрима"), task(measure="Импорт новой версии"),
                 task(removed), task(removed, measure=" патч  из АПСТРИМА "),
                 task(removed, measure="Импорт новой версии"), task(removed, measure=""),
                 task(removed, measure='Своя "мера"'), task(removed, dev="SecOps", measure="Только SecOps"),
                 task(removed, end="", measure="Незавершённая мера")],
    "unbalanced": [task(removed)] + [task(removed, dev="SecOps") for _ in range(19)],
    "scope": [task(comp="kept", cve="CVE-2026-1", sev="Low"),
              task("В работе", comp="kept", cve="CVE-2026-2", sev="Low", end=""),
              task(removed, comp="kept", cve="CVE-2026-1", sev="Critical", ai_verdict="affected", ai_run="2026-11-05"),
              task(removed, dev="Ghost", start="2025-01-01", end="", comp="removed-only", sev="Critical", rstate="Fixed", p="+", measure="Убранная мера"),
              task(removed, dev="SecOps", start="2025-01-01", end="2025-01-02", comp="removed-only", sev="Critical"),
              task(removed, start="bad", end="bad", bad=["start", "end"], comp="removed-only", sev="Critical")],
    "speed-only": [task(removed), task(removed, dev="SecOps"), task(removed, dev="Ghost", end="")],
    "empty": [],
    "ordinary": [task(), task("В работе", end="")],
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
fixtures["inflow-no-dates"] = [dict(r, **({"tdate": ""} if r["status"] == removed else {})) for r in fixtures["inflow"]]
for name, rows in fixtures.items():
    for i, row in enumerate(rows):
        row.update(row=i + 2, cve=row.get("cve", "CVE-2026-%d" % (9000 + i)), task="TASK-%d" % i)
    meta = dict(version="test", source="removed", as_of="2026-11-05", skipped=0, bad_dates=0, missing=[])
    if name == "missing-ai":
        meta["missing"] = ["ai_verdict", "ai_rem"]
    (out / (name + ".html")).write_text(page.render(dict(meta=meta, rows=rows)), encoding="utf-8")
