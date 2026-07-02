"""
同比变化注入脚本。
读取 comparison_data.json，将对比标识(CSS+JS)注入到所有HTML页面。

用法:
    python inject_comparison.py <工作目录>

示例:
    python inject_comparison.py C:/Users/.../2026-05-22-xxx
"""
import sys
import json
import re
import os

# ===== 配置 =====
if len(sys.argv) >= 2:
    WORKSPACE = sys.argv[1]
else:
    WORKSPACE = os.getcwd()

cmp_path = os.path.join(WORKSPACE, 'comparison_data.json')
if not os.path.exists(cmp_path):
    print(f"错误: 找不到 comparison_data.json: {cmp_path}")
    print("请先运行 compute_comparison.py 生成对比数据")
    sys.exit(1)

with open(cmp_path, 'r', encoding='utf-8') as f:
    cmp = json.load(f)


def build_injected_html(html, overview_cmp=None, region_cmp=None):
    """添加同比变化CSS和JS到HTML，替换之前的注入。"""

    # 移除之前的注入 (CSS + JS)
    html = re.sub(r'/\* ===== 同比变化标识样式 ===== \*/\s*\.cmp-badge[^}]*}[^}]*}[^}]*}[^}]*}', '', html, flags=re.DOTALL)
    html = re.sub(r'\n\s*/\* ===== 同比变化标识样式 ===== \*/[\s\S]*?(?=\n\s*/\*|\n</style>)', '', html)
    html = re.sub(r'<script>\s*// ===== 同比变化标识 \(自动注入\) =====[\s\S]*?</script>', '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)

    # 注入CSS
    cmp_css = '''
/* ===== 同比变化标识样式 ===== */
.cmp-badge { display: inline; vertical-align: middle; }
.cmp-badge-green { color: #22c55e; }
.cmp-badge-red { color: #ef4444; }
.cmp-badge-gray { color: #64748b; }
'''
    if '/* ===== 同比变化标识样式 ===== */' not in html:
        idx = html.find('</style>')
        if idx > 0:
            html = html[:idx] + cmp_css + html[idx:]

    # 构建JS
    compare_js_parts = ['<script>']
    compare_js_parts.append('// ===== 同比变化标识 (自动注入) =====')

    if overview_cmp:
        compare_js_parts.append('var CMP_OVERVIEW = ' + json.dumps(overview_cmp, ensure_ascii=False) + ';')
    if region_cmp:
        compare_js_parts.append('var CMP_REGION = ' + json.dumps(region_cmp, ensure_ascii=False) + ';')

    compare_js_parts.append('''
(function() {
  function addBadges() {
    var cmpData = window.CMP_OVERVIEW || window.CMP_REGION || {};

    var cards = document.querySelectorAll('.card, .kpi-card');
    cards.forEach(function(card) {
      var titleEl = card.querySelector('.card-title, .kpi-label');
      if (!titleEl) return;
      var title = titleEl.textContent.trim();

      var existing = card.querySelector('.cmp-badge');
      if (existing) existing.remove();

      var key = null;
      if (title.includes('日超8H') || title.includes('日超8小时') || title.includes('超标')) { key = '超标率'; }
      else if (title.includes('排班率') && !title.includes('正确') && !title.includes('HUB')) { key = '排班率'; }
      else if (title.includes('排班正确率') || (title.includes('正确率') && !title.includes('HUB'))) { key = '正确率'; }
      else if (title.includes('缺卡') && !title.includes('排班')) { key = '缺卡率'; }
      else if (title.includes('HUB排班正确率') || title.includes('HUB正确率')) { key = 'HUB正确率'; }

      if (!key || !cmpData[key]) return;

      var c = cmpData[key];
      var diffPp = c.diff_pp;
      var ppText = diffPp !== 0 ? (diffPp > 0 ? '+' : '') + diffPp.toFixed(1) + '%' : '持平';
      var clr = c.color === 'green' ? '#22c55e' : (c.color === 'red' ? '#ef4444' : '#64748b');

      var badge = document.createElement('span');
      badge.className = 'cmp-badge';
      badge.style.cssText = 'color:' + clr + ';font-size:11px;margin-left:6px;white-space:nowrap;font-weight:600;';
      badge.textContent = c.arrow + ' ' + ppText;

      var valueEl = card.querySelector('.card-value, .kpi-value');
      if (valueEl) {
        valueEl.appendChild(badge);
      } else {
        titleEl.appendChild(badge);
      }
    });
  }

  addBadges();
  setTimeout(addBadges, 500);
  setTimeout(addBadges, 1500);
  setTimeout(addBadges, 3000);

  var observer = new MutationObserver(function() { setTimeout(addBadges, 300); });
  var mainContent = document.getElementById('mainContent');
  if (mainContent) observer.observe(mainContent, { childList: true, subtree: true });
})();
</script>''')

    compare_js = '\n'.join(compare_js_parts)

    # 注入到 </body> 前
    html = html.replace('</body>', compare_js + '\n</body>', 1)

    return html


# ===== 处理所有HTML文件 =====
overview_cmp = cmp.get('__overview__', {})

# 1. 考勤首页.html
home_path = os.path.join(WORKSPACE, '考勤首页.html')
if os.path.exists(home_path):
    with open(home_path, 'r', encoding='utf-8') as f:
        html = f.read()
    html = build_injected_html(html, overview_cmp=overview_cmp, region_cmp=None)
    with open(home_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Updated: 考勤首页.html')

# 2. 考勤分析报告.html
report_path = os.path.join(WORKSPACE, '考勤分析报告.html')
if os.path.exists(report_path):
    with open(report_path, 'r', encoding='utf-8') as f:
        html = f.read()
    html = build_injected_html(html, overview_cmp=overview_cmp, region_cmp=None)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Updated: 考勤分析报告.html')

# 3. 大区页面
region_files = {
    'WE': '考勤分析_WE 美西大区.html',
    'NE': '考勤分析_NE 东北大区.html',
    'FL': '考勤分析_FL 佛州大区.html',
    'TX': '考勤分析_TX 德州大区.html',
    'Ground项目部': '考勤分析_Ground项目部.html',
    'MS': '考勤分析_MS 中南大区.html',
    'GL': '考勤分析_GL 大湖大区.html',
}

for rk, filename in region_files.items():
    fpath = os.path.join(WORKSPACE, filename)
    if not os.path.exists(fpath):
        print(f'跳过(不存在): {filename}')
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        html = f.read()
    region_cmp = cmp.get(rk, {})
    html = build_injected_html(html, overview_cmp=None, region_cmp=region_cmp)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Updated: {filename}')

print()
print('所有HTML文件已注入同比变化标识!')
