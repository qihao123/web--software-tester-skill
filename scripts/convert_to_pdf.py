#!/usr/bin/env python3
"""
convert_to_pdf.py - Markdown → PDF 转换（Playwright 优先）

优先级:
1. Playwright (推荐) - 跨平台，无需系统依赖
2. WeasyPrint - 需要 GTK 库（Windows 上容易失败）
3. HTML Fallback - 生成可打印的 HTML 文件

用法: python convert_to_pdf.py <markdown_file> [--output PDF_PATH]
"""

import sys
import argparse
from pathlib import Path


def md_to_html(md_content: str) -> str:
    """将 Markdown 转换为 HTML"""
    try:
        import markdown
        return markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])
    except ImportError:
        import re
        html = md_content
        html = re.sub(r'```(\w+)?\n(.*?)```', lambda m: f'<pre><code>{m.group(2)}</code></pre>', html, flags=re.DOTALL)
        for i in range(6, 0, -1):
            html = re.sub(rf'^({"#" * i}) (.+)$', lambda m: f'<h{i}>{m.group(2)}</h{i}>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        return f"<div>{html.replace(chr(10), '<br>')}</div>"


def convert_with_playwright(md_path: str, output_path: str) -> bool:
    """使用 Playwright 生成 PDF（推荐）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    md_file = Path(md_path)
    md_content = md_file.read_text(encoding="utf-8")
    body_html = md_to_html(md_content)

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{md_file.stem}</title>
<style>
  @page {{ margin: 2cm; size: A4; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif;
         max-width: 100%; padding: 40px; line-height: 1.8; color: #333; font-size: 11pt; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #1a1a2e; padding-bottom: 10px; font-size: 22pt; page-break-after: avoid; }}
  h2 {{ color: #16213e; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 6px; font-size: 16pt; page-break-after: avoid; }}
  h3 {{ color: #0f3460; font-size: 13pt; page-break-after: avoid; }}
  table {{ width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 9pt; page-break-inside: avoid; }}
  th, td {{ border: 1px solid #ccc; padding: 7px 10px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-size: 9pt; font-family: 'Consolas', monospace; }}
  pre {{ background: #2d2d2d; color: #f8f8f2; padding: 14px; border-radius: 6px; overflow-x: auto; 
       font-size: 8pt; page-break-inside: avoid; }}
  pre code {{ background: none; padding: 0; color: inherit; }}
  ul, ol {{ padding-left: 22px; }}
  li {{ margin: 4px 0; }}
  strong {{ color: #c0392b; }}
  a {{ color: #2980b9; text-decoration: none; }}
  blockquote {{ border-left: 4px solid #3498db; margin: 14px 0; padding: 10px 18px; background: #f0f7fb; }}
  hr {{ border: none; border-top: 2px solid #eee; margin: 24px 0; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    if not output_path:
        output_path = str(md_file.with_suffix(".pdf"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(full_html, wait_until="networkidle")
        page.pdf(path=output_path, format="A4",
                 print_background=True,
                 margin={"top": "2cm", "right": "2cm", "bottom": "2cm", "left": "2cm"})
        browser.close()

    print(f"✅ PDF 已生成 (Playwright): {output_path}")
    return True


def convert_with_weasyprint(md_path: str, output_path: str) -> bool:
    """使用 WeasyPrint 生成 PDF"""
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        return False

    md_file = Path(md_path)
    body_html = md_to_html(md_file.read_text(encoding="utf-8"))

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{md_file.stem}</title>
<style>
  @page {{ margin: 2cm; }}
  body {{ font-family: sans-serif; max-width: 900px; margin: 40px auto; line-height: 1.8; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 10px; }}
  pre {{ background: #f4f4f4; padding: 16px; overflow-x: auto; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    if not output_path:
        output_path = str(md_file.with_suffix(".pdf"))

    HTML(string=full_html).write_pdf(output_path)
    print(f"✅ PDF 已生成 (WeasyPrint): {output_path}")
    return True


def convert_to_fallback_html(md_path: str, output_path: str) -> str:
    """生成可打印 HTML 作为 fallback"""
    md_file = Path(md_path)
    body_html = md_to_html(md_file.read_text(encoding="utf-8"))

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>测试报告 - {md_file.stem}</title>
<style>
  @media print {{
    body {{ margin: 0; .no-print {{ display: none; }} }}
  }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }}
  h2 {{ color: #16213e; margin-top: 32px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 10px 14px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
  pre {{ background: #f4f4f4; padding: 16px; border-radius: 8px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  .no-print {{ background: #e3f2fd; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; }}
  strong {{ color: #c0392b; }}
</style>
</head>
<body>
<div class="no-print">
  <strong>提示：</strong>未安装 Playwright 或 WeasyPrint。已生成可打印 HTML。
  <br>安装 Playwright（推荐）：<code>pip install playwright && playwright install chromium</code>
  <br>或按 <b>Ctrl+P / Cmd+P</b> 在浏览器中保存为 PDF
</div>
{body_html}
</body>
</html>"""

    if not output_path or output_path.endswith(".pdf"):
        output_path = str(md_file.with_suffix(".html"))
    else:
        output_path = str(Path(output_path).with_suffix(".html"))

    Path(output_path).write_text(full_html, encoding="utf-8")
    print(f"⚠️ 已生成可打印 HTML: {output_path}")
    print("   安装 Playwright 后可获得更好的 PDF 输出:")
    print("   pip install playwright && playwright install chromium")
    return output_path


def convert_to_pdf(md_path: str, output_path: str = None) -> str:
    """转换主函数：按优先级尝试不同方案"""

    md_file = Path(md_path)
    if not md_file.exists():
        print(f"ERROR: Markdown 文件不存在: {md_path}")
        sys.exit(1)

    print(f"📄 正在转换: {md_path}")

    if convert_with_playwright(md_path, output_path):
        return output_path or str(md_file.with_suffix(".pdf"))

    if convert_with_weasyprint(md_path, output_path):
        return output_path or str(md_file.with_suffix(".pdf"))

    return convert_to_fallback_html(md_path, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Markdown → PDF 转换（Playwright 优先）")
    parser.add_argument("markdown", help="Markdown 文件路径")
    parser.add_argument("--output", "-o", help="输出路径（默认与输入同名）")
    args = parser.parse_args()

    convert_to_pdf(args.markdown, args.output)
