"""
步骤4b: HTML 报告生成（薄包装）
通过 subprocess 调用原始 scripts/render_report.py，通过环境变量传递 workspace
"""
import subprocess
import sys
import os


def run(config):
    """调用原始 render_report.py 生成 HTML 报告"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(skill_dir, 'scripts', 'render_report.py')
    script = os.path.normpath(script)

    if not os.path.exists(script):
        print(f"错误: 找不到脚本 {script}")
        return

    env = os.environ.copy()
    env['ATTENDANCE_WORKSPACE'] = config['workspace']

    print(f"调用 render_report.py (workspace={config['workspace']})")
    subprocess.run([sys.executable, script], env=env, check=True)

    # 自动验证 HTML 完整性
    print("=== HTML 完整性验证 ===")
    test_script = os.path.join(skill_dir, 'tests', 'test_html.py')
    if os.path.exists(test_script):
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'tests.test_html'],
            cwd=skill_dir, env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.split('\n') if '...' in l]
            ok_count = sum(1 for l in lines if 'ok' in l)
            fail_count = sum(1 for l in lines if 'FAIL' in l or 'ERROR' in l)
            if fail_count == 0:
                print(f"  ✅ {ok_count} 项检查全部通过")
            else:
                print(f"  ❌ {fail_count} 项失败! {ok_count} 通过")
        else:
            print(f"  ❌ 验证失败 (code={result.returncode})")
            err = result.stderr or result.stdout or ''
            if err:
                print(err[-500:])
    else:
        print(f"  ⚠ 测试文件不存在: {test_script}")
