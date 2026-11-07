from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OPS={0x20:("JSR",2),0x22:("JSL",3),0x4c:("JMP",2),0x5c:("JML",3),0xdc:("JML[]",2),0x6c:("JMP()",2),0x7c:("JMP(x)",2),0xfc:("JSR(x)",2),0x60:("RTS",0),0x6b:("RTL",0),0xea:("NOP",0),0xc2:("REP",1),0xe2:("SEP",1),0xa9:("LDA#","m"),0xc9:("CMP#","m"),0x29:("AND#","m"),0x09:("ORA#","m"),0x49:("EOR#","m"),0x69:("ADC#","m"),0xe9:("SBC#","m"),0xa2:("LDX#","x"),0xa0:("LDY#","x"),0xc0:("CPY#","x"),0xe0:("CPX#","x"),0x89:("BIT#","m"),0xa5:("LDA dp",1),0x85:("STA dp",1),0xa6:("LDX dp",1),0x86:("STX dp",1),0xa4:("LDY dp",1),0x84:("STY dp",1),0xb7:("LDA [dp],Y",1),0x97:("STA [dp],Y",1),0x87:("STA [dp]",1),0x77:("ADC [dp],Y",1),0x07:("ORA [dp]",1),0xbf:("LDA long,X",3),0xaf:("LDA long",3),0x9f:("STA long,X",3),0x8f:("STA long",3),0x1f:("ORA long,X",3),0x3f:("AND long,X",3),0x9d:("STA abs,X",2),0xbd:("LDA abs,X",2),0xb9:("LDA abs,Y",2),0x99:("STA abs,Y",2),0xad:("LDA abs",2),0x8d:("STA abs",2),0xae:("LDX abs",2),0xac:("LDY abs",2),0x6d:("ADC abs",2),0xed:("SBC abs",2),0xcd:("CMP abs",2),0x2c:("BIT abs",2),0x24:("BIT dp",1),0x04:("TSB dp",1),0x14:("TRB dp",1),0x0c:("TSB abs",2),0x1c:("TRB abs",2),0x65:("ADC dp",1),0xe5:("SBC dp",1),0x05:("ORA dp",1),0x25:("AND dp",1),0x45:("EOR dp",1),0x46:("LSR dp",1),0x64:("STZ dp",1),0x9c:("STZ abs",2),0x9e:("STZ abs,X",2),0xc6:("DEC dp",1),0xe6:("INC dp",1),0xce:("DEC abs",2),0xee:("INC abs",2),0xde:("DEC abs,X",2),0xfe:("INC abs,X",2),0x1a:("INC A",0),0x3a:("DEC A",0),0x0a:("ASL A",0),0x4a:("LSR A",0),0x6a:("ROR A",0),0x2a:("ROL A",0),0x18:("CLC",0),0x38:("SEC",0),0x48:("PHA",0),0x68:("PLA",0),0x08:("PHP",0),0x28:("PLP",0),0xda:("PHX",0),0xfa:("PLX",0),0x5a:("PHY",0),0x7a:("PLY",0),0x8b:("PHB",0),0xab:("PLB",0),0xeb:("XBA",0),0xaa:("TAX",0),0xa8:("TAY",0),0x8a:("TXA",0),0x98:("TYA",0),0xbb:("TYX",0),0x9b:("TXY",0),0xc8:("INY",0),0x88:("DEY",0),0xe8:("INX",0),0xca:("DEX",0),0xc5:("CMP dp",1),0xe4:("CPX dp",1)}
for op,name in [(0x80,"BRA"),(0xf0,"BEQ"),(0xd0,"BNE"),(0x10,"BPL"),(0x30,"BMI"),(0x90,"BCC"),(0xb0,"BCS"),(0x50,"BVC"),(0x70,"BVS")]:OPS[op]=(name,"rel")
def dis(start,end,m8=False,x8=False):
 b=(ROOT/"inputs/remix4-original.sfc").read_bytes();p=start
 while p<end:
  op=b[p];name,n=OPS.get(op,("DB",0));n=(1 if m8 else 2)if n=="m"else(1 if x8 else 2)if n=="x"else n
  rel=n=="rel";n=1 if rel else n
  data=b[p+1:p+n+1];v=int.from_bytes(data,"little")
  operand=(f" ->{((p//32768)*65536+(p%32768)+32768+n+1+int.from_bytes(data,'little',signed=True))&65535:04X}" if rel else f" ${v:0{n*2}X}")if n else ""
  yield f"{((p//32768)<<16)|(p%32768+32768):06X} {b[p:p+n+1].hex(' '):12} {name}{operand}"
  if op in (0xc2,0xe2):
   if v&32:m8=op==0xe2
   if v&16:x8=op==0xe2
  p+=n+1
if __name__=="__main__":
 import sys
 print("\n".join(dis(int(sys.argv[1],16),int(sys.argv[2],16))))
