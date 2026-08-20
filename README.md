# Find UI Motion Skill

面向 Codex 的 UI 动效发现与重建 Skill，覆盖 Web 与移动端。它先返回真实案例直达链接，再用 OpenCLIP、动态区域、光流和 RRF 做可选的视觉深度匹配，最后按公开代码片段、软件包、授权资源或独立重建的顺序交付。

## 安装

把下面这段话粘贴给 Codex：

```text
请使用 $skill-installer 安装这个 Skill：
https://github.com/jjacy2024/find-ui-motion-skill/tree/main/skills/find-ui-motion
```

安装后可在新任务中输入：

```text
使用 $find-ui-motion，帮我找一个卡片点击后展开为详情页的真实动效案例。
```

## 主要能力

- 精确搜索、灵感探索和参考重建三种工作流。
- 内置 23 个来源、3656 条经证据门槛筛选的具体案例。
- 按“本地类目 → 3656 条全库文本 → 本地同义词”确定性升级，仅在覆盖缺口时建议一次有标记的外网补充。
- 默认优先代码或运行时可实现的案例；仅在用户明确授权后搜索视频案例。
- 首次启用会告知当前来源与案例数量，并可按需列出全部来源主页。
- 发现清单外的高质量代码动效来源时，可生成仅含“网站名称与域名”的 GitHub Issue 推荐。
- 逐条区分“本地准确匹配”“本地相邻参考”和“外网补充”，不用弱相关案例凑数。
- 快速阶段与视觉深度匹配阶段默认各返回 8 个合格案例。
- 视觉深度匹配默认召回 48 条、硬上限 64 条，再收敛到实时检查与捕获阶段。
- 直接链接到真实案例，不用文字或虚构预览代替来源效果。
- 区分页面可访问与动效真实可见，拒绝空壳页面、失效链接和已确认静态元素。
- OpenCLIP 全帧与动态区域检索，DIS 光流与 Farneback 回退，RRF 融合和选择性 VLM 复核。
- 自动分页、跨批次去重，未指定时下一批默认 3 个。
- 区分 Web 来源与 iOS、Android、Flutter、React Native 等目标平台。
- 按 snippet、package、asset、recreate 的顺序安全重建。

## 可选视觉依赖

基础目录搜索不需要打包模型。启用本地 OpenCLIP 深度匹配时，可在用户确认后安装：

```bash
python3 -m pip install open_clip_torch torch pillow opencv-python-headless
```

模型权重下载到 Skill 之外的用户缓存，不随仓库分发。默认 checkpoint 的代码许可与权重许可需分别核验。

## 目录更新

网站清单、具体案例索引和更新 manifest 单独维护在：

https://github.com/jjacy2024/find-ui-motion-catalog

Skill 首次使用时执行轻量检查；发现新目录版本只提醒，不会自动应用更新。

## 仓库结构

```text
skills/find-ui-motion/
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── references/
└── scripts/
```

维护脚本和测试分别位于 `maintainer/` 与 `tests/`。本仓库不包含模型权重、第三方截图、视频或运行缓存。

## English install prompt

```text
Use $skill-installer to install this Skill:
https://github.com/jjacy2024/find-ui-motion-skill/tree/main/skills/find-ui-motion
```
