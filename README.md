# Biomedical Paper Writing Skills

Six biomedical writing Skills for research-article planning, narrative Review synthesis, language editing, Figure prototypes and integrity QC.

**整理开发与维护 / Maintainer: ChEsSosy**  
发行构建：`0.1.5-six-skill-public.1` · 2026-10-30

这套工具参考其他 Skill 的设计，并结合科研写作需求在 AI 辅助下迭代。贡献、参考项目与许可范围见 [ATTRIBUTION.md](ATTRIBUTION.md)。

仓库：[ChEsSosy/biomedical-paper-writing-skills](https://github.com/ChEsSosy/biomedical-paper-writing-skills)。本项目原创贡献采用 [MIT License](LICENSE)；参考来源和保留声明见 [ATTRIBUTION.md](ATTRIBUTION.md)。第三方来源未完成逐文件审计。

## 快速开始

1. 阅读 [中文使用说明](USER_GUIDE.md)。
2. 将 `skills/` 下需要使用的模块完整复制到项目的 `.agents/skills/` 或用户的 `~/.agents/skills/`。同名版本不要盲目合并。
3. 在支持本地 Skills 的 Codex 环境中，指定稿件、来源、修改范围和结果位置，调用相应 Skill。

例如：

```text
$review-architect-polisher
请阅读 <综述草稿路径> 和 <文献索引路径>。
先诊断段落逻辑、重复和多来源综合不足，给出局部调整建议。
保留科学命题和引用关联，不覆盖原稿。
将建议保存到 <结果路径>，供我审核。
```

## 六个模块

| Skill | 主要用途 |
| --- | --- |
| [style-and-structure-distiller](skills/style-and-structure-distiller/SKILL.md) | 同类论文的可追溯结构提取与可观察风格统计 |
| [manuscript-story-architect](skills/manuscript-story-architect/SKILL.md) | Original Article 研究故事、论点—证据与章节规划 |
| [article-polisher](skills/article-polisher/SKILL.md) | Original Article 的受控语言修订 |
| [review-architect-polisher](skills/review-architect-polisher/SKILL.md) | Narrative Review / mini-review 的架构、综合与修订 |
| [scientific-figure-designer](skills/scientific-figure-designer/SKILL.md) | 有证据约束的 Figure 设计及受限原型 |
| [scientific-integrity-qc](skills/scientific-integrity-qc/SKILL.md) | 对完整 producer package 执行已实现的确定性完整性检查 |

正式修订、Figure 和 QC 路线需要各自的结构化输入及权限。普通建议不等于正式验证通过；QC 不证明科学真理，Figure 原型不等于最终投稿图。当前九个静态跨模块 handoff 保持 blocked；安装不会自动启用完整流水线。

## 建立自己的领域表达资源

本发行版只包含六个通用 Skill。用户可以收集有权分析的同类论文，经 M01 提取可观察结构和统计，再结合定向阅读归纳句子级表达规则，建立自己的专用 Skill。详见 [使用说明第 4 节](USER_GUIDE.md#4-收集自己的文献整理专用风格-skill)。

提炼范围可以是术语搭配、句法与信息组织。科学数据、结论和作者立场不应作为模仿内容。这些是指令与工具资源，不是微调后的模型。

## 版本与目录

六个模块的源码、inventory、vendor、schema 与测试保持既有工程基线；本次仅整理外层发布文件。源合集版本 0.1.5，六包基础为 guidance release 0.1.4。当前文件身份见 [RELEASE_MANIFEST.json](RELEASE_MANIFEST.json)，发行范围见 [PUBLIC_RELEASE.json](PUBLIC_RELEASE.json)。

`skills/` 是模块源码；`schemas/`、`shared-guidance/` 与 `integration-manifest.json` 是套件资源。模块内已有 tests、fixtures、vendor 等属于完整包，安装时保留。

## 版权与使用者稿件

Copyright (c) 2026 ChEsSosy，仅适用于本项目可受保护的原创贡献。MIT 许可文本见 [LICENSE](LICENSE)；第三方权利及已识别声明见 [ATTRIBUTION.md](ATTRIBUTION.md) 和 [third-party-notices/](third-party-notices/)。

署名与许可保留在工具发行物中。使用本工具不要求在论文正文、图注、致谢或参考文献中注明 ChEsSosy，也不自动添加水印或宣传。期刊的 AI 使用披露规定仍须独立遵守。

克隆时保留根目录的 .gitattributes，防止 Git 自动转换行尾而影响包内文件身份。
