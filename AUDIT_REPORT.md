# 兮易AI智体平台 · 产品逻辑修复审计报告

> 审计时间: 2026-05-31
> 审计范围: 前端页面全部 26 个 HTML 文件 + 后端 xiyi_server.py

---

## 一、前端 API 鉴权检查（X-API-Key Header 缺失审计）

**🔴 P0 — 所有 fetch 调用均缺少 X-API-Key header**

当前没有任何一个页面在 fetch 请求中携带 `X-API-Key` header。Tony 将在后端添加鉴权中间件，前端需要统一补充。

### 涉及的文件及 fetch 调用分布

| 文件 | fetch 数量 | 行号范围 | 说明 |
|------|-----------|---------|------|
| `xiyi-quality-workbench.html` | 8 | 269-352 | kpi/场景/预警/任务/新闻/标记已读/AI分析 |
| `xiyi-index.html` | 1 | 71 | 首页角色加载 |
| `xiyi-config-console.html` | 12 | 108-525 | 场景/指标/标准/规则 CRUD |
| `xiyi-datasource-manager.html` | 5 | 80-153 | 数据源 CRUD+测试+CSV导入 |
| `xiyi-prompt-manager.html` | 3 | 64-122 | Prompt CRUD |
| `xiyi-capa-manager.html` | 5 | 86-251 | CAPA/任务/跟踪 CRUD |
| `xiyi-scenes-manager.html` | 1 | 73 | 场景列表 |
| `xiyi-alerts.html` | 1 | 48 | 预警列表 |
| `xiyi-diagnose.html` | 3 | 78-106 | 场景诊断+步骤+分析跟踪 |
| `xiyi-ai-analysis.html` | 4 | 107-192 | 场景详情+AI分析+结果轮询 |
| `pages/xiyi-datasource-manager.html` | 5 | 80-153 | 副本页 |
| `pages/xiyi-prompt-manager.html` | 3 | 64-122 | 副本页 |

**总计: 约 51 处 fetch 调用缺少 X-API-Key header**

### 修复建议
创建一个共享的 `api.js` 或 `fetchWithAuth()` 包装函数：
```javascript
// 统一放在 xiyi-workbench.html 或单独 api.js
async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  headers['X-API-Key'] = 'xiyi-default-dev-key';  // Tony确认后替换
  options.headers = headers;
  return fetch(url, options);
}
// 所有页面使用 apiFetch 替换 fetch
```

> ⚠️ **注意:** 待 Tony 确认最终的 X-API-Key 值后补全

---

## 二、空数据状态体验问题

### 2.1 KPI 详情页（6个独立页面）— 打开时无数据则白屏

**🟡 P1**

当前所有 6 个 KPI 详情页均使用**硬编码静态数据**（mock data），完全不调用后端 API：

| 文件 | 数据来源 | 问题 |
|------|---------|------|
| `xiyi-kpi-fpy-detail.html` | 纯硬编码 `chartData`, `chartLabels` | 无 API 调用，永不白屏但永不真实 |
| `xiyi-kpi-mag-detail.html` | 纯硬编码 | 同上 |
| `xiyi-kpi-abnormal-detail.html` | 纯硬编码 | 同上 |
| `xiyi-kpi-iqc-detail.html` | 纯硬编码 | 同上 |
| `xiyi-kpi-pmp-detail.html` | 纯硬编码 | 同上 |
| `xiyi-kpi-coq-detail.html` | 纯硬编码 | 同上 |

**问题本质:** 无后端数据集成。一旦后端提供真实数据，若 API 返回空列表，页面会尝试渲染空数据导致空白图表（`undefined` 错误）或 `document.getElementById('trendChart')` 为 null。

**修复建议:**
- 为每个详情页添加空状态判断: `if (!data || data.length === 0)` 时展示 "暂无数据" 占位提示
- 把硬编码数据改造成 API 调用，保留 mock 数据作为 fallback
- 示例:
```javascript
async function loadKpiData() {
  try {
    const r = await fetch('/api/v1/xiyi/kpi/fpy').then(d => d.json());
    if (r.code === 0 && r.data && r.data.length > 0) {
      // 渲染真实数据
    } else {
      document.getElementById('content').innerHTML = '<div class="empty-state">📭 暂无数据</div>';
    }
  } catch(e) {
    // fallback: 使用当前硬编码 mock
    renderWithMockData();
  }
}
```

### 2.2 场景页（1~7）首次打开无数据

**🟡 P1**

场景 1~7 全景页面 (`xiyi-full-scene*.html`) 同样全部使用**硬编码静态数据**，不请求后端 API。API 空返回时：
- 图表 canvas 元素会因 `getContext('2d')` on null 而报错
- `setTimeout` 中的 Chart 初始化代码失败但不报友好错误
- 用户看到: 空壳 HTML（标题+导航）+ 空白灰色卡片

**受影响的场景页:**
| 文件 | 场景 |
|------|------|
| `xiyi-full-scene.html` | 场景1（FPY全景） |
| `xiyi-full-scene-2.html` | 场景2（磁物健康MHM） |
| `xiyi-full-scene-3.html` | 场景3（异常料AMA） |
| `xiyi-full-scene-4.html` | 场景4（呆滞库存SIA） |
| `xiyi-full-scene-5.html` | 场景5（IQC） |
| `xiyi-full-scene-6.html` | 场景6（PMP） |
| `xiyi-full-scene-7.html` | 场景7（COQ） |

**修复建议:**
- 每个 `renderTab*`/`drawChart*` 函数前添加数据非空检查
- 统一添加 `renderEmptyState(containerId)` 辅助函数
- 数据加载区域（如 `grid-4` KPI 卡片）添加 `loading` → `empty` → `data` 三态渲染

### 2.3 分析结果页面空白

**🟡 P1**

`xiyi-ai-analysis.html` 加载流程：
```
load page → show loading → fetch(analysis/trace/{traceId}) → render result
```
**问题:** 
- 若 `_traceId` 为空，直接显示 "正在调用AI进行分析..." 无限loading
- 若 API 返回空结果，AI 内容区域显示 `undefined` 或空白

**修复建议:**
```javascript
if (!_traceId) {
  document.getElementById('loadingArea').style.display = 'none';
  document.getElementById('resultArea').innerHTML = '<div class="empty-state">📭 没有分析记录，请从工作台发起AI分析</div>';
  return;
}
```

### 2.4 工作台右侧面板无数据

**🔴 P0**

`xiyi-quality-workbench.html` 右侧 3 个面板（预警/任务/新闻）的 catch 分支已有基本的 "暂无xxx" 文本，但：
- 当 API 正常返回但 `data` 为空数组时，不会触发 catch，会渲染空白列表
- 例如 `alerts.slice(0, 3).map(...).join('')` 返回空字符串，用户看到空面板

**当前部分代码已有改进:**
```javascript
// alerts.html 中已有空状态判断
if (alerts.length === 0) {
  document.getElementById('alertList').innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted)">暂无预警</div>';
  return;
}
```

**需要同样处理的文件:**
| 文件 | 需要添加空状态的位置 |
|------|-------------------|
| `xiyi-quality-workbench.html` | 右侧面板 alertPanel/taskPanel/newsPanel 的 map 输出前 |
| `xiyi-scenes-manager.html` | 场景列表渲染 |
| `xiyi-config-console.html` | 场景/指标/规则列表 |
| `xiyi-diagnose.html` | 步骤加载 |

---

## 三、界面一致性检查

### 3.1 7个场景页布局风格一致性对比

**检查对象:** `xiyi-full-scene*.html` (场景 1~7)

| 维度 | 场景1 (FPY) | 场景2 (磁物) | 场景3 (异常料) | 场景4 (呆滞) | 场景5 (IQC) | 场景6 (PMP) | 场景7 (COQ) |
|------|------------|-------------|--------------|------------|------------|------------|------------|
| CSS变量命名 | `--bg-primary` 模式 | `--bg` 简写 | `--bg` 简写 | `--bg` 简写 | `--bg` 简写 | `--bg` 简写 | `--bg` 简写 |
| Tab导航样式 | 半圆角 `tabs` | 同左 | 同左 | 同左 | 同左 | 同左 | 同左 |
| grid-4 KPI布局 | 有 | 有 | 有 | 有 | 有 | 有 | 有 |
| AI摘要框 | `ai-summary-box` | `ai-box` | `.ai` | `.ai` | `.ai` | `.ai` | `.ai` |
| header 返回按钮 | `btn` 类 | 同左 | `btn` | `btn` | `btn` | `btn` | `btn` |
| 字体大小 | 13-14px | 11-13px | 10-12px | 10-12px | 10-12px | 10-12px | 10-12px |
| 卡片圆角 | 10px | 10px | 10px | 10px | 10px | 10px | 10px |
| 表格字体 | 12px | 11px | 11px | 11px | 11px | 11px | 11px |
| body padding | 20px 24px | 20px 24px | 20px 24px | 20px 24px | 20px 24px | 20px 24px | 20px 24px |
| tab 类命名 | `fpy-tab-item` | `fpy-tab-item` | `.tab` | `.tab` | `.tab` | `.tab` | `.tab` |
| tab 选中样式 | `active` | `active` | `active` | `active` | `active` | `active` | `active` |

**🟢 结论: 总体一致性较好。** 主要差异:

1. **🟡 CSS 变量命名不统一**
   - 场景1 使用 `--bg-primary`, `--bg-secondary`, `--bg-card`
   - 场景2~7 使用 `--bg`, `--bg2`, `--card`
   - **建议:** 统一为一种命名模式

2. **🟡 AI 摘要框类名不统一**
   - 场景1: `ai-summary-box`
   - 场景2: `ai-box`
   - 场景3~7: `.ai`
   - **建议:** 统一为 `.ai-summary-box`

3. **🟡 Tab 类名不统一**
   - 场景1~2: `fpy-tab-item` / `fpy-tab-content`
   - 场景3~7: `.tab` / `.tc`
   - **建议:** 统一为 `.tab-item` / `.tab-content`

4. **🟡 字体大小不一致**
   - 场景1: 表格 12px, KPI 标签 12px
   - 场景3~7: 表格 11px, KPI 标签 10px
   - **建议:** 统一为 12px (表格) / 11px (标签)

### 3.2 6个KPI详情页布局风格一致性对比

**检查对象:** `xiyi-kpi-fpy/mag/abnormal/iqc/pmp/coq-detail.html`

| 维度 | FPY | 磁物 | 异常料 | IQC | PMP | COQ |
|------|-----|------|--------|-----|-----|-----|
| CSS变量前缀 | `--bg/--card/--border` | 同左 | 同左 | 同左 | 同左 | 同左 |
| 3栏 stats 布局 | `stats > 3 × .st` | 同左 | 同左 | 同左 | 同左 | 同左 |
| 趋势图 card | 有 | 有 | 有 | 有 | 有 | 有 |
| grid-2 布局 | 有 (产线对比) | 有 (设备地图) | 有 (饼图+库龄) | 有 (供应商+不合格) | 有 (工序+缺陷) | 有 (结构+趋势) |
| 分解维度框 | ❌ 无 | 有 | ❌ 无 | 有 | 有 | 有 |
| header 副标题 | ❌ 无 | 有 | 有 | 有 | 有 | 有 |
| 预警条/提示框 | `alert-bar` ✓ | ❌ 无 | ❌ 无 | ❌ 无 | `alert-bar` ✓ | ❌ 无 |
| 返回按钮样式 | `btn` ✓ | 同左 | 同左 | 同左 | 同左 | 同左 |

**🟡 发现问题:**

1. **P2 · FPY 和 异常料 详情页缺少 "分解维度" 框**，其他4个页面都有。建议统一添加。
2. **P2 · 磁物/异常料/IQC/PMP/COQ 有副标题而 FPY 没有。** 建议统一。
3. **P2 · 预警条(alert-bar) 仅在 FPY 和 PMP 存在**，其他4个缺失。建议统一添加（如果对应指标有告警）。
4. **FPY 的 header 缺少 `.sub` 副标题行。** 建议补上:"品质专员 · 在线一次检验合格率监控"。

---

## 四、完整问题清单 (P0/P1/P2)

### 🔴 P0 — 必须立即修复

| # | 问题 | 文件 | 修复建议 |
|---|------|------|---------|
| 0-1 | **所有 fetch 缺少 X-API-Key header**（~51处） | 所有 HTML 文件 | 统一 `apiFetch()` 包装函数 |
| 0-2 | **工作台右侧面板空数据时显示空白** | `xiyi-quality-workbench.html` L:290-340 | map 前检查 `alerts/tasks/news.length === 0`，输出"暂无xxx" |
| 0-3 | **场景管理页空列表白屏** | `xiyi-scenes-manager.html` L:73 | 添加空状态判断 |

### 🟡 P1 — 高优先级

| # | 问题 | 文件 | 修复建议 |
|---|------|------|---------|
| 1-1 | **KPI 详情页6个均硬编码 mock 数据，无 API 集成** | `xiyi-kpi-fpy/mag/abnormal/iqc/pmp/coq-detail.html` | 添加 `loadKpiData()` API 调用 + 空状态兜底 |
| 1-2 | **场景全景页1-7均为硬编码，无 API 集成** | `xiyi-full-scene*.html` | 同上，添加 API 调用 |
| 1-3 | **AI分析页面缺少 traceId 时无限 loading** | `xiyi-ai-analysis.html` | 检查 `_traceId` 为空时直接显示提示 |
| 1-4 | **AI分析页面 API 返回空数据时空白** | `xiyi-ai-analysis.html` L:107-192 | 每个渲染前检查数据非空 |
| 1-5 | **诊断页面步骤数据异常时白屏** | `xiyi-diagnose.html` L:78-106 | catch 已有，但空数据时需友好展示 |
| 1-6 | **预警管理页（空数组）显示白屏** | `xiyi-alerts.html` | 已有部分处理，确认覆盖全部 case |
| 1-7 | **系统配置页空数据（场景/指标/规则）白屏** | `xiyi-config-console.html` | 列表渲染前空数组判断 |

### 🟢 P2 — 视觉一致性优化

| # | 问题 | 文件 | 修复建议 |
|---|------|------|---------|
| 2-1 | CSS 变量名场景1 vs 场景2~7 不统一 | `xiyi-full-scene.html` vs `*full-scene-2~7.html` | 统一为 `--bg/--card/--border` 或 `--bg-primary/--bg-card/--border-color` |
| 2-2 | AI 摘要框类名不统一 (ai-summary-box/ai-box/.ai) | 全部 `full-scene*.html` | 统一为 `.ai-summary-box` |
| 2-3 | Tab 类名不统一 (fpy-tab-item/.tab) | 场景1-2 vs 场景3-7 | 统一为 `.tab-item`/`.tab-content` |
| 2-4 | 场景页表格/标签字体大小不一致（12px vs 11px） | 全部 scene 页 | 统一表格 12px, 标签 11px |
| 2-5 | FPY 详情页缺少副标题和分解维度框 | `xiyi-kpi-fpy-detail.html` | 参考 IQC/PMP 模板添加 |
| 2-6 | 异常料详情页缺少分解维度框 | `xiyi-kpi-abnormal-detail.html` | 参考 IQC 模板添加 |
| 2-7 | 磁物/异常料/IQC/COQ 缺少预警条 | 对应的 KPI 详情页 | 根据指标告警状态添加 alert-bar |
| 2-8 | FPY 详情页 header 缺少 `.sub` 副标题 | `xiyi-kpi-fpy-detail.html` | 添加 "品质专员 · 在线一次检验合格率监控" |
| 2-9 | 后端 Python 文件中 f-string 中的 `{` 转义问题 | `xiyi_server.py` | 检查 `message` 字段中的 bracket 转义 (`{{` 应为 `{`) |

---

## 五、修复实施建议

### 优先级顺序
1. **P0 (立即):** 统一添加 X-API-Key + 空状态兜底
2. **P1 (本周):** API 集成至 KPI 详情页 + 场景页
3. **P2 (后续迭代):** 视觉一致化

### 最佳实践
```javascript
// 1. 统一的 API 包装 (建议放 xiyi-quality-workbench.html 顶部)
const API_BASE = '/api/v1/xiyi';
async function xiyiFetch(path, options = {}) {
  const headers = { 'X-API-Key': 'xiyi-default-dev-key' };
  if (options.headers) Object.assign(headers, options.headers);
  options.headers = headers;
  return fetch(API_BASE + path, options);
}

// 2. 统一空状态渲染
function renderEmpty(container, msg = '暂无数据') {
  container.innerHTML = `<div class="empty-state">📭 ${msg}</div>`;
}

// 3. 统一三态模式
async function loadWithStates(container, fetcher, renderer, emptyMsg) {
  container.innerHTML = '<div class="loading">加载中...</div>';
  try {
    const data = await fetcher();
    if (!data || data.length === 0) {
      renderEmpty(container, emptyMsg);
    } else {
      renderer(data);
    }
  } catch(e) {
    container.innerHTML = `<div class="error">❌ 加载失败: ${e.message}</div>`;
  }
}

// 4. 通用 API Key (补充到后端)
// xiyi_server.py: 添加鉴权中间件
const API_KEY = 'xiyi-default-dev-key';  // TODO: 生产环境轮换
```
