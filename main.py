import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

user_styles = {}
chat_mode = {}
photo_cache = {}

def send_message(chat_id, text, keyboard=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": [
                [{"text": "\U0001F3AE Изменить стиль"}, {"text": "\U0001F4AC Обычный режим"}],
                [{"text": "\U0001F4F7 Режим с фото"}, {"text": "♻️ Сбросить стиль"}, {"text": "ℹ️ Помощь"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

    requests.post(url, json=payload)

def get_file_url(file_id):
    file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
    file_path = file_info["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if "photo" in message:
        file_id = message["photo"][-1]["file_id"]
        image_url = get_file_url(file_id)
        photo_cache[chat_id] = image_url
        send_message(chat_id, "\U0001F4F8 Фото получено. Теперь напиши, что с ним сделать.")
        print(f"[DEBUG] Photo URL saved: {image_url}")
        return "ok"

    text = message.get("text", "")
    if not text:
        return "ok"

    if text == "/start":
        send_message(chat_id, "\U0001F44B Привет! Я GPT-бот. Пиши вопросы или выбери режим ниже \U0001F447", keyboard=True)
        chat_mode[chat_id] = "text"
        return "ok"

    if text == "/help" or "ℹ️" in text:
        send_message(chat_id,
            "\U0001F9E0 Просто напиши свой вопрос — я отвечу.\n\n\U0001F4CC Команды:\n\U0001F3AE Изменить стиль — /setstyle <твой стиль>\n♻️ Сбросить стиль — /resetstyle\n\U0001F4F7 Режим с фото — сначала нажми кнопку, потом фото и описание.")
        return "ok"

    if text.startswith("/setstyle") or "\U0001F3AE" in text:
        style = text.replace("/setstyle", "").replace("\U0001F3AE Изменить стиль", "").strip()
        if not style:
            send_message(chat_id, "Напиши стиль после команды. Например:\n/setstyle Пиши как коуч из Кремниевой долины")
        else:
            user_styles[chat_id] = style
            send_message(chat_id, f"✅ Стиль установлен: {style}")
        return "ok"

    if text == "/resetstyle" or "♻️" in text:
        user_styles.pop(chat_id, None)
        send_message(chat_id, "\U0001F5FC Стиль сброшен. Теперь я отвечаю нейтрально.")
        return "ok"

    if "\U0001F4F7" in text:
        chat_mode[chat_id] = "vision"
        send_message(chat_id, "Отправь фото, затем текст с задачей — я всё проанализирую.")
        return "ok"

    if "\U0001F4AC" in text:
        chat_mode[chat_id] = "text"
        send_message(chat_id, "Теперь я в обычном режиме. Просто пиши свои запросы.")
        return "ok"

    mode = chat_mode.get(chat_id, "text")
    style = user_styles.get(chat_id, "")
    prompt = f"{style}\n{text}" if style else text

    if mode == "vision" and chat_id in photo_cache:
        image_url = photo_cache.pop(chat_id)
        chat_mode[chat_id] = "text"

        payload = {
            "model": "google/gemini-pro-vision",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        }
        print(f"[DEBUG] Sending to Gemini Vision with image: {image_url}")
    else:
        payload = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}]
        }
        print(f"[DEBUG] Sending to GPT-3.5 (no image)")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/FreeGPTX11_bot",
        "X-Title": "FreeGPTX11"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        print(f"[DEBUG] GPT response: {response.status_code} | {response.text[:200]}")
        if response.status_code == 200:
            reply = response.json().get("choices", [{}])[0].get("message", {}).get("content", "⚠️ Ответ получен, но не удалось извлечь текст.")
            send_message(chat_id, reply)
        else:
            send_message(chat_id, "❌ GPT ошибка: " + response.text)
    except Exception as e:
        print(f"[ERROR] {e}")
        send_message(chat_id, f"❌ Ошибка при обращении к GPT: {e}")

    return "ok"

@app.route("/")
def home():
    return "Бот работает!"

if __name__ == "__main__":
    print(f"[DEBUG] BOT_TOKEN = {BOT_TOKEN}")
    app.run(host="0.0.0.0", port=5000)
