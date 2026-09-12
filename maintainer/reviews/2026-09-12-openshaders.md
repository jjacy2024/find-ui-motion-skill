# OpenShaders 首批收录审核 — 2026-09-12

本文保留审核完成时的历史快照，文中“未发布”指该审核时点；后续发布版本见仓库 README。

## 范围与状态

- 本次增量：1 个来源、24 个公开直达案例，覆盖全部 9 个效果类型。选择兼顾纹理、构图、块度、线条和色彩；不把仅更换用户名的同质变体批量入库。
- 目录版本：`2026.09.12`，26 个来源、3719 个案例、65 个动效分类；Skill 程序版本仍为 `0.9.7`。
- 这些是当前用户名生成器的精选视觉变体，**不是 24 套独立着色器实现**。描述标题为维护者补充，`@handle` 仅标识公开页面，不证明作者身份。
- 仅更新本地源码、独立 Catalog 工作副本与已安装 Skill；未提交、推送或发布 GitHub Release。保留独立 Catalog 中本来就存在的待发布改动。
- 全部原有 3695 条案例和 25 个来源保持不变；除目录版本与时间字段外，数据只做追加。

## 来源与复用边界

- [官方主页](https://openshaders.com/)、[Explore](https://openshaders.com/explore)、[About](https://openshaders.com/about)。
- [官方链接的仓库说明](https://github.com/openshaders/openshaders/blob/main/README.md)区分平台许可与创作者自选许可；[MIT LICENSE](https://github.com/openshaders/openshaders/blob/main/LICENSE)不代表所有案例均为 MIT。
- 每个入选页面均可匿名预览，并显示 WebGL、WebGPU、React · WebGL、React · WebGPU 四种代码导出选项。只验证菜单入口，没有复制源码、编译或逐一运行四种导出格式。
- 来源能力记为 `snippet / recreate / inspiration`，但案例权利边界保持 `reference-only`：复制或交付前核验案例自身许可，不明确时只作视觉参考或独立重建。
- 来源为 Web；iOS、Android 等原生目标需要另行重建。未验证性能、帧率、无缝循环、reduced-motion 或全部浏览器兼容性。
- 完整平台、编辑器及组件注册表仍处于 coming soon 状态；当前官方仓库未提供完整着色器实现或已发布 npm 包，因此不标记 `package` 能力。

## 选择清单

| 类型 | 数量 | 视觉区分 |
| --- | ---: | --- |
| Pure field / 平滑色场 | 3 | 分叉光带、圆环弯折、层叠拱带 |
| Grain / 颗粒 | 3 | 细颗粒回环、交叉细带、宽幅铜色起伏 |
| ASCII / 字符 | 3 | 数字状字符环、加号折带、星形宽弧 |
| Dither / 抖动纹理 | 3 | 同心流线、弯折宽带、分叉与三角留白 |
| Halftone / 半调网点 | 3 | 细点错层、密点折脊、斜向波峰 |
| Sparkle / 闪光星点 | 2 | 稀疏星点、棱彩交叉星点 |
| Liquid / 液态 | 3 | 波动亮边、不规则沟槽、液池光泽褶皱 |
| Mosaic / 马赛克 | 2 | 大块几何、阶梯像素带 |
| Chroma / 色散 | 2 | 尖锐折面、液态分叉轮廓 |

下表日期均为 **2026-09-12**，时间为 UTC。哈希是两次**整页截图的 FNV-1a-32**，不是源码哈希、媒体完整性证明或单独着色器区域的运动评分。截图仅用于临时审核，未存入仓库。

| 类型 | 案例直达页 | 选入理由 | 最后成功检查 UTC | 整页截图指纹 A / B |
| --- | --- | --- | --- | --- |
| Pure field | [@nard](https://openshaders.com/@nard) | 薄荷绿分叉光带；mint-green smooth branching light ribbons | 02:31:32.986 | `65b74814` / `fcb538fb` |
| Pure field | [@codeindie](https://openshaders.com/@codeindie) | 蜜桃色圆环弯折；peach-orange soft rounded ring and vertical bend | 02:31:36.418 | `0fe8c135` / `4192419c` |
| Pure field | [@looking](https://openshaders.com/@looking) | 淡紫层叠拱带；lavender folded arches and layered curved bands | 02:31:39.799 | `1b09e3fc` / `2a42c892` |
| Grain | [@tiangewang](https://openshaders.com/@tiangewang) | 粉色颗粒回环；fine pink grain with a warm loop and sweeping band | 02:28:39.890 | `598703ce` / `f7978959` |
| Grain | [@salvador](https://openshaders.com/@salvador) | 青蓝颗粒交叉细带；cyan-blue grain with narrow intersecting curved bands | 02:28:43.572 | `e9e50528` / `83e7a3ff` |
| Grain | [@sage](https://openshaders.com/@sage) | 铜橙颗粒起伏；copper-orange grain with broad rolling lobes | 02:28:47.117 | `a202fba8` / `4fb78387` |
| ASCII | [@oceanseth](https://openshaders.com/@oceanseth) | 薄荷绿字符环；mint character-grid ring built from tiny numeric-like glyphs | 02:29:00.515 | `b47bf133` / `e66ae9b6` |
| ASCII | [@arkplatforms](https://openshaders.com/@arkplatforms) | 橙色加号折带；orange plus-shaped glyphs forming an angular turning band | 02:29:04.002 | `d7d0c5fc` / `26cd3d63` |
| ASCII | [@capythulhu](https://openshaders.com/@capythulhu) | 品红星形字符弧；magenta star and plus glyphs forming broad rounded arcs | 02:29:07.741 | `eedf68ad` / `a8241487` |
| Dither | [@futuraforma](https://openshaders.com/@futuraforma) | 蜜桃金抖动同心流；peach-gold dithered concentric rounded flow | 02:29:20.501 | `ebb158c6` / `91867665` |
| Dither | [@ctwhome](https://openshaders.com/@ctwhome) | 青蓝抖动宽带；cyan-blue dithered wide bent ribbon | 02:29:24.402 | `d7d895f8` / `ba2609e8` |
| Dither | [@jstar](https://openshaders.com/@jstar) | 绿色抖动分叉；green dithered angular fork around triangular negative space | 02:29:28.078 | `b1187772` / `e5176f9c` |
| Halftone | [@lexie](https://openshaders.com/@lexie) | 蓝色细网点错层；fine blue halftone dots forming broad offset bands | 02:29:40.971 | `e81875e3` / `ee3b3e91` |
| Halftone | [@ironside](https://openshaders.com/@ironside) | 橙红密网点折脊；orange-red dense dot field with a folded warm ridge | 02:29:44.457 | `c56b42bd` / `3b43de8a` |
| Halftone | [@davey](https://openshaders.com/@davey) | 蓝紫网点斜浪；violet-blue dot field with a diagonal wave crest | 02:29:48.038 | `eeec66d1` / `c9ce978f` |
| Sparkle | [@raja](https://openshaders.com/@raja) | 玫瑰色稀疏星点；sparse star-like points over a soft rose background | 02:30:05.409 | `51a00526` / `72dc13df` |
| Sparkle | [@andrevenancio](https://openshaders.com/@andrevenancio) | 蓝粉棱彩交叉星点；tiny stars over intersecting blue-pink prismatic bands | 02:30:08.881 | `1bd8b11f` / `573f9662` |
| Liquid | [@erkam](https://openshaders.com/@erkam) | 青蓝液态亮边；blue-cyan soft liquid channel with a wavering bright edge | 02:30:12.459 | `6ab06acc` / `e8d7a10c` |
| Liquid | [@zaid](https://openshaders.com/@zaid) | 桃紫液态沟槽；peach-pink and purple liquid channels with irregular boundaries | 02:30:38.536 | `ad078cc7` / `3ac86b68` |
| Liquid | [@nirjxr](https://openshaders.com/@nirjxr) | 粉紫液池光泽褶皱；lilac-pink pooled shapes and glossy rounded creases | 02:30:41.939 | `51388312` / `45d5ba4d` |
| Mosaic | [@rightwayon](https://openshaders.com/@rightwayon) | 绿色大块像素；green pixel blocks forming broad geometry | 02:30:45.296 | `44ebd74a` / `77c35194` |
| Mosaic | [@bonuscloudpt](https://openshaders.com/@bonuscloudpt) | 青色阶梯像素带；cyan stepped pixel ribbons with pronounced block edges | 02:31:03.174 | `9abe7d18` / `815233b1` |
| Chroma | [@shawn_chen](https://openshaders.com/@shawn_chen) | 黄粉虹彩层叠折面；yellow-pink sharp stacked iridescent folds | 02:31:06.808 | `c77f984e` / `fc1f47df` |
| Chroma | [@cry](https://openshaders.com/@cry) | 蓝紫色散分叉轮廓；blue-purple chromatic branching liquid contours | 02:31:10.207 | `5fadc9da` / `4b9ea2dd` |

## 证据与健康检查

每个页面均通过官方 Explore 分类筛选发现，先比较同类候选，再访问其独立 URL。最后一轮成功检查均完成：

1. 页面出现正确的 `@handle` 标题，未重定向到其他案例。
2. 等待 1500 ms 后，直接观察到动画色场和可见 canvas；背板为 1612 × 1007，CSS 尺寸约 815 × 509。
3. 两次整页截图间隔 700 ms，指纹不同；结论同时依赖直接视觉观察，不仅依赖页面像素差异。
4. 打开代码导出菜单，观察到四种格式。未把“菜单可用”写成“导出代码测试通过”。

最终状态为 `render_verified`。早期未充分等待、裁切错误或空菜单的尝试已被成功重试替代。Dither 索引曾出现一次加载失败，点击公开的 Try again 后恢复；不据此将整个站点标为失效。没有记录未经观察的网络状态码或控制台检查结论。

JSON 中 `running_animations=0` 仅为现有 schema 的计数字段占位（未测量 CSS 动画数量），不能解读为页面静止。实际动效证据为 canvas 的直接视觉观察和截图对照；此限制同时保存在每条记录的 `verification.limitations`。

## 维护与发布说明

- 本批仅保存公开链接、语义元数据与审核信息，不保存第三方截图、视频、着色器代码或资源。
- 搜索仍采用原有跨来源与近似家族去重策略；ASCII 作为字符纹理背景，不误标为文字入场动效。
- 独立 Catalog 的 manifest 仍是本地待发布草案。其增量摘要以该仓库已提交的 `2026.08.9` 为基准，包含既有未发布的 ThreeUI、Circle Loaders 和本批 OpenShaders：新增 3 个来源、63 条案例。
- 发布需另行授权；发布时重建时间戳、确定性 gzip 资源与 SHA-256，并先上传不可变资源，再公开 manifest。

## 本地验收结果

- Catalog schema / 65 类动效引用 / 3719 条案例校验通过；原有 3695 条 JSONL 字节保持为新文件的完整前缀，原有 25 个来源对象保持不变。
- 24 个新增 ID 与直达 URL 唯一，9 类数量符合清单；源码、已安装 Skill 和独立 Catalog 的数据文件逐字节一致。
- 已安装 Skill 的实际搜索使用 bundled 目录 2026.09.12；9 类“效果名＋背景”查询均能召回相应 OpenShaders 案例，并遵守单来源最多 3 条的初筛上限。
- Skill 结构校验、来源均衡校验、52 项单元测试、两个仓库的 `git diff --check` 均通过。新增数据改变了合理排序，因此将旧测试的固定前三名限制改为检查液态背景相关性，同时保留旧案例可召回的断言；搜索代码未改动。
- 本地待发布 manifest schema、sites SHA-256、gzip SHA-256、解压内容 SHA-256 与往返一致性检查通过。未进行远程发布或下载验证。
- Catalog 仍有 Motion、Animista、React Bits 三条既有的来源级深审日期提醒，本次未扩大为历史全库重审。
