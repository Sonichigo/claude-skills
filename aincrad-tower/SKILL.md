---
name: aincrad-session-tower
description: Render the user's latest 20 Claude Code sessions as a 20-floor Aincrad-style floating castle from Sword Art Online — each floor themed after the artifacts (code, slides, docs, etc.) created during that session, with the newest session as the top boss floor. Trigger this skill whenever the user asks to "build/show/refresh/open my Aincrad", "tower", "session tower", "SAO floors", "floor map", "visualize my sessions/chats", "where have I been working", or any request to see a creative map of recent conversations. Default trigger even if the user only loosely references SAO, anime, floors, or "the castle" — the skill is the canonical answer to those.
---

# Aincrad Session Tower

Generates an SAO-Aincrad-styled HTML castle that visualizes the user's latest 20 Claude Code sessions as 20 floors. Floor 1 is the oldest, Floor 20 is the **boss floor** (newest). Each floor's theme is chosen from the dominant artifact type created during that session, so a session full of `.py` edits gets a different look than one that produced a `.pptx`.

## When to invoke

Run the build script. That is the entire workflow — there is no manual rendering. The script is deterministic, fast, and handles every concern (parsing, theming, layout, navigation, opening in the browser).

Trigger on phrases like:
- "build my Aincrad / tower / floors"
- "show me my session tower"
- "refresh the tower" / "rebuild the castle"
- "open the floor map"
- "where have I been working lately?" (with SAO/anime framing)

If the user asks to *customize* themes (different colors, new artifact mappings, more floors), read `references/floor_themes.md` first — it explains the theme model and how to edit it.

## How to run it

The script lives at `scripts/build_tower.py` relative to this SKILL.md. It needs only the Python 3 standard library.

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/build_tower.py"
```

If `$CLAUDE_PLUGIN_ROOT` is not set, use the absolute path to this skill directory. The script:

1. Globs `~/.claude/projects/*/*.jsonl` (all Claude Code sessions across every project).
2. Sorts them by last-modified time, descending, takes the latest 20.
3. Parses each session to extract: first user prompt (quest title), project name (from `cwd`), files created/edited (from `Write` / `Edit` / `MultiEdit` / `NotebookEdit` tool uses), message count, and duration.
4. Picks each floor's theme based on the dominant artifact extension (see `references/floor_themes.md`).
5. Writes a self-contained HTML file to `~/.claude/aincrad-tower/index.html`.
6. Opens it in the default browser (`open` on macOS).

### Flags

- `--no-open` — build without launching the browser.
- `--output PATH` — write somewhere other than the default.
- `--limit N` — show fewer than 20 floors (useful for testing).
- `--quiet` — suppress progress output.

## What the user sees

A single dark-themed HTML page styled like a fantasy MMO interface:

- **Floor stack**: 20 floors rendered top-down with Floor 20 (boss floor) at the top of the document. Each floor is a card showing its number, project name, quest title (truncated first prompt), themed icon, artifact list, and metadata (message count, when, duration).
- **Teleport Gate sidebar**: fixed list of all 20 floors. Clicking warps the page anchor to that floor. Hover reveals quest title.
- **Theme styling per floor**: each floor card gets accent colors, a dungeon name (e.g., "Mainframe Catacombs" for Python, "Hall of Mirrors" for PPTX), and an icon glyph reflecting the artifacts created.
- **Special floors**: Floor 1 is labeled "Town of Beginnings" (safe-zone styling, soft gold). Floor 20 is "Ruby Palace — Boss Floor" (deep crimson, glow effect).
- **Empty-artifact floors** become "Wanderer's Plains" — a safe-zone aesthetic indicating a conversation that didn't produce files.

## Why this design

- **HTML, not Markdown**: the SAO aesthetic depends on color, gradients, and layered glow. Markdown can't carry it.
- **Self-contained file**: no external CSS/JS dependencies. The user can move the file, attach it, share it.
- **Stable URL** (`~/.claude/aincrad-tower/index.html`): always overwrites the same path so the user can pin the tab in their browser and just refresh.
- **Newest = top of document**: matches Aincrad lore (you ascend the castle) *and* matches the user's mental model — "what have I been doing lately?" answers from the top.
- **Themed by artifact, not by topic**: artifact type is objective and trivial to extract; topic inference would be lossy and hallucination-prone.

## Reference files

- `references/floor_themes.md` — the full extension → theme map. Read this when the user wants to add/edit themes.
- `assets/themes.json` — machine-readable theme data the script consumes. Edit this (not the script) to add new artifact themes.
