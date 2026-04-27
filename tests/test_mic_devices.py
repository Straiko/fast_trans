"""Unit tests for microphone curation (settings list + voice -1)."""

from mic_devices import SYSTEM_DEFAULT_INDEX, build_mic_entries


def test_system_default_sentinel():
    assert SYSTEM_DEFAULT_INDEX == -1


def test_excludes_hdmi_and_monitor():
    names = [
        'pulse',
        'HDMI 0 Output',
        'Built-in Analog Stereo',
        'alsa_output.pci-0000_00_1f.3.hdmi-stereo.monitor',
    ]
    entries = build_mic_entries(names)
    labels = [e.label for e in entries]
    assert not any('hdmi' in e.tooltip.lower() for e in entries)
    assert not any('monitor' in e.tooltip.lower() for e in entries)
    assert any('pulse' in e.tooltip.lower() or 'Pulse' in e.label for e in entries)


def test_dedupe_fingerprint_keeps_lower_index():
    names = [
        'HDA Intel PCH: ALC892 Analog (hw:0,0)',
        'HDA Intel PCH: ALC892 Analog (hw:0,0)',
    ]
    entries = build_mic_entries(names)
    assert len(entries) == 1
    assert entries[0].index == 0
    assert entries[0].tier == 'physical'


def test_order_system_before_physical():
    names = [
        'HDA Mic (hw:1,0)',
        'pipewire',
    ]
    entries = build_mic_entries(names)
    tiers = [e.tier for e in entries]
    assert tiers[0] == 'system'
    assert tiers[1] == 'physical'
