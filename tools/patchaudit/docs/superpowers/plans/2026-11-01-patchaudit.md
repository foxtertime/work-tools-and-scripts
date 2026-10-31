# patchaudit Implementation Plan

> **For agentic workers:** implement inline using superpowers:executing-plans.

**Goal:** JSON-рекомендации об актуальности CVE-патчей при обновлении RPM.

**Architecture:** самостоятельные копии клиентов vulnsheet; чистая логика
решений; orchestration Koji → ветка PATCH → VEX; CLI и атомарный JSON.

**Tech Stack:** Python 3.9+, unittest, stdlib, системный koji, optional PyYAML.

**Spec:** ../specs/2026-11-01-patchaudit-design.md

## Global Constraints

- Самодостаточный каталог tools/patchaudit; vulnsheet не меняется.
- Два явных взаимоисключающих входа: --package и --nvr.
- Читается PATCH ветки; NVR — цель обновления, а не запрос getBuild.
- Нет автоматического удаления; неизвестность видна в JSON.

## Review Focus

- Один патч под несколько CVE: удаление только при полном покрытии.
- Бэкпорты с одинаковой upstream-версией и разными release.
- Чужой disttag не должен создавать ложную рекомендацию удалить.
- Отсутствие каталога отличается от отсутствия ref/проекта.
- Сбой VEX не заменяется на отсутствие записи и не портит прежний JSON.

### Task 1: Клиенты и решения

Files: patchaudit/{vex,kojiclient,gitlabclient,httpclient,sourceurl,cveid,
rpmvercmp,config,logs}.py; patchaudit/decisions.py; tests/.

- [x] Перенести нужные модули и офлайн-тесты из vulnsheet, сменить namespace.
- [x] Добавить тесты parse_nvr, compare_target и decision/patch_decision;
  проверить RED, затем реализовать и проверить GREEN.
- [x] Добавить all fixed releases в VEX и тесты RHEL/stream/aliases/date.

### Task 2: Отчёт и CLI

Files: patchaudit/{audit,cli,__main__,__init__}.py; tests/{test_audit,test_cli}.py.
Interfaces: audit.run(package, target_nvr, tag, rhel, session, client,
settings, stream=None, aliases=()) -> dict; cli.main(argv=None) -> int.

- [x] Тесты режимов, актуальной ветки вместо коммита, пустых результатов,
  неполных данных и атомарного JSON; запустить до реализации (RED).
- [x] Реализовать orchestration и CLI (GREEN), поддержать YAML и флаги.
- [x] Запустить всю unittest suite и CLI --help/--version.

### Task 3: Документация и проверка

Files: README.md, TODO.md, CHANGELOG.md, setup.cfg, pyproject.toml,
patchaudit.example.yaml; корневые README/CHANGELOG/TODO.

- [x] Документировать оба режима, JSON, ограничения сравнений, коды выхода.
- [x] Обновить индекс тулз/задач и changelog; проверить ссылки и git diff.
- [x] Выполнить полный офлайн-прогон и независимое итоговое ревью.

Коммиты/merge/push в эту задачу не входят: результат остаётся для просмотра
в рабочей feature-ветке.

## Проверка реализации

- 223 офлайн-тестов проходят; CLI --help/--version проверены.
- Отдельный wheel собран без сети; entry point и запуск из изолированного
  каталога работают, соседние тулзы не требуются.
- Реальный документ Red Hat CVE-2024-6387 разобран через VEX-клиент.
- Независимое ревью: пять замечаний исправлены; для каждого дефекта
  воспроизводящий тест сначала падал, после исправлений suite проходит.
- Проверены Python 3.9 grammar, ссылки README/TODO, обязательные файлы,
  синтаксис shell-скриптов и whitespace.
- Уточнение пользователя (2026-11-01): SL соответствует EL. В целевом
  release `sl` преобразуется в `el`, суффикс `^<номер>` отрезается;
  в JSON сохраняется исходный NVR. Иные нестандартные disttag — review.
- Полный сетевой прогон Koji → GitLab требует рабочего пользовательского
  конфига; интеграционная связка покрыта поддельными внешними сервисами.
