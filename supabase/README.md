# 考勤数据处理平台 — Supabase 配置

## 前置条件

1. 在 [supabase.com](https://supabase.com) 创建项目
2. 获取项目 URL 和 Service Key
3. 在 SQL Editor 中执行 `supabase/migrations/001_initial_schema.sql`

## 环境变量

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 表结构

| 表名 | 用途 |
|------|------|
| processing_sessions | 处理会话记录 |
| uploaded_files | 上传文件追踪 |
| reports | 报告 JSON 数据 |
| attendance_data | 考勤明细（清洗后） |
| metric_summaries | 部门指标汇总 |
