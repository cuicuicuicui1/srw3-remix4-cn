from pathlib import Path
import os,sys,subprocess,hashlib,json,time,shutil,re
ROOT=Path(__file__).resolve().parents[1]
tag=sys.argv[1] if len(sys.argv)>1 else "source-cold"
assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',tag),'Invalid runtime tag'
out=ROOT/"work/runtime"/tag;out.mkdir(parents=True,exist_ok=False)
rom_path=Path(os.environ.get("REMIX_ROM",str(ROOT/"inputs/remix4-original.sfc")));rom=rom_path.read_bytes()
isolated=out/('srw3-remix4-'+tag+'.sfc');isolated.write_bytes(rom)
script=ROOT/"source"/os.environ.get("REMIX_SCRIPT","baseline.lua")
fresh=not os.environ.get('REMIX_STATE')and not os.environ.get('REMIX_SRAM')
prelude="""local initialized=false
emu.addMemoryCallback(function()
 if not initialized then
  initialized=true
  for a=0,8191 do emu.write(0x700000+a,255,emu.memType.snesMemory)end
 end
end,emu.callbackType.exec,0x008000,0x008000,emu.cpuType.snes,emu.memType.snesMemory)
"""if fresh else ''
(out/"probe.lua").write_text(prelude+script.read_text(encoding='utf-8'),encoding='utf-8')
settings={"Debug":{"ScriptWindow":{"AllowIoOsAccess":True,"ScriptTimeout":30}},"Snes":{"Port1":{"Type":"SnesController"},"Port2":{"Type":"None"}},"Preferences":{"OverrideSaveDataFolder":False,"OverrideSaveStateFolder":False}}
(out/"settings.json").write_text(json.dumps(settings),encoding="utf-8")
env=os.environ.copy();env["REMIX_OUT"]=str(out)
if env.get('REMIX_CASES'):
    case_path=Path(env['REMIX_CASES']);(out/'cases.lua').write_bytes(case_path.read_bytes());env['REMIX_CASES']=str(out/'cases.lua')
exe=Path(os.environ["MESEN_EXE"]).resolve(strict=True)
started=time.time()
with (out/"stdout.log").open("w",encoding="utf-8") as f:
 q=subprocess.run([str(exe),"--testRunner",str(out/"probe.lua"),str(isolated),"--doNotSaveSettings","--timeout="+os.environ.get("REMIX_TIMEOUT","180"),"--enableStdout"],cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=int(os.environ.get("REMIX_TIMEOUT","180"))+30,creationflags=0x08000000)
report={"returncode":q.returncode,"source_sha256":hashlib.sha256(rom).hexdigest(),"loaded_rom":str(rom_path),"script_sha256":hashlib.sha256(script.read_bytes()).hexdigest(),"mesen_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),"elapsed_seconds":time.time()-started,"fixture":("same-ROM native text checkpoint; declared text/condition/PRNG argument probes"if script.name=="probe_matrix.lua"else"cold identified ROM; natural joypad input only; no PC/WRAM writes")}
if env.get('REMIX_CASES'):report['cases_sha256']=hashlib.sha256((out/'cases.lua').read_bytes()).hexdigest()
report['actual_script_sha256']=hashlib.sha256((out/'probe.lua').read_bytes()).hexdigest()
report['isolated_rom_basename']=isolated.name
report['fresh_sram_before_native_reset']=fresh
if env.get('REMIX_FIXTURE'):report['fixture']=env['REMIX_FIXTURE']
for key in ['REMIX_STATE','REMIX_ACTIONS','REMIX_SRAM']:
    if env.get(key):report[key]={'path':env[key],'sha256':hashlib.sha256(Path(env[key]).read_bytes()).hexdigest()}
(out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report));print((out/"stdout.log").read_text(encoding="utf-8",errors="replace")[-3000:])
