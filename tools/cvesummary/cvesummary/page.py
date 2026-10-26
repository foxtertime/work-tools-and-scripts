"""Страница сводки одним файлом: шаблон, стили, скрипты и данные.

Данные — JSON в <script type="application/json">; «<», «>» и «&» в нём
заменены \\u-последовательностями, поэтому ячейка с «</script>» или «<!--»
блок не закроет. Маркеры заменяются только в шаблоне: в стилях и скриптах
такие же строки ни на что не влияют.
"""
import json
import os
import re

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
# порядок важен: модуль ниже пользуется теми, что выше
SCRIPTS = ("dates.js", "roles.js", "hours.js", "pace.js", "timeline.js", "nav.js", "strips.js", "ai.js", "render.js", "drilldown.js")
_CSS, _DATA, _JS = "/*@css*/", "@data@", "/*@js*/"


def data_json(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render(data: dict) -> str:
    template = _asset("summary.html")
    parts = {
        _CSS: _asset("summary.css"),
        _DATA: data_json(data),
        _JS: "\n".join(_asset(os.path.join("js", name)) for name in SCRIPTS),
    }
    for marker in parts:
        if template.count(marker) != 1:
            raise RuntimeError("шаблон summary.html: маркер %s должен встречаться один раз" % marker)
    pattern = re.compile("|".join(re.escape(marker) for marker in parts))
    return pattern.sub(lambda match: parts[match.group(0)], template)


def _asset(name: str) -> str:
    with open(os.path.join(ASSETS, name), encoding="utf-8") as handle:
        return handle.read()
