# 考勤数据处理平台

GUS 考勤排班数据分析全流程 Web 平台。上传 Excel 文件 → 自动清洗/计算/分析 → 生成交互式 HTML 报告。

## 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js 前端 │────▶│ FastAPI 后端  │────▶│   Supabase   │
│  (Vercel)    │◀────│  (Railway)   │     │  (托管DB)     │
└──────────────┘     └──────────────┘     └──────────────┘
        │                    │
        │  文件上传           │  Pandas 数据处理
        │  进度轮询           │  指标计算 + 透视分析
        │  报告查看           │  HTML 报告生成
```

## 目录结构

```
attendance-platform/
├── frontend/                    # Next.js 15 前端
│   ├── src/
│   │   ├── app/                 # 页面路由
│   │   ├── components/          # 组件
│   │   │   ├── FileUpload.tsx    # 文件上传（拖拽+多文件）
│   │   │   ├── ProcessingStatus.tsx # 处理进度条
│   │   │   └── ReportViewer.tsx  # 结果卡片
│   │   └── lib/
│   │       ├── api.ts           # FastAPI 客户端
│   │       └── supabase.ts      # Supabase 直读
│   └── ...
├── backend/                     # FastAPI Python 后端
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── models/schemas.py    # Pydantic 数据模型
│   │   ├── routers/             # API 路由
│   │   │   ├── files.py         # 文件上传
│   │   │   ├── pipeline.py      # 处理流程
│   │   │   └── reports.py       # 报告查询
│   │   └── services/
│   │       ├── pipeline_runner.py  # Pipeline 封装
│   │       └── supabase_service.py # Supabase 交互
│   └── ...
└── supabase/                    # 数据库 Schema
    └── migrations/
        └── 001_initial_schema.sql
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/files/upload` | 上传 Excel 文件（multipart） |
| `POST` | `/api/v1/process/start` | 启动数据处理 |
| `GET` | `/api/v1/process/{sid}/status` | 查询处理进度 |
| `GET` | `/api/v1/process/{sid}/result` | 获取处理结果摘要 |
| `GET` | `/api/v1/reports/{sid}/html` | 查看 HTML 报告 |
| `GET` | `/api/v1/reports/{sid}/json` | 获取报告 JSON |
| `GET` | `/api/v1/reports/history` | 处理历史列表 |

## 本地开发

### 1. 配置环境变量

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# 填入 Supabase URL 和 keys
```

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 3. 启动服务

```bash
# 后端 (端口 8000)
cd backend
uvicorn app.main:app --reload

# 前端 (端口 3000)
cd frontend
npm run dev
```

### 4. Docker 部署

```bash
docker-compose up -d
```

## 部署方案

| 组件 | 平台 | 说明 |
|------|------|------|
| 前端 | Vercel | 静态托管，配置环境变量 |
| 后端 | Railway / Render | Docker 容器，需持久化存储挂载 |
| 数据库 | Supabase | 托管 PostgreSQL |
| Pipeline | 后端内嵌 | 复用现有 attendance-pipeline 脚本 |

## 数据流程

```
上传 9 类 Excel → 自动文件类型识别 → 创建会话
  → 步骤1: 数据清洗（剔除离职/未入职/GL00/GUS白名单）
  → 步骤2: 指标计算（HUB/排班正确/缺卡/日超8H）
  → 步骤3: 透视分析（5个Sheet Excel）
  → 步骤4a: 构建报告JSON
  → 步骤4b: 生成HTML报告（含Chart.js图表+穿透明细）
  → 结果写入 Supabase
```

## 技术栈

- **前端**: Next.js 15 + TypeScript + Tailwind CSS + Lucide Icons
- **后端**: FastAPI + Pandas + OpenPyXL
- **数据库**: Supabase (PostgreSQL)
- **部署**: Vercel + Railway + Docker
- **Pipeline**: 复用现有 attendance-pipeline（Python + Pandas）
