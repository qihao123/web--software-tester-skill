---
name: web-software-tester
description: Web 业务驱动测试技能。支持自动爬取网站（含 SPA/Hash 路由）、从 Swagger 获取 API 文档、分析业务逻辑、生成专业测试文档（流程/接口/用例/计划）并执行接口和功能测试。触发场景：用户要求测试网站/网页、对页面进行自动化测试、生成测试报告、运行回归测试、验证表单/登录/按钮等功能、获取 API 接口文档。
---

# Web 业务驱动测试技能

## 工作流程

```
目标 URL → Swagger/API 爬取 → 页面探索 → 业务建模 → 生成用例 → 执行测试 → 专业报告
```

### Step 1：接收测试需求

用户通常会提供以下信息：

- **目标 URL**：要测试的网页地址
- **Swagger 地址**：API 文档地址（可选，如 /swagger-ui.html）
- **用户名/密码**：用于登录测试（可选）
- **Token**：认证令牌（可选）
- **报告格式**：Markdown / PDF / Word（默认询问用户）

### Step 2：获取 API 文档（新增）

使用 `scripts/swagger_fetcher.py` 自动发现并抓取 Swagger/OpenAPI 接口文档：

```bash
python3 scripts/swagger_fetcher.py https://target.com --output-dir ./test_data --token TOKEN
```

**特性**：
- 自动探测常见 Swagger 路径（`/swagger-ui.html`, `/v2/api-docs`, `/doc.html` 等）
- 支持 OpenAPI 2.0 / 3.0 规范解析
- 生成本地 JSON + Markdown 双格式接口文档
- 提取完整的参数定义、响应格式、数据模型

### Step 3：网站爬取（支持 SPA）

使用 `scripts/crawler.py` 爬取目标网站：

```bash
python3 scripts/crawler.py "https://target.com" \
  --output-dir ./test_data \
  --max-depth 2 \
  --token TOKEN
```

**核心改进**：
- ✅ **SPA 检测**：自动识别 Vue/React/Angular 应用
- ✅ **Hash 路由**：正确处理 `/#/home` 格式的 SPA 路由
- ✅ **API 拦截**：通过 Playwright 网络拦截提取真实 API 路径（不再靠猜）
- ✅ **Token 注入时机**：使用 `add_init_script()` 在页面加载前注入（解决 Vue domContentLoaded 时序问题）
- ✅ **智能等待**：异步等待页面渲染完成，替代硬编码 `sleep(2)`

### Step 4：业务分析与建模

```bash
# 页面功能分析
python3 scripts/page_analyzer.py --input-dir ./test_data --output ./test_data/page_analysis.json

# 业务逻辑建模
python3 scripts/business_modeler.py --input-dir ./test_data --output ./test_data/business_logic.md
```

**输出内容**：
- 📊 页面类型识别（列表页/表单页/登录页等）
- 🔗 交互流程检测
- 🏢 **业务实体提取**（从页面名 + API 路径）
- 📋 **标准业务流程模板**（登录/CRUD/查询/权限）
- 📐 **业务规则推断**（认证/输入校验/幂等性/审计等）
- 🔄 API 与业务实体的映射关系

### Step 5：生成专业测试文档

```bash
python3 scripts/test_generator.py \
  --business-doc ./test_data/business_logic.md \
  --api-doc ./test_data/apis/swagger_docs.json \
  --page-analysis ./test_data/page_analysis.json \
  --output ./test_data/test_cases.json
```

**生成的文档包含**：
| 文档类型 | 内容 |
|----------|------|
| 测试计划 | 目标/范围/策略/环境/进度安排/准出标准/风险评估 |
| 测试用例 | 业务流程用例 + API 接口用例 + UI 元素用例 + 安全测试用例 |
| 接口文档 | 基于 Swagger 的完整 API 说明（含参数/响应/示例） |
| 流程文档 | 标准化的业务流程步骤和预期结果 |

### Step 6：执行测试

#### 6.1 功能/UI 测试

```bash
python3 scripts/test_runner.py \
  --cases ./test_data/test_cases.json \
  --config '{"url": "https://target.com"}' \
  --output-dir ./test_results
```

#### 6.2 API 接口测试（新增）

```bash
python3 scripts/api_tester.py \
  --apis ./test_data/apis/swagger_docs.json \
  --base-url "https://target.com" \
  --token TOKEN \
  --output-dir ./test_results
```

**特性**：
- 异步并发执行（aiohttp）
- 正常请求 / 未认证 / 非法参数 多场景覆盖
- 响应时间统计（平均/最大/最小）
- 按 HTTP 方法分类汇总

### Step 7：生成专业报告

```bash
python3 scripts/report_generator.py \
  --test-results ./test_results/test_results.json \
  --business-doc ./test_data/business_logic.md \
  --output-dir ./test_results
```

**输出文档**：
| 报告 | 说明 |
|------|------|
| `execution_report.md` | 执行摘要 + 结果明细 + 缺陷汇总 + 改进建议 |
| `test_plan.md` | 完整测试计划（目标/范围/策略/进度/准出标准/风险） |
| `api_documentation.md` | 接口测试结果详情 |
| `flow_documentation.md` | 业务流程测试参考 |

## 脚本说明

| 脚本 | 用途 | 核心改进 |
|------|------|----------|
| `crawler.py` | 网站爬取（Playwright） | SPA/Hash路由、API拦截、Token预注入 |
| `page_analyzer.py` | 页面功能分析 | 类型识别、元素分类、流程推断 |
| `business_modeler.py` | 业务逻辑建模 | 实体提取、流程模板、规则推断、完整 Markdown 输出 |
| `test_generator.py` | 测试用例+计划生成 | 含安全测试用例、完整测试计划结构 |
| `api_tester.py` | API 接口测试 | 异步并发、多场景覆盖、性能指标 |
| `report_generator.py` | 专业报告生成 | 5 类专业文档、缺陷分级、改进建议 |
| `swagger_fetcher.py` | Swagger 文档抓取 | 自动发现、OpenAPI 解析、本地化存储 |
| `test_runner.py` | 功能测试执行器 | 支持多种测试类型 |
| `convert_to_pdf.py` | PDF 生成 | Playwright 优先 > WeasyPrint > HTML Fallback |
| `convert_to_docx.py` | Word 生成 | - |
| `parse_cases.py` | 测试用例解析 | Excel/CSV/JSON |

## 已解决的问题

| # | 问题 | 解决方案 |
|---|------|----------|
| 1 | 不懂 SPA/Hash 路由 | 自动检测 SPA 应用，正确处理 Hash 和 History 路由模式 |
| 2 | Token 注入时机错误 | 使用 `add_init_script()` 在页面加载前注入 |
| 3 | API 路径靠猜 | Playwright 网络请求拦截，从真实流量提取 API |
| 4 | 业务分析为空 | 完整实现 business_modeler，输出实体/流程/规则/映射 |
| 5 | PDF 依赖 WeasyPrint | Playwright PDF 优先，跨平台兼容 |
| 6 | 截图硬等待 | 异步智能等待 + 页面元素就绪检测 |

## 注意事项

- 内网/外网 URL 均可测试
- SPA 应用会自动检测并适配路由模式
- 截图保存在 `screenshots/` 目录
- PDF 推荐 Playwright 方式：`pip install playwright && playwright install chromium`
- Word 需要：`pip install python-docx`
- Swagger 抓取需要网络访问目标系统的 API 文档端点
