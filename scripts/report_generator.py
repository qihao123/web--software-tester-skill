#!/usr/bin/env python3
"""
report_generator.py - 业务测试报告生成器

基于测试结果和业务逻辑文档，生成基于业务视角的测试报告。

用法:
  python report_generator.py --test-results RESULTS --business-doc DOC [--format FORMAT] [--output FILE]

输出:
  business_test_report.md (或 .html)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class ReportGenerator:
    """业务测试报告生成器"""

    def __init__(self, test_results_path: str, business_doc_path: str):
        self.test_results_path = Path(test_results_path)
        self.business_doc_path = Path(business_doc_path)

        self.test_results: Dict = {}
        self.business_doc: str = ""
        self.business_flows: List[str] = []

    def load_data(self):
        """加载数据"""
        # 加载测试结果
        if self.test_results_path.exists():
            with open(self.test_results_path, "r", encoding="utf-8") as f:
                self.test_results = json.load(f)
            print(f"📁 加载测试结果: {self.test_results_path}")
        else:
            print(f"ERROR: 测试结果文件不存在: {self.test_results_path}")
            sys.exit(1)

        # 加载业务逻辑文档
        if self.business_doc_path.exists():
            self.business_doc = self.business_doc_path.read_text(encoding="utf-8")
            self._extract_business_flows()
            print(f"📁 加载业务逻辑文档: {self.business_doc_path}")
        else:
            print(f"⚠️ 业务逻辑文档不存在: {self.business_doc_path}")

    def _extract_business_flows(self):
        """从业务文档中提取流程名称"""
        import re
        # 匹配 "### N. 流程名称" 或 "### 流程名称"
        pattern = r'### \d+\.\s*(.+?)(?:\n|$)'
        matches = re.findall(pattern, self.business_doc)
        self.business_flows = [m.strip() for m in matches]

    def _get_result_summary(self) -> dict:
        """获取结果摘要"""
        summary = self.test_results.get("summary", {})
        return {
            "total": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "skipped": summary.get("skipped", 0),
            "pass_rate": (summary.get("passed", 0) / summary.get("total", 1) * 100) if summary.get("total", 0) > 0 else 0
        }

    def _categorize_results(self) -> dict:
        """按类型分类测试结果"""
        categories = {
            "business_flow": [],
            "navigation": [],
            "element_check": [],
            "api_check": [],
            "form_submit": [],
            "other": []
        }

        for result in self.test_results.get("results", []):
            test_type = result.get("type", "other")
            if test_type in categories:
                categories[test_type].append(result)
            else:
                categories["other"].append(result)

        return categories

    def _group_by_flow(self) -> dict:
        """按业务流程分组结果"""
        flow_groups = {}

        for result in self.test_results.get("results", []):
            flow_name = result.get("source_flow", "")
            if flow_name:
                if flow_name not in flow_groups:
                    flow_groups[flow_name] = []
                flow_groups[flow_name].append(result)

        return flow_groups

    def generate_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        summary = self._get_result_summary()
        categories = self._categorize_results()
        flow_groups = self._group_by_flow()

        md = []

        # 标题
        md.append("# 🧪 业务测试报告")
        md.append("")
        md.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"**测试时间**: {self.test_results.get('timestamp', 'N/A')[:19] if self.test_results.get('timestamp') else 'N/A'}")
        md.append("")

        # 执行摘要
        md.append("## 📊 执行摘要")
        md.append("")
        md.append(f"| 指标 | 数值 |")
        md.append(f"|------|------|")
        md.append(f"| 总测试数 | {summary['total']} |")
        md.append(f"| 通过 | ✅ {summary['passed']} |")
        md.append(f"| 失败 | ❌ {summary['failed']} |")
        md.append(f"| 跳过 | ⏭️ {summary['skipped']} |")
        md.append(f"| 通过率 | {summary['pass_rate']:.1f}% |")
        md.append("")

        # 测试状态评估
        if summary['pass_rate'] >= 90:
            md.append("🟢 **整体状态**: 优秀，系统稳定性良好")
        elif summary['pass_rate'] >= 80:
            md.append("🟡 **整体状态**: 良好，存在少量问题需要修复")
        elif summary['pass_rate'] >= 60:
            md.append("🟠 **整体状态**: 一般，需要重点关注失败用例")
        else:
            md.append("🔴 **整体状态**: 较差，建议暂停发布并进行全面修复")
        md.append("")

        # 业务流程测试结果
        if flow_groups:
            md.append("## 🔄 业务流程测试结果")
            md.append("")

            for flow_name, results in flow_groups.items():
                flow_passed = sum(1 for r in results if r.get("status") == "passed")
                flow_total = len(results)
                flow_rate = (flow_passed / flow_total * 100) if flow_total > 0 else 0

                status_icon = "✅" if flow_rate == 100 else "⚠️" if flow_rate >= 50 else "❌"
                md.append(f"### {status_icon} {flow_name}")
                md.append("")
                md.append(f"**通过率**: {flow_passed}/{flow_total} ({flow_rate:.0f}%)")
                md.append("")

                # 该流程下的测试用例
                md.append("| 测试用例 | 状态 | 响应时间 | 备注 |")
                md.append("|----------|------|----------|------|")
                for r in results:
                    icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(r.get("status"), "❓")
                    rt = f"{r.get('response_time', 'N/A')}ms" if r.get("response_time") else "-"
                    note = r.get("message", "")[:40] if r.get("status") == "passed" else r.get("error", "")[:40]
                    md.append(f"| {r.get('name', '未命名')} | {icon} {r.get('status', 'unknown').upper()} | {rt} | {note} |")
                md.append("")

        # 按测试类型分类的结果
        md.append("## 📋 按测试类型分类")
        md.append("")

        type_names = {
            "business_flow": "业务流程测试",
            "navigation": "页面导航测试",
            "element_check": "元素存在性测试",
            "api_check": "API 接口测试",
            "form_submit": "表单提交测试",
            "other": "其他测试"
        }

        for test_type, results in categories.items():
            if not results:
                continue

            type_passed = sum(1 for r in results if r.get("status") == "passed")
            type_total = len(results)
            type_rate = (type_passed / type_total * 100) if type_total > 0 else 0

            md.append(f"### {type_names.get(test_type, test_type)}")
            md.append("")
            md.append(f"**统计**: {type_passed}/{type_total} 通过 ({type_rate:.0f}%)")
            md.append("")

            md.append("| 用例 | 状态 | 响应时间 | 说明 |")
            md.append("|------|------|----------|------|")
            for r in results:
                icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(r.get("status"), "❓")
                rt = f"{r.get('response_time', 'N/A')}ms" if r.get("response_time") else "-"
                desc = r.get("message", "")[:30] if r.get("status") == "passed" else r.get("error", "")[:30]
                md.append(f"| {r.get('name', '未命名')[:30]} | {icon} {r.get('status', 'unknown')[:3].upper()} | {rt} | {desc} |")
            md.append("")

        # 失败详情
        failed_tests = [r for r in self.test_results.get("results", []) if r.get("status") == "failed"]
        if failed_tests:
            md.append("## ❌ 失败详情")
            md.append("")

            for r in failed_tests:
                md.append(f"### {r.get('name', '未命名测试')}")
                md.append("")
                md.append(f"- **类型**: {r.get('type', 'unknown')}")
                md.append(f"- **错误**: {r.get('error', '未知错误')}")
                if r.get("bug_description"):
                    md.append(f"- **Bug 描述**: {r.get('bug_description')}")
                if r.get("expected"):
                    md.append(f"- **期望结果**: {r.get('expected')}")
                if r.get("response_time"):
                    md.append(f"- **响应时间**: {r.get('response_time')}ms")
                md.append("")

        # 改进建议
        md.append("## 💡 改进建议")
        md.append("")

        if failed_tests:
            md.append(f"1. **优先修复失败用例**: 当前有 {len(failed_tests)} 个失败的测试用例，建议按优先级进行修复。")

        if summary['pass_rate'] < 80:
            md.append(f"2. **提升测试覆盖率**: 当前通过率 {summary['pass_rate']:.1f}% 低于 80%，建议进行全面回归测试。")

        if not categories.get("api_check"):
            md.append(f"3. **增加 API 测试**: 当前未执行 API 测试，建议补充接口层面的测试用例。")

        if not flow_groups:
            md.append(f"4. **关联业务流**: 测试用例未与业务流程关联，建议在生成用例时指定 source_flow 字段。")

        md.append("")

        # 附录：原始数据
        md.append("## 📎 附录")
        md.append("")
        md.append("### 测试配置")
        config = self.test_results.get("config", {})
        for k, v in config.items():
            md.append(f"- {k}: {v}")
        md.append("")

        return "\n".join(md)

    def generate_html(self) -> str:
        """生成 HTML 格式报告"""
        summary = self._get_result_summary()
        categories = self._categorize_results()

        # 计算各状态的颜色
        pass_color = "#28a745" if summary['pass_rate'] >= 80 else "#ffc107" if summary['pass_rate'] >= 60 else "#dc3545"

        # 构建测试结果表格
        result_rows = ""
        for r in self.test_results.get("results", []):
            status = r.get("status", "unknown")
            color = {"passed": "#28a745", "failed": "#dc3545", "skipped": "#ffc107"}.get(status, "#666")
            result_rows += f"""
            <tr>
                <td>{r.get('name', '未命名')}</td>
                <td>{r.get('type', 'unknown')}</td>
                <td style="color:{color};font-weight:bold;">{status.upper()}</td>
                <td>{r.get('response_time', '-')} ms</td>
            </tr>"""

            if r.get("error"):
                result_rows += f"""
            <tr style="background:#f8d7da;">
                <td colspan="4" style="padding:8px 16px;color:#721c24;">
                    ❌ {r.get('error')[:100]}
                </td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>业务测试报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            color: #333;
            line-height: 1.6;
        }}
        h1 {{ color: #1a1a2e; }}
        h2 {{ color: #16213e; border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 32px; }}
        h3 {{ color: #0f3460; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin: 24px 0;
        }}
        .card {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .card .num {{ font-size: 32px; font-weight: bold; }}
        .card .label {{ color: #666; margin-top: 4px; font-size: 14px; }}
        .status-bar {{
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            margin: 16px 0;
            overflow: hidden;
        }}
        .status-fill {{
            height: 100%;
            background: {pass_color};
            width: {summary['pass_rate']}%;        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .skipped {{ color: #ffc107; }}
        .alert {{
            padding: 12px 16px;
            border-radius: 8px;
            margin: 16px 0;
        }}
        .alert-success {{ background: #d4edda; color: #155724; }}
        .alert-warning {{ background: #fff3cd; color: #856404; }}
        .alert-danger {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <h1>🧪 业务测试报告</h1>
    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <h2>📊 执行摘要</h2>
    <div class="summary">
        <div class="card">
            <div class="num">{summary['total']}</div>
            <div class="label">总测试数</div>
        </div>
        <div class="card">
            <div class="num" style="color:#28a745">{summary['passed']}</div>
            <div class="label">通过</div>
        </div>
        <div class="card">
            <div class="num" style="color:#dc3545">{summary['failed']}</div>
            <div class="label">失败</div>
        </div>
        <div class="card">
            <div class="num" style="color:#ffc107">{summary['skipped']}</div>
            <div class="label">跳过</div>
        </div>
        <div class="card">
            <div class="num" style="color:{pass_color}">{summary['pass_rate']:.1f}%</div>
            <div class="label">通过率</div>
        </div>
    </div>

    <div class="status-bar">
        <div class="status-fill"></div>
    </div>

    {'<div class="alert alert-success">🟢 整体状态: 优秀，系统稳定性良好</div>' if summary['pass_rate'] >= 90 else
     '<div class="alert alert-warning">🟡 整体状态: 良好，存在少量问题需要修复</div>' if summary['pass_rate'] >= 80 else
     '<div class="alert alert-danger">🔴 整体状态: 较差，建议进行全面修复</div>'}

    <h2>📋 测试结果详情</h2>
    <table>
        <tr>
            <th>测试用例</th>
            <th>类型</th>
            <th>状态</th>
            <th>响应时间</th>
        </tr>
        {result_rows}
    </table>

    <h2>📊 按类型统计</h2>
    <table>
        <tr>
            <th>测试类型</th>
            <th>总数</th>
            <th>通过</th>
            <th>失败</th>
            <th>通过率</th>
        </tr>"""

        # 按类型统计行
        type_names = {
            "business_flow": "业务流程测试",
            "navigation": "页面导航测试",
            "element_check": "元素存在性测试",
            "api_check": "API 接口测试",
            "form_submit": "表单提交测试",
            "other": "其他测试"
        }

        for test_type, results in categories.items():
            if not results:
                continue
            type_passed = sum(1 for r in results if r.get("status") == "passed")
            type_total = len(results)
            type_rate = (type_passed / type_total * 100) if type_total > 0 else 0
            type_color = "#28a745" if type_rate >= 80 else "#ffc107" if type_rate >= 60 else "#dc3545"

            html += f"""
        <tr>
            <td>{type_names.get(test_type, test_type)}</td>
            <td>{type_total}</td>
            <td>{type_passed}</td>
            <td>{type_total - type_passed}</td>
            <td style="color:{type_color}">{type_rate:.0f}%</td>
        </tr>"""

        html += """
    </table>
</body>
</html>"""

        return html

    def generate_report(self, format_type: str = "markdown") -> str:
        """生成报告"""
        self.load_data()

        if format_type == "html":
            return self.generate_html()
        else:
            return self.generate_markdown()

    def save_report(self, output_file: str, format_type: str = "markdown"):
        """保存报告"""
        report = self.generate_report(format_type)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"📁 测试报告已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="业务测试报告生成器")
    parser.add_argument("--test-results", "-r", required=True, help="测试结果 JSON 文件路径")
    parser.add_argument("--business-doc", "-b", help="业务逻辑文档路径 (Markdown)")
    parser.add_argument("--format", "-f", choices=["markdown", "html"], default="markdown", help="报告格式")
    parser.add_argument("--output", "-o", default="./test_report.md", help="输出文件路径")
    args = parser.parse_args()

    generator = ReportGenerator(args.test_results, args.business_doc or "")
    generator.save_report(args.output, args.format)


if __name__ == "__main__":
    main()
