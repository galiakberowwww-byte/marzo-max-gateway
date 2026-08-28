# MARZO MAX Gateway

Изолированный backend MARZO для MAX. Он не использует RODCOM-код, данные или конфигурацию.

MVP: источник из start-параметра, выбор направления, пять вопросов, SQLite-карточка лида и защищённый endpoint для ручного ввода лида менеджером. `INTERIOR_PROJECT_*` — отдельная точка интеграции с общим сервисом фабрики; в MVP она намеренно не отправляет данные без явного контракта API.

## Локальный запуск

Требуется Python 3.11+ и пользовательская переменная Windows `MAX_BOT_TOKEN`.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:MAX_WEBHOOK_SECRET = 'локальный-секрет-для-теста'
uvicorn app.main:app --reload
```

Проверка в другом окне PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Production Webhook

MAX принимает только публичный HTTPS endpoint на порту 443 с доверенным TLS-сертификатом. После размещения приложения задайте на сервере два секрета:

- `MAX_BOT_TOKEN` — токен бота;
- `MAX_WEBHOOK_SECRET` — отдельная случайная строка для проверки заголовка `X-Max-Bot-Api-Secret`.
- `MAX_CA_BUNDLE` — путь к PEM-файлу с доверенной цепочкой НУЦ Минцифры для исходящих запросов к `platform-api2.max.ru`.

Сертификаты НУЦ скачивайте только с официальной страницы Госуслуг `https://www.gosuslugi.ru/crt`. Не отключайте TLS-проверку через `verify=False`.

Зарегистрируйте endpoint:

```powershell
python -m scripts.register_webhook https://example.ru/webhooks/max
```

Скрипт подписывается на `message_created` и `bot_started`. Секреты в консоль не выводятся.

## Размещение на Render

В репозитории есть `render.yaml` и `Dockerfile`. Blueprint создаёт **новый** сервис
`marzo-max-gateway-v2`; не подключайте его к существующему RODCOM-сервису. При создании Render попросит значения, которые нельзя
публиковать в GitHub:

- `MAX_BOT_TOKEN` — существующий токен бота MAX;
- `MAX_WEBHOOK_SECRET` — существующий секрет webhook.
- `MARZO_ADMIN_TOKEN` — отдельный секрет для ручного создания лидов менеджером.

После успешного развёртывания проверьте адрес:

```text
https://<имя-сервиса>.onrender.com/health
```

Затем переключите подписку MAX на постоянный endpoint:

```powershell
python -m scripts.register_webhook https://<имя-сервиса>.onrender.com/webhooks/max
```
