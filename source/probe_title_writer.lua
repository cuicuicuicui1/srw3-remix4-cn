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

local writes={}
emu.addMemoryCallback(function(address,value)
 local st=emu.getState();local pc=st['cpu.k']*65536+st['cpu.pc']
 if frame<300 or writes[pc]then return end;writes[pc]=true
 local bytes={};for x=0,0x3f do bytes[#bytes+1]=string.format('%02X',emu.read(x,emu.memType.snesMemory))end
 log:write(string.format('FONTWRITE frame=%d addr=%06X value=%02X PC=%06X A=%04X X=%04X Y=%04X dp=%s\n',frame,address,value,pc,st['cpu.a'],st['cpu.x'],st['cpu.y'],table.concat(bytes)));log:flush()
end,emu.callbackType.write,0x7f3000,0x7f33ff,emu.cpuType.snes,emu.memType.snesMemory)

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
