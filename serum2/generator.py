"""Variation generator — creates preset variations from templates."""

import math
import random
from pathlib import Path

from .preset import Preset
from .modulation import (
    SRC_ENV_BASE, SRC_LFO_BASE, SRC_MACRO_BASE,
    SRC_VELOCITY, SRC_NOTE,
    build_mod_slot, get_mod_destinations_for_preset,
)
from .enums import (
    WARP_MODES, VOICE_FILTER_TYPES, BASIC_VOICE_FILTER_TYPES,
    FX_FILTER_TYPES, DISTORTION_MODES, WAVETABLES as _STATIC_WAVETABLES,
    LFO_TYPES, FX_TYPE_IDS,
)
from .paths import find_wavetables as _find_wavetables


def _get_wavetables() -> list[str]:
    """Return available wavetables, preferring the live filesystem scan."""
    try:
        live = _find_wavetables()
        if live:
            return live
    except Exception:
        pass
    return _STATIC_WAVETABLES

MACRO_NAMES = [
    "CUTOFF", "RESONANCE", "DRIVE", "WARP", "DETUNE",
    "MOVEMENT", "GRIT", "SPACE", "WIDTH", "DEPTH",
    "MORPH", "GROWL", "RUMBLE", "TEXTURE", "WEIGHT",
    "FILTER", "SWEEP", "BODY", "ATTACK", "DARKNESS",
    "TONE", "CRUSH", "WOBBLE", "PHASE", "STOMP",
    "SCREAM", "FILTH", "NASTY", "TEETH", "MANGLE",
    "CHAOS", "DRIFT", "RATE", "COLOR", "FM",
]

FILTER_FREQ_RANGE = (0.03, 0.9)
FILTER_RESO_RANGE = (0.0, 65.0)
FILTER_DRIVE_RANGE = (0.0, 80.0)
LFO_RATE_RANGE = (0.01, 0.9)
UNISON_RANGE = (2, 16)
FINE_TUNE_RANGE = (42.0, 58.0)
PORTAMENTO_RANGE = (0.003, 0.25)
MASTER_VOLUME_RANGE = (0.3, 0.65)


def _perturb(value, rng, intensity=0.3):
    lo, hi = rng
    return max(lo, min(hi, value + random.gauss(0, intensity * (hi - lo))))


def _rr(rng):
    return random.uniform(*rng)


def _generate_lfo_shape():
    shape = random.choices(
        ["saw_up", "saw_down", "square", "steps", "random", "smooth", "triangle"],
        weights=[15, 15, 10, 15, 20, 15, 10],
    )[0]

    if shape == "triangle":
        return {"curveVals": [0.5, 0.5], "isOpen": True, "numPoints": 2, "xVals": [0.5, 0.5], "yVals": [1.0, 0.0]}
    elif shape == "saw_up":
        return {"curveVals": [0.5, 0.5], "isOpen": True, "numPoints": 2, "xVals": [0.98, 0.02], "yVals": [0.0, 1.0]}
    elif shape == "saw_down":
        return {"curveVals": [0.5, 0.5], "isOpen": True, "numPoints": 2, "xVals": [0.98, 0.02], "yVals": [1.0, 0.0]}
    elif shape == "square":
        return {"curveVals": [0.5]*4, "isOpen": True, "numPoints": 4, "xVals": [0.01, 0.49, 0.01, 0.49], "yVals": [1.0, 1.0, 0.0, 0.0]}
    elif shape == "steps":
        n = random.choice([4, 6, 8, 12, 16])
        w = 1.0 / n
        x, y, c = [], [], []
        for j in range(n):
            v = random.random()
            x += [w * 0.01, w * 0.99] if j < n - 1 else [w]
            y += [v, v] if j < n - 1 else [v]
            c += [0.5, 0.5] if j < n - 1 else [0.5]
        return {"curveVals": c, "isOpen": True, "numPoints": len(x), "xVals": x, "yVals": y}
    elif shape == "random":
        n = random.randint(4, 16)
        x = [random.random() for _ in range(n)]
        xs = sum(x)
        x = [v / xs for v in x]
        return {"curveVals": [random.uniform(0.1, 0.9) for _ in range(n)], "isOpen": True, "numPoints": n, "xVals": x, "yVals": [random.random() for _ in range(n)]}
    else:
        n = random.randint(4, 12)
        phase = random.uniform(0, math.pi * 2)
        y = [max(0.0, min(1.0, 0.5 + 0.5 * math.sin(2 * math.pi * j / n + phase) + random.gauss(0, 0.1))) for j in range(n)]
        return {"curveVals": [random.uniform(0.2, 0.8) for _ in range(n)], "isOpen": True, "numPoints": n, "xVals": [1.0 / n] * n, "yVals": y}


def _activate_lfo(p, lfo_idx):
    key = f"LFO{lfo_idx}"
    lfo = p.get(key, {})

    is_chaos = random.random() < 0.3
    lfo_pp = {
        "kParamDefaultMode": 0.0,
        "kParamMode": "Free",
        "kParamRate": _rr(LFO_RATE_RANGE),
    }

    if is_chaos:
        chaos_type = random.choice([t for t in LFO_TYPES if t != "Path"])
        lfo_pp["kParamType"] = chaos_type
        lfo_pp["kParamRate"] = _rr((0.05, 0.5))
        if random.random() < 0.3:
            lfo_pp["kParamSmooth"] = _rr((0.0, 100.0))
        if random.random() < 0.4:
            lfo_pp["kParamRate10x"] = 1.0
    else:
        lfo["pathData"] = _generate_lfo_shape()

    if random.random() < 0.2:
        lfo_pp["kParamMode"] = "Envelope"
    if random.random() < 0.15:
        lfo_pp["kParamDelay"] = _rr((0.0, 50.0))
    if random.random() < 0.1:
        lfo_pp["kParamRise"] = _rr((0.0, 50.0))

    lfo["plainParams"] = lfo_pp
    p[key] = lfo
    return SRC_LFO_BASE + lfo_idx


def generate_variation(
    template: Preset,
    intensity: float = 0.5,
    name_prefix: str = "GEN",
    variation_id: int = 0,
    seed: int | None = None,
) -> Preset:
    if seed is not None:
        random.seed(seed)

    preset = template.clone()
    p = preset.params

    wavetables = _get_wavetables()
    for oi in [0, 1]:
        wt = p.get(f"Oscillator{oi}", {}).get(f"WTOsc{oi}", {})
        if "relativePathToWT" in wt and random.random() < intensity * 0.8:
            wt["relativePathToWT"] = random.choice(wavetables)

    for oi in [0, 1]:
        osc_pp = p.get(f"Oscillator{oi}", {}).get("plainParams", "default")
        if isinstance(osc_pp, dict):
            if "kParamUnison" in osc_pp:
                osc_pp["kParamUnison"] = float(max(2, min(16, round(_perturb(osc_pp["kParamUnison"], UNISON_RANGE, intensity)))))
            if "kParamFine" in osc_pp:
                osc_pp["kParamFine"] = _perturb(osc_pp["kParamFine"], FINE_TUNE_RANGE, intensity)

        wt_pp = p.get(f"Oscillator{oi}", {}).get(f"WTOsc{oi}", {}).get("plainParams", "default")
        if isinstance(wt_pp, dict) and random.random() < intensity * 0.7:
            wt_pp["kParamWarpMenu"] = random.choice(WARP_MODES)

    osc4_pp = p.get("Oscillator4", {}).get("plainParams", "default")
    if isinstance(osc4_pp, dict) and "kParamVolume" in osc4_pp:
        osc4_pp["kParamVolume"] = _perturb(osc4_pp["kParamVolume"], (0.15, 0.85), intensity)

    vf_pp = p.get("VoiceFilter0", {}).get("plainParams", "default")
    if isinstance(vf_pp, dict):
        current_type = vf_pp.get("kParamType", "")
        if current_type in BASIC_VOICE_FILTER_TYPES or current_type == "":
            vf_pp["kParamType"] = random.choice(VOICE_FILTER_TYPES)
        if "kParamFreq" in vf_pp:
            vf_pp["kParamFreq"] = _perturb(vf_pp["kParamFreq"], FILTER_FREQ_RANGE, intensity * 0.5)
        if "kParamReso" in vf_pp:
            vf_pp["kParamReso"] = _perturb(vf_pp["kParamReso"], FILTER_RESO_RANGE, intensity * 0.5)
        if "kParamDrive" in vf_pp:
            vf_pp["kParamDrive"] = _perturb(vf_pp["kParamDrive"], FILTER_DRIVE_RANGE, intensity * 0.5)
        if "kParamVar" in vf_pp:
            vf_pp["kParamVar"] = _perturb(vf_pp["kParamVar"], (0, 100), intensity * 0.3)

    num_lfos = random.choices([3, 4, 5, 6, 8, 10], weights=[5, 15, 25, 25, 20, 10])[0]
    num_lfos = max(num_lfos, 2)
    active_lfo_sources = []
    for li in range(num_lfos):
        src_id = _activate_lfo(p, li)
        active_lfo_sources.append([src_id, 0])

    p["LFO0"]["pathData"] = _generate_lfo_shape()
    p["LFO1"]["pathData"] = _generate_lfo_shape()

    env0 = p.get("Env0", {})
    env0_pp = env0.get("plainParams", {})
    if isinstance(env0_pp, str):
        env0_pp = {}
    if "kParamDecay" not in env0_pp:
        env0_pp["kParamDecay"] = _rr((0.15, 0.5))
    if "kParamSustain" not in env0_pp:
        env0_pp["kParamSustain"] = _rr((0.0, 0.15))
    if "kParamAttack" not in env0_pp:
        env0_pp["kParamAttack"] = _rr((0.001, 0.02))
    if "kParamRelease" not in env0_pp:
        env0_pp["kParamRelease"] = _rr((0.1, 0.4))
    env0["plainParams"] = env0_pp
    p["Env0"] = env0

    # --- Fixed macros 1-3 ---
    macro_sources = [[SRC_MACRO_BASE + i, 0] for i in range(8)]
    p["Macro0"] = {"name": "ENV 1", "plainParams": {"kParamValue": 50.0}}
    p["Macro1"] = {"name": "CUTOFF", "plainParams": {"kParamValue": 50.0}}
    p["Macro2"] = {"name": "LFO SPEED", "plainParams": {"kParamValue": 50.0}}

    remaining_names = random.sample(MACRO_NAMES, 5)
    for i in range(3, 8):
        p[f"Macro{i}"] = {
            "name": remaining_names[i - 3],
            "plainParams": {"kParamValue": _rr((0, 40)) if random.random() < 0.4 else 0.0},
        }

    for i in range(64):
        p[f"ModSlot{i}"] = {"plainParams": "default"}

    slot_idx = 0
    used_combos = set()

    # Fixed slots
    p[f"ModSlot{slot_idx}"] = build_mod_slot(
        [SRC_ENV_BASE + 0, 0],
        {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0},
        _rr((30.0, 70.0)),
    )
    slot_idx += 1

    p[f"ModSlot{slot_idx}"] = build_mod_slot(
        macro_sources[0],
        {"t": "Env", "p": "kParamSustain", "pid": 3, "mid": 0},
        _rr((70.0, 100.0)),
    )
    slot_idx += 1

    p[f"ModSlot{slot_idx}"] = build_mod_slot(
        macro_sources[1],
        {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0},
        _rr((60.0, 100.0)),
    )
    slot_idx += 1

    p[f"ModSlot{slot_idx}"] = build_mod_slot(
        [SRC_LFO_BASE + 0, 0],
        {"t": "VoiceFilter", "p": "kParamFreq", "pid": 3, "mid": 0},
        _rr((20.0, 80.0)),
        bipolar=random.random() < 0.4,
    )
    slot_idx += 1

    p[f"ModSlot{slot_idx}"] = build_mod_slot(
        macro_sources[2],
        {"t": "LFO", "p": "kParamRate", "pid": 0, "mid": 0},
        _rr((30.0, 60.0)),
    )
    slot_idx += 1

    # Random slots
    available_dests = get_mod_destinations_for_preset(p)
    num_extra_mods = random.randint(10, 24)

    for _ in range(int(num_extra_mods * 0.5)):
        if slot_idx >= 63:
            break
        dest = random.choice(available_dests)
        src = random.choice(active_lfo_sources)
        combo = (tuple(src), dest["t"], dest["p"], dest["mid"])
        if combo in used_combos:
            continue
        used_combos.add(combo)
        amount = _rr((-100, 100)) if random.random() < 0.3 else _rr((15, 100))
        p[f"ModSlot{slot_idx}"] = build_mod_slot(src, dest, amount, random.random() < 0.35)
        slot_idx += 1

    for mi in range(3, 8):
        if slot_idx >= 63:
            break
        dest = random.choice(available_dests)
        src = macro_sources[mi]
        combo = (tuple(src), dest["t"], dest["p"], dest["mid"])
        if combo in used_combos:
            continue
        used_combos.add(combo)
        p[f"ModSlot{slot_idx}"] = build_mod_slot(src, dest, _rr((20, 100)), random.random() < 0.2)
        slot_idx += 1

    for _ in range(int(num_extra_mods * 0.2)):
        if slot_idx >= 63:
            break
        dest = random.choice(available_dests)
        src_type = random.choices(
            [SRC_ENV_BASE + random.randint(0, 3), SRC_VELOCITY, SRC_NOTE],
            weights=[50, 30, 20]
        )[0]
        src = [src_type, 0]
        combo = (tuple(src), dest["t"], dest["p"], dest["mid"])
        if combo in used_combos:
            continue
        used_combos.add(combo)
        p[f"ModSlot{slot_idx}"] = build_mod_slot(src, dest, _rr((-80, 80)), random.random() < 0.3)
        slot_idx += 1

    for fx in p.get("FXRack0", {}).get("FX", []):
        if "FXDistortion" in fx:
            dp = fx["FXDistortion"].get("plainParams", {})
            if isinstance(dp, dict):
                dp["kParamDrive"] = _rr((15, 100))
                dp["kParamMode"] = random.choice(DISTORTION_MODES)
                dp["kParamWet"] = _rr((20, 100))
                if random.random() < 0.4:
                    dp["kParamPrePost"] = float(random.choice([0, 1]))

        if "FXReverb" in fx:
            rp = fx["FXReverb"].get("plainParams", {})
            if isinstance(rp, dict):
                if "kParamSize" in rp: rp["kParamSize"] = _rr((10, 70))
                if "kParamWet" in rp: rp["kParamWet"] = _rr((0, 50))

        if "FXFilter" in fx:
            fp = fx["FXFilter"].get("plainParams", {})
            if isinstance(fp, dict):
                if random.random() < 0.6:
                    fp["kParamType"] = random.choice(FX_FILTER_TYPES)
                if "kParamFreq" in fp: fp["kParamFreq"] = _rr(FILTER_FREQ_RANGE)
                if "kParamDrive" in fp: fp["kParamDrive"] = _rr(FILTER_DRIVE_RANGE)

        if "FXUtils" in fx:
            up = fx["FXUtils"].get("plainParams", {})
            if isinstance(up, dict):
                if "kParamLFXover" in up: up["kParamLFXover"] = _rr((50, 300))
                if "kParamWidth" in up: up["kParamWidth"] = _rr((20, 80))

    fx_rack = p.get("FXRack0", {})
    fx_list = fx_rack.get("FX", [])
    fx_types_present = set()
    for fx in fx_list:
        for k in fx:
            if k.startswith("FX"):
                fx_types_present.add(k)

    if "FXUtils" not in fx_types_present:
        fx_list.append({
            "FXUtils": {
                "plainParams": {
                    "kParamLFMono": 1.0,
                    "kParamLFXover": _rr((100, 200)),
                    "kParamWidth": _rr((55, 75)),
                }
            },
            "kUIParamMixOrGain": 0.0,
            "type": FX_TYPE_IDS["FXUtils"],
        })
    else:
        for fx in fx_list:
            if "FXUtils" in fx:
                up = fx["FXUtils"].get("plainParams", {})
                if isinstance(up, dict):
                    up.setdefault("kParamLFMono", 1.0)
                    up.setdefault("kParamLFXover", _rr((100, 200)))
                    if "kParamWidth" not in up:
                        up["kParamWidth"] = _rr((55, 75))

    if "FXComp" not in fx_types_present:
        fx_list.append({
            "FXComp": {
                "plainParams": {
                    "kParamRatio": _rr((2.0, 4.0)),
                    "kParamThresh": _rr((0.15, 0.35)),
                    "kParamAttack": _rr((30, 80)),
                    "kParamRelease": _rr((60, 120)),
                    "kParamMakeup": _rr((1.5, 4.0)),
                    "kParamWet": _rr((60, 100)),
                }
            },
            "kUIParamMixOrGain": 0.0,
            "type": FX_TYPE_IDS["FXComp"],
        })

    fx_rack["FX"] = fx_list
    p["FXRack0"] = fx_rack

    if random.random() < intensity * 0.3:
        p["Arp0"] = {
            "plainParams": {
                "kParamEnabled": 1.0,
                "kParamActiveClipID": float(random.randint(0, 11)),
            }
        }

    g0_pp = p.get("Global0", {}).get("plainParams", "default")
    if isinstance(g0_pp, dict):
        if "kParamPortamentoTime" in g0_pp:
            g0_pp["kParamPortamentoTime"] = _rr(PORTAMENTO_RANGE)
        if "kParamMasterVolume" in g0_pp:
            g0_pp["kParamMasterVolume"] = _perturb(g0_pp["kParamMasterVolume"], MASTER_VOLUME_RANGE, intensity)

    name = f"{name_prefix} - V{variation_id:03d}"
    preset.name = name
    preset.description = f"Generated variation #{variation_id}"

    return preset


def batch_generate(
    template_path: str | Path,
    output_dir: str | Path,
    count: int = 10,
    intensity: float = 0.5,
    name_prefix: str = "GEN",
    base_seed: int | None = None,
) -> list[Path]:
    template = Preset.load(template_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for i in range(count):
        seed = (base_seed + i) if base_seed is not None else None
        variation = generate_variation(
            template,
            intensity=intensity,
            name_prefix=name_prefix,
            variation_id=i,
            seed=seed,
        )
        filepath = output_dir / f"{name_prefix} - V{i:03d}.SerumPreset"
        variation.save(filepath)
        generated.append(filepath)

    return generated
