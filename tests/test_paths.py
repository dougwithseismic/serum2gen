"""Tests for serum2.paths — OS-specific preset path detection."""

from pathlib import Path
from unittest.mock import patch

import pytest

from serum2.paths import (
    get_preset_root,
    get_user_folder,
    find_presets,
    resolve_preset,
    get_tables_root,
    find_wavetables,
    get_noises_root,
    find_noise_samples,
    find_arp_patterns,
    find_clips,
    SERUM2_PRESET_DIRS,
)
from tests.conftest import requires_factory_presets, FACTORY_BASS_PRESET, FACTORY_ROOT


# ── get_preset_root ──────────────────────────────────────────────────


class TestGetPresetRoot:
    """Tests for get_preset_root()."""

    @requires_factory_presets
    def test_returns_existing_path(self):
        root = get_preset_root()
        assert root is not None
        assert root.exists()
        assert root.is_dir()

    def test_returns_none_when_no_dirs_exist(self):
        with patch("serum2.paths.SERUM2_PRESET_DIRS", [Path("/nonexistent/a"), Path("/nonexistent/b")]):
            assert get_preset_root() is None


# ── get_user_folder ──────────────────────────────────────────────────


class TestGetUserFolder:
    """Tests for get_user_folder()."""

    @requires_factory_presets
    def test_returns_user_path(self):
        folder = get_user_folder()
        assert folder is not None
        assert folder.name == "User"

    def test_returns_none_when_no_root(self):
        with patch("serum2.paths.get_preset_root", return_value=None):
            assert get_user_folder() is None


# ── find_presets ─────────────────────────────────────────────────────


class TestFindPresets:
    """Tests for find_presets()."""

    @requires_factory_presets
    def test_finds_presets_in_factory(self):
        presets = find_presets(FACTORY_ROOT)
        assert len(presets) > 0
        assert all(p.suffix == ".SerumPreset" for p in presets)

    @requires_factory_presets
    def test_finds_presets_sorted(self):
        presets = find_presets(FACTORY_ROOT)
        assert presets == sorted(presets)

    def test_returns_empty_for_nonexistent_root(self):
        presets = find_presets(Path("/nonexistent"))
        assert presets == []

    def test_returns_empty_for_none_root_without_system_dirs(self):
        with patch("serum2.paths.get_preset_root", return_value=None):
            presets = find_presets(None)
            assert presets == []

    def test_custom_pattern(self, tmp_path):
        """find_presets supports custom glob patterns."""
        (tmp_path / "a.SerumPreset").touch()
        (tmp_path / "b.txt").touch()
        presets = find_presets(tmp_path, "*.SerumPreset")
        assert len(presets) == 1
        assert presets[0].name == "a.SerumPreset"

    @requires_factory_presets
    def test_category_pattern(self):
        """A category-scoped pattern only returns presets in that subfolder."""
        presets = find_presets(FACTORY_ROOT, "**/Piano/**/*.SerumPreset")
        assert len(presets) > 0
        assert all("Piano" in str(p) for p in presets)


# ── resolve_preset ───────────────────────────────────────────────────


class TestResolvePreset:
    """Tests for resolve_preset()."""

    @requires_factory_presets
    def test_resolve_by_full_path(self):
        result = resolve_preset(str(FACTORY_BASS_PRESET))
        assert result is not None
        assert result == FACTORY_BASS_PRESET

    @requires_factory_presets
    def test_resolve_by_filename(self):
        """Resolving by just the filename finds it in the factory tree."""
        result = resolve_preset("BA - Perfect Pluck.SerumPreset")
        assert result is not None
        assert result.name == "BA - Perfect Pluck.SerumPreset"

    @requires_factory_presets
    def test_resolve_adds_extension(self):
        """Resolving without .SerumPreset extension still finds it."""
        result = resolve_preset("BA - Perfect Pluck")
        assert result is not None
        assert result.name == "BA - Perfect Pluck.SerumPreset"

    @requires_factory_presets
    def test_resolve_by_fuzzy_match(self):
        """Resolving with a partial stem finds a matching preset."""
        result = resolve_preset("Perfect Pluck")
        assert result is not None
        assert "Perfect Pluck" in result.stem

    def test_resolve_returns_none_for_unknown(self):
        """Resolving a completely nonexistent name returns None."""
        with patch("serum2.paths.get_preset_root", return_value=None):
            result = resolve_preset("DefinitelyDoesNotExist12345")
            assert result is None

    def test_resolve_existing_file_directly(self, tmp_path):
        """If given a path to an existing file, returns it directly."""
        f = tmp_path / "test.SerumPreset"
        f.touch()
        result = resolve_preset(str(f))
        assert result == f


# ── get_tables_root ─────────────────────────────────────────────────


class TestGetTablesRoot:
    """Tests for get_tables_root()."""

    def test_returns_none_when_no_preset_root(self):
        with patch("serum2.paths.get_preset_root", return_value=None):
            assert get_tables_root() is None

    def test_returns_none_when_tables_dir_missing(self, tmp_path):
        """If Tables/ doesn't exist as sibling, returns None."""
        presets = tmp_path / "Presets"
        presets.mkdir()
        with patch("serum2.paths.get_preset_root", return_value=presets):
            assert get_tables_root() is None

    def test_returns_tables_path_when_exists(self, tmp_path):
        presets = tmp_path / "Presets"
        presets.mkdir()
        tables = tmp_path / "Tables"
        tables.mkdir()
        with patch("serum2.paths.get_preset_root", return_value=presets):
            result = get_tables_root()
            assert result == tables


# ── find_wavetables ─────────────────────────────────────────────────


class TestFindWavetables:
    """Tests for find_wavetables()."""

    def test_returns_empty_for_none_root(self):
        with patch("serum2.paths.get_tables_root", return_value=None):
            assert find_wavetables() == []

    def test_finds_wav_files(self, tmp_path):
        (tmp_path / "Analog").mkdir()
        (tmp_path / "Analog" / "Saw.wav").touch()
        (tmp_path / "Analog" / "Square.wav").touch()
        (tmp_path / "readme.txt").touch()
        result = find_wavetables(root=tmp_path)
        assert result == ["Analog/Saw.wav", "Analog/Square.wav"]

    def test_category_filter(self, tmp_path):
        (tmp_path / "Analog").mkdir()
        (tmp_path / "Digital").mkdir()
        (tmp_path / "Analog" / "Saw.wav").touch()
        (tmp_path / "Digital" / "FM.wav").touch()
        result = find_wavetables(root=tmp_path, category="Analog")
        assert result == ["Analog/Saw.wav"]
        assert "Digital/FM.wav" not in result

    def test_category_nonexistent_returns_empty(self, tmp_path):
        result = find_wavetables(root=tmp_path, category="Nonexistent")
        assert result == []


# ── get_noises_root ─────────────────────────────────────────────────


class TestGetNoisesRoot:
    """Tests for get_noises_root()."""

    def test_returns_none_when_no_preset_root(self):
        with patch("serum2.paths.get_preset_root", return_value=None):
            assert get_noises_root() is None

    def test_returns_none_when_noises_dir_missing(self, tmp_path):
        presets = tmp_path / "Presets"
        presets.mkdir()
        with patch("serum2.paths.get_preset_root", return_value=presets):
            assert get_noises_root() is None

    def test_returns_noises_path_when_exists(self, tmp_path):
        presets = tmp_path / "Presets"
        presets.mkdir()
        noises = tmp_path / "Samples" / "Factory Non-Tonal" / "Noises"
        noises.mkdir(parents=True)
        with patch("serum2.paths.get_preset_root", return_value=presets):
            result = get_noises_root()
            assert result == noises


# ── find_noise_samples ──────────────────────────────────────────────


class TestFindNoiseSamples:
    """Tests for find_noise_samples()."""

    def test_returns_empty_for_none_root(self):
        with patch("serum2.paths.get_noises_root", return_value=None):
            assert find_noise_samples() == []

    def test_finds_multiple_extensions(self, tmp_path):
        (tmp_path / "hum.wav").touch()
        (tmp_path / "crackle.aif").touch()
        (tmp_path / "hiss.flac").touch()
        (tmp_path / "notes.txt").touch()
        result = find_noise_samples(root=tmp_path)
        assert "hum.wav" in result
        assert "crackle.aif" in result
        assert "hiss.flac" in result
        assert "notes.txt" not in result

    def test_category_filter(self, tmp_path):
        (tmp_path / "Analog").mkdir()
        (tmp_path / "Organics").mkdir()
        (tmp_path / "Analog" / "buzz.wav").touch()
        (tmp_path / "Organics" / "hum.wav").touch()
        result = find_noise_samples(root=tmp_path, category="Analog")
        assert result == ["Analog/buzz.wav"]


# ── find_arp_patterns ───────────────────────────────────────────────


class TestFindArpPatterns:
    """Tests for find_arp_patterns()."""

    def test_returns_empty_for_nonexistent_root(self, tmp_path):
        result = find_arp_patterns(root=tmp_path / "nonexistent")
        assert result == []

    def test_finds_xferarp_files(self, tmp_path):
        (tmp_path / "pattern1.XferArp").touch()
        (tmp_path / "pattern2.XferArp").touch()
        (tmp_path / "other.txt").touch()
        result = find_arp_patterns(root=tmp_path)
        assert result == ["pattern1.XferArp", "pattern2.XferArp"]


# ── find_clips ──────────────────────────────────────────────────────


class TestFindClips:
    """Tests for find_clips()."""

    def test_returns_empty_for_nonexistent_root(self, tmp_path):
        result = find_clips(root=tmp_path / "nonexistent")
        assert result == []

    def test_finds_xferclip_files(self, tmp_path):
        (tmp_path / "clip1.XferClip").touch()
        (tmp_path / "clip2.XferClip").touch()
        (tmp_path / "other.txt").touch()
        result = find_clips(root=tmp_path)
        assert result == ["clip1.XferClip", "clip2.XferClip"]
