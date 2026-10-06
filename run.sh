#!/bin/bash
# Olympus — запуск приложения
# Автоматически определяет режим: sudo/обычный, venv/dist

cd "$(dirname "$0")"

# Аудио и дисплей при sudo
if [ -n "$SUDO_USER" ]; then
    REAL_UID=$(id -u "$SUDO_USER")
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    [ -z "$REAL_HOME" ] && REAL_HOME=$(eval echo "~$SUDO_USER")
    export XDG_RUNTIME_DIR="/run/user/$REAL_UID"
    export PULSE_SERVER="unix:/run/user/$REAL_UID/pulse/native"
    export PULSE_COOKIE="$REAL_HOME/.config/pulse/cookie"

    # X11 / Wayland display access
    if [ -z "$DISPLAY" ]; then
        export DISPLAY=":0"
    fi
    if [ -z "$XAUTHORITY" ]; then
        export XAUTHORITY="$REAL_HOME/.Xauthority"
    fi
    # Grant root access to the X11 display (needs xhost installed)
    if command -v xhost &>/dev/null; then
        DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" xhost +local:root &>/dev/null || true
    fi
    # Wayland socket detection
    if [ -z "$WAYLAND_DISPLAY" ]; then
        for sock in "/run/user/$REAL_UID"/wayland-[0-9]*; do
            if [ -S "$sock" ]; then
                export WAYLAND_DISPLAY="$(basename "$sock")"
                break
            fi
        done
    fi
fi

# Приоритет: venv → системный python
if [ -x ./venv/bin/python ]; then
    exec ./venv/bin/python main.py
elif [ -x ./.venv/bin/python ]; then
    exec ./.venv/bin/python main.py
else
    exec python3 main.py
fi
