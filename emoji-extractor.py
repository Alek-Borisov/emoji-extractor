#!/usr/bin/env python3
"""🍎 Emoji Extractor by Alek Borisov

Saves every emoji in Apple Color Emoji as a PNG at the font's largest size (160 px), named
after Apple's own emoji names ("eagle.png"), into a fresh Emojis folder. emoji-extractor.sh
runs it in a temporary Python environment and removes that environment afterwards.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import itertools
import json
import plistlib
import re
import shutil
import signal
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path

import pyfiglet
from fontTools.ttLib import TTFont
from PIL import Image, ImageOps, UnidentifiedImageError
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.style import Style
from rich.text import Text

FONT = Path("/System/Library/Fonts/Apple Color Emoji.ttc")
OUT = Path("Emojis")
COREEMOJI = Path("/System/Library/PrivateFrameworks/CoreEmoji.framework/Versions/A/Resources")
NAME_SOURCES = [COREEMOJI / "en.lproj" / "AppleName.strings", COREEMOJI / "AppleName.loctable"]

THEMES = {
    "orange":        ["#FFB74D", "#FFA726", "#FF9800", "#FB8C00", "#F57C00", "#EF6C00"],
    "mono":          ["grey58", "grey66", "grey74", "grey82", "grey89", "white"],
    "high-contrast": ["bright_white", "bright_yellow", "bright_cyan"],
}


# ── Emoji names ──────────────────────────────────────────────────────────────────
ZWJ, VS15, VS16, KEYCAP = 0x200D, 0xFE0E, 0xFE0F, 0x20E3
JOINERS = {ZWJ, VS15, VS16}
TONES = {1: 0x1F3FB, 2: 0x1F3FC, 3: 0x1F3FD, 4: 0x1F3FE, 5: 0x1F3FF}  # digit in a glyph name, 0 or 6 = no tone
TONE_NAMES = {0x1F3FB: "light skin tone", 0x1F3FC: "medium-light skin tone", 0x1F3FD: "medium skin tone",
              0x1F3FE: "medium-dark skin tone", 0x1F3FF: "dark skin tone"}
# Two-person emoji that only exist with mixed skin tones, so they have no tone-less name to build on.
TONED_ONLY = {
    (0x1FAF1, 0x1FAF2): "handshake",
    (0x1F469, 0x1F91D, 0x1F469): "women holding hands",
    (0x1F469, 0x1F91D, 0x1F468): "woman and man holding hands",
    (0x1F468, 0x1F91D, 0x1F468): "men holding hands",
    (0x1F9D1, 0x2764, 0x1F48B, 0x1F9D1): "kiss: person, person",
    (0x1F9D1, 0x2764, 0x1F9D1): "couple with heart: person, person",
    (0x1F9D1, 0x1F430, 0x1F9D1): "people with bunny ears",
    (0x1F468, 0x1F430, 0x1F468): "men with bunny ears",
    (0x1F469, 0x1F430, 0x1F469): "women with bunny ears",
    (0x1F9D1, 0x1FAEF, 0x1F9D1): "people wrestling",
    (0x1F468, 0x1FAEF, 0x1F468): "men wrestling",
    (0x1F469, 0x1FAEF, 0x1F469): "women wrestling",
}
# Apple names glyphs like u1F600, u1F44B.3 (one skin tone) or u1F9D1_u1F91D_u1F9D1.12 (two), ZWJs left out.
CP_PART = re.compile(r"u([0-9A-Fa-f]{4,6})")        # one code point: u1F600
AGL_PART = re.compile(r"uni((?:[0-9A-Fa-f]{4})+)")  # BMP code points: uni263A, uni0023FE0F
TONE_TOKEN = re.compile(r"[0-6]{1,2}")


def _read_plist(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        return plistlib.loads(raw)
    except Exception:  # old-style text .strings, let macOS' plutil convert it
        out = subprocess.run(["plutil", "-convert", "json", "-o", "-", str(path)], capture_output=True, check=True)
        return json.loads(out.stdout)


class AppleNames:
    """Apple's English emoji names from CoreEmoji, keyed by the sequence without ZWJ/VS15/VS16."""

    def __init__(self, sources: list[Path]):
        self.table: dict[tuple[int, ...], str] = {}
        self.source = None
        for path in sources:
            try:
                data = _read_plist(path)
            except Exception:
                continue
            if isinstance(data, dict) and isinstance(data.get("en"), dict):  # .loctable: {locale: {emoji: name}}
                data = data["en"]
            if not isinstance(data, dict):
                continue
            for seq, name in data.items():
                if isinstance(seq, str) and isinstance(name, str) and seq and name.strip():
                    self.table.setdefault(self.key(map(ord, seq)), name.strip())
            if self.table:
                self.source = f"{path.name} ({len(self.table):,} names)"
                break

    @staticmethod
    def key(cps) -> tuple[int, ...]:
        return tuple(c for c in cps if c not in JOINERS)

    def lookup(self, cps):
        return self.table.get(self.key(cps))


def _unicode_label(base: list[int]) -> str:
    """Fallback name when Apple's list doesn't know an emoji."""
    if len(base) == 2 and all(0x1F1E6 <= c <= 0x1F1FF for c in base):
        return "flag: " + "".join(chr(c - 0x1F1E6 + 65) for c in base)
    if len(base) > 2 and base[0] == 0x1F3F4 and all(0xE0020 <= c <= 0xE007F for c in base[1:]):
        return "flag: " + "".join(chr(c - 0xE0000) for c in base[1:-1])
    if len(base) > 1 and base[-1] == KEYCAP:
        return "keycap: " + "".join(map(chr, base[:-1]))
    return ", ".join(unicodedata.name(chr(c), f"U+{c:04X}").lower() for c in base)


def _tone_label(label: str, tones: list[int]) -> str:
    """CLDR-style: 'waving hand: medium skin tone', 'man: medium skin tone, red hair',
    'kiss: woman, man, light skin tone, dark skin tone'."""
    tone = ", ".join(dict.fromkeys(TONE_NAMES[t] for t in tones))  # two people with the same tone: name it once
    if ":" not in label:
        return f"{label}: {tone}"
    if len(tones) == 1:
        head, _, rest = label.partition(":")
        return f"{head}: {tone}, {rest.strip()}"
    return f"{label}, {tone}"


def parse_glyph_name(glyph: str):
    """'u1F44B.3' → ([0x1F44B], ['3']). None unless the name starts with valid code points."""
    head, *tokens = glyph.split(".")
    cps = []
    for part in head.split("_"):
        agl, one = AGL_PART.fullmatch(part), CP_PART.fullmatch(part)
        if agl:
            cps += [int(agl.group(1)[i:i + 4], 16) for i in range(0, len(agl.group(1)), 4)]
        elif one:
            cps.append(int(one.group(1), 16))
        else:
            return None
    if any(c > 0x10FFFF or 0xD800 <= c <= 0xDFFF for c in cps):
        return None
    return cps, [t for t in tokens if t]


def emoji_name(glyph: str, names: AppleNames):
    """'u1F44B.3' → ('waving hand: medium skin tone', []), 'u1F46E.W' → ('police officer', ['W']).

    The list holds name parts that couldn't be interpreted. None when the glyph isn't an emoji
    (.notdef, a lone ZWJ, silhouettes …)."""
    parsed = parse_glyph_name(glyph)
    if parsed is None:
        return None
    cps, tokens = parsed
    base, mods = [], {}
    for cp in cps:
        if cp in JOINERS:
            continue
        if cp in TONE_NAMES and base:  # explicit modifier, e.g. u1F44B_u1F3FB
            mods[len(base) - 1] = cp
        else:
            base.append(cp)
    if not base:  # a ZWJ or variation selector on its own
        return None
    extra, toned = [], False
    for token in tokens:
        if not toned and TONE_TOKEN.fullmatch(token) and (len(token) == 1 or len(base) > 1):
            toned = True  # .3 = one skin tone, .12 = first and last person's tones
            for slot, digit in zip((0, len(base) - 1), map(int, token)):
                if digit in TONES:
                    mods[slot] = TONES[digit]
        else:
            extra.append(token)

    label = names.lookup(base) or TONED_ONLY.get(tuple(base)) or _unicode_label(base)
    if mods:
        toned_seq = []
        for i, cp in enumerate(base):
            toned_seq += [cp, mods[i]] if i in mods else [cp]
        label = names.lookup(toned_seq) or _tone_label(label, [mods[k] for k in sorted(mods)])
    return label, extra


# Names that work the same on macOS, Windows, Linux, BSD and GNU Hurd: plain letters, digits, spaces,
# hyphens, periods and apostrophes. Separators become " - " and symbols are spelled out.
PORTABLE = str.maketrans({
    ":": " - ", ",": " - ", ";": " - ", "/": " - ", "\\": " - ", "|": " - ",
    "&": " and ", "*": " asterisk ", "#": " number sign ",
    "‘": "'", "’": "'", "ʼ": "'", "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D",
    "ł": "l", "Ł": "L", "ı": "i", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th",
})
WINDOWS_DEVICES = re.compile(r"(con|prn|aux|nul|com[0-9]|lpt[0-9])", re.IGNORECASE)


def safe(text: str, limit: int = 120) -> str:
    """A file name that works on macOS, Windows, Linux, BSD and GNU Hurd alike.

    'flag: Côte d’Ivoire' → "flag - Cote d'Ivoire", 'kiss: woman, man' → 'kiss - woman - man',
    'A button (blood type)' → 'A button blood type', 'keycap: *' → 'keycap - asterisk'."""
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))  # é → e
    text = re.sub(r"[^A-Za-z0-9 .'-]+", " ", text.translate(PORTABLE))  # brackets, quotes, ! ? and the rest
    text = re.sub(r"(?: -)+ ", " - ", " ".join(text.split()) + " ")  # single spaces, one " - " at a time
    text = text[:limit].strip(" .-'")  # never hidden, never starts with '-', never ends with '.'
    head, dot, tail = text.partition(".")
    if WINDOWS_DEVICES.fullmatch(head.strip()):  # CON, NUL, COM1 … are reserved names on Windows
        text = f"{head.strip()} emoji{dot}{tail}"
    return text or "unnamed"


def plan_names(glyphs, names: AppleNames) -> dict[str, tuple[str, bool]]:
    """glyph → (file name without extension, whether the glyph is clearly one emoji)."""
    plan = {}
    for glyph in glyphs:
        try:
            info = emoji_name(glyph, names)
        except Exception:  # an unexpected glyph name must never stop the run
            info = None
        if info is None:  # not an emoji: a tidied version of the glyph's own name
            plan[glyph] = (safe(re.sub(r"[._]+", " ", glyph)), False)
        else:
            label, extra = info
            plan[glyph] = (safe(", ".join([label, *extra])), not extra)
    return plan


# ── The font's biggest bitmaps ───────────────────────────────────────────────────
RASTER = {"jpg ", "tiff", "gif ", "bmp ", "heic", "avif"}  # converted to PNG with Pillow


def largest_strike(font: TTFont):
    """Reads only the biggest sbix strike: (ppem, {glyph name: (graphic type, data)}) for glyphs with an image."""
    raw = memoryview(font.getTableData("sbix"))
    order = font.getGlyphOrder()
    count = struct.unpack_from(">I", raw, 4)[0]
    strikes = {struct.unpack_from(">H", raw, off)[0]: off for off in struct.unpack_from(f">{count}I", raw, 8)}
    if not strikes:
        raise ValueError("the sbix table has no images")
    ppem = max(strikes)
    start = strikes[ppem]
    offsets = struct.unpack_from(f">{len(order) + 1}I", raw, start + 4)
    glyphs = {}
    for gid, name in enumerate(order):
        a, b = start + offsets[gid], start + offsets[gid + 1]
        if b - a > 8:  # 8-byte header (origin x/y, graphic type), then the image
            glyphs[name] = (bytes(raw[a + 4:a + 8]).decode("latin-1"), raw[a + 8:b])
    return ppem, glyphs


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class Images:
    """Turns glyphs into PNG bytes, following Apple's dupe/flip references."""

    def __init__(self, glyphs: dict, order: list[str]):
        self.glyphs, self.order, self.cache = glyphs, order, {}

    def get(self, name: str, depth: int = 0):
        if name in self.cache:
            return self.cache[name]
        if depth > 16:
            raise ValueError("dupe/flip reference loop")
        gtype, data = self.glyphs[name]
        if gtype in ("dupe", "flip"):
            if len(data) < 2 or struct.unpack_from(">H", data)[0] >= len(self.order):
                raise ValueError("broken reference to another glyph")
            target = self.order[struct.unpack_from(">H", data)[0]]
            if target not in self.glyphs:
                raise ValueError(f"points at {target}, which has no image")
            result = self.get(target, depth + 1)
            if gtype == "flip":
                result = to_png(ImageOps.mirror(Image.open(io.BytesIO(result)).convert("RGBA")))
        elif gtype == "png ":
            result = data  # Apple's original PNG, untouched
        elif gtype == "emjc":
            result = to_png(decode_emjc(bytes(data)))
        elif gtype in RASTER:
            try:
                result = to_png(Image.open(io.BytesIO(data)))
            except UnidentifiedImageError:
                raise ValueError(f"unreadable {gtype.strip()} image") from None
        else:
            raise ValueError(f"unsupported image type {gtype!r}")
        self.cache[name] = result
        return result


# ── emjc, Apple's LZFSE-compressed sbix format ──────────────────────────────────
# Layout as documented by github.com/cc4966/emjc-decoder: a 16-byte header ("emj1", version,
# flags, width, height, appendix length, padding) followed by an LZFSE stream holding an alpha
# plane, one filter byte per row, zigzag-coded colour residuals and a sparse correction list.

def decode_emjc(blob: bytes) -> Image.Image:
    if blob[:4] != b"emj1":
        raise ValueError("emjc data without the 'emj1' header")
    width, height, extra = struct.unpack_from("<3H", blob, 8)
    if not width or not height:
        raise ValueError("emjc image without a size")
    size = width * height * 4 + height + extra
    raw = lzfse_decompress(blob[16:], size)
    if len(raw) != size:
        raise ValueError(f"emjc payload is {len(raw)} bytes, expected {size}")
    return Image.frombuffer("RGBA", (width, height), emjc_unfilter(raw, width, height, extra), "raw", "BGRA", 0, 1)


def _half(n: int) -> int:
    """C-style n / 2, truncating toward zero (Python's // floors instead)."""
    return -((-n) >> 1) if n < 0 else n >> 1


def _u8(n: int) -> int:
    """C's `n < 0 ? n % 257 + 257 : n % 257` stored into a uint8."""
    return (n % 257 if n >= 0 else 257 - (-n) % 257) & 0xFF


def emjc_unfilter(raw: bytes, w: int, h: int, extra: int) -> bytes:
    """Rebuild BGRA pixels from the decompressed emjc planes (byte-identical to the C reference)."""
    n = w * h
    alpha, filters = raw[:n], raw[n:n + h]
    rgb, appendix = raw[n + h:4 * n + h], raw[4 * n + h:4 * n + h + extra]
    buf = [0] * (3 * n)
    pos = 0
    for a in appendix:  # sparse +128/+256/+384 corrections
        pos += a >> 2
        if pos >= 3 * n:
            break
        buf[pos] = 128 * (a & 3)
        pos += 1
    for k, v in enumerate(rgb):  # zigzag residuals, odd bytes are negative
        buf[k] = -(v >> 1) - buf[k] if v & 1 else (v >> 1) + buf[k]
    out = bytearray(4 * n)
    up = 3 * w
    for y in range(h):
        f = filters[y]
        for x in range(w):
            j = 3 * (y * w + x)
            if f in (1, 2, 3, 4) and (x or y):  # PNG-like predictors
                if f == 1 and x and y:
                    lu = buf[j - up - 3]
                    s = j - up if abs(buf[j - 3] - lu) < abs(buf[j - up] - lu) else j - 3
                elif f == 4 and x and y:
                    s = None
                    for c in range(3):
                        buf[j + c] += _half(buf[j - 3 + c] + buf[j - up + c] + 1)
                elif f == 2:
                    s = j - 3 if x else None
                elif f == 3:
                    s = j - up if y else None
                else:  # filters 1 and 4 on the first row or column
                    s = j - 3 if x else j - up
                if s is not None:
                    buf[j] += buf[s]
                    buf[j + 1] += buf[s + 1]
                    buf[j + 2] += buf[s + 2]
            base, p, q = buf[j], buf[j + 1], buf[j + 2]
            if p < 0 and q < 0:
                r, g, b = base + _half(p) - _half(q + 1), base + _half(q), base - _half(p + 1) - _half(q + 1)
            elif p < 0:
                r, g, b = base + _half(p) - _half(q), base + _half(q + 1), base - _half(p + 1) - _half(q)
            elif q < 0:
                r, g, b = base + _half(p + 1) - _half(q + 1), base + _half(q), base - _half(p) - _half(q + 1)
            else:
                r, g, b = base + _half(p + 1) - _half(q), base + _half(q + 1), base - _half(p) - _half(q)
            o = 4 * (y * w + x)
            out[o], out[o + 1], out[o + 2], out[o + 3] = _u8(b), _u8(g), _u8(r), alpha[y * w + x]
    return bytes(out)


COMPRESSION_LZFSE = 0x801
_lzfse = None


def lzfse_decompress(src: bytes, size: int) -> bytes:
    """LZFSE via macOS' built-in libcompression, or the pyliblzfse package elsewhere."""
    global _lzfse
    if _lzfse is None:
        _lzfse = _find_lzfse()
    return _lzfse(src, size)


def _find_lzfse():
    try:
        fn = ctypes.CDLL("/usr/lib/libcompression.dylib").compression_decode_buffer
        fn.restype = ctypes.c_size_t
        fn.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]

        def libcompression(src: bytes, size: int) -> bytes:
            dst = ctypes.create_string_buffer(size + 1)  # one spare byte shows a stream that's too long
            n = fn(dst, size + 1, src, len(src), None, COMPRESSION_LZFSE)  # fill dst first, then read it
            return dst.raw[:n]
        return libcompression
    except (OSError, AttributeError):
        pass
    for module in ("liblzfse", "lzfse"):  # pip install pyliblzfse provides 'liblzfse'
        try:
            mod = __import__(module)
            return lambda src, size: mod.decompress(src)
        except ImportError:
            continue

    def unavailable(src: bytes, size: int) -> bytes:
        raise RuntimeError("emjc glyphs need LZFSE: run on macOS or pip install pyliblzfse")
    return unavailable


# ── Look ──────────────────────────────────────────────────────────────────────────
class GradientBar(BarColumn):
    """Progress bar whose filled part cycles through the theme colours."""

    def __init__(self, palette: list[str], **kwargs):
        super().__init__(**kwargs)
        self._colors = itertools.cycle(palette)

    def render(self, task):
        self.complete_style = self.finished_style = Style(color=next(self._colors))
        return super().render(task)


def banner(pal: list[str]) -> Panel:
    colors = itertools.cycle(pal)
    art = Group(*[Text.assemble(*[(ch, Style(color=next(colors), bold=True)) for ch in line])
                  for line in pyfiglet.figlet_format("Emoji Extractor", font="slant").splitlines()])
    return Panel(Panel(art, border_style=Style(color=pal[1 % len(pal)]), box=box.DOUBLE, padding=(0, 1)),
                 border_style=Style(color=pal[2 % len(pal)]), box=box.ROUNDED, padding=(1, 2))


# ── Output folder ────────────────────────────────────────────────────────────────
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".bmp", ".heic", ".avif", ".pdf"}  # older versions


def replaceable(folder: Path) -> bool:
    """True if the folder is missing or holds nothing but results of this script or its older versions."""
    if not folder.exists():
        return True
    if not folder.is_dir():
        return False
    for entry in folder.iterdir():
        if entry.is_dir():
            if entry.name not in ("Other", "_other") and not re.fullmatch(r"\d+x\d+", entry.name):
                return False
        elif entry.name not in (".DS_Store", "index.csv") and entry.suffix.lower() not in IMAGE_SUFFIXES:
            return False
    return True


def _count(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def _why(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def _interrupted(*_):
    sys.exit("\nInterrupted.")


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="emoji-extractor",
        description="Save every Apple emoji at 160 px as a PNG named after it, into a fresh Emojis folder.")
    p.add_argument("--theme", choices=list(THEMES), default="orange")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pal = THEMES[args.theme]

    def color(i: int) -> Style:
        return Style(color=pal[i % len(pal)])

    console = Console()
    console.print(banner(pal))

    out = OUT.resolve()
    building, old = out.with_name(f".{out.name}-building"), out.with_name(f".{out.name}-old")
    if not FONT.is_file():
        console.print(Text.assemble(("Font not found: ", "bold red"), str(FONT)))
        return 1
    if not replaceable(out):
        console.print(Panel(Text(f"{out} holds files this script didn't make, so it won't replace that folder.\n"
                                 "Move them somewhere else and run it again."), border_style="red"))
        return 1
    try:
        with console.status("Reading the emoji font…", spinner_style=color(0)):
            font = TTFont(str(FONT), fontNumber=0, lazy=True)
            if "sbix" not in font:
                raise ValueError("it has no sbix table, so Apple has changed how it stores emoji")
            order = font.getGlyphOrder()
            ppem, glyphs = largest_strike(font)
            names = AppleNames(NAME_SOURCES)
            plan = plan_names(glyphs, names)
    except Exception as exc:
        console.print(Panel(Text(f"Couldn't read {FONT.name}: {_why(exc)}"), border_style="red"))
        return 1

    images = Images(glyphs, order)
    reserved = {stem.casefold() for stem, _ in plan.values()}  # every image's own name
    used, hashes, unclear, failures = set(), {}, [], []
    saved = duplicates = 0
    progress = Progress(
        SpinnerColumn(style=color(0)),
        TextColumn("[bold]{task.description}", style=color(0)),
        GradientBar(pal, bar_width=None),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    for leftover in (building, old):  # from a run that was killed halfway
        shutil.rmtree(leftover, ignore_errors=True)
    try:
        building.mkdir(parents=True)
        task = progress.add_task(f"Extracting {ppem} px", total=len(glyphs))
        with progress:
            # real emoji first, so they keep the plain name if anything else happens to share it
            for glyph in sorted(glyphs, key=lambda g: not plan[g][1]):
                gtype = glyphs[glyph][0]
                progress.advance(task)
                try:
                    data = images.get(glyph)
                    stem, clear = plan[glyph]
                    digest = hashlib.sha1(data).digest()
                    seen = hashes.setdefault(stem.casefold(), set())
                    name = stem
                    if seen:  # another image already has this name
                        if digest in seen:
                            duplicates += 1
                            continue
                        n = 2
                        while f"{stem} {n}".casefold() in reserved or f"{stem} {n}".casefold() in used:
                            n += 1
                        name = f"{stem} {n}"
                    (building / f"{name}.png").write_bytes(data)
                except Exception as exc:  # one bad glyph shouldn't sink the run
                    failures.append(f"{glyph} ({gtype.strip()}): {_why(exc)}")
                    continue
                seen.add(digest)
                used.add(name.casefold())
                saved += 1
                if not clear:
                    unclear.append(f"{name}.png")
        signals = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
        signal.pthread_sigmask(signal.SIG_BLOCK, signals)  # swap folders without being interrupted halfway
        try:
            if out.exists():
                out.rename(old)
            try:
                building.rename(out)
            except OSError:
                if old.exists():
                    old.rename(out)  # put the previous results back
                raise
        finally:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, signals)
    except Exception as exc:
        console.print(Panel(Text(f"Stopped: {_why(exc)}"), border_style="red"))
        return 1
    finally:
        shutil.rmtree(building, ignore_errors=True)
        if out.exists():
            shutil.rmtree(old, ignore_errors=True)

    lines = [(f"✔ Saved {saved:,} emoji as {ppem} px PNGs → {out}\n", color(0) + Style(bold=True)),
             f"Names: {names.source or 'Apple names file not found, used Unicode character names'}"]
    if unclear:
        sample = " · ".join(unclear[:6]) + (" · …" if len(unclear) > 6 else "")
        lines.append(f"\n{_count(len(unclear), 'image')} not clearly one emoji, named after the font's glyphs: {sample}")
    if duplicates:
        lines.append(f"\nLeft out {_count(duplicates, 'exact duplicate')}")
    console.print(Panel(Text.assemble(*lines), title="Done", border_style=color(1)))
    if failures:
        more = f"\n… and {len(failures) - 10:,} more" if len(failures) > 10 else ""
        console.print(Panel(Text("\n".join(failures[:10]) + more), title=f"{_count(len(failures), 'image')} failed",
                            border_style="red"))
    return 2 if failures else 0


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _interrupted)
    sys.exit(main())
