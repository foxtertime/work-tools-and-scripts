# Config Secrets Implementation Plan

> **For agentic workers:** use superpowers:dispatching-parallel-agents for the three independent tools and test-driven-development for changed behavior.

**Goal:** заменить env-механизм пользовательских токенов/ключей полями YAML во всех использующих их утилитах.

**Architecture:** каждая тулза сохраняет собственный конфиг и клиентов, общего runtime-кода нет. Источник GitLab-секрета — `gitlab.token`; источник NVD-ключа — `ranges.nvd_key`.

**Tech Stack:** существующие Python 3.9+ пакеты, PyYAML и unittest.

## Spec / Global Constraints

- Dashboard, vulnsheet и patchaudit — все найденные потребители env-секретов.
- Новые поля: строки или null; trim по краям; отсутствие, null, пустая/пробельная строка означают отсутствие ключа.
- Другие типы — ошибка, не содержащая значения секрета. Повреждённый YAML не должен показывать строку исходника с секретом.
- `gitlab.token_env` и `ranges.nvd_key_env` больше не поддерживаются: понятная ошибка миграции, без fallback на env.
- Не менять переменные путей конфигов, кэша и настроек окружения без секретов.
- Не логировать и не включать секреты в CSV/JSON/HTML. Сохранить очистку сетевых исключений.
- Самодостаточность тулз и read-only доступ к внешним сервисам сохраняются.
- Несовместимые версии: dashboard 4.0.0, vulnsheet 5.0.0, patchaudit 1.0.0. Релиз/merge/push не входят в текущую задачу.

## Review Focus

1. Env-токены не используются, даже когда они заданы и поле YAML пусто.
2. Токен с пробелами/переводом строки по краям передаётся очищенным.
3. Ошибки YAML и валидации секретных полей не показывают секрет.
4. Ошибки HTTP не раскрывают секрет в журнале/выходе.
5. Старые ключи конфига отклоняются с указанием новых полей.

### Task 1: dashboard

Files: tools/dashboard/dashboard/{config,cli,httpclient,__init__}.py (as needed), tests/, README.md, dashboard.example.yaml, CHANGELOG.md.

- [x] Добавить/обновить тесты YAML-токена, игнорирования env, анонимной работы, ошибок и редактирования журналов; проверить RED.
- [x] Реализовать `gitlab.token`, убрать env-чтение, проверить GREEN всей suite.
- [x] Обновить пользовательские документы и версию 4.0.0; исторические планы/changelog не переписывать.

### Task 2: vulnsheet

Files: tools/vulnsheet/vulnsheet/{config,cli,__init__}.py (as needed), tests/, README.md, vulnsheet.example.yaml, CHANGELOG.md.

- [x] Тесты `gitlab.token`, `ranges.nvd_key`, отсутствия env-fallback, безопасных ошибок/логов/CSV; проверить RED.
- [x] Подключить новые настройки к GitLab и NVD, сохранить ограничение частоты по наличию NVD-ключа; проверить GREEN всей suite.
- [x] Обновить README, пример YAML и версию 5.0.0.

### Task 3: patchaudit

Files: tools/patchaudit/patchaudit/{config,cli,__init__}.py (as needed), tests/, README.md, patchaudit.example.yaml, CHANGELOG.md, examples/.

- [x] Тесты `gitlab.token`, удаления env-fallback, безопасных ошибок/журнала/JSON; проверить RED.
- [x] Реализовать и проверить GREEN всей suite; сохранить SL-сравнение, кэш и JSON-формат.
- [x] Обновить README, пример YAML, версии и примеры JSON для 1.0.0.

### Task 4: Integration

- [x] Обновить корневой changelog с несовместимыми версиями и миграцией полей.
- [x] Проверить отсутствие runtime-чтения env-секретов по всему tools/.
- [x] Выполнить полные suite трёх тулз, применимые JS-проверки dashboard и корневые проверки.
- [x] Независимое ревью итогового diff, исправления с регрессионными тестами.

## Выполнение и проверка

- dashboard: 406 Python-тестов; vulnsheet: 460; patchaudit: 234. Всего 1100,
  все проходят. Дополнительно dashboard: 557 JavaScript-тестов, все проходят.
- Корневые проверки: синтаксис Python 3.9, shell, обязательные файлы,
  ссылки README/TODO, версии, примеры JSON и git diff --check.
- Поиск по runtime-коду не находит чтения env-секретов; оставшиеся env
  относятся к путям конфигов и кэша. Старые ключи остались только в миграции.
- Независимое ревью нашло две утечки: debug commit-probe в patchaudit
  и repr-экранирование кавычек в HTTP-клиентах трёх тулз. Для обеих добавлены
  падавшие до исправлений регрессионные тесты; итоговые suite проходят.
- Изменения оставлены в feature/config-secrets; release/merge/push в этой
  задаче не выполнялись.
