# Biomedical Paper Writing Skills 使用说明

作者／整理开发与维护：**ChEsSosy**  
通用公开发行准备构建：`0.1.5-six-skill-public.1`（2026-10-30）

本套件参考其他 Skill 设计并经 AI 辅助迭代，贡献与许可记录见 [ATTRIBUTION.md](ATTRIBUTION.md)。署名只保留在套件中，不要求写进论文、图注或致谢。

## 1. 安装

适用于可读取本地 Skill 的 Codex 环境。下载源码或解压发行文件后，在 `biomedical-paper-writing-skills/skills/` 中可见六个独立目录。

选择一个安装范围，将六个目录完整复制到：

- 项目使用：`<你的项目>/.agents/skills/`；
- 当前用户使用：`<用户主目录>/.agents/skills/`，Windows 通常是 `C:/Users/<用户名>/.agents/skills/`。

例如应得到：

```text
<你的项目>/.agents/skills/review-architect-polisher/SKILL.md
<你的项目>/.agents/skills/style-and-structure-distiller/SKILL.md
```

复制整个目录，保留 scripts、references、schemas、tests、vendor 等文件；不要只复制 SKILL.md。安装前检查同名目录，已有版本时先决定采用哪版，不要自动合并或覆盖。整个套件外层目录无需放进 Skill 目录，`vendor/` 中的副本也无需单独安装。

新对话中用 `$review-architect-polisher` 等名字显式调用；若未显示，重启 Codex 后再检查目录层级。不同客户端的 ZIP/插件导入流程可能不同；本说明提供本地文件夹安装方法，不把 ZIP 上传到普通聊天视为完成安装。[官方本地 Skill 文档](https://learn.chatgpt.com/docs/build-skills)

只有阅读和写作咨询时，通常不需要执行脚本。执行确定性工具需要可用的 Python 3；Figure 的受限 Python/Pillow 渲染路线还需相应已获批准的环境。包内不含 Python、模型权重或第三方二进制，不会自动安装软件。缺依赖时按当前工具提示确认，勿未经授权改环境。

## 2. 选择哪一个 Skill

| 你的任务 | 入口 | 注意 |
| --- | --- | --- |
| 从参考论文了解章节结构、句段长度、引用分布 | `$style-and-structure-distiller` | Article 和 Review 分开；输出是描述性统计 |
| 自己的 Original Article 故事和论据顺序不清楚 | `$manuscript-story-architect` | 不处理 Review；不做最终润色 |
| Article 需要正式受控润色 | `$article-polisher` | 候选应用需结构化源稿、外部 revision contract 等输入 |
| Review 骨架、段落逻辑、证据综合或用语需要调整 | `$review-architect-polisher` | 区分初步建议和正式 architecture/revision package |
| Figure 设计、证据到图的安排或受限原型 | `$scientific-figure-designer` | 仅支持已声明模式；不能当作最终投稿图或通用表格制作器 |
| 检查正式 Article/Review/Figure package | `$scientific-integrity-qc` | 需要完整输入；QC 不重写内容、不证明科学真理 |

中文 Review 可先处理骨架、主题和证据，最后再进行英文化。不必为了改逻辑先蒸馏风格。引用扩充和跨段综合属于 Review 内容任务，与同句润色分开授权。

### Review 初步架构建议

```text
$review-architect-polisher
输入：<草稿路径>；来源：<文献索引与可读取来源路径>
类型：narrative_review；语言：中文
本轮只诊断章节逻辑、重复、段落任务与证据缺口。
允许提出局部合并和调整建议，不新增无来源结论，不覆盖原稿。
先交付供我审核的建议，不宣称已产生正式验证包。
输出到：<新结果路径>
```

### Review 同句语言优化

```text
$review-architect-polisher
输入：<稿件路径>；范围：<小节或段落>
只改善同一句话的专业表达，保持句段数量、顺序及全部科学命题。
保留对象、条件、比较、数字、单位、否定范围、确定性、因果强度和引用关联。
不增加内容、不自动补通用警示；歧义问题单列。
输出：干净候选正文，保存到<新结果路径>，不覆盖原稿。
```

翻译需明确写“将中文译为英文”；语言优化不自动包含翻译。正式受控修改与独立 QC 还需各自完整来源、权限、版本和 package，普通建议不能冒充执行收据。

## 3. 少增篇幅，补充文献覆盖

适用于已有本地文献库和成稿的 Review。先提供现稿与明确的待筛来源集合，不要求一次把全部文献塞入上下文。

```text
$review-architect-polisher
沿用<现稿>的主题脉络，筛查<待处理文献清单>。
允许小节内部局部重组和合并重复段落，以保持或缩短正文为目标。
按已有具体观点匹配文献，多篇研究可共同支持同一判断。
新增来源须核读实际支持命题的正文；不同条件和反例保留，不靠引用数量宣称共识。
为每个条目记录：未读、已初筛、已核读相关正文、拟纳入或暂不纳入及理由。
不要给每篇新增文献另写摘要；引用归属于它实际支持的命题。
只做我指定的小节，交付候选正文、篇幅与不同来源数量对照，以及新增来源贡献。
不覆盖原稿；如需改核心观点，先列出供作者确认。
```

这是一种任务安排，不宣称全库阅读能力、自动检索能力或完备覆盖。逐批状态记录帮助上下文切换后接续。全文、补充材料、更正可能属于同一研究，不能当作多个独立验证。参考文献总量不等于证据充分或综合质量。

## 4. 收集自己的文献，整理专用风格 Skill

本分享版不包含作者自用的 mRNA 文风 Skill，也不附其专属语料。建议用户依据本人的领域、文章类型和目标期刊，建立自己的可审阅表达资源；这是可选增强，不是使用六个通用模块的门槛。

### 准备可追溯语料

- 选取有权分析、与当前任务匹配的论文。Review-only 与 Original Article-only 分路；不要把数量当成代表性保证。
- 每篇保留原 PDF 与工作 MD，用文献索引关联标题、年份、DOI、文件位置和来源身份。
- MD 用于快速阅读、定位和观察；PDF 用于关键数字、条件、表格、图像与特殊符号的最终核验。
- 检查正文是否混入参考文献、页眉、图表文字，是否错误断句断段。无法可靠转换的部分显式标记，不补造内容。
- 未经许可，不向公共仓库上传出版商 PDF、论文全文 MD、私人稿件或可识别的审稿材料。

### 提取统计，再归纳表达

1. 使用 `$style-and-structure-distiller` 对已明确纳入的同类语料提取结构、长度、表面标记和引用位置等统计。先核对 manifest 与来源；正式提取和诊断 draft 的批准状态应按 Skill 要求区分。
2. 结合定向阅读，以模型辅助方式整理术语搭配、动词—对象关系、比较句、限定语附着、信息焦点和自然句法。保留来源定位、适用条件、反例和审阅状态。
3. 把统计观察、模型辅助归纳和编辑判断分开。M01 不会自动完成语义风格归纳，也不会直接训练或生成一个专用模型。
4. 将已审阅的可迁移规则整理为专用 `SKILL.md` 与必要 references，可请当前环境的 Skill 创建功能协助。写明适用领域、稿件类型和同句保义职责；不要复制论文的独特表达、数据、结论或作者立场。
5. 用本人稿件中未参与规则归纳的少量句子试用，检查专业性与语义是否保持，再逐步采用。无需为了“风格高级”强行改掉已经有效的句子。

各模块的衔接：

- **M01**：提供可追溯结构与统计，不能独自证明语义风格质量。
- **M04**：用于 Review 架构、综合及语言建议；可在适用范围内参考已审阅的项目表达笔记。正式 profile admission 仍需规定输入。
- **M03**：用于 Original Article 受控润色；只采用匹配的 Article 语料及正式权限，不能套用 Review 专属规则。
- **M02**：负责 Original Article 的故事与证据组织，无需先有文风画像。
- **M05/M06**：承担已声明的 Figure 和完整性检查，不负责文风训练或生成新科学证据。

## 5. 交付与科学边界

原稿保持不动，输出到明确的新位置。区分“建议候选”“确定性 producer 验证”“独立 QC 已执行”和“作者批准”。不把文件存在、零 findings 或某个 validator PASS 当作科学正确、证据充分或可投稿。

Figure 是受限设计/原型；Review 比较表可先由 M04 规划内容，正式表格制作接口需另行处理。六个模块不会自动检索、核验全部新文献，也不默认执行完整端到端流水线。九个静态 handoff 仍 blocked，只有满足各自 runtime 输入才有资格进入相应执行。

包内保留的历史合同和版本记录用于解释当前能力，不表示你的安装已经执行了这些历史测试。当前目录说明与实际 inputs 决定本轮能够执行的范围。

## 6. 署名、参考与 GitHub

- ChEsSosy 的署名用于标识整理开发与维护贡献。项目原创贡献采用 [MIT License](LICENSE)；其许可文本和版权声明随软件发行保留，允许的用途包括商业使用。参见 [MIT 许可说明](https://choosealicense.com/licenses/mit/)。
- 原创贡献的许可不覆盖无权授权的第三方内容。已知上游声明保存在 `third-party-notices/`；两项来源的许可/实际复用关系待确认，详见 [ATTRIBUTION.md](ATTRIBUTION.md)。当前不能将整个发行树描述为已完成第三方权利核清。
- 不要求论文正文、图注、致谢或参考文献包含 ChEsSosy、工具名称或 GitHub 链接，不自动添加水印。出版社的 AI-use disclosure 规定单独遵守。
- 仓库：[ChEsSosy/biomedical-paper-writing-skills](https://github.com/ChEsSosy/biomedical-paper-writing-skills)。保留根 .gitattributes，避免 Git 在 Windows 克隆时自动转换包内行尾。
- 不将原始论文 PDF、全文 MD、个人稿件或私有领域表达 Skill 加入公共仓库。

完整发行目录保留根目录许可、署名和第三方声明。按具体任务安装和调用模块；安装时保留对应模块的完整资源。
