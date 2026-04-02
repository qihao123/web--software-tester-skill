#!/usr/bin/env python3
"""
page_analyzer.py - 页面功能分析器

分析采集到的页面数据，识别：
- 页面类型（列表页/详情页/表单页/登录页等）
- 交互流程
- 可操作元素
- 数据展示区域

用法:
  python page_analyzer.py --input-dir DATA_DIR --output OUTPUT_PATH
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict


class PageAnalyzer:
    PAGE_TYPES = {
        "login": ["登录", "login", "signin", "sign-in", "账号", "密码", "password"],
        "list": ["列表", "list", "管理", "manage", "表格", "table", "查询", "search"],
        "form": ["新增", "添加", "create", "add", "编辑", "edit", "修改", "表单", "form"],
        "detail": ["详情", "detail", "查看", "view", "信息", "info"],
        "dashboard": ["仪表盘", "dashboard", "首页", "home", "概览", "overview", "统计"],
        "report": ["报表", "report", "统计", "statistics", "图表", "chart"],
        "settings": ["设置", "setting", "配置", "config", "偏好", "preference"]
    }

    ELEMENT_PATTERNS = {
        "submit_button": ["提交", "保存", "确定", "确认", "submit", "save", "confirm", "ok"],
        "cancel_button": ["取消", "关闭", "返回", "cancel", "close", "back", "return"],
        "delete_button": ["删除", "remove", "delete", "del"],
        "edit_button": ["编辑", "修改", "edit", "modify"],
        "add_button": ["新增", "添加", "创建", "add", "create", "new"],
        "search_input": ["搜索", "查询", "search", "关键词", "keyword"],
        "pagination": ["上一页", "下一页", "上一页", "分页", "pagination", "prev", "next"],
        "table_element": ["table", "el-table", "ant-table", "data-table", "grid"],
        "form_element": ["form", "el-form", "ant-form", "input", "select", "textarea"]
    }

    def analyze_pages(self, input_dir: str) -> dict:
        """分析所有页面"""
        data_dir = Path(input_dir)
        pages_dir = data_dir / "pages"

        if not pages_dir.exists():
            print(f"ERROR: 页面目录不存在: {pages_dir}")
            return {"error": "pages directory not found"}

        meta_files = list(pages_dir.glob("*_meta.json"))
        print(f"📊 找到 {len(meta_files)} 个页面元数据文件\n")

        analyzed_pages = []
        all_elements = []
        interaction_flows = []

        for meta_file in meta_files:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            analysis = self._analyze_single_page(meta)
            analyzed_pages.append(analysis)
            all_elements.extend(analysis.get("key_elements", []))

        flows = self._detect_interaction_flows(analyzed_pages)

        result = {
            "analysis_time": meta_files[0].stat().st_mtime if meta_files else None,
            "total_pages": len(analyzed_pages),
            "pages": analyzed_pages,
            "interaction_flows": flows,
            "summary": self._generate_summary(analyzed_pages, flows)
        }

        return result

    def _analyze_single_page(self, meta: dict) -> dict:
        """分析单个页面"""
        name = meta.get("name", "unknown")
        title = meta.get("title", "")
        url = meta.get("url", "")
        elements = meta.get("interactive_elements", [])

        page_type = self._detect_page_type(title, name, url, elements)
        categorized_elements = self._categorize_elements(elements)
        form_fields = self._extract_form_fields(elements)
        navigation_elements = self._find_navigation_elements(elements)

        analysis = {
            "name": name,
            "url": url,
            "title": title,
            "type": page_type,
            "load_time_ms": meta.get("load_time_ms"),
            "elements_count": meta.get("elements_count", 0),
            "key_elements": categorized_elements,
            "form_fields": form_fields,
            "navigation": navigation_elements,
            "has_table": any(e.get("category") == "table_element" for e in categorized_elements),
            "has_form": any(e.get("category") == "form_element" for e in categorized_elements),
            "has_search": any(e.get("category") == "search_input" for e in categorized_elements),
            "potential_actions": self._infer_actions(categorized_elements, page_type)
        }

        return analysis

    def _detect_page_type(self, title: str, name: str, url: str, elements: list) -> str:
        """检测页面类型"""
        combined_text = f"{title} {name} {url}".lower()

        scores = {}
        for page_type, keywords in self.PAGE_TYPES.items():
            score = sum(1 for kw in keywords if kw.lower() in combined_text)
            scores[page_type] = score

        element_text = " ".join([e.get("text", "").lower() for e in elements])
        for page_type, keywords in self.PAGE_TYPES.items():
            extra_score = sum(1 for kw in keywords if kw.lower() in element_text)
            scores[page_type] = scores.get(page_type, 0) + extra_score * 0.5

        best_type = max(scores, key=scores.get) if scores else "unknown"
        return best_type if scores[best_type] > 0 else "unknown"

    def _categorize_elements(self, elements: list) -> list:
        """分类元素"""
        categorized = []

        for elem in elements:
            elem_text = elem.get("text", "").lower()
            elem_class = elem.get("class", "").lower()
            elem_tag = elem.get("tag", "").lower()
            combined = f"{elem_text} {elem_class} {elem_tag}"

            category = "other"
            for cat_name, patterns in self.ELEMENT_PATTERNS.items():
                if any(p.lower() in combined for p in patterns):
                    category = cat_name
                    break

            elem["category"] = category
            categorized.append(elem)

        return categorized

    def _extract_form_fields(self, elements: list) -> list:
        """提取表单字段"""
        form_fields = []

        for elem in elements:
            if elem.get("tag") in ["input", "select", "textarea"]:
                field_info = {
                    "tag": elem.get("tag"),
                    "type": elem.get("type", "text"),
                    "id": elem.get("id", ""),
                    "class": elem.get("class", ""),
                    "placeholder": elem.get("text", ""),
                    "selector": elem.get("selector", ""),
                    "likely_field": self._guess_field_name(elem)
                }
                form_fields.append(field_info)

        return form_fields

    def _guess_field_name(self, elem: dict) -> str:
        """猜测字段名称"""
        text = elem.get("text", "").lower()
        elem_class = elem.get("class", "").lower()
        elem_id = elem.get("id", "").lower()

        field_patterns = {
            "username": ["用户名", "username", "user", "账号", "account"],
            "password": ["密码", "password", "pwd"],
            "email": ["邮箱", "email", "mail"],
            "phone": ["手机", "电话", "phone", "mobile", "tel"],
            "name": ["姓名", "名字", "name"],
            "search": ["搜索", "查询", "search", "关键词", "keyword"],
            "date": ["日期", "date", "时间", "time"],
            "address": ["地址", "address"],
            "remark": ["备注", "说明", "remark", "note", "描述", "description"]
        }

        combined = f"{text} {elem_class} {elem_id}"
        for field_name, patterns in field_patterns.items():
            if any(p in combined for p in patterns):
                return field_name

        return "unknown"

    def _find_navigation_elements(self, elements: list) -> list:
        """查找导航元素"""
        nav_elements = []

        for elem in elements:
            if elem.get("tag") == "a":
                nav_elements.append({
                    "text": elem.get("text", ""),
                    "selector": elem.get("selector", ""),
                    "type": "link"
                })
            elif elem.get("category") in ["submit_button", "cancel_button", "delete_button",
                                           "edit_button", "add_button", "pagination"]:
                nav_elements.append({
                    "text": elem.get("text", ""),
                    "selector": elem.get("selector", ""),
                    "type": elem.get("category", "button")
                })

        return nav_elements

    def _infer_actions(self, elements: list, page_type: str) -> list:
        """推断可执行的操作"""
        actions = []

        action_map = {
            "login": ["填写用户名", "填写密码", "点击登录", "验证跳转"],
            "list": ["加载数据", "点击搜索", "切换页码", "点击行操作", "点击新增", "点击编辑", "点击删除"],
            "form": ["填写表单字段", "点击提交", "验证必填项", "检查格式"],
            "detail": ["查看信息", "点击编辑", "点击删除", "点击返回"],
            "dashboard": ["查看统计数据", "刷新数据", "切换时间范围"],
            "settings": ["修改配置", "保存设置", "重置默认值"]
        }

        base_actions = action_map.get(page_type, ["查看内容"])

        for elem in elements:
            cat = elem.get("category", "")
            if cat in ["submit_button", "add_button", "edit_button", "delete_button"]:
                action_text = elem.get("text", cat)
                if action_text and action_text not in [a for a in actions]:
                    actions.append(f"点击{action_text}")

        return base_actions + actions

    def _detect_interaction_flows(self, pages: list) -> list:
        """检测交互流程"""
        flows = []

        login_pages = [p for p in pages if p["type"] == "login"]
        list_pages = [p for p in pages if p["type"] == "list"]
        form_pages = [p for p in pages if p["type"] == "form"]

        if login_pages:
            login_flow = {
                "name": "用户登录流程",
                "steps": [
                    {"action": "访问登录页", "target": login_pages[0]["name"]},
                    {"action": "输入凭证", "target": "登录表单"},
                    {"action": "点击登录按钮", "target": "提交"},
                    {"action": "验证跳转", "target": "首页或仪表盘"}
                ],
                "entry_point": login_pages[0]["url"]
            }
            flows.append(login_flow)

        if list_pages:
            for lp in list_pages:
                crumb_flow = {
                    "name": f"{lp['name']}浏览流程",
                    "steps": [
                        {"action": "访问列表页", "target": lp["name"]},
                        {"action": "查看数据加载", "target": "表格/列表"},
                    ]
                }

                if lp.get("has_search"):
                    crumb_flow["steps"].append({"action": "执行搜索/筛选", "target": "搜索框"})

                crumb_flow["steps"].extend([
                    {"action": "点击分页", "target": "分页组件"} if lp.get("navigation") else {},
                    {"action": "点击操作按钮", "target": "行内按钮"}
                ])
                crumb_flow["steps"] = [s for s in crumb_flow["steps"] if s]

                if form_pages:
                    crumb_flow["steps"].append({"action": "进入表单页", "target": form_pages[0]["name"]})
                    crumb_flow["steps"].append({"action": "填写并提交", "target": "表单"})
                    crumb_flow["steps"].append({"action": "返回列表验证", "target": lp["name"]})

                crumb_flow["entry_point"] = lp["url"]
                flows.append(crumb_flow)

        return flows

    def _generate_summary(self, pages: list, flows: list) -> dict:
        """生成分析摘要"""
        type_counts = {}
        for p in pages:
            t = p["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        total_actions = sum(len(p.get("potential_actions", [])) for p in pages)
        total_forms = sum(1 for p in pages if p.get("has_form"))

        return {
            "page_types": type_counts,
            "total_interaction_flows": len(flows),
            "total_potential_actions": total_actions,
            "total_forms": total_forms,
            "test_complexity": "high" if total_actions > 50 else ("medium" if total_actions > 20 else "low")
        }


def main():
    parser = argparse.ArgumentParser(description="页面功能分析器")
    parser.add_argument("--input-dir", "-i", required=True, help="输入目录（包含 pages/ 子目录）")
    parser.add_argument("--output", "-o", default=None, help="输出路径（默认 input_dir/page_analysis.json）")
    args = parser.parse_args()

    analyzer = PageAnalyzer()
    result = analyzer.analyze_pages(args.input_dir)

    output_path = args.output or f"{args.input_dir}/page_analysis.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成！结果已保存: {output_path}")
    print(f"\n📊 分析摘要:")
    summary = result.get("summary", {})
    print(f"   页面类型分布: {summary.get('page_types', {})}")
    print(f"   发现交互流程: {summary.get('total_interaction_flows', 0)}")
    print(f"   潜在测试动作: {summary.get('total_potential_actions', 0)}")
    print(f"   测试复杂度: {summary.get('test_complexity', 'unknown')}")


if __name__ == "__main__":
    main()
