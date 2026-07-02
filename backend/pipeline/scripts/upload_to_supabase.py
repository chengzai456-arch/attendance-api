"""
上传指标数据到 Supabase (attendance_data + attendance_trends)
输入: 指标计算后数据.xlsx (步骤2输出)
输出: Supabase 数据库写入 + upload_records 状态更新
特性: 仅保留最近 7 天数据，每次上传前自动清理超期数据

用法:
  python main.py upload --workspace ./output
  python main.py all ...  (自动调用)
"""
import os
import sys
import traceback
from datetime import date, datetime, timedelta

# 强制 UTF-8 输出
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import pandas as pd
import numpy as np

# Supabase 客户端（使用 service_role key 绕过 RLS）
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    print("⚠ 未安装 supabase-py，请运行: pip install supabase")
    SUPABASE_AVAILABLE = False

# ============================================================
# 数据保留策略
# ============================================================
DATA_RETENTION_DAYS = 7  # 仅保留最近 7 天的考勤数据


def get_supabase_client() -> Client | None:
    """从环境变量读取 Supabase 配置，创建客户端"""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("⚠ 环境变量未设置:")
        print("  SUPABASE_URL=https://xxx.supabase.co")
        print("  SUPABASE_SERVICE_ROLE_KEY=eyJ...")
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"⚠ Supabase 连接失败: {e}")
        return None


def cleanup_old_data(supabase: Client) -> dict:
    """
    清理超过 DATA_RETENTION_DAYS 天的考勤数据
    优先调用 PostgreSQL 函数，回退到直接 SQL
    """
    cutoff = (datetime.now() - timedelta(days=DATA_RETENTION_DAYS)).strftime('%Y-%m-%d')
    result = {'attendance_data': 0, 'attendance_trends': 0}

    # 方式 1: 调用数据库函数
    try:
        resp = supabase.rpc('cleanup_old_attendance_data').execute()
        if resp.data:
            for row in resp.data:
                key = row.get('table_name', '')
                count = row.get('deleted_count', 0)
                if key == 'attendance_data':
                    result['attendance_data'] = count
                elif key == 'attendance_trends':
                    result['attendance_trends'] = count
            return result
    except Exception:
        pass  # 函数不存在，回退到直接删除

    # 方式 2: 直接 DELETE（兜底）
    try:
        resp = supabase.table('attendance_data').delete().lt('date', cutoff).execute()
        result['attendance_data'] = len(resp.data) if resp.data else 0
    except Exception as e:
        print(f"  ⚠ attendance_data 清理失败: {e}")

    try:
        resp = supabase.table('attendance_trends').delete().lt('date', cutoff).execute()
        result['attendance_trends'] = len(resp.data) if resp.data else 0
    except Exception as e:
        print(f"  ⚠ attendance_trends 清理失败: {e}")

    return result


def _to_str(v):
    if pd.isna(v):
        return None
    return str(v).strip()


def _to_time(v):
    """将时间值转为 HH:MM:SS 字符串，失败返回 None"""
    if pd.isna(v):
        return None
    try:
        if hasattr(v, 'strftime'):
            return v.strftime('%H:%M:%S')
        s = str(v).strip()
        if ':' in s and len(s) >= 5:
            parts = s.split(':')
            if len(parts) == 2:
                return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
            return s
        return None
    except Exception:
        return None


def _to_bool(v):
    """转为布尔值"""
    if pd.isna(v):
        return None
    s = str(v).strip().lower()
    if s in ('是', 'true', '1', 'yes'):
        return True
    if s in ('否', 'false', '0', 'no', ''):
        return False
    return None


def _to_float(v):
    if pd.isna(v):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_int(v):
    if pd.isna(v):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _map_correct(v):
    """是否排班正确 → '正确' / '不正确' / '/' / None"""
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s in ('正确', '不正确', '/'):
        return s
    return None


def _parse_date(v):
    """解析日期值 → YYYY-MM-DD 字符串"""
    if pd.isna(v):
        return None
    try:
        if hasattr(v, 'strftime'):
            return v.strftime('%Y-%m-%d')
        s = str(v).strip()
        from datetime import datetime
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y'):
            try:
                d = datetime.strptime(s, fmt)
                return d.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None
    except Exception:
        return None


def run(config: dict):
    """
    主函数：读取指标数据 → 清理旧数据 → 上传到 Supabase
    
    config: pipeline 配置字典，包含 workspace、metrics_file 等路径
    """
    if not SUPABASE_AVAILABLE:
        print("❌ supabase-py 未安装，跳过上传")
        return

    supabase = get_supabase_client()
    if not supabase:
        print("❌ Supabase 客户端创建失败，跳过上传")
        return

    # ---- 0. 清理超过 7 天的旧数据 ----
    print(f"🧹 清理 {DATA_RETENTION_DAYS} 天前的旧数据...")
    try:
        cleanup_result = cleanup_old_data(supabase)
        del_a = cleanup_result.get('attendance_data', 0)
        del_t = cleanup_result.get('attendance_trends', 0)
        if del_a > 0 or del_t > 0:
            print(f"   已清理: attendance_data {del_a} 条, attendance_trends {del_t} 条")
        else:
            print(f"   无需清理（无超期数据）")
    except Exception as e:
        print(f"⚠ 清理失败（继续上传）: {e}")

    # ---- 1. 读取指标数据 ----
    metrics_file = config.get('metrics_file')
    if not metrics_file or not os.path.exists(metrics_file):
        print(f"❌ 指标文件不存在: {metrics_file}")
        print("   请先运行步骤2 (add_metrics)")
        return

    print(f"📖 读取指标数据: {metrics_file}")
    df = pd.read_excel(metrics_file, dtype=str)
    print(f"   共 {len(df)} 行, {len(df.columns)} 列")

    # ---- 2. 过滤：只保留最近 7 天的数据 ----
    cutoff_str = (datetime.now() - timedelta(days=DATA_RETENTION_DAYS)).strftime('%Y-%m-%d')
    df['_date_parsed'] = [_parse_date(r.get('日期')) for _, r in df.iterrows()]
    valid_dates = df['_date_parsed'].dropna()
    if len(valid_dates) > 0:
        df_valid = df[df['_date_parsed'] >= cutoff_str]
        skipped = len(df) - len(df_valid)
        if skipped > 0:
            print(f"⏭ 跳过 {skipped} 条超过 {DATA_RETENTION_DAYS} 天的旧数据")
        df = df_valid
    else:
        print("⚠ 未找到有效日期列")

    if len(df) == 0:
        print("⚠ 无有效数据可上传（全部超过保留期限）")
        return

    # ---- 3. 获取或创建 upload_records ----
    try:
        resp = supabase.table('upload_records').select('*').eq('status', 'pending').order('upload_time', desc=True).limit(1).execute()
        record = resp.data[0] if resp.data else None
    except Exception:
        record = None

    if not record:
        file_name = os.path.basename(metrics_file)
        try:
            resp = supabase.table('upload_records').insert({
                'file_name': file_name,
                'file_url': '',
                'uploaded_by': None,
                'status': 'processing',
            }).select('*').execute()
            record = resp.data[0] if resp.data else None
            upload_id = record['id'] if record else None
            print(f"   创建 upload_records: {upload_id}")
        except Exception as e:
            print(f"⚠ 创建 upload_records 失败: {e}")
            upload_id = None
    else:
        upload_id = record['id']
        print(f"   使用现有记录: {upload_id}")
        try:
            supabase.table('upload_records').update({'status': 'processing'}).eq('id', upload_id).execute()
        except Exception:
            pass

    # ---- 4. 构建 attendance_data 行 ----
    print("🔄 构建 attendance_data 记录...")
    rows = []
    for idx, r in df.iterrows():
        d = _parse_date(r.get('日期'))
        if not d:
            continue

        row = {
            'upload_id': upload_id,
            'employee_code': _to_str(r.get('工号')),
            'employee_name': _to_str(r.get('姓名')),
            'date': d,
            'department_level3': _to_str(r.get('三级部门')),
            'department_level4': _to_str(r.get('四级部门')),
            'department_level5': _to_str(r.get('五级部门')),
            'region': _to_str(r.get('大区')),
            'shift_name': _to_str(r.get('班次名称')),
            'shift_start': _to_time(r.get('班次上班时间')),
            'shift_end': _to_time(r.get('班次下班时间')),
            'first_punch': _to_time(r.get('首打卡时间')),
            'last_punch': _to_time(r.get('末打卡时间')),
            'punch_count': _to_int(r.get('班次内打卡次数')),
            'standard_punch_count': _to_int(r.get('标准打卡数')),
            'miss_count': _to_int(r.get('缺卡数')),
            'makeup_count': _to_int(r.get('补签数')),
            'is_scheduled': _to_bool(r.get('是否排班')),
            'is_schedule_correct': _map_correct(r.get('是否排班正确')),
            'rest_time': _to_str(r.get('休息时间')),
            'daily_total_hours': _to_float(r.get('每日总工时计算')),
            'is_overtime': _to_bool(r.get('是否日超8H')),
            'overtime_hours': _to_float(r.get('日超8H')),
            'week_overtime_hours': _to_float(r.get('本周累计加班工时')),
            'last_week_overtime_hours': _to_float(r.get('上周累计加班工时')),
            'is_hub': _to_bool(r.get('HUB')),
            'hub_status': _to_str(r.get('HUB排班结果')),
            'is_leave': _to_bool(r.get('是否请假')),
            'is_travel': _to_bool(r.get('是否出差')),
            'leave_hours': _to_float(r.get('请假小时数')),
            'travel_hours': _to_float(r.get('出差小时数')),
            'note': _to_str(r.get('备注（GF）')),
            'sign_hours': _to_float(r.get('签字小时数')),
            'sign_report_hours': _to_float(r.get('签字报表小时')),
            'pending_home_office_hours': _to_float(r.get('待定居家办公小时')),
        }
        rows.append(row)

    print(f"   准备上传 {len(rows)} 条记录")

    # ---- 5. 批量 UPSERT 到 attendance_data ----
    print("⬆️  上传到 Supabase attendance_data...")
    batch_size = 100
    success_count = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            resp = supabase.table('attendance_data').upsert(
                batch,
                on_conflict='employee_code,date'
            ).execute()
            success_count += len(batch)
            print(f"  批次 {i // batch_size + 1}: {len(batch)} 条 ✓")
        except Exception as e:
            print(f"  ❌ 批次 {i // batch_size + 1} 失败: {e}")
            # 逐条重试
            for row in batch:
                try:
                    supabase.table('attendance_data').upsert(
                        [row], on_conflict='employee_code,date'
                    ).execute()
                    success_count += 1
                except Exception as e2:
                    emp_code = row.get('employee_code', '?')
                    print(f"    ❌ {emp_code}: {e2}")

    print(f"✅ attendance_data 上传完成: {success_count}/{len(rows)} 条")

    # ---- 6. 聚合写入 attendance_trends ----
    print("📊 聚合数据 → attendance_trends...")
    try:
        df['_date'] = [_parse_date(r.get('日期')) for _, r in df.iterrows()]
        df = df[df['_date'].notna()]

        trends_rows = []
        grouped = df.groupby(['_date', '大区', '三级部门'])
        
        for (d, region, d3), g in grouped:
            total = len(g)
            
            # 已排班人数
            def _is_scheduled(x):
                if pd.isna(x):
                    return False
                return str(x).strip() in ('是', 'true', '1')
            scheduled = g['是否排班'].apply(_is_scheduled).sum()
            
            # 排班正确率
            correct_series = g['是否排班正确'].apply(
                lambda x: str(x).strip() if pd.notna(x) else ''
            )
            correct_count = (correct_series == '正确').sum()
            incorrect_count = (correct_series == '不正确').sum()
            schedule_correct_rate = round(correct_count / (correct_count + incorrect_count) * 100, 2) if (correct_count + incorrect_count) > 0 else None
            
            # 排班率
            schedule_rate = round(scheduled / total * 100, 2) if total > 0 else None
            
            # HUB 正确率
            hub_total = 0
            hub_correct = 0
            for _, r in g.iterrows():
                if _to_bool(r.get('HUB')):
                    hub_total += 1
                    if str(r.get('是否排班正确', '')).strip() == '正确':
                        hub_correct += 1
            hub_correct_rate = round(hub_correct / hub_total * 100, 2) if hub_total > 0 else None
            
            # 打卡率
            punch_count_sum = pd.to_numeric(g['班次内打卡次数'], errors='coerce').sum()
            std_punch_sum = pd.to_numeric(g['标准打卡数'], errors='coerce').sum()
            punch_rate = round(punch_count_sum / std_punch_sum * 100, 2) if std_punch_sum and std_punch_sum > 0 else None
            
            # 超8H
            overtime_hours_sum = pd.to_numeric(g['日超8H'], errors='coerce').fillna(0).sum()
            overtime_count = (pd.to_numeric(g['日超8H'], errors='coerce').fillna(0) > 0).sum()
            overtime_rate = round(overtime_count / total * 100, 2) if total > 0 else None
            
            # 缺卡
            miss_sum = pd.to_numeric(g['缺卡数'], errors='coerce').fillna(0).sum()
            
            # 补签
            makeup_sum = pd.to_numeric(g['补签数'], errors='coerce').fillna(0).sum()
            makeup_rate = round(makeup_sum / (makeup_sum + miss_sum) * 100, 2) if (makeup_sum + miss_sum) > 0 else None
            
            # 加班工时
            week_ot = pd.to_numeric(g['本周累计加班工时'], errors='coerce').sum()
            last_week_ot = pd.to_numeric(g['上周累计加班工时'], errors='coerce').sum()
            
            trends_rows.append({
                'date': d,
                'region': _to_str(region),
                'department_level3': _to_str(d3),
                'department_level4': None,  # 汇总行
                'schedule_rate': schedule_rate,
                'schedule_count': int(scheduled),
                'unscheduled_count': int(total - scheduled),
                'schedule_correct_rate': schedule_correct_rate,
                'schedule_correct_count': int(correct_count),
                'schedule_incorrect_count': int(incorrect_count),
                'hub_correct_rate': hub_correct_rate,
                'hub_total_count': hub_total,
                'hub_correct_count': hub_correct,
                'punch_rate': punch_rate,
                'punch_count': int(punch_count_sum) if pd.notna(punch_count_sum) else 0,
                'standard_punch_total': int(std_punch_sum) if pd.notna(std_punch_sum) else 0,
                'makeup_rate': makeup_rate,
                'makeup_count': int(makeup_sum) if pd.notna(makeup_sum) else 0,
                'miss_count_total': int(miss_sum) if pd.notna(miss_sum) else 0,
                'overtime_hours': float(overtime_hours_sum) if pd.notna(overtime_hours_sum) else None,
                'overtime_rate': overtime_rate,
                'overtime_employee_count': int(overtime_count),
                'week_overtime_hours': float(week_ot) if pd.notna(week_ot) else None,
                'last_week_overtime_hours': float(last_week_ot) if pd.notna(last_week_ot) else None,
                'total_employees': int(total),
                'upload_id': upload_id,
            })
        
        # 写入 trends（upsert）
        print(f"   写入 {len(trends_rows)} 条趋势记录...")
        for i in range(0, len(trends_rows), batch_size):
            batch = trends_rows[i:i + batch_size]
            try:
                supabase.table('attendance_trends').upsert(
                    batch,
                    on_conflict='date,department_level3,department_level4'
                ).execute()
                print(f"  趋势批次 {i // batch_size + 1}: {len(batch)} 条 ✓")
            except Exception as e:
                print(f"  ❌ 趋势批次失败: {e}")
                traceback.print_exc()
        
        print(f"✅ attendance_trends 写入完成")
        
    except Exception as e:
        print(f"❌ 趋势聚合失败: {e}")
        traceback.print_exc()

    # ---- 7. 更新 upload_records 状态 ----
    if upload_id:
        try:
            supabase.table('upload_records').update({
                'status': 'completed',
                'data_date': _parse_date(df['_date'].iloc[0]) if len(df) > 0 else None,
            }).eq('id', upload_id).execute()
            print(f"✅ upload_records 状态更新为 completed")
        except Exception as e:
            print(f"⚠ 更新 upload_records 状态失败: {e}")

    print(f"\n🎉 全部完成！保留最近 {DATA_RETENTION_DAYS} 天数据。")


if __name__ == '__main__':
    print("此脚本通过 main.py upload 调用，不直接运行。")
    print("用法: python main.py upload --workspace ./output")
