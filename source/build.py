"""Guarded SRW3 ReMix4 Chinese text overlay. Original resources remain intact."""
from pathlib import Path
import hashlib, json, textwrap, sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'edcffa7b6aa734735b64f7674f02e2cf4e24a7a499cfd24675ad34c86218fe8f'
FONT_PATH = ROOT / 'inputs/fonts/fusion-pixel-12px-zh_hans.bdf'
CODE_PC = 0x3F8000

class Asm:
    def __init__(self, base): self.base=base; self.data=bytearray(); self.labels={}; self.fixups=[]
    @property
    def pc(self): return self.base+len(self.data)
    def emit(self,*values): self.data.extend(values); return self
    def word(self,op,value): return self.emit(op,value&255,(value>>8)&255)
    def long(self,op,value): return self.emit(op,value&255,(value>>8)&255,(value>>16)&255)
    def label(self,name):
        assert name not in self.labels
        self.labels[name]=self.pc
    def jump(self,name):
        self.fixups.append((len(self.data)+1,name)); self.long(0x5c,0)
    def cond(self,opcode,name):
        # Opposite condition skips a JML, so targets need not fit a signed byte.
        self.emit(opcode^0x20,4); self.jump(name)
    def finish(self):
        for offset,label in self.fixups:
            self.data[offset:offset+3]=self.labels[label].to_bytes(3,'little')
        return bytes(self.data)

def bdf_font(path):
    result={}; code=None; bbx=None; bitmap=None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('STARTCHAR'): code=None; bbx=None; bitmap=None
        elif line.startswith('ENCODING '): code=int(line.split()[1])
        elif line.startswith('BBX '): bbx=list(map(int,line.split()[1:]))
        elif line=='BITMAP': bitmap=[]
        elif line=='ENDCHAR':
            if code is not None and code>=0 and bbx is not None and bitmap is not None:
                result[chr(code)]=(bbx,bitmap)
            bitmap=None
        elif bitmap is not None: bitmap.append(int(line,16))
    return result

def glyph32(item):
    (w,h,xoff,yoff),rows=item
    result=bytearray(32)
    # BDF ascent 10, source engine's 16-row design box starts two rows lower.
    top=2+10-(h+yoff)
    for y,row in enumerate(rows):
        yy=top+y
        if not 0<=yy<16: continue
        for x in range(w):
            xx=x+xoff
            if 0<=xx<12 and row & (1<<(((w+7)//8)*8-1-x)):
                result[(0 if xx<8 else 16)+yy] |= 0x80>>(xx%8)
    return bytes(result)
