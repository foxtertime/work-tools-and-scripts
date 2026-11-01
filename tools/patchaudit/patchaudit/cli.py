"""CLI patchaudit: JSON в stdout/файл, журнал в stderr."""
import argparse
import json
import logging
import os
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit

from . import __version__, audit, config, httpclient, kojiclient, logs, vex, vmaas
from .decisions import parse_nvr
from .gitlabclient import GitlabClient, GitlabHost

logger = logging.getLogger(__name__)


def _package(value):
    if not re.fullmatch(r"[A-Za-z0-9_+.][A-Za-z0-9_+.-]*", value):
        raise argparse.ArgumentTypeError("нужно имя RPM-пакета")
    return value


def _parser():
    parser = argparse.ArgumentParser(description="Проверить актуальность CVE-патчей по Red Hat VEX")
    parser.add_argument("--version", action="version", version="patchaudit " + __version__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--package", type=_package, help="имя пакета: показать все доступные фиксы Red Hat")
    inputs.add_argument("--nvr", help="целевой NAME-VERSION-RELEASE: разделить фиксы по версии обновления")
    parser.add_argument("--config", help="YAML-конфиг, иначе $PATCHAUDIT_CONFIG")
    parser.add_argument("--koji-url", help="URL kojihub")
    parser.add_argument("--tag", help="Koji-тег с последним билдом пакета")
    parser.add_argument("--rhel", help="точная версия RHEL: 9, 9.2 и т. п.")
    parser.add_argument("--arch", help="архитектура билда RHEL в VMaaS, по умолчанию x86_64")
    parser.add_argument("--gitlab-url", help="адрес GitLab или его API v4; токен в gitlab.token YAML-конфига")
    parser.add_argument("--patch-dir", help="каталог патчей, по умолчанию PATCH")
    parser.add_argument("--stream", help="стрим VEX и VMaaS, например nginx:1.26")
    parser.add_argument("--vex-name", action="append", help="другое имя пакета в VEX; можно повторять")
    parser.add_argument("-o", "--output", default="-", help="JSON-файл, по умолчанию stdout")
    parser.add_argument("--log-level", choices=logs.LEVELS, default="info")
    return parser


def _gitlab_settings(args, cfg):
    settings = cfg.gitlab
    if args.gitlab_url:
        url = args.gitlab_url.rstrip("/")
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("--gitlab-url: нужен URL HTTP(S) без учётных данных, query и fragment")
        api = url if url.endswith("/api/v4") else url + "/api/v4"
        settings = (settings or config.GitlabSettings(hosts={}))._replace(
            hosts={"*": GitlabHost(api)}, default_host="*")
    if settings is None:
        raise ValueError("нужен --gitlab-url или секция gitlab в конфиге")
    if args.patch_dir is not None:
        if not args.patch_dir.strip():
            raise ValueError("--patch-dir не может быть пустым")
        settings = settings._replace(patch_dir=args.patch_dir.strip())
    return settings


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code
    logs.configure(args.log_level)
    handle, temp_path, final_path = None, None, None
    try:
        target = parse_nvr(args.nvr) if args.nvr is not None else None
        package = target.name if target else args.package
        cfg = config.load_config(args.config or os.environ.get(config.ENV_VAR) or None)
        rhel = vex.parse_rhel(args.rhel or cfg.rhel or "")
        arch = args.arch if args.arch is not None else cfg.vmaas.arch
        if not re.fullmatch(r"[A-Za-z0-9_]+", arch):
            raise ValueError("--arch: нужно имя архитектуры, например x86_64")
        hub, tag = args.koji_url or cfg.koji_hub, args.tag or cfg.koji_tag
        if not hub or not tag:
            raise ValueError("нужны --koji-url и --tag или koji.hub и koji.tag в конфиге")
        gitlab = _gitlab_settings(args, cfg)
        stream = args.stream if args.stream is not None else cfg.stream_for(package, rhel)
        aliases = tuple(args.vex_name) if args.vex_name is not None else cfg.names_for(package)
        if (stream is not None and not stream.strip()) or any(not alias.strip() for alias in aliases):
            raise ValueError("стрим и имена VEX не могут быть пустыми")

        # Проверить возможность создать файл до сетевых запросов.
        if args.output != "-":
            final_path = os.path.realpath(args.output)
            if os.path.isdir(final_path):
                raise ValueError("выход — каталог: %s" % args.output)
            handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="",
                                                  dir=os.path.dirname(final_path),
                                                  prefix=".patchaudit-", suffix=".tmp", delete=False)
            temp_path = handle.name
        else:
            handle = sys.stdout
        cache_base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        cache = vex.prepare_cache(cfg.vex.cache_dir or os.path.join(cache_base, "patchaudit"))
        settings = cfg.vex._replace(cache_dir=cache)
        rhel_settings = cfg.vmaas._replace(
            arch=arch, cache_dir=cfg.vmaas.cache_dir or (os.path.join(cache, "vmaas") if cache else None))
        rhel_client = vmaas.VmaasClient(rhel_settings)
        token = gitlab.token
        client = GitlabClient(dict(gitlab.hosts), token=token, patch_dir=gitlab.patch_dir,
                              transport=httpclient.UrllibTransport(timeout=gitlab.timeout),
                              retries=gitlab.retries, default_host=gitlab.default_host)
        logger.info("patchaudit %s: %s%s, тег %s, RHEL %s", __version__, package,
                    " → " + args.nvr if target else " (все фиксы)", tag, rhel)
        session = kojiclient.connect(hub)
        result = audit.run(package, args.nvr, tag, rhel, session, client, settings,
                           stream=stream, aliases=aliases, rhel_client=rhel_client)
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        if temp_path:
            handle.close()
            if os.path.exists(final_path):
                os.chmod(temp_path, stat.S_IMODE(os.stat(final_path).st_mode))
            os.replace(temp_path, final_path)
            temp_path = None
        code = 0 if result["complete"] else 1
        logger.info("итог: CVE %d, патчей %d, решения %s, код %d", result["summary"]["cves"],
                    result["summary"]["patches"], result["summary"]["actions"], code)
        return code
    except (ValueError, OSError, config.ConfigError, kojiclient.KojiError) as exc:
        logger.error("%s", exc)
        return 2
    finally:
        if handle is not None and handle is not sys.stdout and not handle.closed:
            handle.close()
        if temp_path is not None:
            os.unlink(temp_path)
