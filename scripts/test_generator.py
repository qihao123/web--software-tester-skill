#!/usr/bin/env python3
"""
test_generator.py - 基于业务逻辑生成测试用例

支持:
- 从业务流程生成端到端测试用例
- 从 API 文档生成接口测试用例
- 从页面分析生成功能测试用例
- 生成标准化的测试计划文档

用法:
  python test_generator.py --business-doc MD_PATH [--api-doc JSON_PATH] [--page-analysis JSON_PATH] [--output OUTPUT]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import uuid


class TestGenerator:
    def __init__(self):
        self.test_cases = []
        self.test_plan = None

    def generate_from_business(self, business_doc_path: str, api_doc_path: str = None,
                                page_analysis: str = None) -> dict:
        """基于业务文档生成测试用例"""
        business_doc = Path(business_doc_path)
        if not business_doc.exists():
            print(f"ERROR: 业务文档不存在: {business_doc_path}")
            sys.exit(1)

        business_content = business_doc.read_text(encoding="utf-8")

        api_data = {}
        if api_doc_path and Path(api_doc_path).exists():
            with open(api_doc_path, "r", encoding="utf-8") as f:
                api_data = json.load(f)

        page_data = {}
        if page_analysis and Path(page_analysis).exists():
            with open(page_analysis, "r", encoding="utf-8") as f:
                page_data = json.load(f)

        print("\n🧪 开始生成测试用例...")

        flow_cases = self._generate_flow_test_cases(business_content)
        api_cases = self._generate_api_test_cases(api_data)
        ui_cases = self._generate_ui_test_cases(page_data)
        security_cases = self._generate_security_test_cases()

        all_cases = flow_cases + api_cases + ui_cases + security_cases

        self.test_cases = all_cases

        test_plan = self._generate_test_plan(all_cases, business_content, api_data, page_data)

        return {
            "generated_at": datetime.now().isoformat(),
            "total_cases": len(all_cases),
            "by_type": {
                "business_flow": len(flow_cases),
                "api": len(api_cases),
                "ui": len(ui_cases),
                "security": len(security_cases)
            },
            "test_cases": all_cases,
            "test_plan": test_plan
        }

    def _generate_flow_test_cases(self, business_content: str) -> list:
        """从业务流程生成测试用例"""
        cases = []
        case_id = 1

        flows = [
            {
                "name": "用户登录",
                "type": "business_flow",
                "category": "positive",
                "priority": "P0",
                "scenarios": [
                    {"name": "正确凭证登录", "data": {"username": "admin", "password": "123456"}, "expected": "登录成功"},
                    {"name": "错误密码", "data": {"username": "admin", "password": "wrong"}, "expected": "提示密码错误"},
                    {"name": "空用户名", "data": {"username": "", "password": "123456"}, "expected": "提示输入用户名"},
                    {"name": "空密码", "data": {"username": "admin", "password": ""}, "expected": "提示输入密码"}
                ]
            },
            {
                "name": "数据列表查询",
                "type": "navigation",
                "category": "positive",
                "priority": "P0",
                "scenarios": [
                    {"name": "默认加载列表", "data": {}, "expected": "显示数据列表"},
                    {"name": "关键词搜索", "data": {"keyword": "test"}, "expected": "过滤显示结果"},
                    {"name": "翻页操作", "data": {"page": 2}, "expected": "显示第二页数据"},
                    {"name": "空结果搜索", "data": {"keyword": "nonexistent_xyz_123"}, "expected": "显示无结果提示"}
                ]
            },
            {
                "name": "新增数据",
                "type": "form_submit",
                "category": "positive",
                "priority": "P0",
                "scenarios": [
                    {"name": "正常新增", "data": {"name": "测试数据", "status": "1"}, "expected": "保存成功并刷新列表"},
                    {"name": "必填项为空", "data": {"name": ""}, "expected": "提示必填项不能为空"},
                    {"name": "重复名称", "data": {"name": "已存在名称"}, "expected": "提示名称已存在或根据业务规则处理"},
                    {"name": "超长输入", "data": {"name": "a" * 1000}, "expected": "提示长度超限或截断处理"}
                ]
            },
            {
                "name": "编辑数据",
                "type": "form_submit",
                "category": "positive",
                "priority": "P0",
                "scenarios": [
                    {"name": "正常编辑", "data": {"id": 1, "name": "修改后名称"}, "expected": "更新成功"},
                    {"name": "修改为空值（非必填）", "data": {"id": 1, "remark": ""}, "expected": "更新成功"},
                    {"name": "编辑不存在的记录", "data": {"id": 99999}, "expected": "提示记录不存在"}
                ]
            },
            {
                "name": "删除数据",
                "type": "element_check",
                "category": "negative",
                "priority": "P0",
                "scenarios": [
                    {"name": "正常删除并确认", "data": {"id": 1}, "expected": "删除成功，列表不再显示"},
                    {"name": "取消删除", "data": {}, "expected": "对话框关闭，数据保留"},
                    {"name": "删除被引用的数据", "data": {"id": 2}, "expected": "提示无法删除或有级联选项"}
                ]
            }
        ]

        for flow in flows:
            for scenario in flow["scenarios"]:
                case = {
                    "id": f"TC{case_id:03d}",
                    "name": f"{flow['name']} - {scenario['name']}",
                    "type": flow["type"],
                    "category": scenario.get("category", flow["category"]),
                    "description": f"验证 {scenario['name']} 场景",
                    "flow_name": flow["name"],
                    "priority": flow["priority"],
                    "preconditions": ["用户已登录", "具有相应权限"],
                    "test_data": scenario["data"],
                    "expected_result": scenario["expected"],
                    "steps": self._generate_steps_for_flow(flow["type"], scenario),
                    "acceptance_criteria": [f"场景执行完成时: {scenario['expected']}"]
                }
                cases.append(case)
                case_id += 1

        return cases

    def _generate_api_test_cases(self, api_data: dict) -> list:
        """从 API 数据生成接口测试用例"""
        cases = []
        if not api_data:
            return cases

        case_id = 100

        apis = api_data.get("paths", api_data.get("api_endpoints", []))
        if not apis:
            return cases

        for api_path, methods in apis.items() if isinstance(apis, dict) else [(a.get("path", ""), a) for a in apis]:
            if isinstance(methods, dict):
                for method, details in methods.items():
                    case = self._create_api_case(f"API{case_id}", method.upper(), api_path, details)
                    if case:
                        cases.append(case)
                        case_id += 1
            elif isinstance(methods, dict) and "method" in methods:
                case = self._create_api_case(f"API{case_id}", methods.get("method", "GET"),
                                             api_path, methods)
                if case:
                    cases.append(case)
                    case_id += 1

        return cases

    def _create_api_case(self, case_id: str, method: str, path: str, details: dict) -> dict:
        """创建单个 API 测试用例"""
        base_case = {
            "id": case_id,
            "name": f"API {method} {path}",
            "type": "api_check",
            "category": "positive",
            "url": path,
            "method": method,
            "priority": "P0" if method in ["POST", "PUT", "DELETE"] else "P1",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{token}}"},
            "preconditions": ["获取有效 Token"],
            "expected_status": 200 if method == "GET" else (201 if method == "POST" else 200),
            "test_scenarios": [
                {"name": "正常请求", "payload": {}, "expected_status": 200},
                {"name": "未认证请求", "payload": {}, "headers": {"Authorization": ""},
                 "expected_status": 401},
                {"name": "非法参数", "payload": {"invalid": "data"}, "expected_status": 400}
            ]
        }

        if method == "GET":
            base_case["test_scenarios"].extend([
                {"name": "不存在的 ID", "params": {"id": -1}, "expected_status": 404}
            ])

        return base_case

    def _generate_ui_test_cases(self, page_data: dict) -> list:
        """从页面分析生成 UI 测试用例"""
        cases = []
        if not page_data:
            return cases

        case_id = 200

        pages = page_data.get("pages", [])
        for page in pages:
            page_name = page.get("name", "")
            page_type = page.get("type", "")

            base_ui_case = {
                "id": f"UI{case_id}",
                "name": f"UI-{page_name}页面渲染验证",
                "type": "element_check",
                "category": "positive",
                "priority": "P1",
                "url": page.get("url", ""),
                "selector": "",
                "expected": "页面正常渲染无报错"
            }

            elements = page.get("key_elements", [])
            for elem in elements[:5]:
                selector = elem.get("selector", "") or elem.get("class", "")
                if selector:
                    case = base_ui_case.copy()
                    case["id"] = f"UI{case_id}"
                    case["name"] = f"UI-{page_name}-{elem.get('text', '元素')}"
                    case["selector"] = selector if selector.startswith(("#", ".")) else f".{selector}"
                    case["expected"] = f"元素 {elem.get('text', selector)} 可见且可交互"
                    cases.append(case)
                    case_id += 1

        return cases

    def _generate_security_test_cases(self) -> list:
        """生成安全测试用例"""
        case_id = 300
        security_tests = [
            {
                "name": "SQL 注入检测 - 登录框",
                "type": "security",
                "category": "negative",
                "priority": "P0",
                "test_payloads": ["' OR '1'='1", "'--", "; DROP TABLE users--"],
                "target": "login_form"
            },
            {
                "name": "XSS 检测 - 输入框",
                "type": "security",
                "category": "negative",
                "priority": "P0",
                "test_payloads": ["<script>alert('xss')</script>", "<img onerror='alert(1)' src=x>"],
                "target": "input_fields"
            },
            {
                "name": "越权访问检测",
                "type": "security",
                "category": "negative",
                "priority": "P0",
                "description": "使用低权限用户 Token 访问管理员 API",
                "test_method": "token_substitution"
            },
            {
                "name": "CSRF 防护验证",
                "type": "security",
                "category": "negative",
                "priority": "P1",
                "description": "检查表单是否包含 CSRF Token",
                "test_method": "header_inspection"
            },
            {
                "name": "敏感信息泄露检测",
                "type": "security",
                "category": "negative",
                "priority": "P1",
                "check_items": ["password in response", "token in URL", "stack trace visible"]
            }
        ]

        cases = []
        for test in security_tests:
            case = {
                "id": f"SEC{case_id}",
                **test,
                "preconditions": ["获取测试账号"],
                "expected_result": "系统正确防御攻击，不泄露信息"
            }
            cases.append(case)
            case_id += 1

        return cases

    def _generate_steps_for_flow(self, flow_type: str, scenario: dict) -> list:
        """为业务流程生成步骤"""
        generic_steps = [
            "1. 打开目标页面",
            "2. 等待页面加载完成",
            "3. 定位操作元素"
        ]

        type_specific = {
            "business_flow": [
                "4. 填写/选择测试数据",
                "5. 触发提交操作",
                "6. 验证结果符合预期"
            ],
            "navigation": [
                "4. 执行导航操作",
                "5. 验证页面状态"
            ],
            "form_submit": [
                "4. 填写表单字段",
                "5. 点击提交按钮",
                "6. 验证表单响应"
            ],
            "element_check": [
                "4. 检查元素状态",
                "5. 验证属性值"
            ]
        }

        return generic_steps + type_specific.get(flow_type, generic_steps[-2:])

    def _generate_test_plan(self, cases: list, business_content: str,
                            api_data: dict, page_data: dict) -> dict:
        """生成测试计划"""
        total = len(cases)
        p0_count = sum(1 for c in cases if c.get("priority") == "P0")
        p1_count = sum(1 for c in cases if c.get("priority") == "P1")

        by_category = {}
        for c in cases:
            cat = c.get("type", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        plan = {
            "plan_info": {
                "project_name": "Web 应用自动化测试",
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "author": "Auto Generated",
                "status": "draft"
            },
            "scope": {
                "in_scope": [
                    "核心业务流程功能验证",
                    "API 接口正异常测试",
                    "关键 UI 元素可用性",
                    "基础安全漏洞扫描"
                ],
                "out_of_scope": [
                    "性能压测（需单独计划）",
                    "浏览器兼容性全面测试",
                    "移动端适配测试"
                ]
            },
            "statistics": {
                "total_cases": total,
                "p0_critical": p0_count,
                "p1_high": p1_count,
                "estimated_hours": max(total * 0.25, 8),
                "by_category": by_category
            },
            "strategy": {
                "testing_types": ["功能测试", "接口测试", "安全测试"],
                "tools": ["Playwright", "Requests", "Custom Scripts"],
                "environment": ["测试环境", "预发布环境"],
                "entry_criteria": ["测试环境就绪", "测试数据准备完毕"],
                "exit_criteria": ["P0 用例全部通过", "无严重缺陷遗留"]
            },
            "risk_assessment": [
                {"risk": "依赖外部服务", "mitigation": "Mock 外部依赖", "impact": "medium"},
                {"risk": "测试数据污染", "mitigation": "使用独立测试数据库", "impact": "low"},
                {"risk": "环境不稳定", "mitigation": "容器化测试环境", "impact": "high"}
            ],
            "schedule": {
                "phases": [
                    {"phase": "冒烟测试", "duration": "0.5天", "cases": p0_count},
                    {"phase": "功能测试", "duration": "2天", "cases": total - p0_count - len([c for c in cases if c.get("type") == "security"])},
                    {"phase": "回归测试", "duration": "1天", "cases": "全部"},
                    {"phase": "验收测试", "duration": "0.5天", "cases": P0}
                ]
            }
        }

        return plan

    def save_output(self, output_path: str, data: dict):
        """保存输出文件"""
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 测试用例已生成: {out_path}")
        print(f"   总计: {data['total_cases']} 个用例")

        by_type = data.get("by_type", {})
        print(f"   分布:")
        for t, count in by_type.items():
            print(f"     - {t}: {count}")


def main():
    parser = argparse.ArgumentParser(description="测试用例生成器")
    parser.add_argument("--business-doc", "-b", required=True, help="业务逻辑文档路径 (Markdown)")
    parser.add_argument("--api-doc", "-a", default=None, help="API 文档路径 (JSON/Swagger)")
    parser.add_argument("--page-analysis", "-p", default=None, help="页面分析结果路径")
    parser.add_argument("--output", "-o", default="./test_data/test_cases.json", help="输出路径")
    args = parser.parse_args()

    generator = TestGenerator()
    result = generator.generate_from_business(
        args.business_doc,
        args.api_doc,
        args.page_analysis
    )
    generator.save_output(args.output, result)


if __name__ == "__main__":
    main()
