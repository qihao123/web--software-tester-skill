#!/usr/bin/env python3
"""
business_modeler.py - 业务逻辑建模器

基于采集的页面数据和 API 记录，生成业务逻辑文档。
识别业务实体、业务规则和业务流程。

用法:
  python business_modeler.py --input-dir DATA_DIR --output OUTPUT_PATH
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class BusinessModeler:
    def __init__(self):
        self.business_entities = []
        self.business_flows = []
        self.business_rules = []
        self.api_business_mapping = {}

    def model(self, input_dir: str) -> dict:
        """执行业务建模"""
        data_dir = Path(input_dir)

        page_analysis_path = data_dir / "page_analysis.json"
        api_records_path = data_dir / "apis" / "api_records.json"
        page_tree_path = data_dir / "page_tree.json"

        page_analysis = None
        api_records = []
        page_tree = None

        if page_analysis_path.exists():
            with open(page_analysis_path, "r", encoding="utf-8") as f:
                page_analysis = json.load(f)

        if api_records_path.exists():
            with open(api_records_path, "r", encoding="utf-8") as f:
                api_records = json.load(f)

        if page_tree_path.exists():
            with open(page_tree_path, "r", encoding="utf-8") as f:
                page_tree = json.load(f)

        if not page_analysis and not api_records:
            print("⚠️ 未找到足够的分析数据，将基于基础结构生成模板")
            return self._generate_template_model(data_dir)

        print("\n🏢 开始业务建模...")

        entities = self._extract_entities(page_analysis, api_records)
        flows = self._build_business_flows(page_analysis, api_records)
        rules = self._infer_business_rules(page_analysis, api_records)
        api_mapping = self._map_apis_to_business(api_records, entities)

        model = {
            "model_time": datetime.now().isoformat(),
            "source_data": {
                "pages_analyzed": len(page_analysis.get("pages", [])) if page_analysis else 0,
                "apis_captured": len(api_records),
                "spa_detected": page_tree.get("is_spa", False) if page_tree else False
            },
            "business_entities": entities,
            "business_flows": flows,
            "business_rules": rules,
            "api_business_mapping": api_mapping,
            "test_recommendations": self._generate_test_recommendations(entities, flows, rules)
        }

        return model

    def _generate_template_model(self, data_dir: dict) -> dict:
        """当没有足够数据时生成模板模型"""
        return {
            "model_time": datetime.now().isoformat(),
            "source_data": {"note": "基于目录结构生成的模板"},
            "business_entities": [],
            "business_flows": [],
            "business_rules": [],
            "api_business_mapping": {},
            "test_recommendations": [],
            "note": "请先运行 crawler.py 和 page_analyzer.py 以获取完整数据"
        }

    def _extract_entities(self, page_analysis: dict, api_records: list) -> list:
        """提取业务实体"""
        entities = []
        entity_names = set()

        if page_analysis:
            for page in page_analysis.get("pages", []):
                page_name = page.get("name", "")
                page_title = page.get("title", "")

                entity_candidates = self._extract_entity_from_name(page_name, page_title)
                for candidate in entity_candidates:
                    if candidate["name"] not in entity_names:
                        entity_names.add(candidate["name"])
                        entities.append(candidate)

                        candidate["related_pages"] = [page.get("name")]
                        candidate["fields"] = page.get("form_fields", [])
                        candidate["operations"] = self._guess_operations(page)

        if api_records:
            for api in api_records:
                api_path = api.get("path", "")
                entity_from_api = self._extract_entity_from_api_path(api_path)

                if entity_from_api and entity_from_api["name"] not in entity_names:
                    entity_names.add(entity_from_api["name"])
                    entities.append(entity_from_api)

        return entities

    def _extract_entity_from_name(self, name: str, title: str) -> list:
        """从页面名称中提取实体"""
        candidates = []
        combined = f"{name} {title}".strip()

        common_entities = [
            ("用户", ["user", "用户", "账户", "account"]),
            ("商品", ["product", "goods", "商品", "产品"]),
            ("订单", ["order", "订单"]),
            ("角色", ["role", "角色"]),
            ("权限", ["permission", "权限"]),
            ("菜单", ["menu", "菜单"]),
            ("日志", ["log", "日志"]),
            ("配置", ["config", "配置", "设置"]),
            ("部门", ["dept", "department", "部门"]),
            ("任务", ["task", "任务"]),
            ("消息", ["message", "消息", "通知"]),
            ("文件", ["file", "文件"]),
            ("字典", ["dict", "dictionary", "字典"]),
        ]

        for entity_name, keywords in common_entities:
            if any(kw in combined.lower() for kw in keywords):
                candidates.append({
                    "name": entity_name,
                    "name_en": keywords[0],
                    "source": "page_name",
                    "confidence": "high" if entity_name in combined else "medium"
                })

        return candidates if candidates else [{
            "name": name or "未命名实体",
            "name_en": "",
            "source": "page_name",
            "confidence": "low"
        }]

    def _extract_entity_from_api_path(self, api_path: str) -> dict:
        """从 API 路径中提取实体"""
        parts = api_path.strip("/").split("/")
        if len(parts) >= 2:
            entity_name = parts[-2] if parts[-1] in ["list", "detail", "create", "update", "delete", "page"] else parts[-1]

            entity_map = {
                "user": "用户", "users": "用户",
                "product": "商品", "products": "商品",
                "order": "订单", "orders": "订单",
                "role": "角色", "roles": "角色",
                "menu": "菜单", "menus": "菜单",
                "log": "日志", "logs": "日志",
                "dept": "部门", "dept": "部门",
                "file": "文件", "files": "文件",
                "dict": "字典", "dict": "字典",
            }

            display_name = entity_map.get(entity_name.lower(), entity_name)
            return {
                "name": display_name,
                "name_en": entity_name,
                "source": "api_path",
                "api_path": api_path,
                "confidence": "high"
            }

        return None

    def _guess_operations(self, page: dict) -> list:
        """根据页面类型推断操作"""
        page_type = page.get("type", "")
        actions = page.get("potential_actions", [])

        operation_map = {
            "login": ["登录", "登出"],
            "list": ["查询列表", "搜索", "分页", "排序", "批量操作"],
            "form": ["创建", "编辑", "提交", "验证"],
            "detail": ["查看详情", "导出", "打印"],
            "dashboard": ["查看统计", "刷新数据"],
            "settings": ["读取配置", "更新配置"]
        }

        return operation_map.get(page_type, ["查看"])

    def _build_business_flows(self, page_analysis: dict, api_records: list) -> list:
        """构建业务流程"""
        flows = []

        standard_flows = [
            {
                "name": "用户认证流程",
                "description": "用户登录系统的完整流程",
                "trigger": "用户访问需要认证的页面",
                "actors": ["用户", "系统"],
                "preconditions": ["用户拥有有效账户"],
                "steps": [
                    {"step": 1, "action": "访问登录页面", "expected": "显示登录表单"},
                    {"step": 2, "action": "输入用户名", "expected": "用户名字段填充"},
                    {"step": 3, "action": "输入密码", "expected": "密码字段填充（加密显示）"},
                    {"step": 4, "action": "点击登录按钮", "expected": "提交认证请求"},
                    {"step": 5, "action": "等待响应", "expected": "成功则跳转到首页/仪表盘"}
                ],
                "postconditions": ["用户获得会话 Token", "跳转到系统主页"],
                "priority": "critical",
                "test_cases_needed": ["正确凭证登录", "错误密码", "空用户名", "账号锁定状态"]
            },
            {
                "name": "数据 CRUD 流程",
                "description": "通用数据的增删改查流程",
                "trigger": "用户需要进行数据管理操作",
                "actors": ["普通用户", "管理员"],
                "preconditions": ["用户已登录", "用户具有相应权限"],
                "steps": [
                    {"step": 1, "action": "访问数据列表页", "expected": "显示数据表格"},
                    {"step": 2, "action": "点击新增按钮", "expected": "打开新建表单"},
                    {"step": 3, "action": "填写表单数据", "expected": "各字段正常输入"},
                    {"step": 4, "action": "点击保存/提交", "expected": "数据保存成功提示"},
                    {"step": 5, "action": "验证列表刷新", "expected": "新数据显示在列表中"},
                    {"step": 6, "action": "点击编辑", "expected": "打开编辑表单（预填数据）"},
                    {"step": 7, "action": "修改并保存", "expected": "修改成功"},
                    {"step": 8, "action": "点击删除", "expected": "弹出确认对话框"},
                    {"step": 9, "action": "确认删除", "expected": "数据从列表移除"}
                ],
                "postconditions": ["数据库记录变更", "操作日志记录"],
                "priority": "high",
                "test_cases_needed": ["正常增删改查", "重复提交", "并发操作", "权限校验"]
            },
            {
                "name": "数据查询与筛选流程",
                "description": "用户搜索和筛选数据的流程",
                "trigger": "用户需要查找特定数据",
                "actors": ["所有用户"],
                "preconditions": ["存在可供查询的数据"],
                "steps": [
                    {"step": 1, "action": "访问列表页面", "expected": "显示全部数据或默认视图"},
                    {"step": 2, "action": "输入搜索条件", "expected": "搜索框接受输入"},
                    {"step": 3, "action": "触发搜索（回车/按钮）", "expected": "结果过滤显示"},
                    {"step": 4, "action": "使用高级筛选", "expected": "多条件组合查询"},
                    {"step": 5, "action": "重置筛选条件", "expected": "恢复默认视图"},
                    {"step": 6, "action": "切换排序方式", "expected": "数据重新排列"},
                    {"step": 7, "action": "翻页浏览", "expected": "分页导航正常工作"}
                ],
                "postconditions": ["显示符合条件的结果集"],
                "priority": "high",
                "test_cases_needed": ["模糊搜索", "精确匹配", "空结果", "特殊字符", "大数据量"]
            },
            {
                "name": "权限控制流程",
                "description": "基于角色的访问控制验证",
                "trigger": "用户尝试访问受保护资源",
                "actors": ["管理员", "普通用户", "访客"],
                "preconditions": ["系统配置了角色和权限"],
                "steps": [
                    {"step": 1, "action": "以不同角色登录", "expected": "各自看到对应菜单"},
                    {"step": 2, "action": "访问无权限页面", "expected": "拒绝访问或隐藏菜单"},
                    {"step": 3, "action": "尝试越权操作", "expected": "后端拒绝请求"},
                    {"step": 4, "action": "切换用户角色", "expected": "权限即时更新"}
                ],
                "postconditions": ["敏感操作被拦截", "审计日志记录"],
                "priority": "critical",
                "test_cases_needed": ["角色隔离", "越权访问", "权限继承", "动态授权"]
            }
        ]

        flows.extend(standard_flows)

        if page_analysis:
            detected_flows = page_analysis.get("interaction_flows", [])
            for flow in detected_flows:
                custom_flow = {
                    "name": flow.get("name", "自定义流程"),
                    "description": f"从页面交互中自动识别的流程",
                    "trigger": "用户操作",
                    "actors": ["用户"],
                    "preconditions": ["用户已登录"],
                    "steps": [
                        {"step": i + 1, "action": step.get("action", ""), "expected": step.get("target", "")}
                        for i, step in enumerate(flow.get("steps", []))
                    ],
                    "postconditions": ["操作完成"],
                    "priority": "medium",
                    "test_cases_needed": []
                }
                flows.append(custom_flow)

        return flows

    def _infer_business_rules(self, page_analysis: dict, api_records: list) -> list:
        """推断业务规则"""
        rules = []

        common_rules = [
            {
                "rule_id": "BR001",
                "name": "认证要求",
                "description": "除公开页面外，所有页面都需要有效认证才能访问",
                "type": "security",
                "enforcement": "前端路由守卫 + 后端 Token 验证",
                "test_method": "未登录状态下直接访问各页面，验证重定向到登录页"
            },
            {
                "rule_id": "BR002",
                "name": "输入验证",
                "description": "所有用户输入必须经过服务端验证（不依赖前端验证）",
                "type": "validation",
                "enforcement": "后端 DTO 校验 + 参数校验",
                "test_method": "发送非法参数的请求，验证返回适当的错误码和信息"
            },
            {
                "rule_id": "BR003",
                "name": "数据权限隔离",
                "description": "用户只能访问其权限范围内的数据",
                "type": "authorization",
                "enforcement": "后端数据权限过滤器",
                "test_method": "用 A 用户登录后尝试访问 B 用户的数据"
            },
            {
                "rule_id": "BR004",
                "name": "操作幂等性",
                "description": "重复提交相同请求不应产生副作用（如重复下单）",
                "type": "consistency",
                "enforcement": "唯一约束 / 幂等键",
                "test_method": "快速连续点击提交按钮，验证只产生一条记录"
            },
            {
                "rule_id": "BR005",
                "name": "会话超时处理",
                "description": "Token 过期后应自动跳转到登录页",
                "type": "session",
                "enforcement": "Token 有效期检查 + 拦截器",
                "test_method": "等待 Token 过期后操作，验证提示重新登录"
            },
            {
                "rule_id": "BR006",
                "name": "数据完整性",
                "description": "关联数据删除时应检查引用关系",
                "type": "referential",
                "enforcement": "外键约束 / 业务层校验",
                "test_method": "尝试删除被其他记录引用的数据"
            }
        ]

        if api_records:
            api_methods = [api.get("method", "") for api in api_records]
            if "POST" in api_methods or "PUT" in api_methods:
                rules.append({
                    "rule_id": "BR007",
                    "name": "写操作审计",
                    "description": "所有数据变更操作必须记录操作日志",
                    "type": "audit",
                    "enforcement": "AOP 切面 / 拦截器",
                    "test_method": "执行增删改操作后检查日志表"
                })

        rules.extend(common_rules)
        return rules

    def _map_apis_to_business(self, api_records: list, entities: list) -> dict:
        """将 API 映射到业务实体"""
        mapping = {}

        for api in api_records:
            api_path = api.get("path", "")
            method = api.get("method", "")

            matched_entity = None
            for entity in entities:
                entity_en = entity.get("name_en", "").lower()
                if entity_en and entity_en in api_path.lower():
                    matched_entity = entity["name"]
                    break

            if not matched_entity:
                parts = api_path.strip("/").split("/")
                if len(parts) >= 2:
                    matched_entity = parts[-2].capitalize()

            operation = self._infer_api_operation(method, api_path)

            if matched_entity not in mapping:
                mapping[matched_entity] = {"entity": matched_entity, "apis": []}

            mapping[matched_entity]["apis"].append({
                "method": method,
                "path": api_path,
                "operation": operation,
                "description": f"{operation}{matched_entity}"
            })

        return mapping

    def _infer_api_operation(self, method: str, path: str) -> str:
        """推断 API 操作类型"""
        last_part = path.split("/")[-1].lower()

        op_map = {
            "GET": {
                "list": "查询列表", "page": "分页查询", "detail": "查询详情",
                "info": "查询信息", "get": "获取", "": "查询"
            },
            "POST": {
                "create": "创建", "add": "新增", "save": "保存", "": "创建"
            },
            "PUT": {
                "update": "更新", "edit": "编辑", "modify": "修改", "": "更新"
            },
            "DELETE": {
                "delete": "删除", "remove": "移除", "": "删除"
            }
        }

        method_ops = op_map.get(method, {})
        return method_ops.get(last_part, method_ops.get("", "操作"))

    def _generate_test_recommendations(self, entities: list, flows: list, rules: list) -> list:
        """生成测试建议"""
        recommendations = []

        recommendations.append({
            "category": "接口测试",
            "priority": "P0",
            "items": [
                "对所有 API 进行正异常测试",
                "测试参数边界值和特殊字符",
                "验证接口鉴权和权限控制",
                "测试接口性能和并发"
            ]
        })

        recommendations.append({
            "category": "功能测试",
            "priority": "P0",
            "items": [
                "覆盖所有业务流程的主流程和分支流程",
                "测试表单验证（必填、格式、长度限制）",
                "验证搜索、筛选、排序、分页功能",
                "测试数据的增删改查完整闭环"
            ]
        })

        recommendations.append({
            "category": "安全测试",
            "priority": "P1",
            "items": [
                "SQL 注入测试",
                "XSS 攻击测试",
                "CSRF 防护验证",
                "越权访问测试"
            ]
        })

        if len(entities) > 5:
            recommendations.append({
                "category": "性能测试",
                "priority": "P1",
                "items": [
                    "页面加载时间测试",
                    "大数据量下的列表渲染性能",
                    "并发用户操作测试",
                    "接口响应时间基准测试"
                ]
            })

        return recommendations

    def generate_markdown_report(self, model: dict) -> str:
        """生成 Markdown 格式的业务逻辑文档"""
        lines = []
        lines.append("# 业务逻辑文档")
        lines.append("")
        lines.append(f"> 生成时间: {model.get('model_time', '')}")
        lines.append("")

        lines.append("## 1. 业务实体")
        lines.append("")
        entities = model.get("business_entities", [])
        if entities:
            lines.append("| 实体名称 | 英文名 | 来源 | 置信度 |")
            lines.append("|---------|--------|------|--------|")
            for ent in entities:
                lines.append(f"| {ent.get('name', '-')} | {ent.get('name_en', '-')} | "
                           f"{ent.get('source', '-')} | {ent.get('confidence', '-')} |")
        else:
            lines.append("*暂无实体数据*")
        lines.append("")

        lines.append("## 2. 业务流程")
        lines.append("")
        flows = model.get("business_flows", [])
        for i, flow in enumerate(flows, 1):
            lines.append(f"### 2.{i} {flow.get('name', '未命名流程')}")
            lines.append("")
            lines.append(f"**描述**: {flow.get('description', '')}")
            lines.append(f"**优先级**: {flow.get('priority', '-')}")
            lines.append("")
            lines.append("**步骤**:")
            lines.append("")
            lines.append("| 步骤 | 操作 | 预期结果 |")
            lines.append("|------|------|----------|")
            for step in flow.get("steps", []):
                lines.append(f"| {step.get('step')} | {step.get('action', '')} | {step.get('expected', '')} |")
            lines.append("")

            test_cases = flow.get("test_cases_needed", [])
            if test_cases:
                lines.append("**建议测试场景**:")
                lines.append("")
                for tc in test_cases:
                    lines.append(f"- {tc}")
                lines.append("")

        lines.append("## 3. 业务规则")
        lines.append("")
        rules = model.get("business_rules", [])
        for rule in rules:
            lines.append(f"### **{rule.get('rule_id')}**: {rule.get('name', '')}")
            lines.append("")
            lines.append(f"- **描述**: {rule.get('description', '')}")
            lines.append(f"- **类型**: {rule.get('type', '')}")
            lines.append(f"- **测试方法**: {rule.get('test_method', '')}")
            lines.append("")

        lines.append("## 4. API 与业务映射")
        lines.append("")
        api_mapping = model.get("api_business_mapping", {})
        if api_mapping:
            for entity_name, info in api_mapping.items():
                lines.append(f"### {entity_name}")
                lines.append("")
                for api in info.get("apis", []):
                    lines.append(f"- `{api.get('method')}` `{api.get('path')}` - {api.get('description', '')}")
                lines.append("")
        else:
            lines.append("*暂无 API 映射数据*")
            lines.append("")

        lines.append("## 5. 测试建议")
        lines.append("")
        recommendations = model.get("test_recommendations", [])
        for rec in recommendations:
            lines.append(f"### {rec.get('category', '')} ({rec.get('priority', '')})")
            lines.append("")
            for item in rec.get("items", []):
                lines.append(f"- [ ] {item}")
            lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="业务逻辑建模器")
    parser.add_argument("--input-dir", "-i", required=True, help="输入目录")
    parser.add_argument("--output", "-o", default=None, help="输出 Markdown 路径")
    parser.add_argument("--json-output", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    modeler = BusinessModeler()
    model = modeler.model(args.input_dir)

    md_output = args.output or f"{args.input_dir}/business_logic.md"
    json_output = args.json_output or f"{args.input_dir}/business_model.json"

    md_content = modeler.generate_markdown_report(model)
    Path(md_output).write_text(md_content, encoding="utf-8")

    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 业务建模完成!")
    print(f"   Markdown 报告: {md_output}")
    print(f"   JSON 数据: {json_output}")
    print(f"\n   业务实体: {len(model.get('business_entities', []))}")
    print(f"   业务流程: {len(model.get('business_flows', []))}")
    print(f"   业务规则: {len(model.get('business_rules', []))}")


if __name__ == "__main__":
    main()
