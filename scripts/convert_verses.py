#!/usr/bin/env python3
"""
convert_verses.py

Convert custom LaTeX \Verse[...] {SA} {EN} blocks into a Pandoc-friendly
\begin{verse}...\end{verse} structure suitable for EPUB conversion.

Changes implemented:
1) Verse number is NOT a separate line; it is appended to the END of the translation in parentheses, e.g. "... (1.12)".
2) If the English block begins with a speaker line like "Bhagavān Kṛṣṇa said:" (or "Arjuna said:", etc.),
   we force a line break after "... said:" so it becomes:
      Bhagavān Kṛṣṇa said:
      <rest of translation...>
3) Leading \hspace*{...} in the English block is converted into an explicit indentation marker,
   so you still get a visible indent in EPUB (Pandoc ignores LaTeX hspace in many cases).

Notes:
- Handles \Verse[ref]{sa}{en} and \Verse{sa}{en} (ref optional).
- SA lines split on \\ and wrapped as \textit{...}\\
- EN is kept as a single paragraph but may include ONE forced linebreak after "... said:".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


VERSE_RE = re.compile(
    r"""
    \\Verse
    (?:\[(?P<ref>[^\]]*)\])?            # optional [ref]
    \s*
    \{(?P<sa>(?:[^{}]|\{[^{}]*\})*)\}   # {sa} (1-level brace tolerance)
    \s*
    \{(?P<en>(?:[^{}]|\{[^{}]*\})*)\}   # {en}
    """,
    re.VERBOSE | re.DOTALL,
)

HSPACE_CMD_RE = re.compile(r"""\\hspace\*?\{[^}]*\}""", re.DOTALL)

# Detect a leading hspace (possibly preceded by whitespace/newlines)
LEADING_HSPACE_RE = re.compile(r"""^\s*\\hspace\*?\{[^}]*\}\s*""", re.DOTALL)

# Speaker-line detection: "... said:" / "... says:" (covers most of your cases)
SPEAKER_LINE_RE = re.compile(
    r"""^(?P<who>.+?)\s+(?P<verb>said|says)\s*:\s+(?P<rest>.+)$""",
    re.IGNORECASE | re.DOTALL,
)

# What we use for an EPUB-safe "indent" at the start of the English block.
# \quad is typically respected by Pandoc->EPUB (unlike \hspace*).
INDENT_LATEX = r"\quad "


def had_leading_hspace(s: str) -> bool:
    return bool(LEADING_HSPACE_RE.search(s))


def strip_all_hspace(s: str) -> str:
    return HSPACE_CMD_RE.sub("", s)


def split_latex_lines(sa: str) -> List[str]:
    """Split Sanskrit block on LaTeX line breaks (\\) while being robust to whitespace."""
    parts = re.split(r"\s*\\\\\s*", sa.strip())
    return [p.strip() for p in parts if p.strip()]


def sa_to_verse_body(sa: str) -> str:
    """Wrap each Sanskrit line in \textit{...} and join with \\."""
    sa = strip_all_hspace(sa)
    lines = split_latex_lines(sa)
    wrapped = [rf"\textit{{{line}}}" for line in lines]
    return " \\\\\n".join(wrapped)


def normalize_english(en: str) -> str:
    """
    - Preserve whether there was a leading \hspace*{...} to re-express as \quad.
    - Remove all \hspace commands (Pandoc often ignores them).
    - Convert LaTeX line breaks (\\) to spaces.
    - Collapse whitespace.
    - If it looks like "X said: Y", force a line break after the colon.
    """
    indent = INDENT_LATEX if had_leading_hspace(en) else ""

    en = LEADING_HSPACE_RE.sub("", en)   # remove the leading hspace command
    en = strip_all_hspace(en)            # remove any other hspace occurrences

    # Turn LaTeX linebreaks into spaces for now
    en = re.sub(r"\s*\\\\\s*", " ", en)

    # Collapse whitespace
    en = re.sub(r"\s+", " ", en).strip()

    # Force "Speaker said:" onto its own line (only when there's actual text after it)
    m = SPEAKER_LINE_RE.match(en)
    if m:
        who = m.group("who").strip()
        verb = m.group("verb")
        rest = m.group("rest").strip()
        # Use an explicit line break Pandoc respects well inside verse -> blockquote
        en = rf"{who} {verb}:\linebreak {rest}"

    return indent + en


def append_ref_to_translation(en_body: str, ref: str) -> str:
    """Append (ref) to end, unless it already appears to end with a ref-like parenthetical."""
    ref = ref.strip()
    if not ref:
        return en_body

    if re.search(r"\(\s*[\d]+(?:\.[\d]+)?(?:[–-][\d]+(?:\.[\d]+)?)?\s*\)\s*$", en_body):
        return en_body

    return f"{en_body} ({ref})"


def format_verse_block(ref: Optional[str], sa: str, en: str) -> str:
    ref = (ref or "").strip()
    sa_body = sa_to_verse_body(sa)
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


def convert_content(tex: str) -> Tuple[str, int]:
    """Convert all \Verse occurrences in a .tex string. Returns (new_text, count_converted)."""
    count = 0

    def _repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return format_verse_block(m.group("ref"), m.group("sa"), m.group("en"))

    new_tex = VERSE_RE.sub(_repl, tex)
    return new_tex, count


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
    ap.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite input files (dangerous; use git). Ignores --outdir/--suffix.",
    )
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