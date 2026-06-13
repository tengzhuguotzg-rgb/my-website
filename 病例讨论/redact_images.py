"""
redact_images.py - 病例图片 PII 脱敏通用工具

用法：
    1. 修改下面的 CASE_SLUG 和 IMAGES_CONFIG
    2. 跑：python redact_images.py
    3. 每张图脱敏完，脚本会打印 vision 验证 prompt，复制去问 image 工具

支持类型：
    - lab      : 化验报告（自动找 PII 边界）
    - ecg      : 心电图（固定裁顶部 30%）
    - image    : 影像（CT/MRI/X-ray）四角涂黑
    - form     : 医嘱单/处方（裁顶部+底部）
    - skip     : 跳过（已处理过 / 不用脱敏）

详见同目录 readme.md §3-§6。
"""

import os
import sys
import shutil
from PIL import Image, ImageDraw
import numpy as np


# ============================================================================
# 用户配置区
# ============================================================================
CASE_SLUG = '<case-slug>'  # 例: 'zhangjianzhong', 'lingzhengxiu'
ROOT = r'C:\Users\TZG\.openclaw\media\output\my-website'
WORKSPACE = r'C:\Users\TZG\.openclaw\workspace'

CASE_DIR = os.path.join(ROOT, '病例讨论')
IMG_DIR = os.path.join(CASE_DIR, 'images', CASE_SLUG)
BAK_DIR = os.path.join(WORKSPACE, 'temp', f'{CASE_SLUG}-redact-bak')

# 占位符检测：未替换时不建目录
PLACEHOLDER = CASE_SLUG.startswith('<') and CASE_SLUG.endswith('>')

# 待脱敏图片清单
# 字段：
#   - slide   : 标签，仅用于日志
#   - filename: 文件名（在 IMG_DIR 下）
#   - type    : lab / ecg / image / form / skip
#   - kwargs  : 可选，覆盖默认参数 (top_pct / corner_pct / padding ...)
IMAGES_CONFIG = [
    # === 化验报告示例 ===
    # {'slide': '12_08', 'filename': 'slide12_08.png', 'type': 'lab'},

    # === 心电图示例 ===
    # {'slide': '08_05', 'filename': 'slide08_05.png', 'type': 'ecg', 'kwargs': {'top_pct': 0.30}},

    # === 影像示例 ===
    # {'slide': '19_14', 'filename': 'slide19_14.png', 'type': 'image', 'kwargs': {'corner_pct': 0.10}},

    # === 医嘱单示例 ===
    # {'slide': '20_15', 'filename': 'slide20_15.png', 'type': 'form', 'kwargs': {'top_pct': 0.10, 'bottom_pct': 0.05}},
]


# ============================================================================
# 脱敏函数（详见 readme.md §3）
# ============================================================================
def find_pii_boundary(img_path):
    """找化验报告的 PII 边界（第一条贯穿左右的黑线）。"""
    img_gray = Image.open(img_path).convert('L')
    arr = np.array(img_gray)
    h, w = arr.shape
    for y in range(h):
        if np.sum(arr[y, :] < 100) / w > 0.7:
            return y
    return None


def redact_lab_report(src, dst, padding=5):
    """
    化验报告脱敏：自动找 PII 边界，只裁顶部 PII。
    找不到 PII 边界时抛 ValueError。
    """
    pii_end = find_pii_boundary(src)
    if pii_end is None:
        raise ValueError(
            f'没找到 PII 分界线！请检查 {src} 是否真的是化验报告。\n'
            f'如果不是化验报告，请把 type 改成 ecg/image/form/skip。'
        )
    img = Image.open(src)
    w, h = img.size
    crop_top = max(0, pii_end - padding)
    new_img = img.crop((0, crop_top, w, h))
    new_img.save(dst)
    return {
        'method': 'lab',
        'pii_end_y': pii_end,
        'crop_top_px': crop_top,
        'crop_top_pct': round(crop_top / h * 100, 2),
        'original_size': (w, h),
        'new_size': (w, h - crop_top),
    }


def redact_ecg(src, dst, top_pct=0.30):
    """心电图脱敏：固定裁顶部 30%（必须 vision 验证）。"""
    img = Image.open(src)
    w, h = img.size
    crop_top = int(h * top_pct)
    new_img = img.crop((0, crop_top, w, h))
    new_img.save(dst)
    return {
        'method': 'ecg',
        'crop_top_px': crop_top,
        'crop_top_pct': round(top_pct * 100, 2),
        'original_size': (w, h),
        'new_size': (w, h - crop_top),
    }


def redact_medical_image(src, dst, corner_pct=0.10):
    """影像脱敏：四角涂黑，中央影像区域不动。"""
    img = Image.open(src).convert('RGBA')
    w, h = img.size
    corner = int(min(w, h) * corner_pct)
    draw = ImageDraw.Draw(img)
    for x1, y1, x2, y2 in [
        (0, 0, corner, corner),
        (w - corner, 0, w, corner),
        (0, h - corner, corner, h),
        (w - corner, h - corner, w, h),
    ]:
        draw.rectangle([(x1, y1), (x2, y2)], fill='black')
    img.save(dst)
    return {
        'method': 'image',
        'corner_size_px': corner,
        'image_size': (w, h),
    }


def redact_medical_form(src, dst, top_pct=0.10, bottom_pct=0.05):
    """医嘱单/处方脱敏：裁顶部抬头 + 裁底部签名，中间表格不动。"""
    img = Image.open(src)
    w, h = img.size
    top = int(h * top_pct)
    bottom = h - int(h * bottom_pct)
    new_img = img.crop((0, top, w, bottom))
    new_img.save(dst)
    return {
        'method': 'form',
        'crop_top_px': top,
        'crop_bottom_px': h - bottom,
        'new_size': (w, bottom - top),
    }


REDACTORS = {
    'lab': redact_lab_report,
    'ecg': redact_ecg,
    'image': redact_medical_image,
    'form': redact_medical_form,
}


# ============================================================================
# 验证 prompt 模板（详见 readme.md §10）
# ============================================================================
VISION_PROMPT = """请回答以下问题：
1. 这张图是什么类型的报告？（化验报告/心电图/影像/医嘱单/其他）
2. 顶部是否还包含 PII？（病人姓名/医生姓名/身份证号/住院号/医院名）
   - 如果有：列出具体内容
3. 报告的第一个项目（序号 1）是否完整可见？
   - 如果不可见：实际从哪个序号开始？
4. 报告的最后一项（序号 N）是否完整可见？
5. 底部声明 / 报告说明是否还在？
6. 有没有"半截字" / "半截行"？
7. 整体看起来是否专业、可用于教学？

判定标准：
- PII 出现任意一项 = 失败
- 内容缺任意一项 = 失败
- 宁可 PII 残留一点点，也不能让临床信息不完整"""


# ============================================================================
# 批量入口
# ============================================================================
def ensure_backup(src, bak_dst):
    """确保原图已备份。已存在不覆盖（保留最初的原图）。"""
    if os.path.exists(bak_dst):
        return False  # 已备份
    shutil.copy2(src, bak_dst)
    return True  # 新备份


def batch_redact(images_config, dry_run=False):
    """
    批量脱敏。

    Args:
        images_config: list of dicts (见 IMAGES_CONFIG)
        dry_run: True = 只打印不写文件
    """
    if PLACEHOLDER:
        print(f'[!] CASE_SLUG 还是占位符 "<case-slug>"，请先改成实际的 case 标识。')
        print(f'    例: CASE_SLUG = "zhangjianzhong"')
        return 1

    if not images_config:
        print(f'[!] IMAGES_CONFIG 是空的，请先填待脱敏图片清单。')
        print(f'    详见 {os.path.join(os.path.dirname(__file__), "readme.md")} §6')
        return 1

    os.makedirs(BAK_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)

    print(f'== 脱敏任务开始 ==')
    print(f'CASE_SLUG: {CASE_SLUG}')
    print(f'IMG_DIR:   {IMG_DIR}')
    print(f'BAK_DIR:   {BAK_DIR}')
    print(f'图片数量:  {len(images_config)}')
    print(f'DRY_RUN:   {dry_run}')
    print()

    success = 0
    failed = 0
    skipped = 0

    for i, cfg in enumerate(images_config, 1):
        slide = cfg.get('slide', '?')
        filename = cfg['filename']
        img_type = cfg.get('type', 'skip')
        kwargs = cfg.get('kwargs', {})

        src = os.path.join(IMG_DIR, filename)
        bak_name = filename.rsplit('.', 1)
        bak_name = f'{bak_name[0]}.original.{bak_name[1]}' if len(bak_name) == 2 else f'{filename}.original'
        bak_src = os.path.join(BAK_DIR, bak_name)

        print(f'[{i}/{len(images_config)}] {slide} ({img_type})')

        if img_type == 'skip':
            print(f'  [跳过] 标记为 skip')
            skipped += 1
            print()
            continue

        if not os.path.exists(src):
            print(f'  [错误] 找不到文件: {src}')
            failed += 1
            print()
            continue

        if img_type not in REDACTORS:
            print(f'  [错误] 未知类型: {img_type} (可选: {list(REDACTORS.keys())} / skip)')
            failed += 1
            print()
            continue

        # 1. 备份
        if dry_run:
            print(f'  [DRY] 备份: {src} -> {bak_src}')
        else:
            backed_up = ensure_backup(src, bak_src)
            if backed_up:
                print(f'  [备份] {filename} -> {bak_name}')
            else:
                print(f'  [备份] 已存在，跳过: {bak_name}')

        # 2. 脱敏（从 bak 读，输出到 src）
        redactor = REDACTORS[img_type]
        try:
            if dry_run:
                print(f'  [DRY] 脱敏: {bak_src} -> {src} (kwargs={kwargs})')
                result = {'dry_run': True}
            else:
                result = redactor(bak_src, src, **kwargs)
                print(f'  [完成] {result}')

            # 3. 打印验证 prompt
            print(f'  [验证] 请用 vision 模型打开 {src} 并问：')
            for line in VISION_PROMPT.split('\n'):
                print(f'    | {line}')

            if not dry_run:
                success += 1
        except ValueError as e:
            print(f'  [失败] {e}')
            failed += 1
        except Exception as e:
            print(f'  [失败] {type(e).__name__}: {e}')
            failed += 1

        print()

    print(f'== 脱敏任务完成 ==')
    print(f'成功: {success}  失败: {failed}  跳过: {skipped}')
    return 0 if failed == 0 else 1


def restore(slide_filter=None):
    """
    从 bak 还原所有（或指定）图片。
    用法：python redact_images.py --restore [slide_filter]
    """
    if PLACEHOLDER:
        print(f'[!] CASE_SLUG 还是占位符 "<case-slug>"，请先改成实际的 case 标识。')
        return 1

    if not os.path.isdir(IMG_DIR):
        print(f'[!] 图片目录不存在: {IMG_DIR}')
        return 1
    if not os.path.isdir(BAK_DIR):
        print(f'[!] 备份目录不存在: {BAK_DIR}')
        return 1

    print(f'== 还原任务 ==')
    print(f'从: {BAK_DIR}')
    print(f'到: {IMG_DIR}')
    print()

    count = 0
    for f in os.listdir(BAK_DIR):
        if not f.endswith('.original.png'):
            continue
        if slide_filter and slide_filter not in f:
            continue
        bak_path = os.path.join(BAK_DIR, f)
        # 还原文件名: slide12_08.original.png -> slide12_08.png
        target_name = f.replace('.original.png', '.png')
        target_path = os.path.join(IMG_DIR, target_name)
        shutil.copy2(bak_path, target_path)
        print(f'  [还原] {f} -> {target_name}')
        count += 1

    print(f'\n共还原 {count} 张图')
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        slide_filter = sys.argv[2] if len(sys.argv) > 2 else None
        return restore(slide_filter)

    if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
        return batch_redact(IMAGES_CONFIG, dry_run=True)

    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        print('\n命令行参数：')
        print('  (无)         跑脱敏')
        print('  --dry-run    只打印不写文件')
        print('  --restore    从 bak 还原所有图')
        print('  --restore X  从 bak 还原文件名含 X 的图')
        return 0

    return batch_redact(IMAGES_CONFIG)


if __name__ == '__main__':
    sys.exit(main())
