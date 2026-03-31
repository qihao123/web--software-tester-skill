#!/usr/bin/env python3
"""
convert_to_pdf.py - Markdown → PDF / 自包含 HTML 转换
用法: python convert_to_pdf.py <markdown_file> [--output PDF_PATH]

说明:
- 优先尝试使用 weasyprint 生成 PDF（需要系统依赖）
- 若 weasyprint 不可用，则生成一个自包含的 HTML 文件，可直接在浏览器中打开并打印为 PDF
"""

import sys
import argparse
from pathlib import Path


def md_to_html(md_content: str) -> str:
    """将 Markdown 转换为 HTML"""
    try:
        import markdown
        return markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    except ImportError:
        # 极简 fallback
        import re
        html = md_content
        html = re.sub(r'```(\w+)?\n(.*?)```', lambda m: f'<pre><code>{m.group(2)}</code></pre>', html, flags=re.DOTALL)
        for i in range(6, 0, -1):
            html = re.sub(rf'^({"#" * i}) (.+)$', lambda m: f'<h{i}>{m.group(2)}</h{i}>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        return f"<div>{html.replace(chr(10), '<br>')}</div>"


def convert_to_pdf(md_path: str, output_path: str = None) -> str:
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"ERROR: Markdown 文件不存在: {md_path}")
        sys.exit(1)

    md_content = md_file.read_text(encoding="utf-8")
    body_html = md_to_html(md_content)

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>测试报告</title>
<style>
  @media print {{
    body {{ margin: 0; }}
    .no-print {{ display: none; }}
  }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans CJK SC', sans-serif;
         max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }}
  h2 {{ color: #16213e; margin-top: 32px; }}
  h3 {{ color: #0f3460; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 10px 14px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
  pre {{ background: #f4f4f4; padding: 16px; border-radius: 8px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  ul {{ padding-left: 24px; }}
  li {{ margin: 6px 0; }}
  strong {{ color: #c0392b; }}
  img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 8px; }}
  .no-print {{ background: #e3f2fd; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; }}
  .no-print button {{ padding: 8px 16px; cursor: pointer; }}
</style>
</head>
<body>
<div class="no-print">
  <strong>提示：</strong>weasyprint 未安装或不可用，已生成可打印 HTML。请按 Ctrl+P（或 Cmd+P）保存为 PDF。
</div>
{body_html}
</body>
</html>"""

    # 尝试 weasyprint
    try:
        from weasyprint import HTML, CSS
        if not output_path:
            output_path = str(md_file.with_suffix(".pdf"))
        HTML(string=full_html).write_pdf(output_path)
        print(f"✅ PDF 已生成: {output_path}")
        return output_path
    except ImportError:
        pass

    # Fallback: 输出 HTML
    if not output_path:
        output_path = str(md_file.with_suffix(".html"))
    else:
        output_path = str(Path(output_path).with_suffix(".html"))

    Path(output_path).write_text(full_html, encoding="utf-8")
    print(f"⚠️ weasyprint 未安装，已生成可打印 HTML: {output_path}")
    print("   请在浏览器中打开并按 Ctrl+P（或 Cmd+P）另存为 PDF")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将 Markdown 转换为 PDF（或自包含 HTML）")
    parser.add_argument("markdown", help="Markdown 文件路径")
    parser.add_argument("--output", "-o", help="输出路径（默认与输入同名）")
    args = parser.parse_args()

    convert_to_pdf(args.markdown, args.output)
