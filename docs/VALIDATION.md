# 测试证据和复测

`evidence/R1/` 是 **2026-10-27 既有测试记录**，目标 ROM SHA256 为 README 的 `bcde4e...608cd`。公开时移除了报告中的个人机器路径，保留 ROM/脚本/用例哈希、计数与原日志。运行脚本与日志仍保留原字节。没有上传相应存档或内存转储。

既有验证分开解读：

| 类型 | 结果与范围 |
|---|---|
| 成品静态回读 | 4,879 literal runs、7,097 controls、607 分支/续接边；源区变化 46 字节 |
| 65816 模型 | 17,805 项实际钩子指令/ABI 检查；不是 PPU 时序证明 |
| Mesen 2.1.1 原生消费者 | 568 例：随机465、F9条件86、F8条件2、跨bank子对白2、长文本3、孤立正文10 |
| 标题图形 | 实际 VRAM 前 `0x3000` 字节与期望匹配 |
| 自然按键 | 冷启动剧情/地图/精神说明；地图保存→普通SRAM→冷启动继续→单位菜单打开/取消 |
| 构建和补丁 | 哈希种子0/123双构建相同；BPS新进程重放及错误输入拒绝 |

消费者矩阵采用同 ROM 自然入口建立的检查点，再受控替换文本指针、条件和随机输入。它核对实际选中叶及最终 FF 指针，不证明自然全流程触发。`final-global-012` 名称是历史标签，其中地图菜单截图曾误标为全局菜单；最终说明已更正为单位菜单。

## 公开仓库的验证

本次开源整理的双构建、补丁回放和发布下载核对会记录在 `evidence/publication-20261108.json`。它们支持公开构建链和补丁身份，不代表本次重跑了模拟器。

无需 ROM 的检查见 README。完整构建会运行 `source/verify_graph.py` 和 `source/verify_hooks.py`，直接检查当前输出而不是沿用历史报告。

## 自行复测消费者

自备 Mesen 2.1.1（原验证可执行文件 SHA256 `d2eb03c2590c648bf329f127ebcfefd70130e7690a9e2ccdba8616faea1fe96b`）。PowerShell 示例：

```powershell
$env:MESEN_EXE='D:\YourEmulator\Mesen.exe'
$env:REMIX_ROM=(Resolve-Path 'work/build/rebuild-001/remix4-cn.sfc').Path
$env:REMIX_SCRIPT='probe_help_checkpoint.lua'
python source/run_baseline.py fresh-help-001
python source/prepare_runtime_cases.py rebuild-001
$env:REMIX_SCRIPT='probe_matrix.lua'
$env:REMIX_CASES=(Resolve-Path 'work/runtime-cases/rebuild-001-all.lua').Path
python source/run_baseline.py matrix-001
```

每次使用新 tag；不带 State/SRAM 时，运行器会用唯一 ROM 文件名并在原生 reset 前擦除 8 KiB SRAM。Lua 检查点在本轮候选自身的自然入口建立。研究 `probe_*.lua` 的前置条件后再复用，不能把超时、未命中回调或只跑到任意 FF 当作目标测试通过。

`REMIX_STATE`、`REMIX_ACTIONS`、`REMIX_SRAM` 是可选的本地路径参数；这些文件不在公开仓库。保存和续玩复测必须由当前候选建立自己的自然检查点/普通 SRAM，跨版即时存档只能当作明确声明的受控探针。
