#!/usr/bin/env python3
"""Rebuild and decode Dead or Alive Model 2 ROM data from MAME ZIPs.

The tool intentionally contains no copyrighted game data.  It resolves source
chips by CRC32, reproduces the relevant MAME load transformations, and can
decode the validated COMACT/conditional/ordered AI table families.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CHARACTERS = {
    0: "Zack",
    1: "Tina",
    2: "JannLee",
    4: "Hayabusa",
    5: "Kasumi",
    6: "GenFu",
    8: "Bayman",
    11: "Raidou",
    12: "Leifang",
}

# The group counts are structural facts shared by the five supplied builds.
# Requiring the exact shape makes automatic root detection conservative.
COMACT_GROUP_COUNTS = {
    0: 7,
    1: 18,
    2: 14,
    4: 18,
    5: 31,
    6: 23,
    8: 9,
    11: 21,
    12: 8,
}

STATIC_PROGRAM_LIMIT = 0x100000
CONDITIONAL_ROOT_DELTA = 0x17E0
ORDER_ACTION_ROOT_DELTA = 0x2090


@dataclass(frozen=True)
class SourceRef:
    archive: Path
    member: str
    crc32: int
    size: int


class ExtractionError(RuntimeError):
    pass


class RomIndex:
    """Checksum-indexed view of every ZIP in a ROM directory."""

    def __init__(self, rom_dir: Path):
        self.rom_dir = rom_dir
        self.by_crc_size: dict[tuple[int, int], list[SourceRef]] = {}
        archives = sorted(rom_dir.glob("*.zip"))
        if not archives:
            raise ExtractionError(f"no ZIP files found in {rom_dir}")

        for archive in archives:
            try:
                with zipfile.ZipFile(archive) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        ref = SourceRef(archive, info.filename, info.CRC, info.file_size)
                        self.by_crc_size.setdefault((info.CRC, info.file_size), []).append(ref)
            except zipfile.BadZipFile as exc:
                raise ExtractionError(f"invalid ZIP archive: {archive}") from exc

    def resolve(self, spec: dict[str, Any]) -> SourceRef:
        crc = int(spec["crc32"], 16)
        size = int(spec["size"])
        matches = self.by_crc_size.get((crc, size), [])
        if not matches:
            raise ExtractionError(
                f"missing {spec['chip']} (CRC {crc:08x}, {size:#x} bytes); "
                "clone sets require their parent/shared ZIPs in the same directory"
            )
        return matches[0]

    def read(self, spec: dict[str, Any]) -> tuple[bytes, SourceRef]:
        ref = self.resolve(spec)
        with zipfile.ZipFile(ref.archive) as zf:
            data = zf.read(ref.member)  # zipfile verifies the member CRC while reading
        actual = zlib.crc32(data) & 0xFFFFFFFF
        if len(data) != ref.size or actual != ref.crc32:
            raise ExtractionError(
                f"checksum failure for {ref.archive.name}:{ref.member}: "
                f"expected {ref.crc32:08x}/{ref.size:#x}, got {actual:08x}/{len(data):#x}"
            )
        return data, ref


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"cannot load configuration {path}: {exc}") from exc
    if config.get("schema") != 1:
        raise ExtractionError(f"unsupported configuration schema in {path}")
    return config


def place_load32_word(region: bytearray, source: bytes, offset: int) -> None:
    """Implement MAME ROM_LOAD32_WORD: two-byte words on one 32-bit lane."""
    if len(source) == 0 or len(source) % 2:
        raise ExtractionError("ROM_LOAD32_WORD source must contain complete 16-bit words")
    end = offset + (len(source) // 2 - 1) * 4 + 2
    if end > len(region):
        raise ExtractionError("ROM_LOAD32_WORD exceeds destination region")
    region[offset:end:4] = source[0::2]
    region[offset + 1:end:4] = source[1::2]


def place_load16_word_swap(region: bytearray, source: bytes, offset: int) -> None:
    """Implement MAME ROM_LOAD16_WORD_SWAP."""
    end = offset + len(source)
    if end > len(region):
        raise ExtractionError("ROM_LOAD16_WORD_SWAP exceeds destination region")
    region[offset:end:2] = source[1::2]
    region[offset + 1:end:2] = source[0::2]


def source_manifest_entry(spec: dict[str, Any], ref: SourceRef) -> dict[str, Any]:
    return {
        "logical_chip": spec["chip"],
        "crc32": f"{ref.crc32:08x}",
        "size": ref.size,
        "archive": ref.archive.name,
        "member": ref.member,
    }


def build_maincpu(
    set_name: str, config: dict[str, Any], roms: RomIndex
) -> tuple[bytes, list[dict[str, Any]]]:
    specs = config["sets"][set_name]["maincpu"]
    # Two 0x80000 chips create the actual 0x100000-byte program image.  MAME
    # allocates a 0x200000 region, but its unused upper half is not emitted.
    output_size = max(
        int(spec["offset"]) + (int(spec["size"]) // 2 - 1) * 4 + 2
        for spec in specs
    )
    region = bytearray(output_size)
    sources = []
    for spec in specs:
        data, ref = roms.read(spec)
        place_load32_word(region, data, int(spec["offset"]))
        sources.append(source_manifest_entry(spec, ref))
    return bytes(region), sources


def build_shared_region(
    name: str, spec: dict[str, Any], roms: RomIndex
) -> tuple[bytes, list[dict[str, Any]]]:
    region = bytearray([int(spec.get("fill", 0))]) * int(spec["size"])
    sources = []
    for load in spec["loads"]:
        data, ref = roms.read(load)
        mode = load["mode"]
        if mode == "load32_word":
            place_load32_word(region, data, int(load["offset"]))
        elif mode == "load16_word_swap":
            place_load16_word_swap(region, data, int(load["offset"]))
        else:
            raise ExtractionError(f"unsupported load mode {mode!r} in {name}")
        sources.append(source_manifest_entry(load, ref))

    for copy in spec.get("copies", []):
        source = int(copy["source"])
        destination = int(copy["destination"])
        length = int(copy["length"])
        if source + length > len(region) or destination + length > len(region):
            raise ExtractionError(f"ROM_COPY exceeds {name} region")
        region[destination:destination + length] = region[source:source + length]
    return bytes(region), sources


def write_binary(path: Path, data: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "file": path.name,
        "size": len(data),
        "sha256": sha256_bytes(data),
    }


def u32(data: bytes, address: int) -> int:
    if address < 0 or address + 4 > len(data):
        raise ExtractionError(f"32-bit read outside program at {address:#x}")
    return struct.unpack_from("<I", data, address)[0]


def is_program_pointer(value: int) -> bool:
    return 0 < value < STATIC_PROGRAM_LIMIT and value % 4 == 0


def try_comact_group(data: bytes, address: int) -> list[dict[str, int]] | None:
    if not is_program_pointer(address):
        return None
    records = []
    for index in range(256):
        record_address = address + index * 4
        if record_address + 4 > min(len(data), STATIC_PROGRAM_LIMIT):
            return None
        per, actreq, para, lvl = struct.unpack_from("<BBBB", data, record_address)
        records.append({
            "address": record_address,
            "per": per,
            "actreq": actreq,
            "para": para,
            "lvl": lvl,
        })
        if per == 0xFF:
            return records
        if not 1 <= per <= 27:
            return None
    return None


def is_comact_root(data: bytes, root: int) -> bool:
    if root + 15 * 4 > min(len(data), STATIC_PROGRAM_LIMIT):
        return False
    for slot, count in COMACT_GROUP_COUNTS.items():
        table = u32(data, root + slot * 4)
        if not is_program_pointer(table):
            return False
        for group_index in range(count):
            group = u32(data, table + group_index * 4)
            if try_comact_group(data, group) is None:
                return False
        # Requiring an exact boundary eliminates false-positive pointer forests.
        following = u32(data, table + count * 4)
        if try_comact_group(data, following) is not None:
            return False
    return True


def find_comact_root(data: bytes) -> int:
    matches = [
        address
        for address in range(0, min(len(data), STATIC_PROGRAM_LIMIT) - 15 * 4, 4)
        if is_comact_root(data, address)
    ]
    if len(matches) != 1:
        rendered = ", ".join(f"{x:#x}" for x in matches) or "none"
        raise ExtractionError(f"expected one COMACT character root, found {rendered}")
    return matches[0]


def pointer_list(data: bytes, table: int, limit: int = 64) -> list[int]:
    result = []
    for index in range(limit):
        address = table + index * 4
        if address + 4 > min(len(data), STATIC_PROGRAM_LIMIT):
            break
        value = u32(data, address)
        if not is_program_pointer(value):
            break
        result.append(value)
    return result


def backward_pointer_list(data: bytes, table: int, root: int, limit: int = 32) -> list[int]:
    result = []
    for index in range(limit):
        address = table + index * 4
        if address >= root:
            break
        value = u32(data, address)
        if not is_program_pointer(value) or value >= table:
            break
        result.append(value)
    return result


def decode_conditional_table(data: bytes, address: int) -> list[dict[str, int]]:
    records = []
    for index in range(256):
        current = address + index * 8
        if current + 8 > min(len(data), STATIC_PROGRAM_LIMIT):
            raise ExtractionError(f"conditional table runs outside program at {address:#x}")
        weight, set_num, check_condition, adjustment, reserved = struct.unpack_from(
            "<HBBHH", data, current
        )
        records.append({
            "address": current,
            "weight": weight,
            "set_num": set_num,
            "check_condition": check_condition,
            "weight_adjustment": adjustment,
            "reserved": reserved,
        })
        if set_num == 0xFF:
            return records
    raise ExtractionError(f"unterminated conditional table at {address:#x}")


def decode_order_table(data: bytes, address: int) -> list[dict[str, int]]:
    records = []
    for index in range(256):
        current = address + index * 8
        if current + 8 > min(len(data), STATIC_PROGRAM_LIMIT):
            raise ExtractionError(f"ordered-action table runs outside program at {address:#x}")
        opcode, set_num, check_condition, unknown_04, unknown_06 = struct.unpack_from(
            "<hBBHH", data, current
        )
        records.append({
            "address": current,
            "repeat_count_or_opcode": opcode,
            "set_num": set_num,
            "check_condition": check_condition,
            "unknown_04": unknown_04,
            "unknown_06": unknown_06,
        })
        if opcode == -1:
            return records
    raise ExtractionError(f"unterminated ordered-action table at {address:#x}")


def hex_addresses(value: Any) -> Any:
    """Recursively render fields named address/table/root as readable hex."""
    if isinstance(value, list):
        return [hex_addresses(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if isinstance(item, int) and (key == "address" or key.endswith("_root") or key == "table"):
                result[key] = f"0x{item:08X}"
            else:
                result[key] = hex_addresses(item)
        return result
    return value


def decode_ai_tables(data: bytes, set_name: str) -> dict[str, Any]:
    comact_root = find_comact_root(data)
    conditional_root = comact_root + CONDITIONAL_ROOT_DELTA
    order_root = comact_root + ORDER_ACTION_ROOT_DELTA

    characters = []
    comact_total = conditional_total = order_total = 0
    comact_record_total = conditional_record_total = order_record_total = 0

    for slot, name in CHARACTERS.items():
        comact_table = u32(data, comact_root + slot * 4)
        conditional_table = u32(data, conditional_root + slot * 4)
        order_table = u32(data, order_root + slot * 4)
        if not all(is_program_pointer(x) for x in (comact_table, conditional_table, order_table)):
            raise ExtractionError(f"invalid AI family pointer for {name}")

        comact_groups = []
        for group_index in range(COMACT_GROUP_COUNTS[slot]):
            group_address = u32(data, comact_table + group_index * 4)
            records = try_comact_group(data, group_address)
            if records is None:
                raise ExtractionError(f"invalid COMACT group at {group_address:#x}")
            comact_groups.append({
                "index": group_index,
                "address": group_address,
                "records": records,
            })

        conditional_tables = []
        for table_index, table_address in enumerate(pointer_list(data, conditional_table)):
            conditional_tables.append({
                "index": table_index,
                "address": table_address,
                "records": decode_conditional_table(data, table_address),
            })

        order_tables = []
        for table_index, table_address in enumerate(
            backward_pointer_list(data, order_table, order_root)
        ):
            order_tables.append({
                "index": table_index,
                "address": table_address,
                "records": decode_order_table(data, table_address),
            })

        comact_total += len(comact_groups)
        conditional_total += len(conditional_tables)
        order_total += len(order_tables)
        comact_record_total += sum(len(x["records"]) for x in comact_groups)
        conditional_record_total += sum(len(x["records"]) for x in conditional_tables)
        order_record_total += sum(len(x["records"]) for x in order_tables)

        characters.append({
            "slot": slot,
            "name": name,
            "comact_table": comact_table,
            "comact_groups": comact_groups,
            "conditional_table": conditional_table,
            "conditional_tables": conditional_tables,
            "order_action_table": order_table,
            "order_action_tables": order_tables,
        })

    return {
        "schema": 1,
        "set": set_name,
        "program_sha256": sha256_bytes(data),
        "comact_root": comact_root,
        "conditional_root": conditional_root,
        "order_action_root": order_root,
        "statistics": {
            "characters": len(characters),
            "comact_groups": comact_total,
            "comact_records_including_sentinels": comact_record_total,
            "conditional_tables": conditional_total,
            "conditional_records_including_sentinels": conditional_record_total,
            "order_action_tables": order_total,
            "order_action_records_including_sentinels": order_record_total,
        },
        "characters": characters,
    }


def write_ai_csvs(out_dir: Path, decoded: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = []
    definitions = [
        (
            "comact.csv",
            ["character", "slot", "group", "record", "address", "per", "actreq", "para", "lvl"],
            "comact_groups",
        ),
        (
            "conditional_actions.csv",
            [
                "character", "slot", "table", "record", "address", "weight", "set_num",
                "check_condition", "weight_adjustment", "reserved",
            ],
            "conditional_tables",
        ),
        (
            "order_actions.csv",
            [
                "character", "slot", "table", "record", "address", "repeat_count_or_opcode",
                "set_num", "check_condition", "unknown_04", "unknown_06",
            ],
            "order_action_tables",
        ),
    ]

    for filename, fields, family in definitions:
        path = out_dir / filename
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for character in decoded["characters"]:
                for table in character[family]:
                    table_key = "group" if family == "comact_groups" else "table"
                    for record_index, record in enumerate(table["records"]):
                        row = {
                            "character": character["name"],
                            "slot": character["slot"],
                            table_key: table["index"],
                            "record": record_index,
                            "address": f"0x{record['address']:08X}",
                        }
                        for field in fields:
                            if field in record:
                                row[field] = record[field]
                        writer.writerow(row)
        outputs.append({
            "file": path.name,
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return outputs


def required_specs(config: dict[str, Any], set_name: str, include_shared: bool) -> Iterable[dict[str, Any]]:
    yield from config["sets"][set_name]["maincpu"]
    if include_shared:
        for region in config["shared_regions"].values():
            yield from region["loads"]


def verify_sources(
    roms: RomIndex, config: dict[str, Any], set_name: str, include_shared: bool
) -> list[dict[str, Any]]:
    verified = []
    seen = set()
    for spec in required_specs(config, set_name, include_shared):
        key = (spec["crc32"], int(spec["size"]))
        if key in seen:
            continue
        seen.add(key)
        _, ref = roms.read(spec)
        verified.append(source_manifest_entry(spec, ref))
    return verified


def process_set(
    set_name: str,
    config: dict[str, Any],
    roms: RomIndex,
    output_root: Path,
    extract_regions: bool,
    extract_ai: bool,
    verify_only: bool,
) -> None:
    set_dir = output_root / set_name
    include_shared = extract_regions or verify_only
    verified = verify_sources(roms, config, set_name, include_shared)
    print(f"[{set_name}] verified {len(verified)} unique source chips")
    if verify_only and not extract_regions and not extract_ai:
        return

    set_dir.mkdir(parents=True, exist_ok=True)
    maincpu, maincpu_sources = build_maincpu(set_name, config, roms)
    outputs = []
    sources = list(maincpu_sources)

    if extract_regions:
        outputs.append(write_binary(set_dir / "maincpu.bin", maincpu))
        print(f"[{set_name}] wrote maincpu.bin ({len(maincpu):#x} bytes)")
        for name, region_spec in config["shared_regions"].items():
            region, region_sources = build_shared_region(name, region_spec, roms)
            outputs.append(write_binary(set_dir / f"{name}.bin", region))
            sources.extend(region_sources)
            print(f"[{set_name}] wrote {name}.bin ({len(region):#x} bytes)")

    ai_summary = None
    if extract_ai:
        decoded = decode_ai_tables(maincpu, set_name)
        rendered = hex_addresses(decoded)
        ai_path = set_dir / "ai_tables.json"
        ai_path.write_text(json.dumps(rendered, indent=2) + "\n", encoding="utf-8")
        outputs.append({
            "file": ai_path.name,
            "size": ai_path.stat().st_size,
            "sha256": hashlib.sha256(ai_path.read_bytes()).hexdigest(),
        })
        outputs.extend(write_ai_csvs(set_dir, decoded))
        ai_summary = rendered["statistics"] | {
            "comact_root": rendered["comact_root"],
            "conditional_root": rendered["conditional_root"],
            "order_action_root": rendered["order_action_root"],
        }
        print(
            f"[{set_name}] decoded {ai_summary['comact_groups']} COMACT groups, "
            f"{ai_summary['conditional_tables']} conditional tables, "
            f"{ai_summary['order_action_tables']} ordered-action tables"
        )

    manifest = {
        "schema": 1,
        "set": set_name,
        "description": config["sets"][set_name]["description"],
        "sources": sources,
        "outputs": outputs,
        "ai": ai_summary,
    }
    (set_dir / "extraction_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild and decode Dead or Alive Model 2 ROM data from MAME ZIPs."
    )
    parser.add_argument("--rom-dir", type=Path, default=Path("rom"), help="directory containing MAME ZIPs")
    parser.add_argument("--set", dest="set_name", default="doa", help="doa, doab, doaa, doaab, doaae, or all")
    parser.add_argument("--output", type=Path, default=Path("extracted"), help="output directory")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("doa_data.json"))
    parser.add_argument("--rom", action="store_true", help="rebuild logical MAME game-data regions")
    parser.add_argument("--ai", action="store_true", help="decode COMACT and related AI tables")
    parser.add_argument("--all", action="store_true", help="perform both --rom and --ai")
    parser.add_argument("--verify", action="store_true", help="verify required source chips")
    parser.add_argument("--list-sets", action="store_true", help="list supported sets and exit")
    args = parser.parse_args(argv)
    if not any((args.rom, args.ai, args.all, args.verify, args.list_sets)):
        parser.error("choose --rom, --ai, --all, --verify, or --list-sets")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
        supported = list(config["sets"])
        if args.list_sets:
            for name in supported:
                print(f"{name:5s} {config['sets'][name]['description']}")
            return 0
        if args.set_name != "all" and args.set_name not in supported:
            raise ExtractionError(
                f"unsupported set {args.set_name!r}; choose {', '.join(supported)}, or all"
            )

        roms = RomIndex(args.rom_dir)
        selected = supported if args.set_name == "all" else [args.set_name]
        for set_name in selected:
            process_set(
                set_name,
                config,
                roms,
                args.output,
                extract_regions=args.rom or args.all,
                extract_ai=args.ai or args.all,
                verify_only=args.verify,
            )
        return 0
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
