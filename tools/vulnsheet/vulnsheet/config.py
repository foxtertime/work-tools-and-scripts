"""Конфиг vulnsheet: YAML, все поля необязательные.

Модуль читает и проверяет файл; сводит его с флагами командной строки cli.
PyYAML импортируется только при заданном файле: без конфига тулзе хватает
стандартной библиотеки и koji.
"""
import math
import os
import types
from typing import Dict, Mapping, NamedTuple, Optional

from .vex import VexSettings, parse_rhel

ENV_VAR = "VULNSHEET_CONFIG"

_TOP_KEYS = {"koji", "rhel", "vex", "vex_streams"}
_KOJI_KEYS = {"hub", "tag"}
_VEX_KEYS = {"cache_dir", "cache_ttl", "jobs", "retries", "timeout"}


class ConfigError(Exception):
    """Конфиг не найден, не читается или не проходит проверку."""


class Config(NamedTuple):
    path: Optional[str] = None
    koji_hub: Optional[str] = None
    koji_tag: Optional[str] = None
    rhel: Optional[str] = None
    vex: VexSettings = VexSettings()
    # ключ — нормализованная версия RHEL; неизменяемое отображение, поэтому
    # безопасно делить между экземплярами
    vex_streams: Mapping[str, Mapping[str, str]] = types.MappingProxyType({})

    def stream_for(self, component: str, rhel: str) -> Optional[str]:
        """Стрим VEX для компонента — только из набора ровно этой версии RHEL.

        Отката нет: для 9.2 набор "9" не применяется, и наоборот.
        """
        return self.vex_streams.get(rhel, {}).get(component)


def load_config(path: Optional[str]) -> Config:
    if path is None:
        return Config()
    raw = _read_yaml(path)
    if raw is None:  # пустой файл
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("%s: корень конфига должен быть словарём" % path)
    _check_keys(raw, _TOP_KEYS, "", path)
    koji = _section(raw, "koji", path)
    _check_keys(koji, _KOJI_KEYS, "koji.", path)
    vex = _section(raw, "vex", path)
    _check_keys(vex, _VEX_KEYS, "vex.", path)

    defaults = VexSettings()
    cache_dir = _string(vex, "cache_dir", "vex.cache_dir", path)
    settings = VexSettings(
        cache_dir=os.path.expanduser(cache_dir) if cache_dir else None,
        cache_ttl=_integer(vex, "cache_ttl", "vex.cache_ttl", path, 0, defaults.cache_ttl),
        jobs=_integer(vex, "jobs", "vex.jobs", path, 1, defaults.jobs),
        retries=_integer(vex, "retries", "vex.retries", path, 1, defaults.retries),
        timeout=_timeout(vex, path, defaults.timeout),
    )
    return Config(
        path=path,
        koji_hub=_string(koji, "hub", "koji.hub", path),
        koji_tag=_string(koji, "tag", "koji.tag", path),
        rhel=_rhel(raw.get("rhel"), "rhel", path),
        vex=settings,
        vex_streams=_streams(raw.get("vex_streams"), path),
    )


def _read_yaml(path):
    try:
        import yaml  # только при заданном конфиге
    except ImportError:
        raise ConfigError("для конфига нужен PyYAML: поставьте python3-pyyaml "
                          "(или pip install pyyaml)")

    class _StrictLoader(yaml.SafeLoader):
        """safe_load молча берёт последний из двух одинаковых ключей на любом
        уровне (в т. ч. "9" дважды под vex_streams или пакет дважды в одном
        наборе) — тихо теряя данные. Здесь это фатальная ошибка конфига.

        Ключи 9 и "9" — разные объекты Python и дублем не считаются: этот
        случай ловится отдельно, после нормализации версии, в _streams.
        """

        def construct_mapping(self, node, deep=False):
            seen = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=True)
                if key in seen:
                    raise ConfigError("%s: ключ %r указан дважды (строка %d)" % (
                        path, key, key_node.start_mark.line + 1))
                seen.add(key)
            return super().construct_mapping(node, deep=deep)

    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.load(handle, Loader=_StrictLoader)
    except OSError as exc:
        raise ConfigError("%s: не читается: %s" % (path, exc))
    except (yaml.YAMLError, ValueError) as exc:  # ValueError — не UTF-8
        raise ConfigError("%s: ошибка YAML: %s" % (path, exc))


def _check_keys(section, allowed, prefix, path):
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        raise ConfigError("%s: неизвестный ключ %s" % (
            path, ", ".join(prefix + key for key in unknown)))


def _section(raw, key, path):
    value = raw.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("%s: %s должен быть словарём" % (path, key))
    return value


def _string(section, key, name, path):
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("%s: %s должен быть непустой строкой" % (path, name))
    return value.strip()


def _integer(section, key, name, path, minimum, default):
    value = section.get(key)
    if value is None:
        return default
    # bool в питоне — подкласс int: «jobs: true» не должно стать единицей
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("%s: %s должен быть целым числом" % (path, name))
    if value < minimum:
        raise ConfigError("%s: %s должен быть не меньше %d" % (path, name, minimum))
    return value


def _timeout(section, path, default):
    value = section.get("timeout")
    if value is None:
        return default
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ConfigError("%s: vex.timeout должен быть числом больше нуля" % path)
    return value


def _rhel(value, name, path):
    """Версия RHEL строкой или целым; число с точкой — ошибка: YAML читает
    9.10 как 9.1, и версия молча стала бы другой."""
    if value is None:
        return None
    if isinstance(value, float):
        raise ConfigError('%s: %s — версию с точкой пишите в кавычках: "9.2"' % (path, name))
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ConfigError('%s: %s — версия RHEL строкой, например "9" или "9.2"'
                          % (path, name))
    try:
        return parse_rhel(str(value))
    except ValueError as exc:
        raise ConfigError("%s: %s: %s" % (path, name, exc))


def _streams(value, path):
    if value is None:
        return types.MappingProxyType({})
    if not isinstance(value, dict):
        raise ConfigError("%s: vex_streams должен быть словарём версия → пакеты" % path)
    result = {}
    for key, mapping in value.items():
        name = "vex_streams.%s" % key
        rhel = _rhel(key, name, path)
        if rhel is None:
            raise ConfigError("%s: %s — нужна версия RHEL" % (path, name))
        if rhel in result:
            raise ConfigError("%s: в vex_streams версия %s указана дважды" % (path, rhel))
        if mapping is None:
            mapping = {}
        if not isinstance(mapping, dict):
            raise ConfigError("%s: %s должен быть словарём пакет → стрим" % (path, name))
        streams = {}
        for package, stream in mapping.items():
            # число без кавычек — частая опечатка: "1.26" YAML читает как
            # float, и это надо явно подсказать, а не просто отвергнуть.
            if isinstance(stream, (int, float)) and not isinstance(stream, bool):
                raise ConfigError('%s: %s: стрим пишите в кавычках, например "1.26" (%r: %r)'
                                  % (path, name, package, stream))
            if (not isinstance(package, str) or not package.strip()
                    or not isinstance(stream, str) or not stream.strip()):
                raise ConfigError("%s: %s: пакет и стрим — непустые строки (%r: %r)"
                                  % (path, name, package, stream))
            streams[package.strip()] = stream.strip()
        result[rhel] = types.MappingProxyType(streams)
    return types.MappingProxyType(result)
