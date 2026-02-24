# Project Roadmap

> SMS-to-MQTT bridge: stable, maintainable, well-documented service with reproducible builds and automated quality checks.

Основа вех — [.ai-factory/RECOMMENDATIONS-PLAN.md](RECOMMENDATIONS-PLAN.md). Порядок — по зависимостям и приоритету.

## Milestones

- [x] **Critical fixes** — исправить баг с `payload` в `on_mqtt_message` (NameError при ошибке decode); обновить Python и базовый образ Docker до 3.11/3.12 и актуального Alpine
- [x] **Reproducible builds** — добавить `requirements.txt` (или `pyproject.toml`) с зафиксированными версиями зависимостей; в Dockerfile установка через него
- [x] **Reliability and config** — переподключение к MQTT вместо `exit()` при отключении; уровень логирования из env (`LOG_LEVEL`)
- [x] **Testing foundation** — минимальные unit-тесты: парсинг и валидация JSON для send (number/text, ошибки, не UTF-8), без MQTT и Gammu
- [ ] **CI: tests and lint** — в GitHub Actions добавить job с установкой зависимостей, запуском тестов и линтера; ограничить публикацию dev-образа по ветке (например, dev/develop)
- [x] **Operations** — добавить HEALTHCHECK в Dockerfile для оркестраторов
- [x] **Optional: SMS persistence** — отдельный модуль (MQTT Listener): подписка на топики received/sent, запись сообщений в PostgreSQL; отдельная папка, отдельный образ, опциональный сервис в Docker Compose (можно не запускать)
- [ ] **Code quality (optional)** — при рефакторинге уменьшить глобальное состояние (конфиг/колбэки); опционально: нормализация номера и лимиты длины текста
- [ ] **Documentation and security** — в README: все переменные окружения (USETLS, DEVICE, DEVMODE), все топики (control, control_response, stuck_status), рекомендации по TLS и секретам, примечание про ACL для control

## Completed

| Milestone | Date |
|-----------|------|
| Critical fixes | 2025-02-23 |
| Reproducible builds | 2025-02-23 |
| Reliability and config | 2025-02-23 |
| Testing foundation | 2025-02-23 |
| Operations | 2025-02-24 |
| Optional: SMS persistence | 2025-02-24 |
