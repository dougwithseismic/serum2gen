"""serum2 — CLI and Python API for Serum 2 preset manipulation."""

from .preset import Preset
from .core import parse_preset, write_preset, deep_clone
from .paths import (
    get_preset_root, get_user_folder, find_presets, resolve_preset,
    get_tables_root, find_wavetables,
    get_noises_root, find_noise_samples,
    find_arp_patterns, find_clips,
)


def __getattr__(name):
    if name in ("generate_variation", "batch_generate"):
        from . import generator
        return getattr(generator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Preset",
    "parse_preset",
    "write_preset",
    "deep_clone",
    "get_preset_root",
    "get_user_folder",
    "find_presets",
    "resolve_preset",
    "get_tables_root",
    "find_wavetables",
    "get_noises_root",
    "find_noise_samples",
    "find_arp_patterns",
    "find_clips",
    "generate_variation",
    "batch_generate",
]
