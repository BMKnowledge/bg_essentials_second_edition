#!/usr/bin/env python3
# convert_footnotes.py

import re
from pathlib import Path

def extract_braced(text: str, start: int):
    """
    Extracts content inside nested braces { ... }.
    Returns (content, index_after_closing_brace).
    """
    if start >= len(text) or text[start] != '{':
        raise ValueError("extract_braced: start is not at '{'")
    depth = 0
    i = start
    content_start = start + 1
    while i < len(text):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[content_start:i], i + 1
        i += 1
    raise ValueError("Unbalanced braces in footnotetext")

def skip_ws_and_comments(text: str, idx: int) -> int:
    """
    Skips whitespace and LaTeX comments (%) to find the next meaningful character.
    """
    n = len(text)
    i = idx
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if text[i] == '%':
            while i < n and text[i] != '\n':
                i += 1
            continue
        break
    return i

def convert(tex: str) -> str:
    out = []
    i = 0
    n = len(tex)

    # 1. CHANGED: Updated regex to match 'customquote' instead of 'quote'
    begin_re = re.compile(r'\\begin\{customquote\}')
    end_re   = re.compile(r'\\end\{customquote\}')

    while i < n:
        m = begin_re.search(tex, i)
        if not m:
            out.append(tex[i:])
            break

        # copy text before the quote block starts
        out.append(tex[i:m.start()])

        m_end = end_re.search(tex, m.end())
        if not m_end:
            # parsing error or unclosed block; just append the rest
            out.append(tex[m.start():])
            break

        block_end = m_end.end()
        block = tex[m.start():block_end]

        # 2. REMOVED: The check for \itshape. 
        # The script previously skipped blocks without italics, 
        # preventing your example from processing.
        
        # After the quote block, gather consecutive \footnotetext{...}
        j = skip_ws_and_comments(tex, block_end)
        footnotes = []
        
        while j < n and tex.startswith(r'\footnotetext', j):
            j += len(r'\footnotetext')
            j = skip_ws_and_comments(tex, j)
            if j >= n or tex[j] != '{':
                break
            content, after = extract_braced(tex, j)
            footnotes.append(content)
            j = skip_ws_and_comments(tex, after)

        # Replace \footnotemark occurrences in order
        def replace_one(mark_match, state={'idx': 0}):
            idx = state['idx']
            if idx < len(footnotes):
                repl = r'\footnote{' + footnotes[idx] + r'}'
                state['idx'] += 1
                return repl
            return mark_match.group(0)

        # We reset state for every block to ensure counter starts at 0
        # Note: using a mutable default argument (like previous code) is risky 
        # across multiple calls if not careful, but within this scope 
        # we need a fresh counter for every block.
        class Counter:
            idx = 0
        
        def replace_scoped(match):
            if Counter.idx < len(footnotes):
                repl = r'\footnote{' + footnotes[Counter.idx] + r'}'
                Counter.idx += 1
                return repl
            return match.group(0)

        block_converted = re.sub(r'\\footnotemark\b', replace_scoped, block)

        out.append(block_converted)
        i = j  # advance past the quote block AND the consumed footnotetexts

    return ''.join(out)

def main():
    # Adjust this path if your script is not in /scripts
    root_dir = Path(__file__).resolve().parent.parent 
    content_dir = root_dir / "chapters"

    # Fallback to current directory if the specific folder doesn't exist (for testing)
    if not content_dir.exists():
        content_dir = Path('.')

    tex_files = list(content_dir.glob("*.tex"))
    
    if not tex_files:
        print(f"No .tex files found in {content_dir}")
        return

    for file_path in tex_files:
        print(f"Reading {file_path.name}...")
        tex = file_path.read_text(encoding='utf-8')
        converted = convert(tex)

        out_path = file_path.with_name(f"{file_path.name}")
        out_path.write_text(converted, encoding='utf-8')

        print(f"Saved -> {out_path.name}")

if __name__ == '__main__':
    main()