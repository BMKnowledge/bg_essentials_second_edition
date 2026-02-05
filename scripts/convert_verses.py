#!/usr/bin/env python3
"""
convert_verses.py

Robust converter for \Verse[ref]{SA}{EN} blocks, including nested braces in EN
(e.g., footnotes containing \textit{...}).

Features:
1) Append verse ref to end of translation: "... (2.39)"
2) If EN begins with "X said:" or "X says:", force a line break after ":".
3) Leading \hspace*{...} in EN becomes \quad for visible indent in EPUB.
4) Extract \footnote{...} inside EN (supports nested braces) and emit AFTER the verse env.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# ------------ small regex helpers (safe) ------------

HSPACE_CMD_RE = re.compile(r"""\\hspace\*?\{[^}]*\}""", re.DOTALL)
LEADING_HSPACE_RE = re.compile(r"""^\s*\\hspace\*?\{[^}]*\}\s*""", re.DOTALL)

SPEAKER_LINE_RE = re.compile(
    r"""^(?P<who>.+?)\s+(?P<verb>said|says)\s*:\s+(?P<rest>.+)$""",
    re.IGNORECASE | re.DOTALL,
)

INDENT_LATEX = r"\quad "


def strip_all_hspace(s: str) -> str:
    return HSPACE_CMD_RE.sub("", s)


def had_leading_hspace(s: str) -> bool:
    return bool(LEADING_HSPACE_RE.search(s))


# ------------ brace-aware parsing ------------

def parse_optional_bracket(s: str, i: int) -> Tuple[Optional[str], int]:
    """If s[i] == '[', parse up to matching ']' (no nesting)."""
    if i >= len(s) or s[i] != "[":
        return None, i
    j = s.find("]", i + 1)
    if j == -1:
        raise ValueError("Unclosed [ref] in \\Verse")
    return s[i + 1 : j], j + 1


def parse_braced_arg(s: str, i: int) -> Tuple[str, int]:
    """
    Parse a LaTeX braced argument starting at s[i] == '{', supporting nested braces.
    Returns (content_inside_braces, next_index_after_closing_brace).
    """
    if i >= len(s) or s[i] != "{":
        raise ValueError(f"Expected '{{' at position {i}")

    depth = 0
    j = i
    while j < len(s):
        ch = s[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # content is between i+1 and j-1
                return s[i + 1 : j], j + 1
        j += 1

    raise ValueError("Unclosed {arg} while parsing \\Verse")


def skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


# ------------ verse formatting helpers ------------

def split_latex_lines(sa: str) -> List[str]:
    parts = re.split(r"\s*\\\\\s*", sa.strip())
    return [p.strip() for p in parts if p.strip()]


def sa_to_verse_body(sa: str) -> str:
    sa = strip_all_hspace(sa)
    lines = split_latex_lines(sa)
    wrapped = [rf"\textit{{{line}}}" for line in lines]
    return " \\\\\n".join(wrapped)


def extract_footnotes_brace_aware(en: str) -> Tuple[str, List[str]]:
    """
    Extract all \footnote{...} occurrences from EN, supporting nested braces.
    Returns (en_without_footnotes, notes_list).
    """
    notes: List[str] = []
    out: List[str] = []
    i = 0
    while i < len(en):
        if en.startswith(r"\footnote", i):
            k = i + len(r"\footnote")
            k = skip_ws(en, k)
            if k < len(en) and en[k] == "{":
                note, k2 = parse_braced_arg(en, k)
                notes.append(note.strip())
                i = k2
                continue
        out.append(en[i])
        i += 1

    cleaned = "".join(out)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, notes


def normalize_english(en: str) -> str:
    indent = INDENT_LATEX if had_leading_hspace(en) else ""

    en = LEADING_HSPACE_RE.sub("", en)
    en = strip_all_hspace(en)

    # Turn LaTeX linebreaks into spaces (we will add our own linebreak if needed)
    en = re.sub(r"\s*\\\\\s*", " ", en)
    en = re.sub(r"\s+", " ", en).strip()

    # Force speaker line break after "said:" / "says:"
    m = SPEAKER_LINE_RE.match(en)
    if m:
        who = m.group("who").strip()
        verb = m.group("verb")
        rest = m.group("rest").strip()
        en = rf"{who} {verb}:\linebreak {rest}"

    return indent + en


def append_ref_to_translation(en_body: str, ref: str) -> str:
    ref = ref.strip()
    if not ref:
        return en_body

    # If it already ends with a ref-like (...) don’t double-append
    if re.search(r"\(\s*[\d]+(?:\.[\d]+)?(?:[–-][\d]+(?:\.[\d]+)?)?\s*\)\s*$", en_body):
        return en_body

    return f"{en_body} ({ref})"


def format_verse_block(ref: Optional[str], sa: str, en: str) -> str:
    ref = (ref or "").strip()
    sa_body = sa_to_verse_body(sa)

    # KEEP footnotes inline (do NOT extract)
    en_body = normalize_english(en)
    en_body = append_ref_to_translation(en_body, ref)

    return (
        "\n"
        r"\par" "\n"
        r"\begin{verse}" "\n"
        f"{sa_body}\n\n"
        rf"\noindent {en_body}" "\n"
        r"\end{verse}" "\n"
        r"\par" "\n"
    )

# ------------ main conversion (scan, no Verse regex) ------------

def convert_content(tex: str) -> Tuple[str, int]:
    """
    Scan through tex and convert all \Verse blocks using brace-aware parsing.
    """
    out: List[str] = []
    i = 0
    n = 0
    while i < len(tex):
        if tex.startswith(r"\Verse", i):
            j = i + len(r"\Verse")
            j = skip_ws(tex, j)

            ref = None
            if j < len(tex) and tex[j] == "[":
                ref, j = parse_optional_bracket(tex, j)
                j = skip_ws(tex, j)

            # Parse {SA}{EN}
            if j >= len(tex) or tex[j] != "{":
                # Not a real Verse invocation; copy literally
                out.append(tex[i])
                i += 1
                continue

            sa, j = parse_braced_arg(tex, j)
            j = skip_ws(tex, j)

            if j >= len(tex) or tex[j] != "{":
                # malformed; copy literally
                out.append(tex[i])
                i += 1
                continue

            en, j = parse_braced_arg(tex, j)

            out.append(format_verse_block(ref, sa, en))
            i = j
            n += 1
            continue

        out.append(tex[i])
        i += 1

    return "".join(out), n


def iter_tex_files(inputs: List[Path]) -> Iterable[Path]:
    for p in inputs:
        if p.is_dir():
            yield from sorted(p.glob("*.tex"))
        elif p.is_file() and p.suffix.lower() == ".tex":
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="One or more .tex files and/or directories containing .tex files")
    ap.add_argument("-o", "--outdir", required=True, help="Output directory for converted .tex files")
    ap.add_argument("--suffix", default=".epub.tex", help="Suffix to append to output filenames (default: .epub.tex)")
    ap.add_argument("--inplace", action="store_true", help="Overwrite input files (dangerous; use git).")
    args = ap.parse_args()

    in_paths = [Path(x) for x in args.inputs]
    outdir = Path(args.outdir)

    files = list(iter_tex_files(in_paths))
    if not files:
        print("No .tex files found.", file=sys.stderr)
        return 2

    if not args.inplace:
        outdir.mkdir(parents=True, exist_ok=True)

    total = 0
    changed_files = 0

    for f in files:
        original = f.read_text(encoding="utf-8")
        converted, n = convert_content(original)
        total += n
        if n > 0:
            changed_files += 1

        if args.inplace:
            f.write_text(converted, encoding="utf-8")
            print(f"[inplace] {f}: converted {n} verse(s)")
        else:
            out_path = outdir / (f.stem + args.suffix)
            out_path.write_text(converted, encoding="utf-8")
            print(f"{f} -> {out_path}: converted {n} verse(s)")

    print(f"\nDone. Converted {total} verse(s) across {changed_files}/{len(files)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())