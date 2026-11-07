"""Apply the exact-source BPS without overwriting any existing file."""
from pathlib import Path
import argparse,hashlib,json,os,sys
import bps

def main():
    parser=argparse.ArgumentParser(description='Apply SRW3 ReMix4 Chinese BPS to the exact original input.')
    parser.add_argument('source');parser.add_argument('output')
    parser.add_argument('--patch',default=str(Path(__file__).with_name('remix4-cn.bps')))
    parser.add_argument('--identity',default=str(Path(__file__).with_name('identity.json')))
    args=parser.parse_args()
    src=Path(args.source).resolve(strict=True);patch=Path(args.patch).resolve(strict=True)
    output=Path(args.output).resolve();identity=json.loads(Path(args.identity).read_text(encoding='utf-8'))
    assert output not in [src,patch,Path(args.identity).resolve()],'Output aliases input'
    assert not output.exists(),'Output exists; choose a new filename'
    raw=src.read_bytes();encoded=patch.read_bytes()
    assert len(raw)==identity['source_size']and hashlib.sha256(raw).hexdigest()==identity['source_sha256'],'Wrong source ROM'
    assert hashlib.sha256(encoded).hexdigest()==identity['patch_sha256'],'Patch identity mismatch'
    result=bps.decode(encoded,raw)
    assert len(result)==identity['target_size']and hashlib.sha256(result).hexdigest()==identity['target_sha256'],'Target identity mismatch'
    with output.open('xb')as f:f.write(result)
    print('OK '+identity['target_sha256'])
if __name__=='__main__':
    try:main()
    except Exception as e:print('REFUSED: '+str(e),file=sys.stderr);raise SystemExit(1)
