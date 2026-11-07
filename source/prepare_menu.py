"""Collect low-level UI literals only when native F4 selected glyph mode."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]

def prepare(initial_mode=False,target='zcode-menu',only_roots=None):
    source=(ROOT/'inputs/remix4-original.sfc').read_bytes()
    mapping={int(c,16):v for c,v in json.loads((ROOT/'source/japanese-map.json').read_text(encoding='utf-8')).items()}
    counts={0:154,1:128,2:255,8:128}
    args={0xf0:3,0xf1:2,0xf2:1,0xf3:0,0xf4:1,0xf5:1,0xf6:2,0xf7:4,0xf8:3,0xf9:3,0xfa:1,0xfb:0,0xfc:2,0xfd:2,0xfe:1,0xff:0}
    spans={};unresolved=[];root_count=0;visited=set()
    def text_address(group,entry):
        p=0x5277+group*3
        if not 0<=group<48:return None
        root=int.from_bytes(source[p:p+3],'little');bank=root>>16;pointer=root&65535
        if pointer<0x8000 or bank>47:return None
        off=bank*0x8000+(pointer&0x7fff)+entry*2
        if off+2>len(source):return None
        addr=int.from_bytes(source[off:off+2],'little')
        return (bank<<16)|addr if addr>=0x8000 else None
    def parse(cpu,mode=False,depth=0):
        if depth>12:return None
        bank=cpu>>16;p=cpu&65535;seen=set();run=[]
        def flush():
            if not run:return
            if not any(x[0]=='glyph'for x in run):run.clear();return
            start=run[0][1];end=run[-1][2];raw=source[bank*0x8000+(start&0x7fff):bank*0x8000+(end&0x7fff)]
            if end==0x10000:raw=source[bank*0x8000+(start&0x7fff):(bank+1)*0x8000]
            sid=f'menu-{bank:02X}-{start:04X}-{end:04X}'
            text=''.join(x[3]for x in run)
            if text.strip() and any(x[0]=='glyph'and x[3].strip()for x in run):
                widths=[];width=0
                for kind,a,b,ch in run:
                    if kind=='F3':widths.append(width);width=0
                    else:width+=12 if b-a==2 else 8
                widths.append(width)
                spans[sid]={'id':sid,'source_cpu':bank<<16|start,'end_cpu':bank<<16|end,'source_hex':raw.hex(),'japanese':text,'source_line_pixel_widths':widths,'source_root':cpu,'translation':''}
            run.clear()
        while 0x8000<=p<0x10000:
            if p in seen:flush();return mode
            seen.add(p);off=bank*0x8000+(p&0x7fff)
            if off>=len(source):flush();return None
            c=source[off]
            if mode and c<=0xf2:
                start=p
                if c in [0xf0,0xf1,0xf2]:code=c*256+source[off+1];p+=2
                elif c<=0xef:code=c;p+=1
                ch=mapping.get(code,f'<U_{code:04X}>')
                if '<BLANK_'in ch:ch=' '
                run.append(('glyph',start,p,ch));continue
            if mode and c==0xf3:run.append(('F3',p,p+1,'\n'));p+=1;continue
            flush()
            if c<0xf0:p+=1;continue
            n=args[c]
            if p+1+n>0x10000:return None
            operands=source[off+1:off+1+n];p+=1+n
            if c==0xf4:mode=bool(operands[0]&0x40)
            elif c==0xf6:
                entry,group=operands
                if 255 in operands:
                    # Dynamic calls into names/number buffers do not contain F4.
                    if group<16:mode=None
                    continue
                if group<16:
                    target=text_address(group,entry)
                    if target:
                        key=(target,mode)
                        if key not in visited:
                            visited.add(key);mode=parse(target,mode,depth+1)
                    else:mode=None
            elif c==0xff:return mode
        return None
    for group,count in counts.items():
        for entry in range(count):
            address=text_address(group,entry)
            if address is None:continue
            if only_roots is not None and address not in only_roots:continue
            root_count+=1
            parse(address,initial_mode)
    # Avoid substring host replacement swallowing an independently entered literal.
    values=list(spans.values());conflicts=[]
    for i,a in enumerate(values):
        for b in values[i+1:]:
            if a['source_cpu']<b['source_cpu']<a['end_cpu']or b['source_cpu']<a['source_cpu']<b['end_cpu']:
                conflicts.append([a['id'],b['id']])
    data={'source_rom_sha256':hashlib.sha256(source).hexdigest(),'root_count':root_count,'scope':'low script F4 glyph-mode literals only; native controls remain in source ROM; table lengths bounded by explicit provisional schema','entries':values,'overlap_conflicts':conflicts,'unknown':unresolved}
    if target!='zcode-menu':
        known=[]
        for folder in ['zcode-menu','zcode-extra-menu']:
            known+=json.loads((ROOT/'work'/folder/'input.json').read_text(encoding='utf-8'))['entries']
        fresh=[]
        for row in values:
            overlap=[x for x in known if max(x['source_cpu'],row['source_cpu'])<min(x['end_cpu'],row['end_cpu'])]
            if not overlap:fresh.append(row)
            else:assert any(x['source_cpu']==row['source_cpu']and x['end_cpu']==row['end_cpu']for x in overlap),('new mixed overlap',row['id'])
        data['entries']=fresh
    out=ROOT/'work'/target;out.mkdir(exist_ok=True)
    (out/'input.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('menu literals',len(values),'characters',sum(len(x['japanese'])for x in values),'conflicts',len(conflicts))
    for x in values[:12]:print(x['id'],repr(x['japanese']),x['source_line_pixel_widths'])
    return data
if __name__=='__main__':prepare()
