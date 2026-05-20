"""Low-level Serum 2 .SerumPreset binary parser and writer."""

import json
import struct
import copy
from pathlib import Path

import cbor2
import zstandard


def parse_preset(filepath: str | Path) -> dict:
    data = Path(filepath).read_bytes()

    magic = data[:8]
    if magic != b"XferJson":
        raise ValueError(f"Not a Serum 2 preset: bad magic {magic!r}")

    json_start = data.find(b"{")
    depth = 0
    json_end = 0
    for i in range(json_start, len(data)):
        if data[i:i+1] == b"{":
            depth += 1
        elif data[i:i+1] == b"}":
            depth -= 1
        if depth == 0:
            json_end = i + 1
            break

    header = json.loads(data[json_start:json_end])
    after_json = data[json_end:]

    pre_header = after_json[:8]
    decompressed_size = struct.unpack("<I", pre_header[:4])[0]
    section_flags = struct.unpack("<I", pre_header[4:8])[0]

    zstd_offset = after_json.find(b"\x28\xb5\x2f\xfd")
    if zstd_offset < 0:
        raise ValueError("No Zstandard payload found")

    zstd_data = after_json[zstd_offset:]
    dctx = zstandard.ZstdDecompressor()
    decompressed = dctx.decompress(zstd_data, max_output_size=10_000_000)

    params = cbor2.loads(decompressed)

    return {
        "header": header,
        "params": params,
        "_meta": {
            "decompressed_size": decompressed_size,
            "section_flags": section_flags,
        },
    }


def write_preset(preset: dict, filepath: str | Path) -> None:
    header_json = json.dumps(preset["header"], separators=(",", ":"))
    json_bytes = header_json.encode("utf-8")
    cbor_payload = cbor2.dumps(preset["params"])

    cctx = zstandard.ZstdCompressor(level=3)
    compressed = cctx.compress(cbor_payload)

    size_header = struct.pack("<I", len(cbor_payload))
    flags_header = struct.pack("<I", preset["_meta"]["section_flags"])

    out = bytearray()
    out.extend(b"XferJson")
    out.extend(b"\x00")
    out.extend(struct.pack("<H", len(json_bytes)))
    out.extend(b"\x00" * 6)
    out.extend(json_bytes)
    out.extend(size_header)
    out.extend(flags_header)
    out.extend(compressed)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_bytes(bytes(out))


def deep_clone(preset: dict) -> dict:
    return {
        "header": copy.deepcopy(preset["header"]),
        "params": copy.deepcopy(preset["params"]),
        "_meta": copy.deepcopy(preset["_meta"]),
    }
