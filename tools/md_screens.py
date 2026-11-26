"""Mega Drive-exclusive screens and strings for Puyo Puyo 2 (v1.1):
  - Main Mode Select header + 3 animated Carbuncle mouths (bank 0x10)
  - In-game Pause sign (0x0900be) and P2 Join-In banner (0x08c8f9)
  - 2P Special Rule Select header + 6 rule lines (bank 0x10)
  - Rule Edit menu + editor + nuisance hardness values (0x091461 + 0x0177a6..0x017997)
  - Game Option / Ending Record romaji strings (in place, same lengths)"""
import os, struct
import font, gfx, labels, linkmsg, png

# Palette index remap from arcade choose_rule.png ([0,2,3,4,5,7]) to MD headers ([0,8,9,10,11,12])
HEADER_REMAP = {0: 0, 2: 8, 3: 9, 4: 10, 5: 11, 7: 12}

# In-place same-length romaji replacements in GAME OPTION, secret BATTLE MODE, and Ending Record
MD_STRINGS = (
    (b"RULE HENKA",   b"RULE SET  "),
    (b"SOUSAI",       b"OFFSET"),
    (b"RENSA SIBARI", b"CHAIN LIMIT "),
    (b"SENSYU",       b"WINS  "),
    (b"^2MAX RENSA",  b"^2MAX CHAIN"),
)

# 2P Special Rule Select (map 0x103a20, tiles 0x103de2): 6 lines of 18x2 cells (yellow=11, white=15)
SPECIAL_RULES = (
    (0x000, "[Normal] rules!"),
    (0x048, "[Hard Puyo]!"),
    (0x090, "[Point Puyo]!"),
    (0x0d8, "[Pop 2] to clear!"),
    (0x120, "[Pop 6] to clear!"),
    (0x168, "[Rule Edit]!"),
)

# Carbuncle mouth text on Main Mode Select (0x10005a / 0x100626): 3 modes x 3 mouth-open frames
MOUTH_LABELS = (
    ("1 PLAYER", "PUYO"),
    ("2 PLAYER", "PUYO"),
    ("OPTIONS",),
)

# Rule Edit (0x091461 glyphs 0x00..0x3b, preserving curve icons 0x3c..0x3f and digits 256..277)
RULE_EDIT_MENU_AT = 0x0177b2
RULE_EDIT_MENU_PTRS = 0x0177a6
RULE_EDIT_MENU = (
    (2,  10, "RULE EDIT MENU", 0, False),
    (8,  6,  "START GAME",     0, True),
    (13, 5,  "EDIT RULE",      1, True),
    (18, 6,  "RULE SELECT",    0, True),
)

RULE_EDIT_CREATE_AT = 0x017806
RULE_EDIT_CREATE_PTRS = 0x0177e6
RULE_EDIT_CREATE = (
    (1,  12, "RULE EDITOR",   0, False),
    (4,  1,  "DONE",          0, True),
    (7,  1,  "COPY FROM",     0, True),
    (7,  31, "RULE",          0, False),
    (10, 1,  "PUYO TO POP",   0, True),
    (10, 34, "PUYO",          0, False),
    (13, 1,  "NUISANCE RATE", 0, True),
    (13, 36, "PT",            0, False),
    (16, 1,  "NUISANCE PTS",  0, True),
    (16, 36, "PT",            0, False),
    (19, 1,  "NUISANCE TYPE", 0, True),
    (22, 1,  "CHAIN RATE",    0, True),
    (22, 28, "TYPE",          0, False),
    (25, 1,  "ALL CLEAR",     0, True),
    (25, 34, "PUYO",          0, False),
)

# Rule Editor digit & curve VRAM coordinates (patch 16-bit immediates in 0x0178ba..0x017960
# so every value + unit right-aligns cleanly to column 37).
RULE_EDIT_VRAM = (
    (0x0178bc, 0xc3c6),   # r7  copy rule digit 1..6 -> col 37 (after "RULE" at 32..35)
    (0x0178e4, 0xc53c),   # r10 puyo to pop -> cols 30..32 (space col 33, "PUYO" at 34..37)
    (0x0178f4, 0xc6c0),   # r13 nuisance rate -> cols 32..34 (space col 35, "PT" at 36..37)
    (0x017904, 0xc840),   # r16 nuisance pts -> cols 32..34 (space col 35, "PT" at 36..37)
    (0x017914, 0xccbc),   # r25 all clear -> cols 30..32 (space col 33, "PUYO" at 34..37)
    (0x017946, 0xcb44),   # r22 chain rate digit 1..4 -> col 34 (after "TYPE" at 28..31)
    (0x017960, 0xcb48),   # r22 chain curve icon -> cols 36..37
)

RULE_EDIT_HARD_AT = 0x017980    # 3 fixed 8-byte records: 80 82 <4 glyph bytes> ff 00
RULE_EDIT_HARD = ("  NORMAL", "    HARD", "HARD CAP")


def _remap(img, table):
    return [[table[v] for v in row] for row in img]


def _render_rule_line_md(text, cells):
    """18x2 rule line in Spleen 8x16, white (15) with [bracketed] words in yellow (11)."""
    glyphs = font.font()
    plain = text.replace('[', '').replace(']', '')
    img = [[0] * (8 * cells) for _ in range(16)]
    # Snap to 8px tile boundary so identical characters share tiles across all 6 rule lines
    x = ((cells - len(plain)) // 2) * 8
    colour = 0xf
    for ch in text:
        if ch in '[]':
            colour = 0xb if ch == '[' else 0xf
            continue
        for y, row in enumerate(glyphs[ord(ch)]):
            for i in range(8):
                if row >> (7 - i) & 1:
                    img[y][x + i] = colour
        x += 8
    return img


def apply_options(prog):
    for old, new in MD_STRINGS:
        assert len(old) == len(new)
        i = prog.find(old)
        if i < 0 or prog.find(old, i + 1) >= 0:
            raise SystemExit('MD option text %r: not found once' % old)
        prog[i:i + len(new)] = new


def _mouth_cavity_and_erase(blk, frame_idx):
    """Build a smooth, blotch-free Carbuncle mouth interior while preserving fangs, black lip
    outline, and original inner-rim shadow (2). Flood-fills strictly inside the mouth wall so
    cavity painting can never clip into Carbuncle's lips, then shades the upper throat and side
    cheeks in deep red (3) and the lower mouth floor in bright red (4) for 3D depth matching
    the original art."""
    h, w = len(blk), len(blk[0])
    out = [row[:] for row in blk]

    # Mark exterior/wall pixels that must never be painted (bg, black rim, yellow skin, fangs,
    # inner-rim dark-red shadow '2' bordering the rim, and outer lip/cheek orange shading).
    outer = (0, 1, 6, 7, 8)
    wall = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            v = blk[y][x]
            if v in outer or (y <= 11 and v == 15 and (x < 26 or x > 54)):
                wall[y][x] = True
            elif v == 2 and any(
                0 <= y + dy < h and 0 <= x + dx < w and blk[y + dy][x + dx] in outer
                for dy in (-1, 0, 1) for dx in (-2, -1, 0, 1, 2)
            ):
                wall[y][x] = True
            elif v in (4, 5) and any(
                0 <= y + dy < h and 0 <= x + dx < w and blk[y + dy][x + dx] in (6, 7, 8)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            ):
                wall[y][x] = True

    # 4-connected flood-fill from mouth center (40, 20) strictly inside wall
    cavity = [[False] * w for _ in range(h)]
    seed = (40, 20)
    if not wall[seed[1]][seed[0]]:
        cavity[seed[1]][seed[0]] = True
        stack = [seed]
        while stack:
            cx, cy = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and not wall[ny][nx] and not cavity[ny][nx]:
                    cavity[ny][nx] = True
                    stack.append((nx, ny))

    # Shade cavity like Compile's original: deep-red (3) upper throat + side cheeks, with
    # bright-red (4) arching gently downward into the lower mouth floor (staying inside the
    # curved 2/3 lip corners so it never clips into Carbuncle's lips).
    top_y, arch, y_bot, pad_hi, pad_lo = (
        (17.0, 3.0, 46.0, 6.0, 3.0),   # f0: wide open
        (19.0, 3.0, 39.0, 6.0, 2.0),   # f1: mid-open
        (16.0, 2.5, 30.0, 6.0, 2.0),   # f2: resting / unselected
    )[frame_idx]
    for y in range(h):
        xs = [x for x in range(w) if cavity[y][x]]
        if not xs:
            continue
        x_lo, x_hi = xs[0], xs[-1]
        t = max(0.0, min(1.0, (y - top_y) / max(1.0, y_bot - top_y)))
        side_pad = pad_hi + (pad_lo - pad_hi) * (t * t)
        for x in xs:
            dx = (x - 39.5) / 24.0
            if y >= top_y + arch * (dx * dx) and x >= x_lo + side_pad and x <= x_hi - side_pad:
                out[y][x] = 4
            else:
                out[y][x] = 3
    return out, cavity


def _draw_mouth_text(clean, cavity, lines, frame_idx):
    """Draw 1 or 2 centred English lines onto the cleaned Carbuncle mouth cavity."""
    h, w = len(clean), len(clean[0])
    out = [row[:] for row in clean]
    # Vertical squash / fade across mouth-closing frames: f0 (open), f1 (mid), f2 (small)
    fill = (9, 10, 10)[frame_idx]
    outline = (2, 2, 11)[frame_idx] if frame_idx == 2 else 2
    if frame_idx == 2:
        fill, outline = 10, 2

    # Compute mouth vertical centre from cavity
    c_ys = [y for y in range(h) for x in range(w) if cavity[y][x]]
    cy = (min(c_ys) + max(c_ys)) // 2

    if len(lines) == 2:
        # 2 compact lines (11px tall in f0, 9px in f1, 7px in f2)
        lh = (12, 10, 8)[frame_idx]
        gap_y = (2, 1, 1)[frame_idx]
        total_h = 2 * lh + gap_y
        y_starts = (cy - total_h // 2 + 1, cy - total_h // 2 + 1 + lh + gap_y)
    else:
        lh = (15, 13, 11)[frame_idx]
        y_starts = (cy - lh // 2,)

    text_mask = [[0] * w for _ in range(h)]
    for text, y0 in zip(lines, y_starts):
        # Render in title_font (13px tall) scaled to target height lh; pad '1' to '2' width
        # so "1 PLAYER" and "2 PLAYER" share their "PLAYER" tiles on the 8x8 tile grid.
        masks = [labels.letter_mask(ch) for ch in text]
        gap = 1
        widths = [max(len(m[0]), 6) if ch == '1' else len(m[0]) for ch, m in zip(text, masks)]
        tw = sum(widths) + gap * (len(masks) - 1)
        x = (w - tw) // 2
        for m, mw in zip(masks, widths):
            ox = (mw - len(m[0])) // 2
            for dy in range(lh):
                sy = dy * 13 // lh
                for dx in range(len(m[0])):
                    if m[sy][dx]:
                        yy, xx = y0 + dy, x + ox + dx
                        if 0 <= yy < h and 0 <= xx < w and cavity[yy][xx]:
                            text_mask[yy][xx] = 1
            x += mw + gap

    # Draw dark-red outline (2) then white/pink fill inside cavity only (never touches fangs/rim)
    for y in range(h):
        for x in range(w):
            if text_mask[y][x]:
                out[y][x] = fill
            elif cavity[y][x] and any(
                0 <= y + dy < h and 0 <= x + dx < w and text_mask[y + dy][x + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            ):
                out[y][x] = outline
    return out


def apply_mode_select(streams):
    tiles, tmap = streams.get(0x100626), streams.get(0x10005a)
    # Combine header (33x3 at 0x000, uses 69/98 tiles) + all 9 Carbuncle mouth frames in one
    # replace_blocks call so header's 29 spare tiles join the 233-tile mouth pool (331 total).
    hdr = _remap(png.read(os.path.join(labels.ASSETS, 'md_choose_mode.png')), HEADER_REMAP)
    # Seed clean mouth templates from mode 2 (おぷしょん, single line with clean bottom lip)
    templates = [_mouth_cavity_and_erase(gfx.block_pixels(tiles, tmap, 0x282 + (6 + f) * 0x78, 10, 6, 10), f)
                 for f in range(3)]
    blocks = [(0x000, 33, 3, hdr, None)]
    for m, lines in enumerate(MOUTH_LABELS):
        for f in range(3):
            off = 0x282 + (m * 3 + f) * 0x78
            clean, cavity = templates[f]
            img = _draw_mouth_text(clean, cavity, lines, f)
            crop = lambda r0, c0, cw, ch: [row[c0 * 8:(c0 + cw) * 8] for row in img[r0 * 8:(r0 + ch) * 8]]
            if f == 0:
                blocks.append((off + 2, 8, 1, crop(0, 1, 8, 1), 10))
                blocks.append((off + 20, 10, 5, crop(1, 0, 10, 5), 10))
            elif f == 1:
                blocks.append((off + 22, 8, 4, crop(1, 1, 8, 4), 10))
            else:
                blocks.append((off + 22, 8, 3, crop(1, 1, 8, 3), 10))
    gfx.replace_blocks(tiles, tmap, blocks, blank=0xbc)


def apply_pause(streams):
    # きゅうけい (0x0900be): 2 x 4x3 sprites = 64x24, outline 1, vertical shade 7->6->5->4->3
    # (renders pink on P1 palette 0 and blue on P2 palette 1).
    m = labels.scaled_mask("PAUSE", 9, 16, 2)
    w, h = len(m[0]), len(m)
    img = [[0] * 64 for _ in range(24)]
    x0, y0 = (64 - w) // 2, (24 - h) // 2
    shades = (7, 7, 7, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                img[y0 + y][x0 + x] = shades[y]
    img = labels.ring(img, 1, {3, 4, 5, 6, 7})
    labels.put_tiles(streams.get(0x0900be), img, labels.sprite_order(0, 4, 3, 2))


def apply_p2_join(streams):
    # 乱入されたよ (0x08c8f9): 12x2 column-major = 96x16, fill 15 outlined in 1
    img = labels.render("CHALLENGER!", 96, 16, 0xf, 0x1)
    labels.put_tiles(streams.get(0x08c8f9), img, labels.sprite_order(0, 12, 2, 1))


def apply_special_rules(streams):
    # 2P Special Rule Select header (0x103017 @ 0x8c0, 33x3, tiles 0x1031bf)
    hdr = _remap(png.read(os.path.join(labels.ASSETS, 'choose_rule.png')), HEADER_REMAP)
    gfx.replace_block(streams.get(0x1031bf), streams.get(0x103017), 0x8c0, 33, 3, hdr)
    # 6 rule descriptions (0x103a20 @ 0x000..0x1af, 18x2 each, tiles 0x103de2).
    # Use blank=0x80 (empty in 0x103de2 and >= 0x78, outside 0x1031bf's 120-tile VRAM range).
    rtiles = streams.get(0x103de2)
    assert not any(rtiles[0x80 * gfx.TILE:0x81 * gfx.TILE])
    blocks = [(off, 18, 2, _render_rule_line_md(txt, 18), 18) for off, txt in SPECIAL_RULES]
    gfx.replace_blocks(rtiles, streams.get(0x103a20), blocks, blank=0x80)


def apply_rule_edit(prog, streams, at, end):
    """Rule Edit menu + editor + nuisance hardness values (glyph stream 0x091461).
    Uses glyph slots 0x00..0x3b (60 slots) as 8x16 letter pairs via linkmsg helpers,
    preserving chain-curve icons 0x3c..0x3f and narrow digits at tiles 256..277."""
    glyphs = font.font()
    index = {}
    for group in (RULE_EDIT_MENU, RULE_EDIT_CREATE):
        for _, _, txt, sh, _ in group:
            for p in linkmsg.pairs(txt, sh):
                if p != '  ':
                    index.setdefault(p, len(index))
    for txt in RULE_EDIT_HARD:
        for p in linkmsg.pairs(txt, 0):
            if p != '  ':
                index.setdefault(p, len(index))
    if len(index) > 0x3c:
        raise SystemExit('rule_edit: %d glyph pairs, max 60 (0x00..0x3b)' % len(index))

    tiles = streams.get(0x091461)
    for p, g in index.items():
        img = linkmsg.glyph_pixels(p, glyphs)
        for q, (dx, dy) in enumerate(((0, 0), (0, 8), (8, 0), (8, 8))):
            cell = [row[dx:dx + 8] for row in img[dy:dy + 8]]
            gfx.tile_put(tiles, 4 * g + q, cell)
    blank = [[0] * 8 for _ in range(8)]
    for g in range(len(index), 0x3c):
        for q in range(4):
            gfx.tile_put(tiles, 4 * g + q, blank)

    def encode_pairs(txt, sh):
        return bytes(0x81 if p == '  ' else index[p] for p in linkmsg.pairs(txt, sh))

    def write_screen(orig_at, ptr_table, rows, at):
        assert at % 2 == 0
        start = at
        data = bytearray()
        ptrs = []
        for k, (row, col, txt, sh, is_item) in enumerate(rows):
            if len(data) % 2:
                data.append(0)
            if is_item:
                ptrs.append(start + len(data))
            voff = row * 0x80 + col * 2
            data += struct.pack('>H', voff) + b'\x80\x82' + encode_pairs(txt, sh)
            data.append(0xff if k == len(rows) - 1 else 0xfe)
        if len(data) % 2:
            data.append(0)
        if at + len(data) > end:
            raise SystemExit('rule_edit: no room')
        prog[at:at + len(data)] = data
        prog[orig_at:orig_at + 6] = struct.pack('>HI', 0xffff, start)
        for idx, p in enumerate(ptrs):
            prog[ptr_table + 4 * idx:ptr_table + 4 * idx + 4] = struct.pack('>I', p)
        return at + len(data)

    at = write_screen(RULE_EDIT_MENU_AT, RULE_EDIT_MENU_PTRS, RULE_EDIT_MENU, at)
    at = write_screen(RULE_EDIT_CREATE_AT, RULE_EDIT_CREATE_PTRS, RULE_EDIT_CREATE, at)

    # 3 fixed 8-byte nuisance hardness records at 0x017980..0x017997
    for k, txt in enumerate(RULE_EDIT_HARD):
        rec = b'\x80\x82' + encode_pairs(txt, 0) + b'\xff\x00'
        assert len(rec) == 8, 'hardness record %r must be 8 bytes, got %d' % (txt, len(rec))
        off = RULE_EDIT_HARD_AT + 8 * k
        prog[off:off + 8] = rec

    # Align right-hand digits & chain curve flush to column 37 with their English units
    for addr, vram in RULE_EDIT_VRAM:
        prog[addr:addr + 2] = struct.pack('>H', vram)

    return at


def apply(prog, streams, at, end):
    apply_options(prog)
    apply_mode_select(streams)
    apply_pause(streams)
    apply_p2_join(streams)
    apply_special_rules(streams)
    return apply_rule_edit(prog, streams, at, end)
