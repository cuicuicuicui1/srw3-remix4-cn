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
 shot();dump("title.oam",emu.memType.snesSpriteRam,544);local st=emu.getState();local f=assert(io.open(out.."/ppu.txt","w"));for k,v in pairs(st)do if k:find("ppu")then f:write(k.."="..tostring(v).."\n")end end;f:close()
 local f=assert(io.open(out.."/cgram.bin","wb"));local d={};for a=0,511 do d[#d+1]=string.char(emu.read(a,emu.memType.snesCgRam))end;f:write(table.concat(d));f:close()
 end
 if frame>=901 then log:write("DONE frames="..frame.."\n");log:close();emu.stop(0)end
end,emu.eventType.endFrame)
