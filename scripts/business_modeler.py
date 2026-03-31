#!/usr/bin/env python3
"""
business_modeler.py - 业务建模器

基于 crawler 和 page_analyzer 的数据，生成业务逻辑文档。

用法:
  python business_modeler.py --input-dir DIR [--output FILE]

输入:
  input_dir/page_tree.json
  input_dir/apis/api_records.json
  input_dir/page_analysis.json

输出:
  business_logic.md - 业务逻辑文档
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class BusinessModeler:
    """业务建模器"""

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.page_tree_file = self.input_dir / "page_tree.json"
        self.api_records_file = self.input_dir / "apis" / "api_records.json"
        self.page_analysis_file = self.input_dir / "page_analysis.json"

        self.page_tree: Dict = {}
        self.api_records: List[dict] = []
        self.page_analysis: Dict = {}

        # 业务模型数据
        self.business_entities: List[dict] = []
        self.business_flows: List[dict] = []
        self.page_to_function: Dict[str, List[str]] = {}
        self.api_to_function: Dict[str, List[str]] = {}

    def load_data(self):
        """加载所有输入数据"""
        # 加载页面树
        if self.page_tree_file.exists():
            with open(self.page_tree_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.page_tree = data.get("pages", {})
                self.base_url = data.get("base_url", "")
            print(f"📁 加载页面树: {len(self.page_tree)} 个页面")
        else:
            print(f"⚠️ 页面树文件不存在: {self.page_tree_file}")

        # 加载 API 记录
        if self.api_records_file.exists():
            with open(self.api_records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.api_records = data.get("api_records", [])
            print(f"📁 加载 API 记录: {len(self.api_records)} 个 API")
        else:
            print(f"⚠️ API 记录文件不存在: {self.api_records_file}")

        # 加载页面分析
        if self.page_analysis_file.exists():
            with open(self.page_analysis_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.page_analysis = data.get("pages", {})
            print(f"📁 加载页面分析: {len(self.page_analysis)} 个页面")
        else:
            print(f"⚠️ 页面分析文件不存在: {self.page_analysis_file}")

    def _identify_business_entities(self):
        """识别业务实体"""
        entities = []

        # 从 API 端点推断业务实体
        for api in self.api_records:
            url = api.get("url", "")
            path = url.split("?")[0]  # 去掉查询参数

            # 提取可能的实体名（如 /api/users -> User）
            parts = [p for p in path.split("/") if p and not p.startswith("{")]
            if parts:
                # 常见的实体名模式
                entity_candidates = [p for p in parts if p not in ["api", "v1", "v2", "rest", "graphql"]]
                for candidate in entity_candidates:
                    entity_name = candidate.rstrip("s").title()  # users -> User
                    if not any(e["name"] == entity_name for e in entities):
                        entities.append({
                            "name": entity_name,
                            "plural": candidate if candidate.endswith("s") else candidate + "s",
                            "source_api": url,
                            "operations": self._infer_operations(path)
                        })

        # 从页面分析中的数据实体推断
        for url, analysis in self.page_analysis.items():
            data_entities = analysis.get("features", {}).get("data_entities", [])
            for de in data_entities:
                if de.get("type") == "table":
                    columns = de.get("columns", [])
                    entity_name = self._infer_entity_name_from_columns(columns)
                    if entity_name and not any(e["name"] == entity_name for e in entities):
                        entities.append({
                            "name": entity_name,
                            "source_page": url,
                            "attributes": columns
                        })

        # 从表单字段推断
        form_entities = self._extract_entities_from_forms()
        for fe in form_entities:
            if not any(e["name"] == fe["name"] for e in entities):
                entities.append(fe)

        self.business_entities = entities
        print(f"  🎯 识别业务实体: {len(entities)} 个")

    def _infer_operations(self, path: str) -> List[str]:
        """从 API 路径推断操作类型"""
        operations = []
        lower_path = path.lower()

        # RESTful 模式
        if "/create" in lower_path or "/add" in lower_path:
            operations.append("CREATE")
        elif "/update" in lower_path or "/edit" in lower_path:
            operations.append("UPDATE")
        elif "/delete" in lower_path or "/remove" in lower_path:
            operations.append("DELETE")
        elif "/list" in lower_path or "/all" in lower_path:
            operations.append("LIST")
        elif "/get" in lower_path or "/detail" in lower_path or "/{id}" in lower_path:
            operations.append("READ")

        # HTTP 方法推断
        for api in self.api_records:
            if path in api.get("url", ""):
                method = api.get("method", "GET")
                if method == "GET":
                    if not operations:
                        operations.append("READ")
                elif method == "POST":
                    if "CREATE" not in operations:
                        operations.append("CREATE")
                elif method == "PUT" or method == "PATCH":
                    if "UPDATE" not in operations:
                        operations.append("UPDATE")
                elif method == "DELETE":
                    if "DELETE" not in operations:
                        operations.append("DELETE")

        return operations if operations else ["UNKNOWN"]

    def _infer_entity_name_from_columns(self, columns: List[str]) -> Optional[str]:
        """从列名推断实体名"""
        # 常见的实体列名模式
        common_patterns = {
            "User": ["username", "email", "password", "user_id"],
            "Product": ["product_name", "price", "sku", "stock"],
            "Order": ["order_id", "total", "status", "order_date"],
            "Article": ["title", "content", "author", "published_at"],
            "Comment": ["comment", "author", "post_id"],
        }

        col_lower = [c.lower() for c in columns]

        for entity, patterns in common_patterns.items():
            matches = sum(1 for p in patterns if any(p in c for c in col_lower))
            if matches >= 2:
                return entity

        return None

    def _extract_entities_from_forms(self) -> List[dict]:
        """从表单中提取实体"""
        entities = []

        for url, analysis in self.page_analysis.items():
            forms = analysis.get("features", {}).get("forms", [])
            for form in forms:
                purpose = form.get("purpose", "")
                fields = form.get("fields", [])

                if purpose == "login":
                    if not any(e["name"] == "User" for e in entities):
                        entities.append({
                            "name": "User",
                            "source": "login_form",
                            "attributes": ["username", "password"]
                        })
                elif purpose == "registration":
                    if not any(e["name"] == "User" for e in entities):
                        entities.append({
                            "name": "User",
                            "source": "registration_form",
                            "attributes": [f.get("name", "") for f in fields if f.get("name")]
                        })

        return entities

    def _identify_business_flows(self):
        """识别业务流程"""
        flows = []

        # 从页面类型识别流程
        login_pages = [url for url, a in self.page_analysis.items()
                      if a.get("primary_type") == "login_page"]
        register_pages = [url for url, a in self.page_analysis.items()
                         if a.get("primary_type") == "register_page"]
        search_pages = [url for url, a in self.page_analysis.items()
                       if a.get("primary_type") == "search_page"]
        list_pages = [url for url, a in self.page_analysis.items()
                     if a.get("primary_type") == "list_page"]
        form_pages = [url for url, a in self.page_analysis.items()
                     if a.get("primary_type") == "form_page"]

        # 登录流程
        if login_pages:
            flows.append({
                "name": "用户登录",
                "description": "用户通过登录页面进行身份验证",
                "entry_page": login_pages[0],
                "steps": [
                    {"action": "访问登录页面", "page": login_pages[0]},
                    {"action": "输入用户名/邮箱", "input": "username"},
                    {"action": "输入密码", "input": "password"},
                    {"action": "点击登录按钮"},
                    {"action": "验证登录状态", "expected": "跳转到首页或仪表盘"}
                ],
                "involved_apis": self._find_related_apis(["login", "auth", "token", "signin"]),
                "success_criteria": ["HTTP 200", "返回认证 token", "跳转到登录后页面"]
            })

        # 注册流程
        if register_pages:
            flows.append({
                "name": "用户注册",
                "description": "新用户创建账户",
                "entry_page": register_pages[0],
                "steps": [
                    {"action": "访问注册页面", "page": register_pages[0]},
                    {"action": "填写注册信息", "inputs": ["username", "email", "password"]},
                    {"action": "提交注册表单"},
                    {"action": "验证注册结果"}
                ],
                "involved_apis": self._find_related_apis(["register", "signup", "create"]),
                "success_criteria": ["账户创建成功", "发送验证邮件"]
            })

        # 搜索流程
        if search_pages:
            flows.append({
                "name": "内容搜索",
                "description": "用户搜索系统中的内容",
                "entry_page": search_pages[0],
                "steps": [
                    {"action": "访问搜索页面", "page": search_pages[0]},
                    {"action": "输入搜索关键词"},
                    {"action": "执行搜索"},
                    {"action": "查看搜索结果"}
                ],
                "involved_apis": self._find_related_apis(["search", "query", "find"]),
                "success_criteria": ["返回搜索结果列表", "结果包含关键词"]
            })

        # 列表查看流程
        if list_pages:
            flows.append({
                "name": "数据列表查看",
                "description": "查看数据列表并浏览详情",
                "entry_page": list_pages[0],
                "steps": [
                    {"action": "访问列表页面", "page": list_pages[0]},
                    {"action": "加载列表数据"},
                    {"action": "浏览列表项"},
                    {"action": "点击某一项查看详情"}
                ],
                "involved_apis": self._find_related_apis(["list", "items", "get"]),
                "success_criteria": ["列表数据加载成功", "支持分页"]
            })

        # 从页面分析中的用户流程提取
        for url, analysis in self.page_analysis.items():
            user_flows = analysis.get("features", {}).get("user_flows", [])
            for flow in user_flows:
                if not any(f["name"] == flow["name"] for f in flows):
                    flows.append({
                        "name": flow["name"],
                        "entry_page": url,
                        "steps": [{"action": step} for step in flow.get("steps", [])],
                        "expected_outcome": flow.get("expected_outcome", "")
                    })

        # 表单提交流程
        for url, analysis in self.page_analysis.items():
            forms = analysis.get("features", {}).get("forms", [])
            for form in forms:
                if form.get("purpose") not in ["unknown", "search"]:
                    flow_name = f"{form['purpose'].replace('_', ' ').title()}"
                    if not any(f["name"] == flow_name for f in flows):
                        flows.append({
                            "name": flow_name,
                            "description": f"Submit {form['purpose']} form",
                            "entry_page": url,
                            "steps": [
                                {"action": "访问表单页面", "page": url},
                                {"action": "填写表单字段", "fields": [f.get("name") for f in form.get("fields", [])]},
                                {"action": "提交表单"},
                                {"action": "验证提交结果"}
                            ],
                            "involved_apis": [form.get("action")] if form.get("action") else []
                        })

        self.business_flows = flows
        print(f"  🔄 识别业务流程: {len(flows)} 个")

    def _find_related_apis(self, keywords: List[str]) -> List[str]:
        """根据关键词查找相关 API"""
        related = []
        for api in self.api_records:
            url = api.get("url", "").lower()
            if any(kw in url for kw in keywords):
                related.append(api.get("url"))
        return related

    def _map_pages_to_functions(self):
        """映射页面到功能"""
        for url, analysis in self.page_analysis.items():
            ptype = analysis.get("primary_type", "unknown")
            functions = []

            type_to_function = {
                "login_page": ["用户认证", "登录功能"],
                "register_page": ["用户注册", "账户创建"],
                "search_page": ["内容搜索", "信息检索"],
                "list_page": ["数据展示", "列表浏览"],
                "detail_page": ["详情查看", "信息展示"],
                "form_page": ["数据录入", "表单提交"],
                "dashboard": ["数据概览", "系统监控"],
                "profile_page": ["个人中心", "信息管理"],
                "cart_page": ["购物车管理"],
                "checkout_page": ["订单结算", "支付处理"]
            }

            if ptype in type_to_function:
                functions.extend(type_to_function[ptype])

            # 从交互分析中添加功能
            interactions = analysis.get("features", {}).get("interactions", [])
            for inter in interactions:
                if inter.get("type") == "search_submission":
                    functions.append("搜索功能")
                elif inter.get("type") == "login_submission":
                    functions.append("登录功能")
                elif inter.get("type") == "registration_submission":
                    functions.append("注册功能")

            self.page_to_function[url] = functions

    def _map_apis_to_functions(self):
        """映射 API 到功能"""
        for api in self.api_records:
            url = api.get("url", "")
            functions = []

            # 从 URL 路径推断功能
            path_parts = url.lower().split("/")

            if any(x in path_parts for x in ["auth", "login", "token", "signin"]):
                functions.append("用户认证")
            if any(x in path_parts for x in ["register", "signup"]):
                functions.append("用户注册")
            if any(x in path_parts for x in ["user", "users", "profile"]):
                functions.append("用户管理")
            if any(x in path_parts for x in ["search", "query", "find"]):
                functions.append("搜索服务")
            if any(x in path_parts for x in ["list", "items", "all"]):
                functions.append("数据查询")
            if any(x in path_parts for x in ["create", "add", "new"]):
                functions.append("数据创建")
            if any(x in path_parts for x in ["update", "edit"]):
                functions.append("数据更新")
            if any(x in path_parts for x in ["delete", "remove"]):
                functions.append("数据删除")

            self.api_to_function[url] = functions

    def generate_document(self) -> str:
        """生成业务逻辑文档"""
        self.load_data()
        self._identify_business_entities()
        self._identify_business_flows()
        self._map_pages_to_functions()
        self._map_apis_to_functions()

        doc = []

        # 文档标题
        doc.append(f"# 业务逻辑文档")
        doc.append(f"")
        doc.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc.append(f"**目标网站**: {self.base_url}")
        doc.append(f"**分析页面数**: {len(self.page_tree)}")
        doc.append(f"**发现 API 数**: {len(self.api_records)}")
        doc.append(f"")

        # 执行摘要
        doc.append(f"## 📋 执行摘要")
        doc.append(f"")
        doc.append(f"本系统是一个基于 Web 的应用程序，包含以下核心能力：")
        doc.append(f"")
        if self.business_flows:
            doc.append(f"- **核心业务流**: {len(self.business_flows)} 个")
        if self.business_entities:
            doc.append(f"- **业务实体**: {len(self.business_entities)} 个")
        doc.append(f"- **功能页面**: {len(self.page_tree)} 个")
        doc.append(f"- **API 端点**: {len(self.api_records)} 个")
        doc.append(f"")

        # 业务实体
        if self.business_entities:
            doc.append(f"## 🏗️ 业务实体")
            doc.append(f"")
            for entity in self.business_entities:
                doc.append(f"### {entity['name']}")
                if "attributes" in entity:
                    doc.append(f"**属性**: {', '.join(entity['attributes'])}")
                if "operations" in entity:
                    doc.append(f"**操作**: {', '.join(entity['operations'])}")
                if "source_api" in entity:
                    doc.append(f"**数据来源**: `{entity['source_api']}`")
                doc.append(f"")

        # 业务流程
        if self.business_flows:
            doc.append(f"## 🔄 业务流程")
            doc.append(f"")
            for i, flow in enumerate(self.business_flows, 1):
                doc.append(f"### {i}. {flow['name']}")
                if "description" in flow:
                    doc.append(f"**描述**: {flow['description']}")
                if "entry_page" in flow:
                    doc.append(f"**入口页面**: `{flow['entry_page']}`")
                doc.append(f"")

                doc.append(f"**流程步骤**:")
                for step in flow.get("steps", []):
                    if isinstance(step, dict):
                        action = step.get("action", "")
                        if "page" in step:
                            doc.append(f"1. {action} - [{step['page']}]")
                        elif "input" in step:
                            doc.append(f"1. {action} (`{step['input']}`)")
                        elif "fields" in step:
                            fields = ", ".join(step['fields'])
                            doc.append(f"1. {action} ({fields})")
                        else:
                            doc.append(f"1. {action}")
                    else:
                        doc.append(f"1. {step}")
                doc.append(f"")

                if flow.get("involved_apis"):
                    doc.append(f"**涉及 API**:")
                    for api in flow["involved_apis"]:
                        doc.append(f"- `{api}`")
                    doc.append(f"")

                if flow.get("success_criteria"):
                    doc.append(f"**成功标准**:")
                    for criteria in flow["success_criteria"]:
                        doc.append(f"- {criteria}")
                    doc.append(f"")

                if flow.get("expected_outcome"):
                    doc.append(f"**预期结果**: {flow['expected_outcome']}")
                    doc.append(f"")

        # 页面功能映射
        if self.page_to_function:
            doc.append(f"## 📄 页面功能映射")
            doc.append(f"")
            doc.append(f"| 页面 | 功能 |")
            doc.append(f"|------|------|")
            for url, functions in self.page_to_function.items():
                func_str = ", ".join(functions) if functions else "-"
                doc.append(f"| `{url}` | {func_str} |")
            doc.append(f"")

        # API 功能映射
        if self.api_to_function:
            doc.append(f"## 🔌 API 功能映射")
            doc.append(f"")
            doc.append(f"| API | 功能 |")
            doc.append(f"|-----|------|")
            for url, functions in self.api_to_function.items():
                func_str = ", ".join(functions) if functions else "数据接口"
                doc.append(f"| `{url}` | {func_str} |")
            doc.append(f"")

        # 系统架构概览
        doc.append(f"## 🏛️ 系统架构概览")
        doc.append(f"")
        doc.append(f"```")
        doc.append(f"用户 -> Web 界面 -> 业务逻辑层 -> API 服务 -> 数据层")
        doc.append(f"```")
        doc.append(f"")

        if self.business_flows:
            doc.append(f"### 核心业务流程图")
            doc.append(f"")
            for flow in self.business_flows:
                doc.append(f"**{flow['name']}**:")
                steps = []
                for step in flow.get("steps", []):
                    if isinstance(step, dict):
                        steps.append(step.get("action", ""))
                    else:
                        steps.append(step)
                flow_str = " -> ".join(steps[:5])  # 只显示前5步
                if len(flow.get("steps", [])) > 5:
                    flow_str += " -> ..."
                doc.append(f"```")
                doc.append(f"{flow_str}")
                doc.append(f"```")
                doc.append(f"")

        # 附录：原始数据
        doc.append(f"## 📎 附录：原始数据汇总")
        doc.append(f"")
        doc.append(f"### 页面类型分布")
        if self.page_analysis:
            type_count = {}
            for analysis in self.page_analysis.values():
                ptype = analysis.get("primary_type", "unknown")
                type_count[ptype] = type_count.get(ptype, 0) + 1
            for ptype, count in sorted(type_count.items(), key=lambda x: x[1], reverse=True):
                doc.append(f"- {ptype}: {count} 个")
        doc.append(f"")

        return "\n".join(doc)

    def save_document(self, output_file: str):
        """保存业务逻辑文档"""
        document = self.generate_document()

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(document)

        print(f"📁 业务逻辑文档已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="业务建模器 - 生成业务逻辑文档")
    parser.add_argument("--input-dir", "-i", required=True, help="crawler 输出目录")
    parser.add_argument("--output", "-o", default="./test_data/business_logic.md", help="输出文件路径")
    args = parser.parse_args()

    modeler = BusinessModeler(args.input_dir)
    modeler.save_document(args.output)


if __name__ == "__main__":
    main()
