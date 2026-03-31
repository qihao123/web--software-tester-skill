---
name: web-software-tester
description: Web 业务驱动测试技能。支持自动爬取网站构建页面树、分析页面功能、保存 HTML 和 API 数据、进行业务建模、生成业务逻辑文档、基于业务逻辑自动生成测试用例并执行，最终输出基于业务的测试报告。触发场景：用户要求测试网站/网页、进行业务流程测试、生成业务测试报告、理解网站业务逻辑、进行回归测试。
---

# Web 软件测试技能（业务驱动）

本技能通过分析网站业务逻辑，自动生成并执行基于业务场景的测试用例。

## 工作流程概览

```
目标 URL → 爬取采集 → 页面分析 → 业务建模 → 生成用例 → 执行测试 → 生成报告
```

## 阶段说明

### 阶段 1: 数据采集（crawler）

爬取目标网站，构建页面树，保存 HTML 代码，嗅探 API 端点。

```bash
python3 scripts/crawler.py <URL> --output-dir ./test_data --max-depth 3
```

**输出：**
- `page_tree.json` - 页面树结构（页面间关联关系）
- `pages/*.html` - 各页面原始 HTML
- `pages/*_meta.json` - 页面元数据（表单、按钮、链接等）
- `apis/api_records.json` - API 调用记录（URL、方法、参数、响应样例）

**参数说明：**
- `--max-depth N` - 最大爬取深度（默认 3）
- `--delay SEC` - 请求间隔（默认 0.5 秒）
- `--use-playwright` - 使用 Playwright 渲染动态页面（需要安装 playwright）

### 阶段 2: 页面功能分析（page_analyzer）

分析采集的页面数据，识别页面类型和功能。

```bash
python3 scripts/page_analyzer.py --input-dir ./test_data --output ./test_data/page_analysis.json
```

**分析内容：**
- 页面类型检测（登录页、注册页、搜索页、列表页等）
- 表单功能分析（登录、注册、搜索、提交等）
- 用户交互流程识别
- 数据实体提取

**输出：**
- `page_analysis.json` - 各页面的详细功能分析

### 阶段 3: 业务建模（business_modeler）

基于采集数据生成业务逻辑文档。

```bash
python3 scripts/business_modeler.py --input-dir ./test_data --output ./test_data/business_logic.md
```

**生成内容：**
- 业务实体定义（用户、订单、商品等）
- 业务流程描述（登录流程、注册流程、下单流程等）
- 页面与功能映射
- API 与功能映射

**输出：**
- `business_logic.md` - Markdown 格式业务逻辑文档

### 阶段 4: 测试用例生成（test_generator）

基于业务逻辑自动生成测试用例。

```bash
python3 scripts/test_generator.py \
  --business-doc ./test_data/business_logic.md \
  --page-analysis ./test_data/page_analysis.json \
  --output ./test_data/test_cases.json
```

**生成用例类型：**
- 业务流程测试（主流程 + 异常分支）
- 页面功能测试（导航、元素存在性）
- API 接口测试（可访问性、响应验证）
- 跨页面端到端测试

**输出：**
- `test_cases.json` - 机器可读测试用例
- `test_cases.csv` - 人工可读测试用例（表格格式）

### 阶段 5: 测试执行（test_runner）

执行生成的测试用例。

```bash
python3 scripts/test_runner.py \
  --config '{"url": "<目标URL>"}' \
  --cases ./test_data/test_cases.json \
  --output-dir ./test_results
```

**测试模式：**
- **静态模式**（默认）：使用 requests + BeautifulSoup，速度快，适合静态页面
- **Playwright 模式**（加 `--use-playwright`）：真实浏览器，支持 JS 交互和截图

**输出：**
- `test_results.json` - 详细测试结果
- `screenshots/*.png` - 失败截图（Playwright 模式）

### 阶段 6: 报告生成（report_generator）

生成基于业务的测试报告。

```bash
python3 scripts/report_generator.py \
  --test-results ./test_results/test_results.json \
  --business-doc ./test_data/business_logic.md \
  --format markdown \
  --output ./test_report.md
```

**报告内容：**
- 执行摘要（通过率、状态评估）
- 业务流程测试结果（按流程分组）
- 按测试类型分类的详细结果
- 失败详情与 Bug 描述
- 改进建议

**输出格式：**
- Markdown（默认）
- HTML（加 `--format html`）

### 格式转换（可选）

将 Markdown 报告转换为 PDF 或 Word：

```bash
# 转 PDF（需要 weasyprint 或生成可打印 HTML）
python3 scripts/convert_to_pdf.py ./test_report.md -o ./test_report

# 转 Word（需要 python-docx）
python3 scripts/convert_to_docx.py ./test_report.md -o ./test_report.docx
```

## 完整端到端流程

一次性执行完整测试流程：

```bash
# 1. 设置变量
URL="https://example.com"
DATA_DIR="./test_data"
RESULTS_DIR="./test_results"

# 2. 爬取网站
python3 scripts/crawler.py "$URL" --output-dir "$DATA_DIR" --max-depth 2

# 3. 分析页面
python3 scripts/page_analyzer.py --input-dir "$DATA_DIR" --output "$DATA_DIR/page_analysis.json"

# 4. 业务建模
python3 scripts/business_modeler.py --input-dir "$DATA_DIR" --output "$DATA_DIR/business_logic.md"

# 5. 生成测试用例
python3 scripts/test_generator.py \
  --business-doc "$DATA_DIR/business_logic.md" \
  --page-analysis "$DATA_DIR/page_analysis.json" \
  --output "$DATA_DIR/test_cases.json"

# 6. 执行测试
python3 scripts/test_runner.py \
  --config "{\"url\": \"$URL\"}" \
  --cases "$DATA_DIR/test_cases.json" \
  --output-dir "$RESULTS_DIR"

# 7. 生成报告
python3 scripts/report_generator.py \
  --test-results "$RESULTS_DIR/test_results.json" \
  --business-doc "$DATA_DIR/business_logic.md" \
  --output "./test_report.md"

echo "✅ 测试完成！报告: ./test_report.md"
```

## 测试用例字段说明

生成的测试用例 JSON 结构：

```json
{
  "id": "FLOW_001",
  "name": "用户登录 - 主流程测试",
  "type": "business_flow",
  "category": "positive",
  "description": "验证用户登录主流程可以正常完成",
  "url": "https://example.com/login",
  "selector": "",
  "value": "",
  "expected": "登录成功",
  "priority": "high",
  "steps": ["访问登录页面", "输入用户名", "输入密码", "点击登录"],
  "source_flow": "用户登录"
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `name` | 测试用例名称 |
| `type` | 测试类型：business_flow, navigation, element_check, api_check, form_submit |
| `category` | 测试分类：positive（正向）, negative（异常） |
| `description` | 测试描述 |
| `url` | 目标页面 URL |
| `selector` | 元素选择器（用于 element_check） |
| `value` | 输入值或 API 端点 |
| `expected` | 期望结果 |
| `priority` | 优先级：high, medium, low |
| `steps` | 测试步骤列表（用于 business_flow） |
| `source_flow` | 所属业务流程 |

## 依赖安装

```bash
# 核心依赖
pip install requests beautifulsoup4

# 可选依赖（用于 Excel/Word 支持）
pip install openpyxl python-docx

# 可选依赖（用于真实浏览器测试）
pip install playwright
playwright install chromium

# 可选依赖（用于 PDF 生成）
pip install weasyprint
```

## 注意事项

1. **爬取限制**
   - 遵守网站的 robots.txt
   - 合理设置爬取延迟（`--delay`）
   - 限制爬取深度避免过度采集

2. **动态页面**
   - 静态模式无法执行 JavaScript
   - 需要测试 JS 交互时请使用 `--use-playwright`
   - Playwright 模式速度较慢但更真实

3. **业务建模局限**
   - 自动生成的业务逻辑文档是初版，建议人工审核
   - 复杂业务逻辑可能需要手动补充
   - 测试用例覆盖率取决于页面分析的完整性

4. **测试执行**
   - 静态模式下表单提交可能不完整（无法执行 JS 验证）
   - 涉及登录态的测试需要先在配置中提供凭证
   - API 测试可能受限于认证机制

## 扩展功能

### 使用外部测试用例

除了自动生成的用例，也可以导入外部测试用例：

```bash
python3 scripts/test_runner.py --cases ./my_custom_cases.csv --output-dir ./test_results
```

CSV 格式：
```csv
id,name,type,url,selector,value,expected
TC001,自定义测试,navigation,https://example.com,,,200
TC002,元素检查,element_check,https://example.com,h1,,Welcome
```

### 手动补充业务逻辑

自动生成的 `business_logic.md` 是初版，建议人工审核后补充：
- 添加业务规则说明
- 补充异常流程
- 完善数据实体定义

修改后的业务文档可以重新用于生成测试用例。
