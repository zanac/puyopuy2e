"""Builds the English program from the original one (tools/make_puyopuy2e.py runs it)."""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'text'))
import font, text, script_en, gfx, titles, labels, logo, linkmsg, levels


def patch_file(name):
    return open(os.path.join(ROOT, 'patch', name), 'rb').read()


def jmp(prog, at, to, length):
    """jmp to.l at at, the rest of length nops"""
    code = struct.pack('>HI', 0x4ef9, to) + b'\x4e\x71' * ((length - 6) // 2)
    prog[at:at + length] = code


def update_checksums(prog):
    """Update the 16-bit EPROM checksums at 0x1f8 (IC32) and 0x1fa (IC31) for MEMORY TEST."""
    sums = [sum((prog[a] << 8) | prog[a + 2] for a in range(off, len(prog), 4)
                if not (0x1f8 <= a < 0x200)) & 0xffff for off in (0, 1)]
    prog[0x1f8:0x1fc] = struct.pack('>HH', *sums)


def build(prog, logo_mode=logo.DEFAULT_MODE):
    prog = bytearray(prog)
    # text engine: 8x16 glyphs
    eng = patch_file('text8.bin')
    assert len(eng) <= 0x17676 - 0x17538
    prog[0x17538:0x17538 + len(eng)] = eng
    # font
    prog[text.FONT_BANK_ENTRY:text.FONT_BANK_ENTRY + 2] = struct.pack('>H', text.FONT & 0xffff)
    for code, rows in font.font().items():
        prog[text.FONT + code * 16:text.FONT + code * 16 + 16] = rows
    # page openers: indirect English text
    hooks = patch_file('hooks.bin')
    prog[text.HOOKS:text.HOOKS + len(hooks)] = hooks
    jmp(prog, 0x171b4, text.HOOKS, 14)          # op 03
    jmp(prog, 0x1720c, text.HOOKS + 0x10, 24)   # op 0b
    used = text.apply(prog, script_en.TEXT)
    print('English text: %d bytes' % used)
    streams = gfx.Streams(prog)
    titles.apply(streams)
    labels.apply(streams)
    logo.apply(prog, streams, logo_mode)
    if logo_mode != 'original':
        logo.apply_wallpaper(streams.get(logo.WALLPAPER_TILES), 258, logo_mode)
    labels.apply_service(prog)
    labels.apply_yay(prog, streams)
    labels.apply_sign(prog, streams)
    end = linkmsg.apply(prog, streams, text.TEXT_AT + used, text.TEXT_END)
    print('join-in messages: %d bytes' % (end - text.TEXT_AT - used))
    end = levels.apply(prog, streams, end, text.TEXT_END)
    streams.write()
    update_checksums(prog)
    return prog
