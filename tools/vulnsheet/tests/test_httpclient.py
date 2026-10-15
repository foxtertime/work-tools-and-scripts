"""HTTP-слой: повторы, паузы и то, что токен из сообщений не уезжает.

Раньше всё это проверялось через дерево GitLab — то есть доказывалось не
там, где живёт. Здесь ни одного запроса к GitLab нет: только транспорт,
повторы и текст.
"""
import io
import logging
import unittest
import urllib.error
from unittest import mock

from vulnsheet.httpclient import HttpClient, UrllibTransport
from tests.fakes import FakeTransport, Response

URL = "https://gitlab.example.com/api/v4/projects/g%2Fr/repository/tree"
# токен в тестах непременно должен быть похож на настоящий: односимвольный
# затирался бы очисткой в любом постороннем тексте и прятал бы её ошибки
TOKEN = "glpat-t0ken"
SECRET = "glpat-SECRET123"


class _BrokenTransport:
    """Транспорт, у которого каждый запрос падает сетевой ошибкой."""

    def __init__(self):
        self.requests = []

    def get(self, url, headers=None, params=None):
        self.requests.append(url)
        raise IOError("connection reset")

class RetrySleepTest(unittest.TestCase):
    def sleeps_for(self, transport, **kwargs):
        slept = []
        client = HttpClient(transport=transport, token=TOKEN,
                            sleeper=slept.append, **kwargs)
        return client.get(URL, {}, {}), slept

    def test_no_backoff_after_the_last_failed_attempt(self):
        # три попытки — две паузы: ждать после последней нечего, а с
        # --jobs 8 против приболевшего GitLab это секунды на каждый билд
        result, slept = self.sleeps_for(_BrokenTransport(), retries=3)
        self.assertIn("connection reset", result)
        self.assertEqual(len(slept), 2)

    def test_no_backoff_after_the_last_bad_status(self):
        transport = FakeTransport({URL: Response(500, {}, {})})
        _, slept = self.sleeps_for(transport, retries=3)
        self.assertEqual(len(slept), 2)

    def test_single_attempt_never_sleeps(self):
        _, slept = self.sleeps_for(_BrokenTransport(), retries=1)
        self.assertEqual(slept, [])

class ScrubTest(unittest.TestCase):
    """Очистка текста исключения от токена во всех формах, в которых он туда
    попадает."""

    def scrub(self, token, text):
        return HttpClient(transport=FakeTransport({}), token=token,
                          sleeper=lambda _s: None).scrub(text)

    def test_raw_token_is_scrubbed(self):
        self.assertEqual(self.scrub(SECRET, "заголовок %s тут" % SECRET),
                         "заголовок *** тут")

    def test_token_with_a_newline_is_scrubbed_in_its_raw_form(self):
        # если текст несёт настоящий перевод строки, а не его запись
        self.assertNotIn(SECRET, self.scrub(SECRET + "\n", SECRET + "\n"))

    def test_repr_escaped_token_is_scrubbed(self):
        # requests печатает значение заголовка через repr: настоящий перевод
        # строки становится двумя символами «\» и «n», и замена по сырому
        # токену не находит ничего
        token = SECRET + "\n"
        text = "Invalid header value b'%s'" % (
            token.encode("unicode_escape").decode("ascii"))
        self.assertEqual(self.scrub(token, text), "Invalid header value b'***'")

    def test_stripped_token_is_scrubbed(self):
        # после срезки пробелов на провод уходит именно этот вид токена,
        # и в чужом сообщении может оказаться он
        token = SECRET + "\n"
        self.assertEqual(self.scrub(token, "хвост %s хвост" % SECRET),
                         "хвост *** хвост")

    def test_short_token_is_not_scrubbed(self):
        # настоящий PAT GitLab — около 26 символов; слепая замена короткого
        # «токена» испортила бы обычный текст ошибки, а он идёт в журнал
        text = "connection reset by peer"
        self.assertEqual(self.scrub("t", text), text)
        self.assertEqual(self.scrub("connect", text), text)

    def test_token_at_the_threshold_is_scrubbed(self):
        self.assertEqual(self.scrub("abcdefgh", "x abcdefgh y"), "x *** y")

    def test_whitespace_only_token_is_not_scrubbed(self):
        text = "connection reset by peer"
        self.assertEqual(self.scrub("        ", text), text)

    def test_no_token_leaves_the_text_alone(self):
        text = "connection reset by peer"
        self.assertEqual(self.scrub(None, text), text)
        self.assertEqual(self.scrub("", text), text)

    def test_non_string_input_is_converted(self):
        self.assertEqual(self.scrub(SECRET, ValueError("ой %s" % SECRET)),
                         "ой ***")

class LoggingTest(unittest.TestCase):
    """Что попадает в лог при неудачах: предупреждение обещает следующую
    попытку, поэтому после последней его быть не должно."""

    def failing(self, retries):
        return HttpClient(transport=_BrokenTransport(), token=TOKEN,
                          sleeper=lambda _s: None, retries=retries)

    def test_final_transport_failure_is_not_warned_about(self):
        # об окончательной неудаче один раз и с именем компонента напишет
        # patches; здесь предупреждение только пообещало бы новую попытку
        with self.assertLogs("vulnsheet.httpclient", level="DEBUG") as caught:
            self.failing(1).get(URL, {}, {})
        self.assertEqual([r.levelname for r in caught.records], ["DEBUG"])

    def test_transport_failures_warn_only_while_attempts_remain(self):
        with self.assertLogs("vulnsheet.httpclient", level="DEBUG") as caught:
            self.failing(3).get(URL, {}, {})
        warnings = [r for r in caught.records if r.levelno == logging.WARNING]
        self.assertEqual(len(warnings), 2)



class _Raw:
    """Ответ urlopen: тело, код и заголовки, как у http.client.HTTPResponse."""

    def __init__(self, status, body, headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class UrllibTransportTest(unittest.TestCase):
    """Транспорт на urllib: сети нет, подменён urlopen."""

    def get(self, outcome):
        transport = UrllibTransport(timeout=7)
        with mock.patch("vulnsheet.httpclient.urllib.request.urlopen") as urlopen:
            if isinstance(outcome, Exception):
                urlopen.side_effect = outcome
            else:
                urlopen.return_value = outcome
            response = transport.get(URL, {"PRIVATE-TOKEN": TOKEN},
                                     {"ref": "feat/x", "page": "2"})
        return response, urlopen.call_args

    def test_query_headers_and_timeout_reach_urlopen(self):
        _, call = self.get(_Raw(200, b"[]"))
        request = call.args[0]
        self.assertEqual(request.full_url, URL + "?ref=feat%2Fx&page=2")
        self.assertEqual(request.get_header("Private-token"), TOKEN)
        self.assertEqual(call.kwargs["timeout"], 7)

    def test_json_body_and_headers_are_returned(self):
        response, _ = self.get(_Raw(200, b'[{"path": "PATCH/a.patch"}]',
                                    {"x-next-page": "2"}))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, [{"path": "PATCH/a.patch"}])
        self.assertEqual(response.headers["x-next-page"], "2")

    def test_http_error_is_a_response_not_an_exception(self):
        # 404 у GitLab — ответ, по которому решается «ветки нет» или
        # «каталога нет»: тело с сообщением нужно разбору
        error = urllib.error.HTTPError(URL, 404, "Not Found", {},
                                       io.BytesIO(b'{"message": "404 Tree Not Found"}'))
        response, _ = self.get(error)
        self.assertEqual(response.status, 404)
        self.assertEqual(response.body, {"message": "404 Tree Not Found"})

    def test_body_that_is_not_json_is_none(self):
        response, _ = self.get(_Raw(502, b"<html>bad gateway</html>"))
        self.assertIsNone(response.body)


if __name__ == "__main__":
    unittest.main()
