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


def get_tables_root() -> Path | None:
    """Return the Tables/ folder (sibling of Presets/)."""
    root = get_preset_root()
    if root is None:
        return None
    tables = root.parent / "Tables"
    return tables if tables.exists() else None


def find_wavetables(root: Path | None = None, category: str | None = None) -> list[str]:
    """Find .wav wavetable files, returning paths relative to the Tables/ root.

    If *category* is given, only return tables in that subfolder.
    """
    if root is None:
        root = get_tables_root()
    if root is None or not root.exists():
        return []
    if category:
        search_root = root / category
        if not search_root.exists():
            return []
    else:
        search_root = root
    return sorted(
        str(p.relative_to(root)) for p in search_root.glob("**/*.wav")
    )


def get_noises_root() -> Path | None:
    """Return the Noises/ folder inside Samples/Factory Non-Tonal/."""
    root = get_preset_root()
    if root is None:
        return None
    noises = root.parent / "Samples" / "Factory Non-Tonal" / "Noises"
    return noises if noises.exists() else None


def find_noise_samples(root: Path | None = None, category: str | None = None) -> list[str]:
    """Find noise sample files (.wav/.aif/.flac), returning paths relative to the Noises/ root."""
    if root is None:
        root = get_noises_root()
    if root is None or not root.exists():
        return []
    if category:
        search_root = root / category
        if not search_root.exists():
            return []
    else:
        search_root = root
    results = []
    for ext in ("*.wav", "*.aif", "*.flac"):
        results.extend(str(p.relative_to(root)) for p in search_root.glob(f"**/{ext}"))
    return sorted(results)


def find_arp_patterns(root: Path | None = None) -> list[str]:
    """Find .XferArp arpeggiator pattern files."""
    if root is None:
        preset_root = get_preset_root()
        if preset_root is None:
            return []
        root = preset_root.parent / "Arp Patterns"
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in root.glob("**/*.XferArp"))


def find_clips(root: Path | None = None) -> list[str]:
    """Find .XferClip clip files."""
    if root is None:
        preset_root = get_preset_root()
        if preset_root is None:
            return []
        root = preset_root.parent / "Clips"
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in root.glob("**/*.XferClip"))


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
