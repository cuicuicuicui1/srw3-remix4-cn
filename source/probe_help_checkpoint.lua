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

local function w(a)return emu.readWord(a,emu.memType.snesMemory)end
local seenGlyphs={};local extcount=0
local saved=false
emu.addMemoryCallback(function()
 if frame>=8999 and not saved then
 saved=true
 local f=assert(io.open(out..'/help-menu.State','wb'));f:write(emu.createSavestate());f:close()
 log:write('NATURAL_CHECKPOINT_SAVED\n');log:flush()
 end
end,emu.callbackType.exec,0x00804b,0x00804b,emu.cpuType.snes,emu.memType.snesMemory)
emu.addMemoryCallback(function()
 if frame>=8450 and frame<8800 then
 local z=emu.getState();local sp=z['cpu.sp']or 0;local stack={}
 for i=1,12 do stack[#stack+1]=string.format('%02X',emu.read(sp+i,emu.memType.snesMemory))end
 log:write(string.format('GLYPH frame=%d A=%04X font=%06X AD=%06X menu=%06X stack=%s\n',frame,z['cpu.a'],w(0xf4)|(emu.read(0xf6,emu.memType.snesMemory)<<16),w(0xad)|(emu.read(0xaf,emu.memType.snesMemory)<<16),w(0x1a)|(emu.read(0x1c,emu.memType.snesMemory)<<16),table.concat(stack)));log:flush()
 end
end,emu.callbackType.exec,0x00c90e,0x00c90e,emu.cpuType.snes,emu.memType.snesMemory)
emu.addMemoryCallback(function()
 local st=emu.getState();local ptr=w(0xf4)|(emu.read(0xf6,emu.memType.snesMemory)<<16)
 if ptr>=0x3c0000 and ptr<0x3e0000 then
  extcount=extcount+1
  if not seenGlyphs[st["cpu.a"]]then seenGlyphs[st["cpu.a"]]=true;log:write(string.format("CN_GLYPH frame=%d A=%04X source=%06X AD=%06X SP=%04X\n",frame,st["cpu.a"],ptr,w(0xad)|(emu.read(0xaf,emu.memType.snesMemory)<<16),st["cpu.sp"]or 0));log:flush()end
 end
end,emu.callbackType.exec,0x00c90e,0x00c90e,emu.cpuType.snes,emu.memType.snesMemory)

emu.addEventCallback(function()
 local keys={}
 if frame>=700 and frame<708 then keys.start=true end
 if frame>=950 and frame<958 then keys.a=true end
 if frame>=1500 and frame<7400 and frame%90<6 then keys.a=true end
 if frame>=8200 and frame<8250 then keys.b=true end
 if frame>=8400 and frame<8420 then keys.down=true end
 if frame>=8500 and frame<8520 then keys.right=true end
 if frame>=8700 and frame<8720 then keys.a=true end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if frame==500 or frame==900 or frame==1200 or frame==1800 or frame==2400 or frame==1850 or frame==2050 or frame==2600 or frame==3200 or frame==4500 or frame==6000 or frame==8000 or frame==9000 or frame==10000 or frame==11000 or frame==12000 or frame==14000 or frame==9100 then shot()end
 if frame>=9001 then log:write("DONE frames="..frame.." extended_glyphs="..extcount.."\n");log:close();emu.stop(0)end
end,emu.eventType.endFrame)
