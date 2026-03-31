#!/usr/bin/env python3
"""
test_generator.py - 基于业务逻辑的测试用例生成器

基于 business_modeler 和 page_analyzer 的数据，生成覆盖业务场景的测试用例。

用法:
  python test_generator.py --business-doc DOC --page-analysis ANALYSIS [--output FILE]

输出:
  test_cases.json - 机器可读测试用例
  test_cases.csv  - 人工可读测试用例
"""

import sys
import json
import csv
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class TestGenerator:
    """测试用例生成器"""

    def __init__(self, business_doc_path: str, page_analysis_path: str):
        self.business_doc_path = Path(business_doc_path)
        self.page_analysis_path = Path(page_analysis_path)

        self.business_flows: List[dict] = []
        self.business_entities: List[dict] = []
        self.page_analysis: Dict = {}
        self.api_records: List[dict] = []

        self.test_cases: List[dict] = []

    def load_data(self):
        """加载输入数据"""
        # 加载业务逻辑文档
        if self.business_doc_path.exists():
            # 解析 Markdown 格式的业务逻辑文档
            self._parse_business_doc(self.business_doc_path.read_text(encoding="utf-8"))
            print(f"📁 加载业务逻辑文档: {self.business_doc_path}")
        else:
            print(f"⚠️ 业务逻辑文档不存在: {self.business_doc_path}")

        # 加载页面分析数据
        if self.page_analysis_path.exists():
            with open(self.page_analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.page_analysis = data.get("pages", {})
            print(f"📁 加载页面分析: {len(self.page_analysis)} 个页面")
        else:
            print(f"⚠️ 页面分析文件不存在: {self.page_analysis_path}")

    def _parse_business_doc(self, content: str):
        """解析业务逻辑文档"""
        # 提取业务流程（简单解析 Markdown）
        flow_pattern = r'### \d+\. (.+?)\n\*\*描述\*\*: (.+?)\n\*\*入口页面\*\*: `(.+?)`'
        for match in re.finditer(flow_pattern, content, re.DOTALL):
            flow = {
                "name": match.group(1).strip(),
                "description": match.group(2).strip(),
                "entry_page": match.group(3).strip()
            }
            self.business_flows.append(flow)

        # 如果上面的模式没匹配到，尝试另一种格式
        if not self.business_flows:
            flow_pattern2 = r'### \d+\. (.+?)\n\*\*描述\*\*: (.+?)\n'
            for match in re.finditer(flow_pattern2, content, re.DOTALL):
                flow = {
                    "name": match.group(1).strip(),
                    "description": match.group(2).strip(),
                    "entry_page": None
                }
                # 尝试提取入口页面
                entry_match = re.search(r'\*\*入口页面\*\*: `(.+?)`', content[match.end():match.end()+200])
                if entry_match:
                    flow["entry_page"] = entry_match.group(1)
                self.business_flows.append(flow)

        # 提取业务实体
        entity_pattern = r'### (.+?)\n\*\*属性\*\*: (.+?)\n'
        for match in re.finditer(entity_pattern, content):
            entity = {
                "name": match.group(1).strip(),
                "attributes": [a.strip() for a in match.group(2).split(",")]
            }
            self.business_entities.append(entity)

    def _get_page_forms(self, url: str) -> List[dict]:
        """获取页面的表单信息"""
        analysis = self.page_analysis.get(url, {})
        return analysis.get("features", {}).get("forms", [])

    def _get_page_type(self, url: str) -> str:
        """获取页面类型"""
        analysis = self.page_analysis.get(url, {})
        return analysis.get("primary_type", "unknown")

    def generate_flow_tests(self):
        """基于业务流程生成测试用例"""
        for flow in self.business_flows:
            flow_name = flow.get("name", "")
            entry_page = flow.get("entry_page", "")
            description = flow.get("description", "")

            if not entry_page:
                # 如果没有明确入口页面，跳过
                continue

            # 1. 主流程正向测试
            self.test_cases.append({
                "id": f"FLOW_{len(self.test_cases)+1:03d}",
                "name": f"{flow_name} - 主流程测试",
                "type": "business_flow",
                "category": "positive",
                "description": f"验证{flow_name}主流程可以正常完成",
                "url": entry_page,
                "steps": self._generate_flow_steps(flow),
                "expected": f"{flow_name}成功完成",
                "priority": "high",
                "source_flow": flow_name
            })

            # 2. 根据页面类型生成额外的边界测试
            page_type = self._get_page_type(entry_page)
            forms = self._get_page_forms(entry_page)

            if page_type == "login_page" or "登录" in flow_name:
                # 登录错误场景
                self.test_cases.append({
                    "id": f"FLOW_{len(self.test_cases)+1:03d}",
                    "name": f"{flow_name} - 错误密码测试",
                    "type": "business_flow",
                    "category": "negative",
                    "description": "验证使用错误密码无法登录",
                    "url": entry_page,
                    "steps": ["访问登录页面", "输入正确的用户名", "输入错误的密码", "点击登录"],
                    "expected": "登录失败，显示错误提示",
                    "priority": "high",
                    "source_flow": flow_name
                })

                self.test_cases.append({
                    "id": f"FLOW_{len(self.test_cases)+1:03d}",
                    "name": f"{flow_name} - 空字段验证",
                    "type": "business_flow",
                    "category": "negative",
                    "description": "验证提交空表单时的处理",
                    "url": entry_page,
                    "steps": ["访问登录页面", "留空用户名和密码", "点击登录"],
                    "expected": "提示用户名和密码必填",
                    "priority": "medium",
                    "source_flow": flow_name
                })

            elif page_type == "form_page" or forms:
                # 表单验证测试
                for form in forms:
                    required_fields = [f.get("name") for f in form.get("fields", []) if f.get("required")]
                    if required_fields:
                        self.test_cases.append({
                            "id": f"FLOW_{len(self.test_cases)+1:03d}",
                            "name": f"{flow_name} - 必填字段验证",
                            "type": "business_flow",
                            "category": "negative",
                            "description": f"验证必填字段: {', '.join(required_fields)}",
                            "url": entry_page,
                            "steps": [f"访问页面", "留空必填字段", "提交表单"],
                            "expected": "提示必填字段不能为空",
                            "priority": "medium",
                            "source_flow": flow_name
                        })

    def _generate_flow_steps(self, flow: dict) -> List[str]:
        """生成流程步骤"""
        steps = []

        # 从流程描述中提取步骤
        if "entry_page" in flow:
            steps.append(f"访问 {flow['entry_page']}")

        # 根据流程名称推断步骤
        flow_name = flow.get("name", "").lower()

        if "登录" in flow_name or "login" in flow_name:
            steps.extend(["输入用户名", "输入密码", "点击登录按钮"])
        elif "注册" in flow_name or "register" in flow_name or "signup" in flow_name:
            steps.extend(["填写用户名", "填写邮箱", "设置密码", "确认密码", "提交注册"])
        elif "搜索" in flow_name or "search" in flow_name:
            steps.extend(["输入搜索关键词", "点击搜索按钮", "查看搜索结果"])
        else:
            steps.append("执行主要业务操作")

        return steps

    def generate_page_function_tests(self):
        """基于页面功能生成测试用例"""
        for url, analysis in self.page_analysis.items():
            page_type = analysis.get("primary_type", "unknown")
            page_id = analysis.get("page_id", "")
            title = analysis.get("title", "")

            # 1. 页面可访问性测试
            self.test_cases.append({
                "id": f"PAGE_{len(self.test_cases)+1:03d}",
                "name": f"{'登录' if page_type == 'login_page' else title or '页面'} - 可访问性测试",
                "type": "navigation",
                "category": "positive",
                "description": f"验证页面 {url} 可以正常访问",
                "url": url,
                "selector": "",
                "value": "",
                "expected": "HTTP 200",
                "priority": "high",
                "source_page": url
            })

            # 2. 页面关键元素存在性测试
            features = analysis.get("features", {})

            # 表单测试
            forms = features.get("forms", [])
            for i, form in enumerate(forms):
                purpose = form.get("purpose", "form")
                self.test_cases.append({
                    "id": f"PAGE_{len(self.test_cases)+1:03d}",
                    "name": f"{title or '页面'} - {purpose} 表单存在",
                    "type": "element_check",
                    "category": "positive",
                    "description": f"验证{purpose}表单存在于页面",
                    "url": url,
                    "selector": "form",
                    "value": "",
                    "expected": "form element exists",
                    "priority": "medium",
                    "source_page": url
                })

            # 3. 页面类型特定测试
            if page_type == "login_page":
                self.test_cases.append({
                    "id": f"PAGE_{len(self.test_cases)+1:03d}",
                    "name": f"登录页 - 密码输入框存在",
                    "type": "element_check",
                    "category": "positive",
                    "description": "验证密码输入框存在于登录页面",
                    "url": url,
                    "selector": "input[type=password]",
                    "value": "",
                    "expected": "password input exists",
                    "priority": "high",
                    "source_page": url
                })

    def generate_api_tests(self):
        """基于 API 记录生成测试用例"""
        # 尝试从 API 记录文件加载
        api_file = self.page_analysis_path.parent / "apis" / "api_records.json"
        if api_file.exists():
            with open(api_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.api_records = data.get("api_records", [])

        for api in self.api_records:
            url = api.get("url", "")
            method = api.get("method", "GET")

            # 1. API 可访问性测试
            self.test_cases.append({
                "id": f"API_{len(self.test_cases)+1:03d}",
                "name": f"API - {method} {self._get_api_name(url)}",
                "type": "api_check",
                "category": "positive",
                "description": f"验证 API {url} 可以正常访问",
                "url": url,
                "method": method,
                "selector": "",
                "value": url,
                "expected": f"HTTP 200 and valid JSON",
                "priority": "high",
                "source_api": url
            })

            # 2. 根据 HTTP 方法生成特定测试
            if method in ["POST", "PUT", "PATCH"]:
                # 测试无效数据
                self.test_cases.append({
                    "id": f"API_{len(self.test_cases)+1:03d}",
                    "name": f"API - {method} {self._get_api_name(url)} - 无效数据",
                    "type": "api_check",
                    "category": "negative",
                    "description": f"验证 API 对无效数据的处理",
                    "url": url,
                    "method": method,
                    "selector": "",
                    "value": url,
                    "payload": "{}",
                    "expected": "HTTP 400 or error response",
                    "priority": "medium",
                    "source_api": url
                })

            elif method == "DELETE":
                # 测试删除不存在的数据
                self.test_cases.append({
                    "id": f"API_{len(self.test_cases)+1:03d}",
                    "name": f"API - {method} {self._get_api_name(url)} - 删除不存在",
                    "type": "api_check",
                    "category": "negative",
                    "description": "验证删除不存在资源的处理",
                    "url": url + "/nonexistent-id",
                    "method": method,
                    "selector": "",
                    "value": url + "/nonexistent-id",
                    "expected": "HTTP 404 or appropriate error",
                    "priority": "low",
                    "source_api": url
                })

    def _get_api_name(self, url: str) -> str:
        """从 URL 提取 API 名称"""
        parts = url.split("/")
        return parts[-1] if parts[-1] else parts[-2] if len(parts) > 1 else "api"

    def generate_cross_page_tests(self):
        """生成跨页面/端到端测试"""
        # 如果有登录页面和其他页面，生成登录后访问测试
        login_pages = [url for url, a in self.page_analysis.items() if a.get("primary_type") == "login_page"]
        other_pages = [url for url, a in self.page_analysis.items() if a.get("primary_type") != "login_page"]

        if login_pages and other_pages:
            self.test_cases.append({
                "id": f"E2E_{len(self.test_cases)+1:03d}",
                "name": "端到端 - 登录后访问受限页面",
                "type": "business_flow",
                "category": "positive",
                "description": "验证登录后可以正常访问其他页面",
                "url": login_pages[0],
                "steps": [
                    f"访问登录页面 {login_pages[0]}",
                    "执行登录",
                    f"访问 {other_pages[0]}"
                ],
                "expected": "成功访问目标页面",
                "priority": "high",
                "is_e2e": True
            })

    def generate_all_tests(self):
        """生成所有测试用例"""
        print("🔧 生成测试用例...")

        self.generate_flow_tests()
        print(f"  📋 业务流程测试: {len(self.test_cases)} 个")

        start_idx = len(self.test_cases)
        self.generate_page_function_tests()
        print(f"  📋 页面功能测试: {len(self.test_cases) - start_idx} 个")

        start_idx = len(self.test_cases)
        self.generate_api_tests()
        print(f"  📋 API 测试: {len(self.test_cases) - start_idx} 个")

        start_idx = len(self.test_cases)
        self.generate_cross_page_tests()
        print(f"  📋 端到端测试: {len(self.test_cases) - start_idx} 个")

        print(f"\n✅ 总计生成: {len(self.test_cases)} 个测试用例")

    def save_tests(self, output_path: str):
        """保存测试用例"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 保存 JSON 格式
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total_cases": len(self.test_cases),
                "test_cases": self.test_cases
            }, f, ensure_ascii=False, indent=2)

        print(f"📁 测试用例已保存 (JSON): {output_file}")

        # 保存 CSV 格式
        csv_file = output_file.with_suffix(".csv")
        if self.test_cases:
            with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "名称", "类型", "分类", "描述", "URL", "优先级", "期望结果"])
                for case in self.test_cases:
                    writer.writerow([
                        case.get("id", ""),
                        case.get("name", ""),
                        case.get("type", ""),
                        case.get("category", ""),
                        case.get("description", ""),
                        case.get("url", ""),
                        case.get("priority", ""),
                        case.get("expected", "")
                    ])
            print(f"📁 测试用例已保存 (CSV): {csv_file}")


def main():
    parser = argparse.ArgumentParser(description="基于业务逻辑的测试用例生成器")
    parser.add_argument("--business-doc", "-b", required=True, help="业务逻辑文档路径 (Markdown)")
    parser.add_argument("--page-analysis", "-p", required=True, help="页面分析结果路径 (JSON)")
    parser.add_argument("--output", "-o", default="./test_data/test_cases.json", help="输出文件路径")
    args = parser.parse_args()

    generator = TestGenerator(args.business_doc, args.page_analysis)
    generator.load_data()
    generator.generate_all_tests()
    generator.save_tests(args.output)


if __name__ == "__main__":
    main()
