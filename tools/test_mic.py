#!/usr/bin/env python3
"""Тест микрофона"""

import speech_recognition as sr

recognizer = sr.Recognizer()

print('Доступные микрофоны:')
for index, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f'  {index}: {name}')

print('\nТест записи с микрофона по умолчанию...')

try:
    with sr.Microphone() as source:
        print('Калибровка...')
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print(f'Порог энергии: {recognizer.energy_threshold}')

        recognizer.energy_threshold = 100
        print(f'Новый порог: {recognizer.energy_threshold}')

        print('\nГоворите что-нибудь (5 секунд)...')
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

        print('Распознавание...')
        text = recognizer.recognize_google(audio, language='ru-RU')
        print(f'Распознано: {text}')

except sr.WaitTimeoutError:
    print('Тайм-аут - речь не обнаружена')
except sr.UnknownValueError:
    print('Речь не распознана')
except Exception as e:
    print(f'Ошибка: {e}')
