"""Build source-preserving complete graph components from accepted ZCode text."""
from pathlib import Path
import json,hashlib,sys,textwrap,re,unicodedata
from build import ROOT,SOURCE_SHA,FONT_PATH,bdf_font,glyph32,Asm

def load_graph():
    graph=json.loads((ROOT/'work/text-graph/graph.json').read_text(encoding='utf-8'))
    names_path=ROOT/'work/zcode-names/translations.json'
    if names_path.is_file():
        original=json.loads((ROOT/'work/name-contracts.json').read_text(encoding='utf-8'))
        names=json.loads(names_path.read_text(encoding='utf-8-sig'))
        assert names['source_rom_sha256']==original['source_rom_sha256']==SOURCE_SHA
        expected={x['id']:x for x in original['entries']};rows=names['entries']
        assert len(rows)==len(expected) and len({x['id']for x in rows})==len(rows)
        assert set(expected)=={x['id']for x in rows}
        byid={x['id']:x for x in rows}
        for sid,src in expected.items():
            row=byid[sid];assert row['japanese']==src['japanese']
            display=row.get('display')or row['translation'];assert display
            raw=bytes.fromhex(src['source_hex']);assert raw[-1]==255
            bank=src['source_cpu']>>16;start=src['source_cpu']&65535
            # Names are independently bounded strings: raw source preimage is checked at build.
            graph['nodes'].append({'source_cpu':src['source_cpu'],'source_offset':src['source_offset'],'stop':'FF_end','complete_block':True,'tokens':[{'offset':start,'kind':'glyph','raw':raw[:-1].hex(),'text':src['japanese'],'params':{}},{'offset':start+len(raw)-1,'kind':'FF','raw':'ff','text':'<FF>','params':{}}],'edges':[],'fallthrough':None,'root_ids':[src['id']],'unknown_glyphs':[],'span_refs':[{'id':sid,'first_offset':start,'end_offset':start+len(raw)-1}],'resource_type':'name'})
            graph['literal_spans'].append({'id':sid,'japanese':src['japanese'],'source_hex':raw[:-1].hex(),'hosts':[src['source_cpu']],'translation':display,'resource_type':'name','original_pixel_width':src['original_pixel_width']})
    extra_path=ROOT/'work/zcode-extra-names/translations.json'
    if extra_path.exists():
        contract=json.loads(extra_path.with_name('input.json').read_text(encoding='utf-8'))
        extra=json.loads(extra_path.read_text(encoding='utf-8-sig'))
        assert extra['source_rom_sha256']==contract['source_rom_sha256']==SOURCE_SHA
        expected={x['id']:x for x in contract['entries']};rows={x['id']:x for x in extra['entries']}
        assert len(rows)==len(extra['entries'])and set(rows)==set(expected)
        existing={x['source_cpu']for x in graph['nodes']}
        for sid,src in expected.items():
            row=rows[sid];assert row['japanese']==src['japanese']
            text=row.get('display')or row['translation'];assert text
            raw=bytes.fromhex(src['source_hex']);assert raw[-1]==255
            addr=src['source_cpu'];assert addr not in existing
            start=addr&65535
            graph['nodes'].append({'source_cpu':addr,'source_offset':src['source_offset'],'stop':'FF_end','complete_block':True,'tokens':[{'offset':start,'kind':'glyph','raw':raw[:-1].hex(),'text':src['japanese'],'params':{}},{'offset':start+len(raw)-1,'kind':'FF','raw':'ff','text':'<FF>','params':{}}],'edges':[],'fallthrough':None,'root_ids':[sid],'unknown_glyphs':[],'span_refs':[{'id':sid,'first_offset':start,'end_offset':start+len(raw)-1}],'resource_type':'item-name'})
            graph['literal_spans'].append({'id':sid,'japanese':src['japanese'],'source_hex':raw[:-1].hex(),'hosts':[addr],'translation':text,'resource_type':'item-name','original_pixel_width':src['original_pixel_width']})
    return graph

def translations(graph):
    spans={x['id']:x for x in graph['literal_spans']}
    bytext={x['japanese'].replace('\n',''):x['translation']for x in spans.values()if x['translation']}
    accepted=[]
    for batch in sorted((ROOT/'work').glob('zcode-bulk-*')):
        input_path=batch/'input.json';output=batch/'translations.json'
        if not output.exists():continue
        inp=json.loads(input_path.read_text(encoding='utf-8-sig'));out=json.loads(output.read_text(encoding='utf-8-sig'))
        assert inp['source_rom_sha256']==out['source_rom_sha256']==SOURCE_SHA
        expected={x['id']:x for x in inp['entries']};rows=out['entries']
        assert len(rows)==len(expected) and len(set(x['id']for x in rows))==len(rows)
        assert {x['id']for x in rows}==set(expected)
        for row in rows:
            assert row['japanese']==expected[row['id']]['japanese'],row['id']
            text=row['translation'];assert text and '<U_'not in text and '<F'not in text
            bytext[row['japanese'].replace('\n','')]=text
        accepted.append({'batch':batch.name,'entries':len(rows),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
    override=ROOT/'work/zcode-final-review/overrides.json'
    if override.exists():
        data=json.loads(override.read_text(encoding='utf-8-sig'));assert data['source_rom_sha256']==SOURCE_SHA
        for row in data['entries']:
            assert row['id']in spans and spans[row['id']]['japanese']==row['japanese']
            bytext[row['japanese'].replace('\n','')]=row['translation']
    result={sid:bytext[x['japanese'].replace('\n','')]for sid,x in spans.items()if x['japanese'].replace('\n','')in bytext}
    speaker_path=ROOT/'work/translation-review/speaker-map-reviewed.json'
    speakers=json.loads(speaker_path.read_text(encoding='utf-8'))if speaker_path.exists()else{}
    for sid,text in list(result.items()):
        japanese=spans[sid]['japanese']
        match=re.match(r'^([^「（\n]{1,25})[「（]',japanese)
        if match and match[1]in speakers:
            opening=re.search(r'[「“（]',text)
            if opening and opening.start()<30:
                text=speakers[match[1]]+('：'if opening[0]in'「“'else'')+text[opening.start():]
        result[sid]=text.replace('「','“').replace('」','”')
    return result,accepted

def connected(nodes):
    adjacent={address:set()for address in nodes}
    for address,node in nodes.items():
        for dst in [e['target']for e in node['edges']]+([node['fallthrough']]if node['fallthrough']else[]):
            adjacent[address].add(dst);adjacent[dst].add(address)
    seen=set();result=[]
    for root in sorted(nodes):
        if root in seen:continue
        todo=[root];component=[]
        while todo:
            address=todo.pop()
            if address in seen:continue
            seen.add(address);component.append(address);todo.extend(adjacent[address]-seen)
        result.append(sorted(component))
    return result

def hooks(redirects):
    a=Asm(0x3f8000)
    table=0x3f8800
    def redirect(name,destination,initial=False,ptr=0xad):
        a.label(name)
        a.emit(0x85,ptr,0x08,0x48,0xda,0x5a,0xa5,0x00,0x48) # preserve A/X/Y/P and scratch
        a.emit(0xa5,0x02,0x48,0xa5,0x04,0x48,0xa5,0x06,0x48)
        a.word(0xa9,0).emit(0x85,0x00).word(0xa9,len(redirects)).emit(0x85,0x02)
        a.label(name+'-search')
        a.emit(0xa5,0x00,0xc5,0x02);a.cond(0xb0,name+'-done')
        a.emit(0x18,0x65,0x02,0x4a,0x85,0x04,0x0a,0x85,0x06,0x0a,0x18,0x65,0x06,0xaa)
        a.long(0xbf,table+2).word(0x29,255).emit(0x85,0x06)
        a.emit(0xa5,ptr+2).word(0x29,255).emit(0xc5,0x06)
        a.cond(0x90,name+'-lower');a.cond(0xd0,name+'-higher')
        a.long(0xbf,table).emit(0x85,0x06,0xa5,ptr,0xc5,0x06)
        a.cond(0x90,name+'-lower');a.cond(0xd0,name+'-higher')
        a.long(0xbf,table+3).emit(0x85,ptr,0xe2,0x20)
        a.long(0xbf,table+5).emit(0x85,ptr+2,0xc2,0x20);a.jump(name+'-done')
        a.label(name+'-lower');a.emit(0xa5,0x04,0x85,0x02);a.jump(name+'-search')
        a.label(name+'-higher');a.emit(0xa5,0x04,0x1a,0x85,0x00);a.jump(name+'-search')
        a.label(name+'-done')
        a.emit(0x68,0x85,0x06,0x68,0x85,0x04,0x68,0x85,0x02,0x68,0x85,0x00,0x7a,0xfa,0x68,0x28)
        if initial:a.word(0xa9,255 if ptr==0xad else 0x8000)
        if isinstance(destination,str):a.jump(destination)
        else:a.long(0x5c,destination)
    redirect('root',0x0184ec,True);redirect('call',0x01858d)
    redirect('menu-root',0x00c7f4,True,0x1a);redirect('menu-call',0x00c804,False,0x1a)
    a.label('menu-getter');a.emit(0xa5,0x1a);a.jump('menu-getter-lookup')
    redirect('menu-getter-lookup','menu-getter-load',False,0x1a)
    a.label('menu-getter-load');a.word(0xa0,0).emit(0xb7,0x1a).long(0x5c,0x00cda7)
    a.label('font')
    a.emit(0x08,0x48,0xda)
    for ptr,value in [(0xf4,0x8856),(0xf7,0x885e),(0xfa,0x8866),(0xfd,0x886e)]:a.word(0xa9,value).emit(0x85,ptr)
    a.emit(0xe2,0x20,0xa9,0x10)
    for ptr in [0xf6,0xf9,0xfc,0xff]:a.emit(0x85,ptr)
    a.emit(0xc2,0x20,0xa5,0xaf).word(0x29,255).word(0xc9,0x30);a.cond(0x90,'font-done')
    a.word(0xc9,0x3c);a.cond(0xb0,'font-done')
    a.emit(0xa3,3).word(0xc9,0xe8);a.cond(0x90,'font-done')
    a.word(0xc9,0xf3);a.cond(0xb0,'font-done')
    a.emit(0x38).word(0xe9,0xe8).emit(0x0a,0xaa)
    a.long(0xbf,0);base_ref=len(a.data)-3
    a.word(0x2c,0x0e1a);a.cond(0x30,'font-base-ready')
    a.emit(0x18).word(0x69,0x1000)
    a.label('font-base-ready');a.emit(0x85,0xf4,0x18)
    for ptr in [0xf7,0xfa,0xfd]:a.word(0x69,8).emit(0x85,ptr)
    a.long(0xbf,0);bank_ref=len(a.data)-3
    a.emit(0xe2,0x20)
    for ptr in [0xf6,0xf9,0xfc,0xff]:a.emit(0x85,ptr)
    a.emit(0xc2,0x20).word(0xa9,0xf0).emit(0x83,3)
    a.label('font-done');a.emit(0xfa,0x68,0x28).word(0xc9,0xf3)
    a.cond(0xb0,'font-control');a.long(0x5c,0x0185af)
    a.label('font-control');a.long(0x5c,0x0185e8)
    a.label('menu-font')
    a.emit(0x08,0x48,0xda)
    for ptr,value in [(0xf4,0x8856),(0xf7,0x885e),(0xfa,0x8866),(0xfd,0x886e)]:a.word(0xa9,value).emit(0x85,ptr)
    a.emit(0xe2,0x20,0xa9,0x10)
    for ptr in [0xf6,0xf9,0xfc,0xff]:a.emit(0x85,ptr)
    a.emit(0xc2,0x20,0xa5,0x1c).word(0x29,255).word(0xc9,0x30);a.cond(0x90,'menu-font-native')
    a.word(0xc9,0x3c);a.cond(0xb0,'menu-font-native')
    a.emit(0xa3,3).word(0xc9,0xe8);a.cond(0x90,'menu-font-single')
    a.word(0xc9,0xf3);a.cond(0xb0,'menu-font-native')
    a.emit(0x38).word(0xe9,0xe8).emit(0x0a,0xaa)
    a.long(0xbf,0);menu_base_ref=len(a.data)-3
    a.word(0x2c,0x0e1a);a.cond(0x30,'menu-font-base-ready')
    a.emit(0x18).word(0x69,0x1000)
    a.label('menu-font-base-ready');a.emit(0x85,0xf4,0x18)
    for ptr in [0xf7,0xfa,0xfd]:a.word(0x69,8).emit(0x85,ptr)
    a.long(0xbf,0);menu_bank_ref=len(a.data)-3
    a.emit(0xe2,0x20)
    for ptr in [0xf6,0xf9,0xfc,0xff]:a.emit(0x85,ptr)
    a.emit(0xc2,0x20).word(0xa9,0xf0).emit(0x83,3,0xfa,0x68,0x28)
    a.long(0x5c,0x00c832)
    a.label('menu-font-single');a.emit(0xfa,0x68,0x28).long(0x5c,0x00c877)
    a.label('menu-font-native');a.emit(0xfa,0x68,0x28,0x24,0x2a)
    a.cond(0x70,'menu-font-map');a.long(0x5c,0x00c80b)
    a.label('menu-font-map');a.long(0x5c,0x00c828)
    a.label('font-bases')
    for i in range(11):a.emit(*(0x7000+(i%4)*0x2000).to_bytes(2,'little'))
    a.label('font-banks')
    for i in range(11):a.emit(*(0x3c+i//4).to_bytes(2,'little'))
    a.data[base_ref:base_ref+3]=a.labels['font-bases'].to_bytes(3,'little')
    a.data[bank_ref:bank_ref+3]=a.labels['font-banks'].to_bytes(3,'little')
    a.data[menu_base_ref:menu_base_ref+3]=a.labels['font-bases'].to_bytes(3,'little')
    a.data[menu_bank_ref:menu_bank_ref+3]=a.labels['font-banks'].to_bytes(3,'little')
    code=a.finish();assert len(code)<0x800
    assert len(redirects)*6<=0x7800
    data=b''.join(src.to_bytes(3,'little')+dst.to_bytes(3,'little')for src,dst in sorted(redirects.items()))
    return code,data,a.labels

def build(tag):
    source=(ROOT/'inputs/remix4-original.sfc').read_bytes();assert hashlib.sha256(source).hexdigest()==SOURCE_SHA
    graph=load_graph()
    assert not graph['unknown_nodes'] and not graph['invalid_anchors']
    nodes={n['source_cpu']:n for n in graph['nodes']}
    translated,batches=translations(graph)
    menu_entries=[]
    menu_review_path=ROOT/'work/translation-review/menu-overrides.json'
    menu_review=json.loads(menu_review_path.read_text(encoding='utf-8'))if menu_review_path.exists()else{}
    for folder in ['zcode-menu','zcode-extra-menu','zcode-mixed-menu']:
        menu_path=ROOT/'work'/folder/'translations.json'
        if not menu_path.exists():continue
        menu=json.loads(menu_path.read_text(encoding='utf-8-sig'))
        original_menu=json.loads(menu_path.with_name('input.json').read_text(encoding='utf-8'))
        assert menu['source_rom_sha256']==original_menu['source_rom_sha256']==SOURCE_SHA
        expected={x['id']:x for x in original_menu['entries']}
        assert len(menu['entries'])==len(expected) and len({x['id']for x in menu['entries']})==len(expected)
        for x in menu['entries']:
            old=expected[x['id']];assert x['japanese']==old['japanese']
            if x['id']in menu_review:
                review=menu_review[x['id']];assert review['japanese']==x['japanese']
                x=dict(x,translation=review['translation'])
            x=dict(x,translation=x['translation'].replace('「','“').replace('」','”'))
            assert x['translation']and x['translation'].count('\n')==x['japanese'].count('\n'),x['id']
            if x['id']in ['menu-03-EB89-EBA7','menu-03-EBA9-ED54']:
                # Native glyph-inventory/debug records are a code-space display, not prose.
                continue
            if x['id']=='menu-0C-C9AA-C9AC':
                # Fifteen unused/default slots share this isolated source placeholder.
                # Keep its actual original glyph; an invented "B" is not a translation.
                continue
            menu_entries.append(dict(old,translation=x['translation']))
    accepted=[];waiting=[]
    for component in connected(nodes):
        required={x['id']for address in component for x in nodes[address].get('span_refs',[])}
        if required and required<=set(translated):accepted.append(component)
        elif required:waiting.append(component)
    used_spans={s['id']for c in accepted for q in c for s in nodes[q].get('span_refs',[])}
    texts=''.join(translated[s].replace('\n','')for s in used_spans)+''.join(x['translation'].replace('\n','')for x in menu_entries)
    source_mapping=json.loads((ROOT/'source/japanese-map.json').read_text(encoding='utf-8'))
    ascii_codes={}
    for code,ch in source_mapping.items():
        if int(code,16)>=0xe8 or len(ch)!=1:continue
        if not ('\u3040'<=ch<='\u30ff'):
            ascii_codes[ch]=bytes([int(code,16)])
        norm=unicodedata.normalize('NFKC',ch)
        if len(norm)==1 and 0x20<=ord(norm)<=0x7e:ascii_codes[norm]=bytes([int(code,16)])
    # Original $00 space is ideographic but has the same blank 8px cell.
    ascii_codes[' ']=b'\x00'
    chars=sorted(set(texts)-set(ascii_codes))
    assert chars and len(chars)<=2816,('Chinese glyph encoding capacity',len(chars))
    font=bdf_font(FONT_PATH);assert not [c for c in chars if c not in font]
    encoder={c:bytes([0xe8+i//256,i%256])for i,c in enumerate(chars)}
    encoder.update({c:code for c,code in ascii_codes.items()if c in texts})
    def encode(text):
        lines=textwrap.wrap(text.replace('\n',''),width=16,break_long_words=True,break_on_hyphens=False,replace_whitespace=False,drop_whitespace=False)
        return b'\xf3'.join(b''.join(encoder[c]for c in line)for line in lines)
    encoded={};fixups={}
    for component in accepted:
        for address in component:
            n=nodes[address];refs={s['first_offset']:s for s in n.get('span_refs',[])}
            data=bytearray();patch=[];skip_to=0
            for token in n['tokens']:
                if token['offset']<skip_to:continue
                if token['offset']in refs:
                    span=refs[token['offset']];data.extend(encode(translated[span['id']]));skip_to=span['end_offset'];continue
                raw=bytes.fromhex(token['raw']);base=len(data);data.extend(raw)
                for edge in n['edges']:
                    if edge['token_offset']==token['offset']:patch.append((base+edge['operand_offset'],edge['target']))
            if n['fallthrough']:
                patch.append((len(data)+1,n['fallthrough']));data.extend(b'\xf9\x00\x00')
            encoded[address]=data;fixups[address]=patch
    image=bytearray(source+b'\xff'*0x80000);writes=[]
    def put(offset,data,name,pre=None):
        assert data and offset+len(data)<=len(image)
        assert not any(max(offset,w['start'])<min(offset+len(data),w['end'])for w in writes)
        if offset<len(source):assert pre is not None and image[offset:offset+len(data)]==pre,(name,hex(offset))
        else:assert image[offset:offset+len(data)]==b'\xff'*len(data)
        image[offset:offset+len(data)]=data
        writes.append({'start':offset,'end':offset+len(data),'name':name,'sha256':hashlib.sha256(data).hexdigest()})
    cursor=0x180000;locations={}
    for component in sorted(accepted,key=lambda c:(-sum(len(encoded[q])for q in c),min(c))):
        size=sum(len(encoded[q])for q in component)
        assert size<=0x8000
        if cursor%0x8000+size>0x8000:cursor=(cursor+0x7fff)&~0x7fff
        assert cursor+size<=0x1c8000,('Text pool capacity',hex(cursor),size)
        for address in component:
            locations[address]=cursor;cursor+=len(encoded[address])
    def cpu(offset):return (offset//0x8000)<<16|0x8000|(offset%0x8000)
    relocation={src:cpu(dst)for src,dst in locations.items()}
    for address,data in encoded.items():
        for offset,target in fixups[address]:
            assert relocation[target]>>16==relocation[address]>>16
            data[offset:offset+2]=(relocation[target]&65535).to_bytes(2,'little')
        put(locations[address],data,f'text {address:06X}')
    put(0x1e0000,b''.join(glyph32(font[c])for c in chars),'Chinese font')
    lookup=dict(relocation);menu_records=[];menu_cursor=0x1d8000
    for x in menu_entries:
        raw=b'\xf3'.join(b''.join(encoder[c]for c in line)for line in x['translation'].split('\n'))
        assert raw and menu_cursor+len(raw)+1<=0x1e0000
        # Sentinels are not consumed: the getter redirects at the exact end first.
        put(menu_cursor,raw+b'\xff',x['id'])
        target=cpu(menu_cursor);finish=target+len(raw)
        source_off=(x['source_cpu']>>16)*0x8000+(x['source_cpu']&0x7fff)
        assert source[source_off:source_off+len(bytes.fromhex(x['source_hex']))].hex()==x['source_hex']
        assert x['source_cpu']not in lookup and finish not in lookup
        lookup[x['source_cpu']]=target;lookup[finish]=x['end_cpu']
        menu_records.append(dict(x,target_cpu=target,target_end=finish,offset=menu_cursor,hex=raw.hex()))
        menu_cursor+=len(raw)+1
    code,table,labels=hooks(lookup);put(0x1f8000,code,'entry/font hook code');put(0x1f8800,table,'bounded binary-search redirects')
    put(0x84e7,b'\x5c'+labels['root'].to_bytes(3,'little')+b'\xea','root hook',bytes.fromhex('85ada9ff00'))
    put(0x8714,b'\x5c'+labels['call'].to_bytes(3,'little')+b'\xea','call hook',bytes.fromhex('85ad4c8d85'))
    put(0x8a4a,b'\x5c'+labels['call'].to_bytes(3,'little')+b'\xea','dynamic-name call hook',bytes.fromhex('85ad4c8d85'))
    put(0x85aa,b'\x5c'+labels['font'].to_bytes(3,'little')+b'\xea','font hook',bytes.fromhex('c9f300b039'))
    put(0x47ef,b'\x5c'+labels['menu-root'].to_bytes(3,'little')+b'\xea','menu root hook',bytes.fromhex('851aa90080'))
    put(0x4f24,b'\x5c'+labels['menu-call'].to_bytes(3,'little')+b'\xea','menu subcall hook',bytes.fromhex('851a4c04c8'))
    put(0x4807,b'\x5c'+labels['menu-font'].to_bytes(3,'little'),'menu font hook',bytes.fromhex('242a701d'))
    put(0x4da2,b'\x5c'+labels['menu-getter'].to_bytes(3,'little')+b'\xea','menu literal getter hook',bytes.fromhex('a00000b71a'))
    title=json.loads((ROOT/'work/title/manifest.json').read_text(encoding='utf-8'))
    assert title['source_sha256']==SOURCE_SHA
    packed=(ROOT/'work/title/graphics.lz').read_bytes()
    assert hashlib.sha256(packed).hexdigest()==title['compressed_sha256']
    assert len(packed)<=0x8000
    put(title['new_offset'],packed,'Chinese title menu graphics')
    put(title['source_pointer_offset'],title['new_cpu'].to_bytes(3,'little'),'title graphics pointer',bytes.fromhex(title['source_pointer_hex']))
    checksum=(sum(image[:0x7fdc])+sum(image[0x7fe0:])+0x1fe)&65535
    put(0x7fdc,(checksum^65535).to_bytes(2,'little')+checksum.to_bytes(2,'little'),'checksum',source[0x7fdc:0x7fe0])
    changed=[i for i in range(len(source))if source[i]!=image[i]]
    allowed={i for p in [0x84e7,0x8714,0x85aa,0x8a4a,0x47ef,0x4f24,0x4da2]for i in range(p,p+5)}|set(range(0x4807,0x480b))|set(range(0x7fdc,0x7fe0))
    allowed.update(range(0x8000c,0x8000f))
    assert set(changed)<=allowed
    out=ROOT/'work/build'/tag;out.mkdir(parents=True,exist_ok=True);(out/'remix4-cn.sfc').write_bytes(image)
    manifest={'source_sha256':SOURCE_SHA,'sha256':hashlib.sha256(image).hexdigest(),'source_bytes_changed':changed,'nodes_relocated':len(encoded),'components':len(accepted),'waiting_components':len(waiting),'literal_spans_translated':len(used_spans),'literal_spans_total':len(graph['literal_spans']),'glyph_count':len(chars),'text_pool_end':cursor,'menu_literals':menu_records,'lookup':[{"source_cpu":s,"target_cpu":t}for s,t in sorted(lookup.items())],'redirects':[{"source_cpu":s,"target_cpu":t,"offset":locations[s],"hex":encoded[s].hex()}for s,t in sorted(relocation.items())],'encoder':{c:v.hex()for c,v in encoder.items()},'writes':writes,'labels':labels,'accepted_batches':batches,'font_sha256':hashlib.sha256(FONT_PATH.read_bytes()).hexdigest(),'graph_sha256':hashlib.sha256((ROOT/'work/text-graph/graph.json').read_bytes()).hexdigest(),'not_claimed':['whole-game translation','all root table lengths independently proved','all natural scenarios tested']}
    manifest['title']=title
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k]for k in ['sha256','nodes_relocated','components','waiting_components','literal_spans_translated','glyph_count','text_pool_end']}))
    return manifest

if __name__=='__main__':build(sys.argv[1]if len(sys.argv)>1 else 'graph-candidate-001')
