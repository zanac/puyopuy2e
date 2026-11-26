"""Small English labels drawn over Japanese ones, with the capitals of font/title_font.py:
the letters filled with one colour and outlined with another, as the originals are."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'font'))
import title_font, gfx


def letter_mask(ch):
    """rows of 0/1, trimmed to the letter's columns"""
    if ch == ' ':
        return [[0, 0] for _ in range(13)]
    rows = [r for r in title_font.glyph(ch)[1:14]]
    cols = [x for x in range(8) if any(r[x] for r in rows)]
    return [r[cols[0]:cols[-1] + 1] for r in rows]


def render(text, width, height, fill, outline, gap=1, shine=None):
    """width x height pixel values: text centred, filled and outlined"""
    masks = [letter_mask(ch) for ch in text]
    w = sum(len(m[0]) for m in masks) + gap * (len(masks) - 1)
    if w + 2 > width:
        raise SystemExit('label %r: %d pixels, room for %d' % (text, w + 2, width))
    img = [[0] * width for _ in range(height)]
    x0, y0 = (width - w) // 2, (height - 13) // 2
    x = x0
    for m in masks:
        for y, row in enumerate(m):
            for dx, v in enumerate(row):
                if v:
                    img[y0 + y][x + dx] = fill
        x += len(m[0]) + gap
    out = [row[:] for row in img]
    for y in range(height):
        for x in range(width):
            if img[y][x] == fill:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < height and 0 <= xx < width and img[yy][xx] != fill:
                            out[yy][xx] = outline
    if shine is not None:                    # the top of each letter a lighter colour
        for x in range(width):
            for y in range(height):
                if img[y][x] == fill:
                    out[y][x] = shine
                    break
    return out


def put_tiles(tiles, img, order):
    """order[ty][tx] = the tile that gets the 8x8 block (tx, ty) of img"""
    for ty, row in enumerate(order):
        for tx, t in enumerate(row):
            gfx.tile_put(tiles, t, [r[tx * 8:tx * 8 + 8] for r in img[ty * 8:ty * 8 + 8]])


def sprite_order(first, width_tiles, height_tiles, sprites):
    """tile numbers of sprites side by side, each width_tiles x height_tiles, column-major"""
    order = [[0] * (width_tiles * sprites) for _ in range(height_tiles)]
    for s in range(sprites):
        for c in range(width_tiles):
            for r in range(height_tiles):
                order[r][s * width_tiles + c] = first + s * width_tiles * height_tiles + c * height_tiles + r
    return order


JOIN_IN = "JOIN IN!"


def apply(streams):
    # the 乱入可能 sign: in play (two 4x2 sprites, stream 0x900be tiles 0-15) and in the
    # tutorial (stream 0x91545, 8 x 2 tiles from 0x14d, row by row)
    img = render(JOIN_IN, 64, 16, 0xf, 0x1)
    put_tiles(streams.get(0x900be), img, sprite_order(0, 4, 2, 2))
    apply_crossed(streams, img)
    put_tiles(streams.get(0x91545), img, [list(range(0x14d, 0x155)), list(range(0x155, 0x15d))])
    apply_allclear(streams)
    apply_tower(streams)
    apply_gameover(streams)
    apply_here(streams)
    apply_entry(streams)
    apply_aids(streams)
    apply_chain(streams)
    apply_badge(streams)
    apply_rules(streams)
    apply_ask(streams)
    apply_knockout(streams)


def rows_order(first, width_tiles, height_tiles):
    """tile numbers of a block stored row by row"""
    return [list(range(first + r * width_tiles, first + (r + 1) * width_tiles)) for r in range(height_tiles)]


PICK = ("PICK", "YOUR RIVAL")


def apply_tower(streams):
    # 相手を / えらんでね on the tower screen (stream 0xc62d1): 6 x 2 tiles from 0x78, then
    # 10 x 2 tiles from 0x84, in red (8) outlined (7), the top of each letter lighter (d)
    tiles = streams.get(0xc62d1)
    put_tiles(tiles, render(PICK[0], 48, 16, 8, 7, shine=0xd), rows_order(0x78, 6, 2))
    put_tiles(tiles, render(PICK[1], 80, 16, 8, 7, shine=0xd), rows_order(0x84, 10, 2))


def blit_map(streams, tiles_addr, tile_base, pool, map_addr, map_rows, img, blank=0):
    """draws img through a tile map: map_rows = [(offset of the row in the map stream,
    number of cells)]; each 8x8 cell of img with pixels gets a tile of pool (stream tile
    numbers, VRAM tile = tile_base + n), empty cells the blank tile; the map words keep
    their high bits (palette, priority)"""
    tiles, tmap = streams.get(tiles_addr), streams.get(map_addr)
    pool = list(pool)
    for ty, (off, cells) in enumerate(map_rows):
        for tx in range(cells):
            block = [r[tx * 8:tx * 8 + 8] for r in img[ty * 8:ty * 8 + 8]]
            i = off + 2 * tx
            word = tmap[i] << 8 | tmap[i + 1]
            if any(any(r) for r in block):
                if not pool:
                    raise SystemExit('blit_map: out of tiles')
                t = pool.pop(0)
                gfx.tile_put(tiles, t, block)
                word = (word & 0xe000) | (tile_base + t)
            else:
                word = (word & 0xe000) | blank
            tmap[i:i + 2] = word.to_bytes(2, 'big')
    for t in pool:                              # the tiles left over: empty
        gfx.tile_put(tiles, t, [[0] * 8 for _ in range(8)])


CONTINUE = "CONTINUE?"


def apply_gameover(streams):
    # コンティニューするかい？ under the game over countdown: 24 x 2 cells, map in stream
    # 0xcc655 at 0x3fc and 0x42c, tiles 0x35f-0x38b of stream 0xcca17 (VRAM tile 0x100 on)
    img = render(CONTINUE, 192, 16, 0xf, 0x1)
    blit_map(streams, 0xcca17, 0x100, range(0x25f, 0x28c), 0xcc655, [(0x3fc, 24), (0x42c, 24)], img)


TINY = {        # 3x5 capitals for Nomi's tiny "I'm here" icon and CHAIN
    'Y': ["#.#", "#.#", ".#.", ".#.", ".#."],
    'O': ["###", "#.#", "#.#", "#.#", "###"],
    'U': ["#.#", "#.#", "#.#", "#.#", "###"],
    'A': [".#.", "#.#", "###", "#.#", "#.#"],
    'R': ["##.", "#.#", "##.", "#.#", "#.#"],
    'E': ["###", "#..", "##.", "#..", "###"],
    'H': ["#.#", "#.#", "###", "#.#", "#.#"],
    'C': ["###", "#..", "#..", "#..", "###"],
    'I': ["###", ".#.", ".#.", ".#.", "###"],
    'N': ["##.", "#.#", "#.#", "#.#", "#.#"],
    'M': ["#.#", "###", "###", "#.#", "#.#"],
    "'": [".#.", ".#.", "...", "...", "..."],
}


def apply_chain(streams):
    # れんさ next to the chain count in play: a 3x1 sprite, tiles 0x78-0x7a of stream
    # 0x83f2b (VRAM 0x378); colour 6 with a dark (2) shadow, like the kana
    img = [[0] * 24 for _ in range(8)]
    x0 = 1
    for k, ch in enumerate("CHAIN"):
        for y, row in enumerate(TINY[ch]):
            for x, c in enumerate(row):
                if c == '#':
                    xx, yy = x0 + 4 * k + x, 1 + y
                    img[yy][xx] = 6
                    for dy, dx in ((1, 0), (0, 1), (1, 1)):
                        if img[yy + dy][xx + dx] == 0:
                            img[yy + dy][xx + dx] = 2
    put_tiles(streams.get(0x83f2b), img, [[0x78, 0x79, 0x7a]])
    apply_offset(streams)


SMALL = {       # 4x9 capitals, 1-pixel strokes
    'E': ["####", "#...", "#...", "#...", "###.", "#...", "#...", "#...", "####"],
    'F': ["####", "#...", "#...", "#...", "###.", "#...", "#...", "#...", "#..."],
    'O': [".##.", "#..#", "#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    'S': [".###", "#...", "#...", "#...", ".##.", "...#", "...#", "...#", "###."],
    'T': ["####", ".#..", ".#..", ".#..", ".#..", ".#..", ".#..", ".#..", ".#.."],
}
OFFSET = "OFFSET"


def apply_offset(streams):
    # 相殺 in a four-player match: a 4x2 sprite, tiles 0x70-0x77 of stream 0x83f2b (column
    # by column), a white (f) box on rows 2-15 with the kanji in black (1); the box kept,
    # its inside redrawn with the word
    tiles = streams.get(0x83f2b)
    order = sprite_order(0x70, 4, 2, 1)
    img = [[0] * 32 for _ in range(16)]
    for ty, row in enumerate(order):
        for tx, t in enumerate(row):
            for y, line in enumerate(gfx.tile_get(tiles, t)):
                img[ty * 8 + y][tx * 8:tx * 8 + 8] = line
    for y in range(3, 15):
        img[y] = [0xf] * 32
    x = (32 - (5 * len(OFFSET) - 1)) // 2
    for ch in OFFSET:
        for y, line in enumerate(SMALL[ch]):
            for dx, c in enumerate(line):
                if c == '#':
                    img[5 + y][x + dx] = 0x1
        x += 5
    put_tiles(tiles, img, order)


def _draw_tiny(img, text, y0, colour, outline=None):
    """Draw compact 3x5 text centred horizontally on img at y0."""
    h, w = len(img), len(img[0])
    glyphs = []
    for ch in text:
        if ch == ' ':
            glyphs.append(None)
        elif ch == "'":
            glyphs.append([[1 if r[1] == '#' else 0] for r in TINY[ch]])
        else:
            glyphs.append([[1 if c == '#' else 0 for c in r] for r in TINY[ch]])
    tw = sum(2 if g is None else len(g[0]) for g in glyphs) + max(0, len(glyphs) - 1)
    x = (w - tw) // 2
    mask = [[0] * w for _ in range(h)]
    for g in glyphs:
        if g is None:
            x += 3
            continue
        for dy, row in enumerate(g):
            for dx, v in enumerate(row):
                if v and 0 <= y0 + dy < h and 0 <= x + dx < w:
                    mask[y0 + dy][x + dx] = 1
        x += len(g[0]) + 1
    if outline is not None:
        for y in range(h):
            for xx in range(w):
                if not mask[y][xx] and any(
                    0 <= y + dy < h and 0 <= xx + dx < w and mask[y + dy][xx + dx]
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                ):
                    img[y][xx] = outline
    for y in range(h):
        for xx in range(w):
            if mask[y][xx]:
                img[y][xx] = colour


def _render_with_apos(text, width, height, fill, outline, shine=None):
    """Like render(), adding a 2x4 apostrophe matching title_font's 13px height."""
    apos = [[1, 1], [1, 1], [1, 0], [1, 0]] + [[0, 0]] * 9
    masks = [apos if ch == "'" else letter_mask(ch) for ch in text]
    w = sum(len(m[0]) for m in masks) + len(masks) - 1
    img = [[0] * width for _ in range(height)]
    x, y0 = (width - w) // 2, (height - 13) // 2
    for m in masks:
        for y, row in enumerate(m):
            for dx, v in enumerate(row):
                if v:
                    img[y0 + y][x + dx] = fill
        x += len(m[0]) + 1
    out = [r[:] for r in img]
    for y in range(height):
        for xx in range(width):
            if img[y][xx] == fill:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, nx = y + dy, xx + dx
                        if 0 <= yy < height and 0 <= nx < width and img[yy][nx] != fill:
                            out[yy][nx] = outline
    if shine is not None:
        for xx in range(width):
            for y in range(height):
                if img[y][xx] == fill:
                    out[y][xx] = shine
                    break
    return out


def apply_here(streams):
    # Nomi the Flea ("ここにいる" = "I'M HERE" pointing at the 1px white flea dot):
    # 1. Tower 24x24 portrait (0x0c8503 tiles 0x1b..0x23): preserve frame (f), border (1),
    #    red arrow (8, top cap at y=17 x=11..12, shaft at y=18 x=10..12), and flea dot (f).
    htiles = streams.get(0xc8503)
    horder = sprite_order(0x1b, 3, 3, 1)
    himg = [[0] * 24 for _ in range(24)]
    for ty, row in enumerate(horder):
        for tx, t in enumerate(row):
            cell = gfx.tile_get(htiles, t)
            for y in range(8):
                himg[ty * 8 + y][tx * 8:tx * 8 + 8] = cell[y]
    for y in range(2, 19):
        for x in range(2, 22):
            if (y == 17 and x in (11, 12)) or (y == 18 and x in (10, 11, 12)):
                continue
            himg[y][x] = 3
    _draw_tiny(himg, "I'M", 3, 0xa, outline=1)
    _draw_tiny(himg, "HERE", 10, 0xa, outline=1)
    put_tiles(htiles, himg, horder)

    # 2. Blown-up profile/battle sprites (0x0ebd39): s06 "I'M / HERE!", s07 "YAY!", s08 "K.O."
    btiles = streams.get(0xebd39)
    def put_pair(img, t_left, t_right, rows):
        put_tiles(btiles, [r[:32] for r in img], sprite_order(t_left, 4, rows, 1))
        put_tiles(btiles, [r[32:48] for r in img], sprite_order(t_right, 2, rows, 1))

    im6 = _render_with_apos("I'M", 48, 16, 0xa, 1, shine=0xf) + render("HERE!", 48, 16, 0xa, 1, shine=0xf)
    for x in range(48):
        for y in (15, 31):
            for yy in range(y, y - 16, -1):
                if im6[yy][x] == 0xa:
                    im6[yy][x] = 8
                    break
    put_pair(im6, 0x04, 0x14, 4)
    put_pair(render("YAY!", 48, 24, 8, 1, shine=0xd), 0x1c, 0x28, 3)

    m8 = scaled_mask("K.O.", 10, 22, 2)
    im8 = [[0] * 48 for _ in range(32)]
    x0, y0 = (48 - len(m8[0])) // 2, (32 - len(m8)) // 2
    for y, row in enumerate(m8):
        for x, v in enumerate(row):
            if v:
                im8[y0 + y][x0 + x] = 6 if y < 14 else 5
    put_pair(ring(im8, 1, {5, 6}), 0x2e, 0x3e, 4)

    # 3. Center-panel Nomi animations & Tower box (0x0a5a1e, 0x0a5ce6, 0x0a602d)
    t_idle, t_win, m_box = streams.get(0xa5a1e), streams.get(0xa5ce6), streams.get(0xa602d)
    strip40 = [[0] * 40 for _ in range(8)]
    _draw_tiny(strip40, "I'M HERE", 2, 0xa)
    for ts in (t_idle, t_win):
        put_tiles(ts, strip40, [[0, 1, 2, 3, 4]])
    strip32 = [[0] * 32 for _ in range(8)]
    _draw_tiny(strip32, "I'M HERE", 2, 0xa)
    put_tiles(t_idle, strip32, [[0x22, 0x23, 0x24, 0x25]])
    r3 = 3 * 32 + 13
    assert m_box[r3:r3 + 5] == bytearray([0x22, 0x22, 0x23, 0x24, 0x25])
    m_box[r3:r3 + 5] = bytes([0x1f, 0x22, 0x23, 0x24, 0x25])
    # Bottom half of m_box (rows 8..15) reuses tile 0x0e (blank in JP "やったー!") as transparent
    # background fill; append a dedicated blank tile so "YAY!" does not fill Nomi's defeat panel.
    blank = len(t_win) // gfx.TILE
    t_win.extend(bytes(gfx.TILE))
    for i in range(256, len(m_box)):
        if m_box[i] == 0x0e:
            m_box[i] = blank
    put_tiles(t_win, render("YAY!", 48, 16, 8, 7), sprite_order(10, 6, 2, 1))
    put_tiles(t_win, render("YAY!", 48, 16, 6, 5), sprite_order(22, 6, 2, 1))


ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'gfx')


def apply_entry(streams):
    # 参加者募集中 over the entry screen: a 36 x 6 block at 0x2a4 of the map stream 0xff8d4,
    # tiles of stream 0xca599 (the map holds the stream's tile numbers)
    import png
    img = png.read(os.path.join(ASSETS, 'players_wanted.png'))
    gfx.replace_block(streams.get(0xca599), streams.get(0xff8d4), 0x2a4, 36, 6, img)
    # ひとり / ふたり / さんにん / よにん + でぷよぷよ ("<n> players' Puyo Puyo") above it:
    # 6-row blocks of the same map, put side by side on the screen
    # The game puts the two blocks side by side, the pair centred on screen. "nP" is drawn
    # flush right in its block and "PUYO PUYO" fills its own, so the line would sit right
    # of centre: everything is moved left (the start of "PUYO" into the number's block) by
    # what centres the 2P line; the 3P block is wider, its line stays a little right
    counts = ((0x454, 12, 'count_1p'), (0x4e4, 12, 'count_2p'), (0x574, 16, 'count_3p'),
              (0x634, 12, 'count_4p'))
    puyo = png.read(os.path.join(ASSETS, 'puyo_puyo.png'))
    imgs = {name: png.read(os.path.join(ASSETS, name + '.png')) for _, _, name in counts}
    used = lambda img: [x for x in range(len(img[0])) if any(row[x] for row in img)]
    left = used(imgs['count_2p'])[0]
    right = len(puyo[0]) - 1 - used(puyo)[-1]
    shift = (left - right) // 2
    blocks = []
    for off, w, name in counts:
        line = [a + b for a, b in zip(imgs[name], puyo)]
        line = [row[shift:] + [0] * shift for row in line]
        blocks.append((off, w, 6, [row[:8 * w] for row in line], None))
    blocks.append((0x6c4, 20, 6, [row[-160:] for row in line], None))
    gfx.replace_blocks(streams.get(0xca599), streams.get(0xff8d4), blocks)


SLOGAN = "COURAGE AND LOVE"


def apply_aids(streams):
    # 勇気と愛気 under the Act Against AIDS logo: 20 x 3 cells at 0x604 of the screen map
    # (stream 0x3eaff, 40 wide), tiles of stream 0x3ee26; grey (b) on white (f), in the
    # thin capitals of the text font
    import font
    glyphs = font.font()
    img = [[0xf] * 160 for _ in range(24)]
    x0 = (160 - 8 * len(SLOGAN)) // 2
    for k, ch in enumerate(SLOGAN):
        for y, row in enumerate(glyphs[ord(ch)]):
            for x in range(8):
                if row >> (7 - x) & 1:
                    img[4 + y][x0 + 8 * k + x] = 0xb
    gfx.replace_block(streams.get(0x3ee26), streams.get(0x3eaff), 0x604, 20, 3, img,
                      row_stride=40, background=0xf, blank=0x01)


ALL_CLEAR = "ALL CLEAR"


def apply_allclear(streams):
    # 全消し in the tutorial's ALL CLEAR page: the box inside is 12 x 3 cells at 0x270 of
    # the map stream 0x45503 (rows 14 words apart), tiles of the tutorial stream 0x91545;
    # yellow (a) outlined (1), the bottom of each letter darker (9)
    img = [[0] * 96 for _ in range(8)] + render(ALL_CLEAR, 96, 16, 0xa, 0x1)
    for x in range(96):          # (the text on cell rows 1 and 2 only: there are 20 tiles)
        for y in range(23, -1, -1):
            if img[y][x] == 0xa:
                img[y][x] = 0x9
                break
    gfx.replace_block(streams.get(0x91545), streams.get(0x45503), 0x270, 12, 3, img,
                      row_stride=14, blank=0x1c)


def apply_crossed(streams, plain):
    # the crossed-out 乱入可能 of the tutorial's JOINING IN page: its middle 6 x 2 tiles
    # (0x19a-0x19f, 0x1a0-0x1a5 of stream 0x91545) are the sign's middle with a red X;
    # the X (the pixels where they differ from the plain sign's tiles 0x14e-0x153,
    # 0x156-0x15b) goes over the English sign
    tiles = streams.get(0x91545)
    crossed = [list(range(0x19a, 0x1a0)), list(range(0x1a0, 0x1a6))]
    orig_plain = [list(range(0x14e, 0x154)), list(range(0x156, 0x15c))]
    for r in range(2):
        for c in range(6):
            xp = gfx.tile_get(streams.original(0x91545), crossed[r][c])
            pp = gfx.tile_get(streams.original(0x91545), orig_plain[r][c])
            new = [row[8 + 8 * c:16 + 8 * c] for row in plain[8 * r:8 * r + 8]]
            out = [[xp[y][x] if xp[y][x] != pp[y][x] else new[y][x] for x in range(8)] for y in range(8)]
            gfx.tile_put(tiles, crossed[r][c], out)


SERVICE = (   # the service menu's (and the ending record's) Japanese words in romaji, same lengths
    (b"^3SOUSAI", b"^3OFFSET"),
    (b"^3RULE HENKA", b"^3RULE SET  "),
    (b"RANNYU OFF BUTTON", b"NO JOIN-IN BUTTON"),
    (b"^3RANNYU\xfe", b"^3JOINS \xfe"),
    (b"^2MAX RENSA", b"^2MAX CHAIN"),
)


def apply_service(prog):
    for old, new in SERVICE:
        assert len(old) == len(new)
        i = prog.find(old)
        if i < 0 or prog.find(old, i + 1) >= 0:
            raise SystemExit('service text %r: not found once' % old)
        prog[i:i + len(new)] = new


SIGN = ("PUSH {}P", "START!")
SIGN_LISTS = {1: 0x2e8fc, 2: 0x2e91e}     # the sprite list of each variant


KO = "K.O."


def scaled_mask(text, width, height, gap):
    """text in the title font, each letter stretched to width x height pixels
    (a '.' a square at the foot), letters gap apart: rows of 0/1"""
    masks = []
    for ch in text:
        if ch == '.':
            m = [[0, 0] for _ in range(11)] + [[1, 1], [1, 1]]
            w = max(2, width * 2 // 7)
        else:
            m = letter_mask(ch)
            w = width
        sw = len(m[0])
        masks.append([[m[y * 13 // height][x * sw // w] for x in range(w)] for y in range(height)])
    out = [[] for _ in range(height)]
    for k, m in enumerate(masks):
        for y in range(height):
            out[y] += ([0] * gap if k else []) + m[y]
    return out


def ring(img, colour, inside):
    """img with the pixels next to any of inside (and not in it) set to colour"""
    h, w = len(img), len(img[0])
    out = [row[:] for row in img]
    for y in range(h):
        for x in range(w):
            if img[y][x] not in inside and any(0 <= y + dy < h and 0 <= x + dx < w and img[y + dy][x + dx] in inside
                                               for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                out[y][x] = colour
    return out


KO_SPRITES = [(0x00, 4, 4, 0, 0), (0x10, 4, 4, 32, 0), (0x20, 3, 4, 64, 0), (0x2c, 1, 2, 16, 32),
              (0x2e, 2, 3, 24, 32), (0x34, 4, 3, 40, 32), (0x40, 3, 2, 72, 32)]


def apply_knockout(streams):
    # ばたんきゅ～, over the field of a player knocked out while the others play on (three or
    # four players, and the attract demo): stream 0x869e7, 70 tiles, seven sprites (list at
    # 0x1e57c) covering 96 x 56 pixels as KO_SPRITES (first tile, columns, rows, x, y), in
    # light blue (1) edged 5, outlined 6. Now K.O.
    tiles = streams.get(0x869e7)
    m = scaled_mask(KO, 21, 39, 3)
    w = len(m[0])
    img = [[0] * 96 for _ in range(56)]
    x0, y0 = 16 + (72 - w) // 2, 6
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                img[y0 + y][x0 + x] = 1
    img = ring(ring(img, 5, {1}), 6, {1, 5})
    for first, cols, rows, x, y in KO_SPRITES:
        for c in range(cols):
            for r in range(rows):
                gfx.tile_put(tiles, first + c * rows + r,
                             [row[x + 8 * c:x + 8 * c + 8] for row in img[y + 8 * r:y + 8 * r + 8]])
    covered = {(x + 8 * c + i, y + 8 * r + j) for first, cols, rows, x, y in KO_SPRITES
               for c in range(cols) for r in range(rows) for i in range(8) for j in range(8)}
    if any(img[y][x] and (x, y) not in covered for y in range(56) for x in range(96)):
        raise SystemExit('K.O.: outside the sprites')
    # the same in the small field of a knocked-out player on the score panel: stream
    # 0x85dc1, 3 x 6 tiles row by row, yellow (6) on the field's blue (1)
    tiles = streams.get(0x85dc1)
    img = [[1] * 24 for _ in range(48)]
    for k, line in enumerate(("K.", "O.")):
        m = scaled_mask(line, 14, 19, 2)
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    img[4 + 22 * k + y][(24 - len(row)) // 2 + x] = 6
    put_tiles(tiles, img, [[3 * r + c for c in range(3)] for r in range(6)])


ASK = ("JOIN IN?", "YES", "NO")
ARROW = ["......#......",
         ".....##......",
         "....###......",
         "...##########",
         "..###########",
         "...##########",
         "....###......",
         ".....##......",
         "......#......"]


def apply_ask(streams):
    # The JOINING IN tutorial page (shown only on a linked cabinet) draws a small join
    # prompt, 乱入するの？ / はい / いいえ and コレ pointing at はい: four blocks of the map stream
    # 0x456fa (loaded to RAM 0xffb000, put on screen by 0x209c6): 12 x 2 cells at 0x1a4,
    # 4 x 2 at 0x1d4, 6 x 2 at 0x1e4, 3 x 2 at 0x1fc, tiles of the tutorial stream 0x91545.
    # 乱入 borrowed the 乱入可能 sign's tiles (0x14d-), now JOIN IN!, so it read "JOI"; the
    # blocks are redrawn with tiles 0x175-0x196 (the rest of the prompt's own, used by
    # nothing else while the tutorial is on), the text in white (f) outlined (1) and the
    # word "this" an arrow
    tiles, tmap = streams.get(0x91545), streams.get(0x456fa)
    def left(img):
        cols = [x for x in range(len(img[0])) if any(r[x] for r in img)]
        s = cols[0] - 1
        return [r[s:] + [0] * s for r in img]
    arrow = [[0] * 24 for _ in range(16)]
    for y, line in enumerate(ARROW):
        for x, ch in enumerate(line):
            if ch == '#':
                arrow[3 + y][1 + x] = 0xf
    for y in range(16):
        for x in range(24):
            if arrow[y][x] == 0 and any(0 <= y + dy < 16 and 0 <= x + dx < 24 and arrow[y + dy][x + dx] == 0xf
                                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                arrow[y][x] = 0x1
    blocks = [(0x1a4, 12, left(render(ASK[0], 96, 16, 0xf, 0x1))),
              (0x1d4, 4, left(render(ASK[1], 32, 16, 0xf, 0x1))),
              (0x1e4, 6, left(render(ASK[2], 48, 16, 0xf, 0x1))),
              (0x1fc, 3, arrow)]
    pool = list(range(0x175, 0x197))
    n = len(tiles) // gfx.TILE
    blank = next(t for t in range(n) if not any(tiles[t * gfx.TILE:(t + 1) * gfx.TILE]))
    made = {}
    for off, w, img in blocks:
        for r in range(2):
            for c in range(w):
                cell = [row[8 * c:8 * c + 8] for row in img[8 * r:8 * r + 8]]
                key = tuple(map(tuple, cell))
                if not any(any(row) for row in cell):
                    t = blank
                elif key in made:
                    t = made[key]
                else:
                    if not pool:
                        raise SystemExit('join prompt: not enough tiles')
                    t = made[key] = pool.pop(0)
                    gfx.tile_put(tiles, t, cell)
                i = off + 2 * (r * w + c)
                word = (tmap[i] << 8 | tmap[i + 1]) & 0xe000
                tmap[i:i + 2] = (word | t).to_bytes(2, 'big')


def apply_sign(prog, streams):
    # 1Pの / 2Pの + スタートボタンを / 押してね over the rabbit still waiting on the entry
    # screen: sprites of stream 0xca599 (loaded at tile 0x100), the lists at 0x2e8fc (1P)
    # and 0x2e91e (2P), each a count word then y, size, attribute, x: three sprites shared
    # (4x4 tiles 0x1a, 4x4 0x2a, 1x4 0x3a at x 4, 0x24, 0x44: 72 x 32 pixels) and the
    # number, 3x2 tiles 0x3e (1P) or 0x44 (2P), put over them. Two lines in white (f)
    # outlined (1); the number sprite moved to where the number of the first line is
    tiles = streams.get(0xca599)
    line1, line2 = SIGN
    head = line1[:line1.index('{')]
    masks = [letter_mask(ch) for ch in line1.format(1)]
    width = sum(len(m[0]) for m in masks) + len(masks) - 1
    x_num = (72 - width) // 2 + sum(len(m[0]) + 1 for m in masks[:len(head)])
    d_x = x_num - 1 - 4                      # the number sprite, from the 72-pixel area
    for n, lst in SIGN_LISTS.items():
        img = render(line1.format(n), 72, 16, 0xf, 0x1) + render(line2, 72, 16, 0xf, 0x1)
        if n == 1:          # the shared sprites: the number's place left empty
            shared = [row[:] for row in img]
            for y in range(16):
                for x in range(d_x, d_x + 24):
                    shared[y][x] = 0
            pad = lambda rows, w: [r + [0] * (w - len(r)) for r in rows]
            put_tiles(tiles, shared, sprite_order(0x1a, 4, 4, 2))
            put_tiles(tiles, pad([r[64:72] for r in shared], 8), sprite_order(0x3a, 1, 4, 1))
        num = [row[d_x:d_x + 24] for row in img[:16]]
        if any(img[y][x] != shared[y][x] for y in range(32) for x in range(72)
               if not (y < 16 and d_x <= x < d_x + 24)):
            raise SystemExit('sign: the number is not inside its sprite')
        put_tiles(tiles, num, sprite_order(0x3e if n == 1 else 0x44, 3, 2, 1))
        count = prog[lst] << 8 | prog[lst + 1]
        for k in range(count):
            e = lst + 2 + 8 * k
            attr = prog[e + 4] << 8 | prog[e + 5]
            if attr & 0x7ff in (0x13e, 0x144):
                prog[e + 6:e + 8] = (4 + d_x).to_bytes(2, 'big')


BADGE = "JOIN!"


def apply_badge(streams):
    # 参加 on the red badge the left rabbit holds on the entry screen: its map is 10 x 8
    # cells at 0x1f4 of the map stream 0xff8d4 (rows 10 words apart), tiles of stream
    # 0xca599. The kanji (white f, shaded a/b/4/5 on the red 3) are painted over with red,
    # then the English drawn in white outlined with 5
    tiles, tmap = streams.get(0xca599), streams.get(0xff8d4)
    img = gfx.block_pixels(tiles, tmap, 0x1f4, 10, 8, 10)
    for y in range(13, 50):
        row = img[y]
        inside = [x for x in range(9, 71) if row[x] == 3]      # (inside the rim)
        if not inside:
            continue
        for x in range(inside[0], inside[-1] + 1):
            if row[x] in (0xf, 0xa, 0xb, 0x4, 0x5):
                row[x] = 3
    text = render(BADGE, 56, 16, 0xf, 0x5)
    for y in range(16):
        for x in range(56):
            if text[y][x]:
                img[23 + y][12 + x] = text[y][x]
    gfx.write_block_pixels(tiles, tmap, 0x1f4, 10, 8, 10, img)


# the rule select screen (map stream 0xfbd02, tiles of stream 0xfbf8f; the map holds the
# stream's tile numbers): its title, 33 x 3 cells at 0x8c0, and the box's line for each
# rule, 28 x 2 cells at 0x986 (ojama puyo score) and 24 x 2 cells at 0xa0e (rows 28 words
# apart; the plain rule), both centred on screen, in white (f) with the words that matter
# in yellow (c); [] mark the yellow part
RULE_LINES = ((0x986, 28, "Nuisance Puyo [score points]!"), (0xa0e, 24, "Plain [Puyo Puyo] battle!"))


def rule_line(text, cells):
    import font
    glyphs = font.font()
    plain = text.replace('[', '').replace(']', '')
    img = [[0] * (8 * cells) for _ in range(16)]
    x = (8 * cells - 8 * len(plain)) // 2
    colour = 0xf
    for ch in text:
        if ch in '[]':
            colour = 0xc if ch == '[' else 0xf
            continue
        for y, row in enumerate(glyphs[ord(ch)]):
            for i in range(8):
                if row >> (7 - i) & 1:
                    img[y][x + i] = colour
        x += 8
    return img


def apply_rules(streams):
    import png
    title = png.read(os.path.join(ASSETS, 'choose_rule.png'))
    blocks = [(0x8c0, 33, 3, title, None)]
    blocks += [(off, cells, 2, rule_line(text, cells), 28) for off, cells, text in RULE_LINES]
    gfx.replace_blocks(streams.get(0xfbf8f), streams.get(0xfbd02), blocks)


# やった on the winner's side after a match: sprites of stream 0x86f09 (VRAM tile 0x680),
# its list of 7 sprites at 0x1e542 (count, then y, size and link, attribute, x) becomes 6:
# three 4x4 over three 4x1, a 96 x 40 picture from the centre 48 left and 32 up
YAY_LIST = 0x1e542


def apply_yay(prog, streams):
    import png, struct
    img = png.read(os.path.join(ASSETS, 'yay.png'))
    tiles = streams.get(0x86f09)
    sprites = []
    for k in range(3):
        sprites.append((-32, 0x0f08, 16 * k, -48 + 32 * k, 4, 4))
    for k in range(3):
        sprites.append((0, 0x0c08, 48 + 4 * k, -48 + 32 * k, 4, 1))
    data = struct.pack('>H', len(sprites))
    for y, size, first, x, w, h in sprites:
        data += struct.pack('>hHHh', y, size, 0x0680 + first, x)
        for c in range(w):
            for r in range(h):
                cell = [row[x + 48 + 8 * c:x + 56 + 8 * c] for row in img[y + 32 + 8 * r:y + 40 + 8 * r]]
                gfx.tile_put(tiles, first + h * c + r, cell)
    assert len(data) <= 2 + 7 * 8
    prog[YAY_LIST:YAY_LIST + len(data)] = data
    for t in range(60, 69):
        gfx.tile_put(tiles, t, [[0] * 8 for _ in range(8)])
