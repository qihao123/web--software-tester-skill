---
name: web-software-tester
description: Web 端软件测试技能。支持自动探索网页、运行功能测试、解析 Excel/CSV/JSON 测试用例数据，并生成 Markdown/PDF/Word 格式的详细测试报告。触发场景：用户要求测试网站/网页、对页面进行自动化测试、生成测试报告、运行回归测试、验证表单/登录/按钮等功能。
---

# Web 软件测试技能

## 工作流程

### Step 1：接收测试需求

用户通常会提供以下信息（不一定全部提供，有多少用多少）：

- **目标 URL**：要测试的网页地址
- **用户名/密码**：用于登录测试（可选）
- **测试用例文件**：Excel / CSV / JSON 格式的测试数据（可选）
- **报告格式**：Markdown / PDF / Word（默认询问用户）

如果用户没有提供测试用例文件，引导用户上传或手动输入测试数据。

### Step 2：页面探索（自动探索模式）

使用 `browser` 工具打开目标 URL：

1. 打开页面并等待加载完成
2. 使用 `browser snapshot` 获取页面结构
3. 截图保存初始页面状态
4. 识别可测试元素：表单、按钮、链接、输入框等

**注意**：如果提供了用户名密码，先尝试登录流程。

### Step 3：与用户确认测试计划

探索完成后，向用户展示发现的页面功能，然后询问：

- 是否要运行**功能测试**？
- 是否上传**测试用例数据文件**（Excel/CSV/JSON）？
- 报告要什么格式（Markdown / PDF / Word）？

> 如果用户提供了测试用例文件，使用 `scripts/parse_cases.py` 解析内容（支持 .xlsx/.csv/.json）。

### Step 4：执行测试

根据用户确认的计划执行测试。测试类型包括：

| 测试类型 | 说明 |
|----------|------|
| `navigation` | 页面跳转、链接点击 |
| `form_submit` | 表单提交、输入验证 |
| `login` | 登录/登出流程 |
| `button_click` | 按钮点击响应 |
| `api_check` | API 请求/响应检查 |

**执行要点**：
- 每个测试步骤都记录响应时间
- 失败时立即截图保存
- 如果没有提供测试数据，跳过数据填充测试，仅测试基础功能

### Step 5：生成报告

使用 `scripts/test_runner.py` 生成报告：

```bash
python3 ~/.qclaw/skills/web-software-tester/scripts/test_runner.py \
  --config '{"url": "https://example.com", "auto_explore": true}' \
  --cases /path/to/test_data.xlsx \
  --format markdown \
  --report-output /tmp/test_report.md
```

**报告内容**（全部包含）：
- ✅ 每个测试用例的通过/失败状态
- 📸 失败时的页面截图（保存到 `screenshots/` 目录）
- ⏱️ 每个操作的响应时间
- 🐛 发现的 Bug 描述（失败原因 + 期望行为 vs 实际行为）
- 📊 测试概览：总数、通过数、失败数、通过率

**格式转换**：
- Markdown → 直接保存
- PDF → 使用 `scripts/convert_to_pdf.py` 转换（需要 weasyprint）
- Word → 使用 `scripts/convert_to_docx.py` 转换（需要 python-docx）

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `scripts/page_explorer.py` | 页面探索辅助（参数解析 + 结果格式定义） |
| `scripts/test_runner.py` | 测试执行器 + 报告生成（Markdown/HTML） |
| `scripts/parse_cases.py` | 解析 Excel/CSV/JSON 测试用例 |
| `scripts/convert_to_pdf.py` | Markdown → PDF 转换 |
| `scripts/convert_to_docx.py` | Markdown → Word 转换 |

## 测试用例格式

### CSV 格式示例

```csv
name,type,selector,value,expected
测试登录-正确账号,login,input[name=username],admin,登录成功
测试登录-错误密码,login,input[name=password],wrongpass,提示错误
测试搜索功能,form_submit,input[name=q],keyword,显示结果
```

### JSON 格式示例

```json
[
  {
    "name": "测试登录-正确账号",
    "type": "login",
    "selector": "input[name=username]",
    "value": "admin",
    "expected": "登录成功"
  }
]
```

### Excel 格式

第一行为表头，后续每行一个用例。支持的表头字段：`name`, `type`, `selector`, `value`, `expected`, `wait_ms`。

## 注意事项

- 内网/外网 URL 均可测试
- 如果页面需要登录，先完成登录再进行其他测试
- 截图统一保存在 `screenshots/` 子目录下
- 报告中的截图路径使用相对路径 `../screenshots/xxx.png`
- PDF 转换需要安装依赖：`pip install weasyprint`
- Word 转换需要安装依赖：`pip install python-docx`
- 如果测试用例文件不存在或格式错误，跳过该文件并继续执行
