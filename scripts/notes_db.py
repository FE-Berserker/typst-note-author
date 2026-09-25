#!/usr/bin/env python3
"""typst-note-author 的关键词库、知识图谱与思维导图工具。

把笔记项目的关键词与结构存进 SQLite，再生成可交互的浏览器视图。

子命令（--root 指向笔记项目目录；不传时依次取：环境变量 TYPST_NOTES_HOME >
状态文件里登记的位置 > 当前目录）：
  sync      扫描 notes/*.typ 的 note-header（标题/日期/标签/状态/来源/摘要）
            与节标题（== / ===），全量重建 notes.db；同时对比往期合集收录的
            清单，未收录的笔记攒满 20 篇就自动编一卷（合集-日期-卷NN.pdf）
  collect   立即编一卷：把当前**未收录**的笔记（至多 20 篇）写进 collection.typ
            的 include 列表（AUTO-INCLUDE 标记段内），再 typst compile，卷号递增。
            已收录进往期合集的笔记不会再进新卷，单卷体积因此不会一直长下去。
            没有 AUTO 标记段说明是手工维护模式，include 不自动改；
            --full 例外：把全部笔记编成一个整套合集（文件大，慎用）
  graph     从 notes.db 生成 graph.html——交互式知识图谱（vis-network 力导向图）：
            关键词为节点、同一篇笔记出现过的关键词互相关联（共现边），
            节点大小 = 关联笔记数；可拖动重排、缩放、点击高亮、搜索定位，
            「显示笔记节点」开关把每篇笔记也放进图里（推荐先看这个）
  mindmap   从 notes.db 生成 mindmap.html / mindmap.md——树状思维导图
            （markmap），层级视图的补充
  root      查询/登记笔记项目的存储位置（不带参数=查询，带路径=登记）。
            第一次为用户建笔记项目时先问清存哪里，登记一次，
            之后所有子命令不带 --root 就默认用这个位置
  pack      把笔记项目打成一个 zip（迁移到另一台电脑用）：模板核心文件 +
            notes/*.typ + assets/ + 打包清单；编译产物（PDF、notes.db、图谱）
            默认不收——它们在目标机器上重新生成即可，而合集 PDF 动辄几百 MB。
            --with-pdfs 连编译好的 PDF 一起收，--all 连临时文件一起收
  restore   解开 pack 打的包：还原笔记到目标目录、登记笔记位置、并把包里的
            「已收录清单」写回状态——不这么做的话目标机器上的 sync 会把所有
            老笔记当成未收录，一次编出一堆卷
  bump      已废弃（保留只为兼容旧指令）：计数不再手动记，由 sync 对比
            往期合集收录的清单自动统计

状态文件：~/.typst-note-author/state.json（存储位置、已收录清单、历卷记录）。
依赖：Python 3.8+（仅标准库）。HTML 视图优先用项目内 assets/vendor/ 的
本地渲染库（vis-network / markmap），缺件时回落 CDN（需联网）；
图数据本身已内嵌在 HTML 里。
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import webbrowser
import zipfile
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_NAME = "notes.db"
MD_NAME = "mindmap.md"
HTML_NAME = "mindmap.html"
GRAPH_NAME = "graph.html"
PDF_DIR_NAME = "notes-pdf"  # 逐篇编译的 PDF，供知识图谱点击跳转

# ---- 技能的持久状态（跨会话记住存储位置与计数器）----
# 环境变量 TYPST_NOTES_HOME 优先于状态文件；两者都没有时 --root 才落到当前目录
ENV_VAR = "TYPST_NOTES_HOME"
COLLECT_EVERY = 20  # 一卷收录多少篇：未收录的笔记攒够这个数就自动编一卷
STATE_DIR = Path.home() / ".typst-note-author"
STATE_FILE = STATE_DIR / "state.json"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def save_state(st):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def notes_root():
    """笔记项目的位置：环境变量 > 状态文件；都没有返回 None。"""
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser()
    st = load_state()
    if st.get("notes_root"):
        return Path(st["notes_root"])
    return None


def resolve_root(cli):
    """子命令实际使用的目录：显式 --root > 环境变量 > 状态文件 > 当前目录。"""
    if cli:
        return Path(cli).expanduser().resolve()
    r = notes_root()
    if r:
        return r.resolve()
    return Path.cwd()

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

    # 还有多少篇没进过合集：与状态里记的「往期合集收录清单」对账。
    # 计数从这里来，不靠手动 bump——建笔记时谁都不用记着计数这件事。
    # 攒够一卷就编一卷，编完接着数：一次 sync 之后未收录的必定不足一卷。
    all_names = [fname for fname, _h, _s in notes]
    while True:
        collected = set(load_state().get("collected_notes", []))
        pending = [n for n in all_names if n not in collected]
        if len(pending) < COLLECT_EVERY:
            print(f"[sync] 未收录 {len(pending)} 篇，距下一卷还有 "
                  f"{COLLECT_EVERY - len(pending)} 篇")
            return notes
        print(f"[sync] 未收录 {len(pending)} 篇（一卷 {COLLECT_EVERY} 篇）——自动编卷")
        try:
            auto = cmd_collect(root)
        except SystemExit:
            print("[sync] 合集编译失败：处理上面的报错后手动跑一次 collect", file=sys.stderr)
            return notes
        if not auto:
            # 手工维护模式：include 列表不由我们决定，编一次就够，别再循环
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
  .markmap-container svg {{ width: 100%; height: 100%; display: block; }}
</style>
{runtime_head}
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
{runtime_tail}
</body>
</html>
"""

#: 离线运行时：项目内存在 assets/vendor 三件套（d3 / markmap-lib /
#: markmap-view 的本地副本）时优先使用——CDN（jsdelivr）不可达或 file://
#: 受限时在线版会整页空白（2026-09-22 实测）。三件套可用
#: curl -sLO https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js 等同源命令取得
_VENDOR_FILES = (
    "assets/vendor/d3.min.js",
    "assets/vendor/markmap-lib.js",   # markmap-lib@0.18 dist/browser/index.iife.js
    "assets/vendor/markmap-view.js",  # markmap-view@0.18 dist/browser/index.js
)

_ONLINE_HEAD = """<script>
  window.markmap = { autoLoader: { manual: false } };
</script>
<script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@0.18"></script>"""

_OFFLINE_TAIL = """<script>
(function () {
  var transformer = new markmap.Transformer();
  document.querySelectorAll(".markmap-container").forEach(function (el) {
    var md = el.querySelector('script[type="text/markdown"]').textContent;
    var root = transformer.transform(md).root;
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    el.appendChild(svg);
    markmap.Markmap.create(svg, { autoFit: true }, root);
  });
})();
</script>"""


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
    offline = all((root / f).exists() for f in _VENDOR_FILES)
    if offline:
        runtime_head = "\n".join(f'<script src="{f}"></script>' for f in _VENDOR_FILES)
        runtime_tail = _OFFLINE_TAIL
    else:
        runtime_head = _ONLINE_HEAD
        runtime_tail = ""
    html_path.write_text(
        HTML_TEMPLATE.format(
            tags_md=tags_md,
            notes_md=notes_md,
            runtime_head=runtime_head,
            runtime_tail=runtime_tail,
        ),
        encoding="utf-8",
    )
    print(f"[mindmap] {html_path}  （{n} 篇笔记，两个视图；{'本地离线渲染' if offline else 'CDN 在线渲染'}）")
    print(f"[mindmap] 大纲备份：{root / MD_NAME}")
    if open_browser:
        webbrowser.open(html_path.resolve().as_uri())


# ============================================================
# 知识图谱（数据自 SQLite，渲染交给 vis-network）
# ============================================================

# 关键词节点配色：与模板 colors.typ 的 note-themes 同一套，图与笔记同源
KW_PALETTE = ["#c1002a", "#1d4ed8", "#15803d", "#86198f", "#a35c00", "#0f766e"]


def build_graph_data(con):
    """关键词为节点、共现为边的图数据。共现 = 两个关键词出现在同一篇笔记，
    边越粗说明这对关键词一起出现的次数越多——这是知识图谱里真正的「关系」。"""
    notes = con.execute("SELECT id, file, title, date, status FROM notes ORDER BY file").fetchall()
    note_kws = {}
    for note_id, name in con.execute(
        "SELECT note_id, k.name FROM note_keywords nk JOIN keywords k ON k.id = nk.keyword_id"
    ):
        note_kws.setdefault(note_id, []).append(name)

    kw_count = {}
    for kws in note_kws.values():
        for k in set(kws):
            kw_count[k] = kw_count.get(k, 0) + 1

    nodes = []
    for i, name in enumerate(sorted(kw_count)):
        col = KW_PALETTE[i % len(KW_PALETTE)]
        tip = [f"{name} · 关联笔记 {kw_count[name]}"]
        for nid, _f, title, date, _s in notes:
            if name in note_kws.get(nid, []):
                tip.append(f"· {title}" + (f"（{date}）" if date else ""))
        nodes.append({
            "id": f"kw:{name}", "label": sanitize(name), "group": "kw",
            "value": kw_count[name], "color": col, "baseColor": col,
            "title": "<br>".join(tip),
        })
    # 笔记节点默认隐藏：先看关键词之间的关系，需要时再勾选把笔记放进来
    for nid, fname, title, date, status in notes:
        nodes.append({
            "id": f"note:{fname}", "label": sanitize(title)[:14], "group": "note",
            "shape": "box", "color": "#8f9aa8", "hidden": True,
            "title": f"{sanitize(title)}（{date or '无日期'} · {status or '无状态'}）",
        })

    pair_w = {}
    for nid, kws in note_kws.items():
        u = sorted(set(kws))
        for i in range(len(u)):
            for j in range(i + 1, len(u)):
                pair_w[(u[i], u[j])] = pair_w.get((u[i], u[j]), 0) + 1
    edges = []
    eid = 0
    for (a, b), w in sorted(pair_w.items()):
        eid += 1
        edges.append({
            "id": f"e{eid}", "from": f"kw:{a}", "to": f"kw:{b}", "group": "kw",
            "value": w, "color": {"color": "rgba(120,120,130,0.45)"},
            "title": f"「{a}」与「{b}」在 {w} 篇笔记中同现",
        })
    for nid, fname, title, date, status in notes:
        for k in sorted(set(note_kws.get(nid, []))):
            eid += 1
            edges.append({
                "id": f"e{eid}", "from": f"note:{fname}", "to": f"kw:{k}",
                "group": "note", "hidden": True, "dashes": [2, 4],
                "color": {"color": "rgba(140,140,150,0.35)"},
                "title": f"《{sanitize(title)}》打了标签 #{sanitize(k)}",
            })

    stats = f"{len(notes)} 篇笔记 · {len(kw_count)} 个关键词 · {len(pair_w)} 条共现关联"
    return {"nodes": nodes, "edges": edges, "stats": stats}


GRAPH_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>笔记知识图谱</title>
<style>
  body { margin: 0; background: #fafafa; font-family: system-ui, "Microsoft YaHei", sans-serif; }
  h1 { font-size: 18px; margin: 14px 20px 2px; color: #333; }
  .hint { font-size: 12px; color: #999; margin: 0 20px 8px; }
  #bar { padding: 4px 20px 10px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  label { font-size: 13px; color: #444; display: flex; align-items: center; gap: 4px; }
  button { font-size: 13px; padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px;
           background: #fff; cursor: pointer; }
  input[type=text] { font-size: 13px; padding: 4px 8px; border: 1px solid #ccc;
           border-radius: 4px; width: 170px; }
  #stats { font-size: 12px; color: #999; }
  #net { width: 100vw; height: calc(100vh - 118px); background: #fff;
         border-top: 1px solid #eee; }
</style>
<script src="__VIS_SRC__"></script>
</head>
<body>
<h1>笔记知识图谱</h1>
<div class="hint">点击笔记节点打开该篇 PDF · 点击关键词节点高亮它的关联 · 拖动重排 · 滚轮缩放 · 搜索定位 · 节点大小 = 关联笔记数</div>
<div id="bar">
  <input type="text" id="q" placeholder="搜索关键词…">
  <label><input type="checkbox" id="show-notes">显示笔记节点</label>
  <label><input type="checkbox" id="physics" checked>物理模拟</label>
  <button id="fit">适应屏幕</button>
  <span id="stats"></span>
</div>
<div id="net"></div>
<script>
const DATA = __DATA__;
const nodes = new vis.DataSet(DATA.nodes);
const edges = new vis.DataSet(DATA.edges);
const net = new vis.Network(
  document.getElementById('net'),
  { nodes: nodes, edges: edges },
  {
    interaction: { hover: true, tooltipDelay: 150 },
    // 大图谱必须关掉 improvedLayout：它对 100+ 节点跑 Kamada-Kawai 预布局，
    // O(n²) 的同步计算会把主线程卡死几分钟——页面一片空白就是它。
    layout: { improvedLayout: false },
    physics: { enabled: true, solver: 'barnesHut',
               // 布局还是交给 vis 现场跑（力导向 + 可拖动），但稳定化预布局这个
               // 闸门必须关：enabled 为 true 时，那几百次迭代跑完之前画布上什么
               // 都不画——900+ 节点的库跑不完，页面就一直白着，看着像图谱坏了。
               // 关掉它，先画出初始布局，让物理边跑边收敛。
               stabilization: { enabled: false },
               barnesHut: { gravitationalConstant: -2600, springLength: 95,
                            springConstant: 0.04, damping: 0.4 } },
    nodes: { shape: 'dot', borderWidth: 2,
             scaling: { min: 10, max: 36 },
             font: { face: 'system-ui, Microsoft YaHei, sans-serif', size: 14 } },
    edges: { scaling: { min: 1, max: 6 } },
  }
);
document.getElementById('stats').textContent = DATA.stats;
// 同步画出首帧：不依赖 requestAnimationFrame，任何环境下都不会停在空白画布
net.redraw();

function applyNotes(on) {
  nodes.update(DATA.nodes.filter(n => n.group === 'note')
    .map(n => ({ id: n.id, hidden: !on })));
  edges.update(DATA.edges.filter(e => e.group === 'note')
    .map(e => ({ id: e.id, hidden: !on })));
}
document.getElementById('show-notes').addEventListener('change', e => applyNotes(e.target.checked));
document.getElementById('physics').addEventListener('change', e =>
  net.setOptions({ physics: { enabled: e.target.checked } }));
document.getElementById('fit').addEventListener('click', () => net.fit());
// 视野适配要等画布拿到真实尺寸才算得对：加载时立刻 fit() 会因为容器尺寸还是 0
// 而落空，停在 scale=1（图只露出中间一小块）。首帧画完后适配一次，容器尺寸变化
// 时再适配；用户自己滚轮缩放或拖动过就不打扰。
const netEl = document.getElementById('net');
let viewTouched = false;
netEl.addEventListener('wheel', () => { viewTouched = true; }, { passive: true });
netEl.addEventListener('pointerdown', () => { viewTouched = true; });
const refit = () => { if (!viewTouched) net.fit(); };
net.once('afterDrawing', refit);
new ResizeObserver(refit).observe(netEl);
window.addEventListener('resize', refit);

// 笔记节点点击 → 打开该篇 PDF（相对本页的路径；编译失败的节点没有 pdf 字段）
net.on('click', props => {
  if (props.nodes.length !== 1) return;
  const n = nodes.get(props.nodes[0]);
  if (n && n.pdf) window.open(n.pdf, '_blank');
});

const q = document.getElementById('q');
q.addEventListener('input', () => {
  const s = q.value.trim().toLowerCase();
  const upd = DATA.nodes.filter(n => n.group === 'kw').map(n => {
    const hit = s !== '' && n.label.toLowerCase().includes(s);
    return { id: n.id, borderWidth: hit ? 4 : 2,
             color: hit ? '#2b2b2b' : n.baseColor };
  });
  nodes.update(upd);
  if (s === '') { net.unselectAll(); return; }
  const ids = DATA.nodes.filter(n => n.group === 'kw'
    && n.label.toLowerCase().includes(s)).map(n => n.id);
  if (ids.length) net.selectNodes(ids);
});
</script>
</body>
</html>
"""


def compile_note_pdfs(root):
    """把每篇笔记单独编译成 notes-pdf/<文件名>.pdf，返回 {笔记文件名: 相对路径}。

    入口文件临时写在项目根（与 single.typ 同构），因为笔记里的相对 import
    （../note.typ）按笔记文件自身位置解析，根目录正好匹配。"""
    notes_dir = root / "notes"
    if not notes_dir.is_dir() or not (root / "note.typ").exists():
        return {}
    typst = shutil.which("typst")
    if not typst:
        print("[graph] 找不到 typst，跳过逐篇 PDF（笔记节点将不可跳转）", file=sys.stderr)
        return {}
    pdf_dir = root / PDF_DIR_NAME
    pdf_dir.mkdir(exist_ok=True)
    links = {}
    failed = []
    for note in sorted(notes_dir.glob("*.typ")):
        entry = root / f"_build-{note.stem}.typ"
        out_pdf = pdf_dir / f"{note.stem}.pdf"
        entry.write_text(
            '#import "note.typ": *\n#import "figstyle.typ": *\n'
            "#show: note-setup\n"
            f'#include "notes/{note.name}"\n',
            encoding="utf-8",
        )
        try:
            r = subprocess.run(
                [typst, "compile", str(entry), str(out_pdf)],
                cwd=str(root), capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode == 0:
                links[note.name] = f"{PDF_DIR_NAME}/{out_pdf.name}"
            else:
                failed.append((note.name, " / ".join(
                    (r.stderr or r.stdout).strip().splitlines()[:2])))
        finally:
            entry.unlink(missing_ok=True)
    for name, err in failed:
        print(f"[graph] ⚠ {name} 编译失败（节点保留、不可跳转）：{err}", file=sys.stderr)
    return links


def existing_note_pdfs(root):
    """不编译时复用 notes-pdf/ 里已有的 PDF。"""
    pdf_dir = root / PDF_DIR_NAME
    if not pdf_dir.is_dir():
        return {}
    notes_dir = root / "notes"
    links = {}
    for note in sorted(notes_dir.glob("*.typ")) if notes_dir.is_dir() else []:
        p = pdf_dir / f"{note.stem}.pdf"
        if p.exists():
            links[note.name] = f"{PDF_DIR_NAME}/{p.name}"
    return links


def cmd_graph(root, open_browser, make_pdfs):
    db = root / DB_NAME
    if not db.exists():
        print(f"[graph] 没找到 {db}，先运行 sync", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(db)
    data = build_graph_data(con)
    con.close()
    if not data["nodes"]:
        print("[graph] 库是空的：先在笔记的 note-header 里写 tags，再 sync", file=sys.stderr)
        sys.exit(1)

    # 逐篇编译 PDF 并挂到笔记节点上：点击节点即可打开该篇 PDF
    links = compile_note_pdfs(root) if make_pdfs else existing_note_pdfs(root)
    for n in data["nodes"]:
        if n["group"] != "note":
            continue
        fname = n["id"][len("note:"):]
        if fname in links:
            n["pdf"] = links[fname]
            n["title"] += "<br>点击打开 PDF"
        else:
            n["title"] += "<br>（未生成 PDF，不可跳转；重跑 graph 可补）"
    if links:
        print(f"[graph] 逐篇 PDF：{len(links)} 篇就绪（{PDF_DIR_NAME}/，点击笔记节点打开）")

    # </ 转义防止笔记标题里出现它时截断 <script>
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = root / GRAPH_NAME
    # 本地离线渲染：assets/vendor/vis-network.min.js 在场时优先（CDN 不可达
    # 或 file:// 受限时在线版整页空白——与 mindmap 的离线逻辑同款）
    vis_local = root / "assets/vendor/vis-network.min.js"
    vis_src = "assets/vendor/vis-network.min.js" if vis_local.exists() \
        else "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"
    out.write_text(
        GRAPH_HTML.replace("__DATA__", payload).replace("__VIS_SRC__", vis_src),
        encoding="utf-8",
    )
    print(f"[graph] {out}  （{data['stats']}；{'本地离线渲染' if vis_local.exists() else 'CDN 在线渲染'}）")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())


# ============================================================
# 模板体检（doctor）：项目里的模板拷贝是否落后于技能模板
# ------------------------------------------------------------
# 脚手架把 template/ 复制进用户项目后就断了联系：技能里修复的规则
# 不会自动到达旧项目（旧拷贝缺「表题在表格上方」就是这么发生的）。
# ============================================================

# 历次修复中「旧拷贝最容易缺」的关键规则，逐条检查（文件, 名称, 匹配, 补法）
CRITICAL_RULES = [
    (
        "note.typ",
        "表题在表格上方",
        r"figure\.where\(kind: table\): set figure\.caption\(position: top\)",
        "题注一节补：show figure.where(kind: table): set figure.caption(position: top)",
    ),
    (
        "note.typ",
        "跨页表头重复（三线表底线用表格内 hline，不外包 block）",
        r"table\.hline\(position: top",
        "三线表一节换成「重建表格 + 追加 table.hline(position: top)」方案，见技能模板",
    ),
    (
        "note.typ",
        "插图不被重复缩放（没有多余的 show image 规则）",
        r"插图：不需要额外规则",
        "删掉 show image: it => layout(sz => context { … scale … }) 那一段。"
        "Typst 自身会把过宽的图夹到容器宽度，旧规则把比例缩了两次"
        "（实际宽度 = 版心² ÷ 自然宽），越宽的图越小，6000px 只剩版心 7%。"
        "改法见技能模板 note.typ 的注释",
    ),
]


def cmd_doctor(root):
    skill_tpl = Path(__file__).resolve().parent.parent / "template"
    print(f"[doctor] 项目：{root}")
    print(f"[doctor] 技能模板：{skill_tpl}")
    problems = 0

    core = ("note.typ", "colors.typ", "boxes.typ", "figstyle.typ", "single.typ", "collection.typ")
    for f in core:
        if not (root / f).exists():
            print(f"✗ 缺核心文件 {f}——这个项目可能不是本技能搭的脚手架")
            problems += 1

    note = root / "note.typ"
    if note.exists():
        src = note.read_text(encoding="utf-8")
        skill_note = skill_tpl / "note.typ"
        skill_src = skill_note.read_text(encoding="utf-8") if skill_note.exists() else ""

        v_proj = re.search(r'#let template-version = "([^"]*)"', src)
        v_skill = re.search(r'#let template-version = "([^"]*)"', skill_src)
        if not v_proj:
            print("✗ note.typ 没有版本戳——技能修复之前的旧拷贝，强烈建议对照技能模板逐条体检并同步")
            problems += 1
        elif v_skill and v_proj.group(1) != v_skill.group(1):
            print(f"! 模板版本 {v_proj.group(1)} ≠ 技能 {v_skill.group(1)}：技能模板修过问题，逐条做规则体检")
        else:
            print(f"✓ 模板版本 {v_proj.group(1)}（与技能一致）")

        for fname, name, pat, fix in CRITICAL_RULES:
            text = src if fname == "note.typ" else (root / fname).read_text(encoding="utf-8")
            if re.search(pat, text):
                print(f"✓ {name}")
            else:
                print(f"✗ {name}——{fix}")
                problems += 1

    # 其余文件逐字节对比是信息性的：有差异可能是用户的定制，也可能是旧拷贝
    if skill_tpl.is_dir():
        for f in core:
            a, b = root / f, skill_tpl / f
            if a.exists() and b.exists():
                print(f"- {f}: {'与技能模板一致' if a.read_bytes() == b.read_bytes() else '有差异（你的定制，或旧拷贝）'}")

    if problems:
        print(f"[doctor] 发现 {problems} 个问题——修完再开工；拿不准时对照技能模板同步（保留你的定制）")
        sys.exit(1)
    print("[doctor] 模板健康，可以开工")


# ============================================================
# 存储位置与合集计数（状态在 ~/.typst-note-author/state.json）
# ============================================================


def cmd_root(path):
    if path:
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            print(f"[root] 目录还不存在：{p}（先搭脚手架再登记，或先 mkdir）", file=sys.stderr)
            sys.exit(1)
        st = load_state()
        st["notes_root"] = str(p)
        save_state(st)
        print(f"[root] 笔记位置已登记：{p}")
        print(f"[root] 之后所有子命令不带 --root 都默认用这里（{ENV_VAR} 环境变量可覆盖）")
    else:
        r = notes_root()
        if r:
            print(r)
        else:
            print("[root] NOT_SET——第一次使用先问用户存哪里，然后：notes_db.py root <路径>")
            sys.exit(3)


AUTO_BEGIN = "// ---- AUTO-INCLUDE BEGIN ----"
AUTO_END = "// ---- AUTO-INCLUDE END ----"
VOLUME_RE = re.compile(r"合集-\d{8}-卷(\d+)\.pdf$")


def next_volume_no(root):
    """下一个卷号：取目录里 合集-日期-卷NN.pdf 的最大号 +1（没有卷就是 1）。

    不把卷号存进状态：目录里有哪些卷就是哪些卷，手工改了文件名也不会串号。
    """
    nums = [int(m.group(1))
            for m in (VOLUME_RE.search(p.name) for p in root.glob("合集-*-卷*.pdf"))
            if m]
    return max(nums) + 1 if nums else 1


def auto_includes(root, names):
    """把 collection.typ 的 AUTO-INCLUDE 标记段重写成本卷的 include 列表
    （按文件名排序，排序即卷内顺序）。没有标记段＝手工维护模式，不动并返回 False。"""
    col = root / "collection.typ"
    text = col.read_text(encoding="utf-8")
    if AUTO_BEGIN not in text or AUTO_END not in text:
        return False
    block = AUTO_BEGIN + "\n" + "\n\n".join(
        f'#include "notes/{n}"' for n in sorted(names)) + "\n" + AUTO_END
    pattern = re.compile(re.escape(AUTO_BEGIN) + r".*?" + re.escape(AUTO_END), re.S)
    col.write_text(pattern.sub(lambda _m: block, text, count=1), encoding="utf-8")
    return True


def cmd_collect(root, full=False):
    """编一卷：只收还没进过合集的笔记（一卷至多 COLLECT_EVERY 篇）。

    收完把清单**累加**进状态——已进过往期合集的笔记不会再次进新卷，所以单卷
    体积稳定在一卷的量级，不会随着笔记总数越编越厚。full=True 例外：全部笔记
    编成一个整套合集（沿用旧行为，几百篇就是几百 MB，慎用）。
    返回是否接管了 include 列表（AUTO 标记段在，即非手工维护模式）。
    """
    col = root / "collection.typ"
    if not col.exists():
        print(f"[collect] {col} 不存在——先按技能第 1 步把 template/ 搭到这个目录", file=sys.stderr)
        sys.exit(1)

    notes_dir = root / "notes"
    all_typ = sorted(p.name for p in notes_dir.glob("*.typ")) if notes_dir.is_dir() else []
    all_names = [fname for fname, _h, _s in scan_notes(root)]
    # notes/ 里没有 note-header 的文件不是笔记（辅助文件），每卷都要跟着一起编
    helpers = [n for n in all_typ if n not in set(all_names)]

    st = load_state()
    # 已删掉的笔记顺手从清单里剔掉，状态文件不积死名字
    collected = set(st.get("collected_notes", [])) & set(all_names)
    pending = [n for n in all_names if n not in collected]
    if full:
        picked = all_names
    else:
        picked = pending[:COLLECT_EVERY]
        if not picked:
            print(f"[collect] 没有未收录的笔记（{len(all_names)} 篇都在往期合集里）——不编卷")
            print("[collect] 要把全部笔记重编成整套：collect --full（文件会很大）")
            return False
        if len(pending) > len(picked):
            print(f"[collect] 未收录 {len(pending)} 篇，本卷收 {len(picked)} 篇，"
                  f"余下 {len(pending) - len(picked)} 篇留到下一卷")

    auto = auto_includes(root, helpers + picked)
    if auto:
        print(f"[collect] include 列表已重写为本卷 {len(picked)} 篇（AUTO-INCLUDE 段）")
    else:
        print("[collect] collection.typ 没有 AUTO-INCLUDE 标记（手工维护模式）：include 不自动改，"
              "确认本卷的笔记都加进去了")
    typst = shutil.which("typst")
    if not typst:
        print("[collect] 找不到 typst 命令，确认已安装并在 PATH 里", file=sys.stderr)
        sys.exit(1)
    if full:
        out = root / f"合集-{date.today():%Y%m%d}.pdf"
    else:
        out = root / f"合集-{date.today():%Y%m%d}-卷{next_volume_no(root):02d}.pdf"
    r = subprocess.run(
        [typst, "compile", str(col), str(out)],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(f"[collect] 合集编译失败：\n{(r.stderr or r.stdout)[:2000]}", file=sys.stderr)
        sys.exit(1)
    # 收录清单只增不减：下次「未收录」接着往后数，已经编进卷里的不再进新卷
    st["collected_notes"] = sorted(collected | set(picked))
    st["last_collection"] = f"{date.today():%Y-%m-%d}"
    st.setdefault("volumes", []).append(
        {"file": out.name, "date": f"{date.today():%Y-%m-%d}", "count": len(picked)}
    )
    save_state(st)
    left = len(all_names) - len(st["collected_notes"])
    print(f"[collect] 合集已生成：{out}")
    print(f"[collect] 本卷 {len(picked)} 篇；累计已收录 {len(st['collected_notes'])}/{len(all_names)} 篇"
          + (f"，还有 {left} 篇未收录" if left else "，全部笔记都已进过合集"))
    return auto


def cmd_bump():
    print("[bump] bump 已移除：合集计数现在由 sync 自动统计")
    print(f"[bump] 建/删笔记后照常 sync，未收录的笔记攒满 "
          f"{COLLECT_EVERY} 篇时 sync 会自动编一卷")


# ============================================================
# 打包迁移（pack / restore）：整个笔记项目打成一个 zip，换台电脑继续用
# ------------------------------------------------------------
# 打包只收「迁移真正需要的」：模板核心文件 + notes/*.typ + assets/。
# 编译产物（合集与单篇 PDF、notes.db、graph.html、mindmap.html、notes-pdf/）
# 都能在目标机器上重新生成，而它们往往比笔记本身大两个数量级——合集一个
# 文件就几百 MB，默认收进去，包就没法传了。
# 打包清单（note-pack.json）里带着「已收录清单」：restore 把它写回状态，
# 目标机器上的 sync 才不会把老笔记当成未收录、一口气编出一堆卷。
# ============================================================

PACK_PREFIX = "笔记包"
PACK_MANIFEST = "note-pack.json"
PACK_README = "迁移说明.md"
# 模板核心文件：skill 的 template/ 里除 notes/ 之外的那几个（跨项目复制的那份）
CORE_FILES = ("note.typ", "colors.typ", "boxes.typ", "figstyle.typ", "single.typ", "collection.typ")
PACK_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".idea", ".vscode"}


def pack_readme(manifest):
    src = manifest["source_root"]
    if manifest["with_pdfs"]:
        pdfs_line = ("编译好的 PDF（`合集-*.pdf`、逐篇 PDF）**也在这个包里**"
                     "（打包时用了 `--with-pdfs`），解出来就能看，不必重新编译。")
    else:
        pdfs_line = ("不含 `合集-*.pdf`、`notes-pdf/`、`notes.db`、`graph.html`、"
                     "`mindmap.html`——这些在目标机器上重新生成即可（合集少则几十 MB、"
                     "多则几百 MB，收进来包就没法传了）。")
    return f"""# 笔记包迁移说明

这个包由 typst-note-author 的 `notes_db.py pack` 生成（{manifest["packed_at"]}，来自 `{src}`）。
里面是笔记项目的**正文与素材**，不是编译产物。

## 包里有什么

- `note.typ` / `colors.typ` / `boxes.typ` / `figstyle.typ` / `single.typ` / `collection.typ`
  与 `.gitignore`：模板核心文件；
- `notes/*.typ`：全部笔记正文，共 **{manifest["note_count"]} 篇**；
- `assets/`：笔记引用的图片与素材{"" if manifest["with_assets"] else "（**本次没打进来**，见下）"}；
- `note-pack.json`：打包清单（来源路径、篇数、已收录清单、模板版本）。

{pdfs_line}

## 目标机器上怎么用

1. 装 Typst 0.13+，以及模板要的字体：Noto Serif SC（正文）、SimHei + Arial（标题）、
   KaiTi/STKaiti（强调）、New Computer Modern（西文与数学）、DejaVu Sans Mono（代码）；
   首次编译要联网拉 `@preview` 依赖包。
2. 装好本技能（github.com/FE-Berserker/typst-note-author），然后：

   ```bash
   python <技能目录>/scripts/notes_db.py restore 这个包.zip --into D:/我的笔记
   ```

   装技能的目的只是拿到 `notes_db.py`；不装也行——把包解开就能用
   `typst compile single.typ 笔记.pdf` 编译，只是没有入库/图谱/自动合集。
3. 恢复之后重建生成物：

   ```bash
   python <技能目录>/scripts/notes_db.py --root D:/我的笔记 sync       # 重建 notes.db
   python <技能目录>/scripts/notes_db.py --root D:/我的笔记 graph --open # 重建知识图谱
   ```

`restore` 会把包里的「已收录清单」写回状态，所以 `sync` 不会把老笔记当成
未收录、又编一遍卷；之后攒够 20 篇新笔记才会自动编下一卷。

{"" if manifest["with_assets"] else "## 注意：这个包不含 assets/\n\n打包时用了 `--no-assets`（或 assets 为空）。笔记里的图片在目标机器上会缺，"
 "需要把源项目的 `assets/` 目录单独拷过去，放在项目根目录下。\n"}
"""


def pack_members(root, with_pdfs=False, everything=False):
    """挑出要打进包的文件，返回 (录入, 跳过) 两组相对路径。

    默认＝模板核心文件 + notes/*.typ + assets/ + .gitignore；
    --with-pdfs 再加编译好的 PDF，--all 则整个项目都收（跳过 .git 之类）。
    产物、临时文件是否被打进包，都会在结尾逐条报出来，不会闷声丢东西。
    """
    included, skipped = [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in PACK_SKIP_DIRS for part in rel.parts):
            continue
        # 上一版打出来的包不收，免得包里有包、越打越大
        if p.name.startswith(PACK_PREFIX) and p.suffix.lower() == ".zip":
            skipped.append(rel)
            continue
        if everything:
            included.append(rel)
            continue
        parts = rel.parts
        top = parts[0]
        if len(parts) == 1:
            if top == ".gitignore" or top in CORE_FILES:
                included.append(rel)
            elif with_pdfs and p.suffix.lower() == ".pdf":
                included.append(rel)
            else:
                skipped.append(rel)
        elif top == "assets":
            included.append(rel)
        elif top == "notes":
            # notes/ 下的东西基本都带上（可能有贴在笔记旁边的图），但 *.pdf
            # 按项目 .gitignore 的约定算编译产物，跟根目录一样默认不收
            if p.suffix.lower() == ".pdf" and not with_pdfs:
                skipped.append(rel)
            else:
                included.append(rel)
        elif top == PDF_DIR_NAME and with_pdfs:
            included.append(rel)
        else:
            skipped.append(rel)
    return included, skipped


def cmd_pack(root, out=None, with_pdfs=False, everything=False, no_assets=False):
    col = root / "collection.typ"
    if not col.exists():
        print(f"[pack] {root} 里没有 collection.typ——这不是本技能的笔记项目吧？", file=sys.stderr)
        sys.exit(1)
    if out:
        out = Path(out).expanduser()
        out = (out / f"{PACK_PREFIX}-{date.today():%Y%m%d}.zip") if out.is_dir() else out
        out = out.resolve()
    else:
        out = root / f"{PACK_PREFIX}-{date.today():%Y%m%d}.zip"

    st = load_state()
    # 已收录清单只跟登记的那个项目对得上：打包别的项目时不带清单，
    # 免得目标机器拿着另一个项目的清单对账（那会把这篇项目的笔记全算成新笔记）
    owner = st.get("notes_root")
    same_project = (not owner) or Path(owner).expanduser().resolve() == root.resolve()
    if not same_project:
        print(f"[pack] 注意：状态里登记的是另一个项目（{owner}），本包不带已收录清单——"
              "到目标机器上第一次 sync 会把这里的笔记都当成未收录", file=sys.stderr)
    notes = scan_notes(root)
    tmpl = re.search(r'#let template-version = "([^"]*)"',
                     (root / "note.typ").read_text(encoding="utf-8"))
    manifest = {
        "tool": "typst-note-author",
        "manifest": PACK_MANIFEST,
        "packed_at": f"{date.today():%Y-%m-%d}",
        "source_root": str(root),
        "template_version": tmpl.group(1) if tmpl else None,
        "note_count": len(notes),
        "with_assets": not no_assets,
        "with_pdfs": with_pdfs,
        "everything": everything,
        # 迁移的关键：目标机器靠它认账，不把老笔记当新笔记重编卷
        "collected_notes": sorted(st.get("collected_notes", [])) if same_project else [],
        "last_collection": st.get("last_collection") if same_project else None,
        "volumes": st.get("volumes", []) if same_project else [],
        "note": "collected_notes 是打包时的「已收录清单」，restore 会写回目标机器的状态",
    }

    included, skipped = pack_members(root, with_pdfs, everything)
    if no_assets:
        included = [r for r in included if r.parts[0] != "assets"]
    # 清单与说明排在最前，解包时第一眼就能看到
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = raw_notes = raw_assets = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(PACK_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        z.writestr(PACK_README, pack_readme(manifest))
        for rel in included:
            p = root / rel
            if p.resolve() == out:
                continue
            z.write(p, rel.as_posix())
            sz = p.stat().st_size
            raw += sz
            if rel.parts[0] == "notes":
                raw_notes += sz
            elif rel.parts[0] == "assets":
                raw_assets += sz
    size = out.stat().st_size
    n_note_files = sum(1 for r in included if r.parts[0] == "notes")
    n_assets = sum(1 for r in included if r.parts[0] == "assets")
    print(f"[pack] 已生成：{out}")
    if included:
        print(f"[pack] 文件 {len(included)} 个 + 清单/说明 2 个；"
              f"原始 {raw / 1048576:.1f} MB → 压缩后 {size / 1048576:.1f} MB"
              f"（{size / raw * 100:.0f}%）")
    else:
        print(f"[pack] 包里没有内容文件（{size / 1048576:.1f} MB）")
    print(f"[pack] notes/ {n_note_files} 个文件（笔记 {manifest['note_count']} 篇，"
          f"{raw_notes / 1048576:.1f} MB） | "
          + (f"素材 {n_assets} 个（{raw_assets / 1048576:.1f} MB）" if not no_assets
             else "素材未打包（--no-assets）")
          + f" | 模板版本 {manifest['template_version'] or '未知'}")
    if not no_assets and raw_assets > 200 * 1048576:
        print(f"[pack] 素材占了 {raw_assets / 1048576:.0f} MB：素材能单独拷（U 盘、云盘）的话，"
              "用 --no-assets 出一个只有笔记的小包更快")
    if manifest["collected_notes"]:
        print(f"[pack] 已收录清单随包带上：{len(manifest['collected_notes'])} 篇"
              "（restore 会写回状态，目标机器不会把老笔记再编一遍卷）")
    else:
        print("[pack] 包里没有已收录清单：目标机器上第一次 sync 会把全部笔记当成未收录，"
              f"按 {COLLECT_EVERY} 篇一卷编出来")
    if no_assets:
        print("[pack] --no-assets：没打素材，目标机器上笔记里的图片会缺")
    if not with_pdfs and not everything:
        print(f"[pack] 没打编译产物（PDF / {DB_NAME} / {GRAPH_NAME} / {PDF_DIR_NAME}/ 等），"
              "目标机器上重新生成即可；要一起带走加 --with-pdfs")
    if skipped:
        by_top = {}
        for rel in skipped:
            by_top.setdefault(rel.parts[0], 0)
            by_top[rel.parts[0]] += 1
        items = "、".join(f"{k}{'/' if (root / k).is_dir() else ''}({v})"
                          for k, v in sorted(by_top.items(), key=lambda x: -x[1])[:8])
        more = f" 等 {len(by_top)} 项" if len(by_top) > 8 else ""
        print(f"[pack] 没打进去：{items}{more}——需要就加 --with-pdfs / --all")
    return out


def _inside(target, dest):
    """dest 是否落在 target 里（防 zip 里塞 ../ 或绝对路径往外写）。"""
    try:
        dest.relative_to(target)
        return True
    except ValueError:
        return False


def cmd_restore(zip_path, into=None, force=False, no_state=False):
    zp = Path(zip_path).expanduser()
    if not zp.is_file():
        print(f"[restore] 找不到包：{zp}", file=sys.stderr)
        sys.exit(1)
    target = Path(into).expanduser() if into else Path.cwd() / zp.stem
    target = target.resolve()

    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        if PACK_MANIFEST not in names:
            print(f"[restore] {zp.name} 里没有 {PACK_MANIFEST}——不是 pack 打的包", file=sys.stderr)
            sys.exit(1)
        manifest = json.loads(z.read(PACK_MANIFEST).decode("utf-8"))
        bad = [n for n in names if not _inside(target, (target / n).resolve())]
        if bad:
            print(f"[restore] 包里这些路径会写到目标目录外面，已中止：{bad[:5]}", file=sys.stderr)
            sys.exit(1)
        if target.exists() and any(target.iterdir()) and not force:
            print(f"[restore] {target} 不是空目录——确认要往里面写，加 --force", file=sys.stderr)
            sys.exit(1)
        target.mkdir(parents=True, exist_ok=True)
        z.extractall(target)

    files = [n for n in names if n != PACK_MANIFEST and not n.endswith("/")]
    n_notes = sum(1 for n in files if n.startswith("notes/"))
    n_assets = sum(1 for n in files if n.startswith("assets/"))
    print(f"[restore] 已解开到：{target}")
    print(f"[restore] notes/ 下 {n_notes} 个文件（清单记的笔记 {manifest.get('note_count')} 篇） | "
          f"素材 {n_assets} 个 | 其它 {len(files) - n_notes - n_assets} 个")
    if manifest.get("template_version"):
        skill_note = Path(__file__).resolve().parent.parent / "template" / "note.typ"
        v_skill = None
        if skill_note.exists():
            m = re.search(r'#let template-version = "([^"]*)"', skill_note.read_text(encoding="utf-8"))
            v_skill = m.group(1) if m else None
        if v_skill and v_skill != manifest["template_version"]:
            print(f"[restore] 提示：包的模板版本 {manifest['template_version']} ≠ 技能的 {v_skill}，"
                  "恢复后先跑一次 doctor 按提示补")
    if not manifest.get("with_assets", True) or not n_assets:
        print("[restore] 包里没有 assets/：笔记里的图片会缺，把源项目的 assets/ 拷到项目根目录下")

    if no_state:
        print("[restore] --no-state：没登记笔记位置、没写回已收录清单")
    else:
        st = load_state()
        owner = st.get("notes_root")
        incoming = manifest.get("collected_notes") or []
        other = (st.get("collected_notes") and owner
                 and Path(owner).expanduser().resolve() != target)
        if other and not force:
            print(f"[restore] 本机已登记另一个笔记项目（{owner}）并记着它的收录清单，没有覆盖。",
                  file=sys.stderr)
            print("[restore] 确实要用这个包的状态：加 --force；只想解包不动状态：加 --no-state",
                  file=sys.stderr)
        else:
            st["notes_root"] = str(target)
            if incoming:
                st["collected_notes"] = sorted(set(incoming))
            if manifest.get("last_collection"):
                st["last_collection"] = manifest["last_collection"]
            if manifest.get("volumes"):
                st["volumes"] = manifest["volumes"]
            save_state(st)
            print(f"[restore] 笔记位置已登记：{target}")
            print(f"[restore] 已收录清单已写回：{len(incoming)} 篇"
                  "——之后 sync 只把新笔记算作待编卷")
    print("[restore] 下一步：装 Typst 0.13+ 与模板字体，然后"
          f"\n    python {Path(__file__).name} --root {target} sync"
          f"\n    python {Path(__file__).name} --root {target} graph --open")
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="笔记项目目录；不传时用 TYPST_NOTES_HOME 或已登记的位置")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync", help="扫描 notes/*.typ，全量重建 notes.db")
    p_graph = sub.add_parser("graph", help="从 notes.db 生成 vis-network 交互式知识图谱 HTML")
    p_graph.add_argument("--open", action="store_true", help="生成后直接在浏览器打开")
    p_graph.add_argument("--no-pdf", action="store_true", help="跳过逐篇编译 PDF（笔记节点不可跳转）")
    p_mm = sub.add_parser("mindmap", help="从 notes.db 生成 markmap 交互导图 HTML")
    p_mm.add_argument("--open", action="store_true", help="生成后直接在浏览器打开")
    p_root = sub.add_parser("root", help="查询/登记笔记项目位置（不带参数=查询）")
    p_root.add_argument("path", nargs="?", help="登记的目录路径")
    sub.add_parser("bump", help="（已废弃）计数改由 sync 自动统计")
    p_collect = sub.add_parser(
        "collect", help=f"编一卷：收录未收录的笔记（至多 {COLLECT_EVERY} 篇），卷号递增")
    p_collect.add_argument(
        "--full", action="store_true",
        help="不按卷：把所有笔记编成一个整套合集（文件会很大，慎用）")
    sub.add_parser("doctor", help="体检项目里的模板拷贝是否落后于技能模板（已有项目开工前先跑）")
    p_pack = sub.add_parser("pack", help="把笔记项目打成一个 zip（迁移到另一台电脑用）")
    p_pack.add_argument("--out", default=None,
                        help=f"输出 zip 路径（默认 <项目>/{PACK_PREFIX}-日期.zip）")
    p_pack.add_argument("--with-pdfs", action="store_true",
                        help="连编译好的 PDF 一起打包（合集动辄几百 MB）")
    p_pack.add_argument("--all", action="store_true",
                        help="整个项目都打（含编译产物与临时文件）")
    p_pack.add_argument("--no-assets", action="store_true",
                        help="不打 assets/（素材另拷时用；目标机器上图片会缺）")
    p_restore = sub.add_parser("restore", help="解开 pack 的包：还原笔记、登记位置、写回已收录清单")
    p_restore.add_argument("zip", help="pack 生成的 zip")
    p_restore.add_argument("--into", default=None, help="解到哪个目录（默认当前目录下与包同名的新目录）")
    p_restore.add_argument("--force", action="store_true",
                           help="目标目录非空也往里写；本机登记着别的项目时用它确认接管状态")
    p_restore.add_argument("--no-state", action="store_true",
                           help="只解包：不登记笔记位置、不写回已收录清单")
    args = ap.parse_args()

    # root / bump / restore 不依赖 --root
    # （root 管的就是位置本身；bump 读状态文件；restore 的落点是 --into）
    if args.cmd == "root":
        cmd_root(args.path)
        return
    if args.cmd == "bump":
        cmd_bump()
        return
    if args.cmd == "restore":
        cmd_restore(args.zip, args.into, args.force, args.no_state)
        return

    root = resolve_root(args.root)
    if not root.is_dir():
        print(f"[!] 目录不存在：{root}", file=sys.stderr)
        sys.exit(1)
    if args.cmd == "sync":
        cmd_sync(root)
    elif args.cmd == "graph":
        cmd_graph(root, args.open, not args.no_pdf)
    elif args.cmd == "collect":
        cmd_collect(root, full=args.full)
    elif args.cmd == "doctor":
        cmd_doctor(root)
    elif args.cmd == "pack":
        cmd_pack(root, args.out, args.with_pdfs, args.all, args.no_assets)
    else:
        cmd_mindmap(root, args.open)


if __name__ == "__main__":
    main()
