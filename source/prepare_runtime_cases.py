"""Independent source-graph expectations for native chooser/conditional probes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def prepare(tag):
    graph=json.loads((ROOT/'work/text-graph/graph.json').read_text(encoding='utf-8'))
    nodes={n['source_cpu']:n for n in graph['nodes']}
    m=json.loads((ROOT/'work/build'/tag/'manifest.json').read_text(encoding='utf-8'))
    reloc={r['source_cpu']:r for r in m['redirects']};cases=[]
    source=(ROOT/'inputs/remix4-original.sfc').read_bytes()
    def path(start,choice,flags,f8=False):
        flags=dict(flags);seen=set();p=start;route=[]
        while p not in seen:
            seen.add(p);n=nodes[p];route.append(p)
            if p not in reloc:return None
            if any(t['kind']in ['F6']for t in n['tokens']):return None
            for token in n['tokens']:
                if token['kind']=='FB'and token['params']['sub']<=7:
                    flags[token['params']['condition']]=token['params']['sub']>=4
            if n['stop']=='FF_end':
                q=reloc[p]
                # Final FF is a native token after all glyph operands, verified by static pass.
                return route,q['target_cpu']+len(bytes.fromhex(q['hex']))
            if n['stop']=='random_branch_F7':
                targets=n['tokens'][-1]['params']['targets']
                p=(p&0xff0000)|targets[choice%len(targets)]
            elif n['stop']=='absolute_jump_F9':p=n['edges'][0]['target']
            elif n['stop'].startswith('conditional_branch_F9'):
                args=n['tokens'][-1]['params'];bit=flags.get(args['condition'],False)
                take=bit if args['sub']>=4 else not bit
                p=n['edges'][0]['target']if take else n['fallthrough']
            elif n['stop'].startswith('conditional_branch_F8'):
                p=n['edges'][0]['target']if f8 else n['fallthrough']
            else:return None
        return None
    for addr,n in sorted(nodes.items()):
        if addr not in reloc:continue
        if n['stop']=='random_branch_F7':
            for choice in range(len(n['edges'])):
                result=path(addr,choice,{})
                if result:
                    route,end=result
                    # Isolate chooser from battle-only dynamic name macros in the prelude.
                    # F7 is terminal in this basic block and has a proven operand length.
                    control_length=len(bytes.fromhex(n['tokens'][-1]['raw']))
                    input_address=reloc[addr]['target_cpu']+len(bytes.fromhex(reloc[addr]['hex']))-control_length
                    cases.append({'kind':'F7','source':addr,'input':input_address,'choice':choice,'flags':{},'expected_end':end,'expected_route':[input_address]+[reloc[q]['target_cpu']for q in route[1:]]})
        elif n['stop'].startswith('conditional_branch_F9'):
            cond=n['tokens'][-1]['params']['condition']
            for flag in [False,True]:
                result=path(addr,0,{cond:flag})
                if result:
                    route,end=result;cases.append({'kind':'F9','source':addr,'input':reloc[addr]['target_cpu'],'choice':0,'flags':{str(cond):flag},'expected_end':end,'expected_route':[reloc[q]['target_cpu']for q in route]})
        elif n['stop'].startswith('conditional_branch_F8'):
            units={}
            for unit in range(256):
                ptr=int.from_bytes(source[0x20000+unit*2:0x20002+unit*2],'little')
                if ptr<0x8000:continue
                off=0x20000+(ptr&0x7fff)
                units.setdefault(bool(source[off+2]&0x80),unit)
            assert set(units)=={False,True}
            for take in [False,True]:
                result=path(addr,0,{},take);assert result
                route,end=result
                cases.append({'kind':'F8','source':addr,'input':reloc[addr]['target_cpu'],'choice':0,'flags':{},'fields':{0x0f1e:0,0x0f23:0,0x0f24:0,0xe7:0,0x1586:units[take]},'expected_end':end,'expected_route':[reloc[q]['target_cpu']for q in route]})
    for addr,n in sorted(nodes.items()):
        calls=[t for t in n['tokens']if t['kind']=='F6']
        if not calls or n['stop']!='FF_end':continue
        route=[reloc[addr]['target_cpu']]
        for t in calls:
            e,g=t['params']['entry'],t['params']['group'];assert 255 not in [e,g]
            tab=int.from_bytes(source[0x5277+g*3:0x527a+g*3],'little')
            off=(tab>>16)*0x8000+(tab&0x7fff)+e*2
            target=tab&0xff0000|int.from_bytes(source[off:off+2],'little')
            assert target in nodes and nodes[target]['stop']=='FF_end'
            route.append(reloc[target]['target_cpu'])
        q=reloc[addr]
        cases.append({'kind':'CALL','source':addr,'input':q['target_cpu'],'choice':0,'flags':{},'expected_end':q['target_cpu']+len(bytes.fromhex(q['hex'])),'expected_route':route})
    long=sorted((n for n in nodes.values()if n['stop']=='FF_end'and not any(t['kind']in ['F6','F8','FE']for t in n['tokens'])),key=lambda n:sum(len(t['text'])for t in n['tokens']),reverse=True)[:3]
    for n in long:
        q=reloc[n['source_cpu']]
        cases.append({'kind':'LONG','source':n['source_cpu'],'input':q['target_cpu'],'choice':0,'flags':{},'expected_end':q['target_cpu']+len(bytes.fromhex(q['hex'])),'expected_route':[q['target_cpu']]})
    for n in nodes.values():
        if any(x.startswith('unreferenced-literal-')for x in n.get('root_ids',[])):
            assert n['stop']=='FF_end'
            q=reloc[n['source_cpu']]
            cases.append({'kind':'ORPHAN','source':n['source_cpu'],'input':q['target_cpu'],'choice':0,'flags':{},'expected_end':q['target_cpu']+len(bytes.fromhex(q['hex'])),'expected_route':[q['target_cpu']]})
    # A bounded smoke subset first; full list retained for final run.
    destination=ROOT/'work/runtime-cases';destination.mkdir(exist_ok=True)
    for name,rows in [('all',cases),('smoke',cases[:8]+[x for x in cases if x['kind']=='F9'][:4])]:
        lines=['return {']
        for i,x in enumerate(rows,1):
            flags='{'+','.join(f'[{k}]={str(v).lower()}'for k,v in x['flags'].items())+'}'
            route='{'+','.join(str(q)for q in x['expected_route'])+'}'
            fields='{'+','.join(f'[{k}]={v}'for k,v in x.get('fields',{}).items())+'}'
            lines.append(f'{{id={i},kind="{x["kind"]}",source={x["source"]},input={x["input"]},choice={x["choice"]},expected_end={x["expected_end"]},flags={flags},route={route},fields={fields}}},')
        lines.append('}')
        (destination/f'{tag}-{name}.lua').write_text('\n'.join(lines),encoding='utf-8')
    (destination/f'{tag}.json').write_text(json.dumps({'rom_sha256':m['sha256'],'cases':cases},indent=2),encoding='utf-8')
    print('cases',len(cases),'F7',sum(x['kind']=='F7'for x in cases),'F9',sum(x['kind']=='F9'for x in cases))
if __name__=='__main__':prepare(sys.argv[1])
