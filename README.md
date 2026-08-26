# RODCOM MAX Gateway

Транспортный ingress для существующего MAX-бота проекта «Родком».

Репозиторий исторически называется `marzo-max-gateway`, но пользовательских сценариев MARZO здесь больше нет. Сервис принимает события MAX на стабильном endpoint `/webhooks/max` и пересылает их без продуктовой маршрутизации в канонический backend Родкома:

`POST /api/v1/integrations/max/webhook`

Вся бизнес-логика, роли, multi-community, сборы, согласования, состав класса и финансовые сценарии остаются в репозитории `rodcom`.

## Переменные окружения

- `MAX_BOT_TOKEN` — токен существующего MAX-бота; нужен для скрипта регистрации подписки;
- `MAX_WEBHOOK_SECRET` — секрет, которым MAX подписывает входящий webhook;
- `RODCOM_WEBHOOK_URL` — публичный URL канонического Rodcom webhook, например `https://<rodcom-host>/api/v1/integrations/max/webhook`;
- `RODCOM_WEBHOOK_SECRET` — секрет Rodcom webhook. Можно оставить пустым, если используется тот же `MAX_WEBHOOK_SECRET`;
- `MAX_CA_BUNDLE` — CA bundle для исходящих запросов скрипта регистрации к MAX API;
- `RODCOM_REQUEST_TIMEOUT_SECONDS` — timeout проксирования, по умолчанию 10 секунд.

Если `RODCOM_WEBHOOK_URL` не задан, сервис запускается, но `/webhooks/max` возвращает `503` — это fail-closed режим, чтобы не возвращать пользователю старый или неподтверждённый продуктовый сценарий.

## Локальный запуск

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:MAX_BOT_TOKEN = 'test-token'
$env:MAX_WEBHOOK_SECRET = 'local-secret'
$env:RODCOM_WEBHOOK_URL = 'https://rodcom.example/api/v1/integrations/max/webhook'
uvicorn app.main:app --reload
```

Проверка:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## MAX subscription

Для Rodcom нужны события:

- `bot_started`;
- `message_created`;
- `message_callback`.

Регистрация существующего публичного endpoint:

```powershell
python -m scripts.register_webhook https://<legacy-service>.onrender.com/webhooks/max
```

Стабильный внешний URL старого Render-сервиса можно сохранить: переименование сервиса не требуется для переключения логики на Родком.

## Render

`render.yaml` намеренно сохраняет прежнее имя Render-сервиса, чтобы не создавать второй MAX ingress и не менять публичный webhook URL без необходимости.

После merge обязательно задать в Render `RODCOM_WEBHOOK_URL`. После этого проверить `/health`: поле `rodcomWebhookConfigured` должно быть `true`.
