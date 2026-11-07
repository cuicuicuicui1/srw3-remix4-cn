# 未汉化 ReMix4 的解包成果

对象是 SHA256 `edcffa7b6aa734735b64f7674f02e2cf4e24a7a499cfd24675ad34c86218fe8f` 的 1.5 MiB 日文改版。不是 SRW4，不是已独立验证的第三次零售原版，也不是完整游戏反编译。

## 从哪里看

- `source/japanese-map.json`：原始字符编码到日文字形映射。解码字形也可能需要修正，不能把机器提取的汉字直接当成正确原文。
- `work/text-graph/graph.json`：最终 R1 的正文冻结图。`nodes` 包含 `source_cpu`、`source_offset`、`root_ids`、原始 `tokens`（`offset/kind/raw/text/params`）、`edges`、`fallthrough`、`span_refs`；`literal_spans` 关联日文、原字节、宿主、原始片段哈希以及已复用译文。
- `work/zcode-control-audit/out/tables.json`：日文主文本根表的早期布局推断和置信度，不能用其槽数宣称全游戏覆盖。
- 同目录 `spans.jsonl`、`branch-spans.jsonl`：早期逐根及分支的 token、控制、动态项、重编码信息。`translation-spans.jsonl` 和 `branch-translation-spans.jsonl` 是相应文字视图。
- `work/name-contracts.json`：名称原字节、地址、像素宽度和表别名。`work/zcode-extra-names/input.json` 另含 `06:F42F` 独立 16 槽道具表中的 14 个非空名称。
- `work/zcode-menu/input.json`、`zcode-extra-menu/input.json`、`zcode-mixed-menu/input.json`：原生菜单、继承字形模式的纯文字菜单及混合调用菜单的源合同。排除项保留原因。
- `work/zcode-control-audit/control-contracts.json`：正文读取器地址、操作码、参数长度、指针与调用栈状态。低级菜单是另一种语法，不能直接套此表。
- `work/zcode-coverage/evidence.json`：时点覆盖审计，包含孤立字面、疑似表及当时的局限；其中“未集成 graph009”不是最终 R1 状态。
- `analysis/parent-control-review.json`：原生 FF bank 恢复及字形纠错的独立裁定。此记录优先于早期错误推断。

这些是文本和相关控制结构的提取，未声称完整解包单位数值、关卡地图、战斗脚本、事件调度、音频、美术或所有隐藏消费者。调查原改版卡关还需要追踪事件消费者；这里提供入口和文本对照，不能替代该分析。

## 安全地重新提取

先按 README 构建一次以安装本地忽略的源文件，然后：

```sh
python source/prepare_graph.py --output work/extracted-audit-001
```

输出目录必须不存在；冻结的 `work/text-graph/graph.json` 不会被覆盖。入口集合来自已公开的早期根表记录，并补充已发现孤立正文，随后递归跟随原生分支；遇未知结构或非法锚点会登记。源合同、原字节及映射都公开，维护者可扩大提取范围，但新分母应另外验证。

重提取会使用当前审定字形表及可复用译文，字形校正和原样冻结的历史批次之间可能存在差异。重提取图是新的分析成果，不能未经审校替换 R1 构建输入。不要把早期提取器副本或 `font001/graph001..007` 作为交付入口。

## 两个容易误修的反例

**F9 无条件跳转**必须结束基本块。早期解析器曾继续读取并合并不连续 token，导致错误分支；当前图准备器逐 token 核对连续性。

**FF 的返回 bank 已恢复**：原生 M=16 下先 `STA $AD`，再 `STA $AE`，第二次重叠写也会更新 `$AF`。早期“bank 丢失”的结论错误；这不是待修的原改版 bug。
