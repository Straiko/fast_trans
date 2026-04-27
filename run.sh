#!/bin/bash
# Olympus — запуск приложения
# Автоматически определяет режим: sudo/обычный, venv/dist

cd "$(dirname "$0")"

# Аудио окружение (для PulseAudio при sudo)
if [ -n "$SUDO_USER" ]; then
    REAL_UID=$(id -u "$SUDO_USER")
    export XDG_RUNTIME_DIR="/run/user/$REAL_UID"
    export PULSE_SERVER="unix:/run/user/$REAL_UID/pulse/native"
    export PULSE_COOKIE="/home/$SUDO_USER/.config/pulse/cookie"
fi

# Приоритет: venv → системный python
if [ -x ./venv/bin/python ]; then
    exec ./venv/bin/python main.py
elif [ -x ./.venv/bin/python ]; then
    exec ./.venv/bin/python main.py
else
    exec python3 main.py
fi
