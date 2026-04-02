#!/usr/bin/env python3
"""
swagger_fetcher.py - Swagger/OpenAPI 接口文档抓取器

支持:
- 自动发现 Swagger 端点
- 解析 OpenAPI 2.0/3.0 格式
- 提取 API 定义和参数
- 生成本地化接口文档

用法:
  python swagger_fetcher.py <BASE_URL> [--output DIR] [--token TOKEN] [--header KEY=VALUE]
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse


class SwaggerFetcher:
    SWAGGER_PATHS = [
        "/swagger-ui.html",
        "/swagger-ui/",
        "/swagger-ui/index.html",
        "/api/swagger-ui.html",
        "/api/swagger-ui/",
        "/doc.html",
        "/docs",
        "/api/docs",
        "/v2/api-docs",
        "/v3/api-docs",
        "/swagger-resources",
        "/swagger-resources/configuration/ui",
        "/swagger-resources/configuration/security"
    ]

    def __init__(self, output_dir: str = "./test_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, base_url: str, token: str = None, headers: dict = None) -> dict:
        """抓取 Swagger 文档"""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as e:
            print(f"ERROR: 缺少依赖: {e}")
            print("安装方法: pip install requests beautifulsoup4")
            sys.exit(1)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*"
        })

        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})

        if headers:
            session.headers.update(headers)

        print(f"\n🔍 正在探测 Swagger 端点: {base_url}")

        swagger_url = self._discover_swagger_url(session, base_url)

        if not swagger_url:
            print("❌ 未找到 Swagger/OpenAPI 端点")
            print("\n尝试手动指定:")
            print(f"  python swagger_fetcher.py {base_url} --swagger-url /v2/api-docs")
            return {"error": "Swagger endpoint not found"}

        print(f"✅ 发现 Swagger: {swagger_url}")

        api_docs = self._fetch_api_docs(session, base_url, swagger_url)

        if not api_docs:
            print("❌ 无法获取 API 文档内容")
            return {"error": "Failed to fetch API docs"}

        parsed = self._parse_openapi_spec(api_docs, base_url)

        output_file = self.output_dir / "apis" / "swagger_docs.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)

        md_report = self._generate_markdown_report(parsed)
        md_path = self.output_dir / "apis" / "api_documentation.md"
        md_path.write_text(md_report, encoding="utf-8")

        print(f"\n✅ API 文档已保存!")
        print(f"   JSON: {output_file}")
        print(f"   Markdown: {md_path}")
        print(f"   API 数量: {len(parsed.get('paths', {}))}")

        return parsed

    def _discover_swagger_url(self, session, base_url: str) -> str:
        """自动发现 Swagger URL"""
        for path in self.SWAGGER_PATHS:
            url = urljoin(base_url, path)
            try:
                resp = session.get(url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    content_type = resp.headers.get("Content-Type", "")

                    if "json" in content_type:
                        print(f"  📡 发现 JSON API 文档: {url}")
                        return url

                    if "html" in content_type or "text" in content_type:
                        if self._is_swagger_page(resp.text):
                            print(f"  📡 发现 Swagger UI: {url}")
                            api_url = self._extract_api_url_from_html(resp.text, url)
                            if api_url:
                                return api_url
                            return url
            except Exception:
                continue

        try:
            resp = session.get(base_url, timeout=10)
            if resp.status_code == 200:
                api_urls = re.findall(r'(?:url|src)\s*[=:]\s*["\']([^"\']*api-docs[^"\']*)["\']',
                                      resp.text, re.IGNORECASE)
                if api_urls:
                    full_url = urljoin(base_url, api_urls[0])
                    print(f"  📡 从首页发现 API 文档引用: {full_url}")
                    return full_url
        except Exception:
            pass

        return ""

    def _is_swagger_page(self, html: str) -> bool:
        """检查是否是 Swagger 页面"""
        indicators = ["swagger", "openapi", "api-docs", "springfox", "redoc"]
        html_lower = html.lower()
        return any(ind in html_lower for ind in indicators)

    def _extract_api_url_from_html(self, html: str, page_url: str) -> str:
        """从 HTML 中提取 API 文档 URL"""
        patterns = [
            r'url\s*:\s*["\']([^"\']+)["\']',
            r'src\s*=\s*["\']([^"\']*config[^"\']*)["\']',
            r'"url"\s*:\s*"([^"]+)"'
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                candidate = match.group(1)
                if candidate.startswith("http"):
                    return candidate
                return urljoin(page_url, candidate)

        return ""

    def _fetch_api_docs(self, session, base_url: str, swagger_url: str) -> dict:
        """获取 API 文档"""
        try:
            resp = session.get(swagger_url, timeout=30)
            if resp.status_code != 200:
                print(f"  ⚠️ HTTP {resp.status_code}")
                return {}

            content_type = resp.headers.get("Content-Type", "")

            if "json" in content_type:
                try:
                    return resp.json()
                except Exception as e:
                    print(f"  ⚠️ JSON 解析失败: {e}")
                    return {}

            if "html" in content_type:
                return self._extract_embedded_json(resp.text, swagger_url)

            return {}
        except Exception as e:
            print(f"  ❌ 获取失败: {e}")
            return {}

    def _extract_embedded_json(self, html: str, base_url: str) -> dict:
        """从 HTML 页面中提取嵌入的 JSON"""
        patterns = [
            r'window\[\'swagger\'\]\s*=\s*({.+?})\s*;',
            r'SwaggerConfig\s*=\s*({.+?})\s*;',
            r'var\s+spec\s*=\s*({.+?})\s*;'
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        return {}

    def _parse_openapi_spec(self, spec: dict, base_url: str) -> dict:
        """解析 OpenAPI 规范"""
        version = spec.get("swagger") or spec.get("openapi", "unknown")

        info = spec.get("info", {})
        paths = spec.get("paths", {})

        parsed_apis = []

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue

            for method, details in methods.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                api_info = {
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "tags": details.get("tags", []),
                    "parameters": self._extract_parameters(details.get("parameters", [])),
                    "request_body": self._extract_request_body(details.get("requestBody")),
                    "responses": self._extract_responses(details.get("responses", {})),
                    "security": details.get("security", spec.get("security", [])),
                    "consumes": details.get("consumes", []),
                    "produces": details.get("produces", []),
                    "operation_id": details.get("operationId", ""),
                    "deprecated": details.get("deprecated", False)
                }

                parsed_apis.append(api_info)

        result = {
            "fetch_time": datetime.now().isoformat(),
            "base_url": base_url,
            "openapi_version": version,
            "info": {
                "title": info.get("title", ""),
                "version": info.get("version", ""),
                "description": info.get("description", "")
            },
            "base_path": spec.get("basePath", spec.get("servers", [{"url": ""}])[0].get("url", "") if spec.get("servers") else ""),
            "total_apis": len(parsed_apis),
            "paths": {api["path"]: api for api in parsed_apis},
            "apis": parsed_apis,
            "tags": self._extract_tags(spec),
            "definitions": self._extract_definitions(spec)
        }

        return result

    def _extract_parameters(self, parameters: list) -> list:
        """提取参数定义"""
        result = []
        for param in parameters:
            result.append({
                "name": param.get("name", ""),
                "in": param.get("in", ""),
                "required": param.get("required", False),
                "type": param.get("type", param.get("schema", {}).get("type", "")),
                "description": param.get("description", ""),
                "default": param.get("default"),
                "enum": param.get("enum", [])
            })
        return result

    def _extract_request_body(self, request_body: dict) -> dict:
        """提取请求体定义"""
        if not request_body:
            return {}

        content = request_body.get("content", {})
        schema = {}
        for ct, details in content.items():
            schema = details.get("schema", {})
            break

        return {
            "content_types": list(content.keys()),
            "schema": schema,
            "required": request_body.get("required", False),
            "description": request_body.get("description", "")
        }

    def _extract_responses(self, responses: dict) -> list:
        """提取响应定义"""
        result = []
        for code, details in responses.items():
            if isinstance(details, dict):
                result.append({
                    "code": code,
                    "description": details.get("description", ""),
                    "schema": details.get("schema", {}),
                    "content": list(details.get("content", {}).keys())
                })
        return result

    def _extract_tags(self, spec: dict) -> list:
        """提取标签"""
        tags = spec.get("tags", [])
        return [{"name": t.get("name", ""), "description": t.get("description", "")} for t in tags]

    def _extract_definitions(self, spec: dict) -> dict:
        """提取模型定义"""
        definitions = spec.get("definitions", spec.get("components", {}).get("schemas", {}))

        simplified = {}
        for name, schema in definitions.items():
            if isinstance(schema, dict):
                simplified[name] = {
                    "type": schema.get("type", "object"),
                    "properties": list(schema.get("properties", {}).keys()),
                    "required": schema.get("required", [])
                }

        return simplified

    def _generate_markdown_report(self, parsed: dict) -> str:
        """生成 Markdown 格式的 API 文档"""
        lines = []
        lines.append("# API 接口文档")
        lines.append("")
        lines.append(f"> 抓取时间: {parsed.get('fetch_time', '')}")
        lines.append(f"> 来源: {parsed.get('base_url', '')}")
        lines.append(f"> OpenAPI 版本: {parsed.get('openapi_version', '')}")
        lines.append("")

        info = parsed.get("info", {})
        if info.get("title"):
            lines.append(f"## {info.get('title', '')} v{info.get('version', '')}")
            if info.get("description"):
                lines.append(f"\n{info['description']}\n")

        lines.append("---")
        lines.append("")
        lines.append(f"**总计**: {parsed.get('total_apis', 0)} 个 API 接口")
        lines.append("")

        tags = parsed.get("tags", [])
        if tags:
            lines.append("## 接口分类")
            lines.append("")
            for tag in tags:
                lines.append(f"- **{tag['name']}**: {tag.get('description', '')}")
            lines.append("")

        lines.append("## 接口列表")
        lines.append("")

        apis = parsed.get("apis", [])

        current_tag = None
        for api in apis:
            api_tags = api.get("tags", ["default"])
            tag = api_tags[0] if api_tags else "default"

            if tag != current_tag:
                current_tag = tag
                lines.append(f"### {tag}")
                lines.append("")

            method_color = {
                "GET": "🟢", "POST": "🔵", "PUT": "🟡", "PATCH": "🟠", "DELETE": "🔴"
            }
            icon = method_color.get(api["method"], "⚪")

            lines.append(f"#### {icon} `{api['method']}` {api['path']}")
            lines.append("")

            if api.get("summary"):
                lines.append(f"**摘要**: {api['summary']}")
            if api.get("description"):
                lines.append(f"**描述**: {api['description']}")
            lines.append("")

            params = api.get("parameters", [])
            if params:
                lines.append("**参数**:")
                lines.append("")
                lines.append("| 参数名 | 位置 | 类型 | 必填 | 说明 |")
                lines.append("|--------|------|------|------|------|")
                for p in params:
                    lines.append(f"| `{p['name']}` | {p['in']} | {p['type']} | "
                               f"{'✅' if p['required'] else '❌'} | {p['description']} |")
                lines.append("")

            body = api.get("request_body", {})
            if body and body.get("schema"):
                lines.append("**请求体**:")
                lines.append("```json")
                lines.append(json.dumps(body.get("schema", {}), ensure_ascii=False, indent=2))
                lines.append("```")
                lines.append("")

            responses = api.get("responses", [])
            if responses:
                lines.append("**响应**:")
                lines.append("")
                for r in responses:
                    lines.append(f"- `{r['code']}`: {r['description']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        definitions = parsed.get("definitions", {})
        if definitions:
            lines.append("## 数据模型")
            lines.append("")
            for name, defn in definitions.items():
                lines.append(f"### {name}")
                lines.append(f"- 类型: {defn.get('type')}")
                if defn.get("properties"):
                    lines.append(f"- 属性: {', '.join(defn['properties'])}")
                if defn.get("required"):
                    lines.append(f"- 必填: {', '.join(defn['required'])}")
                lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Swagger/OpenAPI 接口文档抓取器")
    parser.add_argument("url", help="基础 URL 或 Swagger 直接地址")
    parser.add_argument("--output-dir", "-o", default="./test_data", help="输出目录")
    parser.add_argument("--token", "-t", help="认证 Token")
    parser.add_argument("--header", "-H", action="append", default=[],
                       help="额外请求头 (格式: Key=Value)")
    parser.add_argument("--swagger-url", default=None, help="手动指定 Swagger 路径")
    args = parser.parse_args()

    fetcher = SwaggerFetcher(args.output_dir)

    headers = {}
    for h in args.header:
        if "=" in h:
            k, v = h.split("=", 1)
            headers[k.strip()] = v.strip()

    if args.swagger_url:
        from urllib.parse import urljoin
        target_url = urljoin(args.url, args.swagger_url)
    else:
        target_url = args.url

    result = fetcher.fetch(target_url, args.token, headers if headers else None)


if __name__ == "__main__":
    main()
