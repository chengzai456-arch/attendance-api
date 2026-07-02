#!/usr/bin/env python3
"""
auth_injector.py — 将飞书 SSO 权限守卫注入到考勤 HTML 页面

用法:
  python auth_injector.py <HTML目录> [--backend-url http://...] [--login-page login.html]

示例:
  python auth_injector.py C:/Users/Administrator/WorkBuddy/gofo-deploy
  python auth_injector.py ./output --backend-url https://abc.cpolar.cn
"""

import os, sys, re, argparse
from pathlib import Path

# ═══════════════════════════════════════════════════════════
#  权限守卫脚本（内嵌，部署时修改 backend_url）
# ═══════════════════════════════════════════════════════════

AUTH_GUARD_TEMPLATE = """<!-- ══════════════════════════════════════════════
     飞书 SSO 权限守卫 — 自动注入（请勿手动修改）
     ══════════════════════════════════════════════ -->
<script>
(function(){'use strict';
var SSO_BACKEND_URL='{backend_url}';
var LOGIN_PAGE='{login_page}';
var PAGE_REGION='{region}';

async function _auth_check(){
 var t=localStorage.getItem('token');
 if(!t){window.location.href=LOGIN_PAGE;return;}
 try{
  var r=await fetch(SSO_BACKEND_URL+'/api/auth/me',{headers:{'Authorization':'Bearer '+t}});
  if(r.ok){
   var u=await r.json();
   localStorage.setItem('user',JSON.stringify(u));
   if(PAGE_REGION&&u.pages&&u.pages.indexOf(PAGE_REGION)===-1){_auth_forbidden(u.name||'?',PAGE_REGION);return;}
   window.__AUTH_USER__=u;
  }else if(r.status===401){
   localStorage.removeItem('token');localStorage.removeItem('user');
   window.location.href=LOGIN_PAGE;return;
  }
 }catch(e){console.warn('[Auth] 后端不可达，跳过权限检查');}
 window.dispatchEvent(new CustomEvent('auth:done'));
}
function _auth_forbidden(nm,rg){
 document.body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:linear-gradient(135deg,#080c14,#0c1220,#0a0f1a);font-family:-apple-system,BlinkMacSystemFont,\\'PingFang SC\\',sans-serif;color:#f1f5f9;"><div style="text-align:center;padding:48px 40px;background:rgba(15,23,42,0.60);backdrop-filter:blur(20px);border-radius:16px;border:1px solid rgba(239,68,68,0.20);max-width:420px;"><div style="font-size:48px;margin-bottom:16px;">🚫</div><h2 style="font-size:20px;margin-bottom:8px;color:#ef4444;">无访问权限</h2><p style="color:#94a3b8;font-size:14px;line-height:1.6;margin-bottom:20px;">'+_e(nm)+'，你没有访问 '+_e(rg)+' 大区数据的权限。<br>如需访问请联系管理员。</p><button onclick="location.href=\\''+LOGIN_PAGE+'\\'" style="background:rgba(148,163,184,0.15);color:#94a3b8;border:1px solid rgba(148,163,184,0.10);padding:8px 20px;border-radius:8px;cursor:pointer;font-size:13px;">返回登录页</button></div></div>';
}
function _e(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
_auth_check();
window.__AUTH__={SSO_BACKEND_URL:SSO_BACKEND_URL,getUser:function(){return window.__AUTH_USER__;},getToken:function(){return localStorage.getItem('token');},logout:function(){localStorage.removeItem('token');localStorage.removeItem('user');window.location.href=LOGIN_PAGE;},isAdmin:function(){return window.__AUTH_USER__&&window.__AUTH_USER__.role==='admin';},canAccess:function(r){return window.__AUTH_USER__&&window.__AUTH_USER__.pages&&window.__AUTH_USER__.pages.indexOf(r)!==-1;}};
})();
</script>
<!-- ══════════════════════════════════════════════ -->

"""

# ═══════════════════════════════════════════════════════════
#  区域映射：文件名 → 区域代码
# ═══════════════════════════════════════════════════════════

REGION_FILE_MAP = {
    # 通用页面（无区域限制）
    'home.html': None,
    'report.html': None,
    'index.html': None,

    # 区域页面
    'region_WE.html': 'WE',
    'region_NE.html': 'NE',
    'region_FL.html': 'FL',
    'region_TX.html': 'TX',
    'region_Ground.html': 'Ground',
    'region_MS.html': 'MS',
    'region_GL.html': 'GL',

    # 兼容旧命名
    '考勤首页.html': None,
    '考勤分析报告.html': None,
}

# ═══════════════════════════════════════════════════════════
#  注入逻辑
# ═══════════════════════════════════════════════════════════

def inject_auth_guard(html_path, backend_url, login_page):
    """向 HTML 文件的 <head> 注入权限守卫脚本"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已注入
    if '飞书 SSO 权限守卫' in content:
        print(f'  ⏭ 跳过（已注入）: {os.path.basename(html_path)}')
        return False

    # 确定区域代码
    filename = os.path.basename(html_path)
    region = REGION_FILE_MAP.get(filename, None)

    # 生成守卫脚本（用 replace 避免 JS 花括号冲突）
    guard_script = AUTH_GUARD_TEMPLATE.replace('{backend_url}', backend_url.rstrip('/')) \
                                       .replace('{login_page}', login_page) \
                                       .replace('{region}', region or '')

    # 注入到 <head> 标签后
    # 策略：在 </head> 之前插入
    if '</head>' in content:
        content = content.replace('</head>', guard_script + '\n</head>', 1)
    elif '<head>' in content:
        content = content.replace('<head>', '<head>\n' + guard_script, 1)
    else:
        print(f'  ⚠ 未找到 <head> 标签: {filename}')
        return False

    # 写回文件
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)

    region_str = f' (区域: {region})' if region else ''
    print(f'  ✅ 已注入: {filename}{region_str}')
    return True


def process_directory(html_dir, backend_url, login_page, dry_run=False):
    """处理目录下所有 HTML 文件"""
    html_dir = Path(html_dir)
    if not html_dir.is_dir():
        print(f'❌ 目录不存在: {html_dir}')
        return

    html_files = sorted(html_dir.glob('*.html'))
    if not html_files:
        print(f'⚠ 目录下无 HTML 文件: {html_dir}')
        return

    print(f'\n目录: {html_dir}')
    print(f'后端地址: {backend_url}')
    print(f'文件数: {len(html_files)}')
    if dry_run:
        print('模式: 预览（不修改文件）')
    print('─' * 60)

    injected = 0
    skipped = 0

    for f in html_files:
        if dry_run:
            filename = f.name
            region = REGION_FILE_MAP.get(filename, None)
            region_str = f' (区域: {region})' if region else ''
            print(f'  📄 {filename}{region_str}')
        else:
            if inject_auth_guard(str(f), backend_url, login_page):
                injected += 1
            else:
                skipped += 1

    if not dry_run:
        print('─' * 60)
        print(f'结果: 注入 {injected} 个, 跳过 {skipped} 个')


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='飞书 SSO 权限守卫注入工具')
    parser.add_argument('html_dir', help='HTML 文件所在目录')
    parser.add_argument('--backend-url', default='http://localhost:3000',
                        help='SSO 后端地址 (默认: http://localhost:3000)')
    parser.add_argument('--login-page', default='login.html',
                        help='登录页文件名 (默认: login.html)')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览模式，不修改文件')

    args = parser.parse_args()

    process_directory(args.html_dir, args.backend_url, args.login_page, args.dry_run)
