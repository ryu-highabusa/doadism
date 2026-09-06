# Dead or Alive Model 2 data extractor

`data_extract.py` reconstructs the logical ROM regions used by MAME for the
five currently dumped arcade builds of **Dead or Alive**, and optionally walks
the validated CPU-AI data structures in the reconstructed i960 program.

The package contains no game data. You must supply your own MAME ROM ZIPs.

## Supported sets

| Set | Hardware/revision |
|---|---|
| `doa` | Model 2B, Jan. 10 1997 / probable revision C |
| `doab` | Model 2B, Dec. 6 1996 / revision B |
| `doaa` | Model 2A, Dec. 4 1996 / revision A |
| `doaab` | Model 2A, Nov. 3 1996 |
| `doaae` | Model 2A export revision |

Place the relevant ZIPs in one directory. Keep `doa.zip` there as well: the
clone archives contain only chips that differ from the parent and rely on the
parent for shared graphics, audio, and sample data.

## Usage

Verify that every required chip can be resolved and read:

```console
python data_extract.py --rom-dir rom --set all --verify
```

Reconstruct MAME-style logical regions for one set:

```console
python data_extract.py --rom-dir rom --set doa --rom --output extracted
```

Decode the CPU-AI tables without writing the large graphics/audio regions:

```console
python data_extract.py --rom-dir rom --set doa --ai --output extracted
```

Do both:

```console
python data_extract.py --rom-dir rom --set doa --all --output extracted
```

`--set all` works with `--rom`, but produces roughly 400 MiB because the shared
regions are emitted once per revision. For ordinary reverse engineering,
`--set all --ai` is much smaller and more useful.

## Region output

The `--rom` operation writes:

| File | Size | Transformation |
|---|---:|---|
| `maincpu.bin` | `0x100000` | Two 16-bit i960 chips interleaved onto a 32-bit bus |
| `main_data.bin` | `0x2000000` | Four chip pairs plus the MAME `ROM_COPY` mirror |
| `polygons.bin` | `0x2000000` | Three chip pairs; unpopulated tail filled with `FF` |
| `textures.bin` | `0x800000` | One interleaved chip pair |
| `audiocpu.bin` | `0x80000` | 16-bit word-swapped sound program |
| `samples.bin` | `0x800000` | Four sequential, 16-bit word-swapped sample chips |

`maincpu.bin` contains the actual 1 MiB assembled program. MAME allocates a
2 MiB region for it, but the unpopulated upper half is omitted so the result
can be imported directly into Ghidra at base address zero.

Every extraction directory also receives `extraction_manifest.json` with the
source archive/member selected for each checksum and SHA-256 hashes of outputs.

The common Model 2 CPU/video-board firmware chips (`mpr-16310`, `opr-14742`,
and related files) are neither verified, decoded, nor emitted yet. They are board
support ROMs rather than the DOA-specific program/data/model/texture/audio
regions targeted by this first version.

## AI output

The `--ai` operation writes:

- `ai_tables.json`: complete nested character/table/record representation;
- `comact.csv`: all four-byte `DOA_COMACT` records;
- `conditional_actions.csv`: all eight-byte weighted conditional records;
- `order_actions.csv`: all eight-byte ordered-action records;
- `extraction_manifest.json`: roots, counts, sources, and output hashes.

The COMACT root is discovered structurally rather than selected from a
hard-coded revision table. The scanner requires all nine known character slots,
the exact per-character group counts, valid program pointers, legal `per`
values, and an `FF` sentinel in every group. The other roots retain stable
distances from that validated anchor:

```text
conditional root = COMACT root + 0x17E0
ordered root     = COMACT root + 0x2090
```

All five supplied builds currently validate as:

```text
149 COMACT groups / 623 records including sentinels
 99 conditional tables / 646 records including sentinels
 37 ordered-action tables / 236 records including sentinels
```

The record contents are identical across these revisions after removing their
revision-specific addresses.

## How this differs from `stfdecomp`

The conceptual starting point is similar: checksum the source chips and rebuild
the byte layout seen by the emulated CPUs. The implementation is independent,
and DOA adds several requirements:

1. **Split clone resolution.** A changed DOA program may be in a tiny clone
   ZIP while all shared chips remain in `doa.zip`. Sources are therefore
   located by `(CRC32, size)` across every ZIP, not only by filename in a fixed
   archive.
2. **More load modes.** DOA uses 32-bit word-lane interleaving, 16-bit word
   swapping, erased-region fill, and a mirrored data block.
3. **Several program layouts.** Each revision moves the useful AI data. The
   extractor identifies a pointer graph by its invariants instead of assuming
   one absolute root.
4. **Graph traversal rather than fixed slicing.** Character roots lead to
   pointer arrays, which lead to variable-length, sentinel-terminated record
   streams. Every pointer, boundary, opcode range, and terminator is checked
   before output is accepted.
5. **Analysis-friendly products.** In addition to raw reconstructed regions,
   the tool emits JSON and CSV views intended for Ghidra labeling, comparison,
   and future semantic work.

## Configuration

`doa_data.json` contains the per-revision program chip checksums and the shared
region load recipe. It is separate from the Python so future dumps or corrected
MAME definitions can be added without rewriting the extraction engine.

## Note on `FUN_0002f280`

The supplied decompile's `uVar4 % uVar4` is a register-recovery artifact, not
credible source logic. The incoming argument and `FUN_0008e6f0`'s return both
occupy `g0` at different times, and the decompiler has merged them. The call
sites use the result as a bounded random delay and also call it with
`(upper - lower) + 1` before adding `lower`. The strongest current static
interpretation is therefore:

```c
/* exclusive_limit is expected to be nonzero */
uint8_t random_u8_below(uint32_t exclusive_limit)
{
    return (uint8_t)(rng_next() % exclusive_limit);
}
```

This naming is intentionally marked as an interpretation until the individual
i960 instructions or a runtime sample confirm which register preserves the
argument across the RNG call. It is not required by the extractor itself.
