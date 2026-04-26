import gradio as gr
import json
import os
import requests
import torch
import tempfile
import soundfile as sf
from datetime import datetime

# ========== НАСТРОЙКИ ==========
GIGACHAT_KEY = "MDE5ZDVkY2ItNzA4ZS03OTQ3LThjMDYtZmI0YmQxMzg1ZjM2Ojg0NDU1MWNkLTZmZTItNGE3OS1hYjQyLTBjY2Y1OGJjYjA4Yg=="

# ========== КАСТОМНЫЙ CSS ==========
custom_css = """
:root {
    --yellow: #F4C542;
    --black: #111111;
    --cream: #F8E7B5;
    --orange: #F27A54;
    --bg: #ffffff;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    background: var(--bg);
    font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
}

.gradio-container {
    background-image:
        radial-gradient(circle at 20% 20%, var(--yellow) 8px, transparent 9px),
        repeating-linear-gradient(45deg, var(--yellow), var(--yellow) 10px, white 10px, white 20px),
        linear-gradient(135deg, rgba(242,122,84,0.08), rgba(244,197,66,0.08));
    background-size: 120px 120px, 200px 200px, cover;
    background-attachment: fixed;
    min-height: 100vh;
}

.gradio-container::after {
    content: "";
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 100px;
    background: repeating-linear-gradient(
        90deg,
        var(--yellow),
        var(--yellow) 12px,
        transparent 12px,
        transparent 24px
    );
    opacity: 0.3;
    pointer-events: none;
    z-index: 1000;
}

.gr-box, .gradio-card, .tab-nav {
    border-radius: 24px !important;
    border: 2px solid var(--black) !important;
    box-shadow: 8px 8px 0px rgba(0,0,0,0.1) !important;
    background: rgba(255,255,255,0.95) !important;
}

@keyframes floaty {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-6px); }
    100% { transform: translateY(0px); }
}

.gr-box {
    animation: floaty 8s ease-in-out infinite;
}

button, .gr-button {
    background: var(--yellow) !important;
    color: var(--black) !important;
    border: 2px solid var(--black) !important;
    border-radius: 16px !important;
    font-weight: 700 !important;
    padding: 10px 20px !important;
    transition: all 0.2s cubic-bezier(0.2, 0.9, 0.4, 1.1) !important;
    cursor: pointer !important;
}

button:hover, .gr-button:hover {
    background: var(--orange) !important;
    transform: translate(-3px, -3px) !important;
    box-shadow: 6px 6px 0px var(--black) !important;
}

button:active {
    transform: translate(2px, 2px) !important;
    box-shadow: 2px 2px 0px var(--black) !important;
}

textarea, input, .gr-textbox {
    border-radius: 16px !important;
    border: 2px solid var(--black) !important;
    background: white !important;
    font-size: 15px !important;
}

textarea:focus, input:focus {
    border-color: var(--orange) !important;
    box-shadow: 0 0 0 3px rgba(242,122,84,0.2) !important;
    outline: none !important;
}

.message {
    padding: 12px 18px;
    border-radius: 18px;
    max-width: 80%;
    margin-bottom: 12px;
}

.message.user {
    background: var(--cream);
    border-bottom-right-radius: 4px;
    margin-left: auto;
}

.message.bot {
    background: white;
    border: 1px solid var(--yellow);
    border-bottom-left-radius: 4px;
    margin-right: auto;
}

audio {
    border-radius: 40px !important;
    background: var(--cream) !important;
    margin-top: 12px;
}

h1, h2, h3 {
    color: var(--black) !important;
    font-weight: 800 !important;
}

::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: var(--cream);
    border-radius: 10px;
}

::-webkit-scrollbar-thumb {
    background: var(--yellow);
    border-radius: 10px;
}
"""

# ========== ЗАГРУЗКА ГОЛОСА ==========
print("🔄 Загрузка Qwen3-TTS...")

try:
    from qwen_tts import Qwen3TTSModel

    tts_model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        device_map="auto",
        dtype=torch.bfloat16
    )
    print("✅ Голос Aiden загружен!")
    TTS_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Qwen3-TTS не загрузился: {e}")
    tts_model = None
    TTS_AVAILABLE = False


def speak(text):
    if not TTS_AVAILABLE or tts_model is None:
        return ""
    try:
        wavs, sr = tts_model.generate_custom_voice(
            text=text,
            language="Russian",
            speaker="Aiden",
            instruct="спокойным, добрым голосом"
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            sf.write(f.name, wavs[0], sr)
            return f.name
    except Exception as e:
        print(f"TTS ошибка: {e}")
        return ""


# ========== ЗАГРУЗКА ДАННЫХ ==========
USER_PROFILE_FILE = "user_profile.json"
CHARACTER_PROFILE_FILE = "character_profile.json"
SCENARIOS_FILE = "scenarios.json"
NOTES_FILE = "notes.json"


def load_file(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== GIGACHAT ==========
def get_gigachat_response(user_text):
    try:
        user_profile = load_file(USER_PROFILE_FILE, {"user_name": "Друг", "pronoun": "ты", "city": "Москва"})
        character_profile = load_file(CHARACTER_PROFILE_FILE, {"name": "Чарли", "personality": "Ты добрый собеседник."})

        system_prompt = f"""
Ты — {character_profile.get('name', 'Чарли')}. 
Твой характер: {character_profile.get('personality', 'Ты добрый собеседник.')}
Обращайся к пользователю на "{user_profile.get('pronoun', 'ты')}" и называй его {user_profile.get('user_name', 'Друг')}.
Отвечай кратко, 2-4 предложения.
"""

        auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": "12345678-1234-1234-1234-123456789012",
            "Authorization": f"Basic {GIGACHAT_KEY}"
        }
        auth_data = {"scope": "GIGACHAT_API_PERS"}
        auth_response = requests.post(auth_url, headers=auth_headers, data=auth_data, verify=False)
        token = auth_response.json().get("access_token")

        if not token:
            return "Ошибка авторизации"

        api_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        api_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }

        api_data = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.8,
            "max_tokens": 200
        }

        response = requests.post(api_url, headers=api_headers, json=api_data, verify=False)
        result = response.json()
        return result["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"GigaChat ошибка: {e}")
        return "Извините, произошла ошибка"


# ========== ПОГОДА И ВРЕМЯ ==========
def get_weather(city="Москва"):
    try:
        url = f"https://wttr.in/{city}?format=%C,+%t&lang=ru"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        return "Не удалось получить погоду"
    except:
        return "Ошибка погоды"


def get_time():
    now = datetime.now()
    months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
              'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    return now.strftime(f"%H:%M, %d {months[now.month - 1]} %Y")


# ========== ОБРАБОТЧИКИ ==========
def respond(message, history):
    if not message:
        return history, "", ""

    user_profile = load_file(USER_PROFILE_FILE, {"city": "Москва"})

    if message.lower() == "погода":
        bot_msg = get_weather(user_profile.get("city", "Москва"))
    elif message.lower() == "время":
        bot_msg = get_time()
    else:
        bot_msg = get_gigachat_response(message)

    history.append((message, bot_msg))
    audio_file = speak(bot_msg) or ""

    return history, audio_file, ""


def clear_history():
    return [], "", ""


def save_profile(user_name, pronoun, city, mbti, temperament, favorite_topics, stress_response, extra):
    save_file(USER_PROFILE_FILE, {
        "user_name": user_name, "pronoun": pronoun, "city": city,
        "mbti": mbti, "temperament": temperament,
        "favorite_topics": favorite_topics, "stress_response": stress_response,
        "extra": extra
    })
    return "✅ Профиль сохранён!"


def save_character(name, personality, response_style):
    save_file(CHARACTER_PROFILE_FILE, {
        "name": name, "personality": personality, "response_style": response_style
    })
    return "✅ Личность Чарли сохранена!"


def add_note(note_text):
    if note_text.strip():
        notes = load_file(NOTES_FILE, {"notes": []})
        notes["notes"].append({"text": note_text, "date": datetime.now().isoformat()})
        save_file(NOTES_FILE, notes)
        return "", render_notes()
    return "", render_notes()


def render_notes():
    notes = load_file(NOTES_FILE, {"notes": []})
    if not notes.get("notes"):
        return "<p style='color:#666;'>✨ Нет заметок. Добавьте первую!</p>"
    html = "<ul style='list-style:none;padding:0;'>"
    for n in notes["notes"][-10:]:
        html += f"<li style='background:#F8E7B5;margin:8px 0;padding:12px;border-radius:16px;border:1px solid #111;'><strong>{n['date'][:16]}</strong><br>{n['text']}</li>"
    html += "</ul>"
    return html


def add_scenario(trigger, response):
    if trigger.strip() and response.strip():
        scenarios = load_file(SCENARIOS_FILE, {"scenarios": []})
        scenarios["scenarios"].append({"trigger": trigger, "response": response})
        save_file(SCENARIOS_FILE, scenarios)
        return "", "", render_scenarios()
    return "", "", render_scenarios()


def render_scenarios():
    scenarios = load_file(SCENARIOS_FILE, {"scenarios": []})
    if not scenarios.get("scenarios"):
        return "<p style='color:#666;'>⚙️ Нет сценариев. Добавьте первый!</p>"
    html = "<div style='display:flex;flex-direction:column;gap:12px;'>"
    for s in scenarios["scenarios"]:
        html += f"""
        <div style='background:#F4C54220;padding:16px;border-radius:20px;border:1px solid #F4C542;'>
            <strong style='color:#F27A54;'>🔊 {s['trigger']}</strong>
            <div style='margin-top:8px;'>→ {s['response']}</div>
        </div>
        """
    html += "</div>"
    return html


# ========== ИНТЕРФЕЙС ==========
with gr.Blocks(title="Чарли", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML("""
        <div style="text-align: center; padding: 20px 0 10px 0;">
            <h1 style="font-size: 3.5rem; margin: 0;">🎭 Чарли</h1>
            <p style="font-size: 1.1rem; color: #666;">Ваш персональный голосовой ассистент с характером</p>
            <div style="width: 100px; height: 4px; background: #F4C542; margin: 10px auto; border-radius: 4px;"></div>
        </div>
    """)

    with gr.Tabs():
        with gr.TabItem("💬 Чат"):
            chatbot = gr.Chatbot(height=450, label="Диалог с Чарли")

            with gr.Row():
                msg = gr.Textbox(label="Ваше сообщение", placeholder="Напишите что-нибудь...", scale=4, lines=2)

            with gr.Row():
                send_btn = gr.Button("📤 Отправить", variant="primary", scale=1)
                clear_btn = gr.Button("🗑️ Очистить", scale=1)

            audio_output = gr.Audio(label="🎤 Голос Чарли", type="filepath", autoplay=True)

            send_btn.click(respond, [msg, chatbot], [chatbot, audio_output, msg])
            msg.submit(respond, [msg, chatbot], [chatbot, audio_output, msg])
            clear_btn.click(clear_history, None, [chatbot, audio_output, msg])

        with gr.TabItem("👤 Мой профиль"):
            gr.Markdown("### 📝 Расскажите о себе")

            with gr.Row():
                with gr.Column():
                    user_name = gr.Textbox(label="Как к вам обращаться?", value="Друг")
                    pronoun = gr.Radio(choices=["ты", "вы"], label="Обращение", value="ты")
                    city = gr.Textbox(label="Ваш город", value="Москва")
                with gr.Column():
                    mbti = gr.Textbox(label="Тип личности (MBTI)", placeholder="INFP")
                    temperament = gr.Dropdown(choices=["Холерик", "Сангвиник", "Флегматик", "Меланхолик"],
                                              label="Темперамент")

            favorite_topics = gr.Textbox(label="Любимые темы")
            stress_response = gr.Textbox(label="Реакция на стресс")
            extra = gr.Textbox(label="Дополнительно", lines=2)

            profile_status = gr.Markdown("")
            save_profile_btn = gr.Button("💾 Сохранить профиль")

            save_profile_btn.click(
                save_profile,
                [user_name, pronoun, city, mbti, temperament, favorite_topics, stress_response, extra],
                [profile_status]
            )

        with gr.TabItem("🎭 Личность Чарли"):
            char_name = gr.Textbox(label="Имя", value="Чарли")
            char_personality = gr.Textbox(label="Характер", lines=3,
                                          value="Ты спокойный, добрый и внимательный собеседник.")
            char_response_style = gr.Textbox(label="Стиль ответов", lines=2, value="Отвечай кратко, 2-4 предложения.")

            char_status = gr.Markdown("")
            save_char_btn = gr.Button("💾 Сохранить личность Чарли")

            save_char_btn.click(
                save_character,
                [char_name, char_personality, char_response_style],
                [char_status]
            )

        with gr.TabItem("⚙️ Сценарии"):
            gr.Markdown("### Если скажу → ответь")

            with gr.Row():
                with gr.Column():
                    trigger = gr.Textbox(label="Ключевая фраза", placeholder="доброе утро")
                    response = gr.Textbox(label="Ответ Чарли", placeholder="Доброе утро!")
                    add_scenario_btn = gr.Button("➕ Добавить сценарий")

            scenarios_list = gr.HTML(value=render_scenarios())

            add_scenario_btn.click(
                add_scenario,
                [trigger, response],
                [trigger, response, scenarios_list]
            )

        with gr.TabItem("📝 Заметки"):
            note_input = gr.Textbox(label="Новая заметка", placeholder="Что запомнить?", lines=2)
            add_note_btn = gr.Button("➕ Добавить заметку")
            notes_list = gr.HTML(value=render_notes())

            add_note_btn.click(
                add_note,
                [note_input],
                [note_input, notes_list]
            )

    gr.HTML("""
        <div style="text-align: center; padding: 30px 0 20px 0; margin-top: 30px; border-top: 1px solid #F4C542;">
            <p style="color: #888; font-size: 0.85rem;">
                🎭 Чарли — ваш персональный голосовой ассистент<br>
                Голос: Qwen3-TTS (Aiden) | Нейросеть: GigaChat
            </p>
        </div>
    """)

if __name__ == "__main__":
    import os
port = int(os.environ.get("PORT", 7860))
demo.launch(server_name="0.0.0.0", server_port=port)
