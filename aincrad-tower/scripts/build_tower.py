#!/usr/bin/env python3
"""Build the Aincrad Session Tower — a 20-floor HTML castle from the user's latest Claude Code sessions.

Reads ~/.claude/projects/*/*.jsonl, picks the latest 20 by mtime, themes each floor by the
dominant artifact type produced during that session, and writes a self-contained HTML file.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
THEMES_FILE = SKILL_DIR / "assets" / "themes.json"
DEFAULT_OUTPUT = Path.home() / ".claude" / "aincrad-tower" / "index.html"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


# ---------- session parsing ----------

def parse_session(path: Path) -> dict:
    """Parse one JSONL session file. Tolerant of malformed lines."""
    first_user_prompt = None
    artifacts: list[str] = []
    message_count = 0
    first_ts = None
    last_ts = None
    cwd = None
    session_id = path.stem

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = event.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            if not cwd and event.get("cwd"):
                cwd = event["cwd"]

            etype = event.get("type")

            # First user prompt — try several shapes.
            if first_user_prompt is None:
                if etype == "queue-operation" and event.get("operation") == "enqueue":
                    content = event.get("content")
                    if isinstance(content, str) and content.strip():
                        first_user_prompt = content.strip()
                elif etype == "user":
                    msg = event.get("message") or {}
                    content = msg.get("content")
                    extracted = _extract_text(content)
                    if extracted:
                        first_user_prompt = extracted

            if etype in ("user", "assistant"):
                message_count += 1
                msg = event.get("message") or {}
                content = msg.get("content")
                artifacts.extend(_extract_artifacts(content))

    # Dedup artifacts preserving order.
    seen = set()
    deduped = []
    for a in artifacts:
        if a not in seen:
            seen.add(a)
            deduped.append(a)

    return {
        "session_id": session_id,
        "path": str(path),
        "cwd": cwd,
        "project_name": _project_name(cwd, path),
        "first_prompt": first_user_prompt or "(no prompt captured)",
        "artifacts": deduped,
        "message_count": message_count,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "mtime": path.stat().st_mtime,
    }


def _extract_text(content) -> str | None:
    """Pull a text snippet from message.content which may be a string or a list of blocks."""
    if isinstance(content, str):
        s = content.strip()
        # Skip system-only echoes that start with <command-name> etc.
        if s and not s.startswith("<"):
            return s
        return None
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = (block.get("text") or "").strip()
                if t and not t.startswith("<"):
                    return t
    return None


_FILE_PATH_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Create"}


def _extract_artifacts(content) -> list[str]:
    """Find file_path arguments from Write/Edit-style tool uses."""
    out: list[str] = []
    if not isinstance(content, list):
        return out
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        name = block.get("name")
        if name not in _FILE_PATH_TOOLS:
            continue
        inp = block.get("input") or {}
        fp = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        if isinstance(fp, str) and fp:
            out.append(fp)
    return out


def _project_name(cwd: str | None, path: Path) -> str:
    if cwd:
        return Path(cwd).name or cwd
    # Decode from the project dir name (e.g. -Users-animeshpathak-Claude)
    parent = path.parent.name
    if parent.startswith("-"):
        return parent.lstrip("-").split("-")[-1]
    return parent


# ---------- theming ----------

def load_themes() -> dict:
    with THEMES_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def pick_theme(artifacts: list[str], themes_data: dict) -> tuple[str, dict]:
    """Return (theme_key, theme_dict) given a list of artifact paths."""
    themes = themes_data["themes"]
    if not artifacts:
        return "empty", themes["empty"]

    # Build extension → theme_key map.
    ext_to_key: dict[str, str] = {}
    for key, theme in themes.items():
        for ext in theme.get("extensions", []):
            ext_to_key[ext.lower()] = key

    counts: Counter[str] = Counter()
    for path in artifacts:
        ext = Path(path).suffix.lower()
        key = ext_to_key.get(ext)
        if key:
            counts[key] += 1

    if not counts:
        return "mixed", themes["mixed"]

    # If >1 distinct theme keys present with similar counts, call it mixed.
    top, top_n = counts.most_common(1)[0]
    distinct = len(counts)
    if distinct >= 3:
        return "mixed", themes["mixed"]
    if distinct == 2:
        second_n = counts.most_common(2)[1][1]
        if second_n >= max(1, top_n // 2):
            return "mixed", themes["mixed"]
    return top, themes[top]


# ---------- rendering ----------

def _fmt_when(ts: str | None, mtime: float | None) -> str:
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            dt = None
        if dt:
            return dt.astimezone().strftime("%b %d, %Y · %H:%M")
    if mtime:
        return datetime.fromtimestamp(mtime).strftime("%b %d, %Y · %H:%M")
    return "unknown"


def _fmt_duration(first_ts: str | None, last_ts: str | None) -> str:
    if not first_ts or not last_ts:
        return ""
    try:
        a = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        b = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
    except ValueError:
        return ""
    secs = max(0, int((b - a).total_seconds()))
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h {(secs % 3600) // 60}m"


def _truncate(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_html(sessions: list[dict], themes_data: dict) -> str:
    # sessions are sorted newest-first. Floor number = position from oldest.
    # i.e. newest of 20 → floor 20 (boss), oldest → floor 1.
    n = len(sessions)
    floors = []
    for idx, s in enumerate(sessions):
        floor_num = n - idx  # newest gets highest floor number
        theme_key, theme = pick_theme(s["artifacts"], themes_data)
        floors.append({"floor": floor_num, "theme_key": theme_key, "theme": theme, "session": s})

    special = themes_data.get("special_floors", {})

    # Build sidebar (highest floor first).
    sidebar_items = []
    for f in floors:
        special_label = special.get(str(f["floor"]), {}).get("label")
        label = special_label or f["theme"]["name"]
        sidebar_items.append(
            f'<a class="gate" href="#floor-{f["floor"]}" title="{html.escape(_truncate(f["session"]["first_prompt"], 120))}">'
            f'<span class="gate-num">F{f["floor"]:02d}</span>'
            f'<span class="gate-name">{html.escape(label)}</span>'
            f'</a>'
        )

    floor_cards = []
    for f in floors:
        s = f["session"]
        theme = f["theme"]
        sp = special.get(str(f["floor"]), {})
        accent = sp.get("accent_override") or theme["accent"]
        glow = theme["glow"]
        bg_tint = theme["bg_tint"]
        label = sp.get("label") or theme["name"]
        is_boss = f["floor"] == n  # boss = the newest in this batch
        is_town = f["floor"] == 1

        artifact_items = []
        for art in s["artifacts"][:12]:
            name = Path(art).name
            artifact_items.append(
                f'<li><span class="art-ext">{html.escape(Path(art).suffix or "·")}</span>'
                f'<span class="art-name" title="{html.escape(art)}">{html.escape(name)}</span></li>'
            )
        if len(s["artifacts"]) > 12:
            artifact_items.append(
                f'<li class="more">… and {len(s["artifacts"]) - 12} more</li>'
            )
        if not artifact_items:
            artifact_items.append('<li class="empty-note">No relics forged on this floor.</li>')

        duration = _fmt_duration(s["first_ts"], s["last_ts"])
        meta_bits = [
            f'<span class="meta-pill">📜 {s["message_count"]} msgs</span>',
            f'<span class="meta-pill">🗺 {html.escape(s["project_name"] or "—")}</span>',
            f'<span class="meta-pill">⏱ {_fmt_when(s["last_ts"], s["mtime"])}</span>',
        ]
        if duration:
            meta_bits.insert(2, f'<span class="meta-pill">⌛ {duration}</span>')

        boss_chip = '<span class="chip boss-chip">▲ BOSS FLOOR</span>' if is_boss else ""
        town_chip = '<span class="chip town-chip">✦ SAFE ZONE</span>' if is_town else ""

        floor_cards.append(f'''
<section class="floor" id="floor-{f["floor"]}" style="--accent:{accent};--glow:{glow};--bg-tint:{bg_tint};">
  <div class="floor-frame">
    <header class="floor-header">
      <div class="floor-num-block">
        <div class="floor-num">F{f["floor"]:02d}</div>
        <div class="floor-icon">{theme["icon"]}</div>
      </div>
      <div class="floor-title-block">
        <div class="floor-chips">{boss_chip}{town_chip}<span class="chip theme-chip">{html.escape(theme["name"])}</span></div>
        <h2 class="floor-name">{html.escape(label)}</h2>
        <p class="floor-lore">{html.escape(sp.get("lore") or theme["lore"])}</p>
      </div>
    </header>
    <div class="floor-quest">
      <div class="quest-label">QUEST LOG</div>
      <p class="quest-text">{html.escape(_truncate(s["first_prompt"], 380))}</p>
    </div>
    <div class="floor-body">
      <div class="floor-artifacts">
        <div class="artifacts-label">RELICS FORGED</div>
        <ul>{"".join(artifact_items)}</ul>
      </div>
      <div class="floor-meta">{"".join(meta_bits)}</div>
    </div>
  </div>
</section>
''')

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Aincrad — Session Tower</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg-0: #07080f;
    --bg-1: #0d1020;
    --bg-2: #161a30;
    --ink: #e9ecf5;
    --ink-dim: #8c93b0;
    --ink-faint: #5a6080;
    --rule: rgba(255,255,255,0.08);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg-0); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
    font-feature-settings: "ss01", "cv02"; }}
  body {{
    background:
      radial-gradient(1200px 800px at 80% -10%, rgba(120,80,200,0.18), transparent 60%),
      radial-gradient(900px 600px at 10% 110%, rgba(60,140,200,0.14), transparent 60%),
      linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 100%);
    min-height: 100vh;
  }}

  .layout {{ display: grid; grid-template-columns: 240px 1fr; max-width: 1280px; margin: 0 auto; }}
  @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} aside.sidebar {{ position: static !important; height: auto !important; }} }}

  aside.sidebar {{
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
    padding: 28px 16px 28px 24px;
    border-right: 1px solid var(--rule);
    background: linear-gradient(180deg, rgba(0,0,0,0.4), rgba(0,0,0,0.0));
  }}
  .sidebar-title {{ font-size: 11px; letter-spacing: 0.18em; color: var(--ink-faint); text-transform: uppercase; margin-bottom: 14px; }}
  .gate {{ display: flex; align-items: center; gap: 10px; padding: 7px 10px; margin: 2px 0; border-radius: 8px;
    color: var(--ink-dim); text-decoration: none; font-size: 13px; transition: background .15s, color .15s; border: 1px solid transparent; }}
  .gate:hover {{ background: rgba(255,255,255,0.05); color: var(--ink); border-color: var(--rule); }}
  .gate-num {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; color: var(--ink-faint); width: 32px; }}
  .gate-name {{ flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  main {{ padding: 36px 36px 96px; }}
  .hero {{ padding: 28px 0 24px; border-bottom: 1px solid var(--rule); margin-bottom: 36px; }}
  .hero h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0.02em; font-weight: 600; }}
  .hero .subtitle {{ color: var(--ink-dim); font-size: 14px; }}
  .hero .stats {{ margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .stat {{ font-size: 12px; padding: 5px 10px; background: rgba(255,255,255,0.04); border: 1px solid var(--rule); border-radius: 999px; color: var(--ink-dim); }}

  .floor {{ margin: 0 0 28px; scroll-margin-top: 24px; }}
  .floor-frame {{
    position: relative;
    border-radius: 14px;
    padding: 22px 24px;
    background:
      linear-gradient(180deg, var(--bg-tint), rgba(10,12,22,0.85)),
      linear-gradient(180deg, var(--bg-2), var(--bg-1));
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: 0 0 0 1px rgba(0,0,0,0.5), 0 24px 48px -28px var(--glow);
    overflow: hidden;
  }}
  .floor-frame::before {{
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    background: linear-gradient(180deg, var(--accent), transparent);
    box-shadow: 0 0 16px var(--glow);
  }}

  .floor-header {{ display: flex; gap: 20px; align-items: flex-start; }}
  .floor-num-block {{ flex: 0 0 100px; text-align: center; padding-top: 4px; }}
  .floor-num {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 28px; color: var(--accent); letter-spacing: 0.02em; text-shadow: 0 0 18px var(--glow); }}
  .floor-icon {{ font-size: 34px; margin-top: 4px; color: var(--accent); opacity: 0.85; text-shadow: 0 0 14px var(--glow); }}

  .floor-title-block {{ flex: 1; }}
  .floor-chips {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }}
  .chip {{ font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; padding: 4px 9px; border-radius: 999px;
    background: rgba(255,255,255,0.05); color: var(--ink-dim); border: 1px solid var(--rule); }}
  .theme-chip {{ color: var(--accent); border-color: var(--accent); opacity: 0.85; }}
  .boss-chip {{ color: #ffd1d1; background: rgba(239,68,68,0.18); border-color: rgba(239,68,68,0.5); }}
  .town-chip {{ color: #fff3cf; background: rgba(234,179,8,0.15); border-color: rgba(234,179,8,0.45); }}
  .floor-name {{ margin: 2px 0 6px; font-size: 22px; font-weight: 600; letter-spacing: 0.01em; }}
  .floor-lore {{ margin: 0; color: var(--ink-dim); font-style: italic; font-size: 13.5px; line-height: 1.5; }}

  .floor-quest {{ margin: 18px 0 16px; padding: 12px 14px; background: rgba(0,0,0,0.25); border-left: 2px solid var(--accent); border-radius: 0 8px 8px 0; }}
  .quest-label {{ font-size: 10px; letter-spacing: 0.2em; color: var(--ink-faint); margin-bottom: 4px; }}
  .quest-text {{ margin: 0; font-size: 14px; line-height: 1.55; color: var(--ink); }}

  .floor-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  @media (max-width: 720px) {{ .floor-body {{ grid-template-columns: 1fr; }} .floor-header {{ flex-direction: column; }} .floor-num-block {{ text-align: left; }} }}

  .artifacts-label, .meta-label {{ font-size: 10px; letter-spacing: 0.2em; color: var(--ink-faint); margin-bottom: 6px; }}
  .floor-artifacts ul {{ list-style: none; padding: 0; margin: 0; }}
  .floor-artifacts li {{ display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px dashed rgba(255,255,255,0.05); font-size: 13px; }}
  .floor-artifacts li:last-child {{ border-bottom: none; }}
  .art-ext {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; color: var(--accent); width: 56px; font-size: 11.5px; opacity: 0.85; }}
  .art-name {{ color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .more {{ color: var(--ink-faint); font-style: italic; }}
  .empty-note {{ color: var(--ink-faint); font-style: italic; border: none !important; }}

  .floor-meta {{ display: flex; flex-wrap: wrap; gap: 6px; align-content: flex-start; }}
  .meta-pill {{ font-size: 11.5px; padding: 4px 10px; background: rgba(255,255,255,0.04); border: 1px solid var(--rule); border-radius: 999px; color: var(--ink-dim); }}

  footer {{ text-align: center; margin: 40px 0 0; color: var(--ink-faint); font-size: 12px; }}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-title">▲ Teleport Gates</div>
    {"".join(sidebar_items)}
  </aside>
  <main>
    <section class="hero">
      <h1>Aincrad — Session Tower</h1>
      <div class="subtitle">The floating castle of your latest {n} Claude Code sessions. Ascend the gates on the left; the boss floor is current, the foundations are history.</div>
      <div class="stats">
        <span class="stat">Floors: {n}/20</span>
        <span class="stat">Rebuilt: {now}</span>
        <span class="stat">Source: ~/.claude/projects</span>
      </div>
    </section>
    {"".join(floor_cards)}
    <footer>« Link Start »</footer>
  </main>
</div>
</body>
</html>
"""


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Aincrad Session Tower.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not PROJECTS_DIR.exists():
        print(f"No sessions dir at {PROJECTS_DIR} — nothing to build.", file=sys.stderr)
        return 1

    jsonl_files = sorted(
        PROJECTS_DIR.glob("*/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, args.limit)]

    if not jsonl_files:
        print(f"No .jsonl session files under {PROJECTS_DIR}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Found {len(jsonl_files)} sessions; parsing…")

    sessions = []
    for p in jsonl_files:
        try:
            sessions.append(parse_session(p))
        except Exception as e:
            if not args.quiet:
                print(f"  skipping {p.name}: {e}", file=sys.stderr)

    if not sessions:
        print("No sessions parsed successfully.", file=sys.stderr)
        return 1

    themes_data = load_themes()
    html_doc = render_html(sessions, themes_data)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_doc, encoding="utf-8")

    if not args.quiet:
        print(f"Tower built: {args.output}")
        print(f"  Floors: {len(sessions)} (Floor {len(sessions)} = boss, Floor 1 = Town of Beginnings)")

    if not args.no_open:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(args.output)], check=False)
            elif sys.platform.startswith("linux"):
                subprocess.run(["xdg-open", str(args.output)], check=False)
            elif sys.platform == "win32":
                os.startfile(str(args.output))  # type: ignore[attr-defined]
        except Exception as e:
            if not args.quiet:
                print(f"(Could not auto-open: {e})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
