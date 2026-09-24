"""Подделки внешних систем для тестов. Сети здесь нет."""


class _Call:
    """Отложенный результат, как koji.VirtualCall: ошибка — при чтении .result."""

    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error

    @property
    def result(self):
        if self._error is not None:
            raise self._error
        return self._value


class _Multicall:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self._session.multicall_down:
            raise ConnectionError("multicall: соединение сброшено")
        return False

    def getLatestBuilds(self, tag, package=None):
        self._session.calls.append((tag, package))
        if package in self._session.errors:
            return _Call(error=RuntimeError(self._session.errors[package]))
        nvr = self._session.builds.get(package)
        return _Call([{"nvr": nvr}] if nvr else [])


class FakeKojiSession:
    """koji.ClientSession в объёме, нужном kojiclient: getTag и multicall."""

    def __init__(self, builds=None, errors=None, tags=("sl9",),
                 hub_down=False, multicall_down=False):
        self.builds = dict(builds or {})
        self.errors = dict(errors or {})
        self.tags = set(tags)
        self.hub_down = hub_down
        self.multicall_down = multicall_down
        self.calls = []

    def getTag(self, tag):
        if self.hub_down:
            raise ConnectionError("хаб недоступен")
        return {"name": tag} if tag in self.tags else None

    def multicall(self, strict=False):
        return _Multicall(self)
