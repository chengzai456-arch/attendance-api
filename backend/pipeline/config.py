"""
考勤排班分析 - 配置管理
统一管理所有输入/输出路径，支持 CLI 参数覆盖
"""
import os

# ============================================================
# 默认路径
# ============================================================
DEFAULT_DOWNLOADS = r"D:\Documents\Downloads"
PYTHON_EXE = r"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
VENV_SITE = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages"

# 强制 UTF-8 输出，解决 Windows Git Bash 中文乱码
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# ============================================================
# Supabase 配置（用于数据上传）
# 从环境变量读取，若未设置则使用默认值（需用户配置）
# ============================================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://your-project.supabase.co')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


def get_config(workspace=None, input_dir=None):
    """
    返回完整配置字典。

    参数:
        workspace: 工作目录（默认 os.getcwd()），中间产物和输出均在此
        input_dir: 原始输入文件目录（默认 DEFAULT_DOWNLOADS）

    返回:
        dict: 包含所有输入/输出文件路径的配置
    """
    if workspace is None:
        workspace = os.getcwd()
    if input_dir is None:
        input_dir = DEFAULT_DOWNLOADS

    return {
        # ==== 原始输入文件 ====
        'raw_file':       os.path.join(input_dir, '原始数据 (2).xlsx'),
        'leave_file':     os.path.join(input_dir, '离职流程 (1).xlsx'),
        'roster_pattern': os.path.join(input_dir, '花名册 ({n}).xlsx'),
        'shift_file':     os.path.join(input_dir, '班次.xlsx'),
        'resign_file':    os.path.join(input_dir, '补签管理 (1).xlsx'),
        'sign_report_this_week': os.path.join(input_dir, 'GUS+美区签字报表.xlsx'),        # 本周（用户指定）
        'sign_report_last_week': os.path.join(input_dir, 'GUS+美区签字报表 (2).xlsx'),     # 上周（用户指定）
        'sign_report_biweek':    os.path.join(input_dir, 'GUS+美区签字报表 (1).xlsx'),    # 双周（用户指定）
        'gus_whitelist_file':  os.path.join(input_dir, 'GUS需剔除人员（白名单）.xlsx'),  # GUS白名单剔除（本次无，自动跳过）

        # ==== 中间输出 (workspace 下) ====
        'cleaned_file':  os.path.join(workspace, '清洗后数据.xlsx'),
        'metrics_file':  os.path.join(workspace, '指标计算后数据.xlsx'),
        'pivot_file':    os.path.join(workspace, '透视分析.xlsx'),
        'report_json':   os.path.join(workspace, 'report_data.json'),
        'comparison_json': os.path.join(workspace, 'comparison_data.json'),

        # ==== HTML 输出 ====
        'html_home':   os.path.join(workspace, '考勤首页.html'),
        'html_report': os.path.join(workspace, '考勤分析报告.html'),

        # ==== 环境 ====
        'workspace': workspace,
        'python_exe': PYTHON_EXE,
        'venv_site':  VENV_SITE,
    }


def get_roster_path(config, roster_index=12):
    """根据花名册序号构造完整路径"""
    return config['roster_pattern'].format(n=roster_index)
