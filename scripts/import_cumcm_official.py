#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path.cwd()
TMP = Path('/tmp/cumcm')
OUT_ROOT = REPO / 'problems' / 'CUMCM'

SOURCES = {
    '2022': {
        'archive': TMP / 'CUMCM2022Problems.rar',
        'page': 'https://www.mcm.edu.cn/html_cn/node/388239ded4b057d37b7b8e51e33fe903.html',
        'url': 'https://www.mcm.edu.cn/upload_cn/node/670/5eWlbmTt28f88a0815a79d555da8b7072f971633.rar',
    },
    '2023': {
        'archive': TMP / 'CUMCM2023Problems.rar',
        'page': 'https://www.mcm.edu.cn/html_cn/node/c74d72127066f510a5723a94b5323a26.html',
        'url': 'https://www.mcm.edu.cn/upload_cn/node/690/Y20WPner9fa62862794e6dc82731a5561ce1132f.rar',
    },
    '2024': {
        'archive': TMP / 'CUMCM2024Problems.zip',
        'page': 'https://www.mcm.edu.cn/html_cn/node/a0c1fb5c31d43551f08cd8ad16870444.html',
        'url': 'https://www.mcm.edu.cn/upload_cn/node/725/pmkWxf8H9cfe9984c1a1a5b1263e5dd3b5596ed5.zip',
    },
    '2025': {
        'archive': TMP / 'CUMCM2025Problems.zip',
        'page': 'https://www.mcm.edu.cn/html_cn/node/03c91a444e62eee81a3740fa97a461a6.html',
        'url': 'https://www.mcm.edu.cn/upload_cn/node/759/SvpohSGacdffe718bcaa3b6e835c03ae3461cab1.zip',
    },
}

ARCHIVE_EXTS = {'.rar', '.zip', '.7z'}
MEDIA_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.webm', '.m4v'}
KEEP_EXTS = {'.pdf', '.xlsx', '.xls', '.csv', '.txt', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
MAX_STATEMENT = 25 * 1024 * 1024
MAX_ATTACHMENT = 5 * 1024 * 1024
MAX_ATTACHMENTS_PER_YEAR = 20 * 1024 * 1024


def human_size(n: int) -> str:
    units = ['B', 'KiB', 'MiB', 'GiB']
    x = float(n)
    for unit in units:
        if x < 1024 or unit == units[-1]:
            return f'{x:.1f} {unit}'
        x /= 1024
    return f'{n} B'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def seven_zip_extract(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(['7z', 'x', '-y', str(archive), f'-o{target}'], check=True)


def expand_nested_archives(root: Path) -> None:
    seen: set[Path] = set()
    for _ in range(4):
        found_new = False
        archives = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS)
        for archive in archives:
            resolved = archive.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            target = archive.with_name(archive.name + '__unpacked')
            try:
                seven_zip_extract(archive, target)
                found_new = True
            except subprocess.CalledProcessError:
                # Keep going: the archive itself remains represented in ATTACHMENTS.md.
                pass
        if not found_new:
            break


def clean_rel(path: Path, root: Path) -> Path:
    parts = []
    for part in path.relative_to(root).parts:
        if part.endswith('__unpacked'):
            part = part[:-len('__unpacked')]
        parts.append(part)
    return Path(*parts)


def question_for(rel: Path) -> str:
    for part in rel.parts:
        m = re.search(r'([ABCDE])题', part, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    m = re.match(r'([ABCDE])题', rel.name, re.IGNORECASE)
    return m.group(1).upper() if m else '其他'


def is_statement(rel: Path) -> bool:
    if rel.suffix.lower() != '.pdf':
        return False
    name = rel.name
    return bool(re.match(r'^[ABCDE]题(?:\.|（|\(|_|-|$)', name, re.IGNORECASE)) and '附件' not in str(rel)


def describe(rel: Path) -> str:
    name = rel.name.lower()
    ext = rel.suffix.lower()
    full = str(rel)
    if ext in MEDIA_EXTS or '视频' in full:
        if '跳远' in full:
            return '跳远动作视频资料（根据官方文件名判断，用于运动过程/姿态分析）'
        return '视频资料（用于题目中的动态过程或实验/运动分析）'
    if '位置' in full or '轨迹' in full:
        return '位置/轨迹数据表（根据官方文件名判断）'
    if '成绩' in full:
        return '成绩数据（根据官方文件名判断）'
    if name.startswith('result'):
        return '结果填写或提交用表格（根据官方文件名判断）'
    if ext in {'.xlsx', '.xls', '.csv'}:
        return '题目配套表格/数据文件'
    if ext == '.txt':
        return '题目配套文本数据或说明'
    if ext in {'.jpg', '.jpeg', '.png'}:
        return '题目配套图片资料'
    if ext == '.pdf':
        return 'PDF 附件或补充说明资料'
    if ext in {'.doc', '.docx'}:
        return '官方格式或说明文档'
    if ext in ARCHIVE_EXTS:
        return '官方压缩附件；导入时仅临时解包用于识别其中内容，不保存压缩容器本身'
    return '题目配套附件'


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_manifests(year: str, source: dict[str, object], rows: list[dict[str, object]], year_dir: Path) -> None:
    archive = Path(source['archive'])
    source_text = f'''# CUMCM {year} 官方题目来源\n\n- 来源：全国大学生数学建模竞赛组委会官网\n- 官方页面：{source['page']}\n- 官方题目压缩包：{source['url']}\n- 官方压缩包文件名：{archive.name}\n- 导入时 SHA256：`{sha256(archive)}`\n\n## 仓库存储策略\n\n本仓库优先保存题目正文，以及体积适合 GitHub/手机离线浏览的表格、文本、图片等附件。视频、压缩包、单个过大的附件，或会使单年附件总体积过大的文件不会提交到 GitHub；它们仍会记录在 `ATTACHMENTS.md` 中，并保留官方来源链接。\n\n因此，`official/` 是“适合直接放进 GitHub 的官方材料子集”，不是对官方压缩包的无条件完整镜像。需要遗漏附件时，请从上面的组委会官方下载地址获取。\n'''
    (year_dir / 'SOURCE.md').write_text(source_text, encoding='utf-8')

    lines = [
        f'# CUMCM {year} 附件说明',
        '',
        '本文件由官方题目压缩包自动盘点生成。说明中的“内容/用途”优先依据官方文件名和文件类型概括；没有足够证据时不会臆测具体字段含义。',
        '',
        f'- 单个普通附件入库上限：{human_size(MAX_ATTACHMENT)}',
        f'- 单年普通附件入库预算：{human_size(MAX_ATTACHMENTS_PER_YEAR)}',
        '- 视频文件与压缩容器默认不入库，但会列在这里。',
        f'- 官方总下载地址：{source["url"]}',
        '',
    ]

    for q in ['A', 'B', 'C', 'D', 'E', '其他']:
        items = [r for r in rows if r['question'] == q and not r['statement']]
        if not items:
            continue
        lines += [f'## {q}题' if q != '其他' else '## 其他文件', '']
        for r in items:
            status = '✅ 已入库' if r['included'] else '⬇️ 未入库'
            lines.append(f'- **{r["path"]}** — {human_size(int(r["size"]))} — {status}')
            lines.append(f'  - 内容/用途：{r["description"]}')
            if not r['included']:
                lines.append(f'  - 未入库原因：{r["reason"]}')
                lines.append(f'  - 获取方式：从本年度组委会官方压缩包下载（见上方官方地址）')
        lines.append('')

    (year_dir / 'ATTACHMENTS.md').write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def import_year(year: str, source: dict[str, object]) -> None:
    archive = Path(source['archive'])
    if not archive.exists() or archive.stat().st_size < 1024:
        raise RuntimeError(f'Official archive missing or unexpectedly small: {archive}')

    work = TMP / 'work' / year
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    seven_zip_extract(archive, work)
    expand_nested_archives(work)

    year_dir = OUT_ROOT / year
    if year_dir.exists():
        shutil.rmtree(year_dir)
    official = year_dir / 'official'
    official.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in work.rglob('*') if p.is_file())
    rows: list[dict[str, object]] = []
    attachment_budget = 0
    emitted_destinations: set[Path] = set()

    for src in files:
        rel = clean_rel(src, work)
        ext = src.suffix.lower()
        size = src.stat().st_size
        statement = is_statement(rel)
        included = False
        reason = ''

        # Nested archive containers are only staging objects. Their extracted contents
        # are considered separately, so do not duplicate them in the repository.
        if ext in ARCHIVE_EXTS:
            rows.append({
                'question': question_for(rel), 'path': str(rel), 'size': size,
                'statement': False, 'included': False,
                'description': describe(rel),
                'reason': '压缩容器本身不入库；已在临时目录解包并逐项检查其中内容。',
            })
            continue

        if statement:
            if size <= MAX_STATEMENT:
                included = True
            else:
                reason = f'题目 PDF 单文件超过仓库安全上限 {human_size(MAX_STATEMENT)}。'
        elif ext in MEDIA_EXTS:
            reason = '视频体积大，不适合纳入 GitHub；保留说明和官方下载入口。'
        elif ext not in KEEP_EXTS:
            reason = f'文件类型 {ext or "(无扩展名)"} 不在仓库离线学习材料白名单中。'
        elif size > MAX_ATTACHMENT:
            reason = f'单个附件超过 {human_size(MAX_ATTACHMENT)}，为避免仓库过大而不入库。'
        elif attachment_budget + size > MAX_ATTACHMENTS_PER_YEAR:
            reason = f'本年度普通附件累计将超过 {human_size(MAX_ATTACHMENTS_PER_YEAR)} 的 GitHub 存储预算。'
        else:
            included = True
            attachment_budget += size

        if included:
            dst = official / rel
            # Recursive expansion can expose the same logical file more than once.
            # Keep only the first copy at a given normalized path.
            if dst in emitted_destinations:
                included = False
                reason = '递归解包后与已保存文件路径重复，避免重复入库。'
            else:
                copy_file(src, dst)
                emitted_destinations.add(dst)

        rows.append({
            'question': question_for(rel),
            'path': str(rel),
            'size': size,
            'statement': statement,
            'included': included,
            'description': '题目正文 PDF' if statement else describe(rel),
            'reason': reason,
        })

    write_manifests(year, source, rows, year_dir)

    statement_count = sum(1 for r in rows if r['statement'] and r['included'])
    attachment_count = sum(1 for r in rows if not r['statement'] and r['included'])
    skipped_count = sum(1 for r in rows if not r['included'])
    print(f'{year}: statements={statement_count}, attachments={attachment_count}, skipped={skipped_count}, attachment_bytes={attachment_budget}')


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for year, source in SOURCES.items():
        import_year(year, source)


if __name__ == '__main__':
    main()
