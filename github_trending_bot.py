#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Trending 每日推送机器人
功能：每日爬取 GitHub Trending，使用硅基流动 AI 总结，通过飞书机器人推送
部署：GitHub Actions 定时任务（每天早上 8 点）
"""

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from datetime import datetime
import json
import re
import sys

# ==============================================================================
# 配置区域 - 通过环境变量读取
# ==============================================================================

import os

# 硅基流动 API 配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3")
SILICONFLOW_TIMEOUT = int(os.getenv("SILICONFLOW_TIMEOUT", "60"))

# 飞书机器人配置
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
FEISHU_EXTRA_WEBHOOK_URLS = os.getenv("FEISHU_EXTRA_WEBHOOK_URLS", "")
FEISHU_MESSAGE_TYPE = "interactive"  # 使用富文本卡片

# GitHub Trending 配置
GITHUB_TRENDING_URL = "https://github.com/trending"
GITHUB_SINCE = os.getenv("GITHUB_SINCE", "daily")  # daily, weekly, monthly
GITHUB_LANGUAGE = os.getenv("GITHUB_LANGUAGE", "")  # 空字符串表示所有语言

# 爬虫配置
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # 请求超时时间（秒）
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))  # 最大重试次数
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))  # 重试间隔（秒）

# 日志配置
LOG_ENABLED = os.getenv("LOG_ENABLED", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR

# ==============================================================================
# 环境变量验证
# ==============================================================================

def validate_env():
    """验证必要的环境变量是否配置"""
    errors = []

    if not SILICONFLOW_API_KEY:
        errors.append("未配置 SILICONFLOW_API_KEY 环境变量")

    if not FEISHU_WEBHOOK_URL.strip():
        errors.append("未配置 FEISHU_WEBHOOK_URL 环境变量")

    if errors:
        log("环境变量配置错误：", "ERROR")
        for error in errors:
            log(f"  - {error}", "ERROR")
        log("请检查 GitHub Secrets 配置", "ERROR")
        sys.exit(1)

    log("环境变量验证通过")

# ==============================================================================
# 工具函数
# ==============================================================================

def log(message, level="INFO"):
    """输出日志"""
    if LOG_ENABLED:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}", flush=True)

def format_number(num_str):
    """格式化数字（例如：1.2k -> 1200）"""
    num_str = num_str.strip()
    if not num_str:
        return 0

    num_str = num_str.replace(',', '').replace('k', '000').replace('K', '000')

    try:
        # 处理小数点，例如：1.2k -> 1200
        if '.' in num_str:
            parts = num_str.split('.')
            if len(parts) == 2 and parts[1] == '000':
                return int(float(num_str))
        return int(num_str)
    except:
        return 0

def format_stars(stars):
    """格式化星数显示"""
    if stars >= 1000:
        return f"{stars / 1000:.1f}k"
    return str(stars)

# ==============================================================================
# 爬虫模块 - GitHub Trending
# ==============================================================================

class GitHubTrendingCrawler:
    """GitHub Trending 爬虫"""

    def __init__(self):
        self.url = GITHUB_TRENDING_URL
        self.since = GITHUB_SINCE
        self.language = GITHUB_LANGUAGE
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def fetch_readme(self, repo_url):
        """获取项目的 README.md 内容"""
        readme_urls = [
            f"{repo_url}/blob/main/README.md",
            f"{repo_url}/blob/master/README.md"
        ]

        for readme_url in readme_urls:
            try:
                response = requests.get(readme_url, headers=self.headers, timeout=20)
                response.raise_for_status()

                # 解析 HTML 提取 README 内容
                soup = BeautifulSoup(response.text, 'lxml')
                readme_div = soup.find('div', {'data-testid': 'raw-content'}) or soup.find('article')

                if readme_div:
                    return readme_div.get_text().strip()[:5000]  # 限制长度

            except Exception as e:
                log(f"获取 README 失败 {readme_url}：{str(e)}", "DEBUG")
                continue

        return ""

    def fetch_trending(self):
        """爬取 GitHub Trending 数据"""
        log("开始爬取 GitHub Trending...")

        for attempt in range(self.max_retries):
            try:
                params = {'since': self.since}
                if self.language:
                    params['language'] = self.language

                log(f"网页爬取（尝试 {attempt + 1}/{self.max_retries}）...")

                response = requests.get(
                    self.url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout
                )
                response.raise_for_status()

                repos = self._parse_html(response.text)
                log(f"成功爬取 {len(repos)} 个仓库")
                return repos

            except requests.exceptions.Timeout:
                log(f"请求超时（尝试 {attempt + 1}/{self.max_retries}）", "ERROR")
            except requests.exceptions.ConnectionError:
                log(f"连接失败（尝试 {attempt + 1}/{self.max_retries}）", "ERROR")
            except Exception as e:
                log(f"爬取失败（尝试 {attempt + 1}/{self.max_retries}）：{str(e)}", "ERROR")

            # 最后一次尝试不等待
            if attempt < self.max_retries - 1:
                import time
                # 指数退避策略
                wait_time = self.retry_delay * (2 ** attempt)
                log(f"等待 {wait_time} 秒后重试...", "INFO")
                time.sleep(wait_time)

        log("所有爬取尝试均失败", "ERROR")
        return []

    def _parse_html(self, html):
        """解析 HTML 提取仓库信息"""
        soup = BeautifulSoup(html, 'lxml')
        repos = []

        repo_articles = soup.find_all('article', class_='Box-row')

        for article in repo_articles:
            try:
                repo = self._extract_repo_info(article)
                if repo:
                    repos.append(repo)
            except Exception as e:
                log(f"解析仓库信息失败：{str(e)}", "WARNING")
                continue

        return repos

    def _extract_repo_info(self, article):
        """提取单个仓库的信息"""
        # 仓库名称和链接
        title_element = article.find('h2', class_='h3')
        if not title_element:
            return None

        link_element = title_element.find('a')
        if not link_element:
            return None

        repo_name = link_element.get_text().strip().replace('\n', '').replace(' ', '')
        repo_url = 'https://github.com' + link_element.get('href', '')

        # 提取作者和项目名
        if '/' in repo_name:
            parts = repo_name.split('/')
            author = parts[0]
            project_name = parts[1] if len(parts) > 1 else repo_name
        else:
            author = ""
            project_name = repo_name

        # 描述
        desc_element = article.find('p', class_='col-9')
        description = desc_element.get_text().strip() if desc_element else ""

        # 编程语言
        language_element = article.find('span', itemprop='programmingLanguage')
        language = language_element.get_text().strip() if language_element else ""

        # 星数
        stars_element = article.find('a', href=lambda x: x and '/stargazers' in x)
        stars = 0
        if stars_element:
            stars_text = stars_element.get_text().strip()
            stars = format_number(stars_text)

        # Fork 数
        forks_element = article.find('a', href=lambda x: x and '/forks' in x)
        forks = 0
        if forks_element:
            forks_text = forks_element.get_text().strip()
            forks = format_number(forks_text)

        # 今日星数增长
        today_stars_element = article.find('span', class_='d-inline-block float-sm-right')
        today_stars = 0
        if today_stars_element:
            today_stars_text = today_stars_element.get_text().strip()
            if 'stars today' in today_stars_text:
                today_stars = format_number(today_stars_text.split('stars')[0].strip())

        return {
            'name': repo_name,
            'author': author,
            'project_name': project_name,
            'url': repo_url,
            'description': description,
            'language': language,
            'stars': stars,
            'forks': forks,
            'today_stars': today_stars,
            'formatted_stars': format_stars(stars),
            'formatted_today_stars': format_stars(today_stars)
        }
# ==============================================================================
# AI 分析模块 - 硅基流动 API
# ==============================================================================

class SiliconFlowSummarizer:
    """硅基流动 AI 分析器"""
    
    def __init__(self):
        self.api_key = SILICONFLOW_API_KEY
        self.base_url = SILICONFLOW_BASE_URL
        self.model = SILICONFLOW_MODEL
        self.timeout = SILICONFLOW_TIMEOUT
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
    
    def analyze_project(self, repo, readme_content=""):
        """对单个项目进行分析：润色描述 + 生成亮点"""
        log(f"正在分析项目: {repo['name']}")
        
        prompt = self._build_prompt(repo, readme_content)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个技术分析师，擅长用简洁的中文总结 GitHub 项目。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            result = response.choices[0].message.content
            parsed = self._parse_result(result)
            log(f"项目 {repo['name']} 分析完成")
            return parsed
            
        except Exception as e:
            log(f"项目分析失败 {repo['name']}：{str(e)}", "ERROR")
            return {
                'chinese_description': repo['description'][:100] if repo['description'] else "暂无描述",
                'highlight': "值得关注的开源项目"
            }
    
    def analyze_repos(self, repos, limit=10, crawler=None):
        """批量分析项目"""
        log(f"开始批量分析 {len(repos)} 个项目...")
        
        # 只分析前 N 个项目
        repos_to_analyze = repos[:limit]
        
        for repo in repos_to_analyze:
            # 获取 README 内容
            readme_content = ""
            if crawler:
                readme_content = crawler.fetch_readme(repo['url'])
            
            # 分析项目
            repo['ai_analysis'] = self.analyze_project(repo, readme_content)
        
        log(f"批量分析完成，共分析 {len(repos_to_analyze)} 个项目")
        return repos_to_analyze
    
    def _build_prompt(self, repo, readme_content):
        """构建分析 prompt"""
        prompt = f"""请分析以下 GitHub 项目：

项目名称: {repo['name']}
作者: {repo['author']}
编程语言: {repo['language']}
Star 数: {repo['stars']}
项目描述: {repo['description']}

"""
        
        if readme_content:
            prompt += f"README 内容（部分）:\n{readme_content[:2000]}\n\n"
        
        prompt += """请完成以下两个任务：

1. **润色描述**：将原英文描述润色并翻译成中文，保留核心信息，表达简洁易懂
2. **生成亮点**：基于项目信息，用一句话概括项目的亮点或特色

请按以下 JSON 格式返回：
{
  "chinese_description": "润色的中文描述",
  "highlight": "一句话的项目亮点"
}

注意：
- 描述要简洁，不超过 100 字
- 亮点要突出，不超过 50 字
- 只返回 JSON，不要其他内容
"""
        return prompt
    
    def _parse_result(self, result_text):
        """解析 AI 返回的结果"""
        try:
            # 尝试提取 JSON
            start_idx = result_text.find('{')
            if start_idx != -1:
                stack = []
                end_idx = start_idx
                for i in range(start_idx, len(result_text)):
                    char = result_text[i]
                    if char == '{':
                        stack.append(char)
                    elif char == '}':
                        if stack:
                            stack.pop()
                            if not stack:
                                end_idx = i + 1
                                break
                
                if end_idx > start_idx:
                    json_str = result_text[start_idx:end_idx]
                    parsed = json.loads(json_str)
                    if 'chinese_description' in parsed and 'highlight' in parsed:
                        return parsed
        except:
            pass
        
        # 如果解析失败，尝试从文本中提取
        lines = result_text.split('\n')
        chinese_desc = ""
        highlight = ""
        
        for line in lines:
            if '润色描述' in line or 'chinese_description' in line:
                chinese_desc = line.split('：')[-1].split(':')[-1].strip()
            elif '亮点' in line or 'highlight' in line:
                highlight = line.split('：')[-1].split(':')[-1].strip()
        
        if not chinese_desc:
            chinese_desc = result_text[:100]
        if not highlight:
            highlight = "值得关注的项目"
        
        return {
            'chinese_description': chinese_desc,
            'highlight': highlight
        }

# ==============================================================================
# 美化模块 - AgentSkills frontend-design
# ==============================================================================

class AgentSkillsBeautifier:
    """AgentSkills 内容美化器"""
    
    def __init__(self):
        self.enabled = True
    
    def beautify(self, repos):
        """使用 AgentSkills 进行内容美化"""
        log("开始使用 AgentSkills 进行内容美化...")
        
        try:
            # 构建 Markdown 格式的美化内容
            date = datetime.now().strftime("%Y-%m-%d")
            
            # 构建 Markdown 内容
            markdown_content = self._build_markdown(repos, date)
            
            log("内容美化完成")
            return markdown_content
            
        except Exception as e:
            log(f"内容美化失败：{str(e)}", "ERROR")
            # 返回降级方案
            return self._fallback_beautify(repos)
    
    def _build_markdown(self, repos, date):
        """构建 Markdown 格式的内容"""
        lines = []
        
        # 标题（带日期）
        lines.append(f"# 🚀 GitHub 热榜日报 - {date}")
        lines.append("")
        
        # 按顺序展示所有项目
        for i, repo in enumerate(repos, 1):
            lines.append(self._build_repo_card(repo, i))
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_repo_card(self, repo, index):
        """构建单个项目的卡片"""
        lines = []
        
        # 项目标题
        lines.append(f"{index}. **[{repo['name']}]({repo['url']})**")
        
        # 基本信息分行显示
        language_emoji = self._get_language_emoji(repo['language'])
        lines.append(f"⭐ **{repo['formatted_stars']}** stars")
        lines.append(f"{language_emoji} **{repo['language']}**")
        lines.append(f"📈 **+{repo['formatted_today_stars']}** today")
        
        # AI 分析信息
        ai_analysis = repo.get('ai_analysis', {})
        
        # 润色的中文描述
        chinese_desc = ai_analysis.get('chinese_description', '')
        if chinese_desc:
            lines.append(chinese_desc)
        
        return "\n".join(lines)
    
    def _get_language_emoji(self, language):
        """获取编程语言的 emoji"""
        emoji_map = {
            'Python': '🐍',
            'JavaScript': '📜',
            'TypeScript': '📘',
            'Java': '☕',
            'Go': '🐹',
            'Rust': '🦀',
            'C++': '⚡',
            'C': '🔧',
            'PHP': '🐘',
            'Ruby': '💎',
            'Swift': '🦉',
            'Kotlin': '🎯',
            'Dart': '🎯',
            'HTML': '🌐',
            'CSS': '🎨',
            'Vue': '💚',
            'React': '⚛️',
            'Angular': '🅰️',
            'Shell': '💻',
            'Jupyter Notebook': '📓',
        }
        return emoji_map.get(language, '💻')
    
    def _fallback_beautify(self, repos):
        """降级美化方案"""
        date = datetime.now().strftime("%Y-%m-%d")
        
        content = f"🚀 GitHub 热榜日报 - {date}\n\n"
        
        for i, repo in enumerate(repos[:10], 1):
            content += f"{i}. [{repo['name']}]({repo['url']}) by {repo['author']}\n"
            content += f"   ⭐ {repo['formatted_stars']} stars\n"
            content += f"   {self._get_language_emoji(repo['language'])} {repo['language']}\n"
            content += f"   📈 +{repo['formatted_today_stars']} today\n"
            content += "\n"
        
        content += f"---\n📊 数据来源：https://github.com/trending\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return content

# ==============================================================================
# 飞书推送模块
# ==============================================================================

class FeishuNotifier:
    """飞书机器人通知器"""
    
    def __init__(self):
        self.webhook_url = FEISHU_WEBHOOK_URL
        # 主机器人始终排在第一位；可选机器人支持逗号或换行分隔。
        candidates = [self.webhook_url] + re.split(r"[,\r\n]", FEISHU_EXTRA_WEBHOOK_URLS)
        self.webhook_urls = list(dict.fromkeys(
            url.strip() for url in candidates if url.strip()
        ))
        self.message_type = FEISHU_MESSAGE_TYPE
    
    def send(self, content):
        """构建一次消息，独立推送所有机器人；任一失败则返回 False。"""
        log("开始发送飞书消息...")
        
        try:
            if self.message_type == "interactive":
                # 发送富文本卡片
                data = self._build_card_message(content)
            else:
                # 发送文本消息
                data = {
                    "msg_type": "text",
                    "content": {
                        "text": content
                    }
                }
            
        except Exception:
            log("飞书消息构建失败", "ERROR")
            return False

        if not self.webhook_urls:
            log("未配置飞书推送目标", "ERROR")
            return False

        succeeded = 0
        for index, webhook_url in enumerate(self.webhook_urls, 1):
            if self._send_one(webhook_url, data, index):
                succeeded += 1

        total = len(self.webhook_urls)
        success = succeeded == total
        log(f"飞书推送完成：成功 {succeeded}/{total}，失败 {total - succeeded}",
            "INFO" if success else "ERROR")
        return success

    def _send_one(self, webhook_url, data, index):
        """日志仅包含目标序号，避免泄露 URL、异常详情或服务端响应。"""
        try:
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('StatusCode') == 0 or result.get('code') == 0:
                log(f"飞书目标 {index} 发送成功")
                return True
            else:
                log(f"飞书目标 {index} 发送失败：业务状态未成功", "ERROR")
                return False
                
        except Exception:
            # requests 异常可能包含完整 Webhook URL，响应体也不可信。
            log(f"飞书目标 {index} 发送失败：请求或响应异常", "ERROR")
            return False
    
    def _build_card_message(self, markdown_content):
        """构建富文本卡片消息"""
        # 解析 Markdown 内容
        lines = markdown_content.split('\n')
        
        # 提取标题
        title = "🚀 GitHub 热榜日报"
        
        # 构建卡片元素
        elements = []
        
        # 简化内容：只显示前 5 个项目 + 底部信息
        simplified_lines = self._simplify_content(lines, max_repos=5)
        
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "\n".join(simplified_lines)
            }
        })
        
        # 构建完整消息
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": elements
        }
        
        return {
            "msg_type": "interactive",
            "card": card
        }
    
    def _simplify_content(self, lines, max_repos=5):
        """简化内容，只显示前 N 个项目"""
        simplified = []
        repo_count = 0
        
        for line in lines:
            # 保留标题
            if line.startswith('#'):
                simplified.append(line)
            # 保留分隔线
            elif line.startswith('---'):
                simplified.append(line)
            # 统计项目数量
            elif line.startswith('###'):
                if repo_count >= max_repos:
                    continue
                repo_count += 1
                simplified.append(line)
            # 保留项目内容
            elif repo_count <= max_repos:
                simplified.append(line)
        
        if repo_count > max_repos:
            simplified.append(f"\n...还有更多项目")
        
        return simplified

# ==============================================================================
# 主程序
# ==============================================================================

def main():
    """主程序入口"""
    log("=" * 60)
    log("GitHub Trending 每日推送机器人启动")
    log("=" * 60)

    # 验证环境变量
    validate_env()

    try:
        # 1. 爬取 GitHub Trending
        crawler = GitHubTrendingCrawler()
        repos = crawler.fetch_trending()
        
        if not repos:
            log("未获取到仓库数据，程序终止", "ERROR")
            sys.exit(1)
        
        # 2. AI 分析（Top 10，传入 crawler 以获取 README）
        summarizer = SiliconFlowSummarizer()
        analyzed_repos = summarizer.analyze_repos(repos, limit=10, crawler=crawler)
        
        # 3. 内容美化
        beautifier = AgentSkillsBeautifier()
        beautified_content = beautifier.beautify(analyzed_repos)
        
        # 4. 飞书推送
        notifier = FeishuNotifier()
        success = notifier.send(beautified_content)
        
        if success:
            log("=" * 60)
            log("✅ GitHub Trending 推送成功！")
            log("=" * 60)
            sys.exit(0)
        else:
            log("=" * 60)
            log("❌ GitHub Trending 推送失败！")
            log("=" * 60)
            sys.exit(1)
            
    except Exception as e:
        log(f"程序执行出错：{str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
