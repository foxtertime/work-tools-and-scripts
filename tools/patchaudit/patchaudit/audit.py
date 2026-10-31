"""Последний билд Koji → PATCH его ветки → рекомендации по Red Hat VEX."""
import logging
from collections import Counter
from pathlib import PurePosixPath

from . import __version__, kojiclient, vex
from .cveid import cves_of
from .decisions import classify, patch_action
from .sourceurl import SourceUrlError, parse_source_url

logger = logging.getLogger(__name__)


def run(package, target_nvr, tag, rhel, session, client,
        settings=vex.VexSettings(), stream=None, aliases=()):
    report = {
        "format": 1, "tool_version": __version__, "complete": True,
        "request": {"mode": "nvr" if target_nvr else "package", "package": package,
                    "target_nvr": target_nvr, "tag": tag, "rhel": rhel,
                    "stream": stream, "aliases": list(aliases)},
        "latest_build": None, "source": None,
        "patch_directory": {"path": client.patch_dir, "present": None},
        "patches": [], "cves": [], "ignored_files": [], "summary": {}, "problems": [],
    }

    def problem(stage, message, **details):
        report["complete"] = False
        report["problems"].append({"stage": stage, "message": message, **details})
        logger.warning("%s: %s", stage, message)

    latest = kojiclient.latest_builds(session, tag, [package])[package]
    if latest in (kojiclient.NOT_FOUND, kojiclient.ERROR):
        problem("koji", "последний билд не найден" if latest == kojiclient.NOT_FOUND else "ошибка запроса последнего билда")
        return _finish(report)
    report["latest_build"] = latest
    logger.info("koji: %s → %s в теге %s", package, latest, tag)
    try:
        info = kojiclient.build_infos(session, [latest])[latest]
    except kojiclient.KojiError as exc:
        problem("koji", str(exc))
        return _finish(report)
    if info is None:
        problem("koji", "не получены детали билда %s" % latest)
        return _finish(report)
    raw = ((info.get("extra") or {}).get("source") or {}).get("original_url")
    try:
        parsed = parse_source_url(raw)
    except SourceUrlError as exc:
        problem("source", str(exc))
        return _finish(report)
    report["source"] = {"host": parsed.host, "project": parsed.project,
                        "branch": parsed.ref if parsed.ref_kind == "branch" else None}
    if parsed.ref_kind != "branch":
        problem("source", "источник билда не указывает ветку (тип %s)" % parsed.ref_kind)
        return _finish(report)

    logger.info("GitLab: %s/%s, ветка %s, каталог %s", parsed.host, parsed.project,
                parsed.ref, client.patch_dir)
    tree = client.patch_files(parsed.host, parsed.project, parsed.ref)
    report["patch_directory"]["present"] = tree.present
    if tree.problem:
        # Подмена хоста, разрешённая конфигом, — предупреждение, не сбой.
        if tree.present is None:
            problem("gitlab", tree.problem)
        else:
            logger.warning("%s", tree.problem)
            report["source"]["warning"] = tree.problem
    if tree.present is None:
        if not tree.problem:
            problem("gitlab", "каталог патчей не прочитан")
        return _finish(report)
    files = {}
    for path in sorted(set(tree.paths)):
        cves = cves_of(PurePosixPath(path).name)
        if cves:
            files[path] = cves
        else:
            report["ignored_files"].append(path)
    cves = sorted({cve for ids in files.values() for cve in ids})
    if not cves:
        return _finish(report)
    indices, failures = vex.fetch_all(cves, settings)
    decisions = {}
    for cve in cves:
        if cve in failures:
            verdict = vex.Verdict(state=vex.FETCH_ERROR)
            fixes = []
            problem("vex", failures[cve], cve=cve)
        else:
            try:
                verdict = vex.lookup(indices[cve], package, rhel, stream, aliases)
                fixes = vex.fixed_releases(indices[cve], package, rhel, stream, aliases)
            except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
                verdict, fixes = vex.Verdict(state=vex.FETCH_ERROR), []
                problem("vex", "не удалось разобрать документ: %s" % exc, cve=cve)
                vex._evict_cache(settings.cache_dir, cve)
        decision = classify(verdict.state, fixes, target_nvr)
        decisions[cve] = decision["action"]
        report["cves"].append({"cve": cve, "status": verdict.state,
                               "vex_url": vex.vex_url(cve), "fixes": fixes, **decision})
    report["patches"] = [{"path": path, "cves": ids,
                          "action": patch_action(decisions[cve] for cve in ids)}
                         for path, ids in files.items()]
    return _finish(report)


def _finish(report):
    report["summary"] = {"patches": len(report["patches"]), "cves": len(report["cves"]),
                         "actions": dict(sorted(Counter(p["action"] for p in report["patches"]).items()))}
    return report
