local out=assert(os.getenv("REMIX_OUT"))
local frame=0
local dumped=false
local log=assert(io.open(out.."/trace.log","w"))
local function dump(name,kind,size)
 local t={};for i=0,size-1 do t[#t+1]=string.char(emu.read(i,kind)&255)end
 local f=assert(io.open(out.."/"..name,"wb"));f:write(table.concat(t));f:close()
end
local function shot()
 local tag=string.format("frame-%05d",frame)
 local f=assert(io.open(out.."/"..tag..".png","wb"));f:write(emu.takeScreenshot());f:close()
 dump(tag..".vram",emu.memType.snesVideoRam,65536)
 dump(tag..".wram",emu.memType.snesWorkRam,131072)
 local st=emu.getState();log:write(tag.." PC="..tostring(st["cpu.k"])..":"..tostring(st["cpu.pc"]).."\n");log:flush()
end

emu.addMemoryCallback(function(address,value)
 if frame>950 then return end
 local st=emu.getState();local dst=st['ppu.vramAddress']
 for c=0,7 do if(value&(1<<c))~=0 then
  local base=0x4300+c*16;local mt=emu.memType.snesMemory
  local mode=emu.read(base,mt);local port=emu.read(base+1,mt);local src=emu.readWord(base+2,mt)|(emu.read(base+4,mt)<<16);local size=emu.readWord(base+5,mt)
  if port==0x18 or port==0x19 then log:write(string.format('DMA frame=%d PC=%02X:%04X vram=%04X src=%06X size=%04X mode=%02X\n',frame,st['cpu.k'],st['cpu.pc'],dst,src,size,mode));log:flush()end
 end end
end,emu.callbackType.write,0x00420b,0x00420b,emu.cpuType.snes,emu.memType.snesMemory)

emu.addEventCallback(function()
 local keys={}
 if frame>=700 and frame<708 then keys.start=true end
 if frame>=950 and frame<958 then keys.a=true end
 if frame>=1500 and frame%90<6 then keys.a=true end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if frame==900 then
 shot();local st=emu.getState();local f=assert(io.open(out.."/ppu.txt","w"));for k,v in pairs(st)do if k:find("ppu")then f:write(k.."="..tostring(v).."\n")end end;f:close()
 local f=assert(io.open(out.."/cgram.bin","wb"));local d={};for a=0,511 do d[#d+1]=string.char(emu.read(a,emu.memType.snesCgRam))end;f:write(table.concat(d));f:close()
 end
 if frame>=901 then log:write("DONE frames="..frame.."\n");log:close();emu.stop(0)end
end,emu.eventType.endFrame)
