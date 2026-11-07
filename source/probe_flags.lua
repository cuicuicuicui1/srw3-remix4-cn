local out=assert(os.getenv('REMIX_OUT'))
local cases=assert(loadfile(assert(os.getenv('REMIX_CASES'))))()
local m=emu.memType.snesMemory
local f=assert(io.open(out..'/trace.log','w'))
local function log(s)f:write(s..'\n');f:flush()end
local frame=0;local checkpoint=nil;local current=0;local active=false;local pending=false;local rel=0;local count=0
local visited={};local glyphs=0;local selected=0
local function read(a)return emu.read(0x7e0000+a,m)end
local function word(a)return read(a)|(read(a+1)<<8)end
local function ptr()return word(0xad)|(read(0xaf)<<16)end
local function write(a,v)emu.write(0x7e0000+a,v&255,m)end
local function writeword(a,v)write(a,v);write(a+1,v>>8)end
local function fail(s)
 local z=emu.getState();log(string.format('FAIL %s ptr=%06X PC=%02X:%04X flags=%04X',s,ptr(),z['cpu.k'],z['cpu.pc'],word(0xe34)))
 local zf=assert(io.open(out..'/failure.png','wb'));zf:write(emu.takeScreenshot());zf:close();emu.stop(1)
end
local function begin()
 current=current+1
 if current>#cases then log('DONE cases='..#cases);f:close();emu.stop(0);return end
 local c=cases[current];active=true;pending=false;rel=0;visited={};glyphs=0;selected=0
 writeword(0xad,c.input&65535);write(0xaf,c.input>>16)
 -- Only declared text argument and native condition bits change; no PC or completion writes.
 for addr=0x101b,0x109a do write(addr,0)end
 for cond,value in pairs(c.flags)do local p=0x101b+(cond>>3);local mask=0x80>>(cond&7);local v=read(p);write(p,value and(v|mask)or(v&(~mask)))end
 log(string.format('BEGIN case=%d kind=%s input=%06X expected=%06X choice=%d',current,c.kind,c.input,c.expected_end,c.choice))
end
emu.addMemoryCallback(function()
 if not checkpoint and frame>=1700 then
  checkpoint=emu.createSavestate();if not checkpoint or #checkpoint<1000 then fail('checkpoint');return end
  log('NATIVE_TEXT_CHECKPOINT bytes='..#checkpoint);begin()
 end
 if active and not pending then visited[ptr()]=true end
end,emu.callbackType.exec,0x0185a7,0x0185a7,emu.cpuType.snes,m)
emu.addMemoryCallback(function(address,value)
 if active and not pending then visited[address]=true end
end,emu.callbackType.read,0x308000,0x3bffff,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if pending then
  if not emu.loadSavestate(checkpoint)then fail('restore');return end
  begin()
 end
end,emu.callbackType.exec,0x00804b,0x00804b,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if active and not pending then
  local c=cases[current];local index=word(0x83)
  -- Native PRNG XOR inputs. The original AE06 modulo selector still executes.
  writeword(0x1f00+((index-0x6e)&0x7e),c.choice)
  writeword(0x1f00+((index-0x30)&0x7e),0)
  selected=selected+1
  log(string.format('SELECTOR case=%d choice=%d ptr=%06X',current,c.choice,ptr()))
 end
end,emu.callbackType.exec,0x01871f,0x01871f,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if active and not pending then glyphs=glyphs+1 end
end,emu.callbackType.exec,0x00c90e,0x00c90e,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if active and not pending and read(0xe2e)==0 then
  local c=cases[current]
  if ptr()~=c.expected_end then fail(string.format('case=%d actual=%06X expected=%06X',current,ptr(),c.expected_end));return end
  for _,address in ipairs(c.route)do if not visited[address]then fail(string.format('case=%d missing path=%06X',current,address));return end end
  if c.kind=='F7'and selected==0 then fail('selector not hit');return end
  log(string.format('PASS case=%d end=%06X glyphs=%d selectors=%d frames=%d',current,ptr(),glyphs,selected,rel))
  count=count+1;pending=true
 end
end,emu.callbackType.exec,0x0188a7,0x0188a7,emu.cpuType.snes,m)
emu.addMemoryCallback(function()
 if active and not pending then
 local st=emu.getState();local cond=st['cpu.a']&1023;log(string.format('FLAGCHECK case=%d cond=%d stored=%02X ptr=%06X',current,cond,read(0x101b+(cond>>3)),ptr()))
 end
end,emu.callbackType.exec,0x009f9c,0x009f9c,emu.cpuType.snes,m)
emu.addMemoryCallback(function(address,value)
 if active and not pending then local st=emu.getState();log(string.format('FLAGWRITE case=%d addr=%06X value=%02X PC=%02X:%04X',current,address,value,st['cpu.k'],st['cpu.pc']))end
end,emu.callbackType.write,0x00101c,0x00101c,emu.cpuType.snes,m)
emu.addEventCallback(function()
 local keys={}
 if frame>=700 and frame<708 then keys.start=true end
 if frame>=950 and frame<958 then keys.a=true end
 if active then if rel%8<4 then keys.a=true end
 elseif frame>=1500 and frame%90<6 then keys.a=true end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if active and not pending then rel=rel+1;if rel>3600 then fail('case timeout '..current)end end
 if frame>tonumber(os.getenv('REMIX_MAX_FRAMES')or'120000')then fail('global timeout')end
end,emu.eventType.endFrame)
