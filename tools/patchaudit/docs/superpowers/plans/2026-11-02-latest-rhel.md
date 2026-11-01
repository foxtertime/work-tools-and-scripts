# Latest RHEL Build Implementation Plan

> **For agentic workers:** independent client and integration work may use superpowers:dispatching-parallel-agents; implementation uses test-driven-development and final independent review.

**Goal:** добавить согласованное поле `latest_rhel_build: NVR | null` в JSON обоих режимов patchaudit.

**Architecture:** отдельный GET-клиент Red Hat VMaaS, выбор исходного NVR через SRPM → бинарные пакеты → NEVRA/repos → исходный пакет. CLI передаёт настройки клиента в audit.run. Общих модулей с другими тулзами не появляется.

**Tech Stack:** Python 3.9+, stdlib HTTP/JSON, существующие кэш VEX и HTTP-транспорт, unittest.

**Spec:** согласованный пользователем пример examples/result-package-with-latest-rhel.json; ограничения ниже.

## Global Constraints

- JSON добавляет только `latest_rhel_build`, строку NVR без epoch/arch, либо null. Формат 1 и решения о патчах не меняются.
- Источник — https://console.redhat.com/api/vmaas/v3; только GET, без токенов GitLab и без авторизации.
- Выбор по RPM EVR (epoch, version, release), точной версии RHEL, архитектуре и стриму, без подстановки EUS/других продуктов.
- Архитектура по умолчанию x86_64; `--arch` и `vmaas.arch` задают другую явно.
- Поиск выполняется и при отсутствии PATCH/CVE. Сбой VMaaS оставляет null + problems/complete=false и код 1; корректное отсутствие пакета — null без сбоя.
- Кэш: подпапка vmaas кэша patchaudit, TTL 3600, атомарная запись; cache_ttl=0 не читает старое. Неполные/битые ответы не становятся пустым успешным результатом.
- Не терять source/binary name mapping, не брать максимум из разных module streams. Если поток нельзя надёжно определить — сообщить проблему, не угадывать.
- Версия patchaudit 1.1.0; README, конфиг, примеры и changelog обновляются. Публикация не входит в задачу.

## Interfaces

`vmaas.py`: VmaasError; VmaasSettings(cache_dir=None, cache_ttl=3600, arch='x86_64', retries=3, timeout=30); VmaasClient(settings=VmaasSettings(), transport=None, sleeper=None).latest(package, rhel, stream=None, aliases=()) -> Optional[str].

`audit.run(..., settings=VexSettings(), stream=None, aliases=(), rhel_client=None)` вызывает latest на переданном клиенте или новом VmaasClient. CLI конструирует клиент с настройками конфига, кеша и --arch.

## Review Focus

- Пакет с дефисами, эпохой, именем SRPM, отличающимся от бинарного.
- Отличать RHEL major/minor/архитектуру, layered/beta/модульные потоки.
- Некорректные HTTP/JSON, частичные страницы и сбой одного кандидата не дают ложный latest.
- VMaaS не получает GitLab-токен; TLS-проверка не отключается.
- Старые решения VEX/пустой PATCH и JSON stdout/атомарный файл сохраняются.

### Task 1: VMaaS client

Files: patchaudit/vmaas.py, tests/test_vmaas.py.

- [x] Тесты выбора/сопоставления, фильтров, null/ошибок, GET, кэша; проверить RED.
- [x] Реализовать клиент по Interfaces, проверить GREEN; подтвердить реальные read-only GET на httpd.

### Task 2: Integration

Files: patchaudit/{config,cli,audit,__init__}.py; tests/{test_config,test_cli,test_audit}.py.

- [x] Добавить падающие тесты минимального поля, успешного/пустого/ошибочного VMaaS, работы без PATCH и --arch/config.
- [x] Реализовать связывание, настройки и обновить офлайн-фикстуры; проверить полную suite.

### Task 3: Documentation and verification

- [x] Обновить README, пример YAML, JSON-примеры, оба changelog и версию 1.1.0.
- [x] Полная suite, синтаксис/ссылки/diff/build/живой запрос VMaaS.
- [x] Независимое ревью и регрессионные исправления.

## Verification

- 270 офлайн-тестов пройдены; Python 3.9 syntax, JSON-примеры, wheel 1.1.0 и проверки репозитория успешны.
- Живые GET: httpd, openssl, vim, nginx:1.26, ruby; ruby с отличающимися версиями бинарных пакетов дал ruby-3.0.7-168.el9_8 (244 GET, 51.85 с).
- Независимое ревью: исправлены regex-имена, выбор по исходному EVR повторное использование бинарного имени разными SRPM и ограничение очереди при сбое; блокирующих замечаний нет.
- Корневой smoke httpd: httpd-2.4.62-13.el9_8.9, повтор из кэша подтверждён.
