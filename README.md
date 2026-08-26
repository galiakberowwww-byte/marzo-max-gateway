# RODCOM MAX Gateway

Транспортный ingress для существующего MAX-бота проекта «Родком».

Репозиторий исторически называется `marzo-max-gateway`, но пользовательских сценариев MARZO здесь больше нет. Сервис принимает события MAX на стабильном endpoint `/webhooks/max` и пересылает их без продуктовой маршрутизации в канонический backend Родкома:

`POST /api/v1/integrations/max/webhook`

Backend Родкома формирует `BotView` и возвращает его через защищённый внутренний транспорт gateway:

`POST /internal/rodcom/send`

Gateway остаётся единственным владельцем существующего `MAX_BOT_TOKEN` и только доставляет подготовленный Rodcom view в MAX. Вся бизнес-логика, роли, multi-community, сборы, согласования, состав класса и финансовые сценарии остаются в репозитории `rodcom`.

## Переменные окружения

- `MAX_BOT_TOKEN` — токен существующего MAX-бота;
- `MAX_WEBHOOK_SECRET` — секрет, которым MAX подписывает входящий webhook;
- `RODCOM_WEBHOOK_URL` — публичный URL канонического Rodcom webhook;
- `RODCOM_WEBHOOK_SECRET` — отдельный секрет между gateway и Rodcom webhook;
- `RODCOM_BRIDGE_SECRET` — секрет обратного канала Rodcom → gateway;
- `PUBLIC_WEBHOOK_URL` — текущий публичный MAX webhook URL; при старте gateway проверяет, что подписка включает callback-события;
- `MAX_CA_BUNDLE` — CA bundle для исходящих запросов к MAX API;
- `RODCOM_REQUEST_TIMEOUT_SECONDS` — timeout проксирования, по умолчанию 10 секунд.

Если `RODCOM_WEBHOOK_URL` не задан, `/webhooks/max` возвращает `503`. Если `RODCOM_BRIDGE_SECRET` не задан, `/internal/rodcom/send` возвращает `503`. Оба режима fail-closed.

## Локальный запуск

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:MAX_BOT_TOKEN = 'test-token'
$env:MAX_WEBHOOK_SECRET = 'local-secret'
$env:RODCOM_WEBHOOK_URL = 'https://rodcom.example/api/v1/integrations/max/webhook'
$env:RODCOM_WEBHOOK_SECRET = 'rodcom-inbound-secret'
$env:RODCOM_BRIDGE_SECRET = 'rodcom-bridge-secret-1234'
uvicorn app.main:app --reload
```

## MAX subscription

Для Rodcom нужны события:

- `bot_started`;
- `message_created`;
- `message_callback`.

Если задан `PUBLIC_WEBHOOK_URL`, gateway проверяет подписку при старте и добавляет недостающий `message_callback`. Ручной скрипт регистрации остаётся резервным способом:

```powershell
python -m scripts.register_webhook https://marzo-max-gateway.onrender.com/webhooks/max
```

Стабильный внешний URL старого Render-сервиса сохраняется; переименование сервиса для переключения логики на Родком не требуется.
