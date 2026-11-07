"""Execute actual hook bytes in the existing 65816 model; scoped ABI proof."""
from pathlib import Path
import importlib.util,json,sys,hashlib,random
ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'source/vendor/sim65816.py'
spec=importlib.util.spec_from_file_location('existing_65816',MODEL)
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
OriginalCPU=model.CPU
class CPU(OriginalCPU):
    def step(self):
        opcode=self.bus.rd(self.pbr,self.pc)
        if opcode in [0x50,0x70]:
            self.fetch();distance=self.fetch()
            if distance>=128:distance-=256
            if self.v==(opcode==0x70):self.pc=(self.pc+distance)&65535
        elif opcode==0x24:
            self.fetch();address=(self.d+self.fetch())&65535
            value=self.bus.rd(0,address)
            if not self.m8:value|=self.bus.rd(0,(address+1)&65535)<<8
            self.z=(self.a&value&(255 if self.m8 else 65535))==0
            self.n=bool(value&(0x80 if self.m8 else 0x8000))
            self.v=bool(value&(0x40 if self.m8 else 0x4000))
        else:super().step()
model.CPU=CPU

def run(tag):
    out=ROOT/'work/build'/tag;rom=(out/'remix4-cn.sfc').read_bytes();manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    redirects={r['source_cpu']:r['target_cpu']for r in manifest.get('lookup',manifest['redirects'])}
    rng=random.Random(0x3e41);passed=0;maxsteps=0
    def execute(c,stops):
        for n in range(3000):
            if (c.pbr<<16|c.pc)in stops:return n
            c.step()
        raise AssertionError('Hook did not exit within bound')
    def word(c,off):return c.bus.wram[off]|c.bus.wram[off+1]<<8
    def setword(c,off,v):c.bus.wram[off:off+2]=v.to_bytes(2,'little')
    for label,end,ptr in [('root',0x0184ec,0xad),('call',0x01858d,0xad),('menu-root',0x00c7f4,0x1a),('menu-call',0x00c804,0x1a)]:
        probes=list(redirects)+[0x078001,0x08ffff,0x09ffff,0x0affff,0x0bffff,0x0cffff,0x2fffff]
        for address in probes:
            c=model.CPU(rom);c.pbr=manifest['labels'][label]>>16;c.pc=manifest['labels'][label]&65535
            c.m8=c.x8=False;c.x=rng.randrange(65536);c.y=rng.randrange(65536);c.s=0x1dc;c.a=address&65535
            c.c=bool(rng.getrandbits(1));c.v=bool(rng.getrandbits(1));c.i=bool(rng.getrandbits(1))
            values=[rng.randrange(65536)for _ in range(4)]
            for off,val in zip([0,2,4,6],values):setword(c,off,val)
            c.bus.wram[ptr+2]=address>>16;old=(c.x,c.y,c.s,c.c,c.v,c.i)
            steps=execute(c,{end});maxsteps=max(maxsteps,steps)
            expected=redirects.get(address,address)
            assert word(c,ptr)|c.bus.wram[ptr+2]<<16==expected
            assert (c.x,c.y,c.s,c.c,c.v,c.i)==old
            assert [word(c,o)for o in [0,2,4,6]]==values
            assert not c.m8 and not c.x8
            assert c.a==(255 if label=='root'else 0x8000 if label=='menu-root'else address&65535)
            passed+=1
    # The menu getter must both enter overlays and resume native code at their end.
    for address in list(redirects)[::7]+[0x078001,0x7e1234]:
        c=model.CPU(rom);c.pbr=0x3f;c.pc=manifest['labels']['menu-getter']&65535
        c.m8=c.x8=False;c.a=0x55aa;c.x=0x1234;c.y=0x4567;c.s=0x1dc
        setword(c,0x1a,address&65535);c.bus.wram[0x1c]=address>>16
        for off,val in zip([0,2,4,6],[0xbeef,0x1234,0x5678,0x9abc]):setword(c,off,val)
        target=redirects.get(address,address)
        expected=c.bus.rd(target>>16,target&65535)|c.bus.rd(target>>16,(target+1)&65535)<<8
        execute(c,{0x00cda7})
        assert (word(c,0x1a)|c.bus.wram[0x1c]<<16)==target
        assert (c.a,c.x,c.y,c.s)==(expected,0x1234,0,0x1dc)
        assert [word(c,o)for o in [0,2,4,6]]==[0xbeef,0x1234,0x5678,0x9abc]
        passed+=1
    for bank in [8,9,0x30,0x3b,0x3c]:
        for prefix in [0x40,0xe7,0xe8,0xeb,0xef,0xf0,0xf2,0xf3,0xff]:
            for highmode in [False,True]:
                c=model.CPU(rom);c.pbr=manifest['labels']['font']>>16;c.pc=manifest['labels']['font']&65535
                c.m8=c.x8=False;c.a=prefix;c.x=0x517f;c.y=0x1234;c.s=0x1d0;c.c=True;c.v=True;c.i=False
                c.bus.wram[0xaf]=bank;setword(c,0xe1a,0x8000 if highmode else 0)
                steps=execute(c,{0x0185af,0x0185e8});active=0x30<=bank<0x3c and 0xe8<=prefix<0xf3
                assert (c.x,c.y,c.s,c.v,c.i)==(0x517f,0x1234,0x1d0,True,False)
                assert c.a==(0xf0 if active else prefix)
                assert c.pbr==1 and c.pc==(0x85e8 if prefix>=0xf3 else 0x85af)
                for operand in [0,0x7f,0x80,0xff]:
                    if not active:continue
                    page=prefix-0xe8
                    # Directly use native instruction formulas, not builder's base expression.
                    internal=0x0100+operand
                    y=((internal<<5)-(0x1000 if highmode else 0x2000))&65535
                    for off,lane in [(0xf4,0),(0xf7,8),(0xfa,16),(0xfd,24)]:
                        pointer=word(c,off)|c.bus.wram[off+2]<<16
                        actual=(pointer+y)&0xffffff
                        expected=((0x3c+page//4)<<16)|0x8000|(page%4*0x2000+operand*32+lane)
                        assert actual==expected,(hex(prefix),highmode,hex(actual),hex(expected))
                passed+=1
    for bank in [8,0x30,0x3b,0x3c]:
        for prefix in [0x40,0xe7,0xe8,0xeb,0xef,0xf0,0xf2,0xf3,0xff]:
            for mode in [0,0x4000,0x8000,0xc000]:
                c=model.CPU(rom);c.pbr=0x3f;c.pc=manifest['labels']['menu-font']&65535
                c.m8=c.x8=False;c.a=prefix;c.x=0x517f;c.y=0x1234;c.s=0x1d0
                c.bus.wram[0x1c]=bank;setword(c,0x2a,mode);setword(c,0xe1a,0x8000)
                execute(c,{0x00c832,0x00c877,0x00c80b,0x00c828})
                translated=0x30<=bank<0x3c
                active=translated and 0xe8<=prefix<0xf3
                endpoint=0xc832 if active else 0xc877 if translated and prefix<0xe8 else 0xc828 if mode&0x4000 else 0xc80b
                assert (c.pbr,c.pc,c.x,c.y,c.s)==(0,endpoint,0x517f,0x1234,0x1d0)
                assert c.a==(0xf0 if active else prefix)
                passed+=1
    result={'status':'pass','model_scope':'actual 65816 hook instructions; M/X=16 native ABI; existing model plus local BIT dp implementation; not PPU timing or natural gameplay proof','cases':passed,'max_root_hook_instructions':maxsteps,'rom_sha256':hashlib.sha256(rom).hexdigest(),'model_sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest()}
    (out/'hook-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':run(sys.argv[1])
