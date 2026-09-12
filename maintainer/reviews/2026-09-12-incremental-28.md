# 28 条候选入库复核 — 2026-09-12

本文保留审核完成时的历史快照，文中“未发布”指该审核时点；后续发布版本见仓库 README。

## 结论

**通过 23 条，暂缓 5 条；本地总数 3719 → 3742，仍为 26 个来源、65 类动效。**

本批：transitions-dev +5 / react-bits +7 / magic-ui +1 / inspira-ui +5 / lightswind-ui +4 / ui-beats +1。

Catalog 仍为未发布的本地 `2026.09.12` 草案，Skill 程序版本 `0.9.7` 不变。仅更新源码 Skill、已安装 Skill 和独立 Catalog 工作副本；不提交、不推送、不发布。此前 OpenShaders 24 条及其他未提交修改全部保留。

范围严格限于先前选出的 28 条“未收录候选”，不把 sitemap lastmod 或 New 标签当作首次发布日期。25 条具有明确动效，其中 2 条许可未通过；另 3 条动效证据不充分或预览身份不符，共暂缓 5 条。不是认定这 5 条永久不可用。

## 逐条审核

相似度是维护者对最近家族的定性判断，不是全库视觉嵌入评分；“中”表示同族但有保留价值。全部 28 条通过 ID／规范化 URL／Transitions 别名精确去重；已有 3719 条未做全量视觉重审。仅对最接近的 Ghost Cursor、Particles、Spiral Images 追加现场对照。

| # | 具体案例 | 实际动效 | 相似度与区别 | 决定 |
| --- | --- | --- | --- | --- |
| 1 | [Thinking states](https://transitions.dev/transitions/thinking-states/) | 思考状态依次切换，文字表面带扫光。 | 中：与 Text states swap、Shimmer text 同族，但组合了 AI 多步骤状态轮换与扫光。 | 通过 |
| 2 | [Reasoning stream](https://transitions.dev/transitions/reasoning-stream/) | 圆角遮罩窗口内，推理段落分段向上推进。 | 低：区别于逐字输出和单行状态切换，重点是多段内容在受限窗口中的连续位移。 | 通过 |
| 3 | [Streaming text](https://transitions.dev/transitions/streaming-text/) | 正文按词逐步从模糊变清晰，形成流式生成效果。 | 中：与普通 Typewriter 同属文本生成，但采用逐词模糊消散，而不是逐字符硬切。 | 通过 |
| 4 | [Matrix dot loader](https://transitions.dev/transitions/matrix-dot-loader/) | 四组 4×4 点阵按不同错峰节奏明灭。 | 中：与 Glyph Matrix、Dotmatrix 同族；此例是紧凑加载状态的四种时序，不再拆成四条。 | 通过 |
| 5 | [Banner stacking](https://transitions.dev/transitions/banner-stacking/) | 重复添加后，灰色胶囊占位横幅形成层叠队列。 | 中：与普通 Toast 同族，但强调层叠深度和队列重排；不是完整通知业务组件。 | 通过 |
| 6 | [Masked Heading](https://reactbits.dev/text-animations/masked-heading) | 标题字形充当遮罩，字内视频纹理持续变化。 | 中：与 GSAP Text Masking 同为文字遮罩，但这里的主要动态来自字形内部视频。 | 通过 |
| 7 | [ASCII Text](https://reactbits.dev/text-animations/ascii-text) | 彩色 ASCII 字符组成的 Hey! 持续扭曲。 | 低：不同于全屏 ASCII 背景，但上游授权关系未通过。 | 暂缓 |
| 8 | [Glow Cursor](https://reactbits.dev/animations/glow-cursor) | 指针移动产生细长青色亮芯拖尾。 | 低：现场对照 Ghost Cursor：旧例为大面积紫色烟雾，新例为收尖细线，形态明确不同。 | 通过 |
| 9 | [Infinite Spiral](https://reactbits.dev/components/infinite-spiral) | 照片卡片沿竖直三维螺旋流动，前大后小并带远景模糊。 | 低：现场对照 Originkit Spiral Images：旧例为平面向心漩涡，新例为竖直圆柱螺旋。 | 通过 |
| 10 | [Aero Shards](https://reactbits.dev/backgrounds/aero-shards) | 紫色反光棱角碎片在纵深中漂移、旋转。 | 低：保留硬质碎片及反光平面特征，不等同于普通圆点粒子。 | 通过 |
| 11 | [Ghost Fibers](https://reactbits.dev/backgrounds/ghost-fibers) | 蓝紫发光长纤维缓慢转动、漂移。 | 低：连续细丝与本批硬质碎片、CRT 波形、隧道光缆均有明确差异。 | 通过 |
| 12 | [CRT Warp](https://reactbits.dev/backgrounds/crt-warp) | 品红波纹沿 CRT 扫描线和像素网格变形移动。 | 低：扫描线、像素纹理和屏幕弯曲是组合特征，不按颜色变体拆条。 | 通过 |
| 13 | [Light Tunnel](https://reactbits.dev/backgrounds/light-tunnel) | 亮段沿指向消失点的紫色曲线光缆向外传播。 | 中：与 Particle Tunnel、Gallery Tunnel 同属纵深通道，但运动载体是连续光缆上的亮段。 | 通过 |
| 14 | [Floating 3D Particles](https://magicui.design/docs/components/floating-3d-particles) | 粒子云旋转漂移，点的大小与透明度表现前后深度。 | 中：现场对照 Particles：同属点云，保留明显纵深投影差异；检索时仍应作为近似家族控制数量。 | 通过 |
| 15 | [HTML ASCII](https://inspira-ui.com/docs/en/components/html-in-canvas/html-ascii) | HTML 内容可见地重建为 ASCII；按压仅确认局部字符明暗变化。 | 中：与 ASCII Text 对象不同，但未确认足够清晰的连续或过渡动效，上游字符算法许可也未厘清。 | 暂缓 |
| 16 | [HTML Blaze](https://inspira-ui.com/docs/en/components/html-in-canvas/html-blaze) | 火焰从 HTML 卡片底部升起，热扰动影响文字及卡片表面。 | 低：不是单独火焰背景；整块实时 HTML 被热浪折射。 | 通过 |
| 17 | [HTML Chromatic](https://inspira-ui.com/docs/en/components/html-in-canvas/html-chromatic) | 指针从中间移向边缘时，HTML 表面红蓝通道逐渐分离。 | 中：与一般色散背景同族，但直接作用于实时 HTML；与布料和水波的几何扭曲不同。 | 通过 |
| 18 | [HTML Cloth](https://inspira-ui.com/docs/en/components/html-in-canvas/html-cloth) | 整块 HTML 表面及文字呈现连续布料褶皱。 | 中：与 HTML Liquid 同属表面变形，但褶皱更锐利；由于上游许可未通过而暂缓。 | 暂缓 |
| 19 | [HTML Drag](https://inspira-ui.com/docs/en/components/html-in-canvas/html-drag) | 滚动进入预览时，HTML 卡片弯成圆柱曲面，随后回平。 | 中：以滚动速度驱动的大尺度弯曲区别于水波、色散和火焰；不宣称指针拖拽分支已验证。 | 通过 |
| 20 | [HTML Liquid](https://inspira-ui.com/docs/en/components/html-in-canvas/html-liquid) | 指针扫过时，柔和水波扭曲 HTML 文字及边界。 | 中：与 Liquid Logo、液态背景对象不同；与同批 HTML Cloth 的锐褶皱也不同。 | 通过 |
| 21 | [Ribbon Background](https://inspira-ui.com/docs/en/components/backgrounds/ribbon-background) | 多层彩色宽带在标题背景后连续弯曲掠过。 | 中：与 Aurora、Silk 等柔性背景同族，但保留清晰多层带状轮廓；只保留默认代表例。 | 通过 |
| 22 | [3d Glass Coin Carousel](https://lightswind.com/components/3d-glass-coin-carousel) | 半透明玻璃硬币沿倾斜椭圆轨道旋转，边缘朝向持续变化。 | 低：同属旋转画廊，但主体为有厚度、折射边缘的硬币，而非图片卡片。 | 通过 |
| 23 | [3d Smokey Frame](https://lightswind.com/components/3d-smokey-frame) | 边框上有极淡紫色烟丝变化，但主体细节难以判读。 | 中：烟雾边界可能不同于普通发光边框，当前证据清晰度不足，不据名称推定通过。 | 暂缓 |
| 24 | [3d Image Pageflip](https://lightswind.com/components/3d-image-pageflip) | 点击 Next 后 0/5 变为 1/5，封面翻成双页展开状态。 | 中：与单卡正反翻转同族，但有多书页堆叠、书脊偏移和折痕阴影。 | 通过 |
| 25 | [3d Beam Circle](https://lightswind.com/components/3d-beam-circle) | 页面旗帜绕圆弧运动，但公开预览代码指向旧 BeamCircle。 | 高／待定：Preview Code 实际导入 ../lightswind/beam-circle，与文档 ThreeDBeamCircle 不同；旧 beam-circle 已在库中。 | 暂缓 |
| 26 | [Cool Slide Gallery](https://lightswind.com/components/cool-slide-gallery) | 点击 Next 后中心卡片换为 Forest Trail，邻卡以透视队列移位。 | 中：常见 coverflow 家族，保留公开组件实现；与竖直螺旋、翻书、硬币及光栅卡面不同。 | 通过 |
| 27 | [Grain Carousel](https://lightswind.com/components/grain-carousel) | 悬停时卡面在双图间变化，带青色全息光泽、光栅纹理和倾斜。 | 中：通过依据是卡面光栅／全息 hover，不是普通轮播；未确认轮播按钮，不写成已通过。 | 通过 |
| 28 | [Scratch to Reveal](https://uibeats.com/docs/component/scratch-to-reveal) | 指针擦除遮罩，超过阈值后余下遮罩自动退场，重播恢复。 | 低：现有同族仅录屏参考，本例提供可实现的公开 React 组件，补上代码案例空缺。 | 通过 |

## 暂缓项与恢复条件

- **ASCII Text**：原始 CodePen 明示 GPL v3 or later，而 React Bits 为 MIT＋Commons Clause；不能确认授权链，暂缓入库，不作侵权认定。
- **HTML ASCII**：仅确认 ASCII 重建和局部字符变化；movAX13h 字符技术没有精确上游许可。
- **HTML Cloth**：Credits 指向 MartinRGB 的 Shadertoy DttSRB，原页触发安全验证；未绕过，未能核验具体许可。
- **3d Smokey Frame**：切换组件自身预设后仍极低对比度，仅见边缘微弱变化，不足以判读体积烟雾；不是认定静态或失效。
- **3d Beam Circle**：预览代码导入旧 BeamCircle，而文档声明 ThreeDBeamCircle；缺少该新组件的可靠对应动效。

恢复条件：补齐具体上游许可或权利人说明；烟雾边框提供可清晰判读的公开预览；光束环修正具体组件与预览映射后重测。暂缓条目完整保留在外部审核目录的 `quarantine.jsonl`，未进入正式索引，也未删除原有记录。

## 许可核验与分发边界

- [transitions-dev：Free/Pro contractual terms](https://transitions.dev/terms.html)：Free directory tier and public CSS/React path reviewed. Terms allow use/modification in personal and commercial products after lawful access, but prohibit repackaging or redistributing the library or a substantial part. No snippets distributed.
- [react-bits：MIT + Commons Clause](https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md)：Public component code/registry reviewed. Use inside applications, websites or products, including commercial, is allowed with notices; selling, sublicensing or redistributing components themselves, including bundles and ports, is restricted. No code or demo media distributed.
- [magic-ui：MIT](https://github.com/magicuidesign/magicui/blob/main/LICENSE.md)：Official MIT repository licence and selected public component registry reviewed. Preserve copyright and licence notices; demo assets have separate rights.
- [inspira-ui：MIT with separate upstream checks](https://github.com/rahulv-official/inspira-ui/blob/main/LICENSE)：Current official repository MIT licence, selected public docs/usage and Credits reviewed. Preserve notices; separately verify third-party shaders and media. Experimental HTML-in-canvas compatibility is not guaranteed.
- [lightswind-ui：MIT for selected public components](https://github.com/codewithMUHILAN/Lightswind-UI-Library/blob/Master/LICENSE)：Official repository alias resolves to Lightswind-UI-Library with MIT licence. Selected Animated/free public component import and Code/CLI path reviewed; Pro products and demo photographs are not covered by this admission.
- [ui-beats：Item-level MIT](https://uibeats.com/docs/component/scratch-to-reveal)：Selected item explicitly states Licence MIT and exposes a public shadcn registry/component source. Preserve copyright and licence notices.

- ASCII Text 的公开组件页明确署名原始 [CodePen](https://codepen.io/JuanFuentes/pen/eYEeoyE)，该原页 HTML 和 JS 均显示 “GNU GPL v3 or later”。此处记录授权链存在未决问题，不作侵权或最终法律结论。
- HTML Cloth 的 [MartinRGB 原作](https://www.shadertoy.com/view/DttSRB)出现安全验证，未绕过，也未根据仓库 MIT 覆盖上游许可。
- HTML Blaze 的 Credits 明示 Ashima Arts Simplex Noise 为 MIT；Ribbon 的 [OGL 仓库 README](https://github.com/oframe/ogl)当前写的是 Unlicense，而不是 MIT。
- 本次“通过”只授权目录中的公开链接及描述性元数据收录，不代表截图、照片、视频、着色器或组件可以随 Skill 转售／再分发。全部新记录仍保持 `reference-only`，实际复制或实现前重新核验具体版本、通知义务及第三方素材。

## 证据质量与限制

- 每个候选页面都完成浅层 HTTP 检查；28 个外壳均返回 200，但通过依据是实际触发及观察，不是 HTTP 状态。
- 实际浏览器证据包括点击前后、循环不同相位、指针操作、页数变化和刮除后 Revealed 状态；仅保留本地审核的文字记录与指纹。没有把第三方截图、视频或源代码加入 Git 仓库。
- 指纹为整页截图 FNV-1a-32，只作辅助溯源，不是独立目标区域运动量化，也不证明截图权属。Thinking states 只有 1 个有效截图指纹，但现场观察到三个状态和文字扫光；没有编造第二帧。
- `running_animations=0` 表示目标 CSS 动画数量未测量，不表示静态；通用页面装饰动画不算目标证据。`last_verified` 只对通过条目设为本次日期。
- Lightswind 的赞助弹窗和滚动定位曾使首次点击不生效；关闭非约束性提示、滚动稳定后重试，翻书、硬币及滑动画廊成功。GitHub 星标计数接口报错不作为演示失效的原因。
- HTML Drag 仅确认滚动弯曲；Grain Carousel 仅确认 hover 光栅／全息效果，不宣称其轮播导航已通过。照片与标题的占位不一致已记录。
- Inspira HTML-in-canvas 为实验性渲染；未验证跨浏览器、移动端、reduced-motion、无缝循环、帧率或安装后执行。Web 代码不自动成为原生 App 可用代码。

## 本地采用和验收

只追加 23 个条目；旧 3719 条 JSONL 保持完整字节前缀。六个相关来源仅追加本轮有限范围审核说明，Inspira 许可链接更新为当前官方仓库，未把局部审核写成历史全站重审。现有深审日期保留。

数据、schema、精确去重、源码／安装／Catalog 一致性、来源占比、单元测试及 manifest 校验结果写入本次外部审核目录的 `verification.json`。发布前须重新生成正式时间戳与不可变 Release 资源，本轮不执行远程发布。

## 最终验收结果

- Schema、65 类引用、3742 个唯一 ID／案例地址通过；规范化时保留 Circle Loaders 用于标识独立案例的锚点，并统一 Transitions 官方别名。
- 原 3719 条字节前缀 SHA-256 与基线完全一致；整个已安装 Skill 与源码一致，独立 Catalog 的两份数据文件也逐字节一致。
- 新增 23 条均通过已安装 CLI 的实际检索，按各自标题查询时均排在初筛第 1 位。检索读取的是本地 bundled 目录，不是旧缓存。
- 53 项单元测试通过。仅更新旧总数断言、把原 CRT 缺口测试隔离为不含新 CRT 条目的固定缺口情境，并新增本批入库／暂缓／许可边界测试；检索实现和 Skill 指令未改动，原有未提交测试修改经逆向核对完整保留。
- 来源占比通过，最大来源为 Rive 2021 条，占 54.01%，低于 80% 上限；两个仓库 `git diff --check` 及 Skill 结构校验通过。
- manifest schema、sites SHA-256、确定性 gzip SHA-256、解压内容 SHA-256 和往返一致性通过。相对于 Catalog 已提交版本，本地累计新增 3 个来源、86 条案例，本轮更新 6 个已有来源的有限审核说明。
- 仍保留 Motion、Animista、React Bits 三条既有全站深审日期提醒；本轮局部复核没有冒充全库重审。没有删除文件、提交、推送或发布。

原始浏览器导出中的 `at` 是该条证据记录首次创建时间，后续补测结论在同日汇总；不是每个最终截图的精确捕获时间。整页截图指纹不作为单独的动效判定。
