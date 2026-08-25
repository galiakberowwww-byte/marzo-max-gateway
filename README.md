# MARZO MAX Gateway

Минимальный backend для приёма событий MAX через Webhook и отправки ответов через MAX Bot API.

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
