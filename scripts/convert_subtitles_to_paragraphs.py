#!/usr/bin/env python3
"""
patch_chapters.py

For files named chapter_XX.tex (e.g., chapter_04.tex), convert:

  \chapter{...}\label{...}
  \chaptersubtitle{Subtitle}

into:

  \chapter{...}\label{...}
  \noindent\textbf{CHAPTER XX}\par
  \paragraph*{\MakeUppercase{Subtitle}}

Notes:
- XX is taken from the filename (chapter_04.tex -> "04", chapter_11.tex -> "11").
- Preserves whatever is inside \chapter{...}\label{...}.
- Overwrites files in-place.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("./content")  # change if needed

# Match:
# \chapter{Title}\label{label}
# \chaptersubtitle{Subtitle}
CHAPTER_BLOCK_RE = re.compile(
    r"""
    (?P<chapterline>\\chapter\{[^\}]+\}\s*\\label\{[^\}]+\})   # \chapter{...}\label{...}
    \s*
    \\chaptersubtitle\{(?P<subtitle>[^\}]*)\}                  # \chaptersubtitle{...}
    """,
    re.MULTILINE | re.VERBOSE,
)



FILENAME_RE = re.compile(r"^chapter_(\d{2})\.tex$", re.IGNORECASE)


def transform(text: str, chapter_num: int) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        chapterline = m.group("chapterline").rstrip()
        subtitle = m.group("subtitle").strip()
        return (
            f"{chapterline}\n"
            f"\\noindent\\textbf{{CHAPTER {chapter_num}}}\\par\n"
            f"\\paragraph*{{\\MakeUppercase{{{subtitle}}}}}"
        )

    new_text, n = CHAPTER_BLOCK_RE.subn(repl, text)
    return new_text, n


def main() -> int:
    total_files = 0
    changed_files = 0

    for path in ROOT.rglob("chapter_*.tex"):
        m = FILENAME_RE.match(path.name)
        if not m:
            continue

        chapter_num = int(m.group(1))  # 🔑 DROP LEADING ZERO HERE
        total_files += 1

        original = path.read_text(encoding="utf-8")
        new_text, changes = transform(original, chapter_num)

        if changes:
            path.write_text(new_text, encoding="utf-8")
            print(f"[UPDATED] {path} — {changes} change(s)")
            changed_files += 1
        else:
            print(f"[SKIP]    {path} — no \\chaptersubtitle block found")

    print(f"\nDone. {changed_files}/{total_files} file(s) updated.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())