"""Portable build of the accepted graph; requires the exact user-owned base."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'edcffa7b6aa734735b64f7674f02e2cf4e24a7a499cfd24675ad34c86218fe8f'
TARGET_SHA = 'bcde4e317f945b23c4ceac6bca89e6725812eb94e53d3cd51cc0e09e0dd608cd'
FONT_SHA = 'b1e9a54fdd1c1e86fdc32efa16a04d8bd2897391ddb441238cee66947d6e3388'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(script, *args):
    subprocess.run([sys.executable, '-B', str(ROOT / 'source' / script), *map(str, args)],
                   cwd=ROOT, check=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=ROOT / 'inputs/remix4-original.sfc')
    cli.add_argument('--tag', default='local-001', help='A new directory name below work/build')
    cli.add_argument('--verify-r1', action='store_true', help='Require exact released ROM and BPS bytes')
    args = cli.parse_args()
    if not __debug__:
        raise ValueError('Do not use Python -O: the native build has assertions as safety gates')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.tag):
        raise ValueError('Invalid tag')
    out = ROOT / 'work/build' / args.tag
    if out.exists():
        raise FileExistsError('Build directory already exists; use a new --tag')
    raw = args.source.resolve(strict=True).read_bytes()
    if len(raw) != 0x180000 or sha(raw) != SOURCE_SHA:
        raise ValueError('Wrong input ROM; see README for exact size and SHA256')
    font = ROOT / 'inputs/fonts/fusion-pixel-12px-zh_hans.bdf'
    if sha(font.read_bytes()) != FONT_SHA:
        raise ValueError('Font identity mismatch')
    local = ROOT / 'inputs/remix4-original.sfc'
    if local.exists():
        if local.read_bytes() != raw:
            raise ValueError('Existing local input differs; refusing to overwrite it')
    else:
        local.parent.mkdir(parents=True, exist_ok=True)
        with local.open('xb') as f:
            f.write(raw)
    run('prepare_title.py')
    run('build_graph.py', args.tag)
    run('verify_graph.py', args.tag)
    run('verify_hooks.py', args.tag)
    sys.path.insert(0, str(ROOT / 'patches/R1'))
    import bps
    target = (out / 'remix4-cn.sfc').read_bytes()
    patch = bps.encode(raw, target, b'SRW3 ReMix4 Chinese R1 2026-10-27 exact supplied base')
    if bps.decode(patch, raw) != target:
        raise ValueError('BPS replay differs from the build')
    if args.verify_r1:
        if sha(target) != TARGET_SHA or patch != (ROOT / 'patches/R1/remix4-cn.bps').read_bytes():
            raise ValueError('Build differs from R1')
    identity = {'source_sha256': SOURCE_SHA, 'source_size': len(raw),
                'target_sha256': sha(target), 'target_size': len(target),
                'patch_sha256': sha(patch), 'patch_size': len(patch)}
    (out / 'remix4-cn.bps').write_bytes(patch)
    (out / 'identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    for name in ['apply_patch.py', 'bps.py']:
        shutil.copyfile(ROOT / 'patches/R1' / name, out / name)
    print(json.dumps({'status': 'pass', 'output': str(out), **identity}, ensure_ascii=False))


if __name__ == '__main__':
    main()
