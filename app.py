from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import requests
from flask import Flask, abort, jsonify, make_response, request, send_from_directory


ROOT_DIR = Path(__file__).resolve().parent.parent
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
STATIC_EXTENSIONS = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webmanifest", ".txt"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024


class AppConfigError(RuntimeError):
    pass


def env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    if not token:
        raise AppConfigError("TELEGRAM_BOT_TOKEN is not configured")

    return token


def get_chat_ids() -> list[str]:
    chat_ids = env_list("TELEGRAM_CHAT_IDS")

    if not chat_ids:
        raise AppConfigError("TELEGRAM_CHAT_IDS is not configured")

    return chat_ids


def origin_is_allowed(origin: str | None) -> bool:
    if not origin:
        return True

    allowed_origins = env_list("ALLOWED_ORIGINS", "*")
    return "*" in allowed_origins or origin in allowed_origins


def cors_response(response):
    origin = request.headers.get("Origin")
    allowed_origins = env_list("ALLOWED_ORIGINS", "*")

    if origin and origin_is_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = "*" if "*" in allowed_origins else origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def clean_text(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    return text[:max_length]


def parse_lead(payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    lead = {
        "gift": clean_text(payload.get("gift"), 120),
        "name": clean_text(payload.get("name"), 120),
        "age": clean_text(payload.get("age"), 20),
        "direction": clean_text(payload.get("direction"), 160),
        "about": clean_text(payload.get("about"), 1400),
        "contact": clean_text(payload.get("contact"), 400),
        "page": clean_text(payload.get("page"), 500),
    }
    errors = {}

    for field in ("gift", "name", "age", "direction", "contact"):
        if not lead[field]:
            errors[field] = "required"

    return lead, errors


def tg_escape(value: str, fallback: str = "Не указано") -> str:
    return html.escape(value or fallback)


def format_lead_message(lead: dict[str, str]) -> str:
    lines = [
        "<b>Новая заявка на расчет стоимости</b>",
        "",
        f"<b>Подарок:</b> {tg_escape(lead['gift'])}",
        f"<b>Имя:</b> {tg_escape(lead['name'])}",
        f"<b>Возраст:</b> {tg_escape(lead['age'])}",
        f"<b>Направление:</b> {tg_escape(lead['direction'])}",
        f"<b>О себе:</b> {tg_escape(lead['about'])}",
        f"<b>Где связаться:</b> {tg_escape(lead['contact'])}",
    ]

    if lead.get("page"):
        lines.extend(["", f"<b>Страница:</b> {tg_escape(lead['page'])}"])

    return "\n".join(lines)


def telegram_request(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = TELEGRAM_API_BASE.format(token=get_bot_token(), method=method)
    response = requests.post(url, json=payload, timeout=12)

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Telegram returned non-json response: {response.text[:300]}") from exc

    if not response.ok or not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")

    return data


def send_lead_to_telegram(lead: dict[str, str]) -> None:
    message = format_lead_message(lead)

    for chat_id in get_chat_ids():
        telegram_request(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )


@app.get("/healthz")
def healthz():
    return jsonify(ok=True)


@app.route("/lead", methods=["POST", "OPTIONS"])
def lead():
    if request.method == "OPTIONS":
        return cors_response(make_response("", 204))

    if not origin_is_allowed(request.headers.get("Origin")):
        return cors_response(make_response(jsonify(ok=False, error="origin_not_allowed"), 403))

    payload = request.get_json(silent=True) or {}
    parsed_lead, errors = parse_lead(payload)

    if errors:
        return cors_response(make_response(jsonify(ok=False, error="validation_error", fields=errors), 400))

    try:
        send_lead_to_telegram(parsed_lead)
    except AppConfigError as exc:
        app.logger.exception("Missing configuration")
        return cors_response(make_response(jsonify(ok=False, error=str(exc)), 500))
    except Exception:
        app.logger.exception("Failed to send lead")
        return cors_response(make_response(jsonify(ok=False, error="telegram_send_failed"), 502))

    return cors_response(jsonify(ok=True))


@app.post("/telegram/webhook")
def telegram_webhook():
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

    if webhook_secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != webhook_secret:
        abort(403)

    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()

    if chat_id and text.startswith("/start"):
        telegram_request(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"Бот подключен. Ваш chat_id: {chat_id}\nДобавьте этот id в TELEGRAM_CHAT_IDS на Render.",
            },
        )

    return jsonify(ok=True)


@app.get("/")
def serve_index():
    return send_from_directory(ROOT_DIR, "index.html")


@app.get("/<path:filename>")
def serve_static(filename: str):
    target = (ROOT_DIR / filename).resolve()

    if ROOT_DIR not in target.parents and target != ROOT_DIR:
        abort(404)

    if ".git" in target.parts or "bot" in target.parts or target.suffix.lower() not in STATIC_EXTENSIONS:
        abort(404)

    if not target.is_file():
        abort(404)

    return send_from_directory(target.parent, target.name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
