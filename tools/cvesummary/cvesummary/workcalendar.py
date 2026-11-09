"""Производственный календарь РФ: загрузка при сборке, автономный HTML."""
import datetime as dt
import logging
from http.client import HTTPException
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.request import urlopen
from xml.etree import ElementTree as ET

SOURCE = 'https://xmlcalendar.ru/'
BUNDLED = Path(__file__).parent / 'assets' / 'calendar'
MAX_BYTES = 65536
MAX_AGE = 7 * 86400
logger = logging.getLogger('cvesummary')


def parse(raw: bytes, year: int) -> dict:
    """Sparse XML overrides; unlisted days follow the ordinary five-day week."""
    if len(raw) > MAX_BYTES or b'<!DOCTYPE' in raw.upper():
        raise ValueError('слишком большой календарь или запрещённый DTD')
    try:
        root = ET.fromstring(raw)
        if (root.tag != 'calendar' or root.get('year') != str(year)
                or root.get('country', 'ru') != 'ru'):
            raise ValueError('неверный год или страна календаря')
        holidays = {h.get('id'): h.get('title') for h in root.findall('holidays/holiday')}
        days = {}
        for item in root.findall('days/day'):
            month_day = item.get('d', '')
            if not re.fullmatch(r'\d{2}\.\d{2}', month_day):
                raise ValueError('неверная дата календаря')
            date = dt.date(year, int(month_day[:2]), int(month_day[3:]))
            key, kind = date.isoformat(), item.get('t')
            if key in days or kind not in ('1', '2', '3'):
                raise ValueError('повтор даты или неизвестный тип дня')
            label = holidays.get(item.get('h'))
            if item.get('h') and not label:
                raise ValueError('неизвестный праздник')
            if not label and item.get('f'):
                moved = item.get('f')
                if not re.fullmatch(r'\d{2}\.\d{2}', moved):
                    raise ValueError('неверная дата переноса')
                dt.date(year, int(moved[:2]), int(moved[3:]))
                label = 'Перенесённый выходной с %s.%s' % (moved[3:], moved[:2])
            label = label or {'1': 'Нерабочий день', '2': 'Сокращённый рабочий день',
                              '3': 'Рабочий день по переносу'}[kind]
            days[key] = dict(working=kind != '1', label=label)
        if not days:
            raise ValueError('пустой календарь')
        return days
    except (ET.ParseError, TypeError, LookupError) as exc:
        raise ValueError('неверный XML календаря') from exc


def _read(path: Path, year: int):
    try:
        with path.open('rb') as handle:
            return parse(handle.read(MAX_BYTES + 1), year)
    except (OSError, ValueError):
        return None


def _save(path: Path, raw: bytes):
    """Не оставляем половину кеша после прерванной записи."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.calendar-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_year(year: int, cache_dir: Path):
    path = Path(cache_dir) / ('ru-%d.xml' % year)
    cached = _read(path, year)
    try:
        if cached is not None and 0 <= time.time() - path.stat().st_mtime < MAX_AGE:
            return cached
    except OSError:
        pass
    try:
        with urlopen(SOURCE + 'data/ru/%d/calendar.xml' % year, timeout=3) as response:
            raw = response.read(MAX_BYTES + 1)
        days = parse(raw, year)
    except (OSError, ValueError, HTTPException) as exc:
        fallback = cached if cached is not None else _read(BUNDLED / ('ru-%d.xml' % year), year)
        logger.warning('календарь РФ %d: %s; %s', year, exc,
                       'используется сохранённая копия' if fallback is not None else 'нет данных, используется Пн–Пт')
        return fallback
    try:
        _save(path, raw)
    except OSError as exc:
        logger.warning('календарь РФ %d загружен, но кеш не записан: %s', year, exc)
    return days


def load(rows, as_of: dt.date, cache_dir=None) -> dict:
    if cache_dir is None:
        cache_dir = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'cvesummary'
    first = as_of.year
    for row in rows:
        for key in ('tdate', 'start', 'end'):
            if key in row.get('bad', []):
                continue
            try:
                date = dt.date.fromisoformat(row.get(key) or '')
                first = min(first, date.year)
            except ValueError:
                pass
    result = dict(country='RU', source=SOURCE, years=[], missing=[], days={})
    # Сервис публикует годы с 2013; ещё не наступившие дальние годы не запрашиваем.
    last_published = dt.date.today().year + 1
    for year in range(first, min(9999, as_of.year + 1) + 1):
        days = load_year(year, cache_dir) if 2013 <= year <= last_published else None
        if days is None:
            result['missing'].append(year)
        else:
            result['years'].append(year)
            result['days'].update(days)
    logger.info('производственный календарь РФ: %s', ', '.join(map(str, result['years'])) or 'нет данных')
    if result['missing']:
        logger.warning('без календаря РФ, используется Пн–Пт: %s', ', '.join(map(str, result['missing'])))
    return result
