"""Последние билды пакетов в koji-теге. Доступ только на чтение."""
import logging
import time
from typing import Dict, Iterable

logger = logging.getLogger(__name__)

NOT_FOUND = "NOT_FOUND"
ERROR = "ERROR"


class KojiError(Exception):
    """Хаб недоступен, тега нет или не установлен модуль koji."""


def connect(hub_url: str):
    try:
        import koji  # системный пакет python3-koji; нужен только здесь
    except ImportError as exc:
        raise KojiError("не установлен модуль koji (python3-koji): %s" % exc)
    return koji.ClientSession(hub_url)


def latest_builds(session, tag: str, packages: Iterable[str]) -> Dict[str, str]:
    """{пакет: NVR последнего билда в теге | NOT_FOUND | ERROR}.

    Каждый пакет спрашивается один раз, все — одним multicall.
    """
    packages = list(dict.fromkeys(packages))
    if not packages:
        return {}
    started = time.monotonic()
    try:
        if session.getTag(tag) is None:
            raise KojiError("в koji нет тега %s" % tag)
        with session.multicall(strict=False) as multicall:
            calls = [multicall.getLatestBuilds(tag, package=pkg) for pkg in packages]
    except KojiError:
        raise
    except Exception as exc:
        raise KojiError("хаб не ответил по тегу %s: %s" % (tag, exc))
    logger.debug("getLatestBuilds %s: %d пакетов за %.2f с", tag, len(packages),
                 time.monotonic() - started)

    result = {}
    for pkg, call in zip(packages, calls):
        try:
            builds = call.result
        except Exception as exc:  # ошибка по одному пакету не роняет остальные
            logger.warning("koji не ответил по пакету %s: %s", pkg, exc)
            result[pkg] = ERROR
            continue
        result[pkg] = builds[0]["nvr"] if builds else NOT_FOUND

    missing = [pkg for pkg in packages if result[pkg] == NOT_FOUND]
    if missing:
        logger.warning("в теге %s нет пакетов (%d): %s", tag, len(missing),
                       ", ".join(missing))
    return result
