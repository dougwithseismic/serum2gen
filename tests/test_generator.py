"""Tests for serum2.generator — variation generator."""

import random
from pathlib import Path

import pytest

from serum2.preset import Preset
from serum2.generator import generate_variation, batch_generate, MACRO_NAMES
from serum2.enums import FX_TYPE_IDS
from tests.conftest import requires_factory_presets, FACTORY_BASS_PRESET


# ── generate_variation ───────────────────────────────────────────────


class TestGenerateVariation:
    """Tests for the single-preset variation generator."""

    @requires_factory_presets
    def test_returns_preset_instance(self):
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)
        assert isinstance(result, Preset)

    @requires_factory_presets
    def test_variation_has_name(self):
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, name_prefix="TEST", variation_id=5, seed=42)
        assert result.name == "TEST - V005"

    @requires_factory_presets
    def test_variation_has_description(self):
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, variation_id=3, seed=42)
        assert result.description == "Generated variation #3"

    @requires_factory_presets
    def test_deterministic_with_seed(self):
        """Two calls with the same seed produce identical results."""
        template = Preset.load(FACTORY_BASS_PRESET)
        a = generate_variation(template, seed=123, variation_id=0)
        b = generate_variation(template, seed=123, variation_id=0)

        assert a.name == b.name
        assert a.get("filter.freq") == b.get("filter.freq")
        assert a.fx_chain() == b.fx_chain()
        assert a.list_mods() == b.list_mods()

    @requires_factory_presets
    def test_different_seeds_produce_different_results(self):
        """Two calls with different seeds produce different presets."""
        template = Preset.load(FACTORY_BASS_PRESET)
        a = generate_variation(template, seed=1)
        b = generate_variation(template, seed=9999)
        # At least names or mod lists should differ
        assert a.name != b.name or a.list_mods() != b.list_mods()

    @requires_factory_presets
    def test_fixed_macro_layout(self):
        """Macros 0, 1, 2 are always ENV 1, CUTOFF, LFO SPEED."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)

        m0 = result.get_macro(0)
        m1 = result.get_macro(1)
        m2 = result.get_macro(2)

        assert m0["name"] == "ENV 1"
        assert m1["name"] == "CUTOFF"
        assert m2["name"] == "LFO SPEED"

    @requires_factory_presets
    def test_fixed_macro_values(self):
        """Fixed macros all have value 50.0."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)

        for i in range(3):
            assert result.get_macro(i)["value"] == 50.0

    @requires_factory_presets
    def test_remaining_macros_have_names(self):
        """Macros 3-7 get names from the MACRO_NAMES pool."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)

        for i in range(3, 8):
            m = result.get_macro(i)
            assert m["name"] != ""
            assert m["name"] in MACRO_NAMES

    @requires_factory_presets
    def test_width_fx_always_present(self):
        """FXUtils (width/compression) is always in the output FX chain."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)
        chain = result.fx_chain()
        fx_types = [f["type"] for f in chain]
        assert "FXUtils" in fx_types

    @requires_factory_presets
    def test_compressor_always_present(self):
        """FXComp is always in the output FX chain."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)
        chain = result.fx_chain()
        fx_types = [f["type"] for f in chain]
        assert "FXComp" in fx_types

    @requires_factory_presets
    def test_has_modulation_slots(self):
        """Generated presets have active modulation."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)
        mods = result.list_mods()
        assert len(mods) >= 5  # at least the fixed slots

    @requires_factory_presets
    def test_has_active_lfos(self):
        """Generated presets have active LFOs."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, seed=42)
        active_lfos = sum(1 for i in range(10) if result.get_lfo(i)["rate"] is not None)
        assert active_lfos >= 2

    @requires_factory_presets
    def test_clone_does_not_mutate_template(self):
        """The template preset is not modified by generate_variation."""
        template = Preset.load(FACTORY_BASS_PRESET)
        original_name = template.name
        original_mods = template.list_mods()

        _ = generate_variation(template, seed=42)

        assert template.name == original_name
        assert template.list_mods() == original_mods

    @requires_factory_presets
    def test_intensity_0_still_produces_valid_preset(self):
        """Even with intensity=0, the output is a valid Preset."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, intensity=0.0, seed=42)
        assert isinstance(result, Preset)
        assert result.name is not None

    @requires_factory_presets
    def test_intensity_1_still_produces_valid_preset(self):
        """Even with intensity=1, the output is a valid Preset."""
        template = Preset.load(FACTORY_BASS_PRESET)
        result = generate_variation(template, intensity=1.0, seed=42)
        assert isinstance(result, Preset)
        assert result.name is not None


# ── batch_generate ───────────────────────────────────────────────────


class TestBatchGenerate:
    """Tests for the batch generation function."""

    @requires_factory_presets
    def test_generates_correct_count(self, tmp_path):
        paths = batch_generate(FACTORY_BASS_PRESET, tmp_path, count=3, base_seed=42)
        assert len(paths) == 3

    @requires_factory_presets
    def test_all_files_exist(self, tmp_path):
        paths = batch_generate(FACTORY_BASS_PRESET, tmp_path, count=3, base_seed=42)
        for p in paths:
            assert p.exists()
            assert p.suffix == ".SerumPreset"

    @requires_factory_presets
    def test_files_are_loadable(self, tmp_path):
        """All generated files can be loaded back as valid presets."""
        paths = batch_generate(FACTORY_BASS_PRESET, tmp_path, count=3, base_seed=42)
        for p in paths:
            preset = Preset.load(p)
            assert isinstance(preset, Preset)

    @requires_factory_presets
    def test_naming_convention(self, tmp_path):
        """Generated files follow the NAME - VNNN.SerumPreset pattern."""
        paths = batch_generate(FACTORY_BASS_PRESET, tmp_path, count=3, name_prefix="BASS", base_seed=42)
        assert paths[0].name == "BASS - V000.SerumPreset"
        assert paths[1].name == "BASS - V001.SerumPreset"
        assert paths[2].name == "BASS - V002.SerumPreset"

    @requires_factory_presets
    def test_creates_output_directory(self, tmp_path):
        out_dir = tmp_path / "new_dir" / "subdir"
        paths = batch_generate(FACTORY_BASS_PRESET, out_dir, count=1, base_seed=42)
        assert out_dir.exists()
        assert len(paths) == 1

    @requires_factory_presets
    def test_deterministic_with_base_seed(self, tmp_path):
        """Batch with same seed produces same files."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        paths_a = batch_generate(FACTORY_BASS_PRESET, dir_a, count=2, base_seed=100)
        paths_b = batch_generate(FACTORY_BASS_PRESET, dir_b, count=2, base_seed=100)

        for pa, pb in zip(paths_a, paths_b):
            a = Preset.load(pa)
            b = Preset.load(pb)
            assert a.name == b.name

    @requires_factory_presets
    def test_zero_count(self, tmp_path):
        """count=0 produces no files."""
        paths = batch_generate(FACTORY_BASS_PRESET, tmp_path, count=0)
        assert len(paths) == 0
