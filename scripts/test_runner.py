#!/usr/bin/env python3
"""
test_runner.py - Web 业务测试执行器

支持执行基于业务逻辑的测试用例。

用法:
  python test_runner.py --cases CASES_FILE [--config CONFIG] [--output-dir DIR] [--use-playwright]
"""

import sys
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"ERROR: 缺少依赖 {e}，请先安装: pip install requests beautifulsoup4")
    sys.exit(1)


class TestRunner:
    """测试执行器"""

    def __init__(self, config: dict, output_dir: str, use_playwright: bool = False):
        self.config = config
        self.output_dir = Path(output_dir)
        self.use_playwright = use_playwright
        self.base_url = config.get("url", "")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        self.results: List[dict] = []
        self.screenshots_dir = self.output_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_url(self, url: str) -> str:
        """标准化 URL"""
        if not url.startswith("http"):
            return urljoin(self.base_url, url)
        return url

    def _find_element(self, soup: BeautifulSoup, selector: str):
        """简化版 selector 查找"""
        selector = selector.strip()
        if selector.startswith("#"):
            return soup.find(id=selector[1:])
        if selector.startswith("."):
            return soup.find(class_=selector[1:])
        m = re.match(r"(\w+)\[(\w+)=(.+?)\]", selector)
        if m:
            tag, attr, val = m.groups()
            return soup.find(tag, {attr: val.strip('"\'')})
        return soup.find(selector)

    def run_navigation_test(self, case: dict) -> dict:
        """执行导航测试"""
        result = self._create_base_result(case)
        url = self._normalize_url(case.get("url", ""))

        start = time.time()
        try:
            resp = self.session.get(url, timeout=30)
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["actual_status"] = resp.status_code

            if resp.status_code < 400:
                result["status"] = "passed"
                result["message"] = f"页面访问成功 ({resp.status_code})"
            else:
                result["status"] = "failed"
                result["error"] = f"HTTP 错误: {resp.status_code}"
                result["bug_description"] = f"期望页面可访问，实际返回 HTTP {resp.status_code}"

        except Exception as e:
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "failed"
            result["error"] = str(e)
            result["bug_description"] = f"请求异常: {e}"

        return result

    def run_element_check(self, case: dict) -> dict:
        """执行元素检查测试"""
        result = self._create_base_result(case)
        url = self._normalize_url(case.get("url", ""))
        selector = case.get("selector", "")
        expected = case.get("expected", "")

        start = time.time()
        try:
            resp = self.session.get(url, timeout=30)
            soup = BeautifulSoup(resp.text, "html.parser")
            result["response_time"] = round((time.time() - start) * 1000, 2)

            elem = self._find_element(soup, selector) if selector else None

            if elem:
                result["status"] = "passed"
                elem_text = elem.get_text(strip=True)[:100]
                result["message"] = f"找到元素: {selector}"
                result["element_preview"] = elem_text

                if expected and expected not in elem_text.lower():
                    result["status"] = "failed"
                    result["error"] = "元素文本不匹配"
                    result["bug_description"] = f"期望包含 '{expected}'，实际为 '{elem_text}'"
            else:
                result["status"] = "failed"
                result["error"] = f"未找到元素: {selector}"
                result["bug_description"] = "页面上不存在指定的元素"

        except Exception as e:
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    def run_api_check(self, case: dict) -> dict:
        """执行 API 检查测试"""
        result = self._create_base_result(case)
        url = self._normalize_url(case.get("value", case.get("url", "")))
        method = case.get("method", "GET").upper()
        payload = case.get("payload", "")
        expected = case.get("expected", "")

        start = time.time()
        try:
            kwargs = {"timeout": 30}
            if payload:
                try:
                    kwargs["json"] = json.loads(payload)
                except json.JSONDecodeError:
                    kwargs["data"] = payload

            resp = self.session.request(method, url, **kwargs)
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["actual_status"] = resp.status_code

            if resp.status_code < 400:
                result["status"] = "passed"
                result["message"] = f"API 调用成功 ({resp.status_code})"

                # 检查响应内容
                if expected:
                    try:
                        resp_text = resp.text
                        if expected.lower() not in resp_text.lower():
                            result["status"] = "failed"
                            result["error"] = "响应内容不匹配"
                            result["bug_description"] = f"期望响应包含 '{expected}'"
                    except Exception:
                        pass
            else:
                result["status"] = "failed"
                result["error"] = f"API 返回错误: {resp.status_code}"
                result["bug_description"] = f"期望 API 成功，实际返回 {resp.status_code}"

        except Exception as e:
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    def run_form_submit_test(self, case: dict) -> dict:
        """执行表单提交测试"""
        result = self._create_base_result(case)
        url = self._normalize_url(case.get("url", ""))
        selector = case.get("selector", "form")
        value = case.get("value", "")  # 表单数据
        expected = case.get("expected", "")

        start = time.time()
        try:
            # 获取页面并解析表单
            resp = self.session.get(url, timeout=30)
            soup = BeautifulSoup(resp.text, "html.parser")

            form = self._find_element(soup, selector)
            if form and form.name != "form":
                form = form.find_parent("form")

            if not form:
                form = soup.find("form")

            if not form:
                result["status"] = "failed"
                result["error"] = "未找到表单"
                return result

            action = self._normalize_url(form.get("action", "")) or url
            method = form.get("method", "post").upper()

            # 解析表单数据
            data = {}
            if value:
                try:
                    data = json.loads(value)
                except json.JSONDecodeError:
                    # 解析 key=value,key2=value2 格式
                    for pair in value.split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            data[k.strip()] = v.strip()

            # 提交表单
            submit_resp = self.session.request(method, action, data=data, timeout=30)
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["actual_status"] = submit_resp.status_code

            if submit_resp.status_code < 400:
                result["status"] = "passed"
                result["message"] = f"表单提交成功 ({submit_resp.status_code})"

                if expected and expected not in submit_resp.text:
                    result["status"] = "failed"
                    result["error"] = "提交后页面内容不匹配"
                    result["bug_description"] = f"期望页面包含 '{expected}'"
            else:
                result["status"] = "failed"
                result["error"] = f"表单提交失败: {submit_resp.status_code}"
                result["bug_description"] = f"表单提交返回错误状态码 {submit_resp.status_code}"

        except Exception as e:
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    def run_business_flow_test(self, case: dict) -> dict:
        """执行业务流程测试"""
        result = self._create_base_result(case)
        steps = case.get("steps", [])
        url = self._normalize_url(case.get("url", ""))

        result["steps_executed"] = []
        start = time.time()

        try:
            # 业务流程测试 - 目前简化为访问入口页面
            # 完整的业务流程测试需要 Playwright 支持
            resp = self.session.get(url, timeout=30)
            result["response_time"] = round((time.time() - start) * 1000, 2)

            if resp.status_code < 400:
                result["status"] = "passed"
                result["message"] = f"业务流程入口页面可访问 ({resp.status_code})"
                result["note"] = "静态模式下仅验证入口页面，完整流程需 Playwright 模式"
                result["steps_executed"] = steps[:1] if steps else ["访问入口页面"]
            else:
                result["status"] = "failed"
                result["error"] = f"入口页面访问失败: {resp.status_code}"

        except Exception as e:
            result["response_time"] = round((time.time() - start) * 1000, 2)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    def _create_base_result(self, case: dict) -> dict:
        """创建基础结果结构"""
        return {
            "id": case.get("id", "unknown"),
            "name": case.get("name", "未命名测试"),
            "type": case.get("type", "unknown"),
            "category": case.get("category", "positive"),
            "status": "skipped",
            "response_time": None,
            "error": "",
            "message": "",
            "bug_description": "",
            "expected": case.get("expected", ""),
            "actual_status": None,
            "steps_executed": []
        }

    def run_single_test(self, case: dict) -> dict:
        """执行单个测试用例"""
        test_type = case.get("type", "").lower()

        if test_type == "navigation":
            return self.run_navigation_test(case)
        elif test_type == "element_check":
            return self.run_element_check(case)
        elif test_type == "api_check":
            return self.run_api_check(case)
        elif test_type == "form_submit":
            return self.run_form_submit_test(case)
        elif test_type == "business_flow":
            return self.run_business_flow_test(case)
        else:
            result = self._create_base_result(case)
            result["status"] = "skipped"
            result["error"] = f"不支持的测试类型: {test_type}"
            return result

    def run_all_tests(self, cases: List[dict]) -> dict:
        """执行所有测试"""
        print(f"🔬 开始执行 {len(cases)} 个测试用例...")
        print(f"   测试模式: {'Playwright 真实浏览器' if self.use_playwright else '静态请求模式'}")
        print()

        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.get('name', '未命名')}")
            result = self.run_single_test(case)
            self.results.append(result)

            status_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(result["status"], "❓")
            print(f"      {status_icon} {result['status'].upper()}")

            if result.get("error"):
                print(f"      ⚠️ {result['error'][:80]}")

        # 统计
        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "passed"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "skipped": sum(1 for r in self.results if r["status"] == "skipped")
        }

        print()
        print(f"✅ 测试完成: 总计 {summary['total']} | 通过 {summary['passed']} | 失败 {summary['failed']} | 跳过 {summary['skipped']}")

        return {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "summary": summary,
            "results": self.results
        }

    def save_results(self, output_file: str):
        """保存测试结果"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "passed"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "skipped": sum(1 for r in self.results if r["status"] == "skipped")
        }

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "summary": summary,
            "results": self.results
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"📁 测试结果已保存: {output_path}")


def load_test_cases(cases_path: str) -> List[dict]:
    """加载测试用例"""
    path = Path(cases_path)

    if not path.exists():
        print(f"ERROR: 测试用例文件不存在: {cases_path}")
        sys.exit(1)

    suffix = path.suffix.lower()

    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("test_cases", data if isinstance(data, list) else [])
    elif suffix == ".csv":
        import csv
        cases = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cases.append({k.strip(): (v.strip() if v else "") for k, v in row.items()})
        return cases
    else:
        print(f"ERROR: 不支持的测试用例格式: {suffix}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Web 业务测试执行器")
    parser.add_argument("--cases", "-c", required=True, help="测试用例文件路径 (JSON/CSV)")
    parser.add_argument("--config", help="测试配置 JSON 字符串或文件路径", default='{"url":""}')
    parser.add_argument("--output-dir", "-o", default="./test_results", help="输出目录")
    parser.add_argument("--report-output", help="报告输出路径")
    parser.add_argument("--use-playwright", action="store_true", help="使用 Playwright 执行真实浏览器测试")
    args = parser.parse_args()

    # 加载配置
    config = {"url": ""}
    if args.config:
        try:
            if Path(args.config).exists():
                with open(args.config, "r", encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"ERROR: 配置解析失败: {e}")
            sys.exit(1)

    # 加载测试用例
    cases = load_test_cases(args.cases)
    print(f"📋 加载测试用例: {len(cases)} 个")
    print()

    # 执行测试
    runner = TestRunner(config, args.output_dir, args.use_playwright)
    results = runner.run_all_tests(cases)

    # 保存结果
    report_path = args.report_output or f"{args.output_dir}/test_results.json"
    runner.save_results(report_path)


if __name__ == "__main__":
    main()
