"""Чтение каталога патчей из GitLab через REST v4. Доступ только на чтение.

Перенесено из тулзы dashboard (тулзы общего кода не делят) в урезанном
виде: нужно только дерево каталога патчей, без сравнения коммитов и
веб-ссылок.

Сам разговор по HTTP — повторы, паузы, чистка токена из сообщений — живёт
в httpclient.py. Здесь только знание о GitLab: как спросить дерево ветки и
как отличить «ветки нет» от «сервер не ответил».
"""
import logging
import threading
from typing import Dict, List, NamedTuple, Optional
from urllib.parse import quote

from .httpclient import HttpClient, server_message

logger = logging.getLogger(__name__)


class GitlabHost(NamedTuple):
    api: str   # https://gitlab.example.com/api/v4
    web: str   # https://gitlab.example.com


class TreeResult(NamedTuple):
    """present: True — каталог прочитан, False — в ветке его нет, None —
    неизвестно (problem объясняет почему). Уровень проблемы: error — дерева
    нет; warning — дерево есть, но с оговоркой (подменён хост)."""
    present: Optional[bool]
    paths: List[str]
    problem: Optional[str]
    level: str = "error"


def _tree_problem(problem: str, level: str = "error") -> TreeResult:
    """Дерево не прочиталось: причина есть, содержимого нет."""
    return TreeResult(None, [], problem, level)


class GitlabClient:
    def __init__(self, hosts: Dict[str, GitlabHost], token: Optional[str] = None,
                 patch_dir: str = "PATCH", transport=None, retries: int = 3,
                 sleeper=None, default_host: Optional[str] = None):
        self._hosts = hosts or {}
        self._token = token
        self._patch_dir = patch_dir
        kwargs = {} if sleeper is None else {"sleeper": sleeper}
        self._http = HttpClient(transport=transport, token=token,
                                retries=retries, **kwargs)
        self._default_host = default_host
        self._cache = {}
        self._lock = threading.Lock()

    def _resolve_host(self, host):
        """Конфиг хоста и, если хост подменён, заметка об этой подмене.

        Незнакомый хост спрашиваем у сервера по умолчанию: чаще всего это
        просто другое имя того же GitLab. Но если там окажется одноимённый
        проект (зеркало, переезд), ответ придёт из чужого репозитория, и
        отличить его от настоящего будет нельзя. Поэтому подстановку
        выполняем, но записываем в проблему.
        """
        if host in self._hosts:
            return self._hosts[host], None
        default = self._default_host
        if default and default in self._hosts:
            # «*» — осознанное «ходить сюда за всем», заметки не заслуживает
            note = None if default == "*" else (
                "gitlab: host %s не описан в конфиге, запрошен %s"
                % (host, default))
            return self._hosts[default], note
        if "*" in self._hosts:
            return self._hosts["*"], None
        return None, None

    def patch_files(self, host, project, ref) -> TreeResult:
        """Пути файлов внутри каталога патчей ref; результат мемоизируется."""
        if not ref:
            return _tree_problem("gitlab: no ref in source url")
        key = (host, project, ref)
        with self._lock:
            if key in self._cache:
                logger.debug("кэш: %s %s@%s", host, project, ref)
                return self._cache[key]
        result = self._fetch(host, project, ref)
        with self._lock:
            self._cache[key] = result
        return result

    def _fetch(self, host, project, ref) -> TreeResult:
        cfg, note = self._resolve_host(host)
        if cfg is None:
            return _tree_problem("gitlab: unknown host %s" % host)
        result = self._fetch_tree(cfg, project, ref)
        if not note:
            return result
        # заметка о подмене хоста не отменяет удачное чтение: present
        # остаётся тем, что вернул сервер, — просто появляется проблема.
        problem = note if not result.problem else "%s; %s" % (note, result.problem)
        # Подмена хоста сама по себе не отказ. Но когда под заметкой лежит
        # настоящий отказ, уровень остаётся его: склеенная строка говорит о
        # двух вещах сразу, и мягче из них она быть не может.
        level = result.level if result.problem else "warning"
        return TreeResult(result.present, result.paths, problem, level)

    def _fetch_tree(self, cfg, project, ref) -> TreeResult:
        url = "%s/projects/%s/repository/tree" % (
            cfg.api.rstrip("/"), quote(project, safe=""))
        headers = {"PRIVATE-TOKEN": self._token} if self._token else {}

        paths = []
        page = None
        while True:
            params = {"ref": ref, "path": self._patch_dir,
                      "recursive": "true", "per_page": "100"}
            if page:
                params["page"] = page
            response = self._http.get(url, headers, params)
            if isinstance(response, str):
                return _tree_problem(response)
            if response.status == 404:
                note = server_message(response)
                if "project not found" in note.lower():
                    return _tree_problem("gitlab: %s" % note)
                # Остальные 404 неоднозначны: «в ветке нет каталога» и «нет
                # самой ветки» приходят одинаковым кодом, а формулировка
                # зависит от версии GitLab — «404 Tree Not Found», «404
                # invalid revision or path Not Found», иногда пустое тело.
                # Поэтому решает не текст, а отдельный запрос к ветке.
                return self._resolve_missing_tree(cfg, project, ref, headers)
            if response.status >= 400:
                return _tree_problem("gitlab: %s %s" % (response.status,
                                                        server_message(response)))
            for item in response.body or []:
                if item.get("type") == "blob":
                    paths.append(item["path"])
            page = (response.headers or {}).get("x-next-page") or ""
            if not page:
                break
        return TreeResult(True, sorted(paths), None)

    def _resolve_missing_tree(self, cfg, project, ref, headers) -> TreeResult:
        """404 на дереве неоднозначен: либо в ветке просто нет каталога
        патчей, либо самой ветки нет. Уточняем через /repository/commits/<ref>."""
        url = "%s/projects/%s/repository/commits/%s" % (
            cfg.api.rstrip("/"), quote(project, safe=""), quote(ref, safe=""))
        response = self._http.get(url, headers, {})
        # вердикт пишем словами: без него в журнале видны только 404 на
        # дереве и 200 на ветке, и прочесть их как «всё в порядке» может лишь
        # тот, кто и так знает про доразбор
        if isinstance(response, str):
            logger.debug("%s: ветка %s — не удалось выяснить, есть ли она: %s",
                         project, ref, response)
            return _tree_problem(response)
        if response.status == 404:
            logger.debug("%s: ветки %s нет, поэтому и каталога %s не нашлось",
                         project, ref, self._patch_dir)
            return _tree_problem("gitlab: ref not found")
        if 200 <= response.status < 300:
            logger.debug("%s: ветка %s есть, каталога %s в ней нет — это не "
                         "ошибка, патчей у билда просто нет",
                         project, ref, self._patch_dir)
            return TreeResult(False, [], None)
        logger.debug("%s: ветка %s — не удалось выяснить, есть ли она: %s %s",
                     project, ref, response.status, server_message(response))
        return _tree_problem("gitlab: %s %s" % (response.status, server_message(response)))
