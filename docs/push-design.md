# Дизайн: отправка push-уведомлений (FCM)

Предварительная проработка функционала пушей в сервисе sms2mqtt-persistence.

## Цель

При появлении нового входящего SMS (и опционально исходящего) уведомлять мобильное/веб-приложение пользователя через Firebase Cloud Messaging (FCM). Уже используется Firebase Admin SDK для Auth — тот же проект и сервисный аккаунт подходят для FCM.

## Триггеры

| Событие        | Пуш по умолчанию | Примечание |
|----------------|-------------------|------------|
| SMS received   | Да                | Основной сценарий: «пришло новое сообщение» |
| SMS sent       | Опционально      | Можно включить флагом (например, env `PUSH_ON_SENT=true`) |

Точка вызова: сразу после успешного `insert_sms()` в цикле обработки очереди MQTT в `listener.py`. Не блокировать запись в БД: пуш — «best effort» после персиста.

## Кому отправлять

- По `device_id` из сообщения находим пользователей, имеющих доступ к этому устройству:
  - Выборка из `devices`: `device_id = ?`.
  - Если у устройства указан `user_id` — уведомляем только этого пользователя (или нескольких, если одна и та же device_id привязана к разным user_id не предполагается; в текущей схеме device_id UNIQUE, значит один user_id на устройство).
  - **Single-tenant**: если для этого `device_id` в `devices` запись с `user_id IS NULL`, считаем, что устройство «общее» — уведомляем всех пользователей из `users` (чтобы любой авторизованный пользователь получил пуш).
- Для каждого такого `user_id` берём все активные FCM-токены из таблицы `fcm_tokens`.
- Итого: один и тот же пуш уходит на все токены всех этих пользователей (без дублирования токенов).

## Хранение FCM-токенов

### Таблица `fcm_tokens`

| Колонка     | Тип         | Описание |
|-------------|-------------|----------|
| id          | BIGSERIAL   | PK |
| user_id     | BIGINT      | FK → users(id), NOT NULL |
| token       | TEXT        | UNIQUE, FCM device token |
| platform    | TEXT        | опционально: `android` / `ios` / `web` |
| created_at  | TIMESTAMPTZ | DEFAULT now() |
| updated_at  | TIMESTAMPTZ | при каждом обновлении (при повторной регистрации с того же устройства) |

- Один пользователь — много токенов (несколько устройств).
- Один токен — один пользователь (UNIQUE по `token`).
- При повторной регистрации того же `token` для того же `user_id` — обновлять `updated_at` (upsert).

### Миграция

Добавить в `schema.sql` (или отдельная миграция):

```sql
CREATE TABLE IF NOT EXISTS fcm_tokens (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    platform   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fcm_tokens_user_id ON fcm_tokens(user_id);
```

## API для клиента

- **POST /fcm-token** (auth required)  
  Тело: `{ "token": "<FCM token>", "platform": "android" | "ios" | "web" }`  
  Действие: upsert токена для текущего пользователя (по Firebase ID token из Bearer).  
  Ответ: 200 + `{ "registered": true }` или 400 при пустом/невалидном token.

- **DELETE /fcm-token** (auth required)  
  Тело или query: `token=...`  
  Действие: удалить токен для текущего пользователя (logout с устройства).

Регистрация токена выполняется при логине/старте приложения; при получении нового токена (например, после обновления Firebase) клиент снова вызывает POST.

## Содержимое push-сообщения

- **Notification** (заголовок/текст для отображения в трее):
  - received: например *«SMS»* / *«От +79001234567: начало текста…»*
  - sent: по желанию *«Отправлено»* / *«Отправлено на +79001234567»*
- **Data payload** (для навигации/обновления UI):
  - `type`: `sms_received` | `sms_sent`
  - `sms_id`: id записи в БД
  - `device_id`: модем/мост
  - `remote_number`: номер отправителя/получателя
  - `direction`: `received` | `sent`
  - при желании: короткий `text_preview` (первые N символов)

Ограничение FCM: в `data` все значения — строки. Числа передавать как строки (например `sms_id`).

## Отправка (backend)

1. После `insert_sms()` для выбранных направлений (`received` всегда, `sent` по конфигу):
   - По `device_id` из строки получить список `user_id` (функция в `db.py`: `get_user_ids_for_device(conn, device_id)`).
   - Для каждого `user_id` получить список токенов (функция `get_fcm_tokens_for_user(conn, user_id)`).
2. Собрать уникальный список токенов (один пользователь мог попасть из нескольких устройств — не дублировать).
3. Если токенов 0 — ничего не делать.
4. Сформировать одно и то же сообщение для всех (notification + data).
5. Вызвать `firebase_admin.messaging.send_each_for_multicast(MulticastMessage(...))` (до 500 токенов за раз; при большем количестве — батчи по 500).
6. Обработка ответа:
   - Успехи — логировать количество.
   - Ошибки: для кодов типа `invalid_argument`, `unregistered`, `registration-token-not-registered` — удалить соответствующие токены из БД, чтобы не слать повторно.

Инициализация Firebase уже есть в `auth_firebase.py`; модуль `firebase_admin.messaging` использует тот же `default` app. Отправку вынести в отдельный модуль, например `push.py`, и вызывать его из listener’а после insert.

## Конфигурация

| Переменная      | По умолчанию | Описание |
|-----------------|--------------|----------|
| PUSH_ENABLED    | true         | Включить отправку пушей (false — только персист, без FCM). |
| PUSH_ON_SENT    | false        | Отправлять пуш и при исходящем SMS. |

Пушы имеют смысл только при включённом API (есть Firebase credentials и пользователи). Если `API_PORT` не задан или нет `FIREBASE_CREDENTIALS`, пуш-модуль не инициализировать / не вызывать.

## Зависимости

- Только `firebase-admin` (уже в pyproject.toml). FCM входит в тот же пакет.

## Риски и упрощения

- **Задержка**: отправка пуша после insert добавляет латентность. Делать отправку асинхронно (фоновая задача/очередь) не обязательно в первой версии: FCM быстрый; при желании позже можно вынести в thread/queue.
- **Частота**: при лавине SMS — много пушей. Можно добавить троттлинг (не более N пушей на пользователя в минуту) в следующей итерации.
- **Приватность**: в notification не класть полный текст длинного SMS — только превью (например, первые 50 символов).

## План реализации (кратко)

1. Схема: таблица `fcm_tokens`, миграция/schema.sql.
2. `db.py`: `get_user_ids_for_device()`, `get_fcm_tokens_for_user()`, upsert/delete токена.
3. `push.py`: инициализация FCM (переиспользовать существующий init), `send_sms_push(conn, config, row)` — по row после insert получает user_ids, токены, шлёт multicast, при ошибках удаляет невалидные токены.
4. `listener.py`: после успешного `insert_sms()` для подходящего direction вызывать `send_sms_push()` (если push включён и конфиг есть).
5. API: `POST/DELETE /fcm-token` в `api.py`.
6. Конфиг: `PUSH_ENABLED`, `PUSH_ON_SENT` в `config.py`, передача в listener и push.

---

После согласования этого дизайна можно переходить к реализации.
