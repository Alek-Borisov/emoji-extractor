# 📝 Changelog

All notable changes to Emoji Extractor are listed here.

## 1.1 – 2026-09-19

### 🍎 macOS Golden Gate compatibility

Emoji Extractor 1.1 supports **macOS Golden Gate (macOS 27)**.

- Runs on the Python 3.9 that comes with Apple's Command Line Tools. Nothing is installed globally.
- Decompresses with the LZFSE decompressor built into macOS, so no package has to be compiled during setup.
- Handles every emoji in Unicode Emoji 17.0, including the new mixed skin tones for people with bunny ears and people wrestling.
- Reads Apple's emoji names from the CoreEmoji framework whether macOS stores them as `AppleName.strings` or `AppleName.loctable`, in binary or text form.

### ✨ Highlights

- **File names that work everywhere.** Just the emoji's name, like `flag - United States.png`, in plain characters that work unchanged on macOS, Windows, Linux, BSD and GNU Hurd.
- **Skin tones have names.** `waving hand - medium skin tone.png` instead of `waving hand-1a2b3c4d.png`-style names that don't say which tone is which.
- **One folder, full resolution.** The largest size (160 px) in a single `Emojis` folder with no subfolders, instead of a copy of every emoji in every size.
- **A fresh result every run.** Re-running no longer piles up extra copies, and an interrupted run leaves your previous results untouched.
- **Nothing left behind.** The temporary environment is removed even after Ctrl-C or a failed download, and pip keeps no cache.
- **No more crashes.** An image the tool can't handle is skipped and listed with the reason instead of stopping the run.
- **Fewer dependencies.** Four packages instead of six, and nothing to compile.

### ➕ Added

- Names for every skin-tone variant, following Unicode's naming (`kiss - woman - man - light skin tone - dark skin tone.png`). If Apple's list has no name for a combination, it's built the same way Unicode names it.
- Names for the 12 two-person emoji that only exist with mixed skin tones: handshake, three kinds of holding hands, kiss, couple with heart, and three kinds each of bunny ears and wrestling.
- Anything in the font that isn't clearly a single emoji is saved in the same folder, named after its glyph in the font, instead of as files called `Unnamed`.
- A summary at the end: how many emoji were saved, where the names came from, which files aren't clearly one emoji, how many exact duplicates were left out, and every image that failed, with the reason.
- Exit codes for scripting: `0` all saved, `1` couldn't run or was stopped, `2` finished but some images failed (or an option was mistyped), `130` stopped with Ctrl-C in the runner.
- A safety check that refuses to replace an `Emojis` folder containing files the tool didn't create.
- A real `--help` with a description and every option.
- The runner checks for `python3` and `emoji-extractor.py` first and explains what to do if either is missing.
- The runner works from any folder (`sh path/to/emoji-extractor.sh`) and always puts `Emojis` next to the scripts.

### 🔄 Changed

- **`emoji-extractor.txt` is now `emoji-extractor.sh`.** Run it with `sh emoji-extractor.sh`.
- The temporary environment lives in the system's temporary folder instead of `Emojis - temp/` next to the script, and it's removed however the run ends.
- pip no longer leaves a download cache in `~/Library/Caches/pip`, and its temporary files stay inside the temporary environment.
- Only the largest size in the font (160 px) is saved, in one folder, instead of every size in `20x20` … `160x160` subfolders.
- Every run starts from a fresh `Emojis` folder, built in a hidden folder and swapped in when complete. An `Emojis` folder from 1.0 is recognized and replaced automatically.
- Apple's PNGs are saved byte for byte, and other formats are converted to real PNGs.
- When two different images share a name, the second becomes `name 2.png` instead of getting a hash suffix. Exact duplicates are left out.
- File names use only letters, digits, spaces, hyphens, periods and apostrophes, instead of keeping commas, brackets, quotation marks, symbols and accents as 1.0 did. Colons and commas become a hyphen with spaces around it (`flag - United States.png`), accents are dropped (`flag - Cote d'Ivoire.png`), `&`, `*` and `#` are spelled out, and brackets, quotation marks and `!` are left out (`A button blood type.png`).
- File names never start with a hyphen or a period, avoid names Windows reserves such as `CON` and `NUL`, and are at most 120 characters long, so full paths stay within Windows' length limit.
- Fallback names, used when Apple's name list can't be read, are readable for flags and keycaps (`flag - US`, `keycap - number sign`) instead of strings like `Regional Indicator Symbol Letter U Regional Indicator Symbol Letter S`.
- Faster: only the size being saved is decoded, and reused images are found directly instead of by searching the whole font each time.
- The code is reorganized into clear sections, and both files pass standard linters (pyflakes and ShellCheck).

### 🐛 Fixed

- Apple's compressed `emjc` images are decoded correctly. 1.0 checked for the wrong header and stopped the whole run at the first one.
- One damaged or unusual image can no longer stop the run. 1.0 crashed on images it couldn't open, and a single malformed glyph made fontTools fail on the whole emoji table.
- Files ending in `.png` are always real PNGs. 1.0 saved JPEG, TIFF and HEIC data under a `.png` name.
- Re-running no longer adds another copy of every emoji with a hash suffix.
- `--theme` works. 1.0 always used orange, whatever you picked.
- The progress bar's gradient colors the filled part of the bar instead of the empty track.
- The final count shows how many emoji were actually saved. 1.0 counted every glyph in the font, including those without an image.
- Mistyped options are reported instead of silently ignored.
- Problems reading Apple's name list are no longer silently ignored. The summary always says where the names came from.
- A failed package install stops the setup with an error instead of running the tool without its packages.
- Stopping the setup with Ctrl-C no longer leaves an `Emojis - temp` folder behind.
- Stopping a run halfway no longer leaves a half-written `Emojis` folder mixed with older results.

### 🗑️ Removed

- `emoji-extractor.txt`, replaced by `emoji-extractor.sh`.
- The `pillow-heif`, `pyliblzfse` and `wheel` packages, which are no longer needed.
- The per-size subfolders.

### ✅ Tested

- Checked against a full-size test font (224 MB, nine sizes) built from all 3,944 emoji in Unicode Emoji 17.0. Every file name and every pixel matched the expected result, including about 1,000 skin-tone names the tool had to build itself.
- All 3,971 files from that test copied onto a FAT32 disk, which enforces Windows' file-name rules, with every name unchanged.
- 23 stress tests for the extractor on Python 3.9 and 3.12, covering Ctrl-C, closing the terminal, force quitting, re-runs, damaged fonts, 500 different images sharing one name, and 60,000 random glyph names.
- 24 tests for the runner under `sh`, `bash`, and the same bash 3.2 that macOS uses for `sh`. Nothing was left in the temporary folder, the home folder or next to the scripts, even after Ctrl-C or a failed download.

### ⬆️ Upgrading from 1.0

1. Replace `emoji-extractor.py`, add `emoji-extractor.sh`, and delete `emoji-extractor.txt`.
2. Copy anything you want to keep out of your old `Emojis` folder.
3. Run `sh emoji-extractor.sh`. The 1.0 folder with its size subfolders is replaced by the new layout.
4. If an `Emojis - temp` folder is left over from 1.0, you can delete it.

## 1.0

- First release. Extracts every glyph of Apple Color Emoji in every size into `Emojis/<size>x<size>/`, named with Apple's emoji names, with an orange terminal interface. `emoji-extractor.txt` sets up and removes a temporary virtual environment.
