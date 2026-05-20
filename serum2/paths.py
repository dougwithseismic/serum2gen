"""Auto-detect Serum 2 preset folders on Mac and Windows."""

import platform
from pathlib import Path

_SYSTEM = platform.system()

SERUM2_PRESET_DIRS: list[Path] = []

if _SYSTEM == "Darwin":
    SERUM2_PRESET_DIRS = [
        Path("/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets"),
        Path.home() / "Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets",
    ]
elif _SYSTEM == "Windows":
    SERUM2_PRESET_DIRS = [
        Path.home() / "Documents/Xfer/Serum 2 Presets/Presets",
        Path("C:/ProgramData/Xfer Records/Serum 2 Presets/Presets"),
    ]


def get_preset_root() -> Path | None:
    for d in SERUM2_PRESET_DIRS:
        if d.exists():
            return d
    return None


def get_user_folder() -> Path | None:
    root = get_preset_root()
    if root is None:
        return None
    user = root / "User"
    user.mkdir(parents=True, exist_ok=True)
    return user


def find_presets(root: Path | None = None, pattern: str = "**/*.SerumPreset") -> list[Path]:
    if root is None:
        root = get_preset_root()
    if root is None or not root.exists():
        return []
    return sorted(root.glob(pattern))


def resolve_preset(name_or_path: str) -> Path | None:
    p = Path(name_or_path)
    if p.exists():
        return p
    if not p.suffix:
        p = p.with_suffix(".SerumPreset")
    if p.exists():
        return p
    root = get_preset_root()
    if root is None:
        return None
    matches = list(root.glob(f"**/{p.name}"))
    if matches:
        return matches[0]
    stem = p.stem.lower()
    for preset in find_presets(root):
        if stem in preset.stem.lower():
            return preset
    return None
