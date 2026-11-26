# Puyo Puyo 2 — Mega Drive / Genesis English Translation

Port of `puyopuy2e` (Sega System C2 arcade English translation) to the Sega Mega Drive
release **`Puyo Puyo 2 (Japan) (v1.1).md`** (raw 2 MB binary dump, CRC32 `25b7b2aa`).

## Build

Requires Python 3 standard library only (no Pillow or external tools):

```sh
python3 make_puyopuy2e_md.py "Puyo Puyo 2 (Japan) (v1.1).md"
```

Optional title logo mode (`--logo`, default `no-red-puyos`):

- `no-red-puyos` — English red `"Puyo Puyo"` + gold `2` + green `通` (red handakuten puyos culled)
- `with-red-puyos` — English `"Puyo Puyo"` with cropped 3×2 red puyos over each `u`
- `original` — original Japanese `ぷよぷよ通` title logo

## What is translated

**Shared with the Sega C2 arcade port:**
- 8×16 Spleen text engine (`0x0151cc`), page hooks (`0x110000`), all 58 character profiles and 12 attract tutorial pages (`0x017e6c..0x01937e`)
- Title logo (`0x02836a`, `0x0285a6`, `0x0b751d`), tutorial titles (`0x092640`, `0x044ec8`), tutorial `ALL CLEAR` (`0x045503`)
- Play HUD (`CHAIN`, `OFFSET`, `K.O.` big + small, `YAY!`), level select curry plates (`EXTRA MILD`..`EXTRA HOT`)
- Tower (`PICK YOUR RIVAL`, Nomi `I'M HERE` icon + blown-up battle/profile sprites), Continue (`CONTINUE?`), Act Against AIDS (`COURAGE AND LOVE`)

**Mega Drive-exclusive screens & strings:**
- Main Mode Select header (`CHOOSE A MODE!`) and all 3 animated Carbuncle mouths (`1 PLAYER / PUYO`, `2 PLAYER / PUYO`, `OPTIONS`)
- In-game Pause (`PAUSE`, `0x0900be`) and P2 Join-In banner (`CHALLENGER!`, `0x08c8f9`)
- 2P Special Rule Select header (`CHOOSE A RULE!`) and all 6 rule descriptions (`0x103a20`)
- Rule Edit (`えでぃっとだよ`) menu, editor, and nuisance hardness labels (`NORMAL`, `HARD`, `HARD CAP`) (`0x091461`, `0x0177a6..0x017997`)
- `GAME OPTION`, secret `BATTLE MODE`, and Ending Record romaji (`RULE SET`, `OFFSET`, `CHAIN LIMIT`, `WINS`, `MAX CHAIN`)
- Mega Drive ROM header checksum (`0x00018e`) recomputed automatically

*(Ending staff roll Japanese names in `0x1069fe` / `0x106efd` / `0x107476` are left untouched, matching the arcade translation.)*
