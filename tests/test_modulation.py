"""Tests for serum2.modulation — mod matrix helpers."""

import pytest

from serum2.modulation import (
    resolve_source,
    resolve_destination,
    get_mod_destinations_for_preset,
    build_mod_slot,
    SOURCE_NAMES,
    DEST_SHORTNAMES,
    SAFE_MOD_DESTINATIONS,
    FX_MOD_TARGETS,
    SRC_ENV_BASE,
    SRC_LFO_BASE,
    SRC_VELOCITY,
    SRC_NOTE,
    SRC_MACRO_BASE,
)


# ── resolve_source ───────────────────────────────────────────────────


class TestResolveSource:
    """Tests for mod source resolution."""

    def test_exact_name_env0(self):
        result = resolve_source("Env0")
        assert result == [SRC_ENV_BASE, 0]

    def test_exact_name_lfo0(self):
        result = resolve_source("LFO0")
        assert result == [SRC_LFO_BASE, 0]

    def test_exact_name_velocity(self):
        result = resolve_source("Velocity")
        assert result == [SRC_VELOCITY, 0]

    def test_exact_name_note(self):
        result = resolve_source("Note")
        assert result == [SRC_NOTE, 0]

    def test_exact_name_macro0(self):
        result = resolve_source("Macro0")
        assert result == [SRC_MACRO_BASE, 0]

    def test_alias_env1(self):
        """ENV1 is an alias for Env0 (UI numbering)."""
        result = resolve_source("ENV1")
        assert result == [SRC_ENV_BASE, 0]

    def test_case_insensitive(self):
        result = resolve_source("lfo0")
        assert result == [SRC_LFO_BASE, 0]

    def test_case_insensitive_mixed(self):
        result = resolve_source("Lfo5")
        assert result == [SRC_LFO_BASE + 5, 0]

    def test_case_insensitive_velocity(self):
        result = resolve_source("velocity")
        assert result == [SRC_VELOCITY, 0]

    def test_whitespace_stripped(self):
        result = resolve_source("  LFO0  ")
        assert result == [SRC_LFO_BASE, 0]

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unknown mod source"):
            resolve_source("InvalidSource")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Unknown mod source"):
            resolve_source("")

    def test_all_source_names_resolve(self):
        """Every entry in SOURCE_NAMES resolves without error."""
        for name in SOURCE_NAMES:
            result = resolve_source(name)
            assert isinstance(result, list)
            assert len(result) == 2

    def test_all_env_indices(self):
        for i in range(4):
            result = resolve_source(f"Env{i}")
            assert result == [SRC_ENV_BASE + i, 0]

    def test_all_lfo_indices(self):
        for i in range(10):
            result = resolve_source(f"LFO{i}")
            assert result == [SRC_LFO_BASE + i, 0]

    def test_all_macro_indices(self):
        for i in range(8):
            result = resolve_source(f"Macro{i}")
            assert result == [SRC_MACRO_BASE + i, 0]


# ── resolve_destination ──────────────────────────────────────────────


class TestResolveDestination:
    """Tests for mod destination resolution."""

    def test_exact_name_filter_freq(self):
        result = resolve_destination("filter.freq")
        assert result["t"] == "VoiceFilter"
        assert result["p"] == "kParamFreq"
        assert result["pid"] == 3
        assert result["mid"] == 0

    def test_exact_name_osc0_warp(self):
        result = resolve_destination("osc0.warp")
        assert result["t"] == "WTOsc"
        assert result["p"] == "kParamWarp"
        assert result["mid"] == 0

    def test_exact_name_osc1_warp(self):
        result = resolve_destination("osc1.warp")
        assert result["mid"] == 1

    def test_case_insensitive(self):
        result = resolve_destination("FILTER.FREQ")
        assert result["t"] == "VoiceFilter"

    def test_case_insensitive_mixed(self):
        result = resolve_destination("Filter.Reso")
        assert result["p"] == "kParamReso"

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unknown mod dest"):
            resolve_destination("invalid.destination")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Unknown mod dest"):
            resolve_destination("")

    def test_returns_copy_not_reference(self):
        """resolve_destination returns a copy, not the original dict."""
        a = resolve_destination("filter.freq")
        b = resolve_destination("filter.freq")
        a["pid"] = 999
        assert b["pid"] == 3

    def test_all_shortnames_resolve(self):
        """Every entry in DEST_SHORTNAMES resolves without error."""
        for name in DEST_SHORTNAMES:
            result = resolve_destination(name)
            assert isinstance(result, dict)
            assert "t" in result
            assert "p" in result
            assert "pid" in result
            assert "mid" in result


# ── get_mod_destinations_for_preset ──────────────────────────────────


class TestGetModDestinations:
    """Tests for building the destination list from a preset's FX chain."""

    def test_without_fx_returns_safe_destinations(self):
        """With no FX rack, only the safe base destinations are returned."""
        params = {}
        dests = get_mod_destinations_for_preset(params)
        assert len(dests) == len(SAFE_MOD_DESTINATIONS)

    def test_with_empty_fx_rack(self):
        params = {"FXRack0": {"FX": []}}
        dests = get_mod_destinations_for_preset(params)
        assert len(dests) == len(SAFE_MOD_DESTINATIONS)

    def test_with_distortion_fx(self):
        """Adding FXDistortion to the rack adds its mod targets."""
        params = {
            "FXRack0": {
                "FX": [
                    {"FXDistortion": {"plainParams": {}}, "type": 0},
                ]
            }
        }
        dests = get_mod_destinations_for_preset(params)
        expected_extra = len(FX_MOD_TARGETS["FXDistortion"])
        assert len(dests) == len(SAFE_MOD_DESTINATIONS) + expected_extra

    def test_with_multiple_fx(self):
        """Multiple FX modules each contribute their targets."""
        params = {
            "FXRack0": {
                "FX": [
                    {"FXDistortion": {"plainParams": {}}, "type": 0},
                    {"FXReverb": {"plainParams": {}}, "type": 3},
                ]
            }
        }
        dests = get_mod_destinations_for_preset(params)
        expected_extra = (
            len(FX_MOD_TARGETS["FXDistortion"])
            + len(FX_MOD_TARGETS["FXReverb"])
        )
        assert len(dests) == len(SAFE_MOD_DESTINATIONS) + expected_extra

    def test_fx_destinations_have_correct_mid(self):
        """FX mod targets get the correct module ID (fx_idx)."""
        params = {
            "FXRack0": {
                "FX": [
                    {"FXFilter": {"plainParams": {}}, "type": 1},
                    {"FXDelay": {"plainParams": {}}, "type": 2},
                ]
            }
        }
        dests = get_mod_destinations_for_preset(params)
        fx_dests = [d for d in dests if d not in SAFE_MOD_DESTINATIONS]

        filter_dests = [d for d in fx_dests if d["t"] == "FXFilter"]
        delay_dests = [d for d in fx_dests if d["t"] == "FXDelay"]

        for d in filter_dests:
            assert d["mid"] == 0  # first FX in chain
        for d in delay_dests:
            assert d["mid"] == 1  # second FX in chain

    def test_unknown_fx_type_ignored(self):
        """FX types not in FX_MOD_TARGETS are silently ignored."""
        params = {
            "FXRack0": {
                "FX": [
                    {"FXUnknownThing": {"plainParams": {}}, "type": 99},
                ]
            }
        }
        dests = get_mod_destinations_for_preset(params)
        assert len(dests) == len(SAFE_MOD_DESTINATIONS)

    def test_non_fx_keys_in_fx_entry_ignored(self):
        """Keys like 'type' and 'kUIParamMixOrGain' are not treated as FX."""
        params = {
            "FXRack0": {
                "FX": [
                    {
                        "FXDistortion": {"plainParams": {}},
                        "kUIParamMixOrGain": 0.0,
                        "type": 0,
                    },
                ]
            }
        }
        dests = get_mod_destinations_for_preset(params)
        # Should only add FXDistortion targets, not "type" or "kUI..."
        expected_extra = len(FX_MOD_TARGETS["FXDistortion"])
        assert len(dests) == len(SAFE_MOD_DESTINATIONS) + expected_extra


# ── build_mod_slot ───────────────────────────────────────────────────


class TestBuildModSlot:
    """Tests for the mod slot builder."""

    def test_basic_structure(self):
        source = [6, 0]
        dest = {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0}
        slot = build_mod_slot(source, dest, 50.0)

        assert slot["source"] == [6, 0]
        assert slot["destModuleTypeString"] == "VoiceFilter"
        assert slot["destModuleParamName"] == "kParamFreq"
        assert slot["destModuleParamID"] == 3
        assert slot["destModuleID"] == 0
        assert slot["plainParams"]["kParamAmount"] == 50.0

    def test_not_bipolar_by_default(self):
        source = [6, 0]
        dest = {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0}
        slot = build_mod_slot(source, dest, 50.0)
        assert "kParamBipolar" not in slot["plainParams"]

    def test_bipolar_flag(self):
        source = [6, 0]
        dest = {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0}
        slot = build_mod_slot(source, dest, 50.0, bipolar=True)
        assert slot["plainParams"]["kParamBipolar"] == 1.0

    def test_negative_amount(self):
        source = [1, 0]
        dest = {"t": "WTOsc", "p": "kParamWarp", "pid": 0, "mid": 0}
        slot = build_mod_slot(source, dest, -30.0)
        assert slot["plainParams"]["kParamAmount"] == -30.0
