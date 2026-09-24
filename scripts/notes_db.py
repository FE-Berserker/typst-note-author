#!/usr/bin/env python3
"""typst-note-author 的关键词库、知识图谱与思维导图工具。

把笔记项目的关键词与结构存进 SQLite，再生成可交互的浏览器视图。

子命令（--root 指向笔记项目目录；不传时依次取：环境变量 TYPST_NOTES_HOME >
状态文件里登记的位置 > 当前目录）：
  sync      扫描 notes/*.typ 的 note-header（标题/日期/标签/状态/来源/摘要）
            与节标题（== / ===），全量重建 notes.db；同时对比上次合集收录的
            清单，自上次合集新增满 20 篇时自动创建合集（合集-日期.pdf）
  collect   立即编译一次合集：先按当前笔记自动重写 collection.typ 的
            include 列表（AUTO-INCLUDE 标记段内），再 typst compile，计数归零。
            没有 AUTO 标记段说明是手工维护模式，include 不自动改
  graph     从 notes.db 生成 graph.html——交互式知识图谱（vis-network 力导向图）：
            关键词为节点、同一篇笔记出现过的关键词互相关联（共现边），
            节点大小 = 关联笔记数；可拖动重排、缩放、点击高亮、搜索定位，
            「显示笔记节点」开关把每篇笔记也放进图里（推荐先看这个）
  mindmap   从 notes.db 生成 mindmap.html / mindmap.md——树状思维导图
            （markmap），层级视图的补充
  root      查询/登记笔记项目的存储位置（不带参数=查询，带路径=登记）。
            第一次为用户建笔记项目时先问清存哪里，登记一次，
            之后所有子命令不带 --root 就默认用这个位置
  bump      已废弃（保留只为兼容旧指令）：计数不再手动记，由 sync 对比
            上次合集收录的清单自动统计

状态文件：~/.typst-note-author/state.json（存储位置、计数器、上次合集日期）。
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
COLLECT_EVERY = 20  # 每新建多少篇笔记自动编译一次合集
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

    # 自上次合集以来新增了多少篇：与状态里记的「上次合集收录清单」对账。
    # 计数从这里来，不靠手动 bump——建笔记时谁都不用记着计数这件事。
    st = load_state()
    collected = set(st.get("collected_notes", []))
    pending = [fname for fname, _h, _s in notes if fname not in collected]
    if len(pending) >= COLLECT_EVERY:
        print(f"[sync] 自上次合集已新增 {len(pending)} 篇（阈值 {COLLECT_EVERY}）——自动创建合集")
        try:
            cmd_collect(root)
        except SystemExit:
            print("[sync] 合集编译失败：处理上面的报错后手动跑一次 collect", file=sys.stderr)
    else:
        print(f"[sync] 距下次自动合集还有 {COLLECT_EVERY - len(pending)} 篇")
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
    physics: { enabled: true, solver: 'barnesHut',
               barnesHut: { gravitationalConstant: -4200, springLength: 130 } },
    nodes: { shape: 'dot', borderWidth: 2,
             scaling: { min: 10, max: 36 },
             font: { face: 'system-ui, Microsoft YaHei, sans-serif', size: 14 } },
    edges: { scaling: { min: 1, max: 6 } },
  }
);
document.getElementById('stats').textContent = DATA.stats;

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
setTimeout(() => net.fit(), 1200);

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


def auto_includes(root):
    """把 collection.typ 的 AUTO-INCLUDE 标记段重写为当前 notes/*.typ 的
    include 列表（按文件名排序）。没有标记段＝手工维护模式，不动并返回 False。"""
    col = root / "collection.typ"
    text = col.read_text(encoding="utf-8")
    if AUTO_BEGIN not in text or AUTO_END not in text:
        return False
    notes_dir = root / "notes"
    names = sorted(p.name for p in notes_dir.glob("*.typ")) if notes_dir.is_dir() else []
    block = AUTO_BEGIN + "\n" + "\n\n".join(
        f'#include "notes/{n}"' for n in names) + "\n" + AUTO_END
    pattern = re.compile(re.escape(AUTO_BEGIN) + r".*?" + re.escape(AUTO_END), re.S)
    col.write_text(pattern.sub(lambda _m: block, text, count=1), encoding="utf-8")
    return True


def cmd_collect(root):
    col = root / "collection.typ"
    if not col.exists():
        print(f"[collect] {col} 不存在——先按技能第 1 步把 template/ 搭到这个目录", file=sys.stderr)
        sys.exit(1)
    if auto_includes(root):
        print("[collect] include 列表已按当前笔记更新（AUTO-INCLUDE 段）")
    else:
        print("[collect] collection.typ 没有 AUTO-INCLUDE 标记（手工维护模式）：include 不自动改，确认新笔记都加进去了")
    typst = shutil.which("typst")
    if not typst:
        print("[collect] 找不到 typst 命令，确认已安装并在 PATH 里", file=sys.stderr)
        sys.exit(1)
    out = root / f"合集-{date.today():%Y%m%d}.pdf"
    r = subprocess.run(
        [typst, "compile", str(col), str(out)],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(f"[collect] 合集编译失败：\n{(r.stderr or r.stdout)[:2000]}", file=sys.stderr)
        sys.exit(1)
    # 记下这次合集收录了哪些笔记，作为下次「新增篇数」的基线
    notes_dir = root / "notes"
    st = load_state()
    st["collected_notes"] = sorted(
        p.name for p in notes_dir.glob("*.typ")) if notes_dir.is_dir() else []
    st["last_collection"] = f"{date.today():%Y-%m-%d}"
    save_state(st)
    print(f"[collect] 合集已生成：{out}（收录 {len(st['collected_notes'])} 篇，计数已归零）")


def cmd_bump():
    print("[bump] bump 已移除：合集计数现在由 sync 自动统计")
    print("[bump] 建/删笔记后照常 sync，自上次合集新增满 "
          f"{COLLECT_EVERY} 篇时 sync 会自动创建合集")


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
    sub.add_parser("collect", help="立即编译一次合集：自动更新 include 列表并归零计数")
    sub.add_parser("doctor", help="体检项目里的模板拷贝是否落后于技能模板（已有项目开工前先跑）")
    args = ap.parse_args()

    # root / bump 不依赖 --root（root 管的就是位置本身，bump 读状态文件）
    if args.cmd == "root":
        cmd_root(args.path)
        return
    if args.cmd == "bump":
        cmd_bump()
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
        cmd_collect(root)
    elif args.cmd == "doctor":
        cmd_doctor(root)
    else:
        cmd_mindmap(root, args.open)


if __name__ == "__main__":
    main()
