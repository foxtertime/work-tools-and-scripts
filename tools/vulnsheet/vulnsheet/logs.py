"""Настройка логирования — единственное место, где ставятся хендлеры.

Модули пакета только пишут через logging.getLogger(__name__); настраивает
всё исключительно CLI, чтобы импорт пакета чужим кодом не менял его
логирование.
"""
import logging
import sys

ROOT = "vulnsheet"
DEFAULT_LEVEL = "info"
LEVELS = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

_TIME_FORMAT = "%H:%M:%S"
_FORMAT = "%(asctime)s %(levelname)-7s %(shortname)s: %(message)s"
# VEX грузится пулом потоков: без имени потока дебажный лог не читается
_DEBUG_FORMAT = ("%(asctime)s %(levelname)-7s [%(threadName)s] "
                 "%(shortname)s: %(message)s")


class _ShortName(logging.Filter):
    """vulnsheet.kojiclient → koji, vulnsheet.cli → cli."""

    def filter(self, record) -> bool:
        name = record.name.split(".")[-1]
        if name.endswith("client"):
            name = name[:-len("client")]
        record.shortname = name
        return True


def configure(level: str = DEFAULT_LEVEL, stream=None) -> None:
    """Ставит единственный хендлер на логгер пакета.

    Повторный вызов заменяет хендлер, а не добавляет второй: иначе тесты и
    повторная инициализация давали бы дублирующиеся строки.
    """
    if level not in LEVELS:
        raise ValueError("неизвестный уровень логирования: %s" % level)
    numeric = LEVELS[level]

    logger = logging.getLogger(ROOT)
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    fmt = _DEBUG_FORMAT if numeric <= logging.DEBUG else _FORMAT
    handler.setFormatter(logging.Formatter(fmt, _TIME_FORMAT))
    handler.addFilter(_ShortName())
    handler.setLevel(numeric)

    logger.addHandler(handler)
    logger.setLevel(numeric)
    # записи пакета не должны уходить в корневой логгер: если приложение
    # настроило свой basicConfig, строки задвоятся
    logger.propagate = False
