# GitHub Trending 每日推送机器人

🤖 自动获取 GitHub Trending 热门项目，使用 AI 智能分析，并通过飞书机器人推送日报。

## ✨ 功能特点

- 📊 **每日热榜**：自动获取 GitHub Trending 当日热门项目
- 🤖 **AI 分析**：使用硅基流动 AI（DeepSeek-V3）智能分析项目亮点
- 🎨 **内容美化**：生成格式精美的 Markdown 内容，带编程语言 emoji
- 📱 **飞书推送**：通过飞书机器人富文本卡片推送
- ⏰ **定时任务**：支持 GitHub Actions 定时运行
- 🔒 **安全配置**：所有敏感信息通过环境变量配置

## 📸 效果展示

### 飞书推送效果
- 精美的富文本卡片格式
- 展示项目名称、星数、编程语言
- AI 生成的中文描述和项目亮点
- 编程语言 emoji 图标

## 🚀 快速开始

### 方式一：部署到 GitHub Actions（推荐）

#### 1. Fork 项目

点击右上角 "Fork" 按钮将项目复制到你的 GitHub 仓库。

#### 2. 配置 Secrets

进入你 Fork 的仓库，依次点击：

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

添加以下必需配置：

| Secret 名称 | 说明 | 获取方式 |
|------------|------|---------|
| `SILICONFLOW_API_KEY` | 硅基流动 API Key | [硅基流动官网](https://siliconflow.cn) 注册获取 |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook URL | 飞书群聊添加自定义机器人获取 |

**可选配置**（不配置将使用默认值）：

| Secret 名称 | 说明 | 默认值 |
|------------|------|--------|
| `SILICONFLOW_MODEL` | AI 模型名称 | `deepseek-ai/DeepSeek-V3` |
| `SILICONFLOW_TIMEOUT` | API 超时时间（秒） | `60` |
| `GITHUB_SINCE` | Trending 时间范围 | `daily` |
| `GITHUB_LANGUAGE` | 筛选编程语言 | `""`（所有语言） |
| `REQUEST_TIMEOUT` | 请求超时时间（秒） | `30` |
| `MAX_RETRIES` | 最大重试次数 | `5` |
| `RETRY_DELAY` | 重试间隔（秒） | `5` |
| `LOG_ENABLED` | 是否启用日志 | `true` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

#### 3. 启用 GitHub Actions

进入 `Settings` → `Actions` → `General` → `Actions permissions`

选择 `Allow all actions and reusable workflows`

#### 4. 手动测试

进入 `Actions` 标签 → 选择 `GitHub Trending Bot` → 点击 `Run workflow`

查看运行日志，确认是否成功。

#### 5. 等待定时推送

默认配置为每天北京时间 8:00 自动推送。

### 方式二：本地运行

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

**Windows PowerShell:**
```powershell
$env:SILICONFLOW_API_KEY="your_api_key_here"
$env:FEISHU_WEBHOOK_URL="your_webhook_url_here"
```

**Linux/Mac:**
```bash
export SILICONFLOW_API_KEY="your_api_key_here"
export FEISHU_WEBHOOK_URL="your_webhook_url_here"
```

或者创建 `.env` 文件：
```env
SILICONFLOW_API_KEY=your_api_key_here
FEISHU_WEBHOOK_URL=your_webhook_url_here
```

#### 3. 运行程序

```bash
python github_trending_bot.py
```

## ⚙️ 配置说明

### 基础配置

#### 获取硅基流动 API Key

1. 访问 [硅基流动官网](https://siliconflow.cn)
2. 注册/登录账号
3. 进入控制台 → API Keys
4. 创建新的 API Key

#### 获取飞书 Webhook URL

1. 在飞书群聊中添加自定义机器人
2. 获取 Webhook URL
3. 可选：设置安全设置（关键词、IP 白名单等）

### 高级配置

#### 自定义推送时间

编辑 `.github/workflows/github-trending-bot.yml`：

```yaml
schedule:
  - cron: '0 0 * * *'  # 每天 UTC 0:00（北京时间 8:00）
```

常用时间配置：
- 每天北京时间 8:00：`cron: '0 0 * * *'`
- 每天北京时间 9:00：`cron: '0 1 * * *'`
- 每天北京时间 12:00：`cron: '0 4 * * *'`
- 每天北京时间 20:00：`cron: '0 12 * * *'`
- 每小时运行一次：`cron: '0 * * * *'`
- 每天工作日 9:00：`cron: '0 1 * * 1-5'`

#### 筛选特定编程语言

添加 Secret：`GITHUB_LANGUAGE = "python"`

支持的语言：Python、JavaScript、TypeScript、Java、Go、Rust、C++、PHP、Ruby 等

#### 调整热榜时间范围

添加 Secret：`GITHUB_SINCE = "weekly"`

可选值：
- `daily` - 今日热榜
- `weekly` - 本周热榜
- `monthly` - 本月热榜

## 📦 项目结构

```
8-github热榜日推送/
├── .github/
│   └── workflows/
│       └── github-trending-bot.yml  # GitHub Actions 配置
├── github_trending_bot.py           # 主程序
├── requirements.txt                 # Python 依赖
├── .gitignore                       # Git 忽略文件
├── README.md                        # 项目文档
└── DEPLOYMENT.md                    # 部署指南
```

## 🔧 技术栈

- **爬虫**：requests + BeautifulSoup4
- **AI 分析**：OpenAI SDK（硅基流动 API）
- **消息推送**：飞书机器人 Webhook API
- **自动化**：GitHub Actions

## 📝 配置案例

### 案例 1：推送 Python 项目每日热榜

配置 Secrets：
```
SILICONFLOW_API_KEY=sk-xxxxx
FEISHU_WEBHOOK_URL=https://open.feishu.cn/...
GITHUB_LANGUAGE=python
GITHUB_SINCE=daily
```

### 案例 2：推送每周所有语言热榜

配置 Secrets：
```
SILICONFLOW_API_KEY=sk-xxxxx
FEISHU_WEBHOOK_URL=https://open.feishu.cn/...
GITHUB_SINCE=weekly
```

### 案例 3：自定义推送时间（每天 20:00）

修改 `.github/workflows/github-trending-bot.yml`：
```yaml
schedule:
  - cron: '0 12 * * *'  # 每天 UTC 12:00（北京时间 20:00）
```

### 案例 4：增加重试次数和超时时间

配置 Secrets：
```
REQUEST_TIMEOUT=60
MAX_RETRIES=10
RETRY_DELAY=10
```

## 🐛 常见问题

### 1. 定时任务不运行

**解决方案：**
- 检查 cron 表达式是否正确
- 确认 GitHub Actions 已启用
- 查看运行日志是否有错误

### 2. 环境变量配置错误

**错误信息：**
```
未配置 SILICONFLOW_API_KEY 环境变量
未配置 FEISHU_WEBHOOK_URL 环境变量
```

**解决方案：**
- 确认必需的 Secrets 已配置
- 检查 Secret 名称是否拼写正确（区分大小写）
- 查看 Actions 日志中的环境变量验证信息

### 3. 爬取失败

**错误信息：**
```
请求超时（尝试 1/5）
连接失败（尝试 2/5）
```

**解决方案：**
- 检查网络连接
- 调整 `REQUEST_TIMEOUT` 和 `MAX_RETRIES` 参数
- 查看是否为临时网络问题

### 4. AI 分析失败

**错误信息：**
```
项目分析失败 xxx：API 请求失败
```

**解决方案：**
- 检查 `SILICONFLOW_API_KEY` 是否正确
- 确认 API 账户余额充足
- 检查模型名称是否正确

### 5. 飞书推送失败

**错误信息：**
```
飞书消息发送失败：Webhook 验证失败
```

**解决方案：**
- 检查 `FEISHU_WEBHOOK_URL` 是否正确
- 确认飞书机器人配置正常
- 检查是否设置了关键词验证

## 📊 监控和日志

### 查看 GitHub Actions 日志

1. 进入仓库 `Actions` 标签
2. 点击对应的工作流运行记录
3. 查看每个步骤的详细日志

### 日志级别

- `DEBUG` - 详细调试信息
- `INFO` - 一般信息（默认）
- `WARNING` - 警告信息
- `ERROR` - 错误信息

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📮 联系方式

如有问题，请提交 Issue。

---

⭐ 如果这个项目对你有帮助，请给个 Star！