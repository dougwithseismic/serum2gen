"""High-level Preset class — the main API for Serum 2 preset manipulation."""

import hashlib
import json
from pathlib import Path

from .core import parse_preset, write_preset, deep_clone
from .modulation import (
    build_mod_slot, resolve_source, resolve_destination,
    get_mod_destinations_for_preset, SOURCE_ID_TO_NAME,
)
from .enums import FX_TYPE_IDS

HEADER_ALIASES = {
    "name": "presetName",
    "author": "presetAuthor",
    "description": "presetDescription",
    "tags": "tags",
}

PARAM_ALIASES = {
    "filter.freq": "VoiceFilter0.plainParams.kParamFreq",
    "filter.reso": "VoiceFilter0.plainParams.kParamReso",
    "filter.drive": "VoiceFilter0.plainParams.kParamDrive",
    "filter.type": "VoiceFilter0.plainParams.kParamType",
    "filter.var": "VoiceFilter0.plainParams.kParamVar",
    "filter.enable": "VoiceFilter0.plainParams.kParamEnable",
    "global.volume": "Global0.plainParams.kParamMasterVolume",
    "global.porta": "Global0.plainParams.kParamPortamentoTime",
    "global.glide": "Global0.plainParams.kParamPortamentoTime",
    "global.poly": "Global0.plainParams.kParamPolyphony",
}

for _i in range(5):
    PARAM_ALIASES[f"osc{_i}.enable"] = f"Oscillator{_i}.plainParams.kParamEnable"
    PARAM_ALIASES[f"osc{_i}.volume"] = f"Oscillator{_i}.plainParams.kParamVolume"
    PARAM_ALIASES[f"osc{_i}.pan"] = f"Oscillator{_i}.plainParams.kParamPan"
    PARAM_ALIASES[f"osc{_i}.unison"] = f"Oscillator{_i}.plainParams.kParamUnison"
    PARAM_ALIASES[f"osc{_i}.fine"] = f"Oscillator{_i}.plainParams.kParamFine"
    PARAM_ALIASES[f"osc{_i}.semi"] = f"Oscillator{_i}.plainParams.kParamSemitone"
    PARAM_ALIASES[f"osc{_i}.octave"] = f"Oscillator{_i}.plainParams.kParamOctave"
    PARAM_ALIASES[f"osc{_i}.level"] = f"Oscillator{_i}.plainParams.kParamLevel"
    PARAM_ALIASES[f"osc{_i}.warp"] = f"Oscillator{_i}.WTOsc{_i}.plainParams.kParamWarp"
    PARAM_ALIASES[f"osc{_i}.warp2"] = f"Oscillator{_i}.WTOsc{_i}.plainParams.kParamWarp2"
    PARAM_ALIASES[f"osc{_i}.warpmode"] = f"Oscillator{_i}.WTOsc{_i}.plainParams.kParamWarpMenu"
    PARAM_ALIASES[f"osc{_i}.wavetable"] = f"Oscillator{_i}.WTOsc{_i}.relativePathToWT"

for _i in range(4):
    PARAM_ALIASES[f"env{_i}.attack"] = f"Env{_i}.plainParams.kParamAttack"
    PARAM_ALIASES[f"env{_i}.decay"] = f"Env{_i}.plainParams.kParamDecay"
    PARAM_ALIASES[f"env{_i}.sustain"] = f"Env{_i}.plainParams.kParamSustain"
    PARAM_ALIASES[f"env{_i}.release"] = f"Env{_i}.plainParams.kParamRelease"

for _i in range(10):
    PARAM_ALIASES[f"lfo{_i}.rate"] = f"LFO{_i}.plainParams.kParamRate"
    PARAM_ALIASES[f"lfo{_i}.mode"] = f"LFO{_i}.plainParams.kParamMode"
    PARAM_ALIASES[f"lfo{_i}.type"] = f"LFO{_i}.plainParams.kParamType"
    PARAM_ALIASES[f"lfo{_i}.smooth"] = f"LFO{_i}.plainParams.kParamSmooth"
    PARAM_ALIASES[f"lfo{_i}.delay"] = f"LFO{_i}.plainParams.kParamDelay"

for _i in range(8):
    PARAM_ALIASES[f"macro{_i}.value"] = f"Macro{_i}.plainParams.kParamValue"
    PARAM_ALIASES[f"macro{_i}.name"] = f"Macro{_i}.__name__"


def _resolve_alias(path: str) -> str:
    return PARAM_ALIASES.get(path.lower(), path)


def _coerce_value(raw: str) -> float | str:
    try:
        return float(raw)
    except (ValueError, TypeError):
        return raw


class Preset:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls, path: str | Path) -> "Preset":
        return cls(parse_preset(path))

    def save(self, path: str | Path) -> None:
        write_preset(self._data, path)

    def clone(self) -> "Preset":
        return Preset(deep_clone(self._data))

    @property
    def raw(self) -> dict:
        return self._data

    @property
    def params(self) -> dict:
        return self._data["params"]

    @property
    def header(self) -> dict:
        return self._data["header"]

    @property
    def name(self) -> str:
        return self.header.get("presetName", "")

    @name.setter
    def name(self, value: str):
        self.header["presetName"] = value
        self.header["hash"] = hashlib.md5(value.encode()).hexdigest()

    @property
    def description(self) -> str:
        return self.header.get("presetDescription", "")

    @description.setter
    def description(self, value: str):
        self.header["presetDescription"] = value

    @property
    def author(self) -> str:
        return self.header.get("presetAuthor", "")

    @author.setter
    def author(self, value: str):
        self.header["presetAuthor"] = value

    @property
    def tags(self) -> list[str]:
        return self.header.get("tags", [])

    @tags.setter
    def tags(self, value: list[str]):
        self.header["tags"] = value

    def get(self, path: str, default=None):
        lower = path.lower().strip()
        if lower in HEADER_ALIASES:
            return self.header.get(HEADER_ALIASES[lower], default)

        resolved = _resolve_alias(path)

        if resolved.endswith(".__name__"):
            key = resolved.rsplit(".", 2)[0]
            macro = self.params.get(key, {})
            return macro.get("name", default)

        keys = resolved.split(".")
        current = self.params
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def set(self, path: str, value) -> None:
        lower = path.lower().strip()
        if lower in HEADER_ALIASES:
            header_key = HEADER_ALIASES[lower]
            if header_key == "tags" and isinstance(value, str):
                value = [t.strip() for t in value.split(",")]
            self.header[header_key] = value
            if header_key == "presetName":
                self.header["hash"] = hashlib.md5(str(value).encode()).hexdigest()
            return

        resolved = _resolve_alias(path)

        if resolved.endswith(".__name__"):
            key = resolved.rsplit(".", 2)[0]
            self.params.setdefault(key, {})["name"] = value
            return

        keys = resolved.split(".")
        current = self.params
        for key in keys[:-1]:
            if key not in current or current[key] == "default":
                current[key] = {}
            if not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        if isinstance(value, str):
            value = _coerce_value(value)
        current[keys[-1]] = value

    def _get_plain_params(self, section: str) -> dict:
        obj = self.params.get(section, {})
        pp = obj.get("plainParams", {})
        return {} if isinstance(pp, str) else pp

    def _set_plain_params(self, section: str, param_map: dict, **kwargs):
        obj = self.params.setdefault(section, {})
        pp = obj.get("plainParams", {})
        if isinstance(pp, str):
            pp = {}
        for k, v in kwargs.items():
            if k in param_map and v is not None:
                pp[param_map[k]] = v
        obj["plainParams"] = pp

    def get_macro(self, idx: int) -> dict:
        macro = self.params.get(f"Macro{idx}", {})
        pp = macro.get("plainParams", {})
        return {
            "name": macro.get("name", ""),
            "value": pp.get("kParamValue", 0.0) if isinstance(pp, dict) else 0.0,
        }

    def set_macro(self, idx: int, name: str | None = None, value: float | None = None):
        key = f"Macro{idx}"
        macro = self.params.setdefault(key, {})
        if name is not None:
            macro["name"] = name
        pp = macro.setdefault("plainParams", {})
        if isinstance(pp, str):
            pp = {}
            macro["plainParams"] = pp
        if value is not None:
            pp["kParamValue"] = float(value)

    def list_mods(self) -> list[dict]:
        slots = []
        for i in range(64):
            slot = self.params.get(f"ModSlot{i}", {})
            pp = slot.get("plainParams", "default")
            if pp == "default":
                continue
            source_id = slot.get("source", [0, 0])
            sid = source_id[0] if isinstance(source_id, list) else source_id
            slots.append({
                "slot": i,
                "source": SOURCE_ID_TO_NAME.get(sid, f"Unknown({sid})"),
                "source_id": source_id,
                "dest_type": slot.get("destModuleTypeString", ""),
                "dest_param": slot.get("destModuleParamName", ""),
                "dest_module": slot.get("destModuleID", 0),
                "amount": pp.get("kParamAmount", 0) if isinstance(pp, dict) else 0,
                "bipolar": pp.get("kParamBipolar", 0) == 1.0 if isinstance(pp, dict) else False,
            })
        return slots

    def add_mod(
        self,
        source: str,
        dest: str,
        amount: float,
        bipolar: bool = False,
    ) -> int:
        src = resolve_source(source)
        dst = resolve_destination(dest)
        for i in range(64):
            pp = self.params.get(f"ModSlot{i}", {}).get("plainParams", "default")
            if pp == "default":
                self.params[f"ModSlot{i}"] = build_mod_slot(src, dst, amount, bipolar)
                return i
        raise RuntimeError("No free mod slots (max 64)")

    def clear_mod(self, slot: int):
        self.params[f"ModSlot{slot}"] = {"plainParams": "default"}

    def clear_all_mods(self):
        for i in range(64):
            self.params[f"ModSlot{i}"] = {"plainParams": "default"}

    _LFO_PARAM_MAP = {
        "rate": "kParamRate", "mode": "kParamMode", "type": "kParamType",
        "smooth": "kParamSmooth", "delay": "kParamDelay",
        "rise": "kParamRise", "rate10x": "kParamRate10x",
    }

    _ENV_PARAM_MAP = {
        "attack": "kParamAttack", "decay": "kParamDecay",
        "sustain": "kParamSustain", "release": "kParamRelease",
    }

    def get_lfo(self, idx: int) -> dict:
        pp = self._get_plain_params(f"LFO{idx}")
        lfo = self.params.get(f"LFO{idx}", {})
        return {
            "rate": pp.get("kParamRate"),
            "mode": pp.get("kParamMode"),
            "type": pp.get("kParamType"),
            "smooth": pp.get("kParamSmooth"),
            "delay": pp.get("kParamDelay"),
            "has_path": "pathData" in lfo,
        }

    def set_lfo(self, idx: int, **kwargs):
        self._set_plain_params(f"LFO{idx}", self._LFO_PARAM_MAP, **kwargs)

    def get_envelope(self, idx: int) -> dict:
        pp = self._get_plain_params(f"Env{idx}")
        return {
            "attack": pp.get("kParamAttack"),
            "decay": pp.get("kParamDecay"),
            "sustain": pp.get("kParamSustain"),
            "release": pp.get("kParamRelease"),
        }

    def set_envelope(self, idx: int, **kwargs):
        self._set_plain_params(f"Env{idx}", self._ENV_PARAM_MAP, **kwargs)

    def fx_chain(self) -> list[dict]:
        fx_list = self.params.get("FXRack0", {}).get("FX", [])
        result = []
        for i, fx in enumerate(fx_list):
            for key in fx:
                if key.startswith("FX"):
                    pp = fx[key].get("plainParams", {})
                    result.append({
                        "index": i,
                        "type": key,
                        "params": pp if isinstance(pp, dict) else {},
                    })
        return result

    def add_fx(self, fx_type: str, params: dict | None = None) -> int:
        if fx_type not in FX_TYPE_IDS:
            raise ValueError(f"Unknown FX type: {fx_type!r}. Valid: {', '.join(sorted(FX_TYPE_IDS))}")

        rack = self.params.setdefault("FXRack0", {})
        fx_list = rack.setdefault("FX", [])

        entry = {
            fx_type: {"plainParams": params or {}},
            "kUIParamMixOrGain": 0.0,
            "type": FX_TYPE_IDS[fx_type],
        }
        fx_list.append(entry)
        rack["FX"] = fx_list
        return len(fx_list) - 1

    def remove_fx(self, index: int):
        fx_list = self.params.get("FXRack0", {}).get("FX", [])
        if 0 <= index < len(fx_list):
            fx_list.pop(index)

    def get_oscillator(self, idx: int) -> dict:
        osc = self.params.get(f"Oscillator{idx}", {})
        pp = osc.get("plainParams", "default")
        wt = osc.get(f"WTOsc{idx}", {})
        wt_pp = wt.get("plainParams", {})

        result = {"index": idx}
        if isinstance(pp, dict):
            result["enabled"] = pp.get("kParamEnable", 1.0 if idx == 0 else 0.0) == 1.0
            result["volume"] = pp.get("kParamVolume")
            result["pan"] = pp.get("kParamPan")
            result["unison"] = pp.get("kParamUnison")
            result["fine"] = pp.get("kParamFine")
            result["semitone"] = pp.get("kParamSemitone")
            result["octave"] = pp.get("kParamOctave")
        else:
            result["enabled"] = idx == 0

        if wt:
            result["wavetable"] = wt.get("relativePathToWT", "")
            if isinstance(wt_pp, dict):
                result["warp_mode"] = wt_pp.get("kParamWarpMenu")
                result["warp"] = wt_pp.get("kParamWarp")
                result["warp2"] = wt_pp.get("kParamWarp2")

        return result

    # ── Wavetable management ──────────────────────────────────────────

    def get_wavetable(self, osc_idx: int) -> str | None:
        """Return the relativePathToWT for the given oscillator, or None."""
        return (
            self.params
            .get(f"Oscillator{osc_idx}", {})
            .get(f"WTOsc{osc_idx}", {})
            .get("relativePathToWT")
        )

    def set_wavetable(self, osc_idx: int, path: str) -> None:
        """Set the relativePathToWT for the given oscillator."""
        osc = self.params.setdefault(f"Oscillator{osc_idx}", {})
        wt = osc.setdefault(f"WTOsc{osc_idx}", {})
        wt["relativePathToWT"] = path

    # ── Noise sample management ─────────────────────────────────────

    def get_noise(self, osc_idx: int) -> str | None:
        """Return the relativePathToNoiseSample for the given oscillator, or None."""
        return (
            self.params
            .get(f"Oscillator{osc_idx}", {})
            .get(f"NoiseOsc{osc_idx}", {})
            .get("relativePathToNoiseSample")
        )

    def set_noise(self, osc_idx: int, path: str) -> None:
        """Set the relativePathToNoiseSample for the given oscillator,
        preserving existing metadata (detuneFactor, etc.)."""
        osc = self.params.setdefault(f"Oscillator{osc_idx}", {})
        noise = osc.setdefault(f"NoiseOsc{osc_idx}", {})
        noise["relativePathToNoiseSample"] = path

    # ── Arpeggiator ─────────────────────────────────────────────────

    _ARP_PARAM_MAP = {
        "enabled": "kParamEnabled",
        "clip_id": "kParamActiveClipID",
        "key_zone_max": "kParamKeyZoneMax",
        "launch_quantize": "kParamLaunchQuantize",
    }

    def get_arp(self) -> dict:
        """Return arpeggiator state as a friendly dict."""
        pp = self._get_plain_params("Arp0")
        return {
            "enabled": pp.get("kParamEnabled", 0.0) == 1.0,
            "clip_id": pp.get("kParamActiveClipID"),
            "key_zone_max": pp.get("kParamKeyZoneMax"),
            "launch_quantize": pp.get("kParamLaunchQuantize"),
        }

    def set_arp(self, **kwargs) -> None:
        """Set arpeggiator params. Accepts: enabled, clip_id, key_zone_max, launch_quantize."""
        if "enabled" in kwargs and kwargs["enabled"] is not None:
            kwargs["enabled"] = 1.0 if kwargs["enabled"] else 0.0
        self._set_plain_params("Arp0", self._ARP_PARAM_MAP, **kwargs)

    def summary(self) -> dict:
        oscs = [self.get_oscillator(i) for i in range(5)]
        active_oscs = [o for o in oscs if o.get("enabled")]

        macros = {}
        for i in range(8):
            m = self.get_macro(i)
            if m["name"]:
                macros[f"macro{i}"] = m

        mods = self.list_mods()

        vf = self.params.get("VoiceFilter0", {}).get("plainParams", {})
        filter_info = {}
        if isinstance(vf, dict):
            filter_info = {
                "type": vf.get("kParamType"),
                "freq": vf.get("kParamFreq"),
                "reso": vf.get("kParamReso"),
                "drive": vf.get("kParamDrive"),
                "enabled": vf.get("kParamEnable", 0.0) == 1.0,
            }

        return {
            "name": self.name,
            "author": self.author,
            "tags": self.tags,
            "oscillators": active_oscs,
            "filter": filter_info,
            "macros": macros,
            "mod_count": len(mods),
            "fx": [{"type": f["type"]} for f in self.fx_chain()],
            "envelopes": {f"env{i}": self.get_envelope(i) for i in range(4)},
            "lfos": {f"lfo{i}": l for i in range(10) if (l := self.get_lfo(i))["rate"] is not None},
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.summary(), indent=indent, default=str)

    def export_full(self, indent: int = 2) -> str:
        return json.dumps({
            "header": self.header,
            "params": self.params,
            "_meta": self._data["_meta"],
        }, indent=indent, default=str)

    def __repr__(self) -> str:
        return f"Preset({self.name!r})"
