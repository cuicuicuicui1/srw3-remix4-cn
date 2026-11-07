import json,hashlib,sys
from build import ROOT,SOURCE_SHA
sys.path.insert(0,str(ROOT/'source/vendor'))
from native_parser import Rom,GlyphMap,Parser,file_offset

def prepare():
    rom=Rom(ROOT/'inputs/remix4-original.sfc');gm=GlyphMap(ROOT/'source/japanese-map.json');rows=[]
    for entry in range(16):
        address=rom.data[0x3742f+entry*2:0x37431+entry*2];start=int.from_bytes(address,'little')
        p=Parser(rom,gm,6,start).parse()
        assert p.stop_reason=='FF_end'and all(t.kind in ['glyph','FF']for t in p.tokens)
        text=''.join(t.text for t in p.tokens if t.kind=='glyph')
        if not text:continue
        raw=b''.join(t.raw for t in p.tokens);off=file_offset(6,start)
        rows.append({'id':f'name-06-{start:04X}','source_cpu':0x60000|start,'source_offset':off,'source_hex':raw.hex(),'japanese':text,'original_pixel_width':sum(12 if len(t.raw)==2 else 8 for t in p.tokens if t.kind=='glyph'),'aliases':[{'table_cpu':0x06f42f,'entry':entry}],'translation':''})
    out=ROOT/'work/zcode-extra-names';out.mkdir(exist_ok=True)
    result={'source_rom_sha256':SOURCE_SHA,'entries':rows,'scope':'independent 16-slot item-label table; last two empty; actual consumers not yet located'}
    (out/'input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('item labels',len(rows))
if __name__=='__main__':prepare()
