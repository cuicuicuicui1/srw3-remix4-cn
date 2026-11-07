# 来源与许可范围

本仓库的原创构建、验证、诊断工具及原创汉化贡献以 MIT 许可开放。MIT 不授予原游戏、改版或提取出的日文原文、角色与图像的权利；这些内容的权利属于各自权利人。本项目为非官方维护工程。

`inputs/fonts/fusion-pixel-12px-zh_hans.bdf` 来自 TakWolf 的 Fusion Pixel Font，保留原字体及 `inputs/fonts/OFL.txt` 的 SIL OFL 1.1。生成并包含字形的补丁随附同一许可。

`source/vendor/native_parser.py` 来自本项目受限 ZCode 审计的提取器，经主代理校正无条件 F9 终止及字形处理。原审计关于 FF 返回 bank 丢失的判断已被证伪，参见 `analysis/parent-control-review.json`。`source/vendor/sim65816.py` 与 BPS 工具复用本地既有 SFC 研究工具；地址和行为由本项目重新验证。

翻译由受限 ZCode 批次提供初稿，主代理集成、重点审校并负责验收。这里未将工人的“完成”自报当作测试结果，也未声称已逐句完成独立全文润色。

公开内容包括源码、译文、原始日文改版的文本/控制结构提取、分析报告、字体和 BPS 差分。无游戏 ROM、模拟器程序、即时存档、玩家存档及 RAM/VRAM 转储。
