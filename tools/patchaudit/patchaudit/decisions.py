"""Решения по CVE и файлам патчей. Без сети и файлового ввода-вывода."""
import re
from typing import NamedTuple, Optional

from .rpmvercmp import rpmvercmp


class Nvr(NamedTuple):
    name: str
    version: str
    release: str


def parse_nvr(value: str) -> Nvr:
    parts = value.rsplit("-", 2)
    if (len(parts) != 3 or not re.fullmatch(r"[A-Za-z0-9_+.][A-Za-z0-9_+.-]*", parts[0])
            or any(not re.fullmatch(r"[A-Za-z0-9_+.~^]+", p) for p in parts[1:])
            or parts[2].endswith((".rpm", ".src", ".x86_64", ".aarch64", ".noarch"))):
        raise ValueError("нужен NVR вида NAME-VERSION-RELEASE без эпохи и архитектуры: %r" % value)
    return Nvr(*parts)


def compare_target(target: str, fixed: str) -> Optional[int]:
    """Сравнение VERSION-RELEASE; None, если disttag не позволяет сравнить.

    В целевом release SL соответствует EL; суффикс пересборки ^N отбрасывается.
    Исходный NVR сохраняется в отчёте. Иные disttag остаются несравнимыми.
    Эпохи в NVR нет: здесь намеренно сравнивается VR, не EVR.
    """
    target, fixed = parse_nvr(target), parse_nvr(fixed)
    release = re.sub(r"\^[0-9]+$", "", target.release)
    target = target._replace(release=re.sub(r"(?<=[.+_])sl(?=[0-9])", "el", release))
    target_family, fixed_family = _release_family(target.release), _release_family(fixed.release)
    if target_family is None or target_family != fixed_family:
        return None
    version = rpmvercmp(target.version, fixed.version)
    return version or rpmvercmp(target.release, fixed.release)


def _release_family(release):
    # Разбирается весь release: .el9fdp и .el9.custom не являются RHEL.
    ordinary = re.fullmatch(r"\d+(?:\.\d+)*\.el(\d+)(?:_\d+)*(?:\.\d+)*", release)
    if ordinary:
        return "rpm", ordinary[1]
    module = re.fullmatch(r"\d+(?:\.\d+)*\.module[+_]el(\d+)(?:\.\d+){1,2}\+\d+\+[0-9a-f]+", release)
    return ("module", module[1]) if module else None


def classify(state: str, fixes: list, target: Optional[str]) -> dict:
    result = {"action": "review", "reason": "unknown_status",
              "fixed_in_target": [], "fixed_after_target": []}
    if state != "Fixed":
        if state in {"Affected", "Fix deferred", "Will not fix", "Out of support scope", "Under investigation"}:
            result.update(action="keep", reason="redhat_not_fixed")
        else:
            result["reason"] = "redhat_not_affected" if state == "Not affected" else "no_reliable_verdict"
        return result
    if not fixes or (target is None and any(not f.get("nvr") for f in fixes)):
        result["reason"] = "no_fixed_version"
        return result
    if target is None:
        result.update(action="fixed", reason="redhat_fix_available")
        return result
    required, covered, comparable = set(), set(), set()
    for fix in fixes:
        groups = set(fix.get("products") or ["package"])
        required.update(groups)
        relation = compare_target(target, fix["nvr"]) if fix.get("nvr") else None
        if relation is not None:
            result["fixed_in_target" if relation >= 0 else "fixed_after_target"].append(fix)
            comparable.update(groups)
            if relation >= 0:
                covered.update(groups)
    if required <= covered:
        result.update(action="remove", reason="target_includes_redhat_fix")
    elif required <= comparable:
        result.update(action="remove_on_upgrade", reason="target_older_than_redhat_fix")
    else:
        result["reason"] = "incomparable_release"
    return result


def patch_action(actions) -> str:
    """Файл удаляется, только если исправлена каждая CVE из его имени."""
    actions = set(actions)
    for action in ("keep", "review", "remove_on_upgrade", "fixed", "remove"):
        if action in actions:
            return action
    return "review"
