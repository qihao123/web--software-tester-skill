#!/usr/bin/env python3
"""
convert_to_pdf.py - Markdown → PDF 转换
用法: python convert_to_pdf.py <markdown_file> [--output PDF_PATH]
"""

import sys
import argparse
from pathlib import Path

def convert_to_pdf(md_path: str, output_path: str = None) -> str:
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        print("ERROR: 需要 weasyprint 库")
        print("安装方法: pip install weasyprint")
        sys.exit(1)

    md_file = Path(md_path)
    if not md_file.exists():
        print(f"ERROR: Markdown 文件不存在: {md_path}")
        sys.exit(1)

    if not output_path:
        output_path = str(md_file.with_suffix('.pdf'))

    # 读取 Markdown 内容
    md_content = md_file.read_text(encoding='utf-8')

    # 简单的 Markdown → HTML 转换
    import re

    html = md_content

    # 处理代码块
    html = re.sub(r'```(\w+)?\n(.*?)```', lambda m: f'<pre><code>{m.group(2)}</code></pre>', html, flags=re.DOTALL)

    # 处理标题
    for i in range(6, 0, -1):
        html = re.sub(rf'^({"#" * i}) (.+)$', lambda m: f'<h{i}>{m.group(2)}</h{i}>', html, flags=re.MULTILINE)

    # 处理表格
    def convert_table(match):
        table_md = match.group(0)
        rows = [l for l in table_md.strip().split('\n') if l]
        if len(rows) < 2:
            return table_md

        headers = [h.strip() for h in rows[0].split('|')[1:-1]]
        header_html = '<thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead>'

        body_rows = ''
        for row in rows[2:]:
            cells = [c.strip() for c in row.split('|')[1:-1]]
            body_rows += '<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
        body_html = f'<tbody>{body_rows}</tbody>'

        return f'<table>{header_html}{body_html}</table>'

    html = re.sub(r'\|[^\n]+\|\n\|[-| :]+\|\n(?:\|[^\n]+\|\n?)+', convert_table, html)

    # 处理粗体/斜体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # 处理行内代码
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # 处理列表
    lines = html.split('\n')
    result = []
    in_list = False
    for line in lines:
        if re.match(r'^[\-\*] (.+)', line):
            if not in_list:
                result.append('<ul>')
                in_list = True
            item = re.sub(r'^[\-\*] (.+)', r'<li>\1</li>', line)
            result.append(item)
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)

    html = '\n'.join(result)
    # 闭合未关闭的列表
    if in_list:
        html += '</ul>'

    # 完整 HTML 文档
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans CJK SC', sans-serif;
         max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #333; }}
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
</style>
</head>
<body>
{html}
</body>
</html>"""

    HTML(string=full_html).write_pdf(output_path)
    print(f"✅ PDF 已生成: {output_path}")
    return output_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将 Markdown 转换为 PDF')
    parser.add_argument('markdown', help='Markdown 文件路径')
    parser.add_argument('--output', '-o', help='输出 PDF 路径（默认与输入同名）')
    args = parser.parse_args()

    convert_to_pdf(args.markdown, args.output)
