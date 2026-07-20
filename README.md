# Telegram lead bot

Небольшой Node.js-сервис, который принимает заявку с анкеты сайта и отправляет ее нужным пользователям через Telegram-бота.

## Как это работает

```text
GitHub Pages -> POST /api/lead -> этот сервер -> Telegram Bot API -> нужные chat_id
```

Токен Telegram-бота хранится только на сервере в переменных окружения и не попадает в `script.js`.

## Локальный запуск

1. Скопируйте `.env.example` в `.env`.
2. Заполните:
   - `TELEGRAM_BOT_TOKEN` - токен из BotFather.
   - `TELEGRAM_CHAT_IDS` - получатели через запятую.
   - `ALLOWED_ORIGINS` - домены сайта, например `https://romanenkoevent.ru`.
3. Запустите:

```bash
npm start
```

Проверка:

```bash
curl http://localhost:3000/health
```

Endpoint для сайта:

```text
POST /api/lead
```

## Render

Создайте Web Service:

- Root Directory: `bot`
- Runtime: Node
- Build Command: пусто или `npm install`
- Start Command: `npm start`

В Environment добавьте:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_IDS=123456789,987654321
ALLOWED_ORIGINS=https://romanenkoevent.ru
```

После деплоя вставьте URL сервиса в `script.js`:

```js
const LEAD_ENDPOINT = "https://your-service.onrender.com/api/lead";
```

## Как узнать chat_id

1. Напишите любое сообщение своему Telegram-боту.
2. Откройте:

```text
https://api.telegram.org/bot<token>/getUpdates
```

3. Найдите `message.chat.id`.

Для группы добавьте бота в группу и тоже посмотрите `chat.id` через `getUpdates`.
