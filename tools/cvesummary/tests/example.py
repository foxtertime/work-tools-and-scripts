"""Пример таблицы процесса на 100 строк — для ручной проверки страницы.

python3 -m tests.example пример.xlsx
python3 -m tests.example пример.csv     # то же самое в CSV через «;», как пишет vulnsheet

Данные вымышленные, детерминированные (seed). Над шапкой — строка
группировки, даты — текстом дд.мм.гггг, как в живой выгрузке; две строки
— намеренные аномалии («Готов» без End date, End раньше Start); несколько
строк повторяют пару CVE + компонент более ранних — дубликаты задач. Колонки
ai_* — как их пишет vulnsheet --ai из results.json плагина rhel-security:
примерно половина пар прогнана через AI, вердикты и remediation — его токены.
"""
import csv
import datetime
import random
import sys

from tests.xlsxmake import write

AS_OF = datetime.date(2026, 10, 19)
HEADER = ["Разработчик", "Статус", "Start date", "End date", "Принятая мера", "Task ID",
          "CVE ID", "Task state", "Task date", "Исполнитель", "Компонент", "P", "D",
          "SL NVR (latest build)", "RHEL NVR (if fixed)", "Fix date", "RHEL state",
          "RHEL severity", "RHEL CVSS", "Advisory (RHSA)", "CVE link",
          "ai_nvr", "ai_verdict", "ai_confidence", "ai_remediation", "ai_run", "Комментарий"]
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
# дубликаты задач: строка n повторяет пару CVE + компонент строки DUPLICATES[n]
DUPLICATES = {40: 3, 41: 3, 55: 12, 70: 25, 71: 30, 90: 31}
STATES = ["Affected"] * 4 + ["Fixed"] * 3 + ["Under investigation", "Will not fix", "not listed"]
# вердикт AI → remediation, которые при нём бывают
AI_RESULTS = [("affected", ["backport prepared", "vendor update available", "rebuild required",
                            "manual remediation required", "upstream fix unavailable"])] * 4 + [
    ("not affected", ["not required"])] * 2 + [
    ("unclear", ["not determined"]), ("invalid CVE", ["not required"]),
    ("rejected CVE", ["not required"]), ("not processed", ["-"])]
AI_CONFIDENCE = ["high", "high", "medium", "low"]


def _d(day):
    return day.strftime("%d.%m.%Y")


def rows():
    rnd = random.Random(20261019)
    ai_rnd = random.Random(2026)  # свой генератор: остальные данные не сдвигаются
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
        ai = ["-"] * 5
        if ai_rnd.random() < 0.55:
            run = AS_OF + datetime.timedelta(days=ai_rnd.randrange(3))
            verdict, remediations = ai_rnd.choice(AI_RESULTS)
            confidence = ai_rnd.choice(AI_CONFIDENCE)
            if verdict in ("not processed", "rejected CVE"):  # так пишет плагин
                confidence = "-" if verdict == "not processed" else "high"
            ai = ["%s-1.0-2.el9" % pkg, verdict, confidence, ai_rnd.choice(remediations),
                  run.isoformat() if n % 2 else _d(run)]
        if n in DUPLICATES:  # та же пара CVE + компонент, что у строки DUPLICATES[n]
            first = out[2 + DUPLICATES[n]]
            pkg, cve, ai = first[10], first[6], first[21:26]
        out.append([dev, status, start, end, measure, "TASKID-%d" % (182000 + n), cve,
                    rnd.choice(["В работу", "В работе", "Выполнена"]), _d(tdate),
                    rnd.choice(["КМ", "ПП", "АС", "ДВ"]), pkg,
                    "+" if rnd.random() < 0.2 else "-", "+" if rnd.random() < 0.15 else "-",
                    "%s-1.0-1.sl9" % pkg, "%s-1.0-2.el9_6" % pkg if fixed else "-",
                    _d(tdate - datetime.timedelta(days=20)) if fixed else "-", state,
                    sev or "-", cvss or "-",
                    "https://access.redhat.com/errata/RHSA-2026:%d" % (1000 + n) if fixed else "-",
                    "https://access.redhat.com/security/cve/" + cve] + ai + [
                    rnd.choice(["-", "-", "-", "ждём апстрим", "согласовано с ИБ"])])
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[0].lower().endswith(".csv"):
        with open(argv[0], "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter=";", lineterminator="\n").writerows(rows())
    else:
        write(argv[0], rows())
    return 0


if __name__ == "__main__":
    sys.exit(main())
