#!/usr/bin/env python3
"""
crawler.py - 网站爬虫，构建页面树，保存 HTML，记录 API 调用

用法:
  python crawler.py <start_url> [--output-dir DIR] [--max-depth N] [--use-playwright]

输出结构:
  output_dir/
  ├── page_tree.json          # 页面树结构
  ├── pages/
  │   ├── index.html          # 页面 HTML
  │   ├── index_meta.json     # 页面元数据
  │   └── ...
  └── apis/
      └── api_records.json    # API 调用记录
"""

import sys
import json
import hashlib
import argparse
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
from typing import Dict, List, Set, Optional, Tuple

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"ERROR: 缺少依赖: {e}")
    print("安装方法: pip install requests beautifulsoup4")
    sys.exit(1)


class ApiSniffer:
    """API 嗅探器 - 从 HTML 中提取潜在 API 端点并探测"""

    # 常见 API 路径模式（主动探测）
    COMMON_API_PATTERNS = [
        "/api", "/api/v1", "/api/v2", "/v1", "/v2",
        "/graphql", "/rest", "/swagger", "/openapi",
        "/api/docs", "/api/swagger", "/api/schema"
    ]

    def __init__(self, session: requests.Session, base_url: str, apis_dir: Path):
        self.session = session
        self.base_url = base_url
        self.apis_dir = apis_dir
        self.base_domain = urlparse(base_url).netloc
        self.api_records: List[dict] = []
        self._tested_urls: Set[str] = set()

    def sniff_from_html(self, html: str, source_url: str) -> List[dict]:
        """从 HTML 中嗅探 API"""
        found_apis = []

        # 1. 从 JS 代码中提取 fetch/XHR 调用
        fetch_pattern = r'fetch\(["\']([^"\']+)["\'][^)]*\)'
        xhr_pattern = r'\.open\(["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']'

        for match in re.finditer(fetch_pattern, html):
            url = match.group(1)
            full_url = urljoin(source_url, url)
            if self._is_same_domain(full_url):
                found_apis.append({"url": full_url, "method": "GET", "source": "js_fetch"})

        for match in re.finditer(xhr_pattern, html):
            method = match.group(1).upper()
            url = match.group(2)
            full_url = urljoin(source_url, url)
            if self._is_same_domain(full_url):
                found_apis.append({"url": full_url, "method": method, "source": "js_xhr"})

        # 2. 从 form action 中提取
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            action = form.get("action", "")
            method = form.get("method", "get").upper()
            if action:
                full_url = urljoin(source_url, action)
                if self._is_same_domain(full_url):
                    found_apis.append({"url": full_url, "method": method, "source": "form_action"})

        # 3. 从 data-* 属性中提取 API 端点
        for elem in soup.find_all(attrs={"data-api": True}):
            api_url = elem.get("data-api")
            if api_url:
                full_url = urljoin(source_url, api_url)
                if self._is_same_domain(full_url):
                    found_apis.append({"url": full_url, "method": "GET", "source": "data_api"})

        # 测试发现的 API
        for api_info in found_apis:
            self._test_api(api_info["url"], api_info["method"], api_info["source"])

        return self.api_records

    def probe_common_apis(self) -> List[dict]:
        """主动探测常见 API 端点"""
        for pattern in self.COMMON_API_PATTERNS:
            url = urljoin(self.base_url, pattern)
            self._test_api(url, "GET", "common_pattern")
        return self.api_records

    def _is_same_domain(self, url: str) -> bool:
        """检查 URL 是否属于同一域名"""
        try:
            return urlparse(url).netloc == self.base_domain
        except:
            return False

    def _test_api(self, url: str, method: str = "GET", detected_from: str = ""):
        """测试 API 端点并记录响应"""
        cache_key = f"{method}:{url}"
        if cache_key in self._tested_urls:
            return
        self._tested_urls.add(cache_key)

        try:
            resp = self.session.request(
                method, url, timeout=10,
                headers={"Accept": "application/json, */*"}
            )

            # 只记录成功的 JSON API
            content_type = resp.headers.get("Content-Type", "")
            is_json = "json" in content_type.lower()
            is_api_like = any(x in url.lower() for x in ["/api/", "/v1/", "/v2/", "/rest/"])

            if resp.status_code < 400 and (is_json or is_api_like):
                record = {
                    "url": url,
                    "method": method,
                    "detected_from": detected_from,
                    "status_code": resp.status_code,
                    "content_type": content_type,
                    "sample_request": {"method": method, "url": url},
                    "sample_response": self._safe_parse_response(resp),
                    "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.api_records.append(record)
                print(f"    🔌 发现 API: {method} {url}")

        except Exception as e:
            pass  # 静默忽略失败的探测

    def _safe_parse_response(self, resp: requests.Response) -> dict:
        """安全解析响应内容"""
        try:
            if "json" in resp.headers.get("Content-Type", "").lower():
                data = resp.json()
                # 截断大型响应
                return self._truncate_large_data(data)
            else:
                text = resp.text[:2000]  # 限制文本长度
                return {"text_preview": text}
        except Exception as e:
            return {"raw_preview": resp.text[:1000]}

    def _truncate_large_data(self, data, max_items: int = 10, max_depth: int = 3) -> dict:
        """截断大型数据结构"""
        if isinstance(data, list):
            if len(data) > max_items:
                return [self._truncate_large_data(item) for item in data[:max_items]] + [f"... ({len(data) - max_items} more items)"]
            return [self._truncate_large_data(item) for item in data]
        elif isinstance(data, dict):
            if max_depth <= 0:
                return {"...": "truncated"}
            return {k: self._truncate_large_data(v, max_depth=max_depth-1) for k, v in list(data.items())[:max_items]}
        elif isinstance(data, str) and len(data) > 500:
            return data[:500] + "..."
        return data

    def save_records(self):
        """保存 API 记录到文件"""
        self.apis_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.apis_dir / "api_records.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"api_records": self.api_records}, f, ensure_ascii=False, indent=2)
        print(f"  📁 API 记录已保存: {output_file} ({len(self.api_records)} 个)")


class WebCrawler:
    """网站爬虫 - 构建页面树并保存数据"""

    def __init__(self, start_url: str, output_dir: str, max_depth: int = 3,
                 delay: float = 0.5, use_playwright: bool = False):
        self.start_url = start_url
        self.output_dir = Path(output_dir)
        self.max_depth = max_depth
        self.delay = delay
        self.use_playwright = use_playwright

        self.base_domain = urlparse(start_url).netloc
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        # 页面树结构
        self.page_tree: Dict[str, dict] = {}
        self.visited_urls: Set[str] = set()
        self.url_queue: deque = deque()

        # 目录结构
        self.pages_dir = self.output_dir / "pages"
        self.apis_dir = self.output_dir / "apis"

        # API 嗅探器
        self.api_sniffer = ApiSniffer(self.session, start_url, self.apis_dir)

    def _normalize_url(self, url: str) -> str:
        """标准化 URL（去除 fragment，统一格式）"""
        url, _ = urldefrag(url)
        return url.rstrip("/")

    def _is_same_domain(self, url: str) -> bool:
        """检查是否同一域名"""
        try:
            return urlparse(url).netloc == self.base_domain
        except:
            return False

    def _is_valid_link(self, url: str) -> bool:
        """检查链接是否有效且应被爬取"""
        parsed = urlparse(url)

        # 只爬取 HTTP/HTTPS
        if parsed.scheme not in ("http", "https"):
            return False

        # 同域名检查
        if not self._is_same_domain(url):
            return False

        # 跳过常见非页面资源
        skip_extensions = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".css", ".js",
                         ".zip", ".tar", ".gz", ".mp4", ".mp3", ".avi", ".mov",
                         ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
        if parsed.path.lower().endswith(skip_extensions):
            return False

        # 跳过锚点链接和特殊协议
        if url.startswith(("#", "javascript:", "mailto:", "tel:")):
            return False

        return True

    def _get_page_id(self, url: str) -> str:
        """生成页面唯一 ID"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", "_") or "index"
        return f"{path}_{url_hash}"

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """从 HTML 中提取链接"""
        soup = BeautifulSoup(html, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            if self._is_valid_link(full_url):
                links.append(self._normalize_url(full_url))

        return list(set(links))

    def _extract_meta(self, html: str, url: str) -> dict:
        """提取页面元数据"""
        soup = BeautifulSoup(html, "html.parser")

        meta = {
            "url": url,
            "title": soup.title.string.strip() if soup.title else None,
            "forms": [],
            "buttons": [],
            "inputs": [],
            "links_count": 0,
            "has_login_form": False
        }

        # 提取表单
        for form in soup.find_all("form"):
            form_info = {
                "action": urljoin(url, form.get("action", "")),
                "method": form.get("method", "get").upper(),
                "id": form.get("id", ""),
                "class": " ".join(form.get("class", [])) if isinstance(form.get("class"), list) else str(form.get("class", "")),
                "inputs": []
            }
            for inp in form.find_all(["input", "textarea", "select"]):
                inp_info = {
                    "tag": inp.name,
                    "type": inp.get("type", "text"),
                    "name": inp.get("name", ""),
                    "id": inp.get("id", ""),
                    "placeholder": inp.get("placeholder", ""),
                    "required": inp.get("required") is not None,
                }
                form_info["inputs"].append(inp_info)

                # 检测登录表单特征
                if inp.get("type") == "password":
                    meta["has_login_form"] = True

            meta["forms"].append(form_info)

        # 提取独立输入框
        for inp in soup.find_all(["input", "textarea", "select"]):
            if not inp.find_parent("form"):
                meta["inputs"].append({
                    "tag": inp.name,
                    "type": inp.get("type", "text"),
                    "name": inp.get("name", ""),
                    "id": inp.get("id", ""),
                    "placeholder": inp.get("placeholder", ""),
                })

        # 提取按钮
        for btn in soup.find_all(["button", "input"], {"type": ["button", "submit", "reset"]}):
            meta["buttons"].append({
                "tag": btn.name,
                "type": btn.get("type", "button"),
                "text": btn.get_text(strip=True) or btn.get("value", ""),
                "id": btn.get("id", ""),
                "name": btn.get("name", ""),
            })

        # 统计链接数
        meta["links_count"] = len(soup.find_all("a", href=True))

        return meta

    def _save_page(self, url: str, html: str, meta: dict):
        """保存页面数据"""
        self.pages_dir.mkdir(parents=True, exist_ok=True)

        page_id = self._get_page_id(url)

        # 保存 HTML
        html_file = self.pages_dir / f"{page_id}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)

        # 保存元数据
        meta_file = self.pages_dir / f"{page_id}_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return page_id

    def _fetch_page(self, url: str) -> Tuple[str, int]:
        """获取页面内容"""
        try:
            resp = self.session.get(url, timeout=30)
            return resp.text, resp.status_code
        except Exception as e:
            return "", 0

    def crawl(self) -> dict:
        """执行爬取"""
        print(f"🚀 开始爬取: {self.start_url}")
        print(f"   输出目录: {self.output_dir}")
        print(f"   最大深度: {self.max_depth}")

        # 初始化队列
        start_url = self._normalize_url(self.start_url)
        self.url_queue.append((start_url, 0, None))  # (url, depth, parent_url)

        while self.url_queue:
            url, depth, parent_url = self.url_queue.popleft()

            if url in self.visited_urls or depth > self.max_depth:
                continue

            self.visited_urls.add(url)
            print(f"  📄 [{depth}] {url}")

            # 获取页面
            html, status_code = self._fetch_page(url)
            if not html:
                continue

            # 提取元数据
            meta = self._extract_meta(html, url)
            meta["status_code"] = status_code
            meta["depth"] = depth
            meta["parent_url"] = parent_url

            # 保存页面
            page_id = self._save_page(url, html, meta)

            # 记录到页面树
            self.page_tree[url] = {
                "page_id": page_id,
                "depth": depth,
                "title": meta["title"],
                "links_to": [],
                "parent": parent_url
            }

            # 更新父页面的链接关系
            if parent_url and parent_url in self.page_tree:
                self.page_tree[parent_url]["links_to"].append(url)

            # 嗅探 API
            self.api_sniffer.sniff_from_html(html, url)

            # 提取新链接
            if depth < self.max_depth:
                links = self._extract_links(html, url)
                for link in links:
                    if link not in self.visited_urls:
                        self.url_queue.append((link, depth + 1, url))

            # 延迟
            if self.delay > 0:
                time.sleep(self.delay)

        # 主动探测常见 API
        print("  🔍 主动探测常见 API 端点...")
        self.api_sniffer.probe_common_apis()

        # 保存页面树
        self._save_page_tree()

        # 保存 API 记录
        self.api_sniffer.save_records()

        print(f"\n✅ 爬取完成!")
        print(f"   页面数: {len(self.page_tree)}")
        print(f"   API 数: {len(self.api_sniffer.api_records)}")

        return self.page_tree

    def _save_page_tree(self):
        """保存页面树"""
        tree_file = self.output_dir / "page_tree.json"
        with open(tree_file, "w", encoding="utf-8") as f:
            json.dump({
                "base_url": self.start_url,
                "base_domain": self.base_domain,
                "page_count": len(self.page_tree),
                "pages": self.page_tree
            }, f, ensure_ascii=False, indent=2)
        print(f"  📁 页面树已保存: {tree_file}")


def main():
    parser = argparse.ArgumentParser(description="网站爬虫 - 构建页面树并采集数据")
    parser.add_argument("url", help="起始 URL")
    parser.add_argument("--output-dir", "-o", default="./test_data", help="输出目录")
    parser.add_argument("--max-depth", "-d", type=int, default=3, help="最大爬取深度")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔（秒）")
    parser.add_argument("--use-playwright", action="store_true", help="使用 Playwright 渲染动态页面")
    args = parser.parse_args()

    crawler = WebCrawler(
        start_url=args.url,
        output_dir=args.output_dir,
        max_depth=args.max_depth,
        delay=args.delay,
        use_playwright=args.use_playwright
    )

    crawler.crawl()


if __name__ == "__main__":
    main()
