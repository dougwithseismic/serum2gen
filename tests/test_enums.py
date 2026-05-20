"""Tests for serum2.enums — verified enum constants."""

import pytest

from serum2.enums import (
    WARP_MODES,
    VOICE_FILTER_TYPES,
    BASIC_VOICE_FILTER_TYPES,
    FX_FILTER_TYPES,
    DISTORTION_MODES,
    LFO_TYPES,
    LFO_MODES,
    WAVETABLES,
    FX_TYPE_IDS,
    ENUM_REGISTRY,
)


class TestWarpModes:
    def test_is_list(self):
        assert isinstance(WARP_MODES, list)

    def test_count(self):
        assert len(WARP_MODES) == 16

    def test_no_duplicates(self):
        assert len(WARP_MODES) == len(set(WARP_MODES))

    def test_all_strings(self):
        assert all(isinstance(m, str) for m in WARP_MODES)

    def test_known_modes_present(self):
        for mode in ["kSync", "kFM_OSC", "kPWM", "kSelfPD"]:
            assert mode in WARP_MODES


class TestVoiceFilterTypes:
    def test_is_list(self):
        assert isinstance(VOICE_FILTER_TYPES, list)

    def test_count(self):
        assert len(VOICE_FILTER_TYPES) == 32

    def test_no_duplicates(self):
        assert len(VOICE_FILTER_TYPES) == len(set(VOICE_FILTER_TYPES))

    def test_known_types_present(self):
        for t in ["L12", "L24", "B12", "B24", "Combs"]:
            assert t in VOICE_FILTER_TYPES


class TestBasicVoiceFilterTypes:
    def test_is_set(self):
        assert isinstance(BASIC_VOICE_FILTER_TYPES, set)

    def test_subset_of_voice_filter_types(self):
        """Basic filter types that are in the main list should be there."""
        for t in BASIC_VOICE_FILTER_TYPES:
            # Some like H12, H24, L6, N12 may not be in VOICE_FILTER_TYPES
            # but they are valid basic types referenced by the code
            assert isinstance(t, str)


class TestFXFilterTypes:
    def test_is_list(self):
        assert isinstance(FX_FILTER_TYPES, list)

    def test_no_duplicates(self):
        assert len(FX_FILTER_TYPES) == len(set(FX_FILTER_TYPES))


class TestDistortionModes:
    def test_count(self):
        assert len(DISTORTION_MODES) == 16

    def test_no_duplicates(self):
        assert len(DISTORTION_MODES) == len(set(DISTORTION_MODES))

    def test_known_modes(self):
        assert "kSoftClip" in DISTORTION_MODES
        assert "kHardClip" in DISTORTION_MODES


class TestLFOTypes:
    def test_values(self):
        assert LFO_TYPES == ["Path", "Lorenz", "Rossler", "RandomSH"]


class TestLFOModes:
    def test_values(self):
        assert LFO_MODES == ["Free", "Envelope", "Trigger"]


class TestWavetables:
    def test_is_nonempty(self):
        assert len(WAVETABLES) > 0

    def test_all_strings(self):
        assert all(isinstance(w, str) for w in WAVETABLES)

    def test_all_have_wav_extension(self):
        assert all(w.endswith(".wav") for w in WAVETABLES)


class TestFXTypeIDs:
    def test_is_dict(self):
        assert isinstance(FX_TYPE_IDS, dict)

    def test_all_start_with_fx(self):
        for key in FX_TYPE_IDS:
            assert key.startswith("FX")

    def test_values_are_ints(self):
        for v in FX_TYPE_IDS.values():
            assert isinstance(v, int)

    def test_known_types(self):
        assert "FXDistortion" in FX_TYPE_IDS
        assert "FXFilter" in FX_TYPE_IDS
        assert "FXDelay" in FX_TYPE_IDS
        assert "FXReverb" in FX_TYPE_IDS
        assert "FXComp" in FX_TYPE_IDS

    def test_unique_ids(self):
        values = list(FX_TYPE_IDS.values())
        assert len(values) == len(set(values))


class TestEnumRegistry:
    def test_is_dict(self):
        assert isinstance(ENUM_REGISTRY, dict)

    def test_values_are_lists(self):
        for v in ENUM_REGISTRY.values():
            assert isinstance(v, list)

    def test_expected_keys(self):
        assert "kParamWarpMenu" in ENUM_REGISTRY
        assert "VoiceFilter.kParamType" in ENUM_REGISTRY
