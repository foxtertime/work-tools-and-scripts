"""HTTP с повторами, паузами и чисткой секретов из сообщений.

Перенесено из тулзы dashboard (тулзы общего кода не делят); транспорт там
на requests, здесь — на urllib.

Отделено от gitlabclient не ради красоты: повторы, экспоненциальная пауза,
Retry-After и вычистка токена из текста исключения — свойства разговора по
HTTP, а не знания о том, как устроено дерево файлов в GitLab. Разговор
здесь, знание — там.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# Коды, после которых повтор имеет смысл: сервер перегружен или просит
# подождать. На 404 повторять нечего.
RETRY_STATUSES = (429, 500, 502, 503, 504)

_BODY_LIMIT = 200

# порог, ниже которого строка не считается токеном и не вычищается
_MIN_TOKEN_LEN = 8


class UrllibTransport:
    """GET на urllib: так же, как VEX, без зависимости от requests.

    Код ответа ≥ 400 — не исключение, а ответ: GitLab кладёт в тело
    сообщение, по которому разбирается 404.
    """

    def __init__(self, timeout: float = 30):
        self._timeout = timeout

    def get(self, url, headers=None, params=None):
        if params:
            url = "%s?%s" % (url, urllib.parse.urlencode(params))
        request = urllib.request.Request(url, headers=dict(headers or {}))
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as raw:
                return Response(raw.status, _json(raw.read()), raw.headers)
        except urllib.error.HTTPError as exc:
            return Response(exc.code, _json(exc.read()), exc.headers)


def _json(data):
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, AttributeError):
        return None


class Response:
    def __init__(self, status, body, headers):
        self.status = status
        self.body = body
        self.headers = headers


class HttpClient:
    """GET с повторами. Токен нужен не для запроса, а для чистки сообщений.

    Заголовок авторизации собирает тот, кто знает, как его зовёт сервер;
    сюда токен приходит только затем, чтобы не уехать в журнал.
    """

    def __init__(self, transport=None, token: Optional[str] = None,
                 retries: int = 3, sleeper=time.sleep):
        self._transport = transport or UrllibTransport()
        self._token = token
        self._retries = max(1, int(retries))
        self._sleep = sleeper

    def scrub(self, text) -> str:
        """Текст исключения транспорта может нести заголовки — там токен.

        Причину кривого заголовка снимает cli, срезая пробелы с токена; эта
        очистка — второй рубеж: секрет может оказаться в тексте исключения и
        по другой причине, а утечка происходит молча.

        Ищем токен во всех видах, в которых он туда попадает. HTTP-клиенты
        печатают значение заголовка через repr, и настоящий перевод строки
        превращается в два символа «\\» и «n» — по сырому токену такая замена
        не находит ничего. Поэтому чистим и сырой токен, и его экранированную
        запись, и обрезанный вариант (именно он уходит на провод).
        """
        text = str(text)
        token = self._token or ""
        # ниже порога чистить опаснее, чем не чистить: настоящий PAT GitLab
        # длиной около 26 символов, а слепая замена короткого «токена»
        # превратит «connection reset by peer» в «connec***ion rese*** by
        # peer» — и этот испорченный текст уедет в журнал. Восемь символов —
        # заведомо не секрет.
        if len(token.strip()) < _MIN_TOKEN_LEN:
            return text
        variants = {token, token.strip()}
        variants |= {v.encode("unicode_escape").decode("ascii")
                     for v in list(variants)}
        # длинные варианты первыми: иначе обрезанный съел бы начало полного
        for variant in sorted(variants, key=len, reverse=True):
            text = text.replace(variant, "***")
        return text

    def get(self, url, headers, params):
        """Ответ сервера или строка с причиной, по которой его нет.

        Строка, а не исключение: неудача одного запроса — это проблема
        одного билда, а не всего прогона, и она уезжает в журнал ровно тем
        текстом, который здесь собран.
        """
        last = None
        for attempt in range(self._retries):
            started = time.monotonic()
            try:
                response = self._transport.get(url, headers=headers,
                                               params=params)
            except Exception as exc:  # сетевые ошибки транспорта
                elapsed = time.monotonic() - started
                # текст исключения идёт в журнал — очищаем до того, как он
                # куда-то попал
                text = self.scrub(exc)
                last = "gitlab: %s" % text
                if attempt < self._retries - 1:
                    delay = self._delay(attempt, None)
                    logger.warning("GET %s%s → %s за %.2f с, повтор через "
                                   "%.0f с (попытка %d из %d)", url,
                                   params_note(params), text, elapsed, delay,
                                   attempt + 1, self._retries)
                    self._sleep(delay)
                else:
                    # после последней попытки ждать незачем: с --jobs 8 против
                    # приболевшего GitLab это секунды на каждый билд впустую.
                    # Предупреждать тоже: об окончательной неудаче один раз и
                    # с именем компонента напишет patches, а «попытка 3 из 3»
                    # в WARNING обещала бы несуществующую следующую.
                    logger.debug("GET %s%s → %s за %.2f с (попытка %d из %d, "
                                 "последняя)", url, params_note(params), text,
                                 elapsed, attempt + 1, self._retries)
                continue

            elapsed = time.monotonic() - started
            if response.status >= 400:
                logger.debug("GET %s%s → %s за %.2f с: %s", url,
                             params_note(params), response.status, elapsed,
                             body_note(response))
            else:
                logger.debug("GET %s%s → %s за %.2f с", url,
                             params_note(params), response.status, elapsed)

            if response.status in RETRY_STATUSES and attempt < self._retries - 1:
                # сначала строка, потом пауза: при Retry-After 60 обратный
                # порядок дал бы минуту тишины и рассказ о ней в прошедшем
                # времени, а следить за долгим прогоном — половина смысла лога
                delay = self._delay(attempt,
                                    (response.headers or {}).get("Retry-After"))
                logger.warning("GET %s%s → %s, повтор через %.0f с "
                               "(попытка %d из %d)", url,
                               params_note(params), response.status, delay,
                               attempt + 1, self._retries)
                self._sleep(delay)
                last = "gitlab: %s %s" % (response.status, server_message(response))
                continue
            return response
        return last or "gitlab: запрос не удался"

    def _delay(self, attempt, retry_after) -> float:
        """Длительность паузы перед повтором; сон отдельно, чтобы строка о
        паузе успела уйти в лог до самой паузы."""
        delay = 2 ** attempt
        if retry_after:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                pass
        return delay


def server_message(response) -> str:
    body = getattr(response, "body", None)
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error") or "")
    return ""


def params_note(params) -> str:
    """Параметры запроса для лога — вместе с ведущим пробелом, чтобы у
    запроса без параметров в строке не оставалось дырки.

    Заголовки не логируем никогда — там токен.
    """
    keep = ("ref", "path", "page")
    note = " ".join("%s=%s" % (k, params[k]) for k in keep if k in (params or {}))
    return " " + note if note else ""


def body_note(response) -> str:
    body = getattr(response, "body", None)
    if body is None:
        return "пустое тело"
    text = str(body)
    return text if len(text) <= _BODY_LIMIT else text[:_BODY_LIMIT] + "…"
