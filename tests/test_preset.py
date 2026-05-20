"""Tests for serum2.preset — high-level Preset class."""

import hashlib
import json
from pathlib import Path

import pytest

from serum2.preset import Preset, PARAM_ALIASES, HEADER_ALIASES, _resolve_alias, _coerce_value
from serum2.enums import FX_TYPE_IDS
from tests.conftest import requires_factory_presets, FACTORY_BASS_PRESET


# ── Preset.load / .save round-trip ───────────────────────────────────


class TestPresetLoadSave:
    """Tests for loading from disk and saving back."""

    @requires_factory_presets
    def test_load_returns_preset_instance(self):
        p = Preset.load(FACTORY_BASS_PRESET)
        assert isinstance(p, Preset)

    @requires_factory_presets
    def test_save_round_trip(self, tmp_path):
        """Load, save, reload produces equivalent preset."""
        original = Preset.load(FACTORY_BASS_PRESET)
        out = tmp_path / "rt.SerumPreset"
        original.save(out)
        reloaded = Preset.load(out)
        assert reloaded.name == original.name
        assert reloaded.author == original.author
        assert reloaded.header == original.header
        assert reloaded.params == original.params

    @requires_factory_presets
    def test_save_preserves_modifications(self, tmp_path):
        """Modifications persist through save/reload."""
        p = Preset.load(FACTORY_BASS_PRESET)
        p.name = "Modified Name"
        p.set("filter.freq", 0.8)
        out = tmp_path / "modified.SerumPreset"
        p.save(out)

        reloaded = Preset.load(out)
        assert reloaded.name == "Modified Name"
        assert reloaded.get("filter.freq") == pytest.approx(0.8)


# ── .get / .set with aliases ─────────────────────────────────────────


class TestGetSetAliases:
    """Tests for get/set with parameter aliases."""

    def test_get_filter_freq(self, minimal_preset):
        assert minimal_preset.get("filter.freq") == 0.5

    def test_set_filter_freq(self, minimal_preset):
        minimal_preset.set("filter.freq", 0.75)
        assert minimal_preset.get("filter.freq") == 0.75

    def test_get_filter_reso(self, minimal_preset):
        assert minimal_preset.get("filter.reso") == 20.0

    def test_get_filter_drive(self, minimal_preset):
        assert minimal_preset.get("filter.drive") == 10.0

    def test_get_filter_type(self, minimal_preset):
        assert minimal_preset.get("filter.type") == "L24"

    def test_get_osc0_warp(self, minimal_preset):
        assert minimal_preset.get("osc0.warp") == 0.5

    def test_set_osc0_warp(self, minimal_preset):
        minimal_preset.set("osc0.warp", 0.9)
        assert minimal_preset.get("osc0.warp") == 0.9

    def test_get_osc0_volume(self, minimal_preset):
        assert minimal_preset.get("osc0.volume") == 0.7

    def test_get_env0_sustain(self, minimal_preset):
        assert minimal_preset.get("env0.sustain") == 0.5

    def test_set_env0_sustain(self, minimal_preset):
        minimal_preset.set("env0.sustain", 0.8)
        assert minimal_preset.get("env0.sustain") == 0.8

    def test_get_lfo0_rate(self, minimal_preset):
        assert minimal_preset.get("lfo0.rate") == 0.25

    def test_get_macro0_value(self, minimal_preset):
        assert minimal_preset.get("macro0.value") == 50.0

    def test_get_macro0_name(self, minimal_preset):
        assert minimal_preset.get("macro0.name") == "CUTOFF"

    def test_set_macro0_name(self, minimal_preset):
        minimal_preset.set("macro0.name", "BASS")
        assert minimal_preset.get("macro0.name") == "BASS"

    def test_get_global_volume(self, minimal_preset):
        assert minimal_preset.get("global.volume") == 0.5

    def test_set_global_volume(self, minimal_preset):
        minimal_preset.set("global.volume", 0.35)
        assert minimal_preset.get("global.volume") == pytest.approx(0.35)

    def test_get_nonexistent_returns_default(self, minimal_preset):
        assert minimal_preset.get("nonexistent.path") is None
        assert minimal_preset.get("nonexistent.path", "fallback") == "fallback"

    def test_get_case_insensitive_for_aliases(self, minimal_preset):
        """Alias lookup is case-insensitive."""
        assert minimal_preset.get("Filter.Freq") == 0.5
        assert minimal_preset.get("FILTER.FREQ") == 0.5

    def test_set_string_value_gets_coerced_to_float(self, minimal_preset):
        """When set receives a string that looks like a float, it is coerced."""
        minimal_preset.set("filter.freq", "0.65")
        assert minimal_preset.get("filter.freq") == pytest.approx(0.65)

    def test_set_creates_intermediate_dicts(self, minimal_preset):
        """Setting a deep path creates intermediate dicts as needed."""
        minimal_preset.set("SomeNew.section.param", 42.0)
        assert minimal_preset.get("SomeNew.section.param") == 42.0

    def test_set_raw_path_bypasses_alias(self, minimal_preset):
        """Setting with the full raw CBOR path works directly."""
        minimal_preset.set("VoiceFilter0.plainParams.kParamFreq", 0.99)
        assert minimal_preset.get("filter.freq") == 0.99


# ── .get / .set with header fields ───────────────────────────────────


class TestGetSetHeaderFields:
    """Tests for get/set with header aliases (name, author, etc.)."""

    def test_get_name(self, minimal_preset):
        assert minimal_preset.get("name") == "Test Preset"

    def test_set_name_via_get_set(self, minimal_preset):
        minimal_preset.set("name", "New Name")
        assert minimal_preset.get("name") == "New Name"
        # Hash should also be updated
        expected_hash = hashlib.md5("New Name".encode()).hexdigest()
        assert minimal_preset.header["hash"] == expected_hash

    def test_get_author(self, minimal_preset):
        assert minimal_preset.get("author") == "TestAuthor"

    def test_set_author(self, minimal_preset):
        minimal_preset.set("author", "NewAuthor")
        assert minimal_preset.get("author") == "NewAuthor"

    def test_get_description(self, minimal_preset):
        assert minimal_preset.get("description") == "A test preset"

    def test_set_description(self, minimal_preset):
        minimal_preset.set("description", "Updated desc")
        assert minimal_preset.get("description") == "Updated desc"

    def test_set_tags_from_csv_string(self, minimal_preset):
        """Setting tags with a comma-separated string splits it into a list."""
        minimal_preset.set("tags", "Bass, Lead, Pluck")
        assert minimal_preset.header["tags"] == ["Bass", "Lead", "Pluck"]

    def test_set_tags_from_list(self, minimal_preset):
        minimal_preset.set("tags", ["Pad", "Ambient"])
        assert minimal_preset.header["tags"] == ["Pad", "Ambient"]


# ── .name setter updates hash ────────────────────────────────────────


class TestNameSetter:
    """Tests for the Preset.name property setter and hash update."""

    def test_name_setter_updates_header(self, minimal_preset):
        minimal_preset.name = "Brand New Name"
        assert minimal_preset.header["presetName"] == "Brand New Name"

    def test_name_setter_updates_hash(self, minimal_preset):
        minimal_preset.name = "Hash Test"
        expected = hashlib.md5("Hash Test".encode()).hexdigest()
        assert minimal_preset.header["hash"] == expected

    def test_name_property_reads_back(self, minimal_preset):
        minimal_preset.name = "Readable"
        assert minimal_preset.name == "Readable"


# ── .clone ───────────────────────────────────────────────────────────


class TestPresetClone:
    """Tests for Preset.clone()."""

    def test_clone_produces_equal_preset(self, minimal_preset):
        cloned = minimal_preset.clone()
        assert cloned.name == minimal_preset.name
        assert cloned.params == minimal_preset.params

    def test_clone_is_independent(self, minimal_preset):
        cloned = minimal_preset.clone()
        cloned.name = "Cloned"
        assert minimal_preset.name == "Test Preset"

    def test_clone_params_independent(self, minimal_preset):
        cloned = minimal_preset.clone()
        cloned.set("filter.freq", 0.99)
        assert minimal_preset.get("filter.freq") == 0.5


# ── Macros ───────────────────────────────────────────────────────────


class TestMacros:
    """Tests for get_macro and set_macro."""

    def test_get_macro_returns_name_and_value(self, minimal_preset):
        m = minimal_preset.get_macro(0)
        assert m["name"] == "CUTOFF"
        assert m["value"] == 50.0

    def test_get_macro_empty(self, minimal_preset):
        m = minimal_preset.get_macro(2)
        assert m["name"] == ""
        assert m["value"] == 0.0

    def test_set_macro_name(self, minimal_preset):
        minimal_preset.set_macro(2, name="WARP")
        assert minimal_preset.get_macro(2)["name"] == "WARP"

    def test_set_macro_value(self, minimal_preset):
        minimal_preset.set_macro(0, value=75.0)
        assert minimal_preset.get_macro(0)["value"] == 75.0

    def test_set_macro_name_and_value(self, minimal_preset):
        minimal_preset.set_macro(3, name="DRIVE", value=60.0)
        m = minimal_preset.get_macro(3)
        assert m["name"] == "DRIVE"
        assert m["value"] == 60.0

    def test_set_macro_on_nonexistent_creates_it(self, minimal_preset):
        # Remove Macro7 to simulate it not existing
        minimal_preset.params.pop("Macro7", None)
        minimal_preset.set_macro(7, name="NEW", value=10.0)
        m = minimal_preset.get_macro(7)
        assert m["name"] == "NEW"
        assert m["value"] == 10.0

    def test_set_macro_with_default_plainparams(self, minimal_preset):
        """set_macro handles the case where plainParams is 'default'."""
        minimal_preset.params["Macro5"] = {"name": "Test", "plainParams": "default"}
        minimal_preset.set_macro(5, value=42.0)
        assert minimal_preset.get_macro(5)["value"] == 42.0


# ── Modulation ───────────────────────────────────────────────────────


class TestModulation:
    """Tests for list_mods, add_mod, clear_mod, clear_all_mods."""

    def test_list_mods_returns_active_slots(self, minimal_preset):
        mods = minimal_preset.list_mods()
        assert len(mods) == 2

    def test_list_mods_slot_structure(self, minimal_preset):
        mods = minimal_preset.list_mods()
        m0 = mods[0]
        assert m0["slot"] == 0
        assert m0["dest_type"] == "VoiceFilter"
        assert m0["dest_param"] == "kParamFreq"
        assert m0["amount"] == 50.0
        assert m0["bipolar"] is False

    def test_list_mods_bipolar_detection(self, minimal_preset):
        mods = minimal_preset.list_mods()
        m1 = mods[1]
        assert m1["bipolar"] is True

    def test_add_mod_returns_slot_index(self, minimal_preset):
        slot = minimal_preset.add_mod("LFO1", "filter.reso", 40.0)
        assert isinstance(slot, int)
        assert slot == 2  # first two slots are occupied

    def test_add_mod_appears_in_list(self, minimal_preset):
        minimal_preset.add_mod("Macro0", "osc0.warp", 60.0, bipolar=True)
        mods = minimal_preset.list_mods()
        added = [m for m in mods if m["dest_param"] == "kParamWarp" and m["amount"] == 60.0]
        assert len(added) == 1
        assert added[0]["bipolar"] is True

    def test_clear_mod_removes_specific_slot(self, minimal_preset):
        minimal_preset.clear_mod(0)
        mods = minimal_preset.list_mods()
        slots = [m["slot"] for m in mods]
        assert 0 not in slots
        assert 1 in slots

    def test_clear_all_mods(self, minimal_preset):
        minimal_preset.clear_all_mods()
        mods = minimal_preset.list_mods()
        assert len(mods) == 0

    def test_add_mod_invalid_source_raises(self, minimal_preset):
        with pytest.raises(ValueError, match="Unknown mod source"):
            minimal_preset.add_mod("InvalidSource", "filter.freq", 10.0)

    def test_add_mod_invalid_dest_raises(self, minimal_preset):
        with pytest.raises(ValueError, match="Unknown mod dest"):
            minimal_preset.add_mod("LFO0", "invalid.dest", 10.0)

    def test_add_mod_fills_slots_sequentially(self, minimal_preset):
        """Adding mods fills the first available default slot."""
        slot_a = minimal_preset.add_mod("LFO1", "filter.freq", 10.0)
        slot_b = minimal_preset.add_mod("LFO2", "filter.reso", 20.0)
        assert slot_a == 2
        assert slot_b == 3

    def test_add_mod_raises_when_all_slots_full(self, minimal_preset):
        """When all 64 slots are active, add_mod raises RuntimeError."""
        for i in range(64):
            minimal_preset.params[f"ModSlot{i}"] = {
                "plainParams": {"kParamAmount": 1.0},
                "source": [6, 0],
                "destModuleTypeString": "VoiceFilter",
                "destModuleParamName": "kParamFreq",
                "destModuleID": 0,
            }
        with pytest.raises(RuntimeError, match="No free mod slots"):
            minimal_preset.add_mod("LFO0", "filter.freq", 10.0)


# ── LFOs ─────────────────────────────────────────────────────────────


class TestLFOs:
    """Tests for get_lfo and set_lfo."""

    def test_get_lfo_active(self, minimal_preset):
        lfo = minimal_preset.get_lfo(0)
        assert lfo["rate"] == 0.25
        assert lfo["mode"] == "Free"
        assert lfo["has_path"] is True

    def test_get_lfo_default_returns_none_rate(self, minimal_preset):
        lfo = minimal_preset.get_lfo(1)
        assert lfo["rate"] is None

    def test_set_lfo_rate(self, minimal_preset):
        minimal_preset.set_lfo(0, rate=0.75)
        assert minimal_preset.get_lfo(0)["rate"] == 0.75

    def test_set_lfo_mode(self, minimal_preset):
        minimal_preset.set_lfo(0, mode="Envelope")
        assert minimal_preset.get_lfo(0)["mode"] == "Envelope"

    def test_set_lfo_on_default_slot(self, minimal_preset):
        """Setting LFO params on a default slot creates it."""
        minimal_preset.set_lfo(5, rate=0.5, mode="Free")
        lfo = minimal_preset.get_lfo(5)
        assert lfo["rate"] == 0.5
        assert lfo["mode"] == "Free"


# ── Envelopes ────────────────────────────────────────────────────────


class TestEnvelopes:
    """Tests for get_envelope and set_envelope."""

    def test_get_envelope_active(self, minimal_preset):
        env = minimal_preset.get_envelope(0)
        assert env["attack"] == 0.01
        assert env["decay"] == 0.3
        assert env["sustain"] == 0.5
        assert env["release"] == 0.4

    def test_get_envelope_default_returns_nones(self, minimal_preset):
        env = minimal_preset.get_envelope(2)
        assert env["attack"] is None
        assert env["decay"] is None

    def test_set_envelope_adsr(self, minimal_preset):
        minimal_preset.set_envelope(0, attack=0.05, decay=0.2, sustain=0.8, release=0.6)
        env = minimal_preset.get_envelope(0)
        assert env["attack"] == 0.05
        assert env["decay"] == 0.2
        assert env["sustain"] == 0.8
        assert env["release"] == 0.6

    def test_set_envelope_partial(self, minimal_preset):
        """Setting only some ADSR values doesn't affect others."""
        original = minimal_preset.get_envelope(0)
        minimal_preset.set_envelope(0, sustain=0.9)
        updated = minimal_preset.get_envelope(0)
        assert updated["sustain"] == 0.9
        assert updated["attack"] == original["attack"]

    def test_set_envelope_on_default_slot(self, minimal_preset):
        """Setting envelope on a default slot creates the params."""
        minimal_preset.set_envelope(2, attack=0.1, decay=0.4, sustain=0.3, release=0.5)
        env = minimal_preset.get_envelope(2)
        assert env["attack"] == 0.1


# ── FX Chain ─────────────────────────────────────────────────────────


class TestFXChain:
    """Tests for fx_chain, add_fx, remove_fx."""

    def test_fx_chain_returns_list(self, minimal_preset):
        chain = minimal_preset.fx_chain()
        assert isinstance(chain, list)
        assert len(chain) == 2

    def test_fx_chain_structure(self, minimal_preset):
        chain = minimal_preset.fx_chain()
        assert chain[0]["type"] == "FXDistortion"
        assert chain[0]["index"] == 0
        assert "kParamDrive" in chain[0]["params"]
        assert chain[1]["type"] == "FXReverb"

    def test_add_fx_valid_type(self, minimal_preset):
        idx = minimal_preset.add_fx("FXDelay", {"kParamWet": 50.0})
        assert idx == 2  # added after existing 2
        chain = minimal_preset.fx_chain()
        assert len(chain) == 3
        assert chain[2]["type"] == "FXDelay"

    def test_add_fx_invalid_type_raises(self, minimal_preset):
        with pytest.raises(ValueError, match="Unknown FX type"):
            minimal_preset.add_fx("FXNonexistent")

    def test_add_fx_all_valid_types(self, minimal_preset):
        """Every key in FX_TYPE_IDS can be added without error."""
        for fx_type in FX_TYPE_IDS:
            idx = minimal_preset.add_fx(fx_type)
            assert isinstance(idx, int)

    def test_remove_fx_by_index(self, minimal_preset):
        minimal_preset.remove_fx(0)
        chain = minimal_preset.fx_chain()
        assert len(chain) == 1
        assert chain[0]["type"] == "FXReverb"

    def test_remove_fx_out_of_range_is_noop(self, minimal_preset):
        """Removing at an out-of-range index does nothing."""
        original_len = len(minimal_preset.fx_chain())
        minimal_preset.remove_fx(99)
        assert len(minimal_preset.fx_chain()) == original_len

    def test_add_fx_no_params(self, minimal_preset):
        """add_fx with no params creates entry with empty params dict."""
        idx = minimal_preset.add_fx("FXComp")
        chain = minimal_preset.fx_chain()
        assert chain[idx]["params"] == {}


# ── Oscillators ──────────────────────────────────────────────────────


class TestOscillators:
    """Tests for get_oscillator."""

    def test_get_oscillator_enabled(self, minimal_preset):
        osc = minimal_preset.get_oscillator(0)
        assert osc["enabled"] is True
        assert osc["index"] == 0
        assert osc["volume"] == 0.7
        assert osc["wavetable"] == "Analog/Basic Shapes.wav"
        assert osc["warp_mode"] == "kSync"

    def test_get_oscillator_disabled(self, minimal_preset):
        osc = minimal_preset.get_oscillator(1)
        assert osc["enabled"] is False

    def test_get_oscillator_default(self, minimal_preset):
        """Oscillators with 'default' plainParams report not enabled."""
        osc = minimal_preset.get_oscillator(2)
        assert osc["enabled"] is False

    def test_get_oscillator_all_indices(self, minimal_preset):
        """All 5 oscillator indices are accessible."""
        for i in range(5):
            osc = minimal_preset.get_oscillator(i)
            assert osc["index"] == i


# ── summary ──────────────────────────────────────────────────────────


class TestSummary:
    """Tests for summary() output shape."""

    def test_summary_has_expected_keys(self, minimal_preset):
        s = minimal_preset.summary()
        expected_keys = {
            "name", "author", "tags", "oscillators", "filter",
            "macros", "mod_count", "fx", "envelopes", "lfos",
        }
        assert set(s.keys()) == expected_keys

    def test_summary_name_matches(self, minimal_preset):
        s = minimal_preset.summary()
        assert s["name"] == "Test Preset"

    def test_summary_oscillators_are_active_only(self, minimal_preset):
        s = minimal_preset.summary()
        # Only osc0 is enabled
        assert len(s["oscillators"]) == 1
        assert s["oscillators"][0]["index"] == 0

    def test_summary_macros_only_named(self, minimal_preset):
        s = minimal_preset.summary()
        assert "macro0" in s["macros"]
        assert "macro1" in s["macros"]
        # Macro2-7 have empty names, should not appear
        assert "macro2" not in s["macros"]

    def test_summary_mod_count(self, minimal_preset):
        s = minimal_preset.summary()
        assert s["mod_count"] == 2

    def test_summary_fx_types(self, minimal_preset):
        s = minimal_preset.summary()
        assert len(s["fx"]) == 2
        assert s["fx"][0]["type"] == "FXDistortion"

    def test_summary_envelopes(self, minimal_preset):
        s = minimal_preset.summary()
        assert "env0" in s["envelopes"]
        assert s["envelopes"]["env0"]["attack"] == 0.01

    def test_summary_lfos_only_active(self, minimal_preset):
        s = minimal_preset.summary()
        assert "lfo0" in s["lfos"]
        assert "lfo1" not in s["lfos"]


# ── export_full / to_json ────────────────────────────────────────────


class TestExport:
    """Tests for export_full and to_json."""

    def test_to_json_is_valid_json(self, minimal_preset):
        result = minimal_preset.to_json()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "Test Preset"

    def test_export_full_contains_all_sections(self, minimal_preset):
        result = minimal_preset.export_full()
        parsed = json.loads(result)
        assert "header" in parsed
        assert "params" in parsed
        assert "_meta" in parsed

    def test_export_full_preserves_params(self, minimal_preset):
        result = minimal_preset.export_full()
        parsed = json.loads(result)
        assert parsed["header"]["presetName"] == "Test Preset"
        assert "VoiceFilter0" in parsed["params"]


# ── __repr__ ─────────────────────────────────────────────────────────


class TestRepr:
    def test_repr(self, minimal_preset):
        assert repr(minimal_preset) == "Preset('Test Preset')"


# ── _coerce_value helper ────────────────────────────────────────────


class TestCoerceValue:
    def test_float_string(self):
        assert _coerce_value("0.5") == 0.5

    def test_int_string(self):
        assert _coerce_value("42") == 42.0

    def test_non_numeric_string(self):
        assert _coerce_value("kSync") == "kSync"

    def test_none_returns_none(self):
        assert _coerce_value(None) is None


# ── _resolve_alias helper ───────────────────────────────────────────


class TestResolveAlias:
    def test_known_alias(self):
        assert _resolve_alias("filter.freq") == "VoiceFilter0.plainParams.kParamFreq"

    def test_unknown_path_returned_as_is(self):
        assert _resolve_alias("some.raw.path") == "some.raw.path"

    def test_case_insensitive(self):
        assert _resolve_alias("FILTER.FREQ") == "VoiceFilter0.plainParams.kParamFreq"
