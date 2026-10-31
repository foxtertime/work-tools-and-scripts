"""Сравнение версий так же, как это делает rpm (rpmvercmp). Без сети.

Версия режется на сегменты из цифр и из букв, всё прочее — разделители
(«1_2» и «1.2» равны). Числа сравниваются как числа, буквы — как строки;
числовой сегмент новее буквенного. «~» делает версию старше всего, что
идёт без него (1.0~rc1 < 1.0), «^» — новее (1.0^git1 > 1.0, но < 1.0.1).
"""
import re

_SEGMENT = re.compile(r"[0-9]+|[A-Za-z]+")
_JUNK = re.compile(r"[^0-9A-Za-z~^]+")


def _skip_junk(text: str) -> str:
    match = _JUNK.match(text)
    return text[match.end():] if match else text


def rpmvercmp(a: str, b: str) -> int:
    """-1, 0 или 1: a старше, равна или новее b."""
    if a == b:
        return 0
    while a or b:
        a, b = _skip_junk(a), _skip_junk(b)
        if a.startswith("~") or b.startswith("~"):
            if not a.startswith("~"):
                return 1
            if not b.startswith("~"):
                return -1
            a, b = a[1:], b[1:]
            continue
        if a.startswith("^") or b.startswith("^"):
            if not a:
                return -1
            if not b:
                return 1
            if not a.startswith("^"):
                return 1
            if not b.startswith("^"):
                return -1
            a, b = a[1:], b[1:]
            continue
        if not a or not b:
            break
        numeric = a[0].isdigit()
        one = _SEGMENT.match(a).group(0)
        match = re.match(r"[0-9]+" if numeric else r"[A-Za-z]+", b)
        if match is None:
            # сегменты разного вида: числовой новее буквенного
            return 1 if numeric else -1
        two = match.group(0)
        a, b = a[len(one):], b[len(two):]
        if numeric:
            one, two = one.lstrip("0"), two.lstrip("0")
            if len(one) != len(two):
                return 1 if len(one) > len(two) else -1
        if one != two:
            return 1 if one > two else -1
    if not a and not b:
        return 0
    return 1 if a else -1
