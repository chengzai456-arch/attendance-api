"""
考勤排班数据分析 - 单一入口

用法:
    # 完整流程
    python main.py all --workspace C:\\Users\\...\\2026-05-27-xxx --roster-index 15

    # 单独步骤
    python main.py clean --workspace ... --roster-index 15
    python main.py metrics --workspace ...
    python main.py pivot --workspace ...
    python main.py report --workspace ...
    python main.py render --workspace ...
    python main.py compare --workspace ... --prev-workspace ...
    python main.py inject --workspace ...

    # 含同比对比的完整流程
    python main.py all-with-compare --workspace ... --prev-workspace ...

    # 快速生成报告(已有指标数据)
    python main.py quick-report --workspace ...
"""
import sys
import os

# 强制 UTF-8 输出
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import argparse
from config import get_config

from pipeline.steps.clean_data import run as run_clean
from pipeline.steps.add_metrics import run as run_metrics
from pipeline.steps.upload_trend_data import run as run_upload_trend
from pipeline.steps.build_trend_data import run as run_build_trend
from pipeline.steps.pivot_analysis import run as run_pivot
from pipeline.steps.build_report_data import run as run_report_data
from pipeline.steps.render_report import run as run_render
from pipeline.steps.compute_comparison import run as run_comparison
from pipeline.steps.inject_comparison import run as run_inject
from pipeline.steps.clean_base import run as run_clean_base
from scripts.upload_to_supabase import run as run_upload_supabase


STEPS = [
    ('clean',        run_clean,         '步骤1: 数据清洗'),
    ('metrics',      run_metrics,       '步骤2: 指标计算'),
    ('upload_trend', run_upload_trend,   '步骤2.5: 上传趋势表'),
    ('build_trend',  run_build_trend,    '步骤2.6: 构建趋势数据'),
    ('pivot',        run_pivot,         '步骤3: 透视分析'),
    ('report',       run_report_data,   '步骤4a: 构建报告JSON'),
    ('render',       run_render,        '步骤4b: 生成HTML报告'),
    ('compare',      run_comparison,    '步骤5a: 同比对比计算'),
    ('inject',       run_inject,        '步骤5b: 注入同比变化标识'),
]

STEP_NAMES = [s[0] for s in STEPS]
STEP_FUNCS = {s[0]: s[1] for s in STEPS}
# 独立步骤（不参与 'all' 流程）
EXTRA_STEPS = {
    'clean-base': run_clean_base,
    'compare':   run_comparison,
    'inject':    run_inject,
}


def _run_all(config, roster_index, prev_workspace=None):
    """执行完整流程（步骤1-5b）"""
    for name, func, _ in STEPS:
        print(f'\n{"=" * 60}')
        print(f'>>> {name}')
        print(f'{"=" * 60}')
        kwargs = {}
        if name == 'clean':
            kwargs['roster_index'] = roster_index
        elif name == 'compare':
            if prev_workspace:
                kwargs['prev_workspace'] = prev_workspace
            else:
                print(f"跳过 {name}: 未提供 --prev-workspace")
                continue
        func(config, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description='考勤排班数据分析全流程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python main.py all --workspace C:\\Users\\...\\2026-05-27 --roster-index 15
  python main.py clean --workspace C:\\Users\\...\\2026-05-27 --roster-index 15
  python main.py render --workspace C:\\Users\\...\\2026-05-27
  python main.py quick-report --workspace C:\\Users\\...\\2026-05-27
        '''
    )
    parser.add_argument('--workspace', default=None,
                        help='工作目录 (默认当前目录)')
    parser.add_argument('--prev-workspace', default=None,
                        help='前次工作目录 (同比对比用)')
    parser.add_argument('--roster-index', type=int, default=12,
                        help='花名册文件序号 (默认 12)')

    subparsers = parser.add_subparsers(dest='step', help='执行指定步骤')

    # 单个步骤
    for name, _, desc in STEPS:
        subparsers.add_parser(name, help=desc)

    # 组合命令
    subparsers.add_parser('all', help='执行完整流程 (步骤1-4b + 上传Supabase, 含趋势数据上传+构建)')
    subparsers.add_parser('all-with-compare', help='执行完整流程含同比对比 (步骤1-5b)')
    subparsers.add_parser('quick-report', help='快速生成报告 (趋势构建+步骤4a-4b, 需已有指标数据)')
    subparsers.add_parser('clean-base', help='清理多维表过期数据 (保留最近7天)')
    subparsers.add_parser('upload', help='上传指标数据到 Supabase')

    args = parser.parse_args()

    if not args.step:
        parser.print_help()
        return

    # 若指定了 --workspace，将其同时作为 input_dir（原始文件已复制到该目录）
    # 否则 input_dir=None 表示使用 config 中的 DEFAULT_DOWNLOADS
    input_dir = args.workspace if args.workspace else None
    config = get_config(args.workspace, input_dir=input_dir)
    print(f"工作目录: {config['workspace']}")

    if args.step == 'all':
        # 步骤1-4b (含趋势数据上传和构建)
        for name, func, _ in STEPS[:7]:
            print(f'\n{"=" * 60}')
            print(f'>>> {name}')
            print(f'{"=" * 60}')
            kwargs = {}
            if name == 'clean':
                kwargs['roster_index'] = args.roster_index
            func(config, **kwargs)
        # 步骤5: 上传 Supabase
        print(f'\n{"=" * 60}')
        print(f'>>> upload_to_supabase')
        print(f'{"=" * 60}')
        run_upload_supabase(config)

    elif args.step == 'all-with-compare':
        _run_all(config, args.roster_index, args.prev_workspace)

    elif args.step == 'quick-report':
        # 步骤2.6 + 4a-4b: 趋势构建 + 快速报告
        for name in ['build_trend', 'report', 'render']:
            func = STEP_FUNCS[name]
            print(f'\n{"=" * 60}')
            print(f'>>> {name}')
            print(f'{"=" * 60}')
            func(config)

    elif args.step == 'upload':
        run_upload_supabase(config)

    elif args.step == 'clean-base':
        run_clean_base(config)

    else:
        # 单个步骤
        func = STEP_FUNCS.get(args.step)
        if not func:
            # 也尝试 EXTRA_STEPS
            func = EXTRA_STEPS.get(args.step)
        if func:
            kwargs = {}
            if args.step == 'clean':
                kwargs['roster_index'] = args.roster_index
            elif args.step == 'compare':
                if not args.prev_workspace:
                    print("错误: --prev-workspace 是必须的")
                    return
                kwargs['prev_workspace'] = args.prev_workspace
            func(config, **kwargs)


if __name__ == '__main__':
    main()
