# 🍎 Emoji Extractor

**by Alek Borisov**

![macOS Golden Gate](https://img.shields.io/badge/macOS-Golden%20Gate-000000?logo=apple&logoColor=white)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Version 1.1](https://img.shields.io/badge/version-1.1-FF9800)
![License: All Rights Reserved](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

Save every emoji in Apple Color Emoji as a full-resolution PNG named after the emoji itself, like `eagle.png` or `waving hand - medium skin tone.png`, from a colorful orange-themed terminal interface. Everything the tool needs runs in a temporary Python environment that is deleted afterwards, so your Python installation and Xcode setup are never touched.

> **New in 1.1:** macOS Golden Gate support, clean names that work on every system, one folder of 160 px PNGs, a fresh result on every run, and nothing left behind. See the [changelog](CHANGELOG.md).

## ✨ Features

- **Apple's own names.** Every file is named with the emoji name macOS itself uses, skin tones included.
- **Names that work everywhere.** The same files work unchanged on macOS, Windows, Linux, BSD and GNU Hurd, and on USB drives.
- **Full resolution.** Saves the largest size in the font (160 px on macOS Golden Gate). Apple's PNGs are copied byte for byte.
- **Every emoji.** Handles all emoji in Unicode Emoji 17.0: flags, keycaps, families and every skin-tone combination.
- **A fresh result every run.** Each run builds a new `Emojis` folder. If a run is interrupted, your previous results stay exactly as they were.
- **Nothing left behind.** The temporary environment, its downloads and its temporary files are deleted when the run ends, even after Ctrl-C. There's nothing to uninstall.
- **Read-only and careful.** The system font is only read, never changed, and an `Emojis` folder holding your own files is never replaced.

## 📋 Requirements

- **macOS Golden Gate** (macOS 27)
- **Python 3.9 or newer.** The `python3` from Apple's Command Line Tools works. If it's missing, run `xcode-select --install`.
- **An internet connection** to download the packages into the temporary environment.

## 🚀 Quick start

```sh
git clone https://github.com/Aleksandar-Borisov/emoji-extractor.git
cd emoji-extractor
sh emoji-extractor.sh
```

When it's done, open the results:

```sh
open Emojis
```

**Without Git:** download `emoji-extractor.sh` and `emoji-extractor.py` into the same folder and run the `.sh` file from Terminal, for example `sh ~/Downloads/emoji-extractor.sh`. The `Emojis` folder is always created next to the two files.

> [!TIP]
> If macOS asks whether Terminal may access the folder, click **Allow**.

### Options

| Option | What it does |
| --- | --- |
| `--theme orange` | Orange gradient (default) |
| `--theme mono` | Shades of grey |
| `--theme high-contrast` | Bright white, yellow and cyan |
| `-h`, `--help` | Show the help text |

Example: `sh emoji-extractor.sh --theme mono`

## 📂 Output

```text
emoji-extractor/
├── emoji-extractor.sh
├── emoji-extractor.py
└── Emojis/
    ├── A button blood type.png
    ├── eagle.png
    ├── flag - United States.png
    ├── keycap - asterisk.png
    ├── waving hand.png
    ├── waving hand - medium skin tone.png
    └── …
```

- **Names** come from Apple's emoji name list on your Mac, turned into file names that work on every system (see below).
- **Skin tones** get their own names. If Apple's list has no name for a combination, one is built the same way Unicode names it.
- **Same name, different image:** the second one is saved as `name 2.png`. Exact duplicates are left out.
- **One folder for everything.** Anything in the font that isn't clearly a single emoji is saved alongside the rest, named after its glyph in the font, and the summary at the end lists those files.

### File names that work everywhere

| In Apple's name | In the file name | Example |
| --- | --- | --- |
| Colon or comma | Hyphen with spaces around it | `flag: United States` → `flag - United States.png` |
| Accented letters | Plain letters | `flag: Côte d’Ivoire` → `flag - Cote d'Ivoire.png` |
| `&` `*` `#` | `and`, `asterisk`, `number sign` | `keycap: #` → `keycap - number sign.png` |
| Brackets, quotation marks, `!` | Left out | `A button (blood type)` → `A button blood type.png` |

File names contain only letters, digits, spaces, hyphens, periods and apostrophes. They never start with a hyphen or a period, avoid names Windows reserves such as `CON` and `NUL`, and are at most 120 characters long, so full paths stay within Windows' length limit.

> [!IMPORTANT]
> Each run replaces the `Emojis` folder. Copy out anything you want to keep before running it again.

## 🛠️ How it works

1. **Temporary environment.** `emoji-extractor.sh` creates a Python virtual environment in your system's temporary folder and installs Pillow, fontTools, Rich and pyfiglet into it. pip's download cache is turned off, and its temporary files stay inside that environment.
2. **Reading the font.** `emoji-extractor.py` opens `/System/Library/Fonts/Apple Color Emoji.ttc` read-only and decodes only its largest bitmap size.
3. **Images.** Apple's PNGs are saved exactly as stored. Apple's compressed `emjc` images are decoded with the LZFSE decompressor built into macOS, and JPEG, TIFF, GIF or BMP images are converted to PNG. Glyphs that reuse or mirror another glyph's image are followed. Anything that can't be converted is listed at the end instead of being saved.
4. **Names.** Emoji names come from Apple's CoreEmoji framework. If they can't be read, Unicode's character names are used.
5. **Safe swap.** Everything is written to a hidden folder first and only becomes `Emojis` once it's complete, so an interrupted run never leaves a half-finished folder.
6. **Cleanup.** The temporary environment is deleted, and the run ends with "Temporary environment removed."

## 🧯 Troubleshooting

| Message or situation | What to do |
| --- | --- |
| `python3 not found` | Install Apple's Command Line Tools with `xcode-select --install`, then run again. |
| `… holds files this script didn't make` | Your `Emojis` folder contains files the tool didn't create. Move them somewhere else and run again. |
| `emoji-extractor.py has to be in the same folder as this script` | Put both files in one folder. If your browser renamed a download (for example to `emoji-extractor (1).py`), rename it back. |
| The package download fails | Check your internet connection and run again. A failed attempt leaves nothing behind. |
| The summary lists images that aren't clearly one emoji, or images that failed | Open an issue and paste the summary from the end of the run, so the names can be improved. |

**Exit codes:** `0` everything saved, `1` couldn't run or was stopped, `2` finished but some images couldn't be saved (or an option was mistyped), `130` stopped with Ctrl-C while running `emoji-extractor.sh`.

## ⚖️ Legal & usage notes

- This tool reads the Apple Color Emoji font installed on your Mac. **You are responsible for complying with Apple's macOS license terms and the font's licensing.** This project makes no representation or warranty.
- **Do not** redistribute extracted images beyond personal or internal use without confirming that you have the rights to do so.
- All emoji images and names remain the intellectual property of their respective copyright holders.
- Apple, macOS and Apple Color Emoji are trademarks of Apple Inc. This project is not affiliated with or endorsed by Apple.

## 🚫 Restrictions

By running or distributing this tool, you agree **not** to:

- modify or fork the extraction logic itself,
- embed or integrate the code into other software products,
- use the extracted images for large-scale redistribution, resale, or AI training datasets.

All rights reserved by the author. For any other use, **ask for written permission** first.

## 📜 License

**All Rights Reserved** – see [LICENSE](LICENSE).
Permission is granted to **use** and **share** this tool, unmodified, for personal or internal purposes only.
