"""
Olympus — Demo Video Builder
Renders 8 scenes with Pillow, generates Russian narration via edge-tts,
composes final MP4 with ffmpeg (fades + audio + subtle ken-burns).

Run from project root:
    venv/bin/python demo-output/build_video.py
"""

import asyncio
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import edge_tts
import imageio_ffmpeg


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
SCENES_DIR = ROOT / "scenes"
AUDIO_DIR = ROOT / "audio"
CLIPS_DIR = ROOT / "clips"
ASSETS_DIR = ROOT / "assets"
OUTPUT = ROOT / "olympus_demo.mp4"

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
W, H = 1920, 1080

# Project brand colors (from ui_theme.py)
COLOR_BASE = (19, 17, 28)
COLOR_SURFACE = (28, 25, 41)
COLOR_GLASS = (37, 34, 54)
COLOR_GLASS_LIGHT = (46, 43, 66)
COLOR_BORDER = (61, 56, 96)
COLOR_TEXT = (240, 238, 255)
COLOR_SUBTEXT = (196, 192, 232)
COLOR_MUTED = (139, 133, 168)
COLOR_ACCENT = (139, 92, 246)
COLOR_ACCENT_HOVER = (167, 139, 250)
COLOR_ACCENT_DEEP = (124, 58, 237)
COLOR_FOCUS = (196, 181, 253)
COLOR_DANGER = (239, 68, 68)
COLOR_DANGER_DEEP = (185, 28, 28)
COLOR_SUCCESS = (74, 222, 128)
COLOR_WARNING = (251, 191, 36)


FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_PATH_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_PATH_CJK_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_PATH_ARABIC = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
FONT_PATH_ARABIC_BOLD = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        return ImageFont.truetype(FONT_PATH_MONO, size)
    return ImageFont.truetype(FONT_PATH_BOLD if bold else FONT_PATH_REG, size)


def font_cjk(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH_CJK if bold else FONT_PATH_CJK_REG, size)


def font_arabic(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH_ARABIC_BOLD if bold else FONT_PATH_ARABIC, size)


# ---------------------------------------------------------------- helpers --


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), text, font=f)
    return r - l, b - t


def text_offset(f: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    l, t, _, _ = d.textbbox((0, 0), text, font=f)
    return l, t


def centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    cy: int,
    f: ImageFont.FreeTypeFont,
    fill,
    stroke_w: int = 0,
    stroke_fill=None,
) -> tuple[int, int, int, int]:
    w, h = text_size(draw, text, f)
    ox, oy = text_offset(f, text)
    x, y = cx - w // 2 - ox, cy - h // 2 - oy
    draw.text(
        (x, y),
        text,
        font=f,
        fill=fill,
        stroke_width=stroke_w,
        stroke_fill=stroke_fill,
    )
    return x, y, x + w, y + h


def rounded_box(
    img: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill=None,
    outline=None,
    width: int = 1,
):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def glow(
    img: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    color: tuple,
    alpha: int = 150,
) -> Image.Image:
    """Add a soft glow overlay."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=color + (alpha,),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius // 2))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def gradient_bg() -> Image.Image:
    """Dark base with two soft purple glows (brand feel)."""
    base = Image.new("RGBA", (W, H), COLOR_BASE + (255,))
    base = glow(base, 380, 200, 700, COLOR_ACCENT, 70)
    base = glow(base, 1600, 900, 780, COLOR_ACCENT_DEEP, 70)
    base = glow(base, W // 2, H // 2, 500, COLOR_SURFACE, 90)
    return base


def subtle_noise(img: Image.Image) -> Image.Image:
    """Faint dot grid for depth."""
    d = ImageDraw.Draw(img)
    for y in range(0, H, 42):
        for x in range(0, W, 42):
            d.point((x, y), fill=(*COLOR_BORDER, 40))
    return img


def hotkey_key(
    img: Image.Image,
    text: str,
    cx: int,
    cy: int,
    fsize: int = 56,
    w: int = 180,
    h: int = 130,
    highlight: bool = False,
):
    """Draw a physical keyboard key with label."""
    box = (cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (box[0] + 6, box[1] + 12, box[2] + 6, box[3] + 16),
        radius=18,
        fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img)
    if highlight:
        fill = COLOR_ACCENT
        border = COLOR_ACCENT_HOVER
        text_color = (255, 255, 255)
    else:
        fill = COLOR_GLASS_LIGHT
        border = COLOR_BORDER
        text_color = COLOR_TEXT

    draw.rounded_rectangle(box, radius=18, fill=fill, outline=border, width=2)
    hi = (box[0] + 8, box[1] + 6, box[2] - 8, box[1] + 18)
    draw.rounded_rectangle(hi, radius=6, fill=(255, 255, 255, 40))

    centered_text(
        draw,
        text,
        cx,
        cy + 2,
        font(fsize, bold=True, mono=True),
        text_color,
    )


def pill(
    img: Image.Image,
    text: str,
    cx: int,
    cy: int,
    fsize: int = 28,
    padding: int = 28,
    bg=COLOR_GLASS_LIGHT,
    fg=COLOR_SUBTEXT,
    border=COLOR_BORDER,
):
    draw = ImageDraw.Draw(img)
    f = font(fsize, bold=True)
    tw, th = text_size(draw, text, f)
    w = tw + padding * 2
    h = th + int(padding * 0.9)
    box = (cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)
    draw.rounded_rectangle(box, radius=h // 2, fill=bg, outline=border, width=2)
    centered_text(draw, text, cx, cy, f, fg)
    return box


def check_icon(img: Image.Image, cx: int, cy: int, r: int = 40, color=COLOR_SUCCESS):
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
    d.line(
        [(cx - r * 0.45, cy + r * 0.05),
         (cx - r * 0.1, cy + r * 0.38),
         (cx + r * 0.5, cy - r * 0.3)],
        fill=(15, 20, 25, 255),
        width=max(4, r // 7),
    )


def cross_icon(img: Image.Image, cx: int, cy: int, r: int = 34, color=COLOR_DANGER):
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
    o = int(r * 0.42)
    d.line([(cx - o, cy - o), (cx + o, cy + o)], fill=(255, 255, 255, 255), width=max(4, r // 7))
    d.line([(cx - o, cy + o), (cx + o, cy - o)], fill=(255, 255, 255, 255), width=max(4, r // 7))


def header(img: Image.Image, eyebrow: str, title: str):
    """Top section: small eyebrow + big title."""
    d = ImageDraw.Draw(img)
    centered_text(d, eyebrow.upper(), W // 2, 120, font(22, bold=True), COLOR_ACCENT_HOVER)
    centered_text(d, title, W // 2, 210, font(76, bold=True), COLOR_TEXT)


def footer_dots(img: Image.Image, total: int, current: int):
    """Progress dots."""
    d = ImageDraw.Draw(img)
    gap = 22
    r = 5
    total_w = total * (r * 2) + (total - 1) * gap
    x0 = W // 2 - total_w // 2
    y = H - 70
    for i in range(total):
        cx = x0 + i * (r * 2 + gap) + r
        if i == current:
            d.ellipse((cx - r - 1, y - r - 1, cx + r + 1, y + r + 1), fill=COLOR_ACCENT)
        else:
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=COLOR_BORDER)


# ---------------------------------------------------------------- scenes --


def scene_1_hook(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)

    icon_path = PROJECT / "icon.png"
    if icon_path.exists():
        icon = Image.open(icon_path).convert("RGBA").resize((300, 300), Image.LANCZOS)
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse(
            (W // 2 - 300, H // 2 - 520, W // 2 + 300, H // 2 + 80),
            fill=COLOR_ACCENT + (90,),
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(90))
        img = Image.alpha_composite(img, glow_layer)
        img.alpha_composite(icon, (W // 2 - 150, H // 2 - 370))

    d = ImageDraw.Draw(img)
    centered_text(d, "OLYMPUS", W // 2, H // 2 + 40, font(160, bold=True), COLOR_TEXT)
    centered_text(
        d,
        "Мгновенный переводчик на рабочем столе",
        W // 2,
        H // 2 + 170,
        font(40),
        COLOR_SUBTEXT,
    )
    pill(img, "ТЕКСТ  •  ГОЛОС  •  AI", W // 2, H // 2 + 290, fsize=24, padding=38,
         bg=(*COLOR_GLASS, 255), fg=COLOR_ACCENT_HOVER, border=COLOR_BORDER)

    footer_dots(img, 8, idx)
    return img


def scene_2_problem(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "Проблема", "Старый способ переводить")

    steps = [
        "Выделить текст",
        "Скопировать — Ctrl+C",
        "Открыть вкладку браузера",
        "Вставить в переводчик",
        "Скопировать перевод",
        "Вернуться в приложение",
    ]
    y = 360
    for i, step in enumerate(steps):
        cy = y + i * 95
        cross_icon(img, 440, cy, r=24, color=COLOR_DANGER)
        d = ImageDraw.Draw(img)
        d.text((500, cy - 28), step, font=font(36, bold=True), fill=COLOR_MUTED)
        d.line(
            (500, cy + 4, 500 + 700, cy + 4),
            fill=(*COLOR_DANGER, 200),
            width=3,
        )

    pill(img, "6 шагов  •  ~20 секунд каждый раз", W // 2, y + len(steps) * 95 + 50,
         fsize=24, padding=34, bg=(*COLOR_DANGER, 255), fg=(255, 255, 255), border=COLOR_DANGER_DEEP)

    footer_dots(img, 8, idx)
    return img


def scene_3_magic(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "Решение", "Новый способ")

    y_key = 490
    hotkey_key(img, "Ctrl",  770, y_key, fsize=52, w=220, h=150)
    hotkey_key(img, "Shift", 1020, y_key, fsize=52, w=240, h=150)
    hotkey_key(img, "T",     1240, y_key, fsize=56, w=180, h=150, highlight=True)

    d = ImageDraw.Draw(img)
    centered_text(d, "+",  895, y_key, font(72, bold=True), COLOR_MUTED)
    centered_text(d, "+", 1130, y_key, font(72, bold=True), COLOR_MUTED)

    centered_text(
        d, "нажал один раз — текст уже переведён",
        W // 2, 690, font(32), COLOR_SUBTEXT,
    )

    f_chip = font(30, bold=True)
    chip_text = "Автозамена выделенного"
    tw, th = text_size(d, chip_text, f_chip)
    chip_w = tw + 150
    chip_h = 86
    chip_x0 = W // 2 - chip_w // 2
    chip_y0 = 820
    d.rounded_rectangle(
        (chip_x0, chip_y0, chip_x0 + chip_w, chip_y0 + chip_h),
        radius=43,
        fill=(*COLOR_SUCCESS, 55),
        outline=COLOR_SUCCESS,
        width=2,
    )
    check_icon(img, chip_x0 + 48, chip_y0 + chip_h // 2, r=26, color=COLOR_SUCCESS)
    d.text(
        (chip_x0 + 92, chip_y0 + chip_h // 2 - th // 2 - 4),
        chip_text,
        font=f_chip,
        fill=COLOR_TEXT,
    )

    footer_dots(img, 8, idx)
    return img


def scene_4_voice(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "Голосовой ввод", "Говори — перевод вставится сам")

    cx, cy = 520, 590
    for r, a in [(240, 55), (190, 90), (150, 130)]:
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COLOR_ACCENT + (a,))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(44))
        img = Image.alpha_composite(img, glow_layer)

    d = ImageDraw.Draw(img)
    d.ellipse((cx - 110, cy - 125, cx + 110, cy + 125), fill=COLOR_ACCENT)
    d.rounded_rectangle((cx - 36, cy - 80, cx + 36, cy + 30), radius=36,
                        fill=(255, 255, 255, 255))
    d.arc((cx - 66, cy + 10, cx + 66, cy + 110),
          0, 180, fill=(255, 255, 255, 255), width=10)
    d.line((cx, cy + 75, cx, cy + 110), fill=(255, 255, 255, 255), width=10)

    for i, amp in enumerate([45, 78, 60, 95, 52, 82, 42]):
        bx = cx + 250 + i * 42
        d.rounded_rectangle(
            (bx, cy - amp, bx + 20, cy + amp),
            radius=10,
            fill=COLOR_ACCENT_HOVER,
        )

    kx, ky = 1350, 500
    hotkey_key(img, "Ctrl",  kx,        ky, fsize=44, w=180, h=130)
    hotkey_key(img, "Shift", kx + 220,  ky, fsize=44, w=200, h=130)
    hotkey_key(img, "V",     kx + 420,  ky, fsize=52, w=150, h=130, highlight=True)

    d = ImageDraw.Draw(img)
    centered_text(d, "+", kx + 110, ky, font(54, bold=True), COLOR_MUTED)
    centered_text(d, "+", kx + 320, ky, font(54, bold=True), COLOR_MUTED)

    centered_text(
        d, "микрофон → распознавание → перевод → вставка",
        1560, 660, font(26), COLOR_SUBTEXT,
    )

    f_chip = font(26, bold=True)
    chip_text = "Запись останавливается после паузы"
    tw, th = text_size(d, chip_text, f_chip)
    chip_w = tw + 130
    chip_h = 74
    chip_x0 = 1560 - chip_w // 2
    chip_y0 = 810
    d.rounded_rectangle(
        (chip_x0, chip_y0, chip_x0 + chip_w, chip_y0 + chip_h),
        radius=37,
        fill=(*COLOR_SUCCESS, 55),
        outline=COLOR_SUCCESS,
        width=2,
    )
    check_icon(img, chip_x0 + 42, chip_y0 + chip_h // 2, r=22, color=COLOR_SUCCESS)
    d.text(
        (chip_x0 + 78, chip_y0 + chip_h // 2 - th // 2 - 4),
        chip_text,
        font=f_chip,
        fill=COLOR_TEXT,
    )

    footer_dots(img, 8, idx)
    return img


def scene_5_ai(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "AI-улучшение", "Ошибки — исправлены")

    def card(
        box: tuple[int, int, int, int],
        title: str,
        body: str,
        tone: str,
    ):
        d = ImageDraw.Draw(img)
        tone_color = COLOR_DANGER if tone == "before" else COLOR_SUCCESS
        d.rounded_rectangle(box, radius=24, fill=(*COLOR_GLASS, 220), outline=COLOR_BORDER, width=2)
        d.rounded_rectangle(
            (box[0], box[1], box[0] + 8, box[3]), radius=4, fill=tone_color
        )

        centered_text(
            d,
            title,
            (box[0] + box[2]) // 2,
            box[1] + 50,
            font(24, bold=True),
            tone_color,
        )

        lines = body.split("\n")
        total_h = len(lines) * 42
        y = (box[1] + box[3]) // 2 - total_h // 2 + 20
        for line in lines:
            centered_text(d, line, (box[0] + box[2]) // 2, y, font(28), COLOR_TEXT)
            y += 42

    card(
        (220, 420, 860, 820),
        "ДО — распознано",
        "«созвать в митинга\nзавтро в десять\nутро»",
        "before",
    )
    card(
        (1060, 420, 1700, 820),
        "ПОСЛЕ — AI исправил",
        "«Назначить встречу\nзавтра в 10:00\nутра»",
        "after",
    )

    d = ImageDraw.Draw(img)
    ax, ay = 960, 620

    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.ellipse((ax - 90, ay - 90, ax + 90, ay + 90), fill=COLOR_ACCENT + (130,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, glow_layer)

    d = ImageDraw.Draw(img)
    d.ellipse((ax - 64, ay - 64, ax + 64, ay + 64),
              fill=COLOR_ACCENT, outline=COLOR_ACCENT_HOVER, width=3)
    centered_text(d, "AI", ax, ay, font(48, bold=True), (255, 255, 255))

    def sparkle(sx, sy, sz, color=COLOR_WARNING):
        d.polygon(
            [(sx, sy - sz),
             (sx + sz * 0.22, sy - sz * 0.22),
             (sx + sz, sy),
             (sx + sz * 0.22, sy + sz * 0.22),
             (sx, sy + sz),
             (sx - sz * 0.22, sy + sz * 0.22),
             (sx - sz, sy),
             (sx - sz * 0.22, sy - sz * 0.22)],
            fill=color,
        )

    sparkle(ax - 110, ay - 90, 18)
    sparkle(ax + 105, ay - 120, 14)
    sparkle(ax - 120, ay + 100, 12)
    sparkle(ax + 130, ay + 85, 16)

    pill(img, "также улучшает промпты для ChatGPT и Claude", W // 2, 900,
         fsize=22, padding=28, bg=(*COLOR_ACCENT, 50), fg=COLOR_ACCENT_HOVER, border=COLOR_ACCENT)

    footer_dots(img, 8, idx)
    return img


def scene_6_languages(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "Языки", "15 языков — из коробки")

    langs = [
        ("EN", "English", None),     ("RU", "Русский", None),
        ("UK", "Українська", None),  ("DE", "Deutsch", None),
        ("FR", "Français", None),    ("ES", "Español", None),
        ("IT", "Italiano", None),    ("PT", "Português", None),
        ("PL", "Polski", None),      ("TR", "Türkçe", None),
        ("ZH", "中文", "cjk"),       ("JA", "日本語", "cjk"),
        ("KO", "한국어", "cjk"),     ("AR", "العربية", "arabic"),
        ("AUTO", "Авто", None),
    ]

    cols = 5
    cell_w, cell_h = 300, 140
    gap = 28
    total_w = cols * cell_w + (cols - 1) * gap
    x0 = W // 2 - total_w // 2
    y0 = 360

    d = ImageDraw.Draw(img)
    for i, (code, name, script) in enumerate(langs):
        r = i // cols
        c = i % cols
        x = x0 + c * (cell_w + gap)
        y = y0 + r * (cell_h + gap)
        box = (x, y, x + cell_w, y + cell_h)
        accent = code == "AUTO"
        d.rounded_rectangle(
            box,
            radius=22,
            fill=(*COLOR_ACCENT, 80) if accent else (*COLOR_GLASS, 200),
            outline=COLOR_ACCENT if accent else COLOR_BORDER,
            width=2,
        )
        centered_text(
            d, code, x + cell_w // 2, y + 48,
            font(40, bold=True),
            COLOR_ACCENT_HOVER if accent else COLOR_TEXT,
        )
        if script == "cjk":
            name_font = font_cjk(24)
        elif script == "arabic":
            name_font = font_arabic(24)
        else:
            name_font = font(22)
        centered_text(
            d, name, x + cell_w // 2, y + 100,
            name_font, COLOR_SUBTEXT,
        )

    footer_dots(img, 8, idx)
    return img


def scene_7_benefits(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)
    header(img, "Почему Olympus", "Всё, что нужно — из коробки")

    items = [
        ("Бесплатно", "Groq и HuggingFace — без оплаты"),
        ("Работает в трее", "Всегда под рукой, не мешает"),
        ("Без админки", "Портативная установка в один клик"),
        ("105 тестов", "Стабильность, проверенная кодом"),
        ("Open source", "MIT — меняй под себя"),
        ("Windows и Linux", "Один код, две платформы"),
    ]

    cols = 2
    cell_w, cell_h = 760, 150
    gap_x, gap_y = 60, 40
    total_w = cols * cell_w + gap_x
    x0 = W // 2 - total_w // 2
    y0 = 340

    for i, (title, desc) in enumerate(items):
        r = i // cols
        c = i % cols
        x = x0 + c * (cell_w + gap_x)
        y = y0 + r * (cell_h + gap_y)
        box = (x, y, x + cell_w, y + cell_h)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(box, radius=22, fill=(*COLOR_GLASS, 210), outline=COLOR_BORDER, width=2)
        check_icon(img, x + 70, y + cell_h // 2, r=30, color=COLOR_SUCCESS)
        d.text((x + 130, y + 35), title, font=font(32, bold=True), fill=COLOR_TEXT)
        d.text((x + 130, y + 85), desc, font=font(22), fill=COLOR_SUBTEXT)

    footer_dots(img, 8, idx)
    return img


def scene_8_cta(idx: int) -> Image.Image:
    img = gradient_bg()
    img = subtle_noise(img)

    icon_path = PROJECT / "icon.png"
    if icon_path.exists():
        icon = Image.open(icon_path).convert("RGBA").resize((180, 180), Image.LANCZOS)
        img.alpha_composite(icon, (W // 2 - 90, 200))

    d = ImageDraw.Draw(img)
    centered_text(d, "Скачай бесплатно", W // 2, 460, font(90, bold=True), COLOR_TEXT)
    centered_text(
        d, "1 клик — без админки — портативно",
        W // 2, 560, font(34), COLOR_SUBTEXT,
    )

    box = (W // 2 - 560, 650, W // 2 + 560, 780)
    d.rounded_rectangle(box, radius=28, fill=COLOR_ACCENT, outline=COLOR_ACCENT_HOVER, width=2)
    centered_text(
        d,
        "github.com/Straiko/fast_trans",
        W // 2,
        (box[1] + box[3]) // 2,
        font(44, bold=True, mono=True),
        (255, 255, 255),
    )

    pill(img, "MIT  •  Python 3.10+  •  PyQt6", W // 2, 860,
         fsize=24, padding=32, bg=(*COLOR_GLASS, 210), fg=COLOR_SUBTEXT, border=COLOR_BORDER)

    footer_dots(img, 8, idx)
    return img


SCENES = [
    # (render_fn, duration_sec, narration_text, voice, rate)
    (scene_1_hook,     4.0,
     "Olympus. Мгновенный переводчик прямо на твоём рабочем столе.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_2_problem,  6.0,
     "Устал копировать текст, открывать вкладку переводчика, вставлять, а потом копировать обратно?",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_3_magic,    5.5,
     "Новый способ. Выделил текст, нажал Ctrl Shift T — перевод уже на месте.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_4_voice,    6.0,
     "Нужен голос? Ctrl Shift V — говоришь, речь распознаётся, переводится и вставляется автоматически.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_5_ai,       5.5,
     "Встроенный AI исправляет ошибки распознавания и улучшает текст для нейросетей.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_6_languages, 4.5,
     "Пятнадцать языков — от английского до японского.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_7_benefits, 5.5,
     "Бесплатно, работает в трее, без прав администратора, сто пять тестов и открытый код.",
     "ru-RU-DmitryNeural", "+0%"),
    (scene_8_cta,      5.0,
     "Скачай сейчас. Гитхаб — Straiko слэш fast trans.",
     "ru-RU-DmitryNeural", "+0%"),
]


# ---------------------------------------------------------------- pipeline --


async def tts(text: str, voice: str, rate: str, out_path: Path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out_path))


def audio_duration(path: Path) -> float:
    ffprobe = FFMPEG.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        cmd = [FFMPEG, "-i", str(path), "-hide_banner"]
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = p.stderr
        for line in out.splitlines():
            if "Duration:" in line:
                ts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = ts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return float(p.stdout.strip() or "0")


def run(cmd: list[str]):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("STDERR:", p.stderr[-2000:])
        raise RuntimeError(f"Command failed: {' '.join(cmd[:6])}")


def render_clip(scene_png: Path, audio: Path, dur: float, out: Path, zoom_start: float, zoom_end: float):
    """Image + audio → mp4 clip with gentle ken-burns + fade in/out."""
    frames = max(1, int(dur * FPS))
    zp_expr = (
        f"zoompan=z='min(zoom+0.00035,1.06)':"
        f"d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}"
    )

    vf = (
        f"{zp_expr},"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d=0.4,"
        f"fade=t=out:st={max(0, dur - 0.45):.2f}:d=0.45"
    )
    af = (
        f"afade=t=in:st=0:d=0.3,"
        f"afade=t=out:st={max(0, dur - 0.4):.2f}:d=0.4,"
        f"apad=whole_dur={dur}"
    )
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", str(scene_png),
        "-i", str(audio),
        "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-t", f"{dur}",
        "-r", str(FPS),
        str(out),
    ]
    run(cmd)


def concat_clips(clips: list[Path], out: Path):
    list_file = CLIPS_DIR / "concat.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clips))
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out),
    ]
    run(cmd)


async def main():
    for d in (SCENES_DIR, AUDIO_DIR, CLIPS_DIR, ASSETS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("[1/4] Rendering scenes...")
    scene_pngs = []
    for i, (fn, _, _, _, _) in enumerate(SCENES):
        png = SCENES_DIR / f"scene_{i+1:02d}.png"
        print(f"  - {png.name}")
        img = fn(i)
        img.convert("RGB").save(png, "PNG", optimize=True)
        scene_pngs.append(png)

    print("[2/4] Generating narration (edge-tts)...")
    audios = []
    durations = []
    for i, (_, dur, text, voice, rate) in enumerate(SCENES):
        mp3 = AUDIO_DIR / f"audio_{i+1:02d}.mp3"
        print(f"  - {mp3.name}  [{voice}]")
        await tts(text, voice, rate, mp3)
        real = audio_duration(mp3)
        final = max(dur, real + 0.6)
        durations.append(final)
        audios.append(mp3)
        print(f"      narration {real:.2f}s -> clip {final:.2f}s")

    print("[3/4] Building per-scene clips...")
    clips = []
    for i, (png, audio, dur) in enumerate(zip(scene_pngs, audios, durations)):
        clip = CLIPS_DIR / f"clip_{i+1:02d}.mp4"
        print(f"  - {clip.name}  ({dur:.2f}s)")
        render_clip(png, audio, dur, clip, 1.0, 1.06)
        clips.append(clip)

    print("[4/4] Concatenating final video...")
    concat_clips(clips, OUTPUT)
    total = sum(durations)
    print(f"\nDone: {OUTPUT}")
    print(f"Total duration: {total:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
