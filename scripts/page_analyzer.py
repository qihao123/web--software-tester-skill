#!/usr/bin/env python3
"""
page_analyzer.py - 页面功能分析器

分析 crawler 采集的页面数据，识别页面类型、功能和交互流程。

用法:
  python page_analyzer.py --input-dir DIR [--output FILE]

输入:
  input_dir/page_tree.json
  input_dir/pages/*.html
  input_dir/pages/*_meta.json

输出:
  page_analysis.json - 页面功能分析结果
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: 缺少 beautifulsoup4")
    print("安装方法: pip install beautifulsoup4")
    sys.exit(1)


class PageAnalyzer:
    """页面功能分析器"""

    # 页面类型特征关键词
    PAGE_TYPE_PATTERNS = {
        "login_page": {
            "keywords": ["login", "sign in", "登录", "登入", "log in", "signin"],
            "elements": ["input[type=password]", "input[name=password]", "#password"],
            "required": ["password"]
        },
        "register_page": {
            "keywords": ["register", "sign up", "注册", "signup", "create account"],
            "elements": ["input[name=password_confirmation]", "input[name=confirm_password]"],
        },
        "search_page": {
            "keywords": ["search", "搜索", "查询", "find", "look for"],
            "elements": ["input[type=search]", "input[name=q]", "input[name=query]", "input[name=keyword]"],
        },
        "list_page": {
            "keywords": ["list", "items", "records", "results", "列表", "结果"],
            "elements": ["table", ".list", ".items", "ul li", ".grid"],
            "indicators": ["pagination", "page", "next", "previous"]
        },
        "detail_page": {
            "keywords": ["detail", "info", "详情", "详细信息"],
            "patterns": [r"/\d+$", r"/item/", r"/product/", r"/detail/"]
        },
        "form_page": {
            "keywords": ["form", "submit", "填写", "提交"],
            "required": ["form"]
        },
        "dashboard": {
            "keywords": ["dashboard", "控制台", "仪表盘", "概览", "overview", "home", "首页"],
            "url_patterns": [r"^/$", r"/dashboard", r"/home", r"/index"]
        },
        "profile_page": {
            "keywords": ["profile", "account", "settings", "个人资料", "账户", "设置"],
            "url_patterns": [r"/profile", r"/account", r"/settings", r"/user/"]
        },
        "cart_page": {
            "keywords": ["cart", "basket", "购物车", "购物袋"],
            "url_patterns": [r"/cart", r"/basket"]
        },
        "checkout_page": {
            "keywords": ["checkout", "结算", "结账", "支付", "payment"],
            "url_patterns": [r"/checkout", r"/payment"]
        }
    }

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.pages_dir = self.input_dir / "pages"
        self.page_tree_file = self.input_dir / "page_tree.json"

        self.page_tree: Dict = {}
        self.analysis_results: Dict[str, dict] = {}

    def load_page_tree(self):
        """加载页面树"""
        if not self.page_tree_file.exists():
            print(f"ERROR: 页面树文件不存在: {self.page_tree_file}")
            sys.exit(1)

        with open(self.page_tree_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.page_tree = data.get("pages", {})

        print(f"📁 加载页面树: {len(self.page_tree)} 个页面")

    def _load_page_data(self, url: str) -> Optional[dict]:
        """加载单个页面的数据"""
        if url not in self.page_tree:
            return None

        page_info = self.page_tree[url]
        page_id = page_info["page_id"]

        html_file = self.pages_dir / f"{page_id}.html"
        meta_file = self.pages_dir / f"{page_id}_meta.json"

        if not html_file.exists():
            return None

        result = {
            "url": url,
            "page_id": page_id,
            "page_tree_info": page_info,
            "html": html_file.read_text(encoding="utf-8"),
        }

        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                result["meta"] = json.load(f)

        return result

    def _detect_page_type(self, page_data: dict) -> List[str]:
        """检测页面类型"""
        detected_types = []
        soup = BeautifulSoup(page_data["html"], "html.parser")

        # 提取页面文本
        page_text = soup.get_text(separator=" ", strip=True).lower()
        page_title = (page_data.get("meta", {}).get("title") or "").lower()
        url = page_data["url"].lower()

        for page_type, patterns in self.PAGE_TYPE_PATTERNS.items():
            score = 0

            # 关键词匹配
            keywords = patterns.get("keywords", [])
            for kw in keywords:
                if kw in page_text or kw in page_title:
                    score += 2

            # URL 模式匹配
            url_patterns = patterns.get("url_patterns", [])
            for pattern in url_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    score += 3

            # 元素检查
            required_elements = patterns.get("required", [])
            for elem in required_elements:
                if soup.select(elem):
                    score += 3

            # 可选元素检查
            elements = patterns.get("elements", [])
            for elem in elements:
                if soup.select(elem):
                    score += 1

            # 特殊指标检查
            indicators = patterns.get("indicators", [])
            for ind in indicators:
                if ind in page_text:
                    score += 1

            # 如果得分足够高，认为是该类型
            if score >= 3:
                detected_types.append({"type": page_type, "confidence": min(score / 10, 1.0)})

        # 按置信度排序
        detected_types.sort(key=lambda x: x["confidence"], reverse=True)
        return detected_types

    def _analyze_forms(self, page_data: dict) -> List[dict]:
        """分析表单功能"""
        forms = []
        soup = BeautifulSoup(page_data["html"], "html.parser")

        for form in soup.find_all("form"):
            form_analysis = {
                "action": form.get("action", ""),
                "method": form.get("method", "get").upper(),
                "purpose": "unknown",
                "fields": [],
                "submit_buttons": []
            }

            # 分析输入字段
            for inp in form.find_all(["input", "textarea", "select"]):
                field = {
                    "tag": inp.name,
                    "type": inp.get("type", "text"),
                    "name": inp.get("name", ""),
                    "id": inp.get("id", ""),
                    "placeholder": inp.get("placeholder", ""),
                    "required": inp.get("required") is not None,
                }
                form_analysis["fields"].append(field)

            # 分析提交按钮
            for btn in form.find_all(["button", "input"], {"type": ["submit", "button"]}):
                btn_text = btn.get_text(strip=True) or btn.get("value", "")
                form_analysis["submit_buttons"].append({
                    "text": btn_text,
                    "type": btn.get("type", "button")
                })

            # 推断表单用途
            fields_text = " ".join([f.get("name", "") + " " + f.get("placeholder", "") for f in form_analysis["fields"]]).lower()

            if "password" in fields_text and ("login" in page_data["url"].lower() or "signin" in page_data["url"].lower()):
                form_analysis["purpose"] = "login"
            elif "password" in fields_text and ("register" in page_data["url"].lower() or "signup" in page_data["url"].lower()):
                form_analysis["purpose"] = "registration"
            elif any(kw in fields_text for kw in ["search", "query", "q", "keyword"]):
                form_analysis["purpose"] = "search"
            elif "email" in fields_text and "password" not in fields_text:
                form_analysis["purpose"] = "subscription"
            elif any(kw in fields_text for kw in ["comment", "message", "feedback"]):
                form_analysis["purpose"] = "contact"
            elif form_analysis["fields"]:
                form_analysis["purpose"] = "data_input"

            forms.append(form_analysis)

        return forms

    def _analyze_interactions(self, page_data: dict, forms: List[dict]) -> List[dict]:
        """分析用户交互流程"""
        interactions = []
        soup = BeautifulSoup(page_data["html"], "html.parser")

        # 1. 表单提交流程
        for form in forms:
            if form["purpose"] != "unknown":
                flow = {
                    "type": f"{form['purpose']}_submission",
                    "description": f"{form['purpose'].replace('_', ' ').title()} form submission",
                    "steps": [],
                    "involves_api": bool(form["action"]),
                    "api_endpoint": form["action"]
                }

                for field in form["fields"]:
                    if field["type"] not in ["hidden", "submit"]:
                        step = f"Fill {field['name'] or field['type']} field"
                        if field["required"]:
                            step += " (required)"
                        flow["steps"].append(step)

                if form["submit_buttons"]:
                    flow["steps"].append(f"Click submit button: {form['submit_buttons'][0]['text']}")

                interactions.append(flow)

        # 2. 导航交互
        nav_links = soup.find_all("a", href=True)
        if len(nav_links) > 0:
            # 检测主导航菜单
            nav_selectors = ["nav", ".nav", ".navbar", ".menu", ".sidebar", "header"]
            for selector in nav_selectors:
                nav_elem = soup.select_one(selector)
                if nav_elem:
                    links = nav_elem.find_all("a", href=True)
                    if len(links) >= 2:
                        interactions.append({
                            "type": "navigation",
                            "description": f"Navigation via {selector}",
                            "steps": [f"Click {a.get_text(strip=True) or a['href']}" for a in links[:5]],
                            "total_links": len(links)
                        })
                        break

        # 3. 按钮交互
        buttons = soup.find_all("button")
        for btn in buttons:
            btn_text = btn.get_text(strip=True)
            if btn_text and len(btn_text) < 50:
                onclick = btn.get("onclick", "")
                if onclick or btn.get("type") == "button":
                    interactions.append({
                        "type": "button_click",
                        "description": f"Click '{btn_text}' button",
                        "element": btn.get("id") or btn.get("class") or btn.name,
                        "triggers_action": bool(onclick)
                    })

        return interactions

    def _extract_data_entities(self, page_data: dict) -> List[dict]:
        """提取页面上显示的数据实体"""
        entities = []
        soup = BeautifulSoup(page_data["html"], "html.parser")

        # 1. 表格数据
        tables = soup.find_all("table")
        for i, table in enumerate(tables):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if headers:
                entities.append({
                    "type": "table",
                    "name": f"Table_{i}",
                    "columns": headers,
                    "row_count": len(table.find_all("tr")) - 1  # 减去表头行
                })

        # 2. 列表数据
        lists = soup.find_all(["ul", "ol"])
        for i, lst in enumerate(lists):
            items = lst.find_all("li", recursive=False)
            if len(items) > 2:
                sample_items = [item.get_text(strip=True)[:50] for item in items[:3]]
                entities.append({
                    "type": "list",
                    "name": f"List_{i}",
                    "item_count": len(items),
                    "sample_items": sample_items
                })

        # 3. 卡片/卡片组
        cards = soup.find_all(class_=re.compile(r"card|item|product", re.I))
        if cards:
            entities.append({
                "type": "cards",
                "count": len(cards),
                "sample_structure": self._extract_card_structure(cards[0]) if cards else None
            })

        return entities

    def _extract_card_structure(self, card) -> dict:
        """提取卡片结构"""
        structure = {}

        # 查找图片
        img = card.find("img")
        if img:
            structure["has_image"] = True
            structure["image_alt"] = img.get("alt", "")

        # 查找标题
        title = card.find(["h1", "h2", "h3", "h4", ".title", ".name"])
        if title:
            structure["title"] = title.get_text(strip=True)[:50]

        # 查找描述
        desc = card.find(["p", ".description", ".desc", ".summary"])
        if desc:
            structure["description_preview"] = desc.get_text(strip=True)[:100]

        # 查找按钮/链接
        action = card.find(["a", "button"])
        if action:
            structure["action_text"] = action.get_text(strip=True)

        return structure

    def _identify_user_flows(self, page_data: dict, page_type: List[dict], forms: List[dict]) -> List[dict]:
        """识别用户在当前页面可能的操作流程"""
        flows = []

        # 基于页面类型的典型流程
        if page_type and page_type[0]["type"] == "login_page":
            flows.append({
                "name": "用户登录",
                "steps": ["输入用户名", "输入密码", "点击登录", "等待跳转"],
                "expected_outcome": "登录成功并跳转到首页或仪表盘"
            })

        elif page_type and page_type[0]["type"] == "register_page":
            flows.append({
                "name": "用户注册",
                "steps": ["输入用户名", "输入邮箱", "输入密码", "确认密码", "点击注册"],
                "expected_outcome": "注册成功或提示验证邮箱"
            })

        elif page_type and page_type[0]["type"] == "search_page":
            flows.append({
                "name": "搜索内容",
                "steps": ["输入搜索关键词", "点击搜索按钮/按回车", "查看搜索结果"],
                "expected_outcome": "显示匹配的搜索结果列表"
            })

        # 通用流程：从表单推断
        for form in forms:
            if form["purpose"] == "search" and not any(f["name"] == "搜索内容" for f in flows):
                flows.append({
                    "name": "搜索内容",
                    "steps": [f"填写 {field['name']}" for field in form["fields"] if field["type"] != "submit"] + ["提交搜索"],
                    "expected_outcome": "显示搜索结果"
                })

        return flows

    def analyze_page(self, url: str) -> Optional[dict]:
        """分析单个页面"""
        page_data = self._load_page_data(url)
        if not page_data:
            return None

        print(f"  📄 分析: {url}")

        # 1. 检测页面类型
        page_types = self._detect_page_type(page_data)

        # 2. 分析表单
        forms = self._analyze_forms(page_data)

        # 3. 分析交互
        interactions = self._analyze_interactions(page_data, forms)

        # 4. 提取数据实体
        entities = self._extract_data_entities(page_data)

        # 5. 识别用户流程
        user_flows = self._identify_user_flows(page_data, page_types, forms)

        # 构建分析结果
        result = {
            "url": url,
            "page_id": page_data["page_id"],
            "title": page_data.get("meta", {}).get("title"),
            "page_types": page_types,
            "primary_type": page_types[0]["type"] if page_types else "unknown",
            "features": {
                "forms": forms,
                "interactions": interactions,
                "data_entities": entities,
                "user_flows": user_flows
            },
            "statistics": {
                "form_count": len(forms),
                "interaction_count": len(interactions),
                "entity_count": len(entities),
                "flow_count": len(user_flows)
            }
        }

        return result

    def analyze_all(self) -> dict:
        """分析所有页面"""
        self.load_page_tree()

        print(f"🔍 开始分析 {len(self.page_tree)} 个页面...")

        for url in self.page_tree:
            result = self.analyze_page(url)
            if result:
                self.analysis_results[url] = result

        print(f"✅ 分析完成: {len(self.analysis_results)} 个页面")

        return self.analysis_results

    def save_results(self, output_file: str):
        """保存分析结果"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 构建完整输出
        output_data = {
            "summary": {
                "total_pages": len(self.analysis_results),
                "page_types": self._summarize_page_types(),
                "total_forms": sum(r["statistics"]["form_count"] for r in self.analysis_results.values()),
                "total_interactions": sum(r["statistics"]["interaction_count"] for r in self.analysis_results.values()),
                "total_flows": sum(r["statistics"]["flow_count"] for r in self.analysis_results.values())
            },
            "pages": self.analysis_results
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"📁 分析结果已保存: {output_path}")

    def _summarize_page_types(self) -> dict:
        """统计页面类型分布"""
        type_count = {}
        for result in self.analysis_results.values():
            ptype = result.get("primary_type", "unknown")
            type_count[ptype] = type_count.get(ptype, 0) + 1
        return type_count


def main():
    parser = argparse.ArgumentParser(description="页面功能分析器")
    parser.add_argument("--input-dir", "-i", required=True, help="crawler 输出目录")
    parser.add_argument("--output", "-o", default="./test_data/page_analysis.json", help="输出文件路径")
    args = parser.parse_args()

    analyzer = PageAnalyzer(args.input_dir)
    analyzer.analyze_all()
    analyzer.save_results(args.output)


if __name__ == "__main__":
    main()
