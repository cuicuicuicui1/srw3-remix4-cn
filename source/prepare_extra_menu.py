"""Bounded pure-text low-menu roots called with inherited glyph mode."""
import json,hashlib
from build import ROOT,SOURCE_SHA

def prepare():
    data=(ROOT/'inputs/remix4-original.sfc').read_bytes()
    mapping={int(k,16):v for k,v in json.loads((ROOT/'source/japanese-map.json').read_text(encoding='utf-8')).items()}
    old=json.loads((ROOT/'work/zcode-menu/input.json').read_text(encoding='utf-8'))['entries']
    rows={};rejected=[]
    for group,count in {0:154,1:128,2:255,8:128}.items():
        tab=int.from_bytes(data[0x5277+3*group:0x527a+3*group],'little');bank=tab>>16
        root=bank*0x8000+(tab&0x7fff)
        for entry in range(count):
            start=int.from_bytes(data[root+entry*2:root+entry*2+2],'little')
            if start<0x8000:continue
            offset=bank*0x8000+(start&0x7fff);p=offset;letters=[];widths=[];width=0
            while p-offset<512 and p//0x8000==offset//0x8000:
                c=data[p]
                if c==0xff:break
                if c==0xf3:letters.append('\n');widths.append(width);width=0;p+=1;continue
                if c<=0xef:code=c;length=1
                elif c<=0xf2:code=c<<8|data[p+1];length=2
                else:break
                ch=mapping.get(code)
                if not ch or '<'in ch:break
                letters.append(ch);width+=12 if length==2 else 8;p+=length
            if data[p]!=0xff:continue
            text=''.join(letters)
            if not text.strip():continue
            cpu=bank<<16|start;end=cpu+(p-offset)
            overlaps=[x for x in old if max(cpu,x['source_cpu'])<min(end,x['end_cpu'])]
            if overlaps:
                assert any(x['source_cpu']<=cpu and end<=x['end_cpu']for x in overlaps),('partial overlap',hex(cpu))
                continue
            sid=f'menu-{bank:02X}-{start:04X}-{start+p-offset:04X}'
            rows.setdefault(sid,{'id':sid,'source_cpu':cpu,'end_cpu':end,'source_hex':data[offset:p].hex(),'japanese':text,'source_line_pixel_widths':widths+[width],'source_root':cpu,'translation':'','root_aliases':[]})['root_aliases'].append({'group':group,'entry':entry})
    out=ROOT/'work/zcode-extra-menu';out.mkdir(exist_ok=True)
    excluded=[];included=[]
    for row in rows.values():
        stripped=row['japanese'].strip()
        if set(stripped)<=set('ＵＶＷＸ')or 0x03c654<=row['source_cpu']<0x03c674:
            excluded.append(dict(row,reason='controller or frame tile sequences; original glyph IDs form graphics, not language'))
        else:included.append(row)
    result={'source_rom_sha256':SOURCE_SHA,'contract':'pure glyph/F3/FF roots in low UI tables; callers can inherit glyph mode; no native controls rewritten','entries':included,'excluded':excluded}
    (out/'input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('extra pure menu roots',len(rows))
    for x in rows.values():print(x['id'],repr(x['japanese']))
    return result
if __name__=='__main__':prepare()
