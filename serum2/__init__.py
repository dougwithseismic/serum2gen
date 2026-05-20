"""serum2 — CLI and Python API for Serum 2 preset manipulation."""

from .preset import Preset
from .core import parse_preset, write_preset, deep_clone
from .paths import get_preset_root, get_user_folder, find_presets, resolve_preset
from .generator import generate_variation, batch_generate

__all__ = [
    "Preset",
    "parse_preset",
    "write_preset",
    "deep_clone",
    "get_preset_root",
    "get_user_folder",
    "find_presets",
    "resolve_preset",
    "generate_variation",
    "batch_generate",
]
