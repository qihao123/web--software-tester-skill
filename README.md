# Web Software Tester

Web 业务驱动测试技能，支持自动爬取网站、分析业务逻辑、生成基于业务场景的测试用例并执行。

## 功能特性

- 🕷️ **网站爬取** - 自动构建页面树，保存 HTML 和 API 数据
- 📊 **业务建模** - 自动识别业务实体和业务流程
- 🧪 **智能用例生成** - 基于业务逻辑自动生成测试用例
- 📈 **业务视角报告** - 按业务流程组织的测试报告
- 📸 **失败截图** - 测试失败时自动保存页面状态
- 🔄 **端到端测试** - 支持完整的业务流程测试
- 💰 **Token 节省** - 相比直接页面分析，显著降低 token 消耗（实测 12306 网站从数百万 token 降至 100 万出头）

## 工作流程

```
目标 URL → 爬取采集 → 页面分析 → 业务建模 → 生成用例 → 执行测试 → 生成报告
```

## 脚本列表

| 脚本 | 用途 |
|------|------|
| `crawler.py` | 爬取网站，构建页面树，保存 HTML，嗅探 API |
| `page_analyzer.py` | 分析页面功能，识别页面类型和交互流程 |
| `business_modeler.py` | 基于采集数据生成业务逻辑文档 |
| `test_generator.py` | 基于业务逻辑生成测试用例 |
| `test_runner.py` | 执行测试用例，记录结果 |
| `report_generator.py` | 生成基于业务的测试报告 |
| `convert_to_pdf.py` | Markdown → PDF 转换 |
| `convert_to_docx.py` | Markdown → Word 转换 |
| `parse_cases.py` | 解析外部测试用例（Excel/CSV/JSON）|

## 快速开始

### 安装依赖

```bash
pip install requests beautifulsoup4

# 可选依赖
pip install openpyxl python-docx  # Excel/Word 支持
pip install playwright && playwright install chromium  # 真实浏览器测试
```

### 端到端测试流程

```bash
# 设置目标 URL
URL="https://example.com"
DATA_DIR="./test_data"
RESULTS_DIR="./test_results"

# 1. 爬取网站
python3 scripts/crawler.py "$URL" --output-dir "$DATA_DIR" --max-depth 2

# 2. 分析页面
python3 scripts/page_analyzer.py --input-dir "$DATA_DIR" --output "$DATA_DIR/page_analysis.json"

# 3. 业务建模
python3 scripts/business_modeler.py --input-dir "$DATA_DIR" --output "$DATA_DIR/business_logic.md"

# 4. 生成测试用例
python3 scripts/test_generator.py \
  --business-doc "$DATA_DIR/business_logic.md" \
  --page-analysis "$DATA_DIR/page_analysis.json" \
  --output "$DATA_DIR/test_cases.json"

# 5. 执行测试
python3 scripts/test_runner.py \
  --config "{\"url\": \"$URL\"}" \
  --cases "$DATA_DIR/test_cases.json" \
  --output-dir "$RESULTS_DIR"

# 6. 生成报告
python3 scripts/report_generator.py \
  --test-results "$RESULTS_DIR/test_results.json" \
  --business-doc "$DATA_DIR/business_logic.md" \
  --output "./test_report.md"
```

## 测试用例格式

### JSON 格式

```json
{
  "id": "FLOW_001",
  "name": "用户登录 - 主流程测试",
  "type": "business_flow",
  "category": "positive",
  "description": "验证用户登录主流程可以正常完成",
  "url": "https://example.com/login",
  "expected": "登录成功",
  "priority": "high",
  "steps": ["访问登录页面", "输入用户名", "输入密码", "点击登录"],
  "source_flow": "用户登录"
}
```

### CSV 格式

```csv
id,name,type,url,selector,value,expected,priority
TC001,首页访问,navigation,https://example.com,,,200,high
TC002,搜索功能,element_check,https://example.com,input[name=q],,搜索按钮,medium
```

## 测试类型

| 类型 | 说明 |
|------|------|
| `business_flow` | 业务流程测试（端到端）|
| `navigation` | 页面导航测试 |
| `element_check` | 元素存在性测试 |
| `api_check` | API 接口测试 |
| `form_submit` | 表单提交测试 |

## 输出文件结构

```
test_data/
├── page_tree.json          # 页面树结构
├── pages/
│   ├── index.html          # 页面 HTML
│   ├── index_meta.json     # 页面元数据
│   └── ...
├── apis/
│   └── api_records.json    # API 记录
├── page_analysis.json      # 页面功能分析
├── business_logic.md       # 业务逻辑文档
└── test_cases.json         # 生成的测试用例

test_results/
├── test_results.json       # 测试结果
├── screenshots/            # 失败截图
└── final_report.md         # 测试报告
```

## 报告内容

- 📊 执行摘要（通过率、状态评估）
- 🔄 业务流程测试结果
- 📋 按测试类型分类的详细结果
- ❌ 失败详情与 Bug 描述
- 💡 改进建议

## 详细文档

详见 [SKILL.md](SKILL.md) 了解完整的技能使用指南。
