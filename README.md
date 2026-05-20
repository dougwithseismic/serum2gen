# serum2gen

CLI and Python API for reading, writing, editing, and generating [Serum 2](https://xferrecords.com/products/serum) presets.

- Reverse-engineered Serum 2 `.SerumPreset` binary format (XferJson + CBOR + Zstandard)
- Full read/write cycle with byte-level fidelity
- 20+ CLI commands for every aspect of preset manipulation
- 150+ parameter aliases for human-friendly editing
- Variation generator with constrained randomization
- Auto-detects Serum 2 preset folders (macOS + Windows)
- Python API for scripting and automation

## Install

```bash
pip install -e .
```

Requires Python 3.11+. Dependencies: `cbor2`, `click`, `zstandard`.

## Quick start

```bash
# Browse your presets
serum2 list
serum2 list -c Bass

# Inspect any preset (by full path or partial name)
serum2 inspect "808 - Decomposed"

# Read/write parameters using human-friendly aliases
serum2 get "808 - Decomposed" filter.freq
serum2 set "808 - Decomposed" filter.type LadderAcid -o my_edit.SerumPreset

# Clone and tweak
serum2 clone "808 - Decomposed" "My 808"
serum2 set "My 808" author "Your Name"

# Generate 20 variations from any template
serum2 generate "808 - Decomposed" -n 20 -i 0.6 -p "MY808" -s 42

# Search across all presets
serum2 search acid --author "Matt"
```

## Commands

### Core

| Command | Description |
|---------|-------------|
| `serum2 list [-c category]` | Browse presets in Serum 2 folder |
| `serum2 inspect <preset>` | Full breakdown of a preset |
| `serum2 search <query>` | Find presets by name, author, filter, FX |
| `serum2 get <preset> <param>` | Read any parameter |
| `serum2 set <preset> <param> <value>` | Write any parameter |
| `serum2 bulk-set <preset> -p '{"a":1}'` | Set multiple params at once |
| `serum2 clone <preset> <name>` | Clone with a new name |
| `serum2 rename <preset> <name>` | Rename in place |
| `serum2 diff <a> <b>` | Compare two presets |
| `serum2 export <preset> [--full]` | Export to JSON |
| `serum2 import <json> -o <preset>` | Import from JSON |
| `serum2 generate <template> -n N` | Generate variations |
| `serum2 enums [category]` | Show valid enum values |

### Subcommands

| Command | Description |
|---------|-------------|
| `serum2 mod list <preset>` | Show modulation matrix |
| `serum2 mod add <preset> <src> <dst> <amt>` | Add modulation routing |
| `serum2 mod clear <preset>` | Clear mod slots |
| `serum2 fx list <preset>` | Show FX chain |
| `serum2 fx add <preset> <type>` | Add FX module |
| `serum2 fx remove <preset> <index>` | Remove FX |
| `serum2 macro list <preset>` | Show macros |
| `serum2 macro set <preset> <idx>` | Set macro name/value |
| `serum2 env list <preset>` | Show envelopes |
| `serum2 env set <preset> <idx>` | Set ADSR |
| `serum2 lfo list <preset>` | Show LFOs |
| `serum2 lfo set <preset> <idx>` | Set LFO params |

## Parameter aliases

Instead of raw CBOR paths like `VoiceFilter0.plainParams.kParamFreq`, use aliases:

```
filter.freq    filter.reso    filter.type    filter.drive
osc0.warp      osc0.warpmode  osc0.unison    osc0.fine
osc0.wavetable osc0.volume    osc0.semi      osc0.octave
env0.attack    env0.decay     env0.sustain   env0.release
lfo0.rate      lfo0.mode      lfo0.type      lfo0.smooth
macro0.value   macro0.name    global.volume  global.porta
name           author         description    tags
```

All 150+ aliases: `serum2 enums aliases`

## Python API

```python
from serum2 import Preset, find_presets, batch_generate

# Load and edit
p = Preset.load("path/to/preset.SerumPreset")
p.set("filter.freq", 0.5)
p.set("filter.type", "LadderAcid")
p.set("author", "Your Name")
p.name = "My Preset"

# Macros (0-indexed in API)
p.set_macro(0, name="CUTOFF", value=50.0)

# Modulation
p.add_mod("LFO0", "filter.freq", amount=50.0, bipolar=True)
mods = p.list_mods()

# Envelopes and LFOs
p.set_envelope(0, attack=0.01, decay=0.3, sustain=0.5, release=0.4)
p.set_lfo(0, rate=0.5, mode="Free")

# FX
p.add_fx("FXDistortion", {"kParamDrive": 50, "kParamMode": "kSoftClip"})

# Save
p.save("output.SerumPreset")

# Clone
p2 = p.clone()
p2.name = "Variant"
p2.save("variant.SerumPreset")

# Batch generate
batch_generate("template.SerumPreset", "./output", count=20, intensity=0.6, seed=42)

# Browse
presets = find_presets()  # Auto-detects Serum 2 folder
```

## Generator

The variation generator creates presets from templates with:

- Wavetable, warp mode, and filter type randomization
- Multiple LFOs with varied shapes (saw, square, steps, random, smooth, chaos types)
- Fixed macro layout: Macro 1 = ENV 1 sustain, Macro 2 = CUTOFF (with LFO modulation), Macro 3 = LFO SPEED
- Dynamic FX-aware mod routing (only targets FX modules actually present)
- Width (stereo + LF mono) and compression on every preset
- Pitch-stable: no mod routing to fine tune, detune, or master tuning
- Reproducible via seed

```bash
serum2 generate "template.SerumPreset" -n 50 -i 0.7 -p "ACID" -s 1234
```

## Binary format

Serum 2 `.SerumPreset` files use a custom container:

```
[8 bytes]  Magic: "XferJson"
[1 byte]   Null separator
[2 bytes]  JSON header length (LE uint16)
[6 bytes]  Padding
[N bytes]  JSON header (name, author, tags, description)
[4 bytes]  Decompressed CBOR size (LE uint32)
[4 bytes]  Section flags (LE uint32)
[N bytes]  Zstandard-compressed CBOR payload (all synth parameters)
```

## Enum reference

```bash
serum2 enums              # List all categories
serum2 enums warp         # 16 warp modes
serum2 enums filter       # 32 voice filter types
serum2 enums distortion   # 16 distortion modes
serum2 enums fx           # 12 FX types
serum2 enums sources      # 28 mod sources
serum2 enums destinations # Mod destination shortnames
serum2 enums aliases      # All parameter aliases
serum2 enums header       # Header field names
```

## License

MIT
