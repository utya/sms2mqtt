# Запуск через Dockge

[Dockge](https://github.com/louislam/dockge) — веб-интерфейс для управления Docker Compose стеками. Ниже — как запустить sms2mqtt как стек в Dockge.

## 1. Подготовка на сервере

Убедитесь, что проект доступен на том же хосте, где работает Dockge (например, клонирован в `/opt/stacks/sms2mqtt` или в папку, которую Dockge использует для стеков).

```bash
# Пример: клонировать в каталог стеков Dockge (путь может отличаться)
git clone https://github.com/Domochip/sms2mqtt.git /opt/stacks/sms2mqtt
cd /opt/stacks/sms2mqtt
```

## 2. Конфигурация

1. **Создайте `.env`** из примера и задайте параметры MQTT и при необходимости PIN модема:

   ```bash
   cp .env.example .env
   # Отредактируйте .env: HOST, PORT, USER, PASSWORD, USETLS и т.д.
   ```

2. **Модем (USB):** если используете реальный GSM-модем, в `compose.yml` раскомментируйте и укажите устройство:

   ```yaml
   devices:
     - "/dev/ttyUSB0:/dev/mobile"
   ```

   Для стабильного пути после перезагрузки лучше использовать, например:  
   `/dev/serial/by-id/usb-...:/dev/mobile`.

## 3. Создание стека в Dockge

1. В веб-интерфейсе Dockge: **Stacks** → **Create New Stack**.
2. **Stack name:** например `sms2mqtt`.
3. **Path:** укажите путь к папке проекта (например `/opt/stacks/sms2mqtt`), где лежат `compose.yml` и `.env`.
4. Оставьте **Compose file** как `compose.yml` (или укажите свой файл).
5. **Create** → затем **Deploy** (или **Start**).

Dockge подхватит `compose.yml` и `.env` из этой папки.

## 4. Опционально: persistence (PostgreSQL)

Если нужна опциональная персистентность SMS в PostgreSQL:

- В Dockge для этого стека можно указать **Compose file** как несколько файлов (если ваша версия Dockge поддерживает), например:  
  `compose.yml` + `docker-compose.persistence.yml`  
  и при деплое включить профиль `persistence`.

- Либо подготовить один объединённый `docker-compose.yml` вручную и указать его в Dockge, с профилем `persistence` для сервисов персистентности.

## 5. Проверка

- Логи: в Dockge откройте стек → вкладка логов контейнера `sms2mqtt`, или в терминале:  
  `docker compose -f /path/to/sms2mqtt/compose.yml logs -f sms2mqtt`
- Отправка тестового SMS через MQTT на топик `{PREFIX}/send` (см. [MQTT Topics](mqtt-topics.md)).

## Важно

- Не коммитьте `.env` с паролями и PIN.
- MQTT-брокер должен быть доступен с хоста/сети, где запущен контейнер (указанный `HOST`/`PORT`).
