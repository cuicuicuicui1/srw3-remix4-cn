# 大灾难×ReMix4 简体中文汉化与维护工程

供《第3次超级机器人大战》SFC 日文改版 **大灾难×ReMix4** 使用。公开构建器、译文、原改版文本解包、控制结构、逆向记录与 BPS 补丁，方便定位汉化问题及原改版本身的问题。**这是 SRW3 LoROM 引擎，不是 SRW4。**

当前补丁：**R1 测试版，2026-10-27**；开源整理：2026-11-08。开源整理没有修改已交付的 R1 ROM 内容。

## 下载和使用补丁

[Releases 下载](https://github.com/cuicuicuicui1/srw3-remix4-cn/releases)有补丁专用 ZIP；仓库内也可直接取 `patches/R1/` 的四个文件。ZIP 不含 ROM。

需要自行准备以下精确日文改版文件，无 512 字节外部头：

| 项目 | 身份 |
|---|---|
| 源文件大小 | 1,572,864 字节（1.5 MiB） |
| 源 SHA256 | `edcffa7b6aa734735b64f7674f02e2cf4e24a7a499cfd24675ad34c86218fe8f` |
| 源 CRC32 | `C97D10C6` |
| R1 成品大小 | 2,097,152 字节（2 MiB） |
| R1 成品 SHA256 | `bcde4e317f945b23c4ceac6bca89e6725812eb94e53d3cd51cc0e09e0dd608cd` |
| R1 BPS SHA256 | `02e1faedf958940303802ea976fb3b37c662d420c71f9ec2f0e9166718d96696` |

Python 3.12，无第三方 Python 包：

```sh
python patches/R1/apply_patch.py "你的日文改版.sfc" "新的中文输出.sfc"
```

应用器默认从自身目录读取 BPS 和 `identity.json`，拒绝错误源、损坏补丁、输入输出别名和已有输出。建议给新版本独立文件名，先保留自己的存档；跨版即时存档兼容性未作保证。字库许可随补丁附带，见 `inputs/fonts/OFL.txt`。

## 从源码重建

克隆或下载本仓库，在仓库根目录执行：

```sh
python tools/build.py --source "你的日文改版.sfc" --tag rebuild-001 --verify-r1
```

工具固定源文件和字体身份，将源复制到本地忽略目录，从原文件生成标题图形，再构建文本、字库和钩子，运行成品回读与钩子模型，并生成 BPS。输出在 `work/build/rebuild-001/`；已有输出目录会拒绝覆盖。R1 重建须同时匹配上表的 ROM 和 BPS 字节。

修改译文或代码后，用新的 `--tag`，去掉 `--verify-r1`，保留新 SHA256 和受影响测试。不要给不同字节的候选沿用 R1 的运行结论。同一工作目录请串行构建。

```sh
python -B -m unittest discover -s tests -v
python -B tools/check_data.py
```

这两项不需要 ROM，GitHub Actions 也只运行它们；它们不证明 ROM 构建或游戏通关。构建使用的安全断言需要正常 Python 模式，请勿使用 `-O`。

## 维护入口与解包成果

| 路径 | 内容 |
|---|---|
| `source/build_graph.py` | 当前有效的图结构构建器；完整搬迁关联分支后才重定位 |
| `source/vendor/native_parser.py` | 原生正文语法提取器，遇未知结构停止 |
| `source/japanese-map.json` | 经复核的原码到日文字形映射 |
| `work/text-graph/graph.json` | R1 构建所用冻结图：源 CPU/文件偏移、token 原字节、日文、分支边、续接、别名、字面 span |
| `work/zcode-control-audit/` | 原改版早期根表、正文/分支提取、控制合同；局部过时结论见解包说明 |
| `work/name-contracts.json` | 949 个名称的源字节、位置及共享别名 |
| `work/zcode-*/input.json` | 对应文本、菜单、道具名的源合同及显示预算 |
| `work/zcode-*/translations.json` | ZCode 译文与名称短称；bulk-01 至 bulk-10 是当前正文批次 |
| `work/translation-review/` | 源字形疑点、说话人审校与菜单更正 |
| `analysis/` | 主代理纠错、已失效候选、导入文件来源账 |
| `evidence/R1/` | 2026-10-27 的同 ROM 静态、模型和运行证据，个人机器路径已移除 |
| `docs/` | 解包索引、引擎说明、测试边界、bug 定位流程 |

这里的“原版解包”指**用户提供的未汉化 ReMix4 日文改版**。没有独立确认的 SRW3 零售原版解包，不将二者混称。已公开文本及相关结构；没有把整个游戏解包成可直接重新组装的地图、战斗、音频、美术与事件引擎源码。

## 已完成和未验证范围

R1 回插 4,768 段正文/战斗/名称、306 段菜单、3 个标题按钮，新增 1,817 个中文字形。源 ROM 区域只有 46 字节的明确钩子、标题资源指针与校验和变化，原文本、事件和字库资源保留，新增内容放在扩展空间。

既有 R1 证据：568 个 Mesen 原生消费者用例、17,805 项钩子指令模型检查、成品静态回读、不同哈希种子双构建、标题 VRAM 对照，以及自然按键存档后普通 SRAM 冷启动继续。原生消费者用例包含受控文本指针、条件和随机输入，不等于自然走完整流程。

保留原日文 Logo、控制器/边框图块、字形调试表和用途未明的孤立“バ”默认占位。14 个道具名和 10 段孤立正文虽已回插，自然可达性未证明。部分表长仍是布局推断；未自然全流程通关、未做硬件验证，也未证明原改版无 bug。详细限制见 [已知问题](docs/KNOWN_ISSUES.md)。

## 参与维护

请先读 [贡献指南](CONTRIBUTING.md) 和 [原版解包说明](docs/EXTRACTION.md)。报告问题请带实际 ROM SHA256、模拟器版本、场景和复现步骤；原改版的同入口对照很有价值。不要把跳剧情、清空正文或强写胜利标志作为卡关修复。

原创工具与原创汉化贡献采用 MIT；字体为 SIL OFL 1.1。原游戏和改版素材不因本仓库而重新授权，详见 [NOTICE](NOTICE.md)。
