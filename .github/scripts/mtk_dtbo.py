#!/usr/bin/env python3
"""Wrap a DTB in the MediaTek dtbo table that the stock boot image carries
right after the ramdisk.

usage: mtk_dtbo.py <input.dtb> <output-dtb>
"""
import struct
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

dtb = src.read_bytes()
if dtb[:4] != b"\xd0\x0d\xfe\xed":
    sys.exit(f"{src}: not a DTB")

# Header 0x20 + one entry 0x20, dtb at 0x40. Values taken from the stock image.
header = struct.pack(">8I", 0xD7B7AB1E, 0x40 + len(dtb), 0x20, 0x20, 1, 0x20, 0x800, 0)
entry = struct.pack(">8I", len(dtb), 0x40, 0, 0, 0, 0, 0, 0)

dst.write_bytes(header + entry + dtb)
print(f"{dst}: {len(dtb)} byte dtb, {len(dtb) + 0x40} byte table")
