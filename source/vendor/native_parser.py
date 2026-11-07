#!/usr/bin/env python3

"""Faithful, grammar-limited extractor for the SRW3 ReMix4 main text reader.

This tool is deliberately conservative:

  * it only decodes controls whose operand length and effect were confirmed in

    the 01:84B0-01:8C80 reader;

  * it stops an entry at a branch/unknown instead of guessing a length;

  * it never translates or rewrites bytes;

  * re-encoding the untouched token stream must reproduce the ROM bytes.

Writes only below this script's directory (work/zcode-control-audit).

"""

from __future__ import annotations

import argparse

import hashlib

import json

import sys

from collections import Counter, OrderedDict, deque

from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent

ROOT = HERE.parents[1]

ROM_PATH = ROOT / "inputs" / "remix4-original.sfc"

MAP_PATH = ROOT / "source" / "japanese-map.json"

OUT_DIR = HERE / "out"

EXPECTED_SHA256 = "edcffa7b6aa734735b64f7674f02e2cf4e24a7a499cfd24675ad34c86218fe8f"

# 00:D277, 48 three-byte directory roots.  Group 32 starts at D2D7 (D277+96).

DIRECTORY_CPU = 0x00D277

DIRECTORY_FILE = 0x5277

MAIN_GROUP_FIRST = 32

MAIN_GROUP_LAST = 47

# Reader facts confirmed from the ROM (CPU addresses, bank 01).

READER_ENTRY_CPU = 0x85A7

READER_GETTER_CPU = 0x8B3C

DISPATCH_TABLE_CPU = 0x88E4

def cpu(bank: int, addr: int) -> str:

    return f"{bank:02X}:{addr:04X}"

def file_offset(bank: int, addr: int) -> int:

    """LoROM: banks 00-7F, $8000-$FFFF -> 32 KiB pages."""

    if not (0x8000 <= addr <= 0xFFFF):

        raise ValueError(f"address {addr:04X} is not in a LoROM ROM window")

    off = bank * 0x8000 + (addr - 0x8000)

    if off < 0:

        raise ValueError("negative file offset")

    return off

class Rom:

    def __init__(self, path: Path) -> None:

        self.path = path

        self.data = path.read_bytes()

        digest = hashlib.sha256(self.data).hexdigest()

        if digest != EXPECTED_SHA256:

            raise SystemExit(

                f"ROM sha256 mismatch: {digest} != {EXPECTED_SHA256}"

            )

    def u8(self, bank: int, addr: int) -> int:

        return self.data[file_offset(bank, addr)]

    def u16(self, bank: int, addr: int) -> int:

        off = file_offset(bank, addr)

        return self.data[off] | (self.data[off + 1] << 8)

    def slice(self, bank: int, start: int, end: int) -> bytes:

        a = file_offset(bank, start)

        b = file_offset(bank, end)

        return self.data[a:b]

class GlyphMap:

    def __init__(self, path: Path) -> None:

        raw = json.loads(path.read_text(encoding="utf-8"))

        self.map = {str(k).upper(): str(v) for k, v in raw.items()}

    def glyph(self, code: int) -> str:

        key = f"{code:04X}"

        return self.map.get(key, f"<U_{key}>")

    def is_unknown(self, code: int) -> bool:

        return f"{code:04X}" not in self.map or self.map[f"{code:04X}"].startswith("<U_") or self.map[f"{code:04X}"].startswith("<U_")

@dataclass

class Token:

    offset: int

    kind: str

    raw: bytes

    text: str

    params: Dict[str, Any] = field(default_factory=dict)

    dynamic: Optional[str] = None

    def as_json(self, bank: int) -> Dict[str, Any]:

        return {

            "offset": self.offset,

            "cpu": cpu(bank, self.offset),

            "kind": self.kind,

            "raw": self.raw.hex(),

            "text": self.text,

            "params": self.params,

            "dynamic": self.dynamic,

        }

@dataclass

class ParseResult:

    group: int

    entry: int

    bank: int

    start: int

    complete: bool

    stop_reason: str

    stop_offset: int

    tokens: List[Token]

    segments: List[List[int]]

    refs: List[Dict[str, Any]]

    dynamic: List[Dict[str, Any]]

    unknown_glyphs: List[str]

    glyph_count: int

    @property

    def end(self) -> int:

        return self.stop_offset

    def raw_bytes(self) -> bytes:

        return b"".join(self.tokens[i].raw for i in range(len(self.tokens)))

    def raw_hex(self) -> str:

        return self.raw_bytes().hex()

    def text(self) -> str:

        return "".join(t.text for t in self.tokens)

    def controls(self) -> List[Dict[str, Any]]:

        return [t.as_json(self.bank) for t in self.tokens if t.kind not in ("glyph",)]

    def as_json(self) -> Dict[str, Any]:

        return {

            "id": f"g{self.group:02d}/e{self.entry:03d}",

            "group": self.group,

            "entry": self.entry,

            "bank": self.bank,

            "start": self.start,

            "start_hex": f"{self.start:04X}",

            "cpu": cpu(self.bank, self.start),

            "file_offset": f"0x{file_offset(self.bank, self.start):05X}",

            "end": self.stop_offset,

            "end_hex": f"{self.stop_offset:04X}",

            "byte_length": len(self.raw_bytes()),

            "complete": self.complete,

            "stop_reason": self.stop_reason,

            "segments": self.segments,

            "source_contiguous": len(self.segments) == 1,

            "raw": self.raw_hex(),

            "text": self.text(),

            "glyph_count": self.glyph_count,

            "controls": self.controls(),

            "refs": self.refs,

            "dynamic": self.dynamic,

            "unknown_glyphs": self.unknown_glyphs,

            "reencode_ok": None,  # filled by verify_record()

        }

class Parser:

    def __init__(self, rom: Rom, glyphs: GlyphMap, bank: int, start: int) -> None:

        self.rom = rom

        self.glyphs = glyphs

        self.bank = bank

        self.start = start

        self.p = start

        self.tokens: List[Token] = []

        self.segments: List[List[int]] = []

        self.refs: List[Dict[str, Any]] = []

        self.dynamic: List[Dict[str, Any]] = []

        self.unknowns: List[str] = []

        self.glyph_count = 0

        self.seen: set[int] = set()

    def _read(self, length: int) -> bytes:

        if not (0x8000 <= self.p <= 0xFFFF):

            raise IndexError(f"offset {self.p:04X} outside ROM window")

        if self.p + length > 0x10000:

            raise IndexError(f"read of {length} bytes at {self.p:04X} crosses bank end")

        return self.rom.slice(self.bank, self.p, self.p + length)

    def _add(self, kind: str, length: int, text: str,

             params: Optional[Dict[str, Any]] = None,

             dynamic: Optional[str] = None) -> None:

        raw = self._read(length)

        token = Token(self.p, kind, raw, text, params or {}, dynamic)

        self.tokens.append(token)

        if self.segments and self.segments[-1][1] == self.p:

            self.segments[-1][1] = self.p + length

        else:

            self.segments.append([self.p, self.p + length])

        self.p += length

    def _add_glyph(self, code: int) -> None:

        text = self.glyphs.glyph(code)

        if self.glyphs.is_unknown(code):

            self.unknowns.append(text)

        length = 2 if code > 0xFF else 1

        self._add("glyph", length, text, {"code": f"{code:04X}"})

        self.glyph_count += 1

    def parse(self, max_steps: int = 20000) -> ParseResult:

        stop_reason = "max_steps"

        complete = False

        for _ in range(max_steps):

            if self.p in self.seen:

                stop_reason = "loop"

                break

            self.seen.add(self.p)

            if not (0x8000 <= self.p <= 0xFFFF):

                stop_reason = "address_out_of_bank"

                break

            try:

                c = self.rom.u8(self.bank, self.p)

                if c <= 0xEF:

                    self._add_glyph(c)

                    continue

                if c <= 0xF2:

                    # F0/F1/F2 + one byte; map key is F0xx/F1xx/F2xx.

                    if self.p + 2 > 0x10000:

                        stop_reason = "truncated_2byte_glyph"

                        break

                    code = (c << 8) | self.rom.u8(self.bank, self.p + 1)

                    self._add_glyph(code)

                    continue

                if c == 0xF3:

                    self._add("F3", 1, "<F3>")

                    continue

                if c == 0xF4:

                    self._add("F4", 1, "<F4>")

                    continue

                if c == 0xF5:

                    if self.p + 2 > 0x10000:

                        stop_reason = "truncated_F5"

                        break

                    p1 = self.rom.u8(self.bank, self.p + 1)

                    dyn = "random_delay" if (p1 == 0 or p1 >= 0x80) else None

                    self._add("F5", 2, f"<F5:{p1:02X}>", {"delay": p1}, dyn)

                    if dyn:

                        self.dynamic.append({"control": "F5", "reason": dyn,

                                             "offset": self.tokens[-1].offset})

                    continue

                if c == 0xF6:

                    if self.p + 3 > 0x10000:

                        stop_reason = "truncated_F6"

                        break

                    ent = self.rom.u8(self.bank, self.p + 1)

                    grp = self.rom.u8(self.bank, self.p + 2)

                    dyn = "entry_from_WRAM_0200" if ent == 0xFF else None

                    if grp == 0xFF:

                        dyn = (dyn + "+" if dyn else "") + "group_from_WRAM_0200"

                    self.refs.append({"control": "F6", "group": grp, "entry": ent,

                                      "offset": self.p})

                    self._add("F6", 3, f"<F6:{ent:02X},{grp:02X}>",

                              {"entry": ent, "group": grp}, dyn)

                    if dyn:

                        self.dynamic.append({"control": "F6", "reason": dyn,

                                             "offset": self.tokens[-1].offset})

                    continue

                if c == 0xF7:

                    if self.p + 2 > 0x10000:

                        stop_reason = "truncated_F7"

                        break

                    n = self.rom.u8(self.bank, self.p + 1)

                    length = 2 + 2 * n

                    if self.p + length > 0x10000:

                        stop_reason = "truncated_F7_table"

                        break

                    targets = [self.rom.u16(self.bank, self.p + 2 + 2 * i)

                               for i in range(n)]

                    self._add("F7", length,

                              "<F7:" + f"{n}:" + ",".join(f"{t:04X}" for t in targets) + ">",

                              {"count": n, "targets": targets},

                              "random_branch")

                    self.refs.append({"control": "F7", "targets": targets,

                                      "bank": self.bank,

                                      "offset": self.tokens[-1].offset})

                    self.dynamic.append({"control": "F7", "reason": "random_branch",

                                         "targets": targets,

                                         "offset": self.tokens[-1].offset})

                    stop_reason = "random_branch_F7"

                    break

                if c == 0xF8:

                    if self.p + 4 > 0x10000:

                        stop_reason = "truncated_F8"

                        break

                    sub = self.rom.u8(self.bank, self.p + 1)

                    p2 = self.rom.u8(self.bank, self.p + 2)

                    p3 = self.rom.u8(self.bank, self.p + 3)

                    if sub <= 5:

                        self._add("F8", 4, f"<F8:{sub:02X}>",

                                  {"sub": sub, "opaque": [p2, p3]})

                        continue

                    if sub <= 7:

                        target = p2 | (p3 << 8)

                        self._add("F8", 4, f"<F8:{sub:02X}:->{target:04X}>",

                                  {"sub": sub, "target": target, "bank": self.bank},

                                  "external_condition")

                        self.refs.append({"control": "F8", "sub": sub,

                                          "target": target, "bank": self.bank,

                                          "offset": self.tokens[-1].offset})

                        self.dynamic.append({"control": "F8", "reason": "external_condition",

                                             "sub": sub, "target": target,

                                             "offset": self.tokens[-1].offset})

                        stop_reason = f"conditional_branch_F8_sub{sub}"

                        break

                    stop_reason = f"undefined_F8_sub{sub:02X}"

                    break

                if c == 0xF9:

                    if self.p + 3 > 0x10000:

                        stop_reason = "truncated_F9"

                        break

                    p1 = self.rom.u8(self.bank, self.p + 1)

                    p2 = self.rom.u8(self.bank, self.p + 2)

                    if p2 >= 0x80:

                        target = p1 | (p2 << 8)

                        self._add("F9", 3, f"<F9:JMP:{target:04X}>",

                                  {"form": "absolute_jump", "target": target,

                                   "bank": self.bank})

                        self.refs.append({"control": "F9", "form": "absolute_jump",

                                          "target": target, "bank": self.bank,

                                          "offset": self.tokens[-1].offset})

                        stop_reason = "absolute_jump_F9"
                        break

                    sub = p2

                    if sub <= 7:

                        if self.p + 5 > 0x10000:

                            stop_reason = "truncated_F9_conditional"

                            break

                        p3 = self.rom.u8(self.bank, self.p + 3)

                        p4 = self.rom.u8(self.bank, self.p + 4)

                        target = p3 | (p4 << 8)

                        cond = p1 | ((sub & 3) << 8)

                        self._add("F9", 5,

                                  f"<F9:C{sub}:{cond:03X}:->{target:04X}>",

                                  {"form": "conditional_abs", "sub": sub,

                                   "condition": cond, "target": target,

                                   "bank": self.bank, "polarity": "clear" if sub <= 3 else "set"})

                        self.refs.append({"control": "F9", "form": "conditional_abs",

                                          "sub": sub, "condition": cond,

                                          "target": target, "bank": self.bank,

                                          "offset": self.tokens[-1].offset})

                        stop_reason = f"conditional_branch_F9_sub{sub}"

                        break

                    if sub <= 11:

                        self._add("F9", 2, f"<F9:DLY:{sub:02X}>",

                                  {"form": "delay_then_reprocess_p2", "sub": sub})

                        continue

                    if sub <= 15:

                        self._add("F9", 2, f"<F9:DYN:{sub:02X}>",

                                  {"form": "dynamic_unit_text", "sub": sub,

                                   "group": sub, "entry": "runtime"})

                        self.dynamic.append({"control": "F9", "reason": "dynamic_unit_text",

                                             "sub": sub, "group": sub,

                                             "offset": self.tokens[-1].offset})

                        continue

                    stop_reason = f"undefined_F9_sub{sub:02X}"

                    break

                if c == 0xFA:

                    if self.p + 2 > 0x10000:

                        stop_reason = "truncated_FA"

                        break

                    sub = self.rom.u8(self.bank, self.p + 1)

                    if sub <= 3:

                        self._add("FA", 2, f"<FA:DLY:{sub:02X}>",

                                  {"form": "delay_then_reprocess_p2", "sub": sub})

                        continue

                    if sub <= 7:

                        self._add("FA", 2, f"<FA:DYN:{sub:02X}>",

                                  {"form": "dynamic_unit_text", "sub": sub,

                                   "group": "DP01_unknown", "entry": "runtime"})

                        self.dynamic.append({"control": "FA", "reason": "dynamic_unit_text",

                                             "sub": sub,

                                             "group": "DP01_unknown",

                                             "offset": self.tokens[-1].offset})

                        continue

                    stop_reason = f"undefined_FA_sub{sub:02X}"

                    break

                if c == 0xFB:

                    if self.p + 3 > 0x10000:

                        stop_reason = "truncated_FB"

                        break

                    p1 = self.rom.u8(self.bank, self.p + 1)

                    sub = self.rom.u8(self.bank, self.p + 2)

                    if sub <= 9:

                        cond = p1 | ((sub & 3) << 8)

                        self._add("FB", 3, f"<FB:{sub:02X}:{p1:02X}>",

                                  {"sub": sub, "arg": p1, "condition": cond})

                        if sub <= 7:

                            self.dynamic.append({"control": "FB",

                                                 "reason": "condition_flag_write",

                                                 "sub": sub, "condition": cond,

                                                 "offset": self.tokens[-1].offset})

                        continue

                    stop_reason = f"undefined_FB_sub{sub:02X}"

                    break

                if c == 0xFC:

                    self._add("FC", 1, "<FC>")

                    continue

                if c == 0xFD:

                    if self.p + 2 > 0x10000:

                        stop_reason = "truncated_FD"

                        break

                    p1 = self.rom.u8(self.bank, self.p + 1)

                    # Handler over-reads a 16-bit value but advances DP by one.

                    self._add("FD", 2, f"<FD:{p1:02X}>",

                              {"portrait": p1, "note": "16-bit over-read, 1 byte consumed"})

                    continue

                if c == 0xFE:

                    self._add("FE", 1, "<FE>")

                    continue

                if c == 0xFF:

                    self._add("FF", 1, "<FF>")

                    stop_reason = "FF_end"

                    complete = True

                    break

                stop_reason = f"unknown_opcode_{c:02X}"

                break

            except IndexError as exc:

                stop_reason = f"read_error:{exc}"

                break

        return ParseResult(

            group=0, entry=0, bank=self.bank, start=self.start,

            complete=complete, stop_reason=stop_reason, stop_offset=self.p,

            tokens=self.tokens, segments=self.segments, refs=self.refs,

            dynamic=self.dynamic, unknown_glyphs=self.unknowns,

            glyph_count=self.glyph_count,

        )

def infer_table(rom: Rom, bank: int, root: int) -> Dict[str, Any]:

    """Infer the pointer-table end as the first text address.

    The tables in this ROM are laid out as a contiguous array of 16-bit

    same-bank offsets immediately followed by the text region.  We use the

    minimum word among the first 16 entries as the candidate first text

    address, then verify that every nonzero word before it is >= it.  This is

    a layout inference, not proof that every slot is used.

    """

    words = [rom.u16(bank, root + 2 * i) for i in range(16)]

    nonzero = [w for w in words if w >= 0x8000]

    if not nonzero:

        return {"root": root, "end": None, "count": None,

                "inference": "no plausible pointer", "confidence": "none"}

    cand = min(nonzero)

    if cand <= root:

        return {"root": root, "end": None, "count": None,

                "inference": "candidate <= root", "confidence": "none"}

    count = (cand - root) // 2

    if count < 1 or count > 4096:

        return {"root": root, "end": cand, "count": None,

                "inference": f"implausible count {count}", "confidence": "none"}

    values = [rom.u16(bank, root + 2 * i) for i in range(count)]

    zeros = [i for i, v in enumerate(values) if v == 0]

    below = [(i, v) for i, v in enumerate(values) if 0 < v < cand]

    verified = not below

    return {

        "root": root,

        "end": cand,

        "count": count,

        "zero_entries": zeros,

        "nonzero_below_end": [{"entry": i, "value": v} for i, v in below],

        "inference": "first text address = min nonzero word; every nonzero word before it is >= it",

        "confidence": "medium" if verified else "low",

        "verified_layout": verified,

        "note": "Table length is inferred from layout; entries may be unused, aliases, or non-text. No total-coverage claim.",

    }

def directory_roots(rom: Rom) -> List[Dict[str, Any]]:

    out = []

    for g in range(48):

        off = DIRECTORY_FILE + 3 * g

        ptr = rom.data[off] | (rom.data[off + 1] << 8)

        bank = rom.data[off + 2]

        out.append({"group": g, "root": ptr, "bank": bank})

    return out

def resolve_f6(rom: Rom, roots: List[Dict[str, Any]], group: int, entry: int) -> Optional[Dict[str, Any]]:

    if not (0 <= group < 48) or not (0 <= entry <= 0xFF):

        return None

    root = roots[group]

    if root["root"] == 0 or root["bank"] == 0:

        return None

    if not (0x8000 <= root["root"] <= 0xFFFF):

        return None

    try:

        target = rom.u16(root["bank"], root["root"] + 2 * entry)

    except (IndexError, ValueError):

        return None

    return {

        "group": group,

        "entry": entry,

        "root_bank": root["bank"],

        "root": root["root"],

        "target": target,

        "cpu": cpu(root["bank"], target) if target else None,

        "class": ("main_text_group" if MAIN_GROUP_FIRST <= group <= MAIN_GROUP_LAST

                  else "non_main_or_dynamic_group"),

    }

def verify_parse(rom: Rom, res: ParseResult) -> bool:

    """Prove that the token stream exactly re-encodes the ROM bytes.

    * every token's raw bytes must equal the ROM at that token offset;

    * concatenating token raws must equal the concatenation of the recorded

      executed segments (which also handles F9 absolute jumps).

    """

    joined = b""

    for start, end in res.segments:

        joined += rom.slice(res.bank, start, end)

    if res.raw_bytes() != joined:

        return False

    for tok in res.tokens:

        try:

            actual = rom.slice(res.bank, tok.offset, tok.offset + len(tok.raw))

        except (IndexError, ValueError):

            return False

        if actual != tok.raw:

            return False

    return True

def main(argv: Optional[Sequence[str]] = None) -> int:

    ap = argparse.ArgumentParser(description=__doc__)

    ap.add_argument("--group", type=int, default=None,

                    help="extract one group (32-47); default: all main groups")

    ap.add_argument("--entry", type=int, default=None,

                    help="extract one entry (requires --group)")

    ap.add_argument("--verify", action="store_true", default=True,

                    help="verify exact byte re-encoding (default: on)")

    ap.add_argument("--no-write", action="store_true",

                    help="parse and report without writing output files")

    args = ap.parse_args(argv)

    rom = Rom(ROM_PATH)

    glyphs = GlyphMap(MAP_PATH)

    roots = directory_roots(rom)

    if args.entry is not None and args.group is None:

        ap.error("--entry requires --group")

    groups: Iterable[int]

    if args.group is not None:

        groups = [args.group]

    else:

        groups = range(MAIN_GROUP_FIRST, MAIN_GROUP_LAST + 1)

    only_entry = args.entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tables: Dict[Tuple[int, int, int], Dict[str, Any]] = {}

    table_ranges: List[Tuple[int, int, int]] = []

    for g in range(MAIN_GROUP_FIRST, MAIN_GROUP_LAST + 1):

        meta = roots[g]

        key = (g, meta["bank"], meta["root"])

        if key not in tables:

            info = infer_table(rom, meta["bank"], meta["root"])

            info.update({"group": g, "bank": meta["bank"]})

            tables[key] = info

        if tables[key]["end"] is not None:

            table_ranges.append((meta["bank"], meta["root"], tables[key]["end"]))

    def is_table_pointer(bank: int, addr: int) -> bool:

        if addr == 0:

            return True

        for b, start, end in table_ranges:

            if b == bank and start <= addr < end:

                return True

        return False

    records: List[Dict[str, Any]] = []

    per_group: Dict[int, Dict[str, Any]] = OrderedDict()

    for g in groups:

        meta = roots[g]

        key = (g, meta["bank"], meta["root"])

        info = tables.get(key) or infer_table(rom, meta["bank"], meta["root"])

        count = info.get("count")

        pg = {

            "group": g,

            "bank": meta["bank"],

            "root": meta["root"],

            "root_cpu": cpu(meta["bank"], meta["root"]),

            "table_end": info.get("end"),

            "entry_count": count,

            "table_inference": info,

            "parsed": 0,

            "complete": 0,

            "incomplete": 0,

            "rejected": 0,

            "entries": [],

        }

        per_group[g] = pg

        if count is None:

            continue

        entries = range(count)

        if only_entry is not None:

            entries = [only_entry] if 0 <= only_entry < count else []

        for e in entries:

            try:

                ptr = rom.u16(meta["bank"], meta["root"] + 2 * e)

            except (IndexError, ValueError):

                pg["rejected"] += 1

                continue

            if is_table_pointer(meta["bank"], ptr):

                pg["rejected"] += 1

                pg["entries"].append({"entry": e, "pointer": ptr,

                                      "status": "rejected_non_text_or_table_pointer"})

                continue

            if not (0x8000 <= ptr <= 0xFFFF):

                pg["rejected"] += 1

                pg["entries"].append({"entry": e, "pointer": ptr,

                                      "status": "rejected_pointer_outside_bank"})

                continue

            parser = Parser(rom, glyphs, meta["bank"], ptr)

            res = parser.parse()

            res.group = g

            res.entry = e

            rec = res.as_json()

            rec["reencode_ok"] = verify_parse(rom, res)

            # Attach resolved F6 references.

            refs = []

            for ref in rec["refs"]:

                if ref.get("control") == "F6":

                    r = resolve_f6(rom, roots, ref["group"], ref["entry"])

                    ref = dict(ref)

                    ref["resolved"] = r

                    if r and r["target"] == 0:

                        ref["resolved"] = None

                refs.append(ref)

            rec["refs"] = refs

            rec["status"] = "complete" if res.complete else "incomplete"

            records.append(rec)

            pg["parsed"] += 1

            if res.complete:

                pg["complete"] += 1

            else:

                pg["incomplete"] += 1

            pg["entries"].append({"entry": e, "pointer": ptr,

                                  "status": rec["status"],

                                  "stop_reason": res.stop_reason,

                                  "byte_length": rec["byte_length"],

                                  "segments": rec["segments"]})

    # Deduplicate identical spans (same bank/start/end/raw), keeping group/entry aliases.

    by_span: Dict[Tuple[int, int, int, str], Dict[str, Any]] = OrderedDict()

    for rec in records:

        key = (rec["bank"], rec["start"], rec["end"], rec["raw"])

        if key in by_span:

            by_span[key].setdefault("aliases", []).append(

                {"group": rec["group"], "entry": rec["entry"]})

        else:

            rec = dict(rec)

            rec["aliases"] = []

            by_span[key] = rec

    unique_records = list(by_span.values())

    # ------------------------------------------------------------------

    # Explicit branch-target pass.

    #

    # F7 random branches, F9 conditional branches and F8 sub 6/7 branches

    # contain explicit 16-bit same-bank target words.  Following those words

    # is not guessing: they are operands.  We parse each target as its own

    # span, stop at a further branch, and recursively enqueue that branch's

    # explicit targets.  This recovers branch bodies (notably group 33's

    # FA05 + F7 pattern) that a purely linear entry scan would skip.

    # ------------------------------------------------------------------

    def enqueue_refs(rec: Dict[str, Any], queue_out: List[Tuple[int, int, str, str]]) -> None:

        rid = rec.get("id", "?")

        for ref in rec.get("refs", []):

            if ref.get("control") == "F7":

                for target in ref.get("targets", []):

                    queue_out.append((rec["bank"], target, rid, "F7"))

            elif ref.get("control") == "F9" and ref.get("form") == "conditional_abs":

                queue_out.append((rec["bank"], ref["target"], rid, "F9"))

            elif ref.get("control") == "F8" and ref.get("sub") in (6, 7):

                queue_out.append((rec["bank"], ref["target"], rid, "F8"))

    work: List[Tuple[int, int, str, str]] = []

    for rec in unique_records:

        enqueue_refs(rec, work)

    main_by_start = {(r["bank"], r["start"]): r for r in unique_records}

    branch_by_target: Dict[Tuple[int, int], Dict[str, Any]] = OrderedDict()

    branch_target_origins: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

    branch_skipped: List[Dict[str, Any]] = []

    queue = deque(work)

    while queue and len(branch_by_target) < 10000:

        bank, target, origin_id, kind = queue.popleft()

        key = (bank, target)

        origin = {"origin": origin_id, "control": kind}

        branch_target_origins.setdefault(key, []).append(origin)

        if key in main_by_start:

            main_by_start[key].setdefault("branch_origins", []).extend(

                branch_target_origins[key])

            continue

        if key in branch_by_target:

            branch_by_target[key].setdefault("branch_origins", []).extend(

                branch_target_origins[key])

            continue

        if not (0x8000 <= target <= 0xFFFF) or is_table_pointer(bank, target):

            branch_skipped.append({"bank": bank, "target": target,

                                   "origins": branch_target_origins[key],

                                   "reason": "outside_bank_or_table_pointer"})

            continue

        parser = Parser(rom, glyphs, bank, target)

        res = parser.parse()

        # Synthetic identity; the actual span is a branch target, not a table slot.

        res.group = main_by_start.get((bank, target), {}).get("group", -1)

        res.entry = -1

        rec = res.as_json()

        rec["id"] = f"branch:{bank:02X}:{target:04X}"

        rec["branch_target"] = True

        rec["branch_origins"] = branch_target_origins[key]

        rec["status"] = "complete" if res.complete else "incomplete"

        rec["reencode_ok"] = verify_parse(rom, res)

        branch_by_target[key] = rec

        new_refs: List[Tuple[int, int, str, str]] = []

        enqueue_refs(rec, new_refs)

        queue.extend(new_refs)

    branch_records = list(branch_by_target.values())

    # Overlap diagnostics: a second entry starting strictly inside another

    # entry's executed bytes is a boundary warning.  This is O(total bytes),

    # not O(entries^2).

    start_owner: Dict[Tuple[int, int], Dict[str, Any]] = {

        (r["bank"], r["start"]): r for r in unique_records

    }

    overlap_pairs = []

    for a in unique_records:

        for s, e in a["segments"]:

            for x in range(s, e):

                b = start_owner.get((a["bank"], x))

                if b is not None and b is not a and b["start"] != a["start"]:

                    overlap_pairs.append({

                        "inner": f"g{b['group']:02d}/e{b['entry']:03d}",

                        "outer": f"g{a['group']:02d}/e{a['entry']:03d}",

                        "bank": a["bank"],

                        "address": b["start"],

                    })

    total_bytes = sum(r["byte_length"] for r in unique_records)

    complete_bytes = sum(r["byte_length"] for r in unique_records if r["complete"])

    branch_complete = [r for r in branch_records if r["complete"]]

    branch_complete_bytes = sum(r["byte_length"] for r in branch_complete)

    branch_glyphs = sum(r["glyph_count"] for r in branch_records)

    root34 = next((r for r in unique_records

                   if r["group"] == 34 and r["entry"] == 0), None)

    root34_exact = False

    if root34 is not None and root34["source_contiguous"]:

        root34_exact = (

            bytes.fromhex(root34["raw"])

            == rom.slice(root34["bank"], root34["start"], root34["end"])

        )

    report = {

        "rom": {

            "path": str(ROM_PATH),

            "sha256": hashlib.sha256(rom.data).hexdigest(),

            "size": len(rom.data),

            "mapper": "LoROM",

        },

        "reader": {

            "entry_cpu": "01:85A7",

            "getter_cpu": "01:8B3C",

            "dispatch_cpu": "01:85E8",

            "jump_table_cpu": "01:88E4",

            "directory_cpu": "00:D277",

            "directory_file": "0x005277",

            "main_groups": [MAIN_GROUP_FIRST, MAIN_GROUP_LAST],

            "main_group_directory_cpu": "00:D2D7",

        },

        "tables": list(tables.values()),

        "groups": list(per_group.values()),

        "verification": {

            "all_token_raw_matches_rom": all(r["reencode_ok"] for r in unique_records + branch_records),

            "all_token_streams_reencode_to_segments": all(r["reencode_ok"] for r in unique_records + branch_records),

            "root34_0_raw_equals_rom_slice": root34_exact,

        },

        "totals": {

            "records_raw": len(records),

            "records_unique": len(unique_records),

            "complete_unique": sum(1 for r in unique_records if r["complete"]),

            "incomplete_unique": sum(1 for r in unique_records if not r["complete"]),

            "bytes_unique": total_bytes,

            "bytes_complete": complete_bytes,

            "glyph_tokens": sum(r["glyph_count"] for r in unique_records),

            "unknown_glyphs": sum(len(r["unknown_glyphs"]) for r in unique_records),

            "branch_targets_unique": len(branch_records),

            "branch_complete": len(branch_complete),

            "branch_incomplete": len(branch_records) - len(branch_complete),

            "branch_bytes_complete": branch_complete_bytes,

            "branch_glyph_tokens": branch_glyphs,

            "branch_skipped": len(branch_skipped),

        },

        "coverage": {

            "claim": "Only entries that terminate at FF with the confirmed grammar are called complete. Branch/unknown entries are stopped and listed.",

            "table_length": "inferred from first-text-address layout; not independently proven; see tables[].table_inference",

            "not_claimed": [

                "all slots in a root table are used or are text",

                "runtime condition/random selection; only explicit branch targets are followed",

                "FA dynamic-text group provenance (DP $01)",

            ],

        },

        "branch_skipped_targets": branch_skipped[:200],

        "overlaps": overlap_pairs[:200],

        "overlap_count": len(overlap_pairs),

    }

    if args.no_write:

        print(json.dumps(report["totals"], ensure_ascii=False, indent=2))

        return 0

    # Write outputs only in the audit directory.

    (OUT_DIR / "tables.json").write_text(

        json.dumps(list(tables.values()), ensure_ascii=False, indent=2),

        encoding="utf-8")

    (OUT_DIR / "report.json").write_text(

        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT_DIR / "spans.jsonl").open("w", encoding="utf-8", newline="\n") as fh:

        for rec in unique_records:

            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=False) + "\n")

    translatable = [r for r in unique_records

                    if r["complete"] and r["glyph_count"] > 0]

    with (OUT_DIR / "translation-spans.jsonl").open("w", encoding="utf-8", newline="\n") as fh:

        for rec in translatable:

            fh.write(json.dumps({

                "id": rec["id"],

                "aliases": rec["aliases"],

                "group": rec["group"],

                "entry": rec["entry"],

                "bank": rec["bank"],

                "start": rec["start"],

                "cpu": rec["cpu"],

                "file_offset": rec["file_offset"],

                "end": rec["end"],

                "segments": rec["segments"],

                "raw": rec["raw"],

                "text": rec["text"],

                "controls": rec["controls"],

                "dynamic": rec["dynamic"],

                "unknown_glyphs": rec["unknown_glyphs"],

            }, ensure_ascii=False) + "\n")

    with (OUT_DIR / "branch-spans.jsonl").open("w", encoding="utf-8", newline="") as fh:

        for rec in branch_records:

            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=False) + chr(10))

    branch_translatable = [r for r in branch_records

                           if r["complete"] and r["glyph_count"] > 0]

    with (OUT_DIR / "branch-translation-spans.jsonl").open("w", encoding="utf-8", newline="") as fh:

        for rec in branch_translatable:

            fh.write(json.dumps({

                "id": rec["id"],

                "branch_origins": rec["branch_origins"],

                "bank": rec["bank"],

                "start": rec["start"],

                "cpu": rec["cpu"],

                "file_offset": rec["file_offset"],

                "end": rec["end"],

                "segments": rec["segments"],

                "raw": rec["raw"],

                "text": rec["text"],

                "controls": rec["controls"],

                "dynamic": rec["dynamic"],

                "unknown_glyphs": rec["unknown_glyphs"],

            }, ensure_ascii=False) + chr(10))

    # Root34/0 validation artifact.

    target = next((r for r in unique_records

                   if r["group"] == 34 and r["entry"] == 0), None)

    if target is not None:

        (OUT_DIR / "root34-0.json").write_text(

            json.dumps(target, ensure_ascii=False, indent=2), encoding="utf-8")

    bad = [r["id"] for r in unique_records + branch_records if not r["reencode_ok"]]

    print(json.dumps({

        "records_unique": len(unique_records),

        "complete": report["totals"]["complete_unique"],

        "incomplete": report["totals"]["incomplete_unique"],

        "bytes_unique": total_bytes,

        "bytes_complete": complete_bytes,

        "branch_unique": len(branch_records),

        "branch_complete": len(branch_complete),

        "branch_bytes_complete": branch_complete_bytes,

        "branch_glyph_tokens": branch_glyphs,

        "reencode_failures": bad[:10],

        "root34_0": ({"cpu": target["cpu"], "length": target["byte_length"],

                      "complete": target["complete"],

                      "reencode_ok": target["reencode_ok"]} if target else None),

        "output": str(OUT_DIR),

    }, ensure_ascii=False, indent=2))

    return 0 if not bad else 2

if __name__ == "__main__":

    sys.exit(main())

