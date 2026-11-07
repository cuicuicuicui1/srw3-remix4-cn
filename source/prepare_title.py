"""Relocate one native compressed title graphic; preserve all other tiles."""
from pathlib import Path
import json,hashlib
from build import ROOT,SOURCE_SHA,FONT_PATH,bdf_font,glyph32

def decompress(data,limit=0x10000):
    p=0;bits=0;remaining=0;out=bytearray()
    def byte():
        nonlocal p
        assert p<len(data),'compressed input exhausted'
        value=data[p];p+=1;return value
    def bit():
        nonlocal bits,remaining
        if not remaining:bits=byte();remaining=8
        value=bits>>7;bits=(bits<<1)&255;remaining-=1;return value
    while True:
        if bit():out.append(byte())
        else:
            if bit():
                packed=(byte()<<8)|byte();distance=(packed>>3)|0xe000
                length=packed&7
                if length:length+=2
                else:
                    length=byte()
                    if not length:return bytes(out),p
                    length+=1
            else:
                length=((bit()<<1)|bit())+2;distance=0xff00|byte()
            distance-=0x10000
            for _ in range(length):
                index=len(out)+distance
                assert 0<=index<len(out),('invalid LZ reference',p,index,len(out))
                out.append(out[index])
        assert len(out)<=limit,'decompression overflow'

def literals(raw):
    assert len(raw)%8==0
    return b''.join(b'\xff'+raw[i:i+8]for i in range(0,len(raw),8))+b'\x40\x00\x00\x00'

def prepare():
    source=(ROOT/'inputs/remix4-original.sfc').read_bytes()
    assert hashlib.sha256(source).hexdigest()==SOURCE_SHA
    assert source[0x8000c:0x8000f]==bytes.fromhex('94ba21')
    raw,consumed=decompress(source[0x10ba94:])
    assert len(raw)==0x4000 and hashlib.sha256(raw).hexdigest()=='2a611b8caa1e2bddccded17dc595fc1fa44659de72b473641a47960b3b4aaa87',(len(raw),consumed)
    translated=json.loads((ROOT/'work/zcode-title/translations.json').read_text(encoding='utf-8-sig'))['entries']
    labels={x['id']:x for x in translated}
    assert set(labels)=={'start','continue','load'}
    font=bdf_font(FONT_PATH);edited=bytearray(raw);tile=bytearray(0x400)
    expected={'start':('START',0,40),'continue':('CONTINUE',40,56),'load':('LOAD',96,32)}
    for key,(english,origin,width)in expected.items():
        row=labels[key];assert row['source']==english
        text=row['translation'];assert text and len(text)*12<=width
        left=origin+(width-len(text)*12)//2
        for i,ch in enumerate(text):
            bitmap=glyph32(font[ch])
            for y in range(16):
                for x in range(12):
                    if bitmap[(0 if x<8 else 16)+y]&(0x80>>(x%8)):
                        xx=left+i*12+x
                        # SNES 4bpp, colour 1 preserves native selected/unselected palettes.
                        off=((y//8)*16+xx//8)*32+(y%8)*2
                        tile[off]|=0x80>>(xx%8)
    edited[0x1000:0x1400]=tile
    assert edited[:0x1000]==raw[:0x1000]and edited[0x1400:]==raw[0x1400:]
    packed=literals(edited);roundtrip,n=decompress(packed)
    assert roundtrip==edited and n==len(packed)
    out=ROOT/'work/title';out.mkdir(parents=True,exist_ok=True)
    (out/'graphics.bin').write_bytes(edited);(out/'graphics.lz').write_bytes(packed)
    result={'source_sha256':SOURCE_SHA,'source_pointer_offset':0x8000c,'source_pointer_hex':'94ba21','source_compressed_cpu':0x21ba94,'source_compressed_bytes':consumed,'native_source_pixels_sha256':hashlib.sha256(raw).hexdigest(),'expected_pixels_sha256':hashlib.sha256(edited).hexdigest(),'compressed_sha256':hashlib.sha256(packed).hexdigest(),'compressed_bytes':len(packed),'new_offset':0x1d0000,'new_cpu':0x3a8000,'changed_decompressed_range':[0x1000,0x1400],'entries':translated,'source_pixels_match_frozen_R1_identity':True}
    (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':prepare()
