#!/usr/bin/env python3
"""
api_tester.py - API 接口测试执行器

特性:
- 基于 Swagger 文档或自定义配置执行 API 测试
- 支持 RESTful API 全方法测试
- 自动鉴权处理
- 详细响应断言
- 性能指标采集

用法:
  python api_tester.py --apis API_FILE_OR_URL [--base-url URL] [--token TOKEN]
"""

import sys
import json
import time
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from statistics import mean, median


class APITester:
    def __init__(self, base_url: str = "", token: str = None, output_dir: str = "./test_results"):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.token = token
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[dict] = []
        self.session_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "APITester/1.0"
        }
        if token:
            self.session_headers["Authorization"] = f"Bearer {token}"

    async def run_all_tests(self, apis: List[dict]) -> dict:
        """执行所有 API 测试"""
        try:
            import aiohttp
        except ImportError:
            print("ERROR: 需要 aiohttp 库")
            print("安装: pip install aiohttp")
            sys.exit(1)

        print(f"\n🚀 开始 API 测试...")
        print(f"   目标: {self.base_url or '(从 API 配置读取)'}")
        print(f"   API 数量: {len(apis)}")
        print()

        async with aiohttp.ClientSession(headers=self.session_headers) as session:
            tasks = []
            for i, api in enumerate(apis, 1):
                task = self._test_single_api(session, api, i, len(apis))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            self.results = [r for r in results if isinstance(r, dict)]

        summary = self._generate_summary()

        output_file = self.output_dir / "api_test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "base_url": self.base_url,
                "summary": summary,
                "results": self.results
            }, f, ensure_ascii=False, indent=2)

        report = self._generate_markdown_report(summary)
        report_path = self.output_dir / "api_test_report.md"
        report_path.write_text(report, encoding="utf-8")

        self._print_summary(summary)

        return summary

    async def _test_single_api(self, session, api: dict, index: int, total: int) -> dict:
        """测试单个 API"""
        method = api.get("method", "GET").upper()
        path = api.get("path", api.get("url", ""))
        name = api.get("name", api.get("summary", f"API_{index}"))

        if not path.startswith("http"):
            url = f"{self.base_url}{path}" if self.base_url else path
        else:
            url = path

        scenarios = api.get("test_scenarios", [{}])

        result = {
            "id": index,
            "name": name,
            "method": method,
            "url": url,
            "path": path,
            "scenarios": [],
            "overall_status": "passed"
        }

        print(f"  [{index}/{total}] {method} {path}")

        for si, scenario in enumerate(scenarios):
            scenario_name = scenario.get("name", f"场景_{si+1}")
            print(f"      └─ {scenario_name}", end=" ")

            scenario_result = await self._execute_scenario(
                session, method, url, scenario, api
            )
            result["scenarios"].append(scenario_result)

            if scenario_result["status"] == "failed":
                result["overall_status"] = "failed"
                print(f"❌ ({scenario_result.get('response_time', 0)}ms)")
            else:
                print(f"✅ ({scenario_result.get('response_time', 0)}ms)")

        return result

    async def _execute_scenario(self, session, method: str, url: str,
                                 scenario: dict, api: dict) -> dict:
        """执行单个测试场景"""
        start_time = time.time()

        payload = scenario.get("payload")
        params = scenario.get("params")
        expected_status = scenario.get("expected_status", 200)
        scenario_headers = scenario.get("headers", {})

        headers = {**self.session_headers}
        headers.update(scenario_headers)

        try:
            kwargs = {
                "headers": headers,
                "timeout": aiohttp.ClientTimeout(total=30)
            }

            if payload is not None:
                kwargs["json"] = payload
            if params:
                kwargs["params"] = params

            async with session.request(method, url, **kwargs) as resp:
                response_time = round((time.time() - start_time) * 1000, 2)
                status = resp.status

                try:
                    response_body = await resp.json()
                except Exception:
                    response_body = await resp.text()

                passed = status == expected_status

                assertions = []
                assertions.append({
                    "type": "status_code",
                    "expected": expected_status,
                    "actual": status,
                    "passed": passed
                })

                if isinstance(response_body, dict):
                    if "code" in response_body:
                        assertions.append({
                            "type": "response_code",
                            "expected": 200,
                            "actual": response_body.get("code"),
                            "passed": response_body.get("code") == 200
                        })
                    if "message" in response_body or "msg" in response_body:
                        assertions.append({
                            "type": "has_message",
                            "passed": True,
                            "value": response_body.get("message", response_body.get("msg", ""))
                        })

                return {
                    "name": scenario.get("name", ""),
                    "status": "passed" if passed else "failed",
                    "response_time": response_time,
                    "status_code": status,
                    "expected_status": expected_status,
                    "response_body": response_body if isinstance(response_body, (dict, list)) else response_body[:500],
                    "response_headers": dict(resp.headers),
                    "assertions": assertions,
                    "error": None
                }

        except asyncio.TimeoutError:
            response_time = round((time.time() - start_time) * 1000, 2)
            return {
                "name": scenario.get("name", ""),
                "status": "failed",
                "response_time": response_time,
                "status_code": None,
                "expected_status": expected_status,
                "response_body": None,
                "assertions": [{"type": "timeout", "passed": False}],
                "error": "Request timeout"
            }
        except Exception as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            return {
                "name": scenario.get("name", ""),
                "status": "failed",
                "response_time": response_time,
                "status_code": None,
                "expected_status": expected_status,
                "response_body": None,
                "assertions": [],
                "error": str(e)
            }

    def _generate_summary(self) -> dict:
        """生成测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("overall_status") == "passed")
        failed = total - passed

        all_times = []
        for r in self.results:
            for s in r.get("scenarios", []):
                if s.get("response_time"):
                    all_times.append(s["response_time"])

        avg_time = round(mean(all_times), 2) if all_times else 0
        max_time = max(all_times) if all_times else 0
        min_time = min(all_times) if all_times else 0

        by_method = {}
        for r in self.results:
            m = r.get("method", "UNKNOWN")
            by_method[m] = by_method.get(m, {"total": 0, "passed": 0})
            by_method[m]["total"] += 1
            if r.get("overall_status") == "passed":
                by_method[m]["passed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "performance": {
                "avg_response_ms": avg_time,
                "max_response_ms": max_time,
                "min_response_ms": min_time
            },
            "by_method": by_method
        }

    def _print_summary(self, summary: dict):
        """打印摘要"""
        print(f"\n{'='*50}")
        print(f"📊 API 测试报告")
        print(f"{'='*50}")
        print(f"   总计: {summary['total']}")
        print(f"   通过: ✅ {summary['passed']}")
        print(f"   失败: ❌ {summary['failed']}")
        print(f"   通过率: {summary['pass_rate']}%")
        print()
        perf = summary.get("performance", {})
        print(f"⏱️  性能指标:")
        print(f"   平均响应: {perf.get('avg_response_ms', 0)}ms")
        print(f"   最大响应: {perf.get('max_response_ms', 0)}ms")
        print(f"   最小响应: {perf.get('min_response_ms', 0)}ms")
        print()

    def _generate_markdown_report(self, summary: dict) -> str:
        """生成 Markdown 报告"""
        lines = []
        lines.append("# API 接口测试报告")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().isoformat()}")
        lines.append(f"> 目标地址: {self.base_url}")
        lines.append("")
        lines.append("## 执行摘要")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总数 | {summary['total']} |")
        lines.append(f"| 通过 | ✅ {summary['passed']} |")
        lines.append(f"| 失败 | ❌ {summary['failed']} |")
        lines.append(f"| 通过率 | **{summary['pass_rate']}%** |")
        lines.append("")

        perf = summary.get("performance", {})
        lines.append("## 性能指标")
        lines.append("")
        lines.append(f"- 平均响应时间: **{perf.get('avg_response_ms', 0)}ms**")
        lines.append(f"- 最大响应时间: {perf.get('max_response_ms', 0)}ms")
        lines.append(f"- 最小响应时间: {perf.get('min_response_ms', 0)}ms")
        lines.append("")

        lines.append("## 按请求类型统计")
        lines.append("")
        lines.append("| 方法 | 总数 | 通过 | 通过率 |")
        lines.append("|------|------|------|--------|")
        for method, stats in summary.get("by_method", {}).items():
            rate = round(stats['passed'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
            lines.append(f"| {method} | {stats['total']} | {stats['passed']} | {rate}% |")
        lines.append("")

        lines.append("## 详细结果")
        lines.append("")

        for result in self.results:
            status_icon = "✅" if result["overall_status"] == "passed" else "❌"
            lines.append(f"### {status_icon} {result.get('name', 'Unknown')}")
            lines.append("")
            lines.append(f"- **方法**: `{result['method']}`")
            lines.append(f"- **路径**: `{result['path']}`")
            lines.append(f"- **URL**: {result['url']}")
            lines.append("")

            for scenario in result.get("scenarios", []):
                sc_icon = "✅" if scenario["status"] == "passed" else "❌"
                lines.append(f"#### {sc_icon} {scenario.get('name', '')}")
                lines.append("")
                lines.append(f"- 状态码: {scenario.get('status_code')} (期望: {scenario.get('expected_status')})")
                lines.append(f"- 响应时间: {scenario.get('response_time')}ms")

                if scenario.get("error"):
                    lines.append(f"- ❌ 错误: {scenario['error']}")

                if scenario.get("response_body"):
                    body_preview = json.dumps(scenario['response_body'], ensure_ascii=False)[:300]
                    lines.append(f"- 响应预览: ```{body_preview}```")
                lines.append("")

        return "\n".join(lines)


def load_apis(source: str) -> List[dict]:
    """加载 API 配置"""
    source_path = Path(source)

    if source_path.exists():
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("apis", data.get("paths", []))
    else:
        if source.startswith("http"):
            print(f"正在从远程加载: {source}")
            import requests
            resp = requests.get(source, timeout=30)
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("apis", [])

    print(f"ERROR: 无法加载 API 配置: {source}")
    sys.exit(1)


async def main_async(args):
    tester = APITester(args.base_url, args.token, args.output_dir)
    apis = load_apis(args.apis)
    await tester.run_all_tests(apis)


def main():
    parser = argparse.ArgumentParser(description="API 接口测试执行器")
    parser.add_argument("--apis", "-a", required=True, help="API 配置文件路径 (JSON) 或 URL")
    parser.add_argument("--base-url", "-b", default="", help="API 基础 URL")
    parser.add_argument("--token", "-t", default=None, help="认证 Token")
    parser.add_argument("--output-dir", "-o", default="./test_results", help="输出目录")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
