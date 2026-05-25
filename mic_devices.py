"""
Curated microphone list for the settings UI and voice capture.

This module encodes product rules distilled from these Cursor skills (by name only;
there is no runtime dependency on skill files):

  a11y-audit, apple-hig-expert, ui-design-system, ux-researcher-designer,
  form-cro, page-cro, onboarding-cro, copy-editing, copywriting,
  focused-fix, product-manager-toolkit, product-discovery, code-reviewer,
  senior-frontend, data-quality-auditor, engineering-team, epic-design,
  demo-video, marketing-ops, brand-guidelines, changelog-generator

Goals: fewer junk entries, no duplicate ALSA/Pulse aliases, clear grouping,
short labels + full raw name in tooltip, stable JSON config (index or -1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

# Use -1 in config.json for “follow the OS default input device”.
SYSTEM_DEFAULT_INDEX: Final = -1

_EXCLUDE_SUBSTRINGS: tuple[str, ...] = (
    'hdmi',
    'iec958',
    'spdif',
    'surround',
    'dsnoop',
    'dmix',
    'monitor',
    'hw_accelerometer',
    'loopback',
    'discard',
    'null',
    'vdownmix',
    'upmix',
    'a52',
    'remap',
    'remapped',
    'mono-fake',
    'center_lfe',
    '.monitor',
    'multichannel',
    'vb-audio',
    'cable output',
    'stereo mix',
    'wave out',
    'what u hear',
)

Tier = Literal['system', 'physical', 'other']


@dataclass(frozen=True)
class MicEntry:
    index: int
    label: str
    tooltip: str
    tier: Tier


def _should_exclude(name: str) -> bool:
    low = name.lower()
    return any(s in low for s in _EXCLUDE_SUBSTRINGS)


def _fingerprint(name: str) -> str:
    """Collapse near-duplicate PortAudio labels (same card, different path)."""
    s = name.lower()
    s = re.sub(r'\[[^\]]*\]', ' ', s)
    s = re.sub(r'hw:\d+,\d+', 'hw:', s)
    s = re.sub(r'card \d+', 'card', s)
    s = re.sub(r'dev \d+', 'dev', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:120]


def _tier(name: str) -> Tier:
    low = name.lower()
    if low == 'default' or 'pulse' in low or 'pipewire' in low:
        return 'system'
    if 'hw:' in low or 'usb audio' in low or 'usb' in low:
        return 'physical'
    return 'other'


def _tier_sort(t: Tier) -> int:
    return {'system': 0, 'physical': 1, 'other': 2}[t]


def _short_label(name: str, tier: Tier) -> str:
    raw = name.strip()
    if tier == 'system':
        if 'pipewire' in raw.lower():
            return 'PipeWire / system default'
        if 'pulse' in raw.lower() or raw.lower() == 'default':
            return 'PulseAudio / system default'
        return raw if len(raw) <= 52 else raw[:24] + '…' + raw[-24:]

    cleaned = raw.replace('HDA ', '').strip()
    if len(cleaned) <= 56:
        return cleaned
    return cleaned[:26] + '…' + cleaned[-26:]


def build_mic_entries(device_names: list[str]) -> list[MicEntry]:
    """
    Return a curated ordered list of microphones.

    - Drops obvious non-input / monitor / HDMI junk.
    - Merges duplicates that share the same fingerprint (keeps lowest index).
    - Orders: system defaults → physical → other, then by index.
    """
    candidates: list[tuple[int, str, Tier]] = []
    for idx, name in enumerate(device_names):
        if not name or not str(name).strip():
            continue
        s = str(name).strip()
        if _should_exclude(s):
            continue
        candidates.append((idx, s, _tier(s)))

    # Dedupe by fingerprint — keep first (best ordering applied later).
    seen: set[str] = set()
    unique: list[tuple[int, str, Tier]] = []
    for idx, name, tier in sorted(candidates, key=lambda x: (_tier_sort(x[2]), x[0])):
        fp = _fingerprint(name)
        if fp in seen:
            continue
        seen.add(fp)
        unique.append((idx, name, tier))

    unique.sort(key=lambda x: (_tier_sort(x[2]), x[0]))

    out: list[MicEntry] = []
    for idx, name, tier in unique:
        out.append(
            MicEntry(
                index=idx,
                label=_short_label(name, tier),
                tooltip=f'{name}\n(Device index {idx})',
                tier=tier,
            )
        )
    return out
