"""Collect complete native text graphs; expose only literal runs to translators."""
from pathlib import Path
import sys,json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source/vendor'))
from native_parser import Rom,GlyphMap,Parser,file_offset

def prepare(destination):
    rom=Rom(ROOT/'inputs/remix4-original.sfc');glyphs=GlyphMap(ROOT/'source/japanese-map.json')
    audit=ROOT/'work/zcode-control-audit/out'
    records=[json.loads(x)for x in (audit/'spans.jsonl').read_text(encoding='utf-8').splitlines()]
    roots={};todo=[]
    for r in records:
        address=(r['bank']<<16)|r['start']
        roots.setdefault(address,[]).append(r['id'])
        for alias in r.get('aliases',[]):roots[address].append(f'g{alias["group"]:02d}/e{alias["entry"]:03d}')
        todo.append(address)
    coverage_path=ROOT/'work/zcode-coverage/evidence.json'
    if coverage_path.exists():
        coverage=json.loads(coverage_path.read_text(encoding='utf-8'))
        for item in coverage['findings']['main_text_unreferenced_literals']['entries']:
            address=int(item['source_cpu'].replace(':',''),16)
            roots.setdefault(address,[]).append('unreferenced-literal-'+item['source_cpu'])
            todo.append(address)
    nodes={};unknown=[]
    while todo:
        address=todo.pop()
        if address in nodes:continue
        bank=address>>16;start=address&65535
        if bank>=len(rom.data)//0x8000 or start<0x8000:
            unknown.append({'address':address,'reason':'target outside source ROM'});continue
        result=Parser(rom,glyphs,bank,start).parse()
        expected=start
        for token in result.tokens:
            assert token.offset==expected,('Noncontiguous source block',hex(address),hex(token.offset),hex(expected))
            expected+=len(token.raw)
        assert expected==result.stop_offset
        if result.stop_reason=='absolute_jump_F9':assert result.tokens[-1].kind=='F9'
        tokens=[];edges=[]
        for t in result.tokens:
            assert rom.data[file_offset(bank,t.offset):file_offset(bank,t.offset)+len(t.raw)]==t.raw
            item={'offset':t.offset,'kind':t.kind,'raw':t.raw.hex(),'text':t.text,'params':t.params}
            targets=[]
            if t.kind=='F7':targets=[(2+2*i,target)for i,target in enumerate(t.params['targets'])]
            elif t.kind=='F8'and 'target'in t.params:targets=[(2,t.params['target'])]
            elif t.kind=='F9'and 'target'in t.params:
                targets=[(1 if t.params['form']=='absolute_jump'else 3,t.params['target'])]
            for operand_offset,target in targets:
                edge={'token_offset':t.offset,'operand_offset':operand_offset,'target':(bank<<16)|target}
                edges.append(edge);todo.append(edge['target'])
            tokens.append(item)
        fallthrough=None
        if result.stop_reason.startswith('conditional_branch_'):
            fallthrough=(bank<<16)|result.stop_offset;todo.append(fallthrough)
        accepted=result.complete or result.stop_reason in ['random_branch_F7','absolute_jump_F9'] or result.stop_reason.startswith('conditional_branch_')
        node={'source_cpu':address,'source_offset':file_offset(bank,start),'stop':result.stop_reason,'complete_block':accepted,'tokens':tokens,'edges':edges,'fallthrough':fallthrough,'root_ids':roots.get(address,[]),'unknown_glyphs':result.unknown_glyphs}
        nodes[address]=node
        if not accepted:unknown.append({'address':address,'reason':result.stop_reason})
    # Reject edges landing inside an operand or glyph; never silently round a target.
    roles=collections.defaultdict(set)
    for node in nodes.values():
        bank=node['source_cpu']>>16
        for t in node['tokens']:
            for i in range(1,len(bytes.fromhex(t['raw']))):roles[(bank<<16)|t['offset']+i].add(t['kind'])
    invalid_anchors=[]
    for address in nodes:
        if address in roles:invalid_anchors.append({'address':address,'inside':sorted(roles[address])})
    # Literal spans retain host and adjacent control context, while translators cannot edit bytecode.
    spans={}
    for node in nodes.values():
        run=[]
        def flush():
            if not run:return
            if not any(t['kind']=='glyph'for t in run):run.clear();return
            bank=node['source_cpu']>>16;start=run[0]['offset'];end=run[-1]['offset']+len(bytes.fromhex(run[-1]['raw']))
            raw=b''.join(bytes.fromhex(t['raw'])for t in run)
            sid=f'{bank:02X}-{start:04X}-{end:04X}'
            text=''.join('\n'if t['kind']=='F3'else t['text']for t in run)
            if sid not in spans:spans[sid]={'id':sid,'source_cpu':(bank<<16)|start,'japanese':text,'source_hex':raw.hex(),'source_sha256':hashlib.sha256(raw).hexdigest(),'hosts':[],'translation':''}
            spans[sid]['hosts'].append(node['source_cpu'])
            node.setdefault('span_refs',[]).append({'id':sid,'first_offset':start,'end_offset':end})
            run.clear()
        for t in node['tokens']:
            if t['kind']in ['glyph','F3']:run.append(t)
            else:flush()
        flush()
    # Seed accepted source-identical translations from earlier ZCode batches only.
    reuse={}
    for source_path,translation_path,key in [
        (ROOT/'work/translation-batch-001.json',ROOT/'work/zcode-translation-001/translations.json','entries'),
        (ROOT/'work/intro-contract.json',ROOT/'work/zcode-intro/translations.json','spans')]:
        if not translation_path.exists():continue
        source=json.loads(source_path.read_text(encoding='utf-8'))[key]
        translated=json.loads(translation_path.read_text(encoding='utf-8-sig'))['entries']
        orig={x['id']:x for x in source}
        assert set(orig)=={x['id']for x in translated}
        for row in translated:
            assert row['japanese']==orig[row['id']]['japanese']
            for field in ['original_hex','raw_hex']:
                if field in orig[row['id']]:
                    raw=bytes.fromhex(orig[row['id']][field])
                    if raw.endswith(b'\xff'):raw=raw[:-1]
                    reuse[(raw.hex(),row['japanese'])]=row['translation']
    for span in spans.values():
        value=reuse.get((span['source_hex'],span['japanese']))
        if value:span['translation']=value;span['translation_origin']='previous validated ZCode batch'
    output=Path(destination).resolve();output.mkdir(parents=True,exist_ok=False)
    graph={'source_sha256':hashlib.sha256(rom.data).hexdigest(),'nodes':list(nodes.values()),'literal_spans':list(spans.values()),'unknown_nodes':unknown,'invalid_anchors':invalid_anchors,'root_count':len(roots),'table_scope':'provisional audited root set, plus recursively discovered native branch targets; table length is not independently proven'}
    (output/'graph.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
    pending=[x for x in spans.values()if not x['translation']]
    print(json.dumps({'nodes':len(nodes),'roots':len(roots),'literal_spans':len(spans),'seeded_translations':len(spans)-len(pending),'pending':len(pending),'pending_japanese_characters':sum(len(x['japanese'])for x in pending),'unknown_nodes':len(unknown),'invalid_anchors':len(invalid_anchors),'unknown_source_glyph_markers':sum('<U_'in x['japanese']for x in pending)},ensure_ascii=False))
    return graph

if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser(description='Extract the pinned Japanese hack into a NEW output directory.')
    cli.add_argument('--output',required=True)
    prepare(cli.parse_args().output)
