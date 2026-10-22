"""Чтение JSON с AI-вердиктами — входа колонок ai_*.

Файл — объект с "format": 1 и списком "results"; в каждом результате cve и
package — ключ, по которому он ложится на строки таблицы (CVE без пробелов
по краям и в верхнем регистре, компонент без пробелов по краям, как пары в
merge), и пять полей для колонок: nvr, verdict, confidence, remediation,
run. Поля пишутся как есть, только run — датой dd.mm.yyyy, как остальные
даты таблицы; нет поля, null, пустая строка или «—» (так плагин пишет «нет
значения») — '-'. Время файла — его "run" (запасной вариант — "generated").
Результат без годных cve или package пропускается с причиной; если пара
повторяется, действует самый свежий по run (время с поясом — в UTC), при
равном или неразобранном run — первый. Файл, который не читается, не
JSON или не этого формата, — AiError.
"""
import json
from datetime import datetime, timezone
from typing import Dict, NamedTuple, Optional, Tuple

from .report import EMPTY, format_date
from .tasks import CVE_RE

FORMAT = 1
FIELDS = ("nvr", "verdict", "confidence", "remediation", "run")
RUN = FIELDS.index("run")  # '2026-10-21T12:04' → '21.10.2026'; не ISO — как есть

Pair = Tuple[str, str]  # (CVE, компонент)


class AiError(Exception):
    """Файл AI не читается или не в ожидаемом формате."""


class Skipped(NamedTuple):
    """Пропущенный результат: номер в results (с 1) и почему."""
    number: int
    reason: str


class Found(NamedTuple):
    cells: Dict[Pair, Tuple[str, ...]]  # пара → значения колонок ai_*
    plugin: Optional[str]
    run: Optional[str]                  # когда записан файл: его "run"
    total: int                          # результатов в файле
    skipped: Tuple[Skipped, ...] = ()
    repeated: int = 0                   # повторы пар — действует самый свежий


def read(path: str) -> Found:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            body = json.load(handle)
    except UnicodeDecodeError as exc:
        raise AiError("%s: не в UTF-8: %s" % (path, exc))
    except OSError as exc:
        raise AiError("%s: не читается: %s" % (path, exc))
    except ValueError as exc:
        raise AiError("%s: не JSON: %s" % (path, exc))
    if not isinstance(body, dict):
        raise AiError("%s: верхний уровень — не объект" % path)
    version = body.get("format")
    if version != FORMAT or isinstance(version, bool):
        raise AiError("%s: format %r, ожидается %d" % (path, version, FORMAT))
    results = body.get("results")
    if not isinstance(results, list):
        raise AiError("%s: нет списка results" % path)

    cells, runs, skipped, repeated = {}, {}, [], 0
    for number, result in enumerate(results, 1):
        pair, reason = _pair(result)
        if pair is None:
            skipped.append(Skipped(number, reason))
            continue
        values = [_text(result.get(name)) for name in FIELDS]
        run = _moment(values[RUN])
        if pair in cells:
            repeated += 1
            if run is None or (runs[pair] is not None and run <= runs[pair]):
                continue
        values[RUN] = format_date(values[RUN])
        cells[pair], runs[pair] = tuple(values), run
    return Found(cells, _meta(body.get("plugin")), _meta(body.get("run", body.get("generated"))),
                 len(results), tuple(skipped), repeated)


def _moment(run: str) -> Optional[datetime]:
    """Когда был прогон — для выбора самого свежего результата пары: время с
    поясом — в UTC, без пояса — как есть; не дата ISO — None."""
    try:
        moment = datetime.fromisoformat(run.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _pair(result) -> Tuple[Optional[Pair], str]:
    if not isinstance(result, dict):
        return None, "не объект"
    cve, package = (result.get(name) for name in ("cve", "package"))
    if not isinstance(cve, str) or not cve.strip():
        return None, "нет cve"
    if not CVE_RE.match(cve.strip().upper()):
        return None, "не CVE-ID: %r" % cve
    if not isinstance(package, str) or not package.strip():
        return None, "нет package"
    return (cve.strip().upper(), package.strip()), ""


def _text(value) -> str:
    """Значение для ячейки: строка — без пробелов по краям, прочее — как в
    JSON (true, 0.9, ["a"]); пустое и «—» — '-'."""
    if value is None:
        return EMPTY
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    value = value.strip()
    return EMPTY if value in ("", "—") else value


def _meta(value) -> Optional[str]:
    return None if value is None else str(value)
