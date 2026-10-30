#!/usr/bin/env python3
"""Repack a stock boot.img with a freshly built Image.gz.

The stock image is Android boot header v2, page size 2048: kernel at 0x800,
ramdisk after it, then a 64-byte big-endian MediaTek dtbo table followed by
mt6765.dtb. The AVB footer is dropped because it signs the old image; the
result is for an unlocked bootloader (fastboot boot / fastboot flash boot).

usage: repack_boot.py stock.img Image.gz out.img [--dtb mt6765.dtb]
"""
import hashlib
import struct
import sys
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = dict(zip(sys.argv[1::2], sys.argv[2::2]))
stock_p = Path(args[0] if len(args) > 0 else "/home/omar/stock/boot.img")
kernel_p = Path(args[1] if len(args) > 1 else "out/arch/arm64/boot/Image.gz")
out_p = Path(args[2] if len(args) > 2 else "dist/boot.img")
built_dtb = Path(opts["--dtb"]) if "--dtb" in opts else None

PAGE = 2048
HDR_V2_SIZE = 1660


def align(n, a=PAGE):
    return (n + a - 1) // a * a


d = stock_p.read_bytes()
magic, ksize, kaddr, rsize, raddr, ssize, saddr, tags, page, hv, osver = \
    struct.unpack_from("<8s10I", d, 0)
assert magic == b"ANDROID!", magic
assert page == PAGE, page
assert hv == 2, hv

kernel_off = align(64)
ramdisk_off = align(kernel_off + ksize)
second_off = align(ramdisk_off + rsize)
append_off = align(second_off + ssize)
assert ssize == 0, ssize

footer_magic = d[-64:-60]
orig_size = int.from_bytes(d[-52:-44], "big")
vbmeta_off = int.from_bytes(d[-44:-36], "big")
vbmeta_size = int.from_bytes(d[-36:-28], "big")
assert footer_magic == b"AVBf", footer_magic
assert vbmeta_off == orig_size, (hex(vbmeta_off), hex(orig_size))

appended = d[append_off:orig_size]
tbl = struct.unpack_from(">8I", appended, 0)
assert tbl[0] == 0xD7B7AB1E, hex(tbl[0])
assert tbl[2] == 0x20 and tbl[4] == 1 and tbl[5] == 0x20, tbl
dt_size, dt_off = struct.unpack_from(">2I", appended, 32)
assert dt_off == 0x40 and tbl[1] == dt_off + dt_size, (dt_size, dt_off, tbl[1])
assert appended[dt_off:dt_off + 4] == b"\xd0\x0d\xfe\xed"

stock_dtb = appended[dt_off:dt_off + dt_size]
print(f"stock dtb  : {dt_size} bytes, sha256 {hashlib.sha256(stock_dtb).hexdigest()}")
if built_dtb is not None:
    built = built_dtb.read_bytes()
    if built == stock_dtb:
        print(f"dtb match  : {built_dtb} is identical to the stock dtb")
    else:
        print(f"dtb differ : {built_dtb} does not match the stock dtb "
              f"(built sha256 {hashlib.sha256(built).hexdigest()})")

k = kernel_p.read_bytes()
assert k[:2] == b"\x1f\x8b", "kernel is not gzip"

hdr = bytearray(d[:HDR_V2_SIZE])
struct.pack_into("<I", hdr, 8, len(k))

out = bytearray()
out += bytes(hdr)
out += b"\0" * (align(len(hdr)) - len(hdr))
out += k
out += b"\0" * (align(len(k)) - len(k))
out += d[ramdisk_off:ramdisk_off + rsize]
out += b"\0" * (align(rsize) - rsize)
out += appended
out += b"\0" * (align(len(out)) - len(out))

out_p.parent.mkdir(parents=True, exist_ok=True)
out_p.write_bytes(bytes(out))

print(f"stock      : {stock_p} ({len(d)} bytes)")
print(f"  header v{hv} page {page} kernel {ksize} ramdisk {rsize}")
print(f"  kernel@{kernel_off:#x} ramdisk@{ramdisk_off:#x} appended@{append_off:#x} "
      f"orig_size={orig_size:#x} vbmeta={vbmeta_off:#x}+{vbmeta_size:#x}")
print(f"new kernel : {kernel_p} ({len(k)} bytes)")
print(f"output     : {out_p} ({len(out)} bytes)")
print(f"sha256     : {hashlib.sha256(bytes(out)).hexdigest()}")
