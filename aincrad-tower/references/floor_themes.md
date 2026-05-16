# Floor Themes Reference

The script picks a theme per floor by reading every file path used in `Write` / `Edit` / `MultiEdit` / `NotebookEdit` tool calls in that session, mapping each path's extension to a theme via `assets/themes.json`, and choosing the most common theme. Three or more distinct themes → "Grand Crossroads" (mixed). Two themes near-tied → "Grand Crossroads" too. No artifacts → "Wanderer's Plain" (safe zone). Empty extension match but artifacts exist → "Grand Crossroads".

## Theme catalog

| Theme key       | Floor name              | Extensions                                                                 | Vibe                          |
| --------------- | ----------------------- | -------------------------------------------------------------------------- | ----------------------------- |
| code_python     | Mainframe Catacombs     | `.py`, `.ipynb`                                                            | Green-glow server labyrinth   |
| code_js         | Neon Script Forest      | `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`                               | Cyan electric forest          |
| code_systems    | Iron Bastion            | `.go`, `.rs`, `.java`, `.kt`, `.cpp`, `.c`, `.h`, `.hpp`, `.cs`, `.swift`  | Steel ramparts                |
| shell           | The Forge               | `.sh`, `.bash`, `.zsh`, `.fish`, `.ps1`                                    | Orange anvils                 |
| data_sql        | Crystal Cavern          | `.sql`                                                                     | Sapphire columns              |
| data_tabular    | Merchant Bazaar         | `.csv`, `.tsv`, `.xlsx`, `.xls`, `.parquet`                                | Warm market stalls            |
| config          | Rune Chamber            | `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, `.env`                          | Inscribed declarative runes   |
| doc_word        | Scriptorium             | `.docx`, `.doc`, `.odt`, `.rtf`                                            | Parchment scriptorium         |
| doc_slides      | Hall of Mirrors         | `.pptx`, `.ppt`, `.key`, `.odp`                                            | Gold presentation hall        |
| doc_pdf         | Tome Vault              | `.pdf`                                                                     | Locked tome vault             |
| markup_md       | Scroll Archive          | `.md`, `.mdx`, `.rst`, `.txt`                                              | Sepia scroll shelves          |
| web             | Crystal Palace          | `.html`, `.css`, `.scss`, `.sass`, `.vue`, `.svelte`                       | Magenta glass palace          |
| image           | Gallery of Visions      | `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`, `.webp`                           | Framed pixel galleries        |
| mixed           | Grand Crossroads        | — (chosen when >1 theme appears)                                           | Star-vaulted crossroads       |
| empty           | Wanderer's Plain        | — (chosen when no artifacts)                                               | Misty safe-zone grassland     |

## Special floors

Floors 1 and 20 get badges regardless of theme:

- **Floor 1** — "Town of Beginnings" tag, soft gold accent override. The oldest of the latest 20.
- **Floor 20** (or whatever floor is the newest in the batch) — "Ruby Palace — Boss Floor" tag, crimson accent override. The current frontier.

If fewer than 20 sessions exist on disk, the newest still gets boss styling.

## How to customize

To add a new theme or remap extensions, edit `assets/themes.json`. The keys you can touch per theme:

```json
{
  "name": "string — shown as the floor's dungeon name",
  "icon": "single glyph — shown next to the floor number",
  "accent": "hex color — drives the left edge, floor number, glow",
  "glow": "rgba string — used for shadow/halo",
  "bg_tint": "hex — subtle tint over the card background",
  "lore": "italic flavor text shown under the floor name",
  "extensions": [".ext1", ".ext2"]
}
```

To add a special label to another floor, add a key to `special_floors` in `themes.json`:

```json
"10": { "label": "Mirror Lake", "accent_override": "#5eead4", "lore": "Halfway point of the climb." }
```

After editing, just rerun the script — no other steps required. The HTML is regenerated from scratch each build.
