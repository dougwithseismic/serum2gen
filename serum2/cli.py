"""serum2 CLI — inspect, edit, generate, and manage Serum 2 presets."""

import json
import sys
from pathlib import Path

import click

from .preset import Preset, PARAM_ALIASES, HEADER_ALIASES
from .paths import (
    get_preset_root, get_user_folder, find_presets, resolve_preset,
    find_wavetables, find_noise_samples, find_arp_patterns, find_clips,
)
from .generator import batch_generate
from .enums import (
    WARP_MODES, VOICE_FILTER_TYPES, FX_FILTER_TYPES,
    DISTORTION_MODES, LFO_TYPES, LFO_MODES, FX_TYPE_IDS,
)
from .modulation import SOURCE_NAMES, DEST_SHORTNAMES


def _load(path_str: str) -> tuple[Preset, Path]:
    resolved = resolve_preset(path_str)
    if resolved is None:
        click.echo(f"Preset not found: {path_str}", err=True)
        sys.exit(1)
    return Preset.load(resolved), resolved


def _output_path(preset_path: Path, output: str | None) -> Path:
    if output:
        return Path(output)
    return preset_path


def _validate_index(value: int, label: str, lo: int, hi: int) -> int:
    data_idx = value - 1
    if not lo <= data_idx <= hi:
        click.echo(f"{label} index must be {lo + 1}-{hi + 1}", err=True)
        sys.exit(1)
    return data_idx


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Serum 2 preset toolkit — inspect, edit, generate, and manage presets."""
    pass


# ── list ─────────────────────────────────────────────────────────────

@cli.command("list")
@click.argument("path", required=False)
@click.option("--category", "-c", help="Filter by subfolder name")
@click.option("--limit", "-n", type=int, default=50, help="Max results")
def list_presets(path, category, limit):
    """List Serum 2 presets."""
    root = Path(path) if path else get_preset_root()
    if root is None or not root.exists():
        click.echo("Serum 2 preset folder not found. Pass a path or install Serum 2.", err=True)
        sys.exit(1)

    pattern = f"**/{category}/**/*.SerumPreset" if category else "**/*.SerumPreset"
    presets = find_presets(root, pattern)

    if not presets:
        click.echo("No presets found.")
        return

    for p in presets[:limit]:
        rel = p.relative_to(root) if p.is_relative_to(root) else p
        click.echo(str(rel))

    if len(presets) > limit:
        click.echo(f"\n... and {len(presets) - limit} more (use --limit to see all)")

    click.echo(f"\n{len(presets)} presets total")


# ── inspect ──────────────────────────────────────────────────────────

@cli.command()
@click.argument("preset_path")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--full", is_flag=True, help="Full CBOR dump (verbose)")
def inspect(preset_path, as_json, full):
    """Show detailed info about a preset."""
    preset, _ = _load(preset_path)

    if full:
        click.echo(preset.export_full())
        return

    if as_json:
        click.echo(preset.to_json())
        return

    s = preset.summary()
    click.echo(f"Name:   {s['name']}")
    click.echo(f"Author: {s['author']}")
    if s["tags"]:
        click.echo(f"Tags:   {', '.join(s['tags'])}")

    click.echo(f"\nOscillators ({len(s['oscillators'])} active):")
    for o in s["oscillators"]:
        wt = o.get("wavetable", "")
        warp = o.get("warp_mode", "")
        uni = o.get("unison", "")
        parts = [f"  OSC {o['index'] + 1}"]
        if wt:
            parts.append(wt)
        if warp:
            parts.append(f"warp={warp}")
        if uni:
            parts.append(f"unison={int(uni)}")
        click.echo("  ".join(parts))

    f = s["filter"]
    if f:
        click.echo(f"\nFilter: {f.get('type', '?')}  freq={f.get('freq', '?')}  reso={f.get('reso', '?')}  drive={f.get('drive', '?')}")

    if s["macros"]:
        click.echo(f"\nMacros:")
        for k, m in s["macros"].items():
            idx = int(k.replace("macro", ""))
            click.echo(f"  {idx + 1}. {m['name']}  = {m['value']}")

    if s["lfos"]:
        click.echo(f"\nLFOs:")
        for k, l in s["lfos"].items():
            idx = int(k.replace("lfo", ""))
            parts = [f"  LFO {idx + 1}"]
            if l["rate"] is not None:
                parts.append(f"rate={l['rate']:.3f}")
            if l["mode"]:
                parts.append(f"mode={l['mode']}")
            if l["type"]:
                parts.append(f"type={l['type']}")
            click.echo("  ".join(parts))

    click.echo(f"\nFX chain ({len(s['fx'])}):")
    for f in s["fx"]:
        click.echo(f"  {f['type']}")

    click.echo(f"\nMod slots: {s['mod_count']} active")


# ── get ──────────────────────────────────────────────────────────────

@cli.command()
@click.argument("preset_path")
@click.argument("param")
def get(preset_path, param):
    """Get a parameter value. Supports aliases like filter.freq, osc0.warp, env0.sustain."""
    preset, _ = _load(preset_path)
    value = preset.get(param)
    if value is None:
        click.echo(f"Parameter not found: {param}", err=True)
        sys.exit(1)
    click.echo(json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value))


# ── set ──────────────────────────────────────────────────────────────

@cli.command("set")
@click.argument("preset_path")
@click.argument("param")
@click.argument("value")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def set_param(preset_path, param, value, output):
    """Set a parameter value. Supports aliases like filter.freq, osc0.warp, env0.sustain."""
    preset, resolved = _load(preset_path)
    preset.set(param, value)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Set {param} = {value} → {out.name}")


# ── bulk-set ─────────────────────────────────────────────────────────

@cli.command("bulk-set")
@click.argument("preset_path")
@click.option("-p", "--params", required=True, help='JSON object: {"param": value, ...}')
@click.option("-o", "--output", help="Output path (default: overwrite)")
def bulk_set(preset_path, params, output):
    """Set multiple parameters at once."""
    preset, resolved = _load(preset_path)
    try:
        param_dict = json.loads(params)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(1)

    for k, v in param_dict.items():
        preset.set(k, v)
        click.echo(f"  {k} = {v}")

    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Saved → {out.name}")


# ── clone ────────────────────────────────────────────────────────────

@cli.command()
@click.argument("preset_path")
@click.argument("new_name")
@click.option("-o", "--output", help="Output path (default: User folder)")
def clone(preset_path, new_name, output):
    """Clone a preset with a new name."""
    preset, resolved = _load(preset_path)
    new_preset = preset.clone()
    new_preset.name = new_name

    if output:
        out = Path(output)
    else:
        user_dir = get_user_folder()
        if user_dir is None:
            out = resolved.parent / f"{new_name}.SerumPreset"
        else:
            out = user_dir / f"{new_name}.SerumPreset"

    new_preset.save(out)
    click.echo(f"Cloned → {out}")


# ── mod ──────────────────────────────────────────────────────────────

@cli.group()
def mod():
    """Modulation matrix commands."""
    pass


@mod.command("list")
@click.argument("preset_path")
def mod_list(preset_path):
    """List active modulation slots."""
    preset, _ = _load(preset_path)
    mods = preset.list_mods()
    if not mods:
        click.echo("No active modulation slots.")
        return

    for m in mods:
        bipolar = " [bipolar]" if m["bipolar"] else ""
        click.echo(
            f"  Slot {m['slot']:2d}: {m['source']:>10s} → "
            f"{m['dest_type']}.{m['dest_param']}[{m['dest_module']}]  "
            f"amount={m['amount']:.1f}{bipolar}"
        )
    click.echo(f"\n{len(mods)} active slots")


@mod.command("add")
@click.argument("preset_path")
@click.argument("source")
@click.argument("dest")
@click.argument("amount", type=float)
@click.option("--bipolar", is_flag=True)
@click.option("-o", "--output", help="Output path (default: overwrite)")
def mod_add(preset_path, source, dest, amount, bipolar, output):
    """Add a modulation routing. Source: LFO0, Env0, Macro0, etc. Dest: filter.freq, osc0.warp, etc."""
    preset, resolved = _load(preset_path)
    try:
        slot = preset.add_mod(source, dest, amount, bipolar)
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Added mod slot {slot}: {source} → {dest} amount={amount}")


@mod.command("clear")
@click.argument("preset_path")
@click.option("--slot", type=int, help="Clear specific slot (default: all)")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def mod_clear(preset_path, slot, output):
    """Clear modulation slot(s)."""
    preset, resolved = _load(preset_path)
    if slot is not None:
        preset.clear_mod(slot)
        click.echo(f"Cleared slot {slot}")
    else:
        preset.clear_all_mods()
        click.echo("Cleared all mod slots")

    out = _output_path(resolved, output)
    preset.save(out)


# ── fx ───────────────────────────────────────────────────────────────

@cli.group()
def fx():
    """FX chain commands."""
    pass


@fx.command("list")
@click.argument("preset_path")
def fx_list(preset_path):
    """List FX chain."""
    preset, _ = _load(preset_path)
    chain = preset.fx_chain()
    if not chain:
        click.echo("Empty FX chain.")
        return
    for f in chain:
        params_str = ", ".join(f"{k}={v}" for k, v in list(f["params"].items())[:4]) if f["params"] else ""
        click.echo(f"  [{f['index']}] {f['type']}  {params_str}")


@fx.command("add")
@click.argument("preset_path")
@click.argument("fx_type")
@click.option("-p", "--params", help='FX params as JSON: {"kParamDrive": 50}')
@click.option("-o", "--output", help="Output path")
def fx_add(preset_path, fx_type, params, output):
    """Add an FX module."""
    preset, resolved = _load(preset_path)

    fx_params = {}
    if params:
        try:
            fx_params = json.loads(params)
        except json.JSONDecodeError as e:
            click.echo(f"Invalid JSON: {e}", err=True)
            sys.exit(1)

    try:
        idx = preset.add_fx(fx_type, fx_params)
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Added {fx_type} at index {idx}")


@fx.command("remove")
@click.argument("preset_path")
@click.argument("index", type=int)
@click.option("-o", "--output", help="Output path")
def fx_remove(preset_path, index, output):
    """Remove an FX by index."""
    preset, resolved = _load(preset_path)
    preset.remove_fx(index)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Removed FX at index {index}")


# ── macro ────────────────────────────────────────────────────────────

@cli.group()
def macro():
    """Macro commands."""
    pass


@macro.command("list")
@click.argument("preset_path")
def macro_list(preset_path):
    """List all macros."""
    preset, _ = _load(preset_path)
    for i in range(8):
        m = preset.get_macro(i)
        status = f"{m['name']:>12s}  = {m['value']:.1f}" if m["name"] else "(unused)"
        click.echo(f"  Macro {i + 1}: {status}")


@macro.command("set")
@click.argument("preset_path")
@click.argument("index", type=int)
@click.option("--name", "-n", help="Macro name")
@click.option("--value", "-v", type=float, help="Macro value (0-100)")
@click.option("-o", "--output", help="Output path")
def macro_set(preset_path, index, name, value, output):
    """Set a macro's name and/or value. Index is 1-8 (UI numbering)."""
    preset, resolved = _load(preset_path)
    data_idx = _validate_index(index, "Macro", 0, 7)
    preset.set_macro(data_idx, name=name, value=value)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Macro {index} updated")


# ── envelope ─────────────────────────────────────────────────────────

@cli.group()
def env():
    """Envelope commands."""
    pass


@env.command("list")
@click.argument("preset_path")
def env_list(preset_path):
    """Show envelope ADSR values."""
    preset, _ = _load(preset_path)
    for i in range(4):
        e = preset.get_envelope(i)
        if any(v is not None for v in e.values()):
            click.echo(
                f"  ENV {i + 1}: A={e['attack']}  D={e['decay']}  S={e['sustain']}  R={e['release']}"
            )


@env.command("set")
@click.argument("preset_path")
@click.argument("index", type=int)
@click.option("-a", "--attack", type=float)
@click.option("-d", "--decay", type=float)
@click.option("-s", "--sustain", type=float)
@click.option("-r", "--release", type=float)
@click.option("-o", "--output", help="Output path")
def env_set(preset_path, index, attack, decay, sustain, release, output):
    """Set envelope ADSR. Index is 1-4 (UI numbering)."""
    preset, resolved = _load(preset_path)
    data_idx = _validate_index(index, "Envelope", 0, 3)
    preset.set_envelope(data_idx, attack=attack, decay=decay, sustain=sustain, release=release)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"ENV {index} updated")


# ── lfo ──────────────────────────────────────────────────────────────

@cli.group()
def lfo():
    """LFO commands."""
    pass


@lfo.command("list")
@click.argument("preset_path")
def lfo_list(preset_path):
    """Show active LFOs."""
    preset, _ = _load(preset_path)
    for i in range(10):
        l = preset.get_lfo(i)
        if l["rate"] is not None:
            parts = [f"  LFO {i + 1}: rate={l['rate']:.3f}"]
            if l["mode"]:
                parts.append(f"mode={l['mode']}")
            if l["type"]:
                parts.append(f"type={l['type']}")
            click.echo("  ".join(parts))


@lfo.command("set")
@click.argument("preset_path")
@click.argument("index", type=int)
@click.option("--rate", type=float)
@click.option("--mode", type=click.Choice(LFO_MODES))
@click.option("--type", "lfo_type", type=click.Choice(LFO_TYPES))
@click.option("--smooth", type=float)
@click.option("-o", "--output", help="Output path")
def lfo_set(preset_path, index, rate, mode, lfo_type, smooth, output):
    """Set LFO parameters. Index is 1-10 (UI numbering)."""
    preset, resolved = _load(preset_path)
    data_idx = _validate_index(index, "LFO", 0, 9)
    kwargs = {}
    if rate is not None:
        kwargs["rate"] = rate
    if mode is not None:
        kwargs["mode"] = mode
    if lfo_type is not None:
        kwargs["type"] = lfo_type
    if smooth is not None:
        kwargs["smooth"] = smooth

    preset.set_lfo(data_idx, **kwargs)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"LFO {index} updated")


# ── generate ─────────────────────────────────────────────────────────

@cli.command()
@click.argument("template")
@click.option("-n", "--count", type=int, default=10, help="Number of variations")
@click.option("-i", "--intensity", type=float, default=0.5, help="Variation intensity (0.0-1.0)")
@click.option("-p", "--prefix", default="GEN", help="Preset name prefix")
@click.option("-s", "--seed", type=int, help="Random seed")
@click.option("-o", "--output", help="Output directory (default: User folder)")
def generate(template, count, intensity, prefix, seed, output):
    """Generate preset variations from a template."""
    resolved = resolve_preset(template)
    if resolved is None:
        click.echo(f"Template not found: {template}", err=True)
        sys.exit(1)

    if output:
        out_dir = Path(output)
    else:
        out_dir = get_user_folder()
        if out_dir is None:
            out_dir = Path("./output")

    click.echo(f"Generating {count} variations from: {resolved.name}")
    click.echo(f"Intensity: {intensity}, Seed: {seed or 'random'}")
    click.echo(f"Output: {out_dir}")

    generated = batch_generate(
        resolved,
        out_dir,
        count=count,
        intensity=intensity,
        name_prefix=prefix,
        base_seed=seed,
    )

    click.echo(f"\nGenerated {len(generated)} presets:")
    for p in generated[:5]:
        click.echo(f"  {p.name}")
    if len(generated) > 5:
        click.echo(f"  ... and {len(generated) - 5} more")


# ── export / import ──────────────────────────────────────────────────

@cli.command("export")
@click.argument("preset_path")
@click.option("--full", is_flag=True, help="Export full CBOR data (not just summary)")
@click.option("-o", "--output", help="Output JSON file (default: stdout)")
def export_preset(preset_path, full, output):
    """Export preset to JSON."""
    preset, _ = _load(preset_path)
    data = preset.export_full() if full else preset.to_json()

    if output:
        Path(output).write_text(data)
        click.echo(f"Exported → {output}")
    else:
        click.echo(data)


@cli.command("import")
@click.argument("json_path")
@click.option("-o", "--output", required=True, help="Output .SerumPreset path")
def import_preset(json_path, output):
    """Import preset from a full JSON export."""
    raw = json.loads(Path(json_path).read_text())
    if "header" not in raw or "params" not in raw or "_meta" not in raw:
        click.echo("JSON must contain header, params, and _meta keys (use --full export)", err=True)
        sys.exit(1)

    preset = Preset(raw)
    preset.save(output)
    click.echo(f"Imported → {output}")


# ── diff ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("preset_a")
@click.argument("preset_b")
def diff(preset_a, preset_b):
    """Compare two presets."""
    a, _ = _load(preset_a)
    b, _ = _load(preset_b)
    sa = a.summary()
    sb = b.summary()

    click.echo(f"A: {sa['name']}")
    click.echo(f"B: {sb['name']}")
    click.echo()

    _diff_section("filter", sa.get("filter", {}), sb.get("filter", {}))
    _diff_section("macros", sa.get("macros", {}), sb.get("macros", {}))

    if sa.get("mod_count") != sb.get("mod_count"):
        click.echo(f"  mod_count: {sa.get('mod_count')} → {sb.get('mod_count')}")

    fx_a = [f["type"] for f in sa.get("fx", [])]
    fx_b = [f["type"] for f in sb.get("fx", [])]
    if fx_a != fx_b:
        click.echo(f"  fx chain: {fx_a} → {fx_b}")


def _diff_section(name, a, b):
    if a == b:
        return
    click.echo(f"  {name}:")
    all_keys = (a.keys() | b.keys()) if isinstance(a, dict) and isinstance(b, dict) else set()
    for k in sorted(all_keys):
        va = a.get(k) if isinstance(a, dict) else None
        vb = b.get(k) if isinstance(b, dict) else None
        if va != vb:
            click.echo(f"    {k}: {va} → {vb}")


# ── search ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--path", "-p", help="Search root (default: Serum 2 folder)")
@click.option("--filter-type", "-f", help="Filter by voice filter type")
@click.option("--has-fx", help="Filter by FX type present")
@click.option("--author", "-a", help="Filter by author")
@click.option("--limit", "-n", type=int, default=20)
def search(query, path, filter_type, has_fx, author, limit):
    """Search presets by name, author, filter type, or FX."""
    root = Path(path) if path else get_preset_root()
    if root is None:
        click.echo("Serum 2 preset folder not found.", err=True)
        sys.exit(1)

    needs_parse = bool(author or filter_type or has_fx)
    results = []
    query_lower = query.lower()
    for preset_path in find_presets(root):
        if query_lower not in preset_path.stem.lower():
            continue

        p = None
        if needs_parse:
            try:
                p = Preset.load(preset_path)
            except Exception:
                continue

            if author and author.lower() not in p.author.lower():
                continue
            if filter_type:
                ft = p.get("filter.type")
                if ft and filter_type.lower() not in str(ft).lower():
                    continue
            if has_fx:
                fx_types = [f["type"] for f in p.fx_chain()]
                if not any(has_fx.lower() in ft.lower() for ft in fx_types):
                    continue

        rel = preset_path.relative_to(root) if preset_path.is_relative_to(root) else preset_path
        results.append((rel, p))
        if len(results) >= limit:
            break

    if not results:
        click.echo("No matches.")
        return

    for rel, p in results:
        author_str = f"  [{p.author}]" if p and p.author else ""
        click.echo(f"  {rel}{author_str}")
    click.echo(f"\n{len(results)} results")


# ── enums ────────────────────────────────────────────────────────────

@cli.command("enums")
@click.argument("category", required=False)
def show_enums(category):
    """Show valid enum values for parameters. Categories: warp, filter, fxfilter, distortion, lfo, fx, sources, destinations, aliases, header."""
    cats = {
        "warp": ("Warp Modes", WARP_MODES),
        "filter": ("Voice Filter Types", VOICE_FILTER_TYPES),
        "fxfilter": ("FX Filter Types", FX_FILTER_TYPES),
        "distortion": ("Distortion Modes", DISTORTION_MODES),
        "lfo": ("LFO Types", LFO_TYPES),
        "fx": ("FX Types", list(FX_TYPE_IDS.keys())),
        "sources": ("Mod Sources", list(SOURCE_NAMES.keys())),
        "destinations": ("Mod Destinations (shortnames)", list(DEST_SHORTNAMES.keys())),
        "aliases": ("Parameter Aliases", sorted(PARAM_ALIASES.keys())),
        "header": ("Header Fields", list(HEADER_ALIASES.keys())),
    }

    if category and category.lower() in cats:
        title, values = cats[category.lower()]
        click.echo(f"{title}:")
        for v in values:
            click.echo(f"  {v}")
    else:
        click.echo("Available enum categories:")
        for k, (title, values) in cats.items():
            click.echo(f"  {k:14s} — {title} ({len(values)} values)")
        if not category:
            click.echo("\nUsage: serum2 enums <category>")


# ── rename ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("preset_path")
@click.argument("new_name")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def rename(preset_path, new_name, output):
    """Rename a preset."""
    preset, resolved = _load(preset_path)
    preset.name = new_name
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"Renamed → {new_name}")


# ── wt (wavetable) ──────────────────────────────────────────────────

@cli.group()
def wt():
    """Wavetable management commands."""
    pass


@wt.command("list")
@click.option("--category", "-c", help="Filter by subfolder (e.g. Analog)")
def wt_list(category):
    """List available wavetables."""
    tables = find_wavetables(category=category)
    if not tables:
        click.echo("No wavetables found. Is Serum 2 installed?", err=True)
        sys.exit(1)
    for t in tables:
        click.echo(t)
    click.echo(f"\n{len(tables)} wavetables")


@wt.command("get")
@click.argument("preset_path")
@click.argument("osc", type=int)
def wt_get(preset_path, osc):
    """Show wavetable for an oscillator. OSC is 1-5 (UI numbering)."""
    preset, _ = _load(preset_path)
    data_idx = _validate_index(osc, "Oscillator", 0, 4)
    wt_path = preset.get_wavetable(data_idx)
    if wt_path is None:
        click.echo(f"OSC {osc}: no wavetable assigned")
    else:
        click.echo(f"OSC {osc}: {wt_path}")


@wt.command("set")
@click.argument("preset_path")
@click.argument("osc", type=int)
@click.argument("table")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def wt_set(preset_path, osc, table, output):
    """Assign a wavetable to an oscillator. OSC is 1-5 (UI numbering)."""
    preset, resolved = _load(preset_path)
    data_idx = _validate_index(osc, "Oscillator", 0, 4)
    preset.set_wavetable(data_idx, table)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"OSC {osc} wavetable set to {table}")


# ── noise ───────────────────────────────────────────────────────────

@cli.group()
def noise():
    """Noise sample management commands."""
    pass


@noise.command("list")
@click.option("--category", "-c", help="Filter by subfolder (e.g. Analog)")
def noise_list(category):
    """List available noise samples."""
    samples = find_noise_samples(category=category)
    if not samples:
        click.echo("No noise samples found. Is Serum 2 installed?", err=True)
        sys.exit(1)
    for s in samples:
        click.echo(s)
    click.echo(f"\n{len(samples)} noise samples")


@noise.command("get")
@click.argument("preset_path")
@click.argument("osc", type=int)
def noise_get(preset_path, osc):
    """Show noise sample for an oscillator. OSC is 1-5 (UI numbering)."""
    preset, _ = _load(preset_path)
    data_idx = _validate_index(osc, "Oscillator", 0, 4)
    noise_path = preset.get_noise(data_idx)
    if noise_path is None:
        click.echo(f"OSC {osc}: no noise sample assigned")
    else:
        click.echo(f"OSC {osc}: {noise_path}")


@noise.command("set")
@click.argument("preset_path")
@click.argument("osc", type=int)
@click.argument("sample")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def noise_set(preset_path, osc, sample, output):
    """Assign a noise sample to an oscillator. OSC is 1-5 (UI numbering)."""
    preset, resolved = _load(preset_path)
    data_idx = _validate_index(osc, "Oscillator", 0, 4)
    preset.set_noise(data_idx, sample)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo(f"OSC {osc} noise sample set to {sample}")


# ── arp ─────────────────────────────────────────────────────────────

@cli.group()
def arp():
    """Arpeggiator commands."""
    pass


@arp.command("get")
@click.argument("preset_path")
def arp_get(preset_path):
    """Show arpeggiator state."""
    preset, _ = _load(preset_path)
    a = preset.get_arp()
    click.echo(f"Enabled:          {a['enabled']}")
    click.echo(f"Clip ID:          {a['clip_id']}")
    click.echo(f"Key Zone Max:     {a['key_zone_max']}")
    click.echo(f"Launch Quantize:  {a['launch_quantize']}")


@arp.command("set")
@click.argument("preset_path")
@click.option("--enable/--disable", default=None, help="Enable or disable arp")
@click.option("--clip", type=float, help="Active clip ID")
@click.option("-o", "--output", help="Output path (default: overwrite)")
def arp_set(preset_path, enable, clip, output):
    """Set arpeggiator parameters."""
    preset, resolved = _load(preset_path)
    kwargs = {}
    if enable is not None:
        kwargs["enabled"] = enable
    if clip is not None:
        kwargs["clip_id"] = clip
    preset.set_arp(**kwargs)
    out = _output_path(resolved, output)
    preset.save(out)
    click.echo("Arp updated")


@arp.command("patterns")
def arp_patterns():
    """List available arp patterns (.XferArp files)."""
    patterns = find_arp_patterns()
    if not patterns:
        click.echo("No arp patterns found. Is Serum 2 installed?", err=True)
        sys.exit(1)
    for p in patterns:
        click.echo(p)
    click.echo(f"\n{len(patterns)} arp patterns")


@arp.command("clips")
def arp_clips():
    """List available clips (.XferClip files)."""
    clips = find_clips()
    if not clips:
        click.echo("No clips found. Is Serum 2 installed?", err=True)
        sys.exit(1)
    for c in clips:
        click.echo(c)
    click.echo(f"\n{len(clips)} clips")


# ── ml (VAE-based generation) ──────────────────────────────────────

def _require_ml():
    """Check that ML dependencies are available and import the ml module."""
    try:
        import torch  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        click.echo(
            "ML features require PyTorch and NumPy.\n"
            "Install with: pip install serum2[ml]",
            err=True,
        )
        sys.exit(1)
    from . import ml
    return ml


@cli.group()
def ml():
    """ML/VAE commands — train, generate, interpolate, find similar."""
    pass


@ml.command("train")
@click.argument("presets_dir", required=False)
@click.option("--epochs", type=int, default=100, help="Training epochs")
@click.option("--latent-dim", type=int, default=32, help="Latent space dimensions")
@click.option("--hidden-dim", type=int, default=128, help="Hidden layer width")
@click.option("--lr", type=float, default=1e-3, help="Learning rate")
@click.option("--batch-size", type=int, default=32, help="Batch size")
@click.option("-o", "--output", default="serum2_vae.pt", help="Output model file")
def ml_train(presets_dir, epochs, latent_dim, hidden_dim, lr, batch_size, output):
    """Train a VAE on presets. Defaults to factory preset folder."""
    ml_mod = _require_ml()

    if presets_dir:
        root = Path(presets_dir)
    else:
        root = get_preset_root()
        if root is None:
            click.echo("Serum 2 preset folder not found. Pass a path.", err=True)
            sys.exit(1)

    click.echo(f"Training VAE on presets in: {root}")
    click.echo(f"  epochs={epochs}, latent_dim={latent_dim}, hidden_dim={hidden_dim}")

    try:
        model, metadata = ml_mod.train_vae(
            root,
            epochs=epochs,
            latent_dim=latent_dim,
            hidden_dim=hidden_dim,
            lr=lr,
            batch_size=batch_size,
        )
    except (FileNotFoundError, RuntimeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    ml_mod.save_model(model, metadata, output)
    click.echo(f"\nModel saved to: {output}")
    click.echo(f"Trained on {metadata['n_training_samples']} presets, {metadata['input_dim']} features")


@ml.command("generate")
@click.argument("model_path")
@click.option("-n", "--count", type=int, default=10, help="Number of presets to generate")
@click.option("--template", help="Template preset for structure (default: first factory preset)")
@click.option("-o", "--output", default="./vae_output", help="Output directory")
def ml_generate(model_path, count, template, output):
    """Generate presets by sampling the VAE latent space."""
    ml_mod = _require_ml()

    try:
        model, metadata = ml_mod.load_model(model_path)
    except Exception as e:
        click.echo(f"Error loading model: {e}", err=True)
        sys.exit(1)

    template_preset = None
    if template:
        resolved = resolve_preset(template)
        if resolved is None:
            click.echo(f"Template preset not found: {template}", err=True)
            sys.exit(1)
        template_preset = Preset.load(resolved)
    else:
        root = get_preset_root()
        first = next(root.glob("**/*.SerumPreset"), None) if root else None
        if first is None:
            click.echo("No factory presets found. Pass --template.", err=True)
            sys.exit(1)
        template_preset = Preset.load(first)

    click.echo(f"Generating {count} presets from model: {model_path}")

    presets = ml_mod.sample(model, metadata, n=count, template=template_preset)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, p in enumerate(presets):
        filepath = out_dir / f"VAE Sample {i:03d}.SerumPreset"
        p.save(filepath)

    click.echo(f"\nGenerated {len(presets)} presets in: {out_dir}")
    for p in presets[:5]:
        click.echo(f"  {p.name}")
    if len(presets) > 5:
        click.echo(f"  ... and {len(presets) - 5} more")


@ml.command("interpolate")
@click.argument("model_path")
@click.argument("preset_a")
@click.argument("preset_b")
@click.option("--steps", type=int, default=10, help="Number of interpolation steps")
@click.option("-o", "--output", default="./vae_interp", help="Output directory")
def ml_interpolate(model_path, preset_a, preset_b, steps, output):
    """Interpolate between two presets in VAE latent space."""
    ml_mod = _require_ml()

    try:
        model, metadata = ml_mod.load_model(model_path)
    except Exception as e:
        click.echo(f"Error loading model: {e}", err=True)
        sys.exit(1)

    resolved_a = resolve_preset(preset_a)
    resolved_b = resolve_preset(preset_b)
    if resolved_a is None:
        click.echo(f"Preset A not found: {preset_a}", err=True)
        sys.exit(1)
    if resolved_b is None:
        click.echo(f"Preset B not found: {preset_b}", err=True)
        sys.exit(1)

    pa = Preset.load(resolved_a)
    pb = Preset.load(resolved_b)

    click.echo(f"Interpolating: {pa.name} → {pb.name} ({steps} steps)")

    presets = ml_mod.interpolate(model, metadata, pa, pb, steps=steps)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, p in enumerate(presets):
        filepath = out_dir / f"Interp {i:03d}.SerumPreset"
        p.save(filepath)

    click.echo(f"\nGenerated {len(presets)} interpolation steps in: {out_dir}")


@ml.command("similar")
@click.argument("model_path")
@click.argument("preset_path")
@click.option("-n", "--count", type=int, default=5, help="Number of similar presets to find")
@click.option("--search-dir", help="Directory to search (default: factory presets)")
def ml_similar(model_path, preset_path, count, search_dir):
    """Find the most similar presets by latent distance."""
    ml_mod = _require_ml()

    try:
        model, metadata = ml_mod.load_model(model_path)
    except Exception as e:
        click.echo(f"Error loading model: {e}", err=True)
        sys.exit(1)

    resolved = resolve_preset(preset_path)
    if resolved is None:
        click.echo(f"Preset not found: {preset_path}", err=True)
        sys.exit(1)

    target = Preset.load(resolved)
    click.echo(f"Finding {count} presets similar to: {target.name}")

    if search_dir:
        search_root = Path(search_dir)
    else:
        search_root = get_preset_root()
        if search_root is None:
            click.echo("Serum 2 preset folder not found. Pass --search-dir.", err=True)
            sys.exit(1)

    all_paths = find_presets(search_root)
    if not all_paths:
        click.echo("No presets found to search.", err=True)
        sys.exit(1)

    all_presets = []
    for p in all_paths:
        try:
            all_presets.append(Preset.load(p))
        except Exception:
            continue

    results = ml_mod.find_similar(model, metadata, target, all_presets, n=count)

    click.echo(f"\nMost similar presets:")
    for preset, dist in results:
        click.echo(f"  {preset.name:40s}  distance={dist:.4f}")


if __name__ == "__main__":
    cli()
