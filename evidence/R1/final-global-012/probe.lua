local out=assert(os.getenv('REMIX_OUT'))
local frame=0;local loaded=false;local saved=false
local log=assert(io.open(out..'/trace.log','w'))
local function shot()
 local name=string.format('frame-%05d',frame)
 local f=assert(io.open(out..'/'..name..'.png','wb'));f:write(emu.takeScreenshot());f:close()
 local values={};for a=0,131071 do values[#values+1]=string.char(emu.read(a,emu.memType.snesWorkRam))end
 f=assert(io.open(out..'/'..name..'.wram','wb'));f:write(table.concat(values));f:close()
end
emu.addMemoryCallback(function()
 if not loaded then
  local f=assert(io.open(assert(os.getenv('REMIX_STATE')),'rb'));local s=f:read('*a');f:close()
  assert(#s>1000 and emu.loadSavestate(s));loaded=true;frame=0;log:write('SAME_ROM_CHECKPOINT_LOADED\n');log:flush()
 elseif frame>=1101 and not saved then
  saved=true;local f=assert(io.open(out..'/menu.State','wb'));f:write(emu.createSavestate());f:close()
  log:write('DONE native input route checkpoint\n');log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x00804b,0x00804b,emu.cpuType.snes,emu.memType.snesMemory)
emu.addEventCallback(function()
 local keys={}
 if loaded then
  if frame>=200 and frame<208 or frame>=350 and frame<358 then keys.b=true end
  if frame>=500 and frame<508 then keys.down=true end
  if frame>=600 and frame<608 then keys.right=true end
  if frame>=750 and frame<758 then keys.a=true end
 end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 if loaded then
  frame=frame+1
  if frame==120 or frame==300 or frame==450 or frame==700 or frame==1000 then shot()end
  if frame>1300 then log:write('FAIL checkpoint callback not reached\n');log:close();emu.stop(1)end
 end
end,emu.eventType.endFrame)
