# 病例图片 PII 脱敏 SOP（通用版）

> **适用对象**：任意 `病例讨论/*.html` 中内嵌图片的脱敏处理。
> **目标读者**：能读中文、能调 Python/PIL、能调 vision 模型的 AI agent。
> **首次成文**：2026-06-13 ｜ **核心教训**：2026-06-13 case-张建中.html slide12_08.png 机械套 30% 裁掉报告正文

---

## 0. TL;DR（30 秒速查）

| 问 | 答 |
|---|---|
| 最重要原则是什么？ | **报告内容 > PII 脱敏**。宁可 PII 残留一点点，绝不能把临床内容裁掉。 |
| 能不能套固定百分比？ | **不能**。每张图单独判断 PII 边界。 |
| 备份吗？ | **必须**。脱敏前先复制到 `temp/<case-slug>-redact-bak/`，加 `.original.png` 后缀。 |
| 裁完怎么知道对不对？ | **用 vision 模型**（image 工具）逐张验证 4 项检查。 |
| 有疑问怎么办？ | **停下来问滕老师**，不要猜。 |

---

## 1. 通用约定

### 1.1 假设的文件结构

任意病例 HTML 都有这个结构（如果不一样，先停下来问）：

```
<ROOT>/病例讨论/
├── <case-slug>.html              ← 病例 HTML 文件
└── images/
    └── <case-slug>/              ← 该病例的图片目录
        ├── slideNN_XX.png        ← 脱敏后的图（HTML 引用这个）
        └── ...

<WORKSPACE>/temp/
└── <case-slug>-redact-bak/       ← 备份目录（不存在就创建）
    ├── slideNN_XX.original.png   ← 脱敏前的原图
    └── ...
```

- `<ROOT>` 默认为 `C:\Users\TZG\.openclaw\media\output\my-website\`
- `<WORKSPACE>` 默认为 `C:\Users\TZG\.openclaw\workspace\`

### 1.2 文件命名规则

```
slideNN_XX.png
│   │   │
│   │   └── XX = 图片在该 slide 里的序号（01, 02, 03...）
│   └────── NN = slide 的 data-index（HTML 里 <div class="slide" data-index="N">）
└────────── 字面前缀 "slide"
```

例：
- `slide07_02.png` = slide 7 的第 2 张图
- `slide12_08.png` = slide 12 的第 8 张图

### 1.3 必备工具

- Python 3.11+，装好 `PIL`、`numpy`
- vision 模型（OpenClaw `image` 工具）
- 不要用 PowerShell 做文件 IO（含中文路径会被损坏编码）

---

## 2. 分类决策树（AI 必走）

**打开原图第一件事：判断它是哪一类。** 不同类别走不同分支。

```
原图打开 → 它是什么？
│
├─ 包含表格（多列、有"序号"列、有数值列）
│   ├─ 顶部是 PII 行（医生姓名/标本/诊断）？
│   │   → 【化验报告】→ 走 §3.1
│   ├─ 顶部是医院抬头（医院名 + 病人信息块）？
│   │   → 【医嘱单 / 处方】→ 走 §3.4
│   └─ 顶部是护士记录 / 时间戳
│       → 【护理记录 / 体温单】→ 走 §3.4
│
├─ 包含波形（折线 / 12 导联 ECG）
│   → 【心电图】→ 走 §3.2
│
├─ 灰度大图（黑白色调 + 大块影像区域）
│   → 【CT / MRI / X-ray / 超声】→ 走 §3.3
│
├─ 全文都是文字 + 签名 / 印章
│   → 【知情同意书 / 签字页】→ 走 §3.5（**不要试图脱敏，整张删除**）
│
└─ 彩色照片
    → 【手术 / 内镜 / 病理 / 病人照片】→ 走 §3.6（**必须问滕老师**）
```

**判断不出来时**：停下来问滕老师，不要硬猜。

---

## 3. 各类脱敏详细流程

### 3.1 化验报告（最常见）

**结构**：
```
┌──────────────────────────────────────┐
│ 顶部 PII 行（医生/标本/诊断）         │  ← 100% PII，必须全裁
├──────────────────────────────────────┤
│ 表格标题行（序号/项目/缩写/结果/...） │  ← 100% 临床内容，必须全留
├──────────────────────────────────────┤
│ 序号 1 钾 K       5.62 ↑ mmol/L ... │
│ 序号 2 钠 Na      ...               │  ← 全部必须保留
│ ...                                  │
│ 序号 N B型钠尿肽前体 >35000 ...     │
├──────────────────────────────────────┤
│ 底部声明（本检验结果仅反映...）       │  ← 必须保留
└──────────────────────────────────────┘
```

**核心算法**：找第一条"贯穿左右的水平黑线"（一行 70%+ 像素灰度 < 100），裁顶部到这条线 + 5px padding。

**完整代码**（直接 copy-paste）：

```python
from PIL import Image
import numpy as np
import os

def redact_lab_report(src, dst, padding=5):
    """
    化验报告脱敏：自动找 PII 边界，只裁顶部 PII
    
    Args:
        src: 原图绝对路径（必须已备份到 .original.png）
        dst: 输出绝对路径
        padding: PII 分界线外额外留白（像素），建议 5
    Returns:
        dict: {pii_end_y, cropped_top_px, original_size, new_size}
    Raises:
        ValueError: 找不到 PII 分界线时
    """
    img_gray = Image.open(src).convert('L')
    arr = np.array(img_gray)
    h, w = arr.shape
    
    # 找第一条贯穿左右的黑线
    pii_end = None
    for y in range(h):
        row = arr[y, :]
        dark_ratio = np.sum(row < 100) / w
        if dark_ratio > 0.7:
            pii_end = y
            break
    
    if pii_end is None:
        raise ValueError(
            f'没找到 PII 分界线！请检查 {src} 是否真的是化验报告。\n'
            f'如果确实不是化验报告，请改用其他 §3.x 方法。'
        )
    
    crop_top = max(0, pii_end - padding)
    
    img = Image.open(src)
    new_img = img.crop((0, crop_top, w, h))
    new_img.save(dst)
    
    return {
        'pii_end_y': pii_end,
        'cropped_top_px': crop_top,
        'cropped_top_pct': round(crop_top / h * 100, 2),
        'original_size': (w, h),
        'new_size': (w, h - crop_top)
    }

# 用法
result = redact_lab_report(
    src=r'<CASE_DIR>\images\<case-slug>\slide12_08.original.png',
    dst=r'<CASE_DIR>\images\<case-slug>\slide12_08.png'
)
print(result)
# {'pii_end_y': 40, 'cropped_top_px': 35, 'cropped_top_pct': 5.58, ...}
```

### 3.2 心电图

**结构**：
```
┌──────────────────────────────────────┐
│ 顶部 PII 块（医院名/病人信息/参数/签名）│  ← 厚 ~30%，全 PII
├──────────────────────────────────────┤
│ 12 导联波形 + 测量值                  │  ← 核心临床内容
├──────────────────────────────────────┤
│ 底部报告说明 / 打印时间               │  ← 保留
└──────────────────────────────────────┘
```

**核心算法**：固定裁顶部 30%（心电图的 PII 块通常就是顶部 30%），但**必须**用 vision 验证波形完整。

**代码**：

```python
from PIL import Image

def redact_ecg(src, dst, top_pct=0.30):
    """心电图脱敏：裁顶部固定 30%（必须 vision 验证）"""
    img = Image.open(src)
    w, h = img.size
    crop_top = int(h * top_pct)
    new_img = img.crop((0, crop_top, w, h))
    new_img.save(dst)
    return {
        'crop_top_px': crop_top,
        'crop_top_pct': top_pct * 100,
        'original_size': (w, h),
        'new_size': (w, h - crop_top)
    }
```

**裁完必做 vision 验证**：
- 12 导联波形完整（不能少任何一导联）
- 没有半截字 / 半截波形
- 异常标注（↑↓）可见

### 3.3 影像（CT / MRI / X-ray / 超声）

**PII 分布**：四角 + 边缘散落（医院 logo / 病人信息 / 检查参数）

**核心算法**：**不裁剪，改涂黑四角**。中央 80% 影像区域 0 容忍遮挡。

**代码**：

```python
from PIL import Image, ImageDraw

def redact_medical_image(src, dst, corner_pct=0.10):
    """
    影像脱敏：四角涂黑
    
    Args:
        corner_pct: 角落黑块边长占图片短边的百分比，建议 0.08-0.12
    """
    img = Image.open(src).convert('RGBA')
    w, h = img.size
    corner = int(min(w, h) * corner_pct)
    draw = ImageDraw.Draw(img)
    for x1, y1, x2, y2 in [
        (0, 0, corner, corner),                           # 左上
        (w - corner, 0, w, corner),                       # 右上
        (0, h - corner, corner, h),                       # 左下
        (w - corner, h - corner, w, h),                   # 右下
    ]:
        draw.rectangle([(x1, y1), (x2, y2)], fill='black')
    img.save(dst)
    return {'corner_size_px': corner, 'image_size': (w, h)}
```

**注意**：如果 PII 不在四角（比如嵌入在影像正文中），先停下来问滕老师。

### 3.4 医嘱单 / 处方 / 护理记录

**结构**：
```
┌──────────────────────────────────────┐
│ 医院抬头（医院名 + logo）            │  ← 裁
├──────────────────────────────────────┤
│ 病人信息行（姓名/床号/ID）            │  ← 裁
├──────────────────────────────────────┤
│ 表格主体（医嘱内容 / 时间 / 用法）    │  ← 必须保留
├──────────────────────────────────────┤
│ 执行签名 / 医生签名                   │  ← 裁
└──────────────────────────────────────┘
```

**核心算法**：裁顶部 + 裁底部。**中间表格绝不能动**。

**代码**：

```python
from PIL import Image

def redact_medical_form(src, dst, top_pct=0.10, bottom_pct=0.05):
    """
    医嘱单/处方脱敏：裁顶部抬头 + 裁底部签名
    
    Args:
        top_pct: 顶部裁掉比例（医院抬头 + 病人信息）
        bottom_pct: 底部裁掉比例（签名区）
    """
    img = Image.open(src)
    w, h = img.size
    top = int(h * top_pct)
    bottom = h - int(h * bottom_pct)
    new_img = img.crop((0, top, w, bottom))
    new_img.save(dst)
    return {
        'crop_top_px': top,
        'crop_bottom_px': h - bottom,
        'new_size': (w, bottom - top)
    }
```

### 3.5 知情同意书 / 签字页

**处理**：**整张删除 / 不展示到公开网站**。

理由：PII 和内容高度交织（病人签名 / 身份证号 / 家庭信息），任何局部脱敏都不可靠。

**操作**：
- HTML 里删掉对应的 `<div class="img-wrap">`
- 图片文件不复制到 `images/<case-slug>/`

### 3.6 临床照片（手术 / 内镜 / 病理 / 病人照片）

**AI 自动处理不了** —— PII 位置因图而异（面部、腕带、病理号、日期戳）。

**操作**：**停下来问滕老师**。在任务里明确说明"哪张图是临床照片，等用户告知 PII 位置"。

如果滕老师给了 mask 区域（"涂黑这里"），用：

```python
from PIL import Image, ImageDraw

def redact_photo_with_mask(src, dst, mask_regions):
    """
    临床照片脱敏：按指定区域涂黑
    
    Args:
        mask_regions: list of (left, top, right, bottom) 元组，像素坐标
    """
    img = Image.open(src).convert('RGBA')
    draw = ImageDraw.Draw(img)
    for region in mask_regions:
        draw.rectangle(region, fill='black')
    img.save(dst)
```

---

## 4. 验证流程（每张图必做，4 步）

### 4.1 vision 验证（必做）

调用 `image` 工具，**逐张**打开裁后的图，问这 4 个问题：

1. **PII 清单** —— 出现任意一项 = **失败**
   - 病人姓名 / 住院号 / 病案号 / 床号
   - 性别 / 年龄 / 出生日期
   - 身份证号 / 联系电话
   - 主治医生姓名 / 签名
   - 医院名称 / logo

2. **内容完整性** —— 缺任意一项 = **失败**
   - 化验报告：能看到表头 + 序号 1 + ... + 序号 N + 底部声明
   - 心电图：12 导联波形 + 测量值
   - 影像：中央影像区域无遮挡
   - 医嘱单：表格主体完整

3. **视觉检查** —— 出现任意一项 = **失败**
   - 有"半截字" / "半截行"
   - 黑边 / 白边不均匀
   - 在 HTML 里渲染时变形

4. **PII 残留 vs 内容损坏的取舍**
   - 如果两项冲突：**内容完整性 > PII 残留**
   - 例：宁可 PII 残留一点，也绝不能裁到序号 1

### 4.2 HTML 渲染验证

打开 HTML 实际看：
- 图片能正常显示
- 比例正确
- 在 c2/c3/c4/c5 不同 grid 里都不变形

### 4.3 滕老师审核

让滕老师过目 1 次。这是**最后一道关**。

---

## 5. 备份策略

### 5.1 备份时机

**脱敏前** 100% 备份，**脱敏后** 不动 bak 目录。

### 5.2 备份路径

```
<WORKSPACE>/temp/<case-slug>-redact-bak/
```

### 5.3 备份命名

```
slideNN_XX.original.png   ← 脱敏前原图（保留）
slideNN_XX.png            ← 脱敏后（HTML 引用这个）
```

### 5.4 还原方法

如果搞砸了：
```python
import shutil
shutil.copy2(
    r'<WORKSPACE>\temp\<case-slug>-redact-bak\slideNN_XX.original.png',
    r'<ROOT>\病例讨论\images\<case-slug>\slideNN_XX.png'
)
```

---

## 6. 通用脚本：[`redact_images.py`](./redact_images.py)

> ⚠️ **脚本已抽离成独立文件**：`C:\Users\TZG\.openclaw\media\output\my-website\病例讨论\redact_images.py`
>
> **请直接用脚本，不要再复制下面这段模板代码。** 脚本是下面这段模板的**完整可跑版**（带错误检查、备份逻辑、dry-run、restore、help、统计等），代码一改两处容易漂。

### 6.1 脚本用法（4 步）

1. 用编辑器打开 `redact_images.py`
2. 改顶部 `CASE_SLUG = '<case-slug>'` → 实际值（如 `'zhangjianzhong'`）
3. 在 `IMAGES_CONFIG` 列表里填要脱敏的图：
   ```python
   IMAGES_CONFIG = [
       {'slide': '12_08', 'filename': 'slide12_08.png', 'type': 'lab'},
       {'slide': '12_09', 'filename': 'slide12_09.png', 'type': 'ecg'},
       # ...
   ]
   ```
4. 跑：
   ```bash
   python redact_images.py --dry-run   # 演练，不动文件
   python redact_images.py             # 真跑
   ```

### 6.2 脚本能力

- ✅ 自动备份原图到 `<WORKSPACE>/temp/<case-slug>-redact-bak/`
- ✅ 自动按 type 选对应脱敏函数
- ✅ 脱敏后**自动打印** vision 验证 prompt（直接复制去问 image 工具）
- ✅ 出错时打印**清晰的错误信息**（比如找不到 PII 边界 → 提示是不是选错类型）
- ✅ 跑完打印统计（成功 N / 失败 N / 跳过 N）

### 6.3 命令行参数

| 参数 | 作用 |
|------|------|
| `(无)` | 跑脱敏 |
| `--dry-run` | 只打印不写文件 |
| `--restore` | 从 bak 还原所有图 |
| `--restore 12_08` | 从 bak 还原文件名含 `12_08` 的图 |
| `--help` | 打印脚本用法 |

### 6.4 脚本内部结构

脚本包含 §3 的所有 4 个脱敏函数（化验/心电/影像/医嘱），代码是 readme §3 的逐字版（带边界检查 + 错误提示）。函数名和签名：
- `redact_lab_report(src, dst, padding=5)`
- `redact_ecg(src, dst, top_pct=0.30)`
- `redact_medical_image(src, dst, corner_pct=0.10)`
- `redact_medical_form(src, dst, top_pct=0.10, bottom_pct=0.05)`

---

## 6.x 旧版模板（仅供历史参考，不推荐）

> 以下是初版嵌在 readme 里的代码模板。**已抽离到 `redact_images.py`**，保留是为了让后来人能看懂脚本的内部结构。

```python
"""
通用脱敏脚本模板
- 修改 CASE_SLUG 和 IMAGES_CONFIG 即可
- 支持 lab / ecg / image / form 四种类型
- 自动备份，自动验证提示
"""
import os
import shutil
from PIL import Image
import numpy as np

# ====== 用户配置区 ======
CASE_SLUG = '<case-slug>'  # 例: 'zhangjianzhong'
ROOT = r'C:\Users\TZG\.openclaw\media\output\my-website'
WORKSPACE = r'C:\Users\TZG\.openclaw\workspace'
CASE_DIR = os.path.join(ROOT, '病例讨论')
IMG_DIR = os.path.join(CASE_DIR, 'images', CASE_SLUG)
BAK_DIR = os.path.join(WORKSPACE, 'temp', f'{CASE_SLUG}-redact-bak')
os.makedirs(BAK_DIR, exist_ok=True)

# ====== 脱敏函数（§3 各小节已完整列出） ======
# (此处省略函数定义，复用 §3.1 / §3.2 / §3.3 / §3.4)

# ====== 批量入口 ======
def batch_redact(images_config):
    """
    images_config: list of dicts
    [
        {'slide': '12_08', 'type': 'lab', 'filename': 'slide12_08.png'},
        {'slide': '12_09', 'type': 'ecg', 'filename': 'slide12_09.png'},
        ...
    ]
    """
    for cfg in images_config:
        src = os.path.join(IMG_DIR, cfg['filename'])
        bak_src = os.path.join(BAK_DIR, f"{cfg['filename'].rsplit('.', 1)[0]}.original.png")
        
        # 1. 备份（如果还没备份）
        if not os.path.exists(bak_src):
            shutil.copy2(src, bak_src)
            print(f'[备份] {cfg["filename"]} -> {os.path.basename(bak_src)}')
        
        # 2. 脱敏
        if cfg['type'] == 'lab':
            result = redact_lab_report(bak_src, src)
        elif cfg['type'] == 'ecg':
            result = redact_ecg(bak_src, src)
        elif cfg['type'] == 'image':
            result = redact_medical_image(bak_src, src)
        elif cfg['type'] == 'form':
            result = redact_medical_form(bak_src, src)
        else:
            print(f'[跳过] {cfg["slide"]}: 未知类型 {cfg["type"]}')
            continue
        
        print(f'[完成] {cfg["slide"]} ({cfg["type"]}): {result}')
        print(f'  → 下一步：用 vision 模型验证')

# ====== 用法 ======
if __name__ == '__main__':
    IMAGES_CONFIG = [
        # 修改这里
        {'slide': '12_08', 'type': 'lab', 'filename': 'slide12_08.png'},
    ]
    batch_redact(IMAGES_CONFIG)
```

---

## 7. 常见错误（必读）

### 错误 1：套固定百分比
- ❌ 所有化验报告都裁 30%
- ✅ 每张图先用 PIL 找 PII 边界

### 错误 2：裁完不验证
- ❌ 裁完直接保存
- ✅ **必须**用 vision 模型验证 4 项

### 错误 3：忘记备份
- ❌ 直接覆盖原图
- ✅ 脱敏前**先**复制到 bak 目录

### 错误 4：把 PII 残留当小事
- ❌ "有一点点没关系"
- ✅ 病人姓名 / ID / 住院号 = 0 容忍

### 错误 5：把内容损坏当小事
- ❌ "少一两项不重要"
- ✅ 临床信息 = 0 容忍，缺一项都不行

### 错误 6：批量处理不分类
- ❌ 一次脚本处理所有图
- ✅ 先分类（§2 决策树），分类不同的图用不同方法

### 错误 7：用 PowerShell 写文件
- ❌ `Set-Content` / `Out-File` 改含中文路径的文件
- ✅ 用 Python 或 OpenClaw 的 `read` / `write` 工具

---

## 8. 给 AI 的硬性 DO / DON'T

### ✅ DO
1. **先看原图**再决定策略（用 vision 模型）
2. **每张图单独判断** PII 边界
3. **脱敏前先备份**
4. **脱敏后用 vision 验证**
5. **有疑问停下来问滕老师**
6. **报告内容完整性 > PII 脱干净**
7. **记录每张图的处理结果**（裁了多少 / 涂了多大 / 为什么）

### ❌ DON'T
1. **不要套固定百分比**
2. **不要批量处理不验证**
3. **不要试图脱敏签字页 / 知情同意书**（整张删除）
4. **不要在没备份的情况下覆盖原图**
5. **不要假设"应该差不多"** —— 必须逐张验证
6. **不要用 PowerShell 改含中文路径的文件**
7. **不要自己编 PII 位置**（在临床照片里）

---

## 9. AI 执行清单（按顺序）

```
□ 1. 收到任务："脱敏 <HTML 文件>"
□ 2. 找到 HTML 文件
□ 3. grep 所有 <img src=...>，列出图片清单
□ 4. 确认 case 目录：images/<case-slug>/
□ 5. 创建备份目录：<WORKSPACE>/temp/<case-slug>-redact-bak/
□ 6. 全部原图复制到备份目录（加 .original.png 后缀）
□ 7. 用 vision 工具逐一打开原图
□ 8. 按 §2 决策树分类
□ 9. 按 §3 选对应方法处理
□ 10. 覆盖 images/<case-slug>/slideNN_XX.png
□ 11. 用 vision 工具逐一验证 §4 的 4 项检查
□ 12. 打开 HTML 实际看渲染
□ 13. 写处理报告：哪些图、什么类型、裁了多少、验证结果
□ 14. 等滕老师最终审核
```

---

## 10. 验证 prompt 模板（vision 模型问法）

对每张裁后的图，问这些问题（直接复制到 vision 工具）：

```
请回答以下问题：
1. 这张图是什么类型的报告？（化验报告/心电图/影像/医嘱单/其他）
2. 顶部是否还包含 PII？（病人姓名/医生姓名/身份证号/住院号/医院名）
   - 如果有：列出具体内容
3. 报告的第一个项目（序号 1）是否完整可见？
   - 如果不可见：实际从哪个序号开始？
4. 报告的最后一项（序号 N）是否完整可见？
5. 底部声明 / 报告说明是否还在？
6. 有没有"半截字" / "半截行"？
7. 整体看起来是否专业、可用于教学？
```

---

## 11. 相关文件

| 文件 | 用途 |
|------|------|
| **`redact_images.py`** | 通用脱敏脚本（直接 `python redact_images.py` 跑） |
| `readme.md` | 本文档（SOP）|
| `*.html` | 各病例 HTML |
| `images/<case-slug>/` | 各病例的图片目录 |
| `<WORKSPACE>/temp/<case-slug>-redact-bak/` | 备份目录（脚本自动管理） |
| `~/.self-improving/corrections.md` | 2026-06-13 20:51 教训原文 |
| `MEMORY.md` | 长期记忆 |
