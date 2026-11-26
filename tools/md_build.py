"""Builds the English Mega Drive ROM from Puyo Puyo 2 (Japan) (v1.1).md.

Reuses Zanac's arcade helpers and assets directly with zero edits to the arcade modules.
Only the Spleen 8x16 font goes in bank 0x090000 (required by the 16-bit table entry at
0x09000e); hooks, English script pages, level sprite lists, and Rule Edit strings live in
the empty 448 KB region starting at 0x110000."""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'text'))
sys.path.insert(0, os.path.join(ROOT, 'font'))
import font, gfx, labels, levels, logo, md_screens, png, script_en, text, title_font, titles

# Bank 0x090000 (font offset must be a 16-bit offset in bank 0x090000; free 0xff from 0x993bf)
FONT_BANK_ENTRY = 0x09000e
FONT = 0x099400

# Empty 448 KB region (0x110000..0x17ffff) for 32-bit-addressed code and tables
HOOKS = 0x110000
DATA_AT = 0x110100
DATA_END = 0x118000

# 68000 code hooks
TEXT_PUT = 0x0151cc
TEXT_PUT_END = 0x015314
OP03_PATCH = (0x014e76, 14)
OP0B_PATCH = (0x014ece, 24)

# All 70 MD script pages (58 character profiles + 12 tutorials), 1-to-1 with script_en.TEXT[:70]
MD_PAGES = (
    0x017e6c, 0x017ecc, 0x017f0e, 0x017f64, 0x017fb0, 0x017fd8, 0x018030, 0x018086,
    0x0180cc, 0x018120, 0x01816e, 0x0181b2, 0x018218, 0x01828a, 0x0182d6, 0x01830a,
    0x01835c, 0x018386, 0x0183e0, 0x018426, 0x018482, 0x0184ce, 0x018514, 0x018552,
    0x01858c, 0x0185f4, 0x01862a, 0x01866e, 0x0186b2, 0x0186da, 0x01873c, 0x018766,
    0x0187ce, 0x018832, 0x018898, 0x0188e6, 0x018918, 0x018968, 0x01899c, 0x0189da,
    0x018a18, 0x018a50, 0x018a8e, 0x018aee, 0x018b2e, 0x018b8c, 0x018bd4, 0x018c10,
    0x018c58, 0x018cac, 0x018d00, 0x018d36, 0x018d82, 0x018dea, 0x018e32, 0x018e62,
    0x018eba, 0x018f14, 0x018f7c, 0x018fe4, 0x01903e, 0x019088, 0x0190ce, 0x019156,
    0x0191a8, 0x0191dc, 0x019222, 0x01926c, 0x0192dc, 0x01933e,
)

# Shared MD stream / sprite table addresses
LOGO_TABLES = (0x02836a, 0x0285a6)
LOGO_TILES = 0x0b751d
TUT_TILES = 0x092640
TUT_MAP = 0x044ec8
ALLCLEAR_MAP = 0x045503
CHAIN_TILES = 0x083f37
KO_BIG_TILES = 0x086a7f
KO_SMALL_TILES = 0x085dcd
YAY_TILES = 0x086fa1
YAY_LIST = 0x01a2b8
LEVEL_TILES = 0x0863d1
LEVEL_TABLE = 0x01a6e2
TOWER_TILES = 0x0c62d1
CONT_MAP = 0x0cc655
CONT_TILES = 0x0cca17
AIDS_MAP = 0x03eaff
AIDS_TILES = 0x03ee26


def _patch_file(name):
    return open(os.path.join(ROOT, 'patch', name), 'rb').read()


def _relocate(blob, old, new, count):
    assert blob.count(old) == count, 'expected %d hits, got %d' % (count, blob.count(old))
    return blob.replace(old, new)


def _jmp(prog, at, to, length):
    prog[at:at + length] = struct.pack('>HI', 0x4ef9, to) + b'\x4e\x71' * ((length - 6) // 2)


def _apply_text(prog, at, end):
    assert len(MD_PAGES) == 70
    for idx, orig in enumerate(MD_PAGES):
        _, kind, lines = script_en.TEXT[idx]
        # MD page 59 always shows both rotate buttons (no arcade TURN DIRECTION DIP switch)
        if idx == 59:
            lines = [l for l in lines if l != 'IFTURN']
        assert at % 2 == 0
        words = text.page_words(kind, lines, at)
        data = struct.pack('>%dH' % len(words), *words)
        if at + len(data) > end:
            raise SystemExit('English text does not fit')
        prog[at:at + len(data)] = data
        prog[orig:orig + 6] = struct.pack('>HI', 0xfffe, at)
        at += len(data)
    return at


def _apply_titles(streams):
    # Keep all 8 slots of titles.TITLES: MD skips slot 6 (JOINING IN) and reads slot 7 (QUICK TURN) at 0xffcb28.
    tiles, tmap = streams.get(TUT_TILES), streams.get(TUT_MAP)
    letters = sorted(set(''.join(titles.TITLES)) - {' '})
    assert titles.FIRST_TILE + 2 * len(letters) <= titles.LAST_TILE + 1
    slot = {}
    for k, ch in enumerate(letters):
        g = title_font.glyph(ch)
        top, bot = titles.FIRST_TILE + 2 * k, titles.FIRST_TILE + 2 * k + 1
        gfx.tile_put(tiles, top, [[titles.COLOUR * v for v in r] for r in g[:8]])
        gfx.tile_put(tiles, bot, [[titles.COLOUR * v for v in r] for r in g[8:]])
        slot[ch] = (top, bot)
    blank = [[0] * 8 for _ in range(8)]
    for t in range(titles.FIRST_TILE + 2 * len(letters), titles.LAST_TILE + 1):
        gfx.tile_put(tiles, t, blank)
    for k, title in enumerate(titles.TITLES):
        s = title.center(titles.WIDTH)
        for row in range(2):
            for col, ch in enumerate(s):
                v = titles.BLANK if ch == ' ' else slot[ch][row]
                i = titles.MAP_AT + 2 * ((2 * k + row) * titles.WIDTH + col)
                tmap[i:i + 2] = v.to_bytes(2, 'big')


def _apply_logo(prog, streams, mode):
    if mode not in logo.MODES:
        raise ValueError('unknown logo mode: %r' % (mode,))
    if mode == 'original':
        return
    img = png.read(os.path.join(ROOT, 'assets', 'gfx', 'logo_puyo.png'))
    group_imgs = logo._split_groups(img)
    tiles = streams.get(LOGO_TILES)
    blank = [[0] * 8 for _ in range(8)]
    for t in range(logo.FIRST_RED):
        gfx.tile_put(tiles, t, blank)
    next_tile, starts = 0, []
    for g_img, grp in zip(group_imgs, logo.GROUP_LAYOUT):
        grp_starts = []
        for (_, _, w, h, sx, sy) in grp:
            grp_starts.append(next_tile)
            for c in range(w):
                for r in range(h):
                    x0, y0 = sx + 8 * c, sy + 8 * r
                    cell = [(row[x0:x0 + 8] + [0] * 8)[:8] for row in g_img[y0:y0 + 8]]
                    gfx.tile_put(tiles, next_tile, cell)
                    next_tile += 1
        starts.append(grp_starts)
    assert next_tile <= logo.FIRST_RED
    if mode == 'with-red-puyos':
        logo._repack_red_puyos(tiles, streams.original(LOGO_TILES))
    for table in LOGO_TABLES:
        for g, (at, n) in enumerate(logo.read_groups(prog, table)):
            if g < 2:
                spec = logo.GROUP_LAYOUT[g]
                assert len(spec) <= n
                e0 = at + 2
                low = prog[e0 + 3]
                attr0 = prog[e0 + 4] << 8 | prog[e0 + 5]
                prog[at:at + 2] = struct.pack('>H', len(spec))
                for k, (xr, yr, w, h, _, _) in enumerate(spec):
                    e = at + 2 + 8 * k
                    prog[e:e + 8] = struct.pack('>hBBHh', yr, (w - 1) << 2 | (h - 1), low,
                                                (attr0 & 0xf800) | (logo.FIRST + starts[g][k]), xr)
            elif g in logo.RED_X:
                if mode == 'no-red-puyos':
                    for k in range(n):
                        prog[at + 2 + 8 * k:at + 4 + 8 * k] = struct.pack('>h', logo.OFFSCREEN_Y)
                else:
                    assert n == 1
                    e = at + 2
                    attr = prog[e + 4] << 8 | prog[e + 5]
                    prog[e:e + 8] = struct.pack('>hBBHh', logo.RED_Y, (2 << 2) | 1, prog[e + 3], attr, logo.RED_X[g])


def _apply_shared_labels(prog, streams):
    # Tutorial ALL CLEAR
    img = [[0] * 96 for _ in range(8)] + labels.render(labels.ALL_CLEAR, 96, 16, 0xa, 0x1)
    for x in range(96):
        for y in range(23, -1, -1):
            if img[y][x] == 0xa:
                img[y][x] = 0x9
                break
    gfx.replace_block(streams.get(TUT_TILES), streams.get(ALLCLEAR_MAP), 0x270, 12, 3, img,
                      row_stride=14, blank=0x1c)

    # Play CHAIN (0x78..0x7a) + OFFSET (0x70..0x77)
    ctiles = streams.get(CHAIN_TILES)
    cimg = [[0] * 24 for _ in range(8)]
    for k, ch in enumerate("CHAIN"):
        for y, row in enumerate(labels.TINY[ch]):
            for x, c in enumerate(row):
                if c == '#':
                    xx, yy = 1 + 4 * k + x, 1 + y
                    cimg[yy][xx] = 6
                    for dy, dx in ((1, 0), (0, 1), (1, 1)):
                        if cimg[yy + dy][xx + dx] == 0:
                            cimg[yy + dy][xx + dx] = 2
    labels.put_tiles(ctiles, cimg, [[0x78, 0x79, 0x7a]])

    order = labels.sprite_order(0x70, 4, 2, 1)
    oimg = [[0] * 32 for _ in range(16)]
    for ty, row in enumerate(order):
        for tx, t in enumerate(row):
            for y, line in enumerate(gfx.tile_get(ctiles, t)):
                oimg[ty * 8 + y][tx * 8:tx * 8 + 8] = line
    for y in range(3, 15):
        oimg[y] = [0xf] * 32
    x = (32 - (5 * len(labels.OFFSET) - 1)) // 2
    for ch in labels.OFFSET:
        for y, line in enumerate(labels.SMALL[ch]):
            for dx, c in enumerate(line):
                if c == '#':
                    oimg[5 + y][x + dx] = 0x1
        x += 5
    labels.put_tiles(ctiles, oimg, order)

    # Play K.O. (big + small)
    ktiles = streams.get(KO_BIG_TILES)
    m = labels.scaled_mask(labels.KO, 21, 39, 3)
    kimg = [[0] * 96 for _ in range(56)]
    x0 = 16 + (72 - len(m[0])) // 2
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                kimg[6 + y][x0 + x] = 1
    kimg = labels.ring(labels.ring(kimg, 5, {1}), 6, {1, 5})
    for first, cols, rows, sx, sy in labels.KO_SPRITES:
        for c in range(cols):
            for r in range(rows):
                gfx.tile_put(ktiles, first + c * rows + r,
                             [row[sx + 8 * c:sx + 8 * c + 8] for row in kimg[sy + 8 * r:sy + 8 * r + 8]])
    stiles = streams.get(KO_SMALL_TILES)
    simg = [[1] * 24 for _ in range(48)]
    for k, line in enumerate(("K.", "O.")):
        sm = labels.scaled_mask(line, 14, 19, 2)
        for y, row in enumerate(sm):
            for x, v in enumerate(row):
                if v:
                    simg[4 + 22 * k + y][(24 - len(row)) // 2 + x] = 6
    labels.put_tiles(stiles, simg, [[3 * r + c for c in range(3)] for r in range(6)])

    # Play YAY!
    yimg = png.read(os.path.join(labels.ASSETS, 'yay.png'))
    ytiles = streams.get(YAY_TILES)
    sprites = [(-32, 0x0f08, 16 * k, -48 + 32 * k, 4, 4) for k in range(3)] + \
              [(0, 0x0c08, 48 + 4 * k, -48 + 32 * k, 4, 1) for k in range(3)]
    data = struct.pack('>H', len(sprites))
    for sy, size, first, sx, w, h in sprites:
        data += struct.pack('>hHHh', sy, size, 0x0680 + first, sx)
        for c in range(w):
            for r in range(h):
                cell = [row[sx + 48 + 8 * c:sx + 56 + 8 * c] for row in yimg[sy + 32 + 8 * r:sy + 40 + 8 * r]]
                gfx.tile_put(ytiles, first + h * c + r, cell)
    prog[YAY_LIST:YAY_LIST + len(data)] = data
    for t in range(60, 69):
        gfx.tile_put(ytiles, t, [[0] * 8 for _ in range(8)])

    # Tower, Nomi, Continue, and Act Against AIDS (exact same addresses as arcade)
    labels.apply_tower(streams)
    labels.apply_here(streams)
    labels.apply_gameover(streams)
    labels.apply_aids(streams)


def _apply_levels(prog, streams, at, end):
    pieces, lists = {}, []
    for lines in levels.LABELS:
        sprites = []
        y0 = -4 * len(lines)
        for row, word in enumerate(lines):
            x0 = -((levels.PITCH * len(word) - 1) // 2)
            for i in range(0, len(word), levels.PER_PIECE):
                k = pieces.setdefault(word[i:i + levels.PER_PIECE], len(pieces))
                sprites.append((y0 + 8 * row, 0x0408, levels.ATTR + 2 * k, x0 + levels.PITCH * i))
        lists.append(sprites)
    assert len(pieces) <= 10
    tiles = streams.get(LEVEL_TILES)
    for part, k in pieces.items():
        img = levels.piece_pixels(part)
        for half in (0, 1):
            gfx.tile_put(tiles, 2 * k + half, [row[8 * half:8 * half + 8] for row in img])
    for t in range(2 * len(pieces), 20):
        gfx.tile_put(tiles, t, [[0] * 8 for _ in range(8)])
    for level, sprites in enumerate(lists):
        assert at % 2 == 0
        data = struct.pack('>H', len(sprites)) + b''.join(struct.pack('>hHHh', *s) for s in sprites)
        if at + len(data) > end:
            raise SystemExit('levels: no room')
        prog[at:at + len(data)] = data
        prog[LEVEL_TABLE + 4 * level:LEVEL_TABLE + 4 * level + 4] = struct.pack('>I', at)
        at += len(data)
    return at


def update_md_checksum(prog):
    """Update the standard Sega Mega Drive 16-bit header checksum at 0x00018e."""
    total = sum(struct.unpack('>%dH' % ((len(prog) - 0x200) // 2), prog[0x200:])) & 0xffff
    prog[0x18e:0x190] = struct.pack('>H', total)


def build(prog, logo_mode=logo.DEFAULT_MODE):
    prog = bytearray(prog)
    # 1. Text engine (8x16 glyphs): relocate VDP write helper 0x1056 -> 0x111a
    eng = _relocate(_patch_file('text8.bin'), b'\x4e\xb8\x10\x56', b'\x4e\xb8\x11\x1a', 3)
    assert len(eng) <= TEXT_PUT_END - TEXT_PUT
    prog[TEXT_PUT:TEXT_PUT + len(eng)] = eng

    # 2. Spleen 8x16 font in bank 0x090000; zero 0x00..0x1f so gfx.free_space() never claims it
    prog[FONT_BANK_ENTRY:FONT_BANK_ENTRY + 2] = struct.pack('>H', FONT & 0xffff)
    prog[FONT:FONT + 0x200] = bytes(0x200)
    for code, rows in font.font().items():
        prog[FONT + code * 16:FONT + code * 16 + 16] = rows

    # 3. Script page opener hooks + 70 English pages in empty bank 0x110000
    hooks = _relocate(_patch_file('hooks.bin'), b'\x4e\xf9\x00\x01\x74\x00', b'\x4e\xf9\x00\x01\x50\xac', 2)
    prog[HOOKS:HOOKS + len(hooks)] = hooks
    _jmp(prog, OP03_PATCH[0], HOOKS, OP03_PATCH[1])
    _jmp(prog, OP0B_PATCH[0], HOOKS + 0x10, OP0B_PATCH[1])

    at = _apply_text(prog, DATA_AT, DATA_END)
    print('English text: %d bytes' % (at - DATA_AT))

    # 4. Shared arcade graphics + Mega Drive-exclusive screens
    streams = gfx.Streams(prog)
    _apply_titles(streams)
    _apply_logo(prog, streams, logo_mode)
    if logo_mode != 'original':
        logo.apply_wallpaper(streams.get(logo.WALLPAPER_TILES), 258, logo_mode)
    _apply_shared_labels(prog, streams)
    at = _apply_levels(prog, streams, at, DATA_END)
    at = md_screens.apply(prog, streams, at, DATA_END)
    print('MD extra data total: %d bytes (ends at 0x%06x)' % (at - DATA_AT, at))
    streams.write()
    update_md_checksum(prog)
    return prog
