import http from "node:http";
import fs from "node:fs";
import path from "node:path";

loadDotEnv();

const PORT = Number(process.env.PORT || 3000);
const TELEGRAM_API_BASE = process.env.TELEGRAM_API_BASE || "https://api.telegram.org";
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const TELEGRAM_CHAT_IDS = splitEnv(process.env.TELEGRAM_CHAT_IDS);
const TELEGRAM_SEND_TIMEOUT_MS = Number(process.env.TELEGRAM_SEND_TIMEOUT_MS || 10000);
const ALLOWED_ORIGINS = splitEnv(process.env.ALLOWED_ORIGINS);

function loadDotEnv() {
    const envPath = path.join(process.cwd(), ".env");

    if (!fs.existsSync(envPath)) {
        return;
    }

    const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);

    for (const line of lines) {
        const trimmed = line.trim();

        if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
            continue;
        }

        const [key, ...valueParts] = trimmed.split("=");
        const value = valueParts.join("=").trim().replace(/^["']|["']$/g, "");

        if (key && process.env[key] === undefined) {
            process.env[key] = value;
        }
    }
}

function splitEnv(value = "") {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function getAllowedOrigin(origin) {
    if (!origin) {
        return "*";
    }

    if (ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin)) {
        return origin;
    }

    return "";
}

function setCorsHeaders(response, origin) {
    const allowedOrigin = getAllowedOrigin(origin);

    if (allowedOrigin) {
        response.setHeader("Access-Control-Allow-Origin", allowedOrigin);
        response.setHeader("Vary", "Origin");
    }

    response.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS, GET");
    response.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

function sendJson(response, statusCode, data, origin) {
    setCorsHeaders(response, origin);
    response.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
    response.end(JSON.stringify(data));
}

async function readJsonBody(request) {
    const chunks = [];
    let totalBytes = 0;

    for await (const chunk of request) {
        totalBytes += chunk.length;

        if (totalBytes > 64 * 1024) {
            throw new Error("Request body is too large");
        }

        chunks.push(chunk);
    }

    const raw = Buffer.concat(chunks).toString("utf8");
    return raw ? JSON.parse(raw) : {};
}

function sanitizeText(value) {
    return String(value || "").trim();
}

function buildLeadMessage(payload) {
    const gift = sanitizeText(payload.gift);
    const name = sanitizeText(payload.name);
    const age = sanitizeText(payload.age);
    const direction = sanitizeText(payload.direction);
    const about = sanitizeText(payload.about) || "Не указано";
    const contact = sanitizeText(payload.contact);
    const source = sanitizeText(payload.source);

    return [
        "Заявка на расчет стоимости",
        "",
        `Подарок: ${gift}`,
        `Имя: ${name}`,
        `Возраст: ${age}`,
        `Направление: ${direction}`,
        `О себе: ${about}`,
        `Где связаться: ${contact}`,
        source ? `Источник: ${source}` : ""
    ].filter(Boolean).join("\n").slice(0, 3900);
}

function validateLead(payload) {
    const requiredFields = ["gift", "name", "age", "direction", "contact"];
    const missingFields = requiredFields.filter((field) => !sanitizeText(payload[field]));

    if (missingFields.length > 0) {
        return `Missing required fields: ${missingFields.join(", ")}`;
    }

    if (!TELEGRAM_BOT_TOKEN) {
        return "TELEGRAM_BOT_TOKEN is not configured";
    }

    if (TELEGRAM_CHAT_IDS.length === 0) {
        return "TELEGRAM_CHAT_IDS is not configured";
    }

    return "";
}

async function sendTelegramMessage(chatId, text) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TELEGRAM_SEND_TIMEOUT_MS);

    try {
        const response = await fetch(`${TELEGRAM_API_BASE}/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                chat_id: chatId,
                text,
                disable_web_page_preview: true
            }),
            signal: controller.signal
        });
        const responseText = await response.text();

        if (!response.ok) {
            throw new Error(`Telegram chat_id=${chatId} failed: ${response.status} ${responseText}`);
        }

        return responseText ? JSON.parse(responseText) : {};
    } finally {
        clearTimeout(timeoutId);
    }
}

async function sendLeadToTelegram(payload) {
    const text = buildLeadMessage(payload);
    const results = await Promise.all(TELEGRAM_CHAT_IDS.map((chatId) => sendTelegramMessage(chatId, text)));

    return results.length;
}

const server = http.createServer(async (request, response) => {
    const origin = request.headers.origin || "";
    const url = new URL(request.url || "/", `http://${request.headers.host}`);

    if (request.method === "OPTIONS") {
        setCorsHeaders(response, origin);
        response.writeHead(204);
        response.end();
        return;
    }

    if (url.pathname === "/health" && request.method === "GET") {
        sendJson(response, 200, { ok: true }, origin);
        return;
    }

    if (url.pathname !== "/api/lead" || request.method !== "POST") {
        sendJson(response, 404, { ok: false, error: "Not found" }, origin);
        return;
    }

    if (ALLOWED_ORIGINS.length > 0 && !getAllowedOrigin(origin)) {
        sendJson(response, 403, { ok: false, error: "Origin is not allowed" }, origin);
        return;
    }

    try {
        const payload = await readJsonBody(request);
        const validationError = validateLead(payload);

        if (validationError) {
            sendJson(response, 400, { ok: false, error: validationError }, origin);
            return;
        }

        const delivered = await sendLeadToTelegram(payload);
        sendJson(response, 200, { ok: true, delivered }, origin);
    } catch (error) {
        console.error(error);
        sendJson(response, 500, { ok: false, error: "Lead delivery failed" }, origin);
    }
});

server.listen(PORT, () => {
    console.log(`Telegram lead bot is running on port ${PORT}`);
});
