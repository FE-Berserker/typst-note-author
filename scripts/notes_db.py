#!/usr/bin/env python3
"""typst-note-author 的关键词库与思维导图工具。

把笔记项目的关键词与结构存进 SQLite，并用 markmap（官方发行版，CDN 加载）
生成**交互式**思维导图 HTML：节点可点击折叠/展开、滚轮缩放、拖拽平移。

两个子命令（--root 指向笔记项目目录，默认当前目录）：
  sync      扫描 notes/*.typ 的 note-header（标题/日期/标签/状态/来源/摘要）
            与节标题（== / ===），全量重建 notes.db
  mindmap   从 notes.db 生成 mindmap.md（大纲）与 mindmap.html（交互导图，
            含「关键词图谱」与「笔记库」两个视图）

用法：
  python notes_db.py --root <笔记项目目录> sync
  python notes_db.py --root <笔记项目目录> mindmap
  python notes_db.py --root <笔记项目目录> mindmap --open   # 生成后直接打开浏览器

依赖：Python 3.8+（仅标准库）。查看 HTML 需联网加载 markmap 的 CDN 脚本，
导图数据本身已内嵌在 HTML 里，加载一次后缩放浏览不再请求网络。
"""

import argparse
import re
import sqlite3
import sys
import webbrowser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_NAME = "notes.db"
MD_NAME = "mindmap.md"
HTML_NAME = "mindmap.html"

# ============================================================
# 解析 .typ 笔记
# ============================================================


def read_balanced(text, start, open_ch="(", close_ch=")"):
    """从 start（指向开括号）读到配对的闭括号，返回括号内的文本。

    字符串里的括号不算数；note-header 的参数跨多行，不能按行解析。
    """
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
        elif c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def parse_string(s):
    """去引号、反转义。s 形如 "…"（含引号）。"""
    body = s.strip()
    if body.startswith('"') and body.endswith('"') and len(body) >= 2:
        body = body[1:-1]
    return body.replace('\\"', '"').replace("\\\\", "\\")


def parse_header(call_body):
    """解析 note-header 参数区，返回 dict。只认识字符串、字符串数组与
    [内容块]；theme 这类标识符参数（如 note-themes.indigo）跳过。"""
    out = {}
    for key in ("title", "date", "status", "source", "summary", "tags"):
        m = re.search(rf"\b{key}\s*:\s*", call_body)
        if not m:
            continue
        rest = call_body[m.end() :]
        if rest.lstrip().startswith('"'):
            sm = re.match(r'\s*"((?:[^"\\]|\\.)*)"', rest)
            if sm:
                out[key] = parse_string(f'"{sm.group(1)}"')
        elif rest.lstrip().startswith("("):
            arr = read_balanced(rest, rest.index("("))
            if arr is not None:
                out[key] = [parse_string(x) for x in re.findall(r'"((?:[^"\\]|\\.)*)"', arr)]
        elif rest.lstrip().startswith("["):
            arr = read_balanced(rest, rest.index("["), "[", "]")
            if arr is not None:
                out[key] = strip_inline_markup(arr)
    return out


def strip_inline_markup(t):
    """把标题/内容里的标记语法剥成纯文本。"""
    t = re.sub(r"```.*?```", "", t, flags=re.S)  # 代码块
    t = re.sub(r"`([^`]*)`", r"\1", t)  # 行内代码
    t = re.sub(r"\$([^$]*)\$", r"\1", t)  # 行内公式
    t = re.sub(r"#\w+(?:-\w+)*\([^()]*\)", "", t)  # #func(...) 调用
    t = re.sub(r"#\w+(?:-\w+)*\[[^\]]*\]", "", t)  # #func[...] 调用（如 mnote）
    t = re.sub(r"<[^<>]+>", "", t)  # <标签>
    t = t.replace("*", "").replace("__", "")
    return re.sub(r"\s+", " ", t).strip()


def parse_note(path, text):
    """从一篇笔记里取 note-header 与节标题（== / ===，跳过代码块）。"""
    m = re.search(r"#note-header\s*\(", text)
    if not m:
        return None
    body = read_balanced(text, m.end() - 1)
    head = parse_header(body) if body is not None else {}
    head["title"] = head.get("title") or path.stem

    body_wo_code = re.sub(r"```.*?```", "", text, flags=re.S)
    sections = []
    for line in body_wo_code.splitlines():
        sm = re.match(r"^(={2,3})\s+(.+?)\s*$", line)
        if sm:
            sections.append((len(sm.group(1)), strip_inline_markup(sm.group(2))))
    return head, sections


def scan_notes(root):
    notes_dir = root / "notes"
    files = sorted(p for p in notes_dir.glob("*.typ")) if notes_dir.is_dir() else []
    out = []
    for p in files:
        parsed = parse_note(p, p.read_text(encoding="utf-8"))
        if parsed:
            head, sections = parsed
            out.append((p.name, head, sections))
    return out


# ============================================================
# SQLite
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    file TEXT UNIQUE,
    title TEXT NOT NULL,
    date TEXT,
    status TEXT,
    source TEXT,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    level INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS note_keywords (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    UNIQUE (note_id, keyword_id)
);
"""


def cmd_sync(root):
    notes = scan_notes(root)
    db = root / DB_NAME
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    # 全量重建：笔记量级小，重建比逐条 upsert 简单且不会留下已删文件的残行
    for table in ("note_keywords", "keywords", "sections", "notes"):
        con.execute(f"DELETE FROM {table}")
    kw_total = 0
    for i, (fname, head, sections) in enumerate(notes, start=1):
        con.execute(
            "INSERT INTO notes(id, file, title, date, status, source, summary) VALUES (?,?,?,?,?,?,?)",
            (i, fname, head["title"], head.get("date"), head.get("status"),
             head.get("source"), head.get("summary")),
        )
        for idx, (level, text) in enumerate(sections):
            con.execute(
                "INSERT INTO sections(note_id, idx, level, text) VALUES (?,?,?,?)",
                (i, idx, level, text),
            )
        for tag in head.get("tags") or []:
            con.execute("INSERT OR IGNORE INTO keywords(name) VALUES (?)", (tag,))
            kw_id = con.execute("SELECT id FROM keywords WHERE name = ?", (tag,)).fetchone()[0]
            con.execute(
                "INSERT OR IGNORE INTO note_keywords(note_id, keyword_id) VALUES (?,?)", (i, kw_id)
            )
            kw_total += 1
    con.commit()
    n_kw = con.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
    con.close()
    print(f"[sync] {db}")
    print(f"[sync] 笔记 {len(notes)} 篇，关键词 {n_kw} 个（笔记-关键词关联 {kw_total} 条）")
    if not notes:
        print("[sync] 没扫到笔记：确认 --root 指向的目录下有 notes/*.typ")
    return notes


# ============================================================
# 思维导图（数据自本脚本，渲染交给 markmap）
# ============================================================


def sanitize(t):
    """去掉会破坏 markdown/HTML 的字符（标题里本就不该有尖括号）。"""
    return t.replace("<", "＜").replace(">", "＞").strip()


def note_label(head):
    bits = []
    if head.get("date"):
        bits.append(head["date"])
    if head.get("status"):
        bits.append(head["status"])
    inner = " · ".join(bits)
    title = sanitize(head["title"])
    return f"{title}（{inner}）" if inner else title


def build_markdown(con):
    notes = con.execute(
        "SELECT id, file, title, date, status FROM notes ORDER BY file"
    ).fetchall()
    secs = {}
    for note_id, idx, level, text in con.execute(
        "SELECT note_id, idx, level, text FROM sections ORDER BY note_id, idx"
    ):
        secs.setdefault(note_id, []).append((level, sanitize(text)))
    tags = {}
    for note_id, name in con.execute(
        "SELECT note_id, k.name FROM note_keywords nk JOIN keywords k ON k.id = nk.keyword_id"
    ):
        tags.setdefault(note_id, []).append(name)

    # 视图一：关键词 → 笔记（按关联笔记数排序，一眼看出高频关键词）
    kw_lines = ["# 关键词图谱", ""]
    kw_rows = con.execute(
        """SELECT k.name, COUNT(*) c FROM keywords k
           JOIN note_keywords nk ON nk.keyword_id = k.id
           GROUP BY k.name ORDER BY c DESC, k.name"""
    ).fetchall()
    for name, _c in kw_rows:
        kw_lines.append(f"## {sanitize(name)}")
        for note_id, _file, title, date, status in notes:
            if note_id in tags and name in tags[note_id]:
                head = {"title": title, "date": date, "status": status}
                kw_lines.append(f"- {note_label(head)}")
        kw_lines.append("")

    # 视图二：笔记 → 章节与标签（文件名顺序 = 汇总册顺序）
    note_lines = ["# 笔记库", ""]
    for note_id, _file, title, date, status in notes:
        head = {"title": title, "date": date, "status": status}
        note_lines.append(f"## {note_label(head)}")
        for level, text in secs.get(note_id, []):
            note_lines.append(("#" * (level + 1)) + " " + text)
        if note_id in tags:
            note_lines.append("### 标签")
            for t in tags[note_id]:
                note_lines.append(f"- #{sanitize(t)}")
        note_lines.append("")

    return "\n".join(kw_lines), "\n".join(note_lines)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>笔记思维导图</title>
<style>
  body {{ margin: 0; background: #fafafa; font-family: system-ui, "Microsoft YaHei", sans-serif; }}
  h1 {{ font-size: 18px; margin: 18px 20px 2px; color: #333; }}
  .hint {{ font-size: 12px; color: #999; margin: 0 20px 10px; }}
  .markmap-container {{ width: 100vw; height: 80vh; background: #fff;
       border-top: 1px solid #eee; border-bottom: 1px solid #eee; }}
</style>
<script>
  window.markmap = {{ autoLoader: {{ manual: false }} }};
</script>
<script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.18"></script>
</head>
<body>
<h1>关键词图谱</h1>
<div class="hint">渲染：markmap · 点击节点折叠/展开 · 滚轮缩放 · 拖拽平移</div>
<div class="markmap-container"><script type="text/markdown">
{tags_md}
</script></div>
<h1>笔记库</h1>
<div class="hint">每篇笔记一枝：章节与标签都在下面</div>
<div class="markmap-container"><script type="text/markdown">
{notes_md}
</script></div>
</body>
</html>
"""


def cmd_mindmap(root, open_browser):
    db = root / DB_NAME
    if not db.exists():
        print(f"[mindmap] 没找到 {db}，先运行 sync", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(db)
    tags_md, notes_md = build_markdown(con)
    n = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    con.close()

    (root / MD_NAME).write_text(tags_md + "\n\n---\n\n" + notes_md + "\n", encoding="utf-8")
    html_path = root / HTML_NAME
    html_path.write_text(
        HTML_TEMPLATE.format(tags_md=tags_md, notes_md=notes_md), encoding="utf-8"
    )
    print(f"[mindmap] {html_path}  （{n} 篇笔记，两个视图）")
    print(f"[mindmap] 大纲备份：{root / MD_NAME}")
    if open_browser:
        webbrowser.open(html_path.resolve().as_uri())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="笔记项目目录（含 notes/ 子目录），默认当前目录")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync", help="扫描 notes/*.typ，全量重建 notes.db")
    p_mm = sub.add_parser("mindmap", help="从 notes.db 生成 markmap 交互导图 HTML")
    p_mm.add_argument("--open", action="store_true", help="生成后直接在浏览器打开")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[!] 目录不存在：{root}", file=sys.stderr)
        sys.exit(1)
    if args.cmd == "sync":
        cmd_sync(root)
    else:
        cmd_mindmap(root, args.open)


if __name__ == "__main__":
    main()
