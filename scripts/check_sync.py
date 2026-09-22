#!/usr/bin/env python3
"""typst-note-author 与 typst-book-author 的同步校验（纯标准库，Python 3.8+）。

两个技能共享两类资产，靠注释里的人肉提醒维持同步，这里改成机检：

1. 色值——本端 template/colors.typ 的 note-colors-base 与书籍样板
   template/colors.typ 的 book-colors（primary/tint 取 book-theme 当前指向
   的主题）应逐键相同；
2. 图形样式——两端 template/figstyle.typ 的代码应相同。校验前会剥掉注释，
   并把 note-colors 归一成 book-colors，所以允许的差异只剩这两类，
   其余任何不一致都视为漂移。

任一漂移即以非零码退出并打印差异。改任一端 colors.typ / figstyle.typ 后跑：

  python scripts/check_sync.py
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOTE_ROOT = Path(__file__).resolve().parent.parent
BOOK_ROOT = NOTE_ROOT.parent / "typst-book-author"

NOTE_COLORS = NOTE_ROOT / "template" / "colors.typ"
BOOK_COLORS = BOOK_ROOT / "template" / "colors.typ"
NOTE_FIG = NOTE_ROOT / "template" / "figstyle.typ"
BOOK_FIG = BOOK_ROOT / "template" / "figstyle.typ"

RGB = re.compile(r'([\w-]+):\s*rgb\("#([0-9a-fA-F]{6})"\)')
THEME = re.compile(
    r'(\w+):\s*\(\s*primary:\s*rgb\("#([0-9a-fA-F]{6})"\),\s*'
    r'tint:\s*rgb\("#([0-9a-fA-F]{6})"\)\s*\)'
)


def read_balanced(text, start, open_ch="(", close_ch=")"):
    """从 start（指向开括号）读到配对的闭括号，返回括号内的文本。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    raise ValueError("括号未配对")


def let_block(text, name):
    """取出 `#let <name> = ( ... )` 的括号体。"""
    m = re.search(r"#let\s+" + re.escape(name) + r"\s*=\s*\(", text)
    if not m:
        raise ValueError(f"找不到 #let {name} = (")
    return read_balanced(text, m.end() - 1)


def note_colors():
    body = let_block(NOTE_COLORS.read_text(encoding="utf-8"), "note-colors-base")
    return {k: v.lower() for k, v in RGB.findall(body)}


def book_colors():
    text = BOOK_COLORS.read_text(encoding="utf-8")
    m = re.search(r'#let\s+book-theme\s*=\s*"(\w+)"', text)
    if not m:
        raise ValueError("找不到 book-theme 定义")
    themes = {
        k: (p.lower(), t.lower())
        for k, p, t in THEME.findall(let_block(text, "themes"))
    }
    if m.group(1) not in themes:
        raise ValueError(f"book-theme 指向未知主题 {m.group(1)!r}")
    primary, tint = themes[m.group(1)]
    colors = {}
    # book-colors 里 primary/tint 是主题表查找，不是字面量，逐行只收字面量项
    for line in let_block(text, "book-colors").splitlines():
        m2 = RGB.search(line)
        if m2:
            colors[m2.group(1)] = m2.group(2).lower()
    colors["primary"] = primary
    colors["tint"] = tint
    return colors


def strip_comment(line):
    """剥掉 // 行注释与行尾注释，字符串里的 // 不算。"""
    in_str = False
    esc = False
    for i in range(len(line) - 1):
        c = line[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "/" and line[i + 1] == "/":
            return line[:i]
    return line


def code_lines(path):
    """剥注释、去空行后的有效代码行；note-colors 归一成 book-colors。"""
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = strip_comment(raw).strip()
        if line:
            out.append(line.replace("note-colors", "book-colors"))
    return out


def check_colors():
    n, b = note_colors(), book_colors()
    only_note = sorted(set(n) - set(b))
    only_book = sorted(set(b) - set(n))
    diff = sorted(k for k in set(n) & set(b) if n[k] != b[k])
    if only_note or only_book or diff:
        print("✗ colors.typ 色值漂移：")
        for k in only_note:
            print(f"  仅 note 端有 {k}: #{n[k]}")
        for k in only_book:
            print(f"  仅 book 端有 {k}: #{b[k]}")
        for k in diff:
            print(f"  {k}: note #{n[k]} ≠ book #{b[k]}")
        return False
    print(f"✓ colors.typ 色值一致（{len(n)} 键，book 端按主题 {m_theme()} 解析）")
    return True


def m_theme():
    text = BOOK_COLORS.read_text(encoding="utf-8")
    return re.search(r'#let\s+book-theme\s*=\s*"(\w+)"', text).group(1)


def check_figstyle():
    nl, bl = code_lines(NOTE_FIG), code_lines(BOOK_FIG)
    if nl == bl:
        print(f"✓ figstyle.typ 代码一致（{len(nl)} 个有效行）")
        return True
    print("✗ figstyle.typ 代码漂移（已剥注释、配色字典名已归一）：")
    shown = 0
    for i in range(max(len(nl), len(bl))):
        x = nl[i] if i < len(nl) else "<缺失>"
        y = bl[i] if i < len(bl) else "<缺失>"
        if x != y:
            print(f"  有效行 {i + 1}:\n    note: {x}\n    book: {y}")
            shown += 1
            if shown >= 10:
                print("  ……（更多差异从略）")
                break
    if len(nl) != len(bl):
        print(f"  有效行数不同：note {len(nl)} ≠ book {len(bl)}")
    return False


def main():
    ok = check_colors() and check_figstyle()
    if not ok:
        sys.exit(1)
    print("同步校验通过。")


if __name__ == "__main__":
    main()
