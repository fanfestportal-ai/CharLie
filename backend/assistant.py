import speech_recognition as sr
import requests
import json
import pyaudio
import numpy as np
import torch
import warnings
import time
import os
from datetime import datetime, timedelta

# Отключаем предупреждения
warnings.filterwarnings("ignore")
os.environ['GIGACHAT_VERIFY_SSL_CERTS'] = 'false'


# ========== ЗАГРУЗКА НАСТРОЕК ==========
def load_config():
    with open('../config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_scenarios():
    with open('../scenarios.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_memory():
    try:
        with open('memory.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"conversations": [], "last_cleanup": datetime.now().isoformat()}


def save_memory(memory):
    with open('memory.json', 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


# ========== КЛЮЧ GIGACHAT ==========
GIGACHAT_KEY = "MDE5ZDVkY2ItNzA4ZS03OTQ3LThjMDYtZmI0YmQxMzg1ZjM2OmVhOWY1ZGNhLWEwMDgtNDVhMy1iOGNiLTdhYjNhMzUxYzNjNg=="

# ========== 1. РАСПОЗНАВАНИЕ РЕЧИ ==========
recognizer = sr.Recognizer()
mic = None


def init_microphone():
    """Инициализируем микрофон с повторными попытками"""
    global mic
    try:
        mic = sr.Microphone()
        # Проверяем микрофон
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("✅ Микрофон инициализирован")
        return True
    except Exception as e:
        print(f"❌ Ошибка микрофона: {e}")
        print("   Проверьте подключение микрофона")
        return False


def listen():
    """Слушаем микрофон и возвращаем текст"""
    global mic

    if mic is None:
        if not init_microphone():
            return ""

    try:
        with mic as source:
            # Уменьшаем время адаптации
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            print("🎤 Слушаю...")
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                return ""
            except OSError as e:
                print(f"❌ Ошибка микрофона: {e}")
                init_microphone()  # Пробуем переинициализировать
                return ""

        try:
            text = recognizer.recognize_google(audio, language="ru-RU")
            print(f"📝 Вы сказали: {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("❌ Не расслышал")
            return ""
        except sr.RequestError:
            print("❌ Ошибка сети при распознавании")
            return ""
        except Exception as e:
            print(f"❌ Ошибка распознавания: {e}")
            return ""

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return ""


# ========== 2. ПОГОДА И ВРЕМЯ ==========
def get_weather(city):
    """Получаем погоду через бесплатный API"""
    try:
        url = f"https://wttr.in/{city}?format=%C,+%t&lang=ru"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        return "Не удалось получить погоду"
    except Exception as e:
        return f"Ошибка погоды"


def get_time():
    """Получаем текущее время"""
    now = datetime.now()
    months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
              'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    return now.strftime(f"%H:%M, %d {months[now.month - 1]} %Y")


# ========== 3. ОБРАБОТКА СЦЕНАРИЕВ ==========
def check_scenarios(text, scenarios):
    """Проверяем, есть ли сценарий на эту фразу"""
    for scenario in scenarios.get("scenarios", []):
        if scenario["trigger"].lower() in text:
            return scenario["response"]
    return None


# ========== 4. GIGACHAT ==========
def get_gigachat_response(user_text, config, memory):
    """Отправляем запрос в GigaChat"""
    try:
        character = config["character"]
        address = config["address"]

        system_prompt = f"""
Ты — {character['name']}. 
Твой характер: {character['personality']}
Твой стиль ответов: {character['response_style']}
Обращайся к пользователю на "{address['pronoun']}" и называй его {address['user_name']}.
Отвечай кратко, 2-4 предложения.
"""

        # Добавляем историю
        history = ""
        for conv in memory["conversations"][-5:]:
            history += f"Пользователь: {conv['user']}\n{character['name']}: {conv['assistant']}\n"

        # Получаем токен
        auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": "12345678-1234-1234-1234-123456789012",
            "Authorization": f"Basic {GIGACHAT_KEY}"
        }
        auth_data = {"scope": "GIGACHAT_API_PERS"}

        auth_response = requests.post(auth_url, headers=auth_headers, data=auth_data, verify=False, timeout=30)
        token = auth_response.json().get("access_token")

        if not token:
            return "Ошибка авторизации"

        # Отправляем запрос
        api_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        api_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }

        full_prompt = f"{system_prompt}\n\nИстория:\n{history}\nПользователь: {user_text}\n{character['name']}:"

        api_data = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": 0.8,
            "max_tokens": 150
        }

        response = requests.post(api_url, headers=api_headers, json=api_data, verify=False, timeout=30)
        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        # Сохраняем в память
        memory["conversations"].append({
            "timestamp": datetime.now().isoformat(),
            "user": user_text,
            "assistant": answer
        })

        # Очищаем старые диалоги
        week_ago = datetime.now() - timedelta(days=7)
        memory["conversations"] = [c for c in memory["conversations"] if
                                   datetime.fromisoformat(c["timestamp"]) > week_ago]
        save_memory(memory)

        print(f"🎭 Чарли: {answer}")
        return answer

    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        return "Извините, произошла ошибка"


# ========== 5. СИНТЕЗ РЕЧИ ==========
def speak(text):
    """Озвучиваем текст через Silero"""
    try:
        device = torch.device('cpu')
        model, _ = torch.hub.load('snakers4/silero-models', 'silero_tts',
                                  language='ru', speaker='ru_v3', trust_repo=True)
        model.to(device)

        audio = model.apply_tts(text=text, speaker='aidar', sample_rate=48000,
                                put_accent=True, put_yo=True)
        audio_np = audio.numpy()

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, output=True)
        stream.write(audio_np.astype(np.float32).tobytes())
        stream.stop_stream()
        stream.close()
        p.terminate()
        time.sleep(0.2)
    except Exception as e:
        print(f"⚠️ Ошибка озвучивания: {e}")


# ========== 6. ОСНОВНОЙ ЦИКЛ ==========
def main():
    print("🔄 Загрузка настроек...")
    config = load_config()
    scenarios = load_scenarios()
    memory = load_memory()

    print("\n" + "=" * 50)
    print(f"🎭  {config['character']['name'].upper()} - ГОЛОСОВОЙ АССИСТЕНТ")
    print("=" * 50)
    print(f"🎤 Скажите '{config['wake_word']}' чтобы активировать")
    print(f"🛑 Скажите 'стоп' или 'сброс' чтобы деактивировать")
    print("🌤️ Скажите 'погода' или 'время'")
    print("-" * 50)

    # Инициализируем микрофон
    if not init_microphone():
        print("❌ Не удалось инициализировать микрофон. Проверьте подключение.")
        return

    listening = False

    while True:
        user_text = listen()
        if not user_text:
            continue

        # Проверяем команды
        if user_text == config['wake_word'].lower():
            listening = True
            response = f"Слушаю, {config['address']['user_name']}"
            print(f"🎭 Чарли: {response}")
            speak(response)
            continue

        if any(word in user_text for word in ["стоп", "сброс", "стой"]):
            if listening:
                listening = False
                response = "Хорошо, я замолкаю"
                print(f"🎭 Чарли: {response}")
                speak(response)
            continue

        if not listening:
            continue

        # Специальные команды
        if "погода" in user_text:
            weather = get_weather(config['location']['city'])
            response = f"Погода в {config['location']['city']}: {weather}"
            print(f"🎭 Чарли: {response}")
            speak(response)
            continue

        if "время" in user_text:
            time_str = get_time()
            response = f"Сейчас {time_str}"
            print(f"🎭 Чарли: {response}")
            speak(response)
            continue

        # Проверяем сценарии
        scenario_response = check_scenarios(user_text, scenarios)
        if scenario_response:
            print(f"🎭 Чарли: {scenario_response}")
            speak(scenario_response)
            continue

        # Обычный ответ
        response = get_gigachat_response(user_text, config, memory)
        if response:
            speak(response)


if __name__ == "__main__":
    main()