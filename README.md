# my-website — 滕老师个人网站

- **网址**：https://tengzhuguo.pages.dev
- **托管**：Cloudflare Pages（连 GitHub，自动部署）
- **仓库**：https://github.com/tengzhuguotzg-rgb/my-website
- **本地源**：`C:\Users\TZG\.openclaw\media\output\my-website\`

## 目录结构

```
/ → 首页 index.html（v3.0，滕老师定的最终版）
/病例讨论/
   case-凌正秀.html → 第一个成品病例讨论 PPT 式 HTML
/其它知识地图、课件等 → 其他页面
```

## 病例讨论 HTML 模板（case-凌正秀.html）

### 基本架构
- **单 HTML 文件**，所有 CSS/JS 内嵌，无外部依赖
- 固定画布 1000×562.5（--slide-w / --slide-h CSS 变量）
- JS `scaleViewport()` 根据窗口大小等比缩放
- 每页 slide 为 absolute 定位在 viewport 内，支持 34 页

### 桌面端布局
```
body (flex column, 100vh)
├── .topbar（毛玻璃，无 sticky）
├── .progress-wrap（顶部进度条）
├── .slide-container（flex:1 撑满）
│   ├── .slide-sidebar（左侧缩略图栏 270px）
│   └── .slide-viewport-wrap（flex:1）
│       └── .slide-viewport（1000×562.5 基准）
│           └── .slide（absolute inset:0）
├── .slide-img-hint → 桌面端 display:none
├── .bottom-bar（导航+全屏按钮）
├── button.fs-exit-btn（全屏退出）
└── .lightbox（图片放大）
```

### 手机端布局（≤900px）
- `--slide-w: 400px; --slide-h: 225px`（缩小基准经 scale 到合适大小）
- 不用 `aspect-ratio: 16/9`，靠 JS scale 统一缩放
- `slide-container { flex-direction:column; flex:0 0 auto }` 自然高度
- `slide-viewport-wrap { flex:0 0 auto; padding:30px 32px 0 }` 靠上+两侧留白
- 缩略图条（thumb-strip）显示在 slide 上方，宽度 240px（1.5x）
- `slide-img-hint` 在 container 内部最下方

### 全屏旋转（所有设备通用）
- 不依赖 `screen.orientation.lock()`（华为成功、iPhone 失败，行为不一致）
- 竖屏全屏始终加 `body.fs-rotated` 类
- CSS 旋转：`.fs.fs-rotated .slide-viewport { rotate(90deg) }`
- 旋转后尺寸：`width:calc(100vh-64px) × height:calc(100vw-64px)`（避刘海）
- `doLock()` 先清空 `vp.style.transform`（防 inline scale 覆盖）
- 此时 `scaleViewport()` 跳过（检测到 fs-rotated 直接 return）

### 退出全屏按钮
- 圆形 ⛶ 图标（32×32），不依赖文字方向
- `position:fixed; bottom:16px; right:16px`
- 物理右下 = 视觉横屏右上角（旋转 90° 后对的）
- 不加 rotate 变形（圆形图标不需要）

### Lightbox（图片放大）
- 点击图片弹 lightbox，支持 ← → 切换同组图片
- 全屏+旋转模式下 `.lb-stage` 同技巧旋转 90°
- 提示文字已删除（简洁）

### 缩略图 sidebar / strip
- 桌面端：左侧 270px 缩略图栏，`position:sticky` 滚动
- 手机端：横向 thumb-strip 滑动条
- 缩略图内容从实际 slide 克隆

### 翻页
- 左侧/右侧点击翻页
- 滚轮翻页（即使光标在图片区也能翻）
- 左右键翻页
- 触摸滑动翻页
- 全屏下点击/滚轮翻页+点击图片仍弹 lightbox

### 复刻步骤（做第二个病例讨论）
1. 复制 `case-凌正秀.html` 为 `case-XXX.html`
2. 改 `<title>` 标签文字
3. 改面包屑：`.crumb` 内的文字
4. 改 topbar brand 区域的文字
5. 改封面页（data-index="0"）：
   - `center-title` → 病例名
   - `center-sub` → 科室
   - decorator 横线（inline style）
   - `center-sub small` → 日期
6. 替换 34 页 slide 内容，每页保留：
   - `.slide-mfs` 按钮 <!—必须要有，全屏触发用 —>
   - `.meta-label` 或 `.slide-subtitle`
   - `.slide-title-bar`
   - `.slide-title`
7. 图片放到 `images/case-XXX/` 目录，更新 `<img src="...">`
8. 图片网格用 `.img-grid.c1/c2/c3/c4/c5` 类控制列数
9. 修改 JS 里的 `.thumb-strip` 和 `.thumb-wrap` 构建逻辑（如需）

### 重要教训（2026-06-10 积累）
1. **scaleViewport 用 `.slide-viewport-wrap`，不是 `.slide-container`** —— 后者把 sidebar 宽度算进缩放基准，导致 slide 左溢出被 sidebar 遮挡
2. **手机端不要用 aspect-ratio:16/9** —— 固定基准 + JS scale 保证所有缩放路径一致，文字/图片/边距同步
3. **inline transform 优先级高于 CSS** —— scaleViewport 写入 transform:scale(s) 后，CSS rotate(90deg) 盖不过，导致华为全屏不旋转。必须在 `doLock()` 里先清 `vp.style.transform`
4. **全屏时不要依赖 orientation.lock 的结果** —— 华为（成功）和 iPhone（失败）行为不同，统一用 CSS rotate 保证一致
5. **圆形容器无方向性问题** —— 退出按钮用圆形图标之后，不需要任何 rotate 补偿
6. **绝对定位元素的组群关系** —— subtitle@30 + titleBar@50 + title@78 组成页眉，要按 viewport 基准比例缩放
7. **所有值用 CSS 变量统一管理** —— `--slide-w` 和 `--slide-h` 在手机上覆盖为 400×225，其他值按比例缩放

## 其他页面说明

### 首页（index.html）
- v3.0 最终版，滕老师定的
- 四个入口卡片：病例讨论 / 灌注知识地图 / 期刊简报 / 课件
- 圆角 + 灰绿配色

### 知识地图、课件、期刊简报等
- 单独 HTML，有各自的功能
- 颜色风格统一（灰绿 + 橘橙，同 case-凌正秀 的配色）

## 部署
- 修改本地文件 → `git add → commit → push`
- Cloudflare Pages 自动检测 main 分支变更后部署（30-60 秒）
- 访问 `*.pages.dev` 不需要翻墙
