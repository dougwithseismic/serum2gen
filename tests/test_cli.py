"""Tests for serum2.cli — Click CLI commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from serum2.cli import cli
from serum2.preset import Preset
from serum2.enums import FX_TYPE_IDS
from tests.conftest import requires_factory_presets, FACTORY_BASS_PRESET


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def writable_preset(tmp_path):
    """Create a writable copy of the factory preset for mutating tests."""
    if not FACTORY_BASS_PRESET.exists():
        pytest.skip("Factory presets not available")
    src = Preset.load(FACTORY_BASS_PRESET)
    out = tmp_path / "writable.SerumPreset"
    src.save(out)
    return out


# ── list command ─────────────────────────────────────────────────────


class TestListCommand:

    @requires_factory_presets
    def test_list_default(self, runner):
        result = runner.invoke(cli, ["list", str(FACTORY_BASS_PRESET.parent.parent)])
        assert result.exit_code == 0
        assert "presets total" in result.output

    @requires_factory_presets
    def test_list_with_limit(self, runner):
        result = runner.invoke(cli, ["list", str(FACTORY_BASS_PRESET.parent.parent), "--limit", "2"])
        assert result.exit_code == 0

    def test_list_nonexistent_path(self, runner, tmp_path):
        result = runner.invoke(cli, ["list", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0

    def test_list_empty_dir(self, runner, tmp_path):
        result = runner.invoke(cli, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No presets found" in result.output


# ── inspect command ──────────────────────────────────────────────────


class TestInspectCommand:

    @requires_factory_presets
    def test_inspect_default(self, runner):
        result = runner.invoke(cli, ["inspect", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        assert "BA - Perfect Pluck" in result.output
        assert "Oscillators" in result.output
        assert "FX chain" in result.output

    @requires_factory_presets
    def test_inspect_json(self, runner):
        result = runner.invoke(cli, ["inspect", str(FACTORY_BASS_PRESET), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "name" in data

    @requires_factory_presets
    def test_inspect_full(self, runner):
        result = runner.invoke(cli, ["inspect", str(FACTORY_BASS_PRESET), "--full"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "header" in data
        assert "params" in data


# ── get command ──────────────────────────────────────────────────────


class TestGetCommand:

    @requires_factory_presets
    def test_get_name(self, runner):
        result = runner.invoke(cli, ["get", str(FACTORY_BASS_PRESET), "name"])
        assert result.exit_code == 0
        assert "BA - Perfect Pluck" in result.output

    @requires_factory_presets
    def test_get_author(self, runner):
        result = runner.invoke(cli, ["get", str(FACTORY_BASS_PRESET), "author"])
        assert result.exit_code == 0
        assert "NEST Acoustics" in result.output

    @requires_factory_presets
    def test_get_filter_freq_on_default_preset(self, runner):
        """This factory preset has VoiceFilter0 as 'default', so filter.freq is None."""
        result = runner.invoke(cli, ["get", str(FACTORY_BASS_PRESET), "filter.freq"])
        # The factory preset has "default" for VoiceFilter0, so this returns "not found"
        assert result.exit_code != 0
        assert "not found" in result.output

    @requires_factory_presets
    def test_get_filter_freq_after_set(self, runner, writable_preset):
        """After setting filter.freq, get retrieves it."""
        runner.invoke(cli, ["set", str(writable_preset), "filter.freq", "0.5"])
        result = runner.invoke(cli, ["get", str(writable_preset), "filter.freq"])
        assert result.exit_code == 0
        float(result.output.strip())

    @requires_factory_presets
    def test_get_nonexistent_param(self, runner):
        result = runner.invoke(cli, ["get", str(FACTORY_BASS_PRESET), "nonexistent.param.xyz"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_get_nonexistent_preset(self, runner):
        result = runner.invoke(cli, ["get", "/tmp/nonexistent_preset_12345.SerumPreset", "name"])
        assert result.exit_code != 0


# ── set command ──────────────────────────────────────────────────────


class TestSetCommand:

    @requires_factory_presets
    def test_set_and_verify(self, runner, writable_preset):
        result = runner.invoke(cli, ["set", str(writable_preset), "filter.freq", "0.8"])
        assert result.exit_code == 0
        assert "Set filter.freq" in result.output

        # Verify the change persisted
        verify = runner.invoke(cli, ["get", str(writable_preset), "filter.freq"])
        assert "0.8" in verify.output

    @requires_factory_presets
    def test_set_with_output_file(self, runner, writable_preset, tmp_path):
        out = tmp_path / "output.SerumPreset"
        result = runner.invoke(cli, ["set", str(writable_preset), "filter.freq", "0.3", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    @requires_factory_presets
    def test_set_header_field(self, runner, writable_preset):
        result = runner.invoke(cli, ["set", str(writable_preset), "author", "NewAuthor"])
        assert result.exit_code == 0
        verify = runner.invoke(cli, ["get", str(writable_preset), "author"])
        assert "NewAuthor" in verify.output


# ── clone command ────────────────────────────────────────────────────


class TestCloneCommand:

    @requires_factory_presets
    def test_clone(self, runner, tmp_path):
        out = tmp_path / "Cloned Preset.SerumPreset"
        result = runner.invoke(cli, ["clone", str(FACTORY_BASS_PRESET), "Cloned Preset", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

        # Verify name was changed
        cloned = Preset.load(out)
        assert cloned.name == "Cloned Preset"


# ── rename command ───────────────────────────────────────────────────


class TestRenameCommand:

    @requires_factory_presets
    def test_rename(self, runner, writable_preset, tmp_path):
        out = tmp_path / "renamed.SerumPreset"
        result = runner.invoke(cli, ["rename", str(writable_preset), "Renamed Bass", "-o", str(out)])
        assert result.exit_code == 0
        assert "Renamed" in result.output

        renamed = Preset.load(out)
        assert renamed.name == "Renamed Bass"


# ── mod commands ─────────────────────────────────────────────────────


class TestModCommands:

    @requires_factory_presets
    def test_mod_list(self, runner):
        result = runner.invoke(cli, ["mod", "list", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0

    @requires_factory_presets
    def test_mod_add(self, runner, writable_preset, tmp_path):
        out = tmp_path / "modded.SerumPreset"
        result = runner.invoke(cli, [
            "mod", "add", str(writable_preset),
            "LFO0", "filter.freq", "50.0",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Added mod slot" in result.output

    @requires_factory_presets
    def test_mod_add_invalid_source(self, runner, writable_preset):
        result = runner.invoke(cli, [
            "mod", "add", str(writable_preset),
            "BadSource", "filter.freq", "50.0",
        ])
        assert result.exit_code != 0

    @requires_factory_presets
    def test_mod_clear_all(self, runner, writable_preset, tmp_path):
        out = tmp_path / "cleared.SerumPreset"
        result = runner.invoke(cli, [
            "mod", "clear", str(writable_preset), "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Cleared all" in result.output

    @requires_factory_presets
    def test_mod_clear_specific_slot(self, runner, writable_preset, tmp_path):
        out = tmp_path / "cleared_slot.SerumPreset"
        result = runner.invoke(cli, [
            "mod", "clear", str(writable_preset), "--slot", "0", "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Cleared slot 0" in result.output


# ── fx commands ──────────────────────────────────────────────────────


class TestFXCommands:

    @requires_factory_presets
    def test_fx_list(self, runner):
        result = runner.invoke(cli, ["fx", "list", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0

    @requires_factory_presets
    def test_fx_add(self, runner, writable_preset, tmp_path):
        out = tmp_path / "fxadded.SerumPreset"
        result = runner.invoke(cli, [
            "fx", "add", str(writable_preset), "FXDelay",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Added FXDelay" in result.output

    @requires_factory_presets
    def test_fx_add_with_params(self, runner, writable_preset, tmp_path):
        out = tmp_path / "fxparams.SerumPreset"
        result = runner.invoke(cli, [
            "fx", "add", str(writable_preset), "FXDistortion",
            "-p", '{"kParamDrive": 60}',
            "-o", str(out),
        ])
        assert result.exit_code == 0

    @requires_factory_presets
    def test_fx_add_invalid_type(self, runner, writable_preset):
        result = runner.invoke(cli, [
            "fx", "add", str(writable_preset), "FXNonexistent",
        ])
        assert result.exit_code != 0

    @requires_factory_presets
    def test_fx_remove(self, runner, writable_preset, tmp_path):
        out = tmp_path / "fxremoved.SerumPreset"
        result = runner.invoke(cli, [
            "fx", "remove", str(writable_preset), "0",
            "-o", str(out),
        ])
        assert result.exit_code == 0


# ── macro commands ───────────────────────────────────────────────────


class TestMacroCommands:

    @requires_factory_presets
    def test_macro_list(self, runner):
        result = runner.invoke(cli, ["macro", "list", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        assert "Macro" in result.output

    @requires_factory_presets
    def test_macro_set(self, runner, writable_preset, tmp_path):
        out = tmp_path / "macroset.SerumPreset"
        result = runner.invoke(cli, [
            "macro", "set", str(writable_preset), "1",
            "--name", "BASS", "--value", "75.0",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Macro 1 updated" in result.output


# ── env commands ─────────────────────────────────────────────────────


class TestEnvCommands:

    @requires_factory_presets
    def test_env_list(self, runner):
        result = runner.invoke(cli, ["env", "list", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        assert "ENV" in result.output

    @requires_factory_presets
    def test_env_set(self, runner, writable_preset, tmp_path):
        out = tmp_path / "envset.SerumPreset"
        result = runner.invoke(cli, [
            "env", "set", str(writable_preset), "1",
            "-a", "0.05", "-d", "0.3", "-s", "0.5", "-r", "0.4",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "ENV 1 updated" in result.output


# ── lfo commands ─────────────────────────────────────────────────────


class TestLFOCommands:

    @requires_factory_presets
    def test_lfo_list(self, runner):
        result = runner.invoke(cli, ["lfo", "list", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0

    @requires_factory_presets
    def test_lfo_set(self, runner, writable_preset, tmp_path):
        out = tmp_path / "lfoset.SerumPreset"
        result = runner.invoke(cli, [
            "lfo", "set", str(writable_preset), "1",
            "--rate", "0.5", "--mode", "Free",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "LFO 1 updated" in result.output


# ── enums command ────────────────────────────────────────────────────


class TestEnumsCommand:

    def test_enums_no_category(self, runner):
        result = runner.invoke(cli, ["enums"])
        assert result.exit_code == 0
        assert "Available enum categories" in result.output
        assert "warp" in result.output
        assert "filter" in result.output

    def test_enums_warp(self, runner):
        result = runner.invoke(cli, ["enums", "warp"])
        assert result.exit_code == 0
        assert "kSync" in result.output

    def test_enums_filter(self, runner):
        result = runner.invoke(cli, ["enums", "filter"])
        assert result.exit_code == 0
        assert "L24" in result.output

    def test_enums_fx(self, runner):
        result = runner.invoke(cli, ["enums", "fx"])
        assert result.exit_code == 0
        assert "FXDistortion" in result.output

    def test_enums_sources(self, runner):
        result = runner.invoke(cli, ["enums", "sources"])
        assert result.exit_code == 0
        assert "LFO0" in result.output

    def test_enums_destinations(self, runner):
        result = runner.invoke(cli, ["enums", "destinations"])
        assert result.exit_code == 0
        assert "filter.freq" in result.output

    def test_enums_aliases(self, runner):
        result = runner.invoke(cli, ["enums", "aliases"])
        assert result.exit_code == 0
        assert "filter.freq" in result.output

    def test_enums_header(self, runner):
        result = runner.invoke(cli, ["enums", "header"])
        assert result.exit_code == 0
        assert "name" in result.output

    def test_enums_unknown_category(self, runner):
        result = runner.invoke(cli, ["enums", "nonexistent"])
        assert result.exit_code == 0
        assert "Available enum categories" in result.output


# ── generate command ─────────────────────────────────────────────────


class TestGenerateCommand:

    @requires_factory_presets
    def test_generate(self, runner, tmp_path):
        result = runner.invoke(cli, [
            "generate", str(FACTORY_BASS_PRESET),
            "-n", "2",
            "-s", "42",
            "-o", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Generated 2 presets" in result.output
        files = list(tmp_path.glob("*.SerumPreset"))
        assert len(files) == 2

    @requires_factory_presets
    def test_generate_with_prefix(self, runner, tmp_path):
        result = runner.invoke(cli, [
            "generate", str(FACTORY_BASS_PRESET),
            "-n", "1",
            "-p", "MYBASS",
            "-s", "42",
            "-o", str(tmp_path),
        ])
        assert result.exit_code == 0
        files = list(tmp_path.glob("*.SerumPreset"))
        assert any("MYBASS" in f.name for f in files)


# ── export / import round-trip ───────────────────────────────────────


class TestExportImportCommands:

    @requires_factory_presets
    def test_export_summary(self, runner):
        result = runner.invoke(cli, ["export", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "name" in data

    @requires_factory_presets
    def test_export_full_to_file(self, runner, tmp_path):
        json_out = tmp_path / "export.json"
        result = runner.invoke(cli, ["export", str(FACTORY_BASS_PRESET), "--full", "-o", str(json_out)])
        assert result.exit_code == 0
        assert json_out.exists()

        data = json.loads(json_out.read_text())
        assert "header" in data
        assert "params" in data
        assert "_meta" in data

    @requires_factory_presets
    def test_import_from_full_export(self, runner, tmp_path):
        """Full export -> import round-trip produces a valid preset."""
        json_out = tmp_path / "full.json"
        preset_out = tmp_path / "reimported.SerumPreset"

        # Export full
        runner.invoke(cli, ["export", str(FACTORY_BASS_PRESET), "--full", "-o", str(json_out)])

        # Import
        result = runner.invoke(cli, ["import", str(json_out), "-o", str(preset_out)])
        assert result.exit_code == 0
        assert preset_out.exists()

        # Verify the reimported preset is loadable
        reimported = Preset.load(preset_out)
        assert reimported.name == "BA - Perfect Pluck"

    def test_import_invalid_json(self, runner, tmp_path):
        """Importing JSON without required keys fails gracefully."""
        json_file = tmp_path / "bad.json"
        json_file.write_text('{"foo": "bar"}')
        result = runner.invoke(cli, ["import", str(json_file), "-o", str(tmp_path / "out.SerumPreset")])
        assert result.exit_code != 0
        assert "must contain" in result.output


# ── diff command ─────────────────────────────────────────────────────


class TestDiffCommand:

    @requires_factory_presets
    def test_diff_identical(self, runner):
        """Diffing a preset with itself shows minimal output."""
        result = runner.invoke(cli, ["diff", str(FACTORY_BASS_PRESET), str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        assert "A:" in result.output
        assert "B:" in result.output

    @requires_factory_presets
    def test_diff_modified(self, runner, writable_preset, tmp_path):
        """Diffing original vs modified shows differences."""
        modified = tmp_path / "modified.SerumPreset"
        p = Preset.load(writable_preset)
        p.name = "Modified Version"
        p.save(modified)

        result = runner.invoke(cli, ["diff", str(writable_preset), str(modified)])
        assert result.exit_code == 0


# ── search command ───────────────────────────────────────────────────


class TestSearchCommand:

    @requires_factory_presets
    def test_search_by_name(self, runner):
        result = runner.invoke(cli, ["search", "Piano", "--path", str(FACTORY_BASS_PRESET.parent.parent)])
        assert result.exit_code == 0

    @requires_factory_presets
    def test_search_no_results(self, runner):
        result = runner.invoke(cli, [
            "search", "ZZZZNONEXISTENT12345",
            "--path", str(FACTORY_BASS_PRESET.parent.parent),
        ])
        assert result.exit_code == 0
        assert "No matches" in result.output


# ── version ──────────────────────────────────────────────────────────


# ── wt commands ─────────────────────────────────────────────────────


class TestWtCommands:

    def test_wt_list_no_serum(self, runner):
        """wt list fails gracefully when no Serum 2 installed."""
        from unittest.mock import patch
        with patch("serum2.cli.find_wavetables", return_value=[]):
            result = runner.invoke(cli, ["wt", "list"])
            assert result.exit_code != 0
            assert "No wavetables found" in result.output

    def test_wt_list_with_data(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_wavetables", return_value=["Analog/Saw.wav", "Digital/FM.wav"]):
            result = runner.invoke(cli, ["wt", "list"])
            assert result.exit_code == 0
            assert "Analog/Saw.wav" in result.output
            assert "2 wavetables" in result.output

    def test_wt_list_with_category(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_wavetables", return_value=["Analog/Saw.wav"]):
            result = runner.invoke(cli, ["wt", "list", "--category", "Analog"])
            assert result.exit_code == 0
            assert "Analog/Saw.wav" in result.output

    @requires_factory_presets
    def test_wt_get(self, runner):
        result = runner.invoke(cli, ["wt", "get", str(FACTORY_BASS_PRESET), "1"])
        assert result.exit_code == 0
        assert "OSC 1" in result.output

    @requires_factory_presets
    def test_wt_set(self, runner, writable_preset, tmp_path):
        out = tmp_path / "wt_set.SerumPreset"
        result = runner.invoke(cli, [
            "wt", "set", str(writable_preset), "1", "Digital/Reese.wav",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "wavetable set to" in result.output
        p = Preset.load(out)
        assert p.get_wavetable(0) == "Digital/Reese.wav"


# ── noise commands ──────────────────────────────────────────────────


class TestNoiseCommands:

    def test_noise_list_no_serum(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_noise_samples", return_value=[]):
            result = runner.invoke(cli, ["noise", "list"])
            assert result.exit_code != 0
            assert "No noise samples found" in result.output

    def test_noise_list_with_data(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_noise_samples", return_value=["Analog/buzz.wav", "Organics/hum.wav"]):
            result = runner.invoke(cli, ["noise", "list"])
            assert result.exit_code == 0
            assert "Analog/buzz.wav" in result.output
            assert "2 noise samples" in result.output

    def test_noise_list_with_category(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_noise_samples", return_value=["Analog/buzz.wav"]):
            result = runner.invoke(cli, ["noise", "list", "--category", "Analog"])
            assert result.exit_code == 0

    @requires_factory_presets
    def test_noise_get(self, runner):
        result = runner.invoke(cli, ["noise", "get", str(FACTORY_BASS_PRESET), "1"])
        assert result.exit_code == 0
        assert "OSC 1" in result.output

    @requires_factory_presets
    def test_noise_set(self, runner, writable_preset, tmp_path):
        out = tmp_path / "noise_set.SerumPreset"
        result = runner.invoke(cli, [
            "noise", "set", str(writable_preset), "1", "Organics/AC hum1.wav",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "noise sample set to" in result.output
        p = Preset.load(out)
        assert p.get_noise(0) == "Organics/AC hum1.wav"


# ── arp commands ────────────────────────────────────────────────────


class TestArpCommands:

    @requires_factory_presets
    def test_arp_get(self, runner):
        result = runner.invoke(cli, ["arp", "get", str(FACTORY_BASS_PRESET)])
        assert result.exit_code == 0
        assert "Enabled" in result.output

    @requires_factory_presets
    def test_arp_set_enable(self, runner, writable_preset, tmp_path):
        out = tmp_path / "arp_enable.SerumPreset"
        result = runner.invoke(cli, [
            "arp", "set", str(writable_preset), "--enable", "--clip", "5",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Arp updated" in result.output
        p = Preset.load(out)
        a = p.get_arp()
        assert a["enabled"] is True
        assert a["clip_id"] == 5.0

    @requires_factory_presets
    def test_arp_set_disable(self, runner, writable_preset, tmp_path):
        out = tmp_path / "arp_disable.SerumPreset"
        result = runner.invoke(cli, [
            "arp", "set", str(writable_preset), "--disable",
            "-o", str(out),
        ])
        assert result.exit_code == 0

    def test_arp_patterns_no_serum(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_arp_patterns", return_value=[]):
            result = runner.invoke(cli, ["arp", "patterns"])
            assert result.exit_code != 0
            assert "No arp patterns found" in result.output

    def test_arp_patterns_with_data(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_arp_patterns", return_value=["pattern1.XferArp"]):
            result = runner.invoke(cli, ["arp", "patterns"])
            assert result.exit_code == 0
            assert "pattern1.XferArp" in result.output

    def test_arp_clips_no_serum(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_clips", return_value=[]):
            result = runner.invoke(cli, ["arp", "clips"])
            assert result.exit_code != 0
            assert "No clips found" in result.output

    def test_arp_clips_with_data(self, runner):
        from unittest.mock import patch
        with patch("serum2.cli.find_clips", return_value=["clip1.XferClip"]):
            result = runner.invoke(cli, ["arp", "clips"])
            assert result.exit_code == 0
            assert "clip1.XferClip" in result.output


# ── version ──────────────────────────────────────────────────────────


class TestVersion:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
