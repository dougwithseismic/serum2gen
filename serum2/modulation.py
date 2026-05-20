"""Modulation matrix helpers: source IDs, destination registry, slot building."""

SRC_ENV_BASE = 1      # Env0=1, Env1=2, Env2=3, Env3=4
SRC_LFO_BASE = 6      # LFO0=6, LFO1=7, ..., LFO9=15
SRC_VELOCITY = 22
SRC_NOTE = 23
SRC_MACRO_BASE = 25   # Macro0=25, ..., Macro7=32

SOURCE_NAMES = {}
for i in range(4):
    SOURCE_NAMES[f"Env{i}"] = SRC_ENV_BASE + i
    SOURCE_NAMES[f"ENV{i+1}"] = SRC_ENV_BASE + i
for i in range(10):
    SOURCE_NAMES[f"LFO{i}"] = SRC_LFO_BASE + i
for i in range(8):
    SOURCE_NAMES[f"Macro{i}"] = SRC_MACRO_BASE + i
SOURCE_NAMES["Velocity"] = SRC_VELOCITY
SOURCE_NAMES["Note"] = SRC_NOTE

SOURCE_ID_TO_NAME = {}
for name, sid in SOURCE_NAMES.items():
    if sid not in SOURCE_ID_TO_NAME:
        SOURCE_ID_TO_NAME[sid] = name

SAFE_MOD_DESTINATIONS = [
    {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0},
    {"t": "VoiceFilter", "p": "kParamReso", "pid": 4, "mid": 0},
    {"t": "VoiceFilter", "p": "kParamDrive", "pid": 1, "mid": 0},
    {"t": "VoiceFilter", "p": "kParamVar", "pid": 6, "mid": 0},
    {"t": "WTOsc", "p": "kParamWarp", "pid": 0, "mid": 0},
    {"t": "WTOsc", "p": "kParamWarp", "pid": 0, "mid": 1},
    {"t": "WTOsc", "p": "kParamWarp2", "pid": 3, "mid": 0},
    {"t": "WTOsc", "p": "kParamWarp2", "pid": 3, "mid": 1},
    {"t": "WTOsc", "p": "kParamRandomPhase", "pid": 9, "mid": 0},
    {"t": "WTOsc", "p": "kParamRandomPhase", "pid": 9, "mid": 1},
    {"t": "LFO", "p": "kParamRate", "pid": 0, "mid": 3},
    {"t": "Env", "p": "kParamSustain", "pid": 3, "mid": 0},
    {"t": "Env", "p": "kParamDecay", "pid": 2, "mid": 0},
]

FX_MOD_TARGETS = {
    "FXDistortion": [
        {"p": "kParamDrive", "pid": 2},
        {"p": "kParamWet", "pid": 1},
    ],
    "FXFilter": [
        {"p": "kParamFreq", "pid": 3},
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamReso", "pid": 4},
    ],
    "FXReverb": [
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamSize", "pid": 3},
    ],
    "FXHyperD": [
        {"p": "kParamDetune", "pid": 3},
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamRate", "pid": 2},
    ],
    "FXFlanger": [
        {"p": "kParamRate", "pid": 3},
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamDepth", "pid": 4},
    ],
    "FXPhaser": [
        {"p": "kParamFreq", "pid": 6},
        {"p": "kParamWet", "pid": 1},
    ],
    "FXChorus": [
        {"p": "kParamRate", "pid": 5},
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamDepth", "pid": 3},
    ],
    "FXDelay": [
        {"p": "kParamWet", "pid": 1},
        {"p": "kParamFeedback", "pid": 3},
    ],
    "FXEQ": [
        {"p": "kParamFreq2", "pid": 2},
        {"p": "kParamGain2", "pid": 4},
    ],
    "FXComp": [
        {"p": "kParamThresh", "pid": 5},
    ],
    "FXBode": [
        {"p": "kParamShift", "pid": 4},
        {"p": "kParamWet", "pid": 1},
    ],
}

DEST_SHORTNAMES = {
    "filter.freq": {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0},
    "filter.reso": {"t": "VoiceFilter", "p": "kParamReso", "pid": 4, "mid": 0},
    "filter.drive": {"t": "VoiceFilter", "p": "kParamDrive", "pid": 1, "mid": 0},
    "filter.var": {"t": "VoiceFilter", "p": "kParamVar", "pid": 6, "mid": 0},
    "osc0.warp": {"t": "WTOsc", "p": "kParamWarp", "pid": 0, "mid": 0},
    "osc1.warp": {"t": "WTOsc", "p": "kParamWarp", "pid": 0, "mid": 1},
    "osc0.warp2": {"t": "WTOsc", "p": "kParamWarp2", "pid": 3, "mid": 0},
    "osc1.warp2": {"t": "WTOsc", "p": "kParamWarp2", "pid": 3, "mid": 1},
    "env0.sustain": {"t": "Env", "p": "kParamSustain", "pid": 3, "mid": 0},
    "env0.decay": {"t": "Env", "p": "kParamDecay", "pid": 2, "mid": 0},
    "lfo0.rate": {"t": "LFO", "p": "kParamRate", "pid": 0, "mid": 0},
}


_SOURCE_NAMES_LOWER = {k.lower(): v for k, v in SOURCE_NAMES.items()}
_DEST_SHORTNAMES_LOWER = {k.lower(): v for k, v in DEST_SHORTNAMES.items()}


def resolve_source(name: str) -> list[int]:
    key = name.strip()
    if key in SOURCE_NAMES:
        return [SOURCE_NAMES[key], 0]
    if (v := _SOURCE_NAMES_LOWER.get(key.lower())) is not None:
        return [v, 0]
    raise ValueError(f"Unknown mod source: {name!r}. Valid: {', '.join(sorted(SOURCE_NAMES))}")


def resolve_destination(name: str) -> dict:
    if name in DEST_SHORTNAMES:
        return dict(DEST_SHORTNAMES[name])
    if (v := _DEST_SHORTNAMES_LOWER.get(name.lower())) is not None:
        return dict(v)
    raise ValueError(f"Unknown mod dest: {name!r}. Valid: {', '.join(sorted(DEST_SHORTNAMES))}")


def get_mod_destinations_for_preset(params: dict) -> list[dict]:
    dests = list(SAFE_MOD_DESTINATIONS)
    fx_list = params.get("FXRack0", {}).get("FX", [])
    for fx_idx, fx in enumerate(fx_list):
        for fx_type_name in fx:
            if not fx_type_name.startswith("FX"):
                continue
            targets = FX_MOD_TARGETS.get(fx_type_name, [])
            for target in targets:
                dests.append({
                    "t": fx_type_name,
                    "p": target["p"],
                    "pid": target["pid"],
                    "mid": fx_idx,
                })
    return dests


def build_mod_slot(source: list[int], dest: dict, amount: float, bipolar: bool = False) -> dict:
    slot = {
        "destModuleID": dest["mid"],
        "destModuleParamID": dest["pid"],
        "destModuleParamName": dest["p"],
        "destModuleTypeString": dest["t"],
        "plainParams": {"kParamAmount": amount},
        "source": source,
    }
    if bipolar:
        slot["plainParams"]["kParamBipolar"] = 1.0
    return slot
