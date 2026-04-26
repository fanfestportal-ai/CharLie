import gradio as gr
import json
import os
import requests
import torch
import pyaudio
import numpy as np
import tempfile
import soundfile as sf
import time

GIGACHAT_KEY = "MDE5ZDVkY2ItNzA4ZS03OTQ3LThjMDYtZmI0YmQxMzg1ZjM2Ojg0NDU1MWNkLTZmZTItNGE3OS1hYjQyLTBjY2Y1OGJjYjA4Yg=="


def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "character": {"name": "Чарли", "personality": "Ты добрый собеседник.", "response_style": "Отвечай кратко."},
        "address": {"user_name": "Хозяйка", "pronoun": "ты"}
    }


# ========== ЗАГРУЗКА SILERO (ЛЁГКАЯ МОДЕЛЬ) ==========
print("🔄 Загрузка Silero TTS (лёгкая модель, ~100MB)...")
device = torch.device('cpu')
silero_model, _ = torch.hub.load('snakers4/silero-models', 'silero_tts',
                                 language='ru', speaker='ru_v3', trust_repo=True)
silero_model.to(device)
print("✅ Silero голос загружен! Используется голос: aidar (мужской, спокойный)")


def speak(text):
    """Озвучивание через Silero (лёгкая модель)"""
    try:
        print(f"🎤 Озвучиваю: {text[:50]}...")

        audio = silero_model.apply_tts(text=text, speaker='aidar', sample_rate=48000,
                                       put_accent=True, put_yo=True)
        audio_np = audio.numpy()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            sf.write(f.name, audio_np, 48000)
            return f.name
    except Exception as e:
        print(f"TTS ошибка: {e}")
        return None


def get_gigachat_response(user_text):
    try:
        config = load_config()
        character = config["character"]
        address = config["address"]

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

        system_prompt = f"""
Ты — {character['name']}. 
Твой характер: {character['personality']}
Обращайся к пользователю на "{address['pronoun']}" и называй его {address['user_name']}.
Отвечай кратко, 2-4 предложения.
"""

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
        answer = result["choices"][0]["message"]["content"]
        print(f"🎭 Чарли: {answer}")
        return answer

    except Exception as e:
        print(f"GigaChat ошибка: {e}")
        return "Извините, произошла ошибка"


def respond(message, history):
    if not message:
        return "", history, None
    bot_message = get_gigachat_response(message)
    audio_file = speak(bot_message)
    history.append((message, bot_message))
    return "", history, audio_file


# ========== СОЗДАНИЕ ИНТЕРФЕЙСА ==========
with gr.Blocks(title="Чарли - голосовой ассистент", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎭 Чарли")
    gr.Markdown("Ваш персональный голосовой ассистент. Пишите — он ответит голосом!")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="Диалог с Чарли", height=500)
            msg = gr.Textbox(label="Ваше сообщение:", placeholder="Напишите что-нибудь...", lines=2)
            with gr.Row():
                send_btn = gr.Button("Отправить", variant="primary")
                clear_btn = gr.ClearButton([msg, chatbot])

        with gr.Column(scale=1):
            audio_output = gr.Audio(label="Голос Чарли", type="filepath", autoplay=True)

    send_btn.click(respond, [msg, chatbot], [msg, chatbot, audio_output])
    msg.submit(respond, [msg, chatbot], [msg, chatbot, audio_output])

demo.launch()