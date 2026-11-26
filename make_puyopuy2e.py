#!/usr/bin/env python3
"""make_puyopuy2e.py [--logo MODE] [FOLDER | puyopuy2.zip] [OUT_FOLDER]

Builds puyopuy2e.zip, Puyo Puyo 2 (English bootleg), from the MAME set puyopuy2.zip.
FOLDER is where puyopuy2.zip is (default: this folder); the new set is written next to
it, or to OUT_FOLDER. Only Python 3 is needed."""
import argparse, os, sys, zipfile, zlib, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import romset, build, logo

OUT_NAMES = ('pp2e-17241.ic32', 'pp2e-17240.ic31')
# expected (even, odd) program CRCs for each --logo mode
EXPECTED = {
    'no-red-puyos':   (0x22cbbe78, 0xdade073a),
    'with-red-puyos': (0x92a1fcd8, 0x5c2b808d),
    'original':       (0x23306e66, 0xf6674634),
}


def main():
    p = argparse.ArgumentParser(usage='make_puyopuy2e.py [--logo MODE] [FOLDER | puyopuy2.zip] [OUT_FOLDER]')
    p.add_argument('--logo', choices=logo.MODES, default=logo.DEFAULT_MODE,
                   help='title logo variant (default: %(default)s)')
    args, pos = p.parse_known_args()
    bad = [a for a in pos if a.startswith('-')]
    if bad:
        p.error('unrecognized arguments: %s' % ' '.join(bad))
    src = pos[0] if pos else HERE
    if os.path.isdir(src):
        src = os.path.join(src, 'puyopuy2.zip')
    if not os.path.exists(src):
        raise SystemExit('%s not found: put puyopuy2.zip (the MAME set) there' % src)
    out_dir = pos[1] if len(pos) > 1 else os.path.dirname(os.path.abspath(src))
    prog = romset.read_program(src)
    sound = romset.read_sound(src)
    new = build.build(prog, args.logo)
    even, odd = romset.split_program(new)
    out = os.path.join(out_dir, 'puyopuy2e.zip')
    files = ((OUT_NAMES[0], even), (OUT_NAMES[1], odd), (romset.SOUND[0], sound))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            z.writestr(name, data)
    print('written', out)
    expected = (*EXPECTED[args.logo], romset.SOUND[1])
    ok = True
    for (name, data), want in zip(files, expected):
        crc = zlib.crc32(data) & 0xffffffff
        print('  %-16s %7d  %08x  %s' % (name, len(data), crc, hashlib.sha1(data).hexdigest()))
        ok = ok and crc == want
    print('CRCs match expected (%s)' % args.logo if ok else
          'WARNING: the CRCs differ from expected (%s)' % args.logo)


if __name__ == '__main__':
    main()
