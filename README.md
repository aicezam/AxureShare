# Axure Share

基于 Flask 的 Axure 原型分享平台，支持原型文件上传、多角色账号管理、AI对话答疑等功能。

## 功能特性

- 用户认证与权限管理
- Axure 原型文件上传与管理
- AI 智能答疑对话（内嵌向量数据库），需设置规则元件关键词（元件命名）
- 支持多角色账号简易权限管理
- 支持自动渲染markdown元件，需将该元件命名为`MDAS`
- 原型分享，支持公开、密码保护分享、私有模式
- **浏览器插件**：支持 [Edge 插件](https://microsoftedge.microsoft.com/addons/detail/axureshare-%E4%B8%8A%E4%BC%A0%E5%8A%A9%E6%89%8B/cngakhhemhjeeifiknbpjobbilonckgi) 预览 Axure 时快速上传到托管平台

## 技术栈

- **后端**：Flask 3.1.2
- **数据库**：SQLAlchemy (SQLite)
- **用户认证**：Flask-Login
- **表单处理**：Flask-WTF
- **数据库迁移**：Flask-Migrate (Alembic)
- **AI 集成**：支持OPENAI协议的多种 AI API (SiliconFlow、小米Mimo等)
- **向量检索**：BAAI/bge-m3 嵌入模型

## 项目结构

```
axure.share/
├── app/
│   ├── services/          # 业务逻辑层
│   ├── utils/             # 工具函数
│   ├── models.py          # 数据模型
│   ├── routes.py          # 路由定义
│   ├── forms.py           # 表单定义
│   ├── permissions.py     # 权限控制
│   ├── config.py          # 配置构建
│   └── app_factory.py     # 应用工厂
├── migrations/            # 数据库迁移文件
├── static/                # 静态资源
├── templates/             # Jinja2 模板
├── uploads/               # 上传文件目录
├── instance/              # 数据库实例目录
├── .env.example           # 环境变量示例
├── requirements.txt       # Python 依赖
└── app.py                 # 应用入口
```

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd axure.share
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并配置相关参数：

```bash
cp .env.example .env
```

主要配置项说明：

| 配置项 | 说明 |
|--------|------|
| `SECRET_KEY` | Flask 秘钥密钥 |
| `SQLALCHEMY_DATABASE_URI` | 数据库连接 URI |
| `MAIN_AI_API_KEY` | 主 AI API 密钥 |
| `MAIN_AI_BASE_URL` | 主 AI API 地址 |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 |
| `EMBEDDING_MODEL` | 嵌入模型名称 |

### 5. 数据库初始化

```bash
flask db upgrade
```

### 6. 运行应用

```bash
python app.py
```

访问 `http://localhost:7855` 即可使用。

## 管理命令

### 创建管理员用户

```bash
flask admin create-admin
```

### 数据库迁移

```bash
# 生成迁移脚本
flask db migrate -m "commit message"

# 执行迁移
flask db upgrade
```

## 环境要求

- Python 3.10+
- SQLite 3

## 许可证

MIT License
