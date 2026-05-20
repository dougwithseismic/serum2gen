# serum2gen

CLI and Python API for Serum 2 (.SerumPreset) preset manipulation. Serum 2 only — not Serum 1.

## Binary format

Serum 2 `.SerumPreset` files:
- `XferJson` magic (8 bytes) + null + LE uint16 JSON length + 6 bytes padding + JSON header + LE uint32 decompressed size + LE uint32 flags + Zstandard-compressed CBOR payload
- The JSON header contains metadata (name, author, tags, description, hash)
- The CBOR payload contains all synth parameters (oscillators, filters, FX, modulation, macros, LFOs, envelopes)

## Critical constraints

- **`"default"` sentinel**: Many CBOR fields use the string `"default"` as a type marker. Never replace it with a dict — Serum will crash.
- **0-indexed data, 1-indexed UI**: ENV 1 in Serum UI = `Env0` in data. LFO 1 = `LFO0`. Macro 1 = `Macro0`. The CLI commands accept UI numbering (1-based).
- **Mod destinations must match FX chain**: Never route modulation to FX modules that don't exist in the preset's FX rack. Use `get_mod_destinations_for_preset()` to build safe destination lists.
- **Pitch stability**: Never modulate `kParamFine`, `kParamDetune`, or `kParamMasterTuning` — it makes patches behave differently across octaves.
- **Exotic filter preservation**: Some presets use rare filter types (Allpasses, Combs, etc). Only replace basic types (L12, L24, B12...) when randomizing.

## CLI usage

```bash
serum2 list [-c category]          # Browse presets
serum2 inspect <preset>            # Full breakdown
serum2 search <query>              # Find by name/author/filter
serum2 get <preset> <param>        # Read any param (aliases: filter.freq, osc0.warp, env0.sustain, author, name...)
serum2 set <preset> <param> <val>  # Write any param
serum2 bulk-set <preset> -p '{}'   # Set multiple params as JSON
serum2 clone <preset> <name>       # Clone with new name
serum2 rename <preset> <name>      # Rename in place
serum2 generate <template> -n 10   # Generate variations from template
serum2 mod list/add/clear          # Modulation matrix
serum2 fx list/add/remove          # FX chain
serum2 macro list/set              # Macros (1-8)
serum2 env list/set                # Envelopes (1-4)
serum2 lfo list/set                # LFOs (1-10)
serum2 diff <a> <b>                # Compare presets
serum2 export/import               # JSON round-trip
serum2 enums [category]            # Valid enum values
serum2 wt list/get/set             # Wavetable management (288 factory tables)
serum2 noise list/get/set          # Noise sample assignment (900+ samples)
serum2 arp get/set/patterns/clips  # Arpeggiator editing
serum2 ml train                    # Train VAE on factory presets
serum2 ml generate <model> -n 10   # Sample from latent space
serum2 ml interpolate <model> a b  # Interpolate between presets
serum2 ml similar <model> <preset> # Find similar presets
```

## Python API

```python
from serum2 import Preset

p = Preset.load("path/to/preset.SerumPreset")
p.set("filter.freq", 0.5)
p.set("author", "My Name")
p.set_macro(0, name="CUTOFF", value=50.0)
p.add_mod("LFO0", "filter.freq", amount=50.0)
p.set_envelope(0, attack=0.01, decay=0.3, sustain=0.5, release=0.4)
p.set_lfo(0, rate=0.5, mode="Free")
p.add_fx("FXDistortion", {"kParamDrive": 50, "kParamMode": "kSoftClip"})
p.set_wavetable(0, "Analog/Acid.wav")
p.set_noise(3, "Analog/BrightWhite.wav")
p.set_arp(enabled=True, clip_id=3)
p.save("output.SerumPreset")
```

## Source IDs (for modulation)

- Env0-3 = 1-4, LFO0-9 = 6-15, Velocity = 22, Note = 23, Macro0-7 = 25-32

## Verified enums

Run `serum2 enums` to see all categories. Key ones: warp modes (16), voice filter types (32), distortion modes (16), FX types (12).

## Preset paths

- Mac: `/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets/`
- Windows: `~/Documents/Xfer/Serum 2 Presets/Presets/`
- User presets go in the `User/` subfolder
- Tables (wavetables): `../Tables/` (sibling of Presets/)
- Noise samples: `../Samples/Factory Non-Tonal/Noises/`
- Arp patterns: `../Arp Patterns/` (.XferArp files)
- Clips: `../Clips/` (.XferClip files)

## ML/VAE

Install: `pip install -e ".[ml]"` (requires torch + numpy)

Train a VAE on all factory presets, then sample the latent space or interpolate between presets. The feature vector (98 dims) includes filter, oscillator, envelope, LFO, macro params + one-hot encoded categorical params (filter type, warp modes). Template presets provide the structural skeleton (FX chain, mod matrix, wavetables) that the VAE doesn't model.
