"""Read actual final artifact; independently compare literal text and native edges."""
from pathlib import Path
import json,hashlib,sys
from build_graph import ROOT,translations,load_graph

def verify(tag):
    def cell_text(s):
        # The original single-byte font uses the same glyph for these width aliases.
        return ''.join(chr(ord(c)-0xfee0)if '\uff01'<=c<='\uff5e'else' 'if c=='\u3000'else c for c in s)
    d=ROOT/'work/build'/tag;rom=(d/'remix4-cn.sfc').read_bytes();m=json.loads((d/'manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(rom).hexdigest()==m['sha256']
    source=(ROOT/'inputs/remix4-original.sfc').read_bytes()
    allowed=set(range(0x7fdc,0x7fe0))|set(range(0x4807,0x480b))|{i for p in [0x84e7,0x8714,0x85aa,0x8a4a,0x47ef,0x4f24,0x4da2]for i in range(p,p+5)}
    changes={i for i in range(len(source))if source[i]!=rom[i]}
    allowed.update(range(0x8000c,0x8000f))
    assert changes<=allowed and sorted(changes)==m['source_bytes_changed']
    assert int.from_bytes(rom[0x7fdc:0x7fde],'little')^int.from_bytes(rom[0x7fde:0x7fe0],'little')==65535
    assert sum(rom)&65535==int.from_bytes(rom[0x7fde:0x7fe0],'little')
    graph=load_graph()
    accepted,_=translations(graph)
    nodes={x['source_cpu']:x for x in graph['nodes']};reloc={x['source_cpu']:x for x in m['redirects']}
    decoder={bytes.fromhex(v):c for c,v in m['encoder'].items()}
    checked_spans=0;checked_edges=0;control_count=0;visited=set()
    for addr,r in reloc.items():
        raw=rom[r['offset']:r['offset']+len(bytes.fromhex(r['hex']))]
        assert raw.hex()==r['hex']
        assert (r['target_cpu']&0x7fff)+len(raw)<=0x8000
        node=nodes[addr];spans={s['first_offset']:s for s in node.get('span_refs',[])}
        for token in node['tokens']:
            offset=(addr>>16)*0x8000+(token['offset']&0x7fff)
            original=bytes.fromhex(token['raw'])
            assert source[offset:offset+len(original)]==original,('source preimage',hex(addr),token['kind'])
        pos=0;skip=0
        for token in node['tokens']:
            if token['offset']<skip:continue
            span=spans.get(token['offset'])
            if span:
                letters=[];line_width=0
                while pos<len(raw):
                    b=raw[pos]
                    if b==0xf3:line_width=0;pos+=1;continue
                    if 0xe8<=b<=0xf2:
                        assert pos+1<len(raw)
                        letters.append(decoder[raw[pos:pos+2]]);pos+=2;line_width+=1
                        assert line_width<=16
                    elif bytes([b])in decoder:
                        letters.append(decoder[bytes([b])]);pos+=1;line_width+=1
                    else:break
                assert cell_text(''.join(letters))==cell_text(accepted[span['id']].replace('\n','')),(span['id'],''.join(letters))
                checked_spans+=1;visited.add(span['id']);skip=span['end_offset'];continue
            original=bytes.fromhex(token['raw']);actual=raw[pos:pos+len(original)]
            expect=bytearray(original)
            for edge in node['edges']:
                if edge['token_offset']==token['offset']:
                    target=reloc[edge['target']]['target_cpu']
                    assert target>>16==r['target_cpu']>>16
                    where=edge['operand_offset'];expect[where:where+2]=(target&65535).to_bytes(2,'little')
                    assert int.from_bytes(actual[where:where+2],'little')==target&65535
                    checked_edges+=1
            assert actual==expect,(hex(addr),token['kind'],pos)
            control_count+=1;pos+=len(original)
        if node['fallthrough']:
            target=reloc[node['fallthrough']]['target_cpu']
            assert raw[pos:pos+3]==b'\xf9'+(target&65535).to_bytes(2,'little')
            assert target>>16==r['target_cpu']>>16
            pos+=3;checked_edges+=1
        assert pos==len(raw),(hex(addr),pos,len(raw))
    assert len(visited)==m['literal_spans_translated']
    # Read binary lookup independently as an indexed table and reject stale or extra entries.
    base=0x1f8800
    lookup={r['source_cpu']:r['target_cpu']for r in m.get('lookup',m['redirects'])}
    for i,(src,target)in enumerate(sorted(lookup.items())):
        record=rom[base+i*6:base+(i+1)*6]
        assert int.from_bytes(record[:3],'little')==src
        assert int.from_bytes(record[3:6],'little')==target
    for row in m.get('menu_literals',[]):
        actual=rom[row['offset']:row['offset']+len(bytes.fromhex(row['hex']))];assert actual.hex()==row['hex']
        text=[];p=0
        while p<len(actual):
            code=actual[p]
            if code==0xf3:text.append('\n');p+=1
            elif code>=0xe8:text.append(decoder[actual[p:p+2]]);p+=2
            else:text.append(decoder[actual[p:p+1]]);p+=1
        assert cell_text(''.join(text))==cell_text(row['translation'])
        assert lookup[row['source_cpu']]==row['target_cpu']and lookup[row['target_end']]==row['end_cpu']
    result={'status':'pass','rom_sha256':m['sha256'],'source_changed_bytes':len(changes),'nodes':len(reloc),'menu_literals':len(m.get('menu_literals',[])),'literal_runs_checked':checked_spans,'distinct_literal_spans':len(visited),'control_tokens_checked':control_count,'branch_and_fallthrough_edges_checked':checked_edges,'source_text_font_event_data_unchanged':True,'claims':'static final-byte readback, native control operands except explicitly rebased same-bank edges, lookup identities and no cross-bank string; not gameplay proof'}
    (d/'graph-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    return result
if __name__=='__main__':verify(sys.argv[1])
