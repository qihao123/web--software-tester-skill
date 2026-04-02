#!/usr/bin/env python3
"""
report_generator.py - 专业测试报告生成器

生成专业测试工程师需要的文档:
- 测试流程文档
- 接口文档
- 测试用例文档
- 测试计划文档
- 测试执行报告

用法:
  python report_generator.py --test-results RESULTS_JSON [--business-doc MD_PATH] [--output DIR]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


class ReportGenerator:
    def __init__(self, output_dir: str = "./test_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self, test_results: dict, business_doc: str = None) -> dict:
        """生成所有报告"""
        print("\n📝 开始生成测试报告...")

        reports = {}

        execution_report = self._generate_execution_report(test_results)
        reports["execution_report"] = execution_report

        test_plan = self._generate_test_plan_report(test_results)
        reports["test_plan"] = test_plan

        api_doc = self._generate_api_documentation(test_results)
        reports["api_documentation"] = api_doc

        if business_doc and Path(business_doc).exists():
            flow_doc = self._generate_flow_documentation(business_doc)
            reports["flow_documentation"] = flow_doc

        summary_report = self._generate_summary_report(reports)
        reports["summary"] = summary_report

        for name, content in reports.items():
            ext = ".md" if isinstance(content, str) else ".json"
            path = self.output_dir / f"{name}{ext}"
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 报告已生成到: {self.output_dir}")
        for name in reports.keys():
            print(f"   - {name}")

        return reports

    def _generate_execution_report(self, results: dict) -> str:
        """生成测试执行报告"""
        lines = []
        lines.append("# 测试执行报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**测试人员**: 自动化测试系统")
        lines.append("")
        lines.append("---")
        lines.append("")

        summary = results.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0

        lines.append("## 1. 执行摘要")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 用例总数 | **{total}** |")
        lines.append(f"| 通过数 | ✅ **{passed}** |")
        lines.append(f"| 失败数 | ❌ **{failed}** |")
        lines.append(f"| 跳过数 | ⏭️ **{skipped}** |")
        lines.append(f"| 通过率 | **{pass_rate}%** |")
        lines.append("")

        if pass_rate >= 90:
            status = "🟢 优秀"
        elif pass_rate >= 70:
            status = "🟡 良好"
        elif pass_rate >= 50:
            status="🟠 需改进"
        else:
            status = "🔴 不合格"

        lines.append(f"### 测试结论: **{status}**")
        lines.append("")

        config = results.get("config", {})
        if config.get("url"):
            lines.append(f"- **测试目标**: {config['url']}")
        lines.append(f"- **测试模式**: {'Playwright 真实浏览器' if config.get('use_playwright') else '静态请求'}")
        lines.append("")

        lines.append("## 2. 测试结果明细")
        lines.append("")

        test_results_list = results.get("results", [])
        failed_cases = [r for r in test_results_list if r.get("status") == "failed"]
        passed_cases = [r for r in test_results_list if r.get("status") == "passed"]

        if failed_cases:
            lines.append("### ❌ 失败用例")
            lines.append("")
            lines.append("| ID | 名称 | 类型 | 错误信息 | Bug 描述 |")
            lines.append("|----|------|------|----------|----------|")
            for case in failed_cases[:20]:
                bug_desc = case.get("bug_description", "-")[:80]
                error = case.get("error", "-")[:60]
                lines.append(f"| {case.get('id', '-')} | {case.get('name', '-')[:30]} "
                           f"| {case.get('type', '-')} | {error} | {bug_desc} |")
            lines.append("")

        if passed_cases:
            lines.append(f"### ✅ 通过用例 ({len(passed_cases)} 个)")
            lines.append("")
            lines.append("| ID | 名称 | 类型 | 响应时间(ms) |")
            lines.append("|----|------|------|-------------|")
            for case in passed_cases[:50]:
                rt = case.get("response_time", "-")
                lines.append(f"| {case.get('id', '-')} | {case.get('name', '-')[:35]} "
                           f"| {case.get('type', '-')} | {rt} |")
            lines.append("")

        by_type = {}
        for r in test_results_list:
            t = r.get("type", "unknown")
            by_type[t] = by_type.get(t, {"total": 0, "passed": 0, "failed": 0})
            by_type[t]["total"] += 1
            if r["status"] == "passed":
                by_type[t]["passed"] += 1
            else:
                by_type[t]["failed"] += 1

        lines.append("## 3. 按类型统计")
        lines.append("")
        lines.append("| 类型 | 总数 | 通过 | 失败 | 通过率 |")
        lines.append("|------|------|------|------|--------|")
        for t, stats in sorted(by_type.items()):
            rate = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            lines.append(f"| {t} | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate}% |")
        lines.append("")

        lines.append("## 4. 缺陷汇总")
        lines.append("")
        lines.append("| 序号 | 严重程度 | 缺陷描述 | 相关用例 | 状态 |")
        lines.append("|------|----------|----------|----------|------|")
        for i, case in enumerate(failed_cases[:20], 1):
            severity = "P0-致命" if "认证" in case.get("bug_description", "") or "登录" in case.get("name", "") \
                else ("P1-严重" if "API" in case.get("type", "") or "表单" in case.get("name", "")
                       else "P2-一般")
            lines.append(f"| {i} | {severity} | {case.get('bug_description', '-')[:40]} "
                       f"| {case.get('name', '-')[:25]} | 待确认 |")
        lines.append("")

        lines.append("## 5. 改进建议")
        lines.append("")
        suggestions = []

        if len(failed_cases) > 0:
            auth_failures = [c for c in failed_cases if "401" in str(c.get("actual_status", ""))
                             or "认证" in c.get("bug_description", "")]
            if auth_failures:
                suggestions.append("- 🔐 **鉴权问题**: 发现多个认证相关失败，请检查 Token 配置和有效期")

            api_failures = [c for c in failed_cases if c.get("type") == "api_check"]
            if api_failures:
                suggestions.append("- 📡 **接口问题**: 部分 API 返回异常，建议检查后端服务状态和接口变更")

            form_failures = [c for c in failed_cases if c.get("type") == "form_submit"]
            if form_failures:
                suggestions.append("- 📋 **表单问题**: 表单提交失败，检查字段校验规则和数据格式要求")

        if not suggestions:
            suggestions.append("- ✅ 当前版本质量良好，继续保持")

        for s in suggestions:
            lines.append(s)
        lines.append("")

        return "\n".join(lines)

    def _generate_test_plan_report(self, results: dict) -> str:
        """生成测试计划文档"""
        lines = []
        lines.append("# 测试计划")
        lines.append("")
        lines.append("**项目名称**: Web 应用自动化测试")
        lines.append(f"**制定日期**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"**版本**: V1.0")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## 1. 测试目标")
        lines.append("")
        lines.append("1.1 主要目标")
        lines.append("- 验证核心业务流程的正确性和完整性")
        lines.append("- 确保 API 接口功能符合需求规格说明")
        lines.append("- 检测并记录系统缺陷，推动质量改进")
        lines.append("- 建立可回归的自动化测试基线")
        lines.append("")
        lines.append("1.2 测试范围")
        lines.append("")
        lines.append("**包含范围**:")
        lines.append("- ✅ 用户认证与授权功能")
        lines.append("- ✅ 核心业务数据的增删改查操作")
        lines.append("- ✅ 页面导航与交互功能")
        lines.append("- ✅ API 接口正异常场景验证")
        lines.append("- ✅ 基础安全漏洞检测")
        lines.append("")
        lines.append("**排除范围**:")
        lines.append("- ❌ 性能压力测试（单独进行）")
        lines.append("- ❌ 浏览器兼容性全面测试")
        lines.append("- ❌ 移动端适配测试")
        lines.append("- ❌ 第三方集成深度测试")
        lines.append("")

        summary = results.get("summary", {})
        total = summary.get("total", 0)
        p0_count = sum(1 for r in results.get("results", []) 
                      if r.get("status") == "failed" and any(
                          kw in str(r) for kw in ["登录", "认证", "权限"]))
        
        lines.append("## 2. 测试策略")
        lines.append("")
        lines.append("### 2.1 测试类型与方法")
        lines.append("")
        lines.append("| 测试类型 | 方法 | 工具 | 优先级 |")
        lines.append("|----------|------|------|--------|")
        lines.append("| 功能测试 | 黑盒/灰盒 | Playwright + Requests | P0 |")
        lines.append("| API 接口测试 | 白盒 | aiohttp + 断言库 | P0 |")
        lines.append("| 安全基础测试 | 黑盒 | 自定义脚本 | P1 |")
        lines.append("| 回归测试 | 自动化 | CI/CD 集成 | P1 |")
        lines.append("")

        lines.append("### 2.2 测试环境")
        lines.append("")
        lines.append("| 环境 | 用途 | URL | 数据状态 |")
        lines.append("|------|------|-----|----------|")
        lines.append("| 开发环境 | 冒烟测试 | 开发地址 | 开发数据 |")
        lines.append("| 测试环境 | 功能测试 | 测试地址 | 测试数据 |")
        lines.append("| 预发布环境 | 验收测试 | 预发布地址 | 生产镜像 |")
        lines.append("")

        lines.append("## 3. 测试进度安排")
        lines.append("")
        estimated_hours = max(total * 0.25, 8)
        lines.append(f"**预估总工时**: {estimated_hours} 小时（含用例设计 + 执行 + 报告）")
        lines.append("")
        lines.append("| 阶段 | 内容 | 预估时间 | 输出物 |")
        lines.append("|------|------|----------|--------|")
        lines.append("| 需求分析 | 理解业务逻辑，识别测试点 | 2h | 测试点清单 |")
        lines.append("| 用例设计 | 编写详细测试用例 | 4h | 测试用例文档 |")
        lines.append("| 环境准备 | 搭建测试环境，准备数据 | 1h | 环境就绪确认 |")
        lines.append("| 冒烟测试 | 核心流程快速验证 | 1h | 冒烟结果 |")
        lines.append("| 功能测试 | 全面执行测试用例 | 4h | 测试执行记录 |")
        lines.append("| 缺陷跟踪 | 问题确认、修复验证 | 2h | 缺陷报告 |")
        lines.append("| 回归测试 | 修复后回归 | 2h | 回归结果 |")
        lines.append("| 报告输出 | 整理测试报告 | 1h | 测试报告 |")
        lines.append("")

        lines.append("## 4. 准入准出标准")
        lines.append("")
        lines.append("### 4.1 准入标准")
        lines.append("- [ ] 测试环境部署完成且可访问")
        lines.append("- [ ] 测试数据准备完毕（至少覆盖主要场景）")
        lines.append("- [ ] 需求文档/接口文档已提供或可通过 Swagger 访问")
        lines.append("- [ ] 测试账号和权限已配置")
        lines.append("- [ ] 被测版本已确定且已部署到测试环境")
        lines.append("")

        lines.append("### 4.2 准出标准")
        lines.append("- [ ] P0（致命）缺陷: **0 个**遗留")
        lines.append("- [ ] P1（严重）缺陷: ≤ 2 个且有规避方案")
        lines.append("- [ ] 用例通过率: **≥ 95%**")
        lines.append("- [ ] 所有测试用例均已执行并有明确结果")
        lines.append("- [ ] 测试报告已完成并通过评审")
        lines.append("")

        lines.append("## 5. 风险与应对")
        lines.append("")
        lines.append("| 风险项 | 可能性 | 影响 | 应对措施 |")
        lines.append("|--------|--------|------|----------|")
        lines.append("| 环境不稳定 | 中 | 高 | 使用容器化环境，保留快照 |")
        lines.append("| 需求变更 | 中 | 中 | 变更影响分析，及时更新用例 |")
        lines.append("| 接口变动 | 高 | 中 | 基于 Swagger 动态生成，定期同步 |")
        lines.append("| 数据依赖 | 低 | 高 | 使用独立测试数据库，自动初始化 |")
        lines.append("| 时间不足 | 中 | 中 | 优先 P0 用例，分批执行 |")
        lines.append("")

        return "\n".join(lines)

    def _generate_api_documentation(self, results: dict) -> str:
        """生成接口文档"""
        lines = []
        lines.append("# API 接口测试文档")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().isoformat()}")
        lines.append("")
        lines.append("---")
        lines.append("")

        api_cases = [r for r in results.get("results", []) if r.get("type") == "api_check"]

        if not api_cases:
            lines.append("*本次测试未包含接口测试用例*")
            return "\n".join(lines)

        lines.append("## 1. 接口概览")
        lines.append("")
        lines.append(f"**测试接口总数**: {len(api_cases)}")
        lines.append("")

        passed_apis = [a for a in api_cases if a.get("status") == "passed"]
        failed_apis = [a for a in api_cases if a.get("status") == "failed"]

        lines.append("| 状态 | 数量 | 占比 |")
        lines.append("|------|------|------|")
        lines.append(f"| ✅ 通过 | {len(passed_apis)} | {round(len(passed_apis)/len(api_cases)*100, 1) if api_cases else 0}% |")
        lines.append(f"| ❌ 失败 | {len(failed_apis)} | {round(len(failed_apis)/len(api_cases)*100, 1) if api_cases else 0}% |")
        lines.append("")

        lines.append("## 2. 接口详情")
        lines.append("")

        grouped = {}
        for api in api_cases:
            url = api.get("value", api.get("url", ""))
            base_path = "/".join(url.split("/")[:4]) if url else "unknown"
            if base_path not in grouped:
                grouped[base_path] = []
            grouped[base_path].append(api)

        for group, apis in grouped.items():
            lines.append(f"### {group}")
            lines.append("")
            lines.append("| 接口路径 | 方法 | 结果 | 响应时间 | 备注 |")
            lines.append("|----------|------|------|----------|------|")
            for api in apis:
                icon = "✅" if api["status"] == "passed" else "❌"
                rt = api.get("response_time", "-")
                note = api.get("error", "")[:30] or api.get("message", "")[:30]
                lines.append(f"| `{api.get('value', api.get('url', ''))}` | {api.get('type', '-')} "
                           f"| {icon} | {rt}ms | {note} |")
            lines.append("")

        if failed_apis:
            lines.append("## 3. 问题接口")
            lines.append("")
            for api in failed_apis:
                lines.append(f"#### ❌ {api.get('name', 'Unknown')}")
                lines.append(f"- **URL**: {api.get('value', api.get('url', ''))}")
                lines.append(f"- **状态码**: {api.get('actual_status', 'N/A')}")
                lines.append(f"- **错误**: {api.get('error', 'N/A')}")
                lines.append(f"- **Bug**: {api.get('bug_description', 'N/A')}")
                lines.append("")

        return "\n".join(lines)

    def _generate_flow_documentation(self, business_doc_path: str) -> str:
        """基于业务文档生成流程文档"""
        content = Path(business_doc_path).read_text(encoding="utf-8")

        lines = []
        lines.append("# 业务流程测试文档")
        lines.append("")
        lines.append(f"> 来源: {business_doc_path}")
        lines.append(f"> 同步时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*本文档由 report_generator.py 从业务逻辑文档自动生成*")

        return "\n".join(lines)

    def _generate_summary_report(self, reports: dict) -> dict:
        """生成摘要 JSON"""
        return {
            "generated_at": datetime.now().isoformat(),
            "reports_generated": list(reports.keys()),
            "output_directory": str(self.output_dir),
            "note": "所有报告已生成完毕，可直接用于团队评审和存档"
        }


def main():
    parser = argparse.ArgumentParser(description="专业测试报告生成器")
    parser.add_argument("--test-results", "-r", required=True, help="测试结果 JSON 文件")
    parser.add_argument("--business-doc", "-b", default=None, help="业务逻辑文档 (Markdown)")
    parser.add_argument("--output-dir", "-o", default="./test_results", help="输出目录")
    args = parser.parse_args()

    with open(args.test_results, "r", encoding="utf-8") as f:
        results = json.load(f)

    generator = ReportGenerator(args.output_dir)
    generator.generate_all(results, args.business_doc)


if __name__ == "__main__":
    main()
