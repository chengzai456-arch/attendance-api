# 考勤平台项目交接文档

**文档版本**: v1.0  
**更新日期**: 2026-07-02  
**项目负责人**: -  
**接手人**: -  

---

## 📋 项目概述

### 项目名称
考勤数据处理平台（Attendance Platform）

### 项目简介
自动化处理考勤 Excel 数据的 Web 应用，支持：
- 上传 9 类考勤相关 Excel 文件
- 自动执行数据清洗、指标计算、透视分析
- 生成 3 个处理后的 Excel 报表
- 历史记录查询和文件下载

### 技术栈
- **前端**: Next.js 15 + React 19 + TypeScript + Tailwind CSS
- **后端**: FastAPI (Python 3.11) + Docker
- **数据库**: Supabase (PostgreSQL)
- **文件存储**: Supabase Storage
- **部署**: Vercel (前端) + Render (后端)

---

## 🏗️ 系统架构

```
┌─────────────────┐
│   用户浏览器     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌──────────────────┐
│  Vercel (前端)   │ ◄────► │  Render (后端)    │
│  Next.js 15     │         │  FastAPI         │
│  frontend-...   │         │  attendance-api  │
└─────────────────┘         └────────┬─────────┘
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
                ┌──────────────┐         ┌──────────────┐
                │  Supabase DB │         │  Supabase    │
                │  (历史记录)   │         │  Storage     │
                │              │         │  (Excel文件)  │
                └──────────────┘         └──────────────┘
```

---

## 🚀 部署信息

### 1. 前端（Vercel）

| 项目 | 信息 |
|------|------|
| **部署平台** | Vercel |
| **生产地址** | https://frontend-one-gilt-68.vercel.app |
| **GitHub 仓库** | 需要确认（本地路径：`attendance-platform/frontend`） |
| **环境变量** | `NEXT_PUBLIC_API_URL=https://attendance-api-d4qh.onrender.com` |

#### 部署步骤
```bash
# 1. 进入前端目录
cd attendance-platform/frontend

# 2. 安装依赖
npm install

# 3. 本地开发
npm run dev

# 4. 部署到 Vercel
vercel --prod
```

#### Vercel 环境变量配置
在 [Vercel Dashboard](https://vercel.com/dashboard) → 项目 → Settings → Environment Variables 添加：
```
NEXT_PUBLIC_API_URL=https://attendance-api-d4qh.onrender.com
```

---

### 2. 后端（Render）

| 项目 | 信息 |
|------|------|
| **部署平台** | Render |
| **生产地址** | https://attendance-api-d4qh.onrender.com |
| **GitHub 仓库** | https://github.com/chengzai456-arch/attendance-api |
| **服务类型** | Docker |
| **计划** | Starter ($7/月) |
| **磁盘** | 1GB (`/app/data`) |

#### 环境变量配置
在 [Render Dashboard](https://dashboard.render.com) → `attendance-api` 服务 → Environment 添加：

| 变量名 | 说明 | 获取方式 |
|--------|------|---------|
| `SUPABASE_URL` | Supabase 项目 URL | Supabase Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key | Supabase Dashboard → Project Settings → API → `service_role` key (⚠️ 保密) |
| `CORS_ORIGINS` | 允许的前端域名 | `https://frontend-one-gilt-68.vercel.app,http://localhost:3000` |
| `APP_ENV` | 环境标识 | `production` |
| `DATA_DIR` | 数据存储路径 | `/app/data` |
| `PIPELINE_DIR` | Pipeline 脚本路径 | `/app/pipeline` |

**⚠️ 重要**：`SUPABASE_SERVICE_KEY` 必须使用 `service_role` key，不能使用 `anon` key，否则 Storage 上传会失败。

---

### 3. 数据库（Supabase）

| 项目 | 信息 |
|------|------|
| **平台** | Supabase |
| **项目 URL** | https://dgajqndakknhttbkhveq.supabase.co |
| **项目 ID** | `dgajqndakknhttbkhveq` |
| **区域** | 需要确认 |
| **免费计划限制** | 500MB 数据库，1GB Storage，2GB 带宽/月 |

#### 数据库表结构

**表名**: `processing_sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | text (PK) | 会话 ID (格式: `YYYYMMDD_HHMMSS_随机6位`) |
| `status` | text | 状态: `uploaded` / `processing` / `completed` / `failed` |
| `filename` | text | 主要文件名（花名册） |
| `file_count` | integer | 上传文件数量 |
| `created_at` | timestamp | 创建时间 |
| `updated_at` | timestamp | 更新时间 |
| `completed_at` | timestamp | 完成时间 |
| `error` | text | 错误信息（失败时） |
| `summary` | jsonb | 处理摘要（成功后） |

#### Supabase Storage Bucket

**Bucket 名称**: `attendance-results`

**目录结构**:
```
attendance-results/
├── uploads/
│   └── {session_id}/
│       ├── 原始数据 (2).xlsx
│       ├── 花名册 (46).xlsx
│       └── ...
└── results/
    └── {session_id}/
        ├── 清洗后数据.xlsx
        ├── 指标计算后数据.xlsx
        └── 透视分析.xlsx
```

---

## 📁 项目结构

```
attendance-platform/
├── frontend/                      # 前端（Next.js）
│   ├── src/
│   │   ├── components/           # React 组件
│   │   │   ├── FileUpload.tsx    # 文件上传组件
│   │   │   ├── ProcessStatus.tsx # 处理状态组件
│   │   │   └── ReportViewer.tsx  # 历史记录组件
│   │   ├── lib/
│   │   │   └── api.ts           # API 调用封装
│   │   └── pages/
│   │       ├── index.tsx        # 首页
│   │       └── api/             # API 路由（如有）
│   ├── .env.local               # 环境变量（本地）
│   └── package.json
│
└── backend/                       # 后端（FastAPI）
    ├── app/
    │   ├── main.py              # FastAPI 入口
    │   ├── config.py            # 配置管理
    │   ├── models/              # 数据模型
    │   ├── routers/             # API 路由
    │   │   └── pipeline.py      # 处理相关接口
    │   ├── services/            # 业务逻辑
    │   │   ├── pipeline_runner.py  # Pipeline 执行器
    │   │   ├── supabase_service.py # Supabase 服务
    │   │   └── file_manager.py  # 文件管理
    │   └── utils/
    │       └── file_manager.py  # 文件识别与匹配
    ├── pipeline/                 # 数据处理脚本
    │   ├── main.py             # Pipeline 入口
    │   ├── clean.py            # 数据清洗
    │   ├── metrics.py          # 指标计算
    │   └── pivot.py            # 透视分析
    ├── Dockerfile              # Docker 配置
    ├── render.yaml             # Render 部署配置
    ├── requirements.txt        # Python 依赖
    └── .env                    # 环境变量（本地，不提交）
```

---

## 🔧 核心功能说明

### 1. 文件上传

**支持的文件类型**（9个）：

| 文件类型 | 关键词 | 说明 |
|---------|--------|------|
| 花名册 | 花名册 | 员工名单（必需） |
| 原始数据 | 原始数据 | 考勤原始记录 |
| 离职流程 | 离职 | 离职员工列表 |
| 班次 | 班次 | 排班信息 |
| 补签管理 | 补签 | 补签记录 |
| 签字报表-本周 | 签字报表（无括号） | 本周签字数据 |
| 签字报表-上周 | 签字报表(2) | 上周签字数据 |
| 签字报表-双周 | 签字报表(1) | 双周签字数据 |
| 白名单 | 白名单、剔除 | 需剔除的人员列表 |

**文件识别逻辑**：
- 根据文件名关键词自动匹配文件类型
- 签字报表用括号序号区分：`(2)` = 上周，`(1)` = 双周，无括号 = 本周
- 匹配结果在前端实时显示

---

### 2. 数据处理流程

```
上传文件 → 保存到 Supabase Storage (uploads/{session_id}/)
   ↓
启动后台线程（threading.Thread）
   ↓
步骤1: 数据清洗（clean）
   ↓
步骤2: 指标计算（metrics）
   ↓
步骤3: 透视分析（pivot）
   ↓
生成 3 个 Excel 文件
   ↓
上传到 Supabase Storage (results/{session_id}/)
   ↓
更新数据库状态为 "completed"
   ↓
自动清理 30 天前的旧数据
```

**处理时间**: 约 15-30 秒

**输出文件**：
1. `清洗后数据.xlsx` - 清洗后的完整数据
2. `指标计算后数据.xlsx` - 包含排班正确性、缺卡、日超8H 等指标
3. `透视分析.xlsx` - 5 个 Sheet 的透视分析表

---

### 3. 历史记录与下载

- 所有处理记录保存在 Supabase 数据库
- 处理后的 Excel 文件保存在 Supabase Storage
- 前端可查看历史记录列表
- 点击已完成的任务可下载 3 个结果文件

---

## 🌐 API 接口文档

### 基础信息

- **基础 URL**: `https://attendance-api-d4qh.onrender.com`
- **API 前缀**: `/api/v1`
- **认证**: 无需认证（内部系统）

---

### 1. 文件上传

**接口**: `POST /api/v1/files/upload`

**请求**:
```bash
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/files/upload \
  -F "files=@原始数据.xlsx" \
  -F "files=@花名册.xlsx"
```

**响应**:
```json
{
  "session_id": "20260702_153000_abc123",
  "missing_files": [],
  "file_types": {
    "roster": "花名册 (46).xlsx",
    "raw_data": "原始数据 (2).xlsx",
    ...
  }
}
```

---

### 2. 启动处理

**接口**: `POST /api/v1/process/start`

**请求**:
```bash
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20260702_153000_abc123",
    "roster_index": 46
  }'
```

**响应**:
```json
{
  "session_id": "20260702_153000_abc123",
  "status": "processing",
  "message": "处理已开始"
}
```

---

### 3. 查询处理状态

**接口**: `GET /api/v1/process/{session_id}/status`

**请求**:
```bash
curl https://attendance-api-d4qh.onrender.com/api/v1/process/20260702_153000_abc123/status
```

**响应**:
```json
{
  "session_id": "20260702_153000_abc123",
  "status": "completed",
  "progress": 100,
  "summary": {
    "total_rows": 979,
    "steps_completed": ["clean", "metrics", "pivot"]
  }
}
```

---

### 4. 获取处理结果

**接口**: `GET /api/v1/process/{session_id}/result`

**请求**:
```bash
curl https://attendance-api-d4qh.onrender.com/api/v1/process/20260702_153000_abc123/result
```

**响应**:
```json
{
  "session_id": "20260702_153000_abc123",
  "status": "completed",
  "excel_files": [
    {
      "filename": "清洗后数据.xlsx",
      "url": "https://dgajqndakknhttbkhveq.supabase.co/storage/v1/object/public/attendance-results/results/20260702_153000_abc123/清洗后数据.xlsx",
      "size": 204800
    },
    ...
  ]
}
```

---

### 5. 历史记录

**接口**: `GET /api/v1/reports/history`

**请求**:
```bash
curl https://attendance-api-d4qh.onrender.com/api/v1/reports/history?limit=10&offset=0
```

**响应**:
```json
{
  "sessions": [
    {
      "id": "20260702_153000_abc123",
      "status": "completed",
      "filename": "花名册 (46).xlsx",
      "file_count": 9,
      "created_at": "2026-07-02T15:30:00",
      "completed_at": "2026-07-02T15:30:25"
    },
    ...
  ],
  "total": 50
}
```

---

### 6. 管理接口

#### 清理卡住的任务
```bash
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/admin/cleanup-stuck
```

#### 查询 Storage 使用情况
```bash
curl https://attendance-api-d4qh.onrender.com/api/v1/process/admin/storage-usage
```

#### 手动清理旧数据
```bash
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/admin/cleanup?days=30
```

#### 取消单个任务
```bash
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/{session_id}/cancel
```

---

## 🐛 常见问题排查

### 1. 文件上传后无法识别

**症状**: `missing_files` 数组不为空

**原因**:
- 文件名不包含关键词
- 签字报表文件名格式不对

**解决**:
- 检查文件名是否包含正确的关键词
- 签字报表需用括号区分：`(1)` = 双周，`(2)` = 上周，无括号 = 本周

---

### 2. 处理卡住（状态一直是 "processing"）

**症状**: 处理开始后，状态一直是 `processing`，超过 5 分钟

**原因**:
- 后台线程异常退出
- Render 实例重启

**解决**:
```bash
# 清理卡住的任务
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/admin/cleanup-stuck
```

---

### 3. 处理完成后无法下载文件

**症状**: 状态显示 `completed`，但没有可下载的文件

**原因**:
- Supabase Storage 上传失败
- `SUPABASE_SERVICE_KEY` 配置错误（使用了 `anon` key）

**排查**:
```bash
# 1. 检查 Storage 使用情况
curl https://attendance-api-d4qh.onrender.com/api/v1/process/admin/storage-usage

# 2. 检查具体会话的上传日志
curl https://attendance-api-d4qh.onrender.com/api/v1/process/{session_id}/upload-log

# 3. 诊断 Supabase Storage 连接
curl https://attendance-api-d4qh.onrender.com/api/v1/process/admin/debug-storage
```

**解决**:
- 确认 Render 环境变量中的 `SUPABASE_SERVICE_KEY` 是 `service_role` key
- 重新部署后端

---

### 4. Render 实例睡眠后文件丢失

**症状**: 处理完成后可以下载，但几小时后文件下载失败

**原因**:
- Render 免费计划会在 15 分钟无活动后睡眠
- 本地文件在实例重启后丢失
- 如果 Storage 上传失败，文件会彻底丢失

**解决**:
- 升级到 Render Starter 计划（$7/月），实例不会睡眠
- 确保 Storage 上传功能正常（参考问题 3）

---

### 5. Supabase 免费计划超标

**症状**: 上传文件或保存历史记录失败

**原因**:
- Storage 超过 1GB
- 数据库超过 500MB
- 带宽超过 2GB/月

**解决**:
```bash
# 1. 查询 Storage 使用情况
curl https://attendance-api-d4qh.onrender.com/api/v1/process/admin/storage-usage

# 2. 清理旧数据
curl -X POST https://attendance-api-d4qh.onrender.com/api/v1/process/admin/cleanup?days=7

# 3. 手动删除 Supabase Storage 中的旧文件
# 访问 Supabase Dashboard → Storage → 删除旧文件夹
```

---

## 🔐 环境变量清单

### 后端（Render）

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| `SUPABASE_URL` | ✅ | Supabase 项目 URL | `https://dgajqndakknhttbkhveq.supabase.co` |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service_role key | `eyJhbGciOi...` |
| `CORS_ORIGINS` | ✅ | 允许的前端域名（逗号分隔） | `https://frontend-xxx.vercel.app,http://localhost:3000` |
| `APP_ENV` | ❌ | 环境标识 | `production` |
| `DATA_DIR` | ❌ | 数据存储路径 | `/app/data` |
| `PIPELINE_DIR` | ❌ | Pipeline 脚本路径 | `/app/pipeline` |

### 前端（Vercel）

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| `NEXT_PUBLIC_API_URL` | ✅ | 后端 API 地址 | `https://attendance-api-d4qh.onrender.com` |

---

## 📊 监控与日志

### 健康检查

**接口**: `GET /health`

```bash
curl https://attendance-api-d4qh.onrender.com/health
```

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2026-07-02T15:30:00"
}
```

### 查看 Render 日志

1. 访问 [Render Dashboard](https://dashboard.render.com)
2. 点击 `attendance-api` 服务
3. 点击 "Logs" 标签
4. 查看实时日志

### 查看 Supabase 日志

1. 访问 [Supabase Dashboard](https://app.supabase.com)
2. 选择项目
3. 点击左侧 "Logs"
4. 查看数据库、Storage、API 日志

---

## 🔄 部署流程

### 后端部署（自动）

1. 推送代码到 GitHub `main` 分支
2. Render 自动检测并触发部署
3. 等待部署完成（约 5-10 分钟）
4. 访问 `https://attendance-api-d4qh.onrender.com/health` 确认部署成功

```bash
cd attendance-platform/backend
git add -A
git commit -m "描述本次更新"
git push origin main
```

### 前端部署（手动或自动）

#### 方式 1: Vercel CLI
```bash
cd attendance-platform/frontend
vercel --prod
```

#### 方式 2: Vercel Dashboard
1. 访问 [Vercel Dashboard](https://vercel.com/dashboard)
2. 导入 GitHub 仓库
3. 配置环境变量
4. 点击 "Deploy"

---

## 🚨 应急响应

### 服务不可用

**症状**: 前端或后端无法访问

**排查步骤**:
1. 检查 Vercel/Render 服务状态
2. 查看 Render 日志
3. 检查环境变量是否正确
4. 确认 Supabase 项目是否正常

**应急联系**:
- Render 状态页: https://status.render.com
- Vercel 状态页: https://vercel-status.com
- Supabase 状态页: https://status.supabase.com

---

### 数据丢失

**症状**: 历史记录或文件丢失

**原因**:
- Supabase 项目被删除
- Storage bucket 被清空

**恢复**:
- Supabase 有自动备份（免费计划 1 天，Pro 计划 7 天）
- 联系 Supabase 支持恢复备份

---

## 📝 维护清单

### 每日
- [ ] 检查服务是否正常运行
- [ ] 查看是否有卡住的处理任务

### 每周
- [ ] 检查 Storage 使用情况
- [ ] 清理不需要的历史记录

### 每月
- [ ] 检查 Supabase 免费计划使用量
- [ ] 查看 Render 账单
- [ ] 更新依赖包（如有安全漏洞）

---

## 📞 联系方式

| 角色 | 姓名 | 联系方式 |
|------|------|---------|
| 项目负责人 | - | - |
| 前端开发 | - | - |
| 后端开发 | - | - |
| DevOps | - | - |

---

## 📚 相关文档

- [FastAPI 文档](https://fastapi.tiangolo.com)
- [Next.js 文档](https://nextjs.org/docs)
- [Supabase 文档](https://supabase.com/docs)
- [Render 文档](https://render.com/docs)
- [Vercel 文档](https://vercel.com/docs)

---

## 📝 更新日志

### v1.0 (2026-07-02)
- 初始版本
- 包含完整的系统架构、部署信息、API 文档、常见问题排查

---

**文档结束**
