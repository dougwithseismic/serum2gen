"""Shared fixtures for serum2 tests."""

import copy
from pathlib import Path

import pytest


# ── Factory preset path for integration tests ───────────────────────
FACTORY_ROOT = Path(
    "/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets/Factory"
)
FACTORY_BASS_PRESET = (
    FACTORY_ROOT / "Bass" / "Misc" / "BA - Perfect Pluck.SerumPreset"
)

# Skip integration tests if factory presets are not available
requires_factory_presets = pytest.mark.skipif(
    not FACTORY_BASS_PRESET.exists(),
    reason="Factory presets not available (Serum 2 not installed)",
)


# ── Minimal in-memory preset dict (unit test fixture) ────────────────

def _build_minimal_preset_data() -> dict:
    """Build a minimal preset dict that mirrors the structure of a real
    parsed Serum 2 preset, suitable for unit tests that don't touch disk."""
    return {
        "header": {
            "fileType": "SerumPreset",
            "hash": "d41d8cd98f00b204e9800998ecf8427e",
            "presetAuthor": "TestAuthor",
            "presetDescription": "A test preset",
            "presetName": "Test Preset",
            "product": "Serum2",
            "productVersion": "2.0.0",
            "tags": ["Bass", "Mono"],
            "url": "",
            "vendor": "Test",
            "version": 4.0,
        },
        "params": {
            "Oscillator0": {
                "plainParams": {
                    "kParamEnable": 1.0,
                    "kParamVolume": 0.7,
                    "kParamPan": 0.5,
                    "kParamUnison": 4.0,
                    "kParamFine": 50.0,
                    "kParamSemitone": 0.0,
                    "kParamOctave": 0.0,
                    "kParamLevel": 1.0,
                },
                "WTOsc0": {
                    "plainParams": {
                        "kParamWarp": 0.5,
                        "kParamWarp2": 0.0,
                        "kParamWarpMenu": "kSync",
                    },
                    "relativePathToWT": "Analog/Basic Shapes.wav",
                },
            },
            "Oscillator1": {
                "plainParams": {
                    "kParamEnable": 0.0,
                    "kParamVolume": 0.5,
                    "kParamPan": 0.5,
                    "kParamUnison": 1.0,
                    "kParamFine": 50.0,
                    "kParamSemitone": 0.0,
                    "kParamOctave": 0.0,
                },
                "WTOsc1": {
                    "plainParams": {
                        "kParamWarp": 0.0,
                        "kParamWarp2": 0.0,
                        "kParamWarpMenu": "kSync",
                    },
                    "relativePathToWT": "Digital/Reese.wav",
                },
            },
            "Oscillator2": {"plainParams": "default"},
            "Oscillator3": {"plainParams": "default"},
            "Oscillator4": {"plainParams": "default"},
            "VoiceFilter0": {
                "plainParams": {
                    "kParamEnable": 1.0,
                    "kParamType": "L24",
                    "kParamFreq": 0.5,
                    "kParamReso": 20.0,
                    "kParamDrive": 10.0,
                    "kParamVar": 50.0,
                },
            },
            "Global0": {
                "plainParams": {
                    "kParamMasterVolume": 0.5,
                    "kParamPortamentoTime": 0.01,
                    "kParamPolyphony": 8.0,
                },
            },
            "Env0": {
                "plainParams": {
                    "kParamAttack": 0.01,
                    "kParamDecay": 0.3,
                    "kParamSustain": 0.5,
                    "kParamRelease": 0.4,
                },
            },
            "Env1": {
                "plainParams": {
                    "kParamAttack": 0.05,
                    "kParamDecay": 0.2,
                    "kParamSustain": 0.0,
                    "kParamRelease": 0.3,
                },
            },
            "Env2": {"plainParams": "default"},
            "Env3": {"plainParams": "default"},
            "LFO0": {
                "plainParams": {
                    "kParamRate": 0.25,
                    "kParamMode": "Free",
                    "kParamType": None,
                    "kParamSmooth": 0.0,
                    "kParamDelay": 0.0,
                },
                "pathData": {
                    "curveVals": [0.5, 0.5],
                    "isOpen": True,
                    "numPoints": 2,
                    "xVals": [0.5, 0.5],
                    "yVals": [1.0, 0.0],
                },
            },
            "LFO1": {"plainParams": "default"},
            "LFO2": {"plainParams": "default"},
            "LFO3": {"plainParams": "default"},
            "LFO4": {"plainParams": "default"},
            "LFO5": {"plainParams": "default"},
            "LFO6": {"plainParams": "default"},
            "LFO7": {"plainParams": "default"},
            "LFO8": {"plainParams": "default"},
            "LFO9": {"plainParams": "default"},
            "Macro0": {"name": "CUTOFF", "plainParams": {"kParamValue": 50.0}},
            "Macro1": {"name": "RESO", "plainParams": {"kParamValue": 30.0}},
            "Macro2": {"name": "", "plainParams": {"kParamValue": 0.0}},
            "Macro3": {"name": "", "plainParams": {"kParamValue": 0.0}},
            "Macro4": {"name": "", "plainParams": {"kParamValue": 0.0}},
            "Macro5": {"name": "", "plainParams": {"kParamValue": 0.0}},
            "Macro6": {"name": "", "plainParams": {"kParamValue": 0.0}},
            "Macro7": {"name": "", "plainParams": {"kParamValue": 0.0}},
            # Mod slots — first two active, rest default
            "ModSlot0": {
                "destModuleID": 0,
                "destModuleParamID": 3,
                "destModuleParamName": "kParamFreq",
                "destModuleTypeString": "VoiceFilter",
                "plainParams": {"kParamAmount": 50.0},
                "source": [6, 0],  # LFO0
            },
            "ModSlot1": {
                "destModuleID": 0,
                "destModuleParamID": 0,
                "destModuleParamName": "kParamWarp",
                "destModuleTypeString": "WTOsc",
                "plainParams": {"kParamAmount": 30.0, "kParamBipolar": 1.0},
                "source": [1, 0],  # Env0
            },
            **{f"ModSlot{i}": {"plainParams": "default"} for i in range(2, 64)},
            "FXRack0": {
                "FX": [
                    {
                        "FXDistortion": {
                            "plainParams": {
                                "kParamDrive": 40.0,
                                "kParamMode": "kSoftClip",
                                "kParamWet": 80.0,
                            }
                        },
                        "kUIParamMixOrGain": 0.0,
                        "type": 0,
                    },
                    {
                        "FXReverb": {
                            "plainParams": {
                                "kParamSize": 30.0,
                                "kParamWet": 20.0,
                            }
                        },
                        "kUIParamMixOrGain": 0.0,
                        "type": 3,
                    },
                ],
            },
        },
        "_meta": {
            "decompressed_size": 5000,
            "section_flags": 2,
        },
    }


@pytest.fixture
def minimal_preset_data():
    """Return a fresh deep copy of the minimal preset data dict."""
    return copy.deepcopy(_build_minimal_preset_data())


@pytest.fixture
def minimal_preset():
    """Return a Preset instance backed by the minimal preset data."""
    from serum2.preset import Preset
    return Preset(copy.deepcopy(_build_minimal_preset_data()))


@pytest.fixture
def factory_preset_path():
    """Return the path to a factory preset (skip if not available)."""
    if not FACTORY_BASS_PRESET.exists():
        pytest.skip("Factory presets not available")
    return FACTORY_BASS_PRESET


@pytest.fixture
def factory_preset():
    """Return a loaded Preset from factory (skip if not available)."""
    if not FACTORY_BASS_PRESET.exists():
        pytest.skip("Factory presets not available")
    from serum2.preset import Preset
    return Preset.load(FACTORY_BASS_PRESET)
