#!/usr/bin/env python3
"""
crawler.py - 网站爬取器（支持 SPA/Hash 路由）

特性:
- 自动检测 SPA 应用并使用 Hash 路由
- 拦截网络请求提取真实 API 路径
- 构建页面树结构
- 保存页面 HTML 和元数据

用法:
  python crawler.py <URL> [--output-dir DIR] [--max-depth N] [--token TOKEN]
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse


class WebCrawler:
    def __init__(self, output_dir: str = "./test_data", max_depth: int = 2):
        self.output_dir = Path(output_dir)
        self.max_depth = max_depth
        self.base_url = ""
        self.is_spa = False
        self.api_records = []
        self.page_tree = []
        self.visited_urls = set()

        for subdir in ["pages", "apis", "screenshots"]:
            (self.output_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _detect_spa(self, page) -> bool:
        """检测是否为 SPA 应用"""
        try:
            is_vue = page.evaluate("() => !!window.__VUE__ || !!window.Vue || document.querySelector('#app')")
            is_angular = page.evaluate("() => !!window.ng || !!window.angular")
            is_react = page.evaluate("() => !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__ || !!window.React")

            has_hash_router = page.evaluate("() => window.location.hash !== ''")
            has_history_api = page.evaluate("() => typeof window.history.pushState === 'function'")

            spa_indicators = [is_vue, is_angular, is_react]
            is_spa = any(spa_indicators)

            print(f"  SPA 检测: Vue={is_vue} Angular={is_angular} React={is_react}")
            print(f"  路由模式: Hash路由={has_hash_router} History API={has_history_api}")

            return is_spa
        except Exception as e:
            print(f"  ⚠️ SPA 检测失败: {e}")
            return False

    def _get_route_prefix(self, page) -> str:
        """获取正确的路由前缀"""
        if not self.is_spa:
            return ""

        try:
            has_hash_support = page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script'));
                    return scripts.some(s => s.src && (s.src.includes('router') || s.src.includes('vue-router')));
                }
            """)

            if has_hash_support:
                current_hash = page.evaluate("() => window.location.hash")
                if current_hash or "hash" in str(page.url()).lower():
                    return "#"

            check_html = page.content()
            if 'router' in check_html.lower() and ('hash' in check_html.lower() or 'mode' in check_html.lower()):
                return "#"
        except Exception:
            pass

        return ""

    def _setup_api_interception(self, page):
        """设置 API 请求拦截"""
        captured_apis = []

        def handle_request(request):
            url = request.url
            if any(url.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.svg', '.ico', '.woff', '.woff2']):
                return

            if url.startswith(('http://', 'https://')) and '/api/' in url:
                api_info = {
                    "method": request.method,
                    "url": url,
                    "path": urlparse(url).path,
                    "headers": dict(request.headers),
                    "timestamp": datetime.now().isoformat()
                }
                captured_apis.append(api_info)
                print(f"  📡 拦截到 API: {request.method} {urlparse(url).path}")

        def handle_response(response):
            if response.request.url in [a['url'] for a in captured_apis]:
                try:
                    body = response.text()
                    for api in captured_apis:
                        if api['url'] == response.request.url:
                            api["status"] = response.status
                            api["response_preview"] = body[:500] if len(body) > 500 else body
                            break
                except Exception:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        return captured_apis

    def _inject_token_before_load(self, page, token: str):
        """在页面加载前注入 Token（解决 Vue domContentLoaded 时序问题）"""
        init_script = f"""
        () => {{
            Object.defineProperty(window, 'localStorage', {{
                value: new Proxy(localStorage, {{
                    set: function(target, prop, value) {{
                        if (prop === 'setItem') {{
                            const originalSetItem = target.setItem.bind(target);
                            target.setItem = function(key, val) {{
                                originalSetItem(key, val);
                            }};
                        }}
                        target[prop] = value;
                        return true;
                    }}
                }}),
                writable: false,
                configurable: true
            }});
            
            localStorage.setItem('token', '{token}');
            localStorage.setItem('Authorization', 'Bearer {token}');
            
            Object.defineProperty(document, 'cookie', {{
                get: () => 'token={token}',
                set: () => {{}},
                configurable: true
            }});
        }}
        """
        page.add_init_script(init_script)
        print(f"  🔐 Token 已通过 add_init_script 注入（页面加载前生效）")

    async def crawl(self, url: str, token: str = None) -> dict:
        """执行爬取"""
        from playwright.async_api import async_playwright

        self.base_url = url
        parsed_url = urlparse(url)

        print(f"\n🕷️ 开始爬取: {url}")
        print(f"   最大深度: {self.max_depth}")
        print(f"   输出目录: {self.output_dir}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            if token:
                await context.add_init_script(f"""
                    localStorage.setItem('token', '{token}');
                    localStorage.setItem('Authorization', 'Bearer {token}');
                """)
                print(f"  🔐 全局 Token 注入已配置")

            page = await context.new_page()

            self.is_spa = False
            route_prefix = ""

            captured_apis = self._setup_api_interception(page)

            print(f"\n📄 正在加载首页...")
            start_time = time.time()

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                load_time = round((time.time() - start_time) * 1000, 2)
                print(f"  ✅ 首页加载完成 ({load_time}ms)")

                self.is_spa = self._detect_spa(page)

                if self.is_spa:
                    route_prefix = self._get_route_prefix(page)
                    print(f"  🔄 检测到 SPA 应用，路由前缀: '{route_prefix}' 或使用 History 模式")
                    await page.wait_for_timeout(2000)

            except Exception as e:
                print(f"  ❌ 页面加载失败: {e}")
                load_time = round((time.time() - start_time) * 1000, 2)

            page_info = await self._capture_page(page, url, "index", route_prefix, load_time)
            self.page_tree.append(page_info)

            links = await self._extract_links(page, url, route_prefix)
            print(f"\n🔗 发现 {len(links)} 个链接")

            for i, link_info in enumerate(links[:20], 1):
                if i > self.max_depth * 5:
                    break

                link_url = link_info["url"]
                link_text = link_info.get("text", "")[:30]

                if link_url in self.visited_urls:
                    continue

                self.visited_urls.add(link_url)
                print(f"\n  [{i}] 爬取: {link_text} -> {link_url}")

                try:
                    nav_start = time.time()
                    new_page = await context.new_page()
                    self._setup_api_interception(new_page)

                    if token:
                        await new_page.add_init_script(f"""
                            localStorage.setItem('token', '{token}');
                        """)

                    actual_url = link_url
                    if self.is_spa and route_prefix == "#" and not link_url.startswith(url + "/#"):
                        path = link_url.replace(url, "")
                        actual_url = f"{url}/#{path}" if path.startswith("/") else f"{url}#{path}"

                    await new_page.goto(actual_url, wait_until="domcontentloaded", timeout=30000)
                    nav_time = round((time.time() - nav_start) * 1000, 2)

                    await new_page.wait_for_timeout(1500)

                    page_name = link_info.get("name", f"page_{i}")
                    sub_page_info = await self._capture_page(new_page, actual_url, page_name, route_prefix, nav_time)
                    self.page_tree.append(sub_page_info)

                    sub_links = await self._extract_links(new_page, actual_url, route_prefix)
                    links.extend(sub_links)

                    await new_page.close()

                except Exception as e:
                    print(f"      ⚠️ 跳过: {e}")
                    continue

            await page.close()
            await browser.close()

        all_apis = captured_apis + self.api_records
        unique_apis = []
        seen_paths = set()
        for api in all_apis:
            key = f"{api.get('method', '')}:{api.get('path', '')}"
            if key not in seen_paths and api.get('path'):
                seen_paths.add(key)
                unique_apis.append(api)

        result = {
            "crawl_time": datetime.now().isoformat(),
            "base_url": url,
            "is_spa": self.is_spa,
            "route_mode": "hash" if route_prefix == "#" else ("history" if self.is_spa else "traditional"),
            "total_pages": len(self.page_tree),
            "total_apis": len(unique_apis),
            "pages": [{"name": p["name"], "url": p["url"], "title": p.get("title", "")} for p in self.page_tree],
            "api_endpoints": unique_apis
        }

        output_path = self.output_dir / "page_tree.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        api_path = self.output_dir / "apis" / "api_records.json"
        with open(api_path, "w", encoding="utf-8") as f:
            json.dump(unique_apis, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 爬取完成!")
        print(f"   页面数: {len(self.page_tree)}")
        print(f"   API 数: {len(unique_apis)}")
        print(f"   结果保存: {output_path}")

        return result

    async def _capture_page(self, page, url: str, name: str, route_prefix: str, load_time: float) -> dict:
        """捕获页面信息"""
        pages_dir = self.output_dir / "pages"
        safe_name = name.replace("/", "_").replace("#", "_").replace(" ", "_")

        try:
            title = await page.title()
        except Exception:
            title = ""

        try:
            html_content = await page.content()
            html_path = pages_dir / f"{safe_name}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception:
            html_content = ""
            html_path = None

        try:
            screenshot_path = self.output_dir / "screenshots" / f"{safe_name}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            screenshot_path = None

        try:
            elements = await page.evaluate("""() => {
                const elements = [];
                document.querySelectorAll('a, button, input, select, textarea, form, [role=button], [onclick]').forEach(el => {
                    if (el.offsetParent !== null || el.tagName === 'INPUT' || el.tagName === 'SELECT') {
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            id: el.id || '',
                            class: el.className ? String(el.className).split(' ')[0] : '',
                            text: (el.textContent || el.value || '').trim().slice(0, 50),
                            selector: el.id ? '#' + el.id : (el.className ? '.' + String(el.className).split(' ')[0] : '')
                        });
                    }
                });
                return elements.slice(0, 100);
            }""")
        except Exception:
            elements = []

        meta = {
            "name": name,
            "url": url,
            "title": title,
            "load_time_ms": load_time,
            "timestamp": datetime.now().isoformat(),
            "elements_count": len(elements),
            "html_file": str(html_path.relative_to(self.output_dir)) if html_path else None,
            "screenshot": str(screenshot_path.relative_to(self.output_dir)) if screenshot_path else None,
            "interactive_elements": elements[:50]
        }

        meta_path = pages_dir / f"{safe_name}_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return meta

    async def _extract_links(self, page, base_url: str, route_prefix: str) -> list:
        """提取页面链接"""
        try:
            links = await page.evaluate("""(baseUrl) => {
                const links = [];
                const seen = new Set();
                
                document.querySelectorAll('a[href], [router-link], [data-href]').forEach(el => {
                    let href = el.getAttribute('href') || el.getAttribute('router-link') || el.getAttribute('data-href');
                    
                    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:')) 
                        return;
                        
                    if (!href.startsWith('http')) {
                        href = new URL(href, baseUrl).href;
                    }
                    
                    const urlObj = new URL(href);
                    if (urlObj.origin === new URL(baseUrl).origin && !seen.has(href)) {
                        seen.add(href);
                        links.push({
                            url: href,
                            text: (el.textContent || '').trim().slice(0, 50),
                            name: (el.textContent || '').trim().slice(0, 30).replace(/[^\\w\\u4e00-\\u9fa5]/g, '_') || 'link'
                        });
                    }
                });
                
                return links;
            }""", base_url)

            return links
        except Exception as e:
            print(f"      ⚠️ 链接提取失败: {e}")
            return []


def main():
    parser = argparse.ArgumentParser(description="网站爬取器（支持 SPA）")
    parser.add_argument("url", help="目标 URL")
    parser.add_argument("--output-dir", "-o", default="./test_data", help="输出目录")
    parser.add_argument("--max-depth", "-d", type=int, default=2, help="最大爬取深度")
    parser.add_argument("--token", "-t", help="认证 Token")
    args = parser.parse_args()

    import asyncio
    crawler = WebCrawler(args.output_dir, args.max_depth)
    result = asyncio.run(crawler.crawl(args.url, args.token))

    print(f"\n📊 爬取摘要:")
    print(f"   SPA 应用: {'是' if result['is_spa'] else '否'}")
    print(f"   路由模式: {result['route_mode']}")
    print(f"   发现页面: {result['total_pages']}")
    print(f"   发现 API: {result['total_apis']}")


if __name__ == "__main__":
    main()
