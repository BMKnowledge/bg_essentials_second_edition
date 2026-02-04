#!/usr/bin/env python3
import re
import unicodedata
from pathlib import Path

ROOT = Path("./frontmatter")  # change if needed

# Map LaTeX command -> label prefix
PREFIX = {
    "chapter": "chap",
    "section": "sec",
    "subsection": "subsec",
    "subsubsection": "subsubsec",
}

# Regex to find a heading command \chapter[*]?[...]{...}, capturing:
#  1: command (chapter|section|subsection|subsubsection)
#  2: optional star "*" (or None)
#  3: optional short title [ ... ] (or None)
#  4: the { ... } title text (no nested braces handling)
HEADING_RE = re.compile(
    r"""
    \\(chapter|section|subsection|subsubsection)   # 1: command
    (\*)?                                         # 2: optional star
    \s*
    (\[[^\]]*\])?                                 # 3: optional short title
    \s*
    \{([^}]*)\}                                   # 4: title text (simple)
    """,
    re.VERBOSE | re.MULTILINE | re.DOTALL,
)

# Regex to detect a label at the current scan position (after skipping ws/comments)
LABEL_AHEAD_RE = re.compile(r"""\\label\{([^}]+)\}""", re.MULTILINE)

def slugify(text: str) -> str:
    """ASCII, dash-separated slug."""
    # Normalize and strip diacritics
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase, collapse non-alnum to hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    # Avoid empty slugs
    return text or "x"

def skip_ws_and_comments(s: str, pos: int) -> int:
    """Advance pos over whitespace and full-line/inline % comments."""
    n = len(s)
    while pos < n:
        if s[pos] in (" ", "\t", "\r", "\n"):
            pos += 1
            continue
        # If at start of a comment or inline comment, skip until end of line
        if s[pos] == "%":
            while pos < n and s[pos] != "\n":
                pos += 1
            # consume the newline too (if present)
            if pos < n and s[pos] == "\n":
                pos += 1
            continue
        break
    return pos

def find_existing_label_ahead(s: str, pos: int):
    """After skipping ws/comments, check if there's an immediate \label{...}."""
    pos2 = skip_ws_and_comments(s, pos)
    m = LABEL_AHEAD_RE.match(s, pos2)
    if m:
        return m.group(1), (m.start(), m.end())
    return None, None

def unique_label(base: str, used: set[str]) -> str:
    """Ensure a label is unique across the whole project."""
    if base not in used:
        used.add(base)
        return base
    i = 2
    while True:
        candidate = f"{base}-{i}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1

def process_text(text: str, used_labels: set[str]) -> tuple[str, int]:
    """
    Scan a LaTeX document and inject labels after headings that lack one.
    Returns (updated_text, num_inserted).
    """
    out_parts = []
    last = 0
    inserted = 0

    for m in HEADING_RE.finditer(text):
        cmd = m.group(1)                # chapter/section/subsection/subsubsection
        # star = m.group(2)             # optional "*", not used but allowed
        # short = m.group(3)            # optional [..], not used
        title = (m.group(4) or "").strip()

        # Position right after the matched heading block
        after_heading = m.end()

        # Already labeled?
        existing_label, _span = find_existing_label_ahead(text, after_heading)
        if existing_label:
            continue  # keep as is

        # Build a base label
        prefix = PREFIX.get(cmd, "sec")
        base = f"{prefix}-{slugify(title)}"
        label = unique_label(base, used_labels)

        # Insert label immediately after the heading
        out_parts.append(text[last:after_heading])
        out_parts.append(f"\\label{{{label}}}")
        last = after_heading
        inserted += 1

    out_parts.append(text[last:])
    return "".join(out_parts), inserted

def collect_existing_labels(root: Path) -> set[str]:
    """Collect already-present labels to avoid collisions across files."""
    used = set()
    lab_re = re.compile(r"""\\label\{([^}]+)\}""")
    for p in root.rglob("*.tex"):
        try:
            s = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in lab_re.finditer(s):
            used.add(m.group(1))
    return used

def main():
    used_labels = collect_existing_labels(ROOT)
    total_files = 0
    changed_files = 0
    inserted_total = 0

    for path in ROOT.rglob("*.tex"):
        total_files += 1
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[SKIP] {path} (read error: {e})")
            continue

        new_text, inserted = process_text(text, used_labels)
        if inserted > 0 and new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"[UPDATED] {path} — inserted {inserted} label(s)")
            changed_files += 1
            inserted_total += inserted

    print(f"\nDone. {changed_files}/{total_files} files updated; {inserted_total} label(s) inserted.")

if __name__ == "__main__":
    main()