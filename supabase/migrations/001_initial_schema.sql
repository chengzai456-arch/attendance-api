-- ============================================
-- 考勤数据处理平台 - Supabase 数据库 Schema
-- ============================================

-- 处理会话表
CREATE TABLE IF NOT EXISTS processing_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    date TEXT,                          -- 考勤日期 "2026-06-29"
    status TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded/processing/completed/failed
    files_uploaded TEXT[] DEFAULT '{}', -- 上传文件名列表
    summary JSONB,                      -- 处理结果摘要 {total_people, scheduled_rate, ...}
    error TEXT,                         -- 错误信息
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 上传文件记录表
CREATE TABLE IF NOT EXISTS uploaded_files (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES processing_sessions(session_id) ON DELETE CASCADE,
    file_type TEXT NOT NULL,            -- raw_data/leave/roster/shift/...
    original_name TEXT NOT NULL,        -- 原始文件名
    mapped_name TEXT,                   -- 映射后的标准文件名
    file_size BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 报告数据表
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE REFERENCES processing_sessions(session_id) ON DELETE CASCADE,
    report_data JSONB NOT NULL,         -- report_data.json 完整内容
    report_html TEXT,                   -- HTML 报告内容（可选，较大）
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 考勤明细数据表（清洗后 - 大表）
CREATE TABLE IF NOT EXISTS attendance_data (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES processing_sessions(session_id) ON DELETE CASCADE,
    attendance_date TEXT,               -- 考勤日期
    employee_id TEXT,                   -- 工号
    employee_name TEXT,                 -- 姓名
    department_l2 TEXT,                 -- 二级部门
    department_l3 TEXT,                 -- 三级部门
    department_l4 TEXT,                 -- 四级部门
    department_l5 TEXT,                 -- 五级部门
    shift_name TEXT,                    -- 排班班次
    first_checkin TEXT,                 -- 首打卡
    last_checkin TEXT,                  -- 末打卡
    daily_hours TEXT,                   -- 每日工时
    is_schedule_correct TEXT,           -- 排班是否正确
    is_over_8h BOOLEAN,                 -- 是否超8H
    missing_punch_count INTEGER,        -- 缺卡数
    hub_label TEXT,                     -- HUB标记
    overtime_this_week NUMERIC,         -- 本周加班
    overtime_last_week NUMERIC,         -- 上周加班
    biweek_total_hours NUMERIC,         -- 双周累计工时
    resign_count INTEGER,               -- 补签数
    raw_data JSONB,                     -- 原始行数据（保留全部字段）
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 指标汇总表
CREATE TABLE IF NOT EXISTS metric_summaries (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES processing_sessions(session_id) ON DELETE CASCADE,
    department_l3 TEXT,                 -- 三级部门
    department_l4 TEXT,                 -- 四级部门
    total_people INTEGER,
    scheduled_count INTEGER,
    correct_count INTEGER,
    over_8h_count INTEGER,
    hub_count INTEGER,
    hub_correct_count INTEGER,
    checkin_rate NUMERIC,               -- 打卡率
    correct_rate NUMERIC,               -- 排班正确率
    scheduled_rate NUMERIC,             -- 排班率
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sessions_status ON processing_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON processing_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON processing_sessions(date);
CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance_data(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_data(attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance_data(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_dept ON attendance_data(department_l3);
CREATE INDEX IF NOT EXISTS idx_metrics_session ON metric_summaries(session_id);
CREATE INDEX IF NOT EXISTS idx_metrics_dept ON metric_summaries(department_l3);

-- RLS 策略（允许已认证用户读取）
ALTER TABLE processing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE metric_summaries ENABLE ROW LEVEL SECURITY;

-- 允许所有已认证用户读写
CREATE POLICY "authenticated_access" ON processing_sessions
    FOR ALL TO authenticated USING (true);

CREATE POLICY "authenticated_access" ON uploaded_files
    FOR ALL TO authenticated USING (true);

CREATE POLICY "authenticated_access" ON reports
    FOR ALL TO authenticated USING (true);

CREATE POLICY "authenticated_access" ON attendance_data
    FOR ALL TO authenticated USING (true);

CREATE POLICY "authenticated_access" ON metric_summaries
    FOR ALL TO authenticated USING (true);

-- 7天数据自动清理函数（保留最近7天的数据）
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    DELETE FROM attendance_data
    WHERE created_at < NOW() - INTERVAL '7 days';
    
    DELETE FROM metric_summaries
    WHERE created_at < NOW() - INTERVAL '7 days';
    
    DELETE FROM reports
    WHERE created_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- 如果已启用 pg_cron，则每6小时清理一次
-- SELECT cron.schedule('cleanup-attendance-data', '0 */6 * * *', 'SELECT cleanup_old_data();');
