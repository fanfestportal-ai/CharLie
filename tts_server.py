"""
Qwen3-TTS сервер для голоса Чарли
Запуск: python tts_server.py
"""

import torch
import soundfile as sf
import tempfile
import os
import time
import pygame
import warnings

warnings.filterwarnings("ignore")

# ========== НАСТРОЙКИ ГОЛОСА ==========
# Используем CustomVoice модель с голосом Dylan
MODEL_NAME = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
SPEAKER = "Dylan"  # Мужской голос, идеален для Чарли
LANGUAGE = "Russian"

# ========== ЗАГРУЗКА МОДЕЛИ ==========
print("🔄 Загрузка Qwen3-TTS модели... (первый раз 3-5 минут)")
print(f"   Модель: {MODEL_NAME}")
print(f"   Голос: {SPEAKER}")

from qwen_tts import Qwen3TTSModel

# Загружаем модель на CPU (можно на CUDA если есть видеокарта)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"📱 Используется устройство: {device}")

model = Qwen3TTSModel.from_pretrained(
    MODEL_NAME,
    device_map=device,
    dtype=torch.bfloat16 if device == "cuda" else torch.float32,
)

print(f"✅ Модель загружена! Голос: {SPEAKER}")
print("-" * 50)


# ========== ФУНКЦИЯ ОЗВУЧИВАНИЯ ==========
def speak(text):
    """Озвучивает текст голосом Dylan"""
    try:
        print(f"🎤 Озвучиваю: {text[:50]}...")

        # Генерируем речь
        wavs, sr = model.generate_custom_voice(
            text=text,
            language=LANGUAGE,
            speaker=SPEAKER,
            instruct="спокойным, добрым голосом, с небольшими паузами"
        )

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, wavs[0], sr)
            temp_file = f.name

        # Воспроизводим через pygame
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()

        # Удаляем временный файл
        os.unlink(temp_file)
        return True

    except Exception as e:
        print(f"❌ Ошибка озвучивания: {e}")
        return False


# ========== ИНТЕРАКТИВНЫЙ РЕЖИМ ==========
if __name__ == "__main__":
    print("\n🎭 ЧАРЛИ - ГОЛОС Qwen3-TTS")
    print(f"🎤 Используется голос: {SPEAKER}")
    print("💬 Введите текст, и Чарли его озвучит")
    print("🛑 Введите 'exit' или 'quit' для выхода\n")

    while True:
        text = input("📝 Текст: ")
        if text.lower() in ["exit", "quit", "выход"]:
            print("👋 До свидания!")
            break
        if text.strip():
            speak(text)