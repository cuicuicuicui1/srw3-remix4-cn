local out=assert(os.getenv('REMIX_OUT'))
local frame=0;local loaded=false;local log=assert(io.open(out..'/trace.log','w'))
emu.addMemoryCallback(function()
 if not loaded then
  loaded=true
  local f=assert(io.open(assert(os.getenv('REMIX_SRAM')),'rb'));local s=f:read('*a');f:close();assert(#s==8192)
  -- Emulator SRAM hydration, before the native reset routine reads it.
  for a=0,8191 do emu.write(0x700000+a,s:byte(a+1),emu.memType.snesMemory)end
  log:write('SRAM_IMPORTED_BEFORE_RESET bytes=8192\n');log:flush()
 end
end,emu.callbackType.exec,0x008000,0x008000,emu.cpuType.snes,emu.memType.snesMemory)
local function shot()
 local tag=string.format('frame-%05d',frame)
 local f=assert(io.open(out..'/'..tag..'.png','wb'));f:write(emu.takeScreenshot());f:close()
 local b={};for a=0,131071 do b[#b+1]=string.char(emu.read(a,emu.memType.snesWorkRam))end
 f=assert(io.open(out..'/'..tag..'.wram','wb'));f:write(table.concat(b));f:close()
end
emu.addEventCallback(function()
 local keys={}
 if frame>=700 and frame<708 then keys.start=true end
 if os.getenv('REMIX_LOAD_KIND')=='load'and frame>=1000 and frame<1008 then keys.right=true end
 if frame>=1150 and frame<1158 then keys.a=true end
 if frame>=3000 and frame<3008 then keys.a=true end
 if frame>=3700 and frame<3708 then keys.b=true end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if frame==900 or frame==1100 or frame==1500 or frame==2500 or frame==3500 or frame==4500 then shot()end
 if frame>=4501 then assert(loaded);log:write('DONE native cold SRAM load route\n');log:close();emu.stop(0)end
end,emu.eventType.endFrame)
