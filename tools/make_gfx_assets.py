#!/usr/bin/env python3
"""Draws the English graphics of assets/gfx (maintainers only: needs Pillow and the
Poppins Bold font, OFL; the PNGs are in the repository, building the ROM does not run
this). Each PNG is 8-bit palette: the indices are the game's colour numbers."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bigtext, png

OUT = os.path.join(HERE, '..', 'assets', 'gfx')
GREY = [(i * 17, i * 17, i * 17) for i in range(16)]

# name: (text, width, height, font size, tracking, vertical offset, fill, edge, outline)
# (sizes and offsets chosen so the text takes few enough 8x8 cells for the tiles there are)
BIG = {
    'players_wanted': ("PLAYERS WANTED!", 288, 48, 28, -1, 4, 9, None, 1),
}


# the title logo's palette (palette 0 of the title screen): colour number -> RGB
LOGO_PALETTE = {2: (99, 0, 0), 3: (132, 0, 0), 4: (165, 0, 0), 5: (198, 0, 0), 6: (231, 0, 0),
                8: (231, 0, 66), 9: (231, 33, 99), 10: (231, 66, 99), 11: (231, 99, 132),
                12: (231, 132, 198), 13: (231, 198, 198), 15: (231, 231, 231)}


def logo():
    """"Puyo" from assets/puyopuyo_logo.jpg (its first word), 96 x 64 (94 x 53 placed at
    y=8 so the sprite split at y=24 and the 'y' tail at y=56 land on tile rows), in the
    logo's colours; the near-white background transparent"""
    import collections
    from PIL import Image
    src = Image.open(os.path.join(HERE, '..', 'assets', 'puyopuyo_logo.jpg')).convert('RGB')
    word = src.crop((0, 0, 286, src.height))
    w, h = word.size
    px = word.load()
    dirs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    is_bg = lambda rgb: rgb[1] > 195 and rgb[2] > 195

    # flood-fill exterior and P/o holes (leaving small interior highlights alone);
    # repaint bg dark maroon so downscaling blends edges to dark red, not white
    fg, alpha = word.copy(), Image.new('L', (w, h), 255)
    fpx, apx = fg.load(), alpha.load()
    vis = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if vis[y][x] or not is_bg(px[x, y]):
                continue
            comp, q, border = [], collections.deque([(x, y)]), False
            vis[y][x] = True
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                if cx in (0, w - 1) or cy in (0, h - 1):
                    border = True
                for dx, dy in dirs:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not vis[ny][nx] and is_bg(px[nx, ny]):
                        vis[ny][nx] = True
                        q.append((nx, ny))
            if border or len(comp) >= 150:
                for cx, cy in comp:
                    apx[cx, cy] = 0
                    fpx[cx, cy] = LOGO_PALETTE[2]

    bbox = word.point(lambda v: 255 if v < 200 else 0).convert('L').getbbox()
    rgb_s = fg.crop(bbox).resize((94, 53), Image.BOX)
    alp_s = alpha.crop(bbox).resize((94, 53), Image.BOX)
    img = [[0] * 96 for _ in range(64)]
    for y in range(53):
        for x in range(94):
            if alp_s.getpixel((x, y)) < 140:
                continue
            r, g, b = rgb_s.getpixel((x, y))
            img[8 + y][x] = min(LOGO_PALETTE, key=lambda k: sum((a - c) ** 2 for a, c in zip(LOGO_PALETTE[k], (r, g, b))))

    # keep outer boundary in dark red (2/3) like the original ぷよぷよ and drop 1px spikes
    for y in range(64):
        for x in range(96):
            v = img[y][x]
            if v >= 8 and any(0 <= y + dy < 64 and 0 <= x + dx < 96 and img[y + dy][x + dx] == 0 for dx, dy in dirs):
                img[y][x] = 3 if v <= 10 else 2
    spikes = [(x, y) for y in range(64) for x in range(96) if img[y][x] and
              sum(1 for dx, dy in dirs if 0 <= y + dy < 64 and 0 <= x + dx < 96 and img[y + dy][x + dx]) <= 1]
    for x, y in spikes:
        img[y][x] = 0

    pal = [(0, 0, 0)] * 16
    for k, c in LOGO_PALETTE.items():
        pal[k] = c
    png.write(os.path.join(OUT, 'logo_puyo.png'), img, pal)
    print('logo_puyo')


# the entry screen's "<how many> de Puyo Puyo": the number part (ひとり, ふたり, さんにん,
# よにん: 96, 96, 128 and 96 pixels wide) drawn flush right, against "PUYO PUYO" (でぷよぷよ)
COUNT = {'count_1p': ("1P", 96), 'count_2p': ("2P", 96), 'count_3p': ("3P", 128),
         'count_4p': ("4P", 96)}
PUYO_PUYO = ("PUYO PUYO", 160)


def entry_words():
    from PIL import ImageChops
    for name, (text, w) in COUNT.items():
        m = bigtext.mask(text, w, 48, 28, -1, dy=4)
        right = m.getbbox()[2]
        m = ImageChops.offset(m, w - 3 - right, 0)
        png.write(os.path.join(OUT, name + '.png'), bigtext.indexed(m, 9, 0xe, 1), GREY)
        print(name)
    text, w = PUYO_PUYO
    m = bigtext.mask(text, w, 48, 28, -1, dy=4)
    left = m.getbbox()[0]
    m = ImageChops.offset(m, 3 - left, 0)
    png.write(os.path.join(OUT, 'puyo_puyo.png'), bigtext.indexed(m, 9, 0xe, 1), GREY)
    print('puyo_puyo')


# ルールを選んでください over the rule select screen: 264 x 24, green letters lit from
# the top left (7 highlight, 5, 4 body, 3 lower edge) with a dark drop shadow (2)
CHOOSE_RULE = ("CHOOSE A RULE!", 264, 24, 21)


def rule_title():
    text, w, h, size = CHOOSE_RULE
    m = bigtext.mask(text, w, h, size, 0, dy=-1)
    body = [[m.getpixel((x, y)) >= 110 for x in range(w)] for y in range(h)]
    on = lambda x, y: 0 <= x < w and 0 <= y < h and body[y][x]
    img = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if on(x, y):
                if not on(x, y - 1) or not on(x - 1, y):
                    img[y][x] = 7
                elif not on(x, y - 2) or not on(x - 2, y):
                    img[y][x] = 5
                elif not on(x, y + 1) or not on(x + 1, y):
                    img[y][x] = 3
                else:
                    img[y][x] = 4
            elif on(x - 1, y - 1) or on(x - 2, y - 2) or on(x - 1, y) or on(x, y - 1):
                img[y][x] = 2
    png.write(os.path.join(OUT, 'choose_rule.png'), img, GREY)
    print('choose_rule')


# やった over the winner's side after a match: 96 x 40, white (f) with an outline that
# darkens outwards (b, 9, 4)
YAY = ("YAY!", 96, 40, 33)


def yay():
    text, w, h, size = YAY
    from PIL import ImageChops
    m = bigtext.mask(text, w, h, size, 0, dy=0)
    left, top, right, bottom = m.getbbox()
    m = ImageChops.offset(m, (w - right - left) // 2, (h - bottom - top) // 2)
    body = [[m.getpixel((x, y)) >= 110 for x in range(w)] for y in range(h)]
    img = [[0xf if body[y][x] else 0 for x in range(w)] for y in range(h)]
    for ring in (0xb, 0x9, 0x4):
        prev = [r[:] for r in img]
        for y in range(h):
            for x in range(w):
                if prev[y][x] == 0 and any(0 <= y + dy < h and 0 <= x + dx < w and prev[y + dy][x + dx]
                                           for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    img[y][x] = ring
    png.write(os.path.join(OUT, 'yay.png'), img, GREY)
    print('yay')


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (text, w, h, size, track, dy, fill, edge, outline) in BIG.items():
        img = bigtext.indexed(bigtext.mask(text, w, h, size, track, dy=dy), fill, edge, outline)
        png.write(os.path.join(OUT, name + '.png'), img, GREY)
        print(name)
    logo()
    entry_words()
    rule_title()
    yay()


if __name__ == '__main__':
    main()
