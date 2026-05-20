"""Tests for serum2.paths — OS-specific preset path detection."""

from pathlib import Path
from unittest.mock import patch

import pytest

from serum2.paths import (
    get_preset_root,
    get_user_folder,
    find_presets,
    resolve_preset,
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
