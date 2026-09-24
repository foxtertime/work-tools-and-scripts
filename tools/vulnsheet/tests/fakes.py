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
                 hub_down=False, multicall_down=False, baseurl="https://koji.example.com/kojihub"):
        self.builds = dict(builds or {})
        self.errors = dict(errors or {})
        self.tags = set(tags)
        self.hub_down = hub_down
        self.multicall_down = multicall_down
        self.baseurl = baseurl
        self.calls = []

    def getTag(self, tag):
        if self.hub_down:
            raise ConnectionError("хаб недоступен")
        return {"name": tag} if tag in self.tags else None

    def multicall(self, strict=False):
        return _Multicall(self)


# Платформы CSAF: (product_id, cpe). Версию RHEL тулза берёт из cpe.
RHEL9 = ("red_hat_enterprise_linux_9", "cpe:/o:redhat:enterprise_linux:9")
APPSTREAM96 = ("AppStream-9.6.0.Z.MAIN", "cpe:/a:redhat:enterprise_linux:9::appstream")
BASEOS96 = ("BaseOS-9.6.0.Z.MAIN", "cpe:/o:redhat:enterprise_linux:9::baseos")
EUS92 = ("AppStream-9.2.0.Z.EUS", "cpe:/a:redhat:rhel_eus:9.2::appstream")
RHEL_AI = ("RHEL-AI-9", "cpe:/a:redhat:enterprise_linux_ai:9")
# Надстройка со своими сборками (el9fdp) под CPE семейства RHEL — не RHEL.
FASTDATAPATH9 = ("9Base-Fast-Datapath", "cpe:/o:redhat:enterprise_linux:9::fastdatapath")
# Репозиторий, которого тулза не знает.
UNKNOWN_REPO9 = ("9Base-Something", "cpe:/o:redhat:enterprise_linux:9::something_new")


def pid(platform, component):
    """Составной product_id, каким его пишет Red Hat: платформа:компонент."""
    return "%s:%s" % (platform[0], component)


def csaf(cve, statuses, severity="Moderate", scores=(), remediations=()):
    """Минимальный CSAF/VEX-документ.

    statuses — [(bucket, платформа, component_id)], где bucket — ключ
    product_status (fixed, known_affected, known_not_affected,
    under_investigation).
    """
    platforms, relationships, status = {}, [], {}
    for bucket, platform, component in statuses:
        platforms[platform[0]] = platform[1]
        composite = pid(platform, component)
        relationships.append({
            "full_product_name": {"product_id": composite},
            "relates_to_product_reference": platform[0],
            "product_reference": component,
        })
        status.setdefault(bucket, []).append(composite)
    branches = [{"product": {"product_id": product_id,
                             "product_identification_helper": {"cpe": cpe}}}
                for product_id, cpe in platforms.items()]
    return {
        "document": {"aggregate_severity": {"text": severity}},
        "product_tree": {"branches": branches, "relationships": relationships},
        "vulnerabilities": [{"cve": cve, "product_status": status,
                             "scores": list(scores),
                             "remediations": list(remediations)}],
    }
