# Web Software Tester

Web 端软件测试技能，支持自动探索网页、运行功能测试、解析测试用例数据，并生成详细测试报告。

## 功能特性

- 🌐 **页面自动探索** - 自动发现可测试元素（表单、按钮、链接等）
- 🧪 **多功能测试** - 支持导航、表单提交、登录、按钮点击、API 检查
- 📊 **多格式支持** - Excel、CSV、JSON 测试用例解析
- 📝 **丰富报告** - 生成 Markdown/PDF/Word 格式测试报告
- 📸 **失败截图** - 测试失败时自动保存页面状态

## 测试类型

| 类型 | 说明 |
|------|------|
| `navigation` | 页面跳转、链接点击 |
| `form_submit` | 表单提交、输入验证 |
| `login` | 登录/登出流程 |
| `button_click` | 按钮点击响应 |
| `api_check` | API 请求/响应检查 |

## 快速开始

### 安装依赖

```bash
pip install weasyprint python-docx
```

### 运行测试

```bash
python3 scripts/test_runner.py \
  --config '{"url": "https://example.com", "auto_explore": true}' \
  --cases /path/to/test_data.xlsx \
  --format markdown \
  --report-output /tmp/test_report.md
```

## 项目结构

```
.
├── SKILL.md              # 技能定义文件
├── scripts/
│   ├── page_explorer.py  # 页面探索辅助
│   ├── test_runner.py     # 测试执行器 + 报告生成
│   ├── parse_cases.py     # 测试用例解析
│   ├── convert_to_pdf.py  # Markdown → PDF
│   └── convert_to_docx.py # Markdown → Word
└── screenshots/          # 失败截图保存目录
```

## 测试用例格式

### CSV 格式

```csv
name,type,selector,value,expected
测试登录-正确账号,login,input[name=username],admin,登录成功
测试搜索功能,form_submit,input[name=q],keyword,显示结果
```

### JSON 格式

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

第一行为表头，支持字段：`name`, `type`, `selector`, `value`, `expected`, `wait_ms`。

## 报告内容

- ✅ 测试用例通过/失败状态
- 📸 失败时的页面截图
- ⏱️ 每个操作的响应时间
- 🐛 Bug 描述（期望行为 vs 实际行为）
- 📊 测试概览：总数、通过数、失败数、通过率

## 工作流程

1. **接收需求** - 获取目标 URL、账号密码、测试用例文件
2. **页面探索** - 打开页面、获取结构、识别可测试元素
3. **确认计划** - 与用户确认测试范围和报告格式
4. **执行测试** - 按测试类型执行并记录结果
5. **生成报告** - 输出指定格式的测试报告
