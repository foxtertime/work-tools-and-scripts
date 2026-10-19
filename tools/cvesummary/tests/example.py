"""Пример таблицы процесса на 100 строк — для ручной проверки страницы.

python3 -m tests.example пример.xlsx

Данные вымышленные, детерминированные (seed). Над шапкой — строка
группировки, даты — текстом дд.мм.гггг, как в живой выгрузке; две строки
— намеренные аномалии («Готов» без End date, End раньше Start).
"""
import datetime
import random
import sys

from tests.xlsxmake import write

AS_OF = datetime.date(2026, 10, 19)
HEADER = ["Разработчик", "Статус", "Start date", "End date", "Принятая мера", "Task ID",
          "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент", "P", "D",
          "SL NVR (latest build)", "RHEL NVR (if fixed)", "Fix date", "RHEL state",
          "RHEL severity", "RHEL CVSS", "Advisory (RHSA)", "CVE link", "Комментарий"]
GROUPS = ["AG21", "", "", "", "", "SberLinux"] + [""] * 10 + ["RedHat"] + [""] * 5
DEVS = ["Иванов И.И.", "Петров П.П.", "Сидорова А.А.", "Кузнецов Д.В.", "Смирнова Е.Н."]
STATUSES = ["В работе"] * 4 + ["Готов"] * 8 + ["На паузе", "Есть проблема",
                                               "Нужна доработка", "Ожидает ревью"]
MEASURES = ["Патч из апстрима", "Импорт новой версии", "Тег свежего билда",
            "Пакет пересобран (если в зависимостях)", "Обоснована неприменимость",
            "Патч из прошлой ветки", "Самописный патч", "Было исправлено ранее",
            "Закрыто SecOps", "Написана мера компенсации", "Другое"]
PACKAGES = ["openssl", "bash", "curl", "httpd", "glibc", "systemd", "git", "libxml2",
            "sudo", "openssh", "nodejs", "postgresql", "kernel", "podman", "samba"]
SEVERITY = [("Low", "3.3"), ("Moderate", "5.5"), ("Moderate", "6.5"), ("Important", "7.5"),
            ("Important", "8.1"), ("Critical", "9.8"), ("", "")]
STATES = ["Affected"] * 4 + ["Fixed"] * 3 + ["Under investigation", "Will not fix", "not listed"]


def _d(day):
    return day.strftime("%d.%m.%Y")


def rows():
    rnd = random.Random(20261019)
    out = [GROUPS, HEADER]
    for n in range(100):
        pkg = rnd.choice(PACKAGES)
        cve = "CVE-2026-%05d" % (70000 + n * 37)
        tdate = AS_OF - datetime.timedelta(days=rnd.randrange(60))
        sev, cvss = rnd.choice(SEVERITY)
        state = rnd.choice(STATES)
        fixed = state == "Fixed"
        dev = status = start = end = measure = "-"
        if rnd.random() < 0.7:
            dev = rnd.choice(DEVS)
            status = rnd.choice(STATUSES)
            begin = min(AS_OF, tdate + datetime.timedelta(days=rnd.randrange(10)))
            start = _d(begin)
            if status == "Готов" or (status == "Ожидает ревью" and rnd.random() < 0.5):
                end = _d(min(AS_OF, begin + datetime.timedelta(days=rnd.randrange(6))))
            if status == "Готов":
                measure = rnd.choice(MEASURES)
        if n == 7:
            dev, status, start, end = DEVS[0], "Готов", _d(AS_OF), "-"
        if n == 8:
            dev, status, start, end = DEVS[1], "В работе", _d(AS_OF), _d(AS_OF - datetime.timedelta(days=3))
        out.append([dev, status, start, end, measure, "TASKID-%d" % (182000 + n), cve,
                    rnd.choice(["В работу", "В работе", "Выполнена"]), _d(tdate),
                    rnd.choice(["КМ", "ПП", "АС", "ДВ"]), pkg,
                    "+" if rnd.random() < 0.2 else "-", "+" if rnd.random() < 0.15 else "-",
                    "%s-1.0-1.sl9" % pkg, "%s-1.0-2.el9_6" % pkg if fixed else "-",
                    _d(tdate - datetime.timedelta(days=20)) if fixed else "-", state,
                    sev or "-", cvss or "-",
                    "https://access.redhat.com/errata/RHSA-2026:%d" % (1000 + n) if fixed else "-",
                    "https://access.redhat.com/security/cve/" + cve,
                    rnd.choice(["-", "-", "-", "ждём апстрим", "согласовано с ИБ"])])
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    write(argv[0], rows())
    return 0


if __name__ == "__main__":
    sys.exit(main())
