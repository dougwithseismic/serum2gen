"""Tests for serum2.core — binary parser and writer."""

import struct
from pathlib import Path

import pytest

from serum2.core import parse_preset, write_preset, deep_clone
from tests.conftest import requires_factory_presets, FACTORY_BASS_PRESET


# ── parse_preset ─────────────────────────────────────────────────────


class TestParsePreset:
    """Tests for the low-level binary parser."""

    @requires_factory_presets
    def test_loads_factory_preset_successfully(self):
        """parse_preset returns a dict with header, params, and _meta."""
        result = parse_preset(FACTORY_BASS_PRESET)
        assert isinstance(result, dict)
        assert "header" in result
        assert "params" in result
        assert "_meta" in result

    @requires_factory_presets
    def test_header_contains_expected_keys(self):
        """The header section has the expected Serum 2 metadata fields."""
        result = parse_preset(FACTORY_BASS_PRESET)
        header = result["header"]
        assert "presetName" in header
        assert "presetAuthor" in header
        assert header["presetName"] == "BA - Perfect Pluck"

    @requires_factory_presets
    def test_params_is_nonempty_dict(self):
        """The params section is a non-empty dict of synth parameters."""
        result = parse_preset(FACTORY_BASS_PRESET)
        assert isinstance(result["params"], dict)
        assert len(result["params"]) > 0

    @requires_factory_presets
    def test_meta_has_expected_fields(self):
        """The _meta section has decompressed_size and section_flags."""
        result = parse_preset(FACTORY_BASS_PRESET)
        meta = result["_meta"]
        assert "decompressed_size" in meta
        assert "section_flags" in meta
        assert isinstance(meta["decompressed_size"], int)
        assert isinstance(meta["section_flags"], int)

    def test_rejects_non_serum_file(self, tmp_path):
        """parse_preset raises ValueError on a file without XferJson magic."""
        fake = tmp_path / "fake.SerumPreset"
        fake.write_bytes(b"NotXfer" + b"\x00" * 100)
        with pytest.raises(ValueError, match="Not a Serum 2 preset"):
            parse_preset(fake)

    def test_rejects_empty_file(self, tmp_path):
        """parse_preset raises ValueError on an empty file."""
        empty = tmp_path / "empty.SerumPreset"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="Not a Serum 2 preset"):
            parse_preset(empty)

    def test_rejects_file_with_magic_but_no_zstd(self, tmp_path):
        """parse_preset raises ValueError when magic is present but no
        Zstandard payload exists."""
        # Build a file with valid magic and a valid JSON block, but no zstd data
        header_json = b'{"presetName":"test"}'
        data = bytearray()
        data.extend(b"XferJson")
        data.extend(b"\x00")
        data.extend(struct.pack("<H", len(header_json)))
        data.extend(b"\x00" * 6)
        data.extend(header_json)
        data.extend(struct.pack("<I", 100))  # decompressed size
        data.extend(struct.pack("<I", 2))    # flags
        data.extend(b"\x00" * 50)            # garbage, no zstd magic

        bad_file = tmp_path / "no_zstd.SerumPreset"
        bad_file.write_bytes(bytes(data))
        with pytest.raises(ValueError, match="No Zstandard payload"):
            parse_preset(bad_file)

    def test_rejects_nonexistent_file(self):
        """parse_preset raises an error for a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            parse_preset("/nonexistent/path.SerumPreset")


# ── write_preset ─────────────────────────────────────────────────────


class TestWritePreset:
    """Tests for the binary writer."""

    @requires_factory_presets
    def test_round_trip_produces_identical_data(self, tmp_path):
        """Loading a preset, writing it, and reloading produces the same
        header, params, and meta values."""
        original = parse_preset(FACTORY_BASS_PRESET)
        output_path = tmp_path / "roundtrip.SerumPreset"
        write_preset(original, output_path)

        reloaded = parse_preset(output_path)

        assert reloaded["header"] == original["header"]
        assert reloaded["params"] == original["params"]
        assert reloaded["_meta"]["section_flags"] == original["_meta"]["section_flags"]

    @requires_factory_presets
    def test_written_file_starts_with_magic(self, tmp_path):
        """The written file starts with XferJson magic bytes."""
        original = parse_preset(FACTORY_BASS_PRESET)
        output_path = tmp_path / "magic_check.SerumPreset"
        write_preset(original, output_path)

        raw = output_path.read_bytes()
        assert raw[:8] == b"XferJson"

    @requires_factory_presets
    def test_written_file_has_json_length_field(self, tmp_path):
        """The JSON length field at offset 9-10 matches the actual JSON size."""
        original = parse_preset(FACTORY_BASS_PRESET)
        output_path = tmp_path / "len_check.SerumPreset"
        write_preset(original, output_path)

        raw = output_path.read_bytes()
        # Offset layout: 8 bytes magic, 1 null, 2 bytes LE uint16 length, 6 bytes padding
        json_len = struct.unpack("<H", raw[9:11])[0]
        # The JSON starts at offset 17 (8+1+2+6) and should be exactly json_len bytes
        json_start = 17
        json_bytes = raw[json_start:json_start + json_len]
        import json
        parsed = json.loads(json_bytes)
        assert parsed["presetName"] == original["header"]["presetName"]

    @requires_factory_presets
    def test_written_file_contains_zstd_payload(self, tmp_path):
        """The written file contains a Zstandard magic number (0x28B52FFD)."""
        original = parse_preset(FACTORY_BASS_PRESET)
        output_path = tmp_path / "zstd_check.SerumPreset"
        write_preset(original, output_path)

        raw = output_path.read_bytes()
        assert b"\x28\xb5\x2f\xfd" in raw

    def test_creates_parent_directories(self, tmp_path):
        """write_preset creates parent dirs if they don't exist."""
        data = {
            "header": {"presetName": "test"},
            "params": {"key": "value"},
            "_meta": {"decompressed_size": 10, "section_flags": 2},
        }
        deep_path = tmp_path / "a" / "b" / "c" / "test.SerumPreset"
        write_preset(data, deep_path)
        assert deep_path.exists()


# ── deep_clone ───────────────────────────────────────────────────────


class TestDeepClone:
    """Tests for the deep_clone helper."""

    def test_clone_produces_equal_data(self, minimal_preset_data):
        """deep_clone produces a dict that is equal to the original."""
        cloned = deep_clone(minimal_preset_data)
        assert cloned == minimal_preset_data

    def test_clone_is_independent(self, minimal_preset_data):
        """Mutating the clone does not affect the original."""
        cloned = deep_clone(minimal_preset_data)
        cloned["header"]["presetName"] = "MUTATED"
        assert minimal_preset_data["header"]["presetName"] == "Test Preset"

    def test_clone_nested_independence(self, minimal_preset_data):
        """Mutating nested params in the clone does not affect the original."""
        cloned = deep_clone(minimal_preset_data)
        cloned["params"]["VoiceFilter0"]["plainParams"]["kParamFreq"] = 999.0
        assert minimal_preset_data["params"]["VoiceFilter0"]["plainParams"]["kParamFreq"] == 0.5

    @requires_factory_presets
    def test_clone_with_real_preset(self):
        """deep_clone works correctly with a real parsed preset."""
        original = parse_preset(FACTORY_BASS_PRESET)
        cloned = deep_clone(original)
        assert cloned == original
        cloned["header"]["presetName"] = "MODIFIED"
        assert original["header"]["presetName"] == "BA - Perfect Pluck"
