"""The title logo: keeps the gold 2 and green 通 (+ green puyo), with three logo modes:
  - original:      keep the Japanese ぷよぷよ通 logo untouched
  - no-red-puyos:  "Puyo Puyo 通" with the red handakuten puyos culled offscreen (default)
  - with-red-puyos:"Puyo Puyo 通" with cropped 3x2 red puyos resting over the 'u' letters

The logo's letters are sprites in 9 groups described by two tables (TABLES; one with the
priority bit, one without, for the title's two phases): a group is a count, then per
sprite (signed y, size, low, tile attributes, signed x). The groups are: ぷ, よ (drawn
twice for both ぷよ), the 3 red handakuten puyo frames, 通 (8 sprites), and the 3 green
puyo frames. Their tiles are stream TILES (VRAM tile 0x4e0 on); G0+G1 occupy 0x00..0x44
(69 tiles), G2..G4 occupy 0x45..0x5f, and G5..G8 occupy 0x60..0xd8.

In the English modes, G0+G1 use 66 of the 69 tiles and peak at 296/320 sprite pixels per
scanline (11/20 sprites, SOVR=0 on Sega 315-5313 VDP hardware)."""
import collections, os, struct
import gfx, png

MODES = ('original', 'no-red-puyos', 'with-red-puyos')
DEFAULT_MODE = 'no-red-puyos'

TABLES = (0x2a802, 0x2aa3e)
TILES = 0xb7511
FIRST = 0x4e0
GROUPS = 9                      # ぷ, よ, 3 red puyo frames, 通, 3 green puyo frames
FIRST_RED = 0x45                # 69 tiles (0x00..0x44) belong to G0 + G1
RED_BASES = (0x45, 0x4e, 0x57)  # 3x3 original red puyo frames in stream TILES
RED_X = {2: 2, 3: 2, 4: 0}      # x offsets aligning each red puyo frame over 'u'
RED_Y = -5                      # y offset placing the cropped 3x2 red puyo flush above 'u'
OFFSCREEN_Y = -0x200            # culled by the sprite parser (0x0a840) before VDP SAT

# 96x64 canvas (assets/gfx/logo_puyo.png): (xr, yr, w, h, sx, sy) per sprite.
# G0 (Pu, x=0..52): P top (4x3), P bottom (4x4), u (3x4);
# G1 (yo, x=50..93): y (3x4), o (3x4), y descender tail (2x1).
GROUP_LAYOUT = (
    ((2, -13, 4, 3, 0, 0), (2, 11, 4, 4, 0, 24), (34, 11, 3, 4, 32, 24)),
    ((-4, 11, 3, 4, 50, 24), (20, 11, 3, 4, 74, 24), (-4, 43, 2, 1, 50, 56)),
)
HERE = os.path.dirname(os.path.abspath(__file__))


def _split_groups(img):
    """Split logo_puyo.png by connected component into G0 ('Pu', left < 45) and G1 ('yo')
    so the right edge of 'u' (x=50..52) stays with 'Pu' instead of dropping with 'yo'."""
    h, w = len(img), len(img[0])
    vis = [[False] * w for _ in range(h)]
    out = [[[0] * w for _ in range(h)] for _ in range(2)]
    for y in range(h):
        for x in range(w):
            if not img[y][x] or vis[y][x]:
                continue
            q, pts = collections.deque([(x, y)]), []
            vis[y][x] = True
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny][nx] and not vis[ny][nx]:
                        vis[ny][nx] = True
                        q.append((nx, ny))
            dst = out[0 if min(px for px, _ in pts) < 45 else 1]
            for cx, cy in pts:
                dst[cy][cx] = img[cy][cx]
    return out


def read_groups(prog, at):
    """Read the 9 unmodified group offsets before lowering G0/G1 counts in place
    (pointer tables 0x2a656/0x2a6ea address each group directly)."""
    groups = []
    for _ in range(GROUPS):
        n = prog[at] << 8 | prog[at + 1]
        groups.append((at, n))
        at += 2 + 8 * n
    return groups


def _repack_red_puyos(tiles, orig_tiles):
    """Crop the 3 original 24x24 red puyo frames to rows 3..18 (24x16, 3x2 tiles)
    so they sit directly above 'u' without overlapping it."""
    blank = [[0] * 8 for _ in range(8)]
    for base in RED_BASES:
        full = [[0] * 24 for _ in range(24)]
        for c in range(3):
            for r in range(3):
                cell = gfx.tile_get(orig_tiles, base + c * 3 + r)
                for y in range(8):
                    full[r * 8 + y][c * 8:c * 8 + 8] = cell[y]
        cropped = full[3:19]
        for t in range(base, base + 9):
            gfx.tile_put(tiles, t, blank)
        for c in range(3):
            for r in range(2):
                cell = [cropped[r * 8 + y][c * 8:c * 8 + 8] for y in range(8)]
                gfx.tile_put(tiles, base + c * 2 + r, cell)


def apply(prog, streams, mode=DEFAULT_MODE):
    if mode not in MODES:
        raise ValueError('unknown logo mode: %r' % (mode,))
    if mode == 'original':
        return

    img = png.read(os.path.join(HERE, '..', 'assets', 'gfx', 'logo_puyo.png'))
    assert len(img) == 64 and len(img[0]) == 96
    group_imgs = _split_groups(img)
    for g_img, grp in zip(group_imgs, GROUP_LAYOUT):
        covered = {(x, y) for (_, _, w, h, sx, sy) in grp
                   for y in range(sy, sy + h * 8) for x in range(sx, sx + w * 8)}
        assert not any(v and (x, y) not in covered for y, row in enumerate(g_img) for x, v in enumerate(row))

    tiles = streams.get(TILES)
    blank = [[0] * 8 for _ in range(8)]
    for t in range(FIRST_RED):
        gfx.tile_put(tiles, t, blank)

    # pack G0 and G1 tiles column by column; G5..G8 (通 + green puyo) stay untouched
    next_tile = 0
    starts = []
    for g_img, grp in zip(group_imgs, GROUP_LAYOUT):
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
    assert next_tile <= FIRST_RED

    if mode == 'with-red-puyos':
        _repack_red_puyos(tiles, streams.original(TILES))

    for table in TABLES:
        groups = read_groups(prog, table)
        for g, (at, n) in enumerate(groups):
            if g < 2:
                spec = GROUP_LAYOUT[g]
                assert len(spec) <= n
                e0 = at + 2
                low = prog[e0 + 3]
                attr0 = prog[e0 + 4] << 8 | prog[e0 + 5]
                prog[at:at + 2] = struct.pack('>H', len(spec))
                for k, (xr, yr, w, h, _, _) in enumerate(spec):
                    e = at + 2 + 8 * k
                    size = (w - 1) << 2 | (h - 1)
                    prog[e:e + 8] = struct.pack('>hBBHh', yr, size, low,
                                                (attr0 & 0xf800) | (FIRST + starts[g][k]), xr)
            elif g in RED_X:
                if mode == 'no-red-puyos':
                    for k in range(n):
                        e = at + 2 + 8 * k
                        prog[e:e + 2] = struct.pack('>h', OFFSCREEN_Y)
                else:
                    assert n == 1
                    e = at + 2
                    low = prog[e + 3]
                    attr = prog[e + 4] << 8 | prog[e + 5]
                    prog[e:e + 8] = struct.pack('>hBBHh', RED_Y, (2 << 2) | 1, low, attr, RED_X[g])


# Shared scrolling 'ぷよぷよ通' -> 'Puyo Puyo 2 通' Tower background wallpaper (Arcade & Mega Drive).
# Stream 0x0c497d holds the 81 wallpaper tiles (2..82) contiguously at tiles 260..340 (base=258).
WALLPAPER_TILES = 0x0c497d
_PUYO_LUMA = {2: 30, 3: 40, 4: 49, 5: 59, 6: 69, 8: 77, 10: 119, 11: 142, 12: 169, 13: 208, 15: 231}
_WP_PUYO_CACHE = None


def _wallpaper_puyo_sprite():
    """Downscale assets/gfx/logo_puyo.png into a 55x24 glossy blue 'Puyo' sprite (indices 8..13)."""
    global _WP_PUYO_CACHE
    if _WP_PUYO_CACHE is not None:
        return _WP_PUYO_CACHE
    src = png.read(os.path.join(HERE, '..', 'assets', 'gfx', 'logo_puyo.png'))
    crop = [row[0:94] for row in src[8:61]]
    src_w, src_h, tw, th = 94, 53, 53, 22
    mask = [[0] * tw for _ in range(th)]
    bright = [[0.0] * tw for _ in range(th)]
    for y in range(th):
        sy0, sy1 = y * src_h / th, (y + 1) * src_h / th
        for x in range(tw):
            sx0, sx1 = x * src_w / tw, (x + 1) * src_w / tw
            tot = cov = lsum = 0.0
            for sy in range(int(sy0), min(src_h, int(sy1) + 1)):
                wy = min(sy + 1, sy1) - max(sy, sy0)
                if wy <= 0:
                    continue
                for sx in range(int(sx0), min(src_w, int(sx1) + 1)):
                    wx = min(sx + 1, sx1) - max(sx, sx0)
                    if wx <= 0:
                        continue
                    w = wx * wy
                    tot += w
                    v = crop[sy][sx]
                    if v:
                        cov += w
                        lsum += w * _PUYO_LUMA[v]
            if cov / tot >= 0.36:
                mask[y][x] = 1
                bright[y][x] = lsum / cov
    out = [[0] * (tw + 2) for _ in range(th + 2)]
    for y in range(th):
        for x in range(tw):
            if not mask[y][x]:
                continue
            b = bright[y][x]
            top_e = y == 0 or not mask[y - 1][x]
            left_e = x == 0 or not mask[y][x - 1]
            bot_e = y == th - 1 or not mask[y + 1][x]
            right_e = x == tw - 1 or not mask[y][x + 1]
            if b >= 115 or (top_e and left_e and b >= 60):
                c = 13
            elif b >= 68:
                c = 13 if (top_e or left_e) else 12
            elif b >= 52:
                c = 10 if (bot_e or right_e) else (12 if (top_e or left_e) else 11)
            elif b >= 38:
                c = 9 if (bot_e or right_e) else 10
            else:
                c = 9
            out[y + 1][x + 1] = c
    final = [r[:] for r in out]
    for y in range(th + 2):
        for x in range(tw + 2):
            if not out[y][x] and any(
                0 <= x + dx < tw + 2 and 0 <= y + dy < th + 2 and out[y + dy][x + dx]
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                final[y][x] = 8
    _WP_PUYO_CACHE = final
    return final


def apply_wallpaper(tiles, base=0, mode=DEFAULT_MODE):
    """Replace the 'ぷよぷよ' tiles (base+24..37, 43..56, 62..74) with glossy blue 'Puyo Puyo',
    preserving the '2' medallion, '通' kanji, and shared tile 66 (col 5 & col 12 on row 5) in place."""
    if mode not in MODES:
        raise ValueError('unknown logo mode: %r' % (mode,))
    if mode == 'original':
        return
    # Reconstruct rows 1..2 (y=8..23, x=48..103) from the tile buffer to mirror the exact medallion rim
    top = [[14] * 168 for _ in range(24)]
    for tr, row_tids in ((1, (7, 8, 9, 10, 11, 12, -7)), (2, (13, 14, 15, 16, 17, 18, -13))):
        for idx, tid in enumerate(row_tids):
            hf = tid < 0
            blk = gfx.tile_get(tiles, base + abs(tid))
            for y in range(8):
                for x in range(8):
                    top[tr * 8 + y][(6 + idx) * 8 + x] = blk[y][7 - x if hf else x]

    # Build clean 120x24 band (x=0..119, y=24..47): cyan backdrop + mirrored '2' medallion + '2' stem/bar
    band = [[14] * 120 for _ in range(24)]
    cx, cy = 75.5, 27.5
    for dy in range(24):
        y = 24 + dy
        ref_y = 23 if y <= 31 else (55 - y)
        for x in range(48, 104):
            r = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if r >= 22.0:
                if r <= 28.5:
                    band[dy][x] = top[ref_y][x]
            else:
                band[dy][x] = (14, 13, 12, 11, 10, 9)[min(5, max(0, (y - 23) // 4))]
        if 24 <= y <= 38:
            mx = 85.0 - 17.5 * (y - 24) / 14.0
            for x in range(56, 95):
                d = abs(x - mx)
                if d <= 5.2:
                    band[dy][x] = 9 if d <= 3.8 else 8
        if 37 <= y <= 44:
            for x in range(60, 92):
                band[dy][x] = 8 if (y in (37, 44) or x in (60, 91)) else (11 if y <= 39 else 9)

    puyo = _wallpaper_puyo_sprite()
    for x0 in (8, 64):
        for y, row in enumerate(puyo):
            for x, v in enumerate(row):
                if v:
                    band[y][x0 + x] = v

    # Write tiles 24..37 (row 3), 43..56 (row 4), and 62..74 (row 5; col 5 & col 12 share tile 66)
    row_specs = (
        (0, [(c, 23 + c) for c in range(1, 15)]),
        (1, [(c, 42 + c) for c in range(1, 15)]),
        (2, [(c, 61 + c) for c in range(1, 12)] + [(13, 73), (14, 74)]),
    )
    for ty, pairs in row_specs:
        for tc, tid in pairs:
            cell = [band[ty * 8 + y][tc * 8:tc * 8 + 8] for y in range(8)]
            gfx.tile_put(tiles, base + tid, cell)
