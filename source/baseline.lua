local out=assert(os.getenv("REMIX_OUT"))
local frame=0
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
 if frame==500 or frame==900 or frame==1200 or frame==1800 or frame==2400 or frame==3200 then shot()end
 if frame>=3200 then log:write("DONE frames="..frame.."\n");log:close();emu.stop(0)end
end,emu.eventType.endFrame)
