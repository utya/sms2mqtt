# sms2mqtt-persistence

Опциональный MQTT-слушатель: подписывается на топики `{prefix}/received` и `{prefix}/sent`, сохраняет записи SMS в PostgreSQL. Удобен для логирования, поиска и сценариев с несколькими модемами (у каждой строки есть `device_id` = MQTT-префикс).

## Переменные окружения

**MQTT** (тот же брокер, что и у моста sms2mqtt):

| Переменная | Обязательна | Описание                         |
|------------|-------------|----------------------------------|
| `HOST`     | да          | Хост MQTT-брокера                |
| `PREFIX`   | да          | Префикс топиков (напр. `sms2mqtt`) |
| `PORT`     | нет         | Порт MQTT (по умолчанию 1883)    |
| `USER`     | нет         | Имя пользователя MQTT            |
| `PASSWORD` | нет         | Пароль MQTT                      |
| `USETLS`   | нет         | `true` / `1` для TLS             |
| `CLIENTID` | нет         | Идентификатор клиента (по умолчанию sms2mqtt-persistence) |

**База данных:**

| Переменная  | Обязательна | Описание              |
|-------------|-------------|------------------------|
| `PGHOST`    | да          | Хост PostgreSQL        |
| `PGDATABASE`| да          | Имя базы данных        |
| `PGUSER`    | да          | Пользователь БД        |
| `PGPASSWORD`| да          | Пароль БД              |
| `PGPORT`    | нет         | Порт (по умолчанию 5432) |

**Прочее:** `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR` (по умолчанию `INFO`).

## Схема БД

Создайте базу данных и примените схему перед первым запуском:

```bash
createdb sms2mqtt
psql -d sms2mqtt -f schema.sql
```

При использовании Docker Compose (см. ниже) один раз подключитесь к контейнеру postgres и выполните `schema.sql` или используйте init-скрипт.

## Запуск локально

Для зависимостей используется [uv](https://docs.astral.sh/uv/). Из каталога проекта:

```bash
uv sync
export HOST=localhost PREFIX=sms2mqtt
export PGHOST=localhost PGDATABASE=sms2mqtt PGUSER=u PGPASSWORD=p
uv run python3 listener.py
```

## Запуск в Docker

```bash
docker build -t sms2mqtt-persistence .
docker run -d --name sms2mqtt-persistence \
  -e HOST=your-mqtt-host -e PREFIX=sms2mqtt \
  -e PGHOST=postgres -e PGDATABASE=sms2mqtt -e PGUSER=sms2mqtt -e PGPASSWORD=secret \
  sms2mqtt-persistence
```

## Опциональный Docker Compose

Из корня репозитория можно поднять Postgres и этот сервис командой:

```bash
docker compose -f docker-compose.persistence.yml up -d
```

Задайте `MQTT_HOST`, `MQTT_PREFIX` и т.д. (или используйте значения по умолчанию). Основной мост sms2mqtt в этот compose не входит — запускайте его отдельно. Примените `schema.sql` к сервису postgres до первого успешного запуска слушателя (например: `docker compose -f docker-compose.persistence.yml exec postgres psql -U sms2mqtt -d sms2mqtt -f - < sms2mqtt-persistence/schema.sql` или выполните один раз с хоста).

## Тесты

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

---

См. [README основного репозитория](../README.md).
