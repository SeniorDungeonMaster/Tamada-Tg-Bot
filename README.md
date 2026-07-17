# Telegram lead bot for Render

Этот сервис принимает заявку с сайта на `POST /lead` и отправляет ее нужным пользователям в Telegram через бота.

## Переменные Render

Обязательные:

- `TELEGRAM_BOT_TOKEN` - токен от BotFather.
- `TELEGRAM_CHAT_IDS` - id получателей через запятую, например `123456789,987654321`.

Опциональные:

- `ALLOWED_ORIGINS` - домены сайта через запятую. Для быстрого старта можно оставить `*`.
- `TELEGRAM_WEBHOOK_SECRET` - секрет для Telegram webhook. В `render.yaml` он генерируется автоматически.

## Как получить chat_id

1. Создайте бота в `@BotFather` и сохраните токен в `TELEGRAM_BOT_TOKEN`.
2. Задеплойте сервис на Render.
3. Задайте webhook для бота:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<RENDER_APP>.onrender.com/telegram/webhook
```

Если вы вручную указали `TELEGRAM_WEBHOOK_SECRET`, добавьте его в URL:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<RENDER_APP>.onrender.com/telegram/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>
```

4. Каждый получатель должен открыть бота в Telegram и отправить `/start`.
5. Бот ответит сообщением с `chat_id`.
6. Добавьте эти id в `TELEGRAM_CHAT_IDS` на Render и перезапустите сервис.

## Подключение сайта

Если сайт открывается с этого же Render-сервиса, в `index.html` уже стоит:

```html
<form class="quiz-form" id="costForm" data-api-url="/lead">
```

Если сайт размещен отдельно, замените `data-api-url` на полный адрес Render:

```html
<form class="quiz-form" id="costForm" data-api-url="https://<RENDER_APP>.onrender.com/lead">
```

И поставьте `ALLOWED_ORIGINS` равным домену сайта, например:

```text
https://example.com
```

## Локальный запуск

```bash
pip install -r bot/requirements.txt
python -m bot.app
```

Проверка:

```bash
curl http://localhost:8000/healthz
```
