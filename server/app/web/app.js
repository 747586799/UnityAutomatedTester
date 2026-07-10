/* ======== 全局状态 ======== */
let autoRefreshInterval = null;
let currentDetailId = null;
let currentDetailIsGroupHistory = false;
let refreshTimerRunning = false;
let automationInstanceCount = 0;
let _selectedHistoryIds = new Set();
let _historyPage = 1;
let _historyPageSize = 20;
let _historyTotal = 0;
let _historyTotalPages = 0;

/* ======== 启动时初始化 ======== */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  fetchAgents();
  fetchGroups();
  startAutoRefresh();
  switchTab('instances');
});

/* ======== 选项卡 ======== */
const tabTitles = {
  instances: '实例组',
  agents: 'Agent 状态',
  automation: '自动任务',
  tools: '其它工具',
  history: '执行历史',
};

function switchTab(tabName) {
  for (const key of Object.keys(tabTitles)) {
    const tab = document.getElementById('tab-' + key);
    const panel = document.getElementById('panel-' + key);
    const active = key === tabName;

    if (tab) {
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    }

    if (panel) {
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    }
  }

  const title = document.getElementById('page-title');
  if (title) title.textContent = tabTitles[tabName] || tabTitles.instances;

  if (tabName === 'instances') fetchGroups();
  if (tabName === 'agents') fetchAgents();
  if (tabName === 'automation') fetchAutomationTasks();
  if (tabName === 'history') fetchGroupHistory();
}

/* ======== Agent 状态 ======== */
async function fetchAgents() {
  try {
    const agents = await apiGet('/api/agents');
    renderAgents(agents);
  } catch (e) {
    showToast('获取 Agent 状态失败: ' + e.message, 'error');
  }
}

function renderAgents(agents) {
  const container = document.getElementById('agent-list');
  if (!container) return;
  if (!agents || agents.length === 0) {
    container.innerHTML = '<div class="empty">暂无 Agent 连接</div>';
    return;
  }

  const onlineCount = agents.filter(a => a.state === 'online' || a.state === 'busy').length;
  const totalSlots = agents.reduce((sum, a) => sum + (a.capabilities?.project_slots || []).length, 0);
  const idleSlots = agents.reduce((sum, a) => sum + (a.capabilities?.project_slots || []).filter(s => s.state === 'idle').length, 0);

  let html = `<section class="agent-hero">
    <div>
      <p class="eyebrow">Distributed Test Fleet</p>
      <h3>Agent 资源池</h3>
      <p>已连接 ${onlineCount}/${agents.length} 台 Agent，${idleSlots}/${totalSlots} 个项目实例空闲。</p>
    </div>
    <div class="agent-hero-stats">
      <span><strong>${onlineCount}</strong> 在线</span>
      <span><strong>${idleSlots}</strong> 空闲</span>
      <span><strong>${totalSlots - idleSlots}</strong> 占用</span>
    </div>
  </section><div class="agent-grid">`;

  for (const agent of agents) {
    const slots = agent.capabilities?.project_slots || [];
    const idle = slots.filter(s => s.state === 'idle').length;
    const running = slots.filter(s => s.state === 'running' || s.state === 'reserved').length;
    const total = slots.length;
    const available = idle > 0 && agent.state !== 'disconnected';
    const slotCards = renderAgentSlotCards(slots);
    html += `<article class="agent-card ${available ? 'agent-card-ready' : 'agent-card-busy'}">
      <div class="agent-card-head">
        <div>
          <div class="agent-name">${escapeHtml(agent.agent_id)}</div>
          <div class="agent-subtitle">${escapeHtml(agent.hostname || '-')} · ${escapeHtml(agent.ip || '-')}</div>
        </div>
        <span class="state-badge state-${escapeHtml(agent.state)}">${escapeHtml(agent.state)}</span>
      </div>
      <div class="agent-metrics">
        <div><strong>${idle}/${total}</strong><span>空闲实例</span></div>
        <div><strong>${agent.running_count || running}</strong><span>运行中</span></div>
        <div><strong>${formatTime(agent.last_heartbeat_time)}</strong><span>最后心跳</span></div>
      </div>
      <div class="agent-server-id">server_id: ${escapeHtml(agent.server_id || '-')}</div>
      <div class="agent-slots">${slotCards}</div>
    </article>`;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderAgentSlotCards(slots) {
  if (!slots || slots.length === 0) return '<div class="agent-empty-slots">未配置项目实例</div>';
  return slots.map(slot => {
    const idle = slot.state === 'idle';
    return `<div class="agent-slot ${idle ? 'agent-slot-idle' : 'agent-slot-busy'}">
      <div>
        <strong>${escapeHtml(slot.slot_id)}</strong>
        <span>${escapeHtml(slot.project_id)}</span>
      </div>
      <em>${escapeHtml(slot.state)}</em>
    </div>`;
  }).join('');
}

function formatTime(value) {
  if (!value) return '-';
  return String(value).substring(0, 19).replace('T', ' ');
}

/* ======== 健康检查 ======== */
async function checkHealth() {
  const badge = document.getElementById('health-badge');
  try {
    const res = await fetch('/health');
    if (res.ok) {
      badge.className = 'badge badge-ok';
      badge.textContent = 'ok';
    } else {
      badge.className = 'badge badge-error';
      badge.textContent = 'error';
    }
  } catch {
    badge.className = 'badge badge-error';
    badge.textContent = 'error';
  }
}

/* ======== 按钮 Loading ======== */
function setLoading(btn, loading) {
  if (!btn) return;
  if (loading) {
    btn.classList.add('btn-loading');
    btn.disabled = true;
  } else {
    btn.classList.remove('btn-loading');
    btn.disabled = false;
  }
}

/* ======== API 封装 ======== */
async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail || data.error?.message || JSON.stringify(data);
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function apiDelete(path) {
  const res = await fetch(path, { method: 'DELETE' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

/* ======== Toast ======== */
function showToast(message, type = '') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast' + (type ? ' toast-' + type : '');
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, 4000);
}

/* ======== 自动任务 ======== */
async function fetchAutomationTasks() {
  try {
    const tasks = await apiGet('/api/automation/tasks');
    renderAutomationTasks(tasks);
  } catch (e) {
    showToast('获取自动任务失败: ' + e.message, 'error');
  }
}

function renderAutomationTasks(tasks) {
  const container = document.getElementById('automation-list');
  if (!container) return;
  if (!tasks || tasks.length === 0) {
    container.innerHTML = '<div class="empty">暂无自动任务</div>';
    return;
  }
  let html = '<div class="automation-grid">';
  for (const task of tasks) {
    html += `<article class="agent-card">
      <div class="agent-card-head">
        <div>
          <div class="agent-name">${escapeHtml(task.name)}</div>
          <div class="agent-subtitle">${escapeHtml(task.project_id)} · ${task.instances?.length || 0} 实例 · 间隔 ${task.interval_seconds}s</div>
        </div>
        <span class="state-badge state-${escapeHtml(task.state)}">${escapeHtml(task.state)}</span>
      </div>
      <div class="agent-metrics">
        <div><strong>${task.current_run_count || 0}</strong><span>已运行</span></div>
        <div><strong>${task.max_runs || '∞'}</strong><span>最大轮次</span></div>
        <div><strong>${formatTime(task.next_run_time)}</strong><span>下次运行</span></div>
      </div>
      <div class="agent-server-id">group: ${escapeHtml(task.last_group_id || '-')}</div>
      ${task.last_error ? `<div class="error-box" style="margin:8px 0">${escapeHtml(task.last_error)}</div>` : ''}
      <div class="form-actions">
        <button type="button" class="btn-sm" onclick="startAutomationTask('${task.task_id}')">启动</button>
        <button type="button" class="btn-sm" onclick="stopAutomationTask('${task.task_id}')">停止</button>
        <button type="button" class="btn-sm" onclick="openAutomationDetail('${task.task_id}')">详情</button>
        <button type="button" class="btn-sm" onclick="deleteAutomationTask('${task.task_id}')">删除</button>
      </div>
    </article>`;
  }
  html += '</div>';
  container.innerHTML = html;
}

async function startAutomationTask(taskId) {
  try {
    await apiPost(`/api/automation/tasks/${taskId}/start`, {});
    showToast('自动任务已启动', 'success');
    fetchAutomationTasks();
  } catch (e) {
    showToast('启动自动任务失败: ' + e.message, 'error');
  }
}

async function stopAutomationTask(taskId) {
  try {
    await apiPost(`/api/automation/tasks/${taskId}/stop`, {});
    showToast('自动任务已停止', 'success');
    fetchAutomationTasks();
  } catch (e) {
    showToast('停止自动任务失败: ' + e.message, 'error');
  }
}

async function deleteAutomationTask(taskId) {
  if (!confirm('确认删除自动任务？')) return;
  try {
    await apiDelete(`/api/automation/tasks/${taskId}`);
    showToast('自动任务已删除', 'success');
    fetchAutomationTasks();
  } catch (e) {
    showToast('删除自动任务失败: ' + e.message, 'error');
  }
}

async function openAutomationCreateDialog() {
  const modal = document.getElementById('automation-modal');
  modal.hidden = false;
  automationInstanceCount = 0;
  document.getElementById('automation-instances').innerHTML = '';
  document.getElementById('automation-error').hidden = true;

  let template = {};
  try {
    template = await apiGet('/api/automation/task-template');
  } catch (e) {
    template = {};
  }
  fillAutomationForm(template);
}

function closeAutomationDialog() {
  document.getElementById('automation-modal').hidden = true;
}

function fillAutomationForm(template) {
  const id = (sel) => document.getElementById(sel);
  id('auto-name').value = template.name || 'Auto Task';
  id('auto-project-id').value = template.project_id || 'Project-One';
  id('auto-interval').value = template.interval_seconds ?? 300;
  id('auto-max-runs').value = template.max_runs ?? '';
  id('auto-battle-log-root').value = template.battle_log_root || '';
  id('auto-group-name').value = template.group_name || template.name || 'Auto Group';
  id('auto-method').value = template.execute_method || 'HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest';
  id('auto-group-args').value = JSON.stringify(template.group_args || {}, null, 2);

  const instances = template.instances && template.instances.length > 0
    ? template.instances
    : [{ name: 'instance-1', args: {} }, { name: 'instance-2', args: {} }];
  for (const inst of instances) {
    addAutomationInstance(inst.name || '', JSON.stringify(inst.args || {}, null, 2));
  }
}

function addAutomationInstance(name, argsJson) {
  const container = document.getElementById('automation-instances');
  if (!container) return;
  const idx = automationInstanceCount++;
  const card = document.createElement('div');
  card.className = 'launch-instance-card automation-instance-card';
  card.id = 'automation-inst-' + idx;
  card.innerHTML = `
    <div class="card-header">
      <h5>实例 #${idx + 1}</h5>
      <button type="button" onclick="removeAutomationInstance(${idx})" class="btn-sm">删除</button>
    </div>
    <div class="form-group">
      <label for="auto-inst-name-${idx}">name <span class="json-badge">可选</span></label>
      <input type="text" id="auto-inst-name-${idx}" autocomplete="off" spellcheck="false" value="${escapeHtml(name || `instance-${idx + 1}`)}" style="font-family:inherit">
    </div>
    <div class="form-group">
      <label for="auto-inst-args-${idx}">args <span class="json-badge">JSON</span></label>
      <textarea id="auto-inst-args-${idx}" rows="6" spellcheck="false" autocomplete="off" style="font-family:'SF Mono',Consolas,monospace">${argsJson || '{}'}</textarea>
    </div>
    <div class="form-actions">
      <button type="button" onclick="formatAutomationInstArgs(${idx})" class="btn-sm">格式化 args</button>
    </div>
  `;
  container.appendChild(card);
}

function removeAutomationInstance(idx) {
  const card = document.getElementById('automation-inst-' + idx);
  if (card) card.remove();
}

function formatAutomationInstArgs(idx) {
  const ta = document.getElementById('auto-inst-args-' + idx);
  if (!ta) return;
  try {
    ta.value = JSON.stringify(JSON.parse(ta.value), null, 2);
  } catch (e) {
    showToast('格式化失败: ' + e.message, 'error');
  }
}

function collectAutomationFormPayload() {
  const groupArgsText = document.getElementById('auto-group-args').value.trim();
  const groupArgs = groupArgsText ? JSON.parse(groupArgsText) : {};
  const instances = [];
  for (const card of document.querySelectorAll('.automation-instance-card')) {
    const nameInput = card.querySelector('input[id^="auto-inst-name-"]');
    const argsTextarea = card.querySelector('textarea[id^="auto-inst-args-"]');
    instances.push({
      name: nameInput.value || null,
      args: JSON.parse(argsTextarea.value || '{}'),
    });
  }
  if (instances.length === 0) throw new Error('至少需要一个实例');
  return {
    name: document.getElementById('auto-name').value.trim(),
    project_id: document.getElementById('auto-project-id').value.trim(),
    execute_method: document.getElementById('auto-method').value.trim(),
    group_name: document.getElementById('auto-group-name').value.trim() || null,
    interval_seconds: Number(document.getElementById('auto-interval').value || 0),
    max_runs: document.getElementById('auto-max-runs').value ? Number(document.getElementById('auto-max-runs').value) : null,
    battle_log_root: document.getElementById('auto-battle-log-root').value.trim() || null,
    group_args: groupArgs,
    instances: instances,
  };
}

async function createAutomationTaskFromDialog(btn) {
  const errorBox = document.getElementById('automation-error');
  errorBox.hidden = true;
  setLoading(btn, true);
  try {
    const payload = collectAutomationFormPayload();
    if (!payload.name) throw new Error('任务名称不能为空');
    if (!payload.project_id) throw new Error('project_id 不能为空');
    if (!payload.execute_method) throw new Error('execute_method 不能为空');
    await apiPost('/api/automation/tasks', payload);
    closeAutomationDialog();
    showToast('自动任务已创建', 'success');
    fetchAutomationTasks();
  } catch (e) {
    errorBox.textContent = '创建自动任务失败: ' + e.message;
    errorBox.hidden = false;
    showToast('创建自动任务失败: ' + e.message, 'error');
  } finally {
    setLoading(btn, false);
  }
}

/* ======== 自动任务详情 ======== */
async function openAutomationDetail(taskId) {
  const modal = document.getElementById('automation-detail-modal');
  modal.hidden = false;
  document.getElementById('auto-detail-runs').innerHTML = '<div class="empty">加载中...</div>';
  try {
    const data = await apiGet('/api/automation/tasks/' + taskId);
    renderAutomationDetail(data);
  } catch (e) {
    showToast('获取任务详情失败: ' + e.message, 'error');
  }
}

function closeAutomationDetail() {
  document.getElementById('automation-detail-modal').hidden = true;
}

function renderAutomationDetail(data) {
  if (!data) return;
  const task = data.task;
  const summary = data.summary;
  const runs = data.runs || [];

  // ── Task config table ──
  const infoRows = [
    ['任务名称', task.name],
    ['task_id', task.task_id],
    ['project_id', task.project_id],
    ['execute_method', task.execute_method],
    ['group_name', task.group_name || '-'],
    ['间隔秒数', String(task.interval_seconds)],
    ['最大轮次', task.max_runs != null ? String(task.max_runs) : '无限'],
    ['已运行次数', String(task.current_run_count || 0)],
    ['战斗服日志', task.battle_log_root || '<span style="color:var(--color-text-muted)">未配置</span>'],
    ['状态', task.state],
    ['创建时间', task.created_time ? task.created_time.substring(0, 19).replace('T', ' ') : '-'],
  ];
  if (task.last_error) {
    infoRows.push(['last_error', '<span style="color:var(--color-danger)">' + escapeHtml(task.last_error) + '</span>']);
  }
  let infoHtml = '';
  for (const [key, val] of infoRows) {
    infoHtml += `<tr><td>${escapeHtml(key)}</td><td>${val}</td></tr>`;
  }
  document.getElementById('auto-detail-info').innerHTML = infoHtml;

  // ── Summary with pie charts ──
  const summaryEl = document.getElementById('auto-detail-summary');
  const totalRuns = summary.total_runs || 0;
  const successRuns = summary.success_runs || 0;
  const failRuns = summary.failed_runs || 0;
  const runSuccessRate = totalRuns > 0 ? (summary.run_success_rate || 0) : 0;
  const runFailRate = totalRuns > 0 ? (summary.run_failed_rate || 0) : 0;

  const checkedRuns = summary.report_checked_runs || 0;
  const reportSuccess = summary.report_success_runs || 0;
  const reportFail = summary.report_failed_runs || 0;
  const reportSuccessRate = checkedRuns > 0 ? (summary.report_success_rate || 0) : 0;
  const reportFailRate = checkedRuns > 0 ? (summary.report_failed_rate || 0) : 0;

  const battleChecked = summary.battle_checked_runs || 0;
  const battleMatch = summary.battle_match_runs || 0;
  const battleMismatch = summary.battle_mismatch_runs || 0;
  const battleMatchRate = battleChecked > 0 ? (summary.battle_match_rate || 0) : 0;
  const battleMismatchRate = battleChecked > 0 ? (summary.battle_mismatch_rate || 0) : 0;

  summaryEl.innerHTML = `
    <div class="summary-card">
      <h4>执行统计</h4>
      <div class="summary-numbers">
        <div><strong>${totalRuns}</strong><span>总执行</span></div>
        <div><strong>${successRuns}</strong><span>成功</span></div>
        <div><strong>${failRuns}</strong><span>失败</span></div>
      </div>
      ${totalRuns > 0 ? `
        <div class="pie-chart-wrapper">
          <div class="pie-chart" style="background: conic-gradient(
            var(--color-success) 0% ${(runSuccessRate * 100).toFixed(1)}%,
            var(--color-danger) ${(runSuccessRate * 100).toFixed(1)}% 100%
          )"></div>
          <div class="pie-legend">
            <span><span class="legend-dot success"></span>成功 ${(runSuccessRate * 100).toFixed(1)}%</span>
            <span><span class="legend-dot danger"></span>失败 ${(runFailRate * 100).toFixed(1)}%</span>
          </div>
        </div>` : '<div style="color:var(--color-text-muted);font-size:13px;margin-top:8px">暂无执行数据</div>'}
    </div>
    <div class="summary-card">
      <h4>Report 验证</h4>
      <div class="summary-numbers">
        <div><strong>${checkedRuns}</strong><span>已验证</span></div>
        <div><strong>${reportSuccess}</strong><span>一致</span></div>
        <div><strong>${reportFail}</strong><span>不一致</span></div>
      </div>
      ${checkedRuns > 0 ? `
        <div class="pie-chart-wrapper">
          <div class="pie-chart" style="background: conic-gradient(
            var(--color-success) 0% ${(reportSuccessRate * 100).toFixed(1)}%,
            var(--color-danger) ${(reportSuccessRate * 100).toFixed(1)}% 100%
          )"></div>
          <div class="pie-legend">
            <span><span class="legend-dot success"></span>一致 ${(reportSuccessRate * 100).toFixed(1)}%</span>
            <span><span class="legend-dot danger"></span>不一致 ${(reportFailRate * 100).toFixed(1)}%</span>
          </div>
        </div>` : '<div style="color:var(--color-text-muted);font-size:13px;margin-top:8px">暂无验证数据</div>'}
    </div>
    <div class="summary-card">
      <h4>战斗服验证</h4>
      <div class="summary-numbers">
        <div><strong>${battleChecked}</strong><span>已验证</span></div>
        <div><strong>${battleMatch}</strong><span>一致</span></div>
        <div><strong>${battleMismatch}</strong><span>不一致</span></div>
      </div>
      ${battleChecked > 0 ? `
        <div class="pie-chart-wrapper">
          <div class="pie-chart" style="background: conic-gradient(
            var(--color-success) 0% ${(battleMatchRate * 100).toFixed(1)}%,
            var(--color-danger) ${(battleMatchRate * 100).toFixed(1)}% 100%
          )"></div>
          <div class="pie-legend">
            <span><span class="legend-dot success"></span>一致 ${(battleMatchRate * 100).toFixed(1)}%</span>
            <span><span class="legend-dot danger"></span>不一致 ${(battleMismatchRate * 100).toFixed(1)}%</span>
          </div>
        </div>` : '<div style="color:var(--color-text-muted);font-size:13px;margin-top:8px">暂无战斗服数据</div>'}
    </div>`;

  // ── Run records table ──
  const runsEl = document.getElementById('auto-detail-runs');
  if (!runs || runs.length === 0) {
    runsEl.innerHTML = '<div class="empty">暂无执行记录</div>';
    return;
  }

  let runsHtml = `<table class="auto-runs-table">
    <thead><tr>
      <th>运行 ID</th>
      <th>组名称</th>
      <th>状态</th>
      <th>进度</th>
      <th>Report</th>
      <th>战斗服</th>
      <th>开始时间</th>
      <th>归档</th>
    </tr></thead><tbody>`;

  for (const run of runs) {
    const runStateClass = 'state-' + run.state;
    const progressText = run.completed + '/' + run.total;
    let reportBadge = '<span class="report-same report-same-unknown">未知</span>';
    if (run.report_same === true) reportBadge = '<span class="report-same report-same-yes">通过</span>';
    else if (run.report_same === false) reportBadge = '<span class="report-same report-same-no">失败</span>';

    let battleBadge = '<span class="report-same report-same-unknown">未知</span>';
    if (run.battle_match === true) battleBadge = '<span class="report-same report-same-yes">一致</span>';
    else if (run.battle_match === false) battleBadge = '<span class="report-same report-same-no">差异</span>';

    // Archive link
    let archiveLink = '-';
    if (run.history_id && !run.history_missing) {
      archiveLink = `<a href="#" onclick="event.preventDefault();closeAutomationDetail();openGroupHistoryDetail('${escapeHtml(run.history_id)}')" style="color:var(--color-primary)">查看</a>`;
    } else if (run.history_missing) {
      archiveLink = '<span style="color:var(--color-text-muted)">缺失</span>';
    }

    const startedTime = run.started_time ? run.started_time.substring(0, 19).replace('T', ' ') : '-';

    runsHtml += `<tr>
      <td style="font-size:12px;color:var(--color-text-secondary)">${escapeHtml(run.run_id)}</td>
      <td><strong>${escapeHtml(run.group_name || run.group_id)}</strong></td>
      <td><span class="state-badge ${runStateClass}">${run.state}</span></td>
      <td>${progressText}</td>
      <td>${reportBadge}</td>
      <td>${battleBadge}</td>
      <td style="color:var(--color-text-secondary)">${startedTime}</td>
      <td>${archiveLink}</td>
    </tr>`;
  }

  runsHtml += '</tbody></table>';
  runsEl.innerHTML = runsHtml;
}

/* ======== 手动注册 ======== */
async function registerManual(btn) {
  const errorBox = document.getElementById('manual-error');
  errorBox.hidden = true;
  setLoading(btn, true);

  const instanceId = document.getElementById('inp-manual-id').value.trim();
  if (!instanceId) {
    errorBox.textContent = 'instance_id 不能为空';
    errorBox.hidden = false;
    setLoading(btn, false);
    return;
  }

  try {
    await apiPost('/api/unity/manual', {
      instance_id: instanceId,
      project_path: 'manual-unity-editor',
    });
    showToast('注册成功: ' + instanceId, 'success');
    switchTab('instances');
  } catch (e) {
    errorBox.textContent = '注册失败: ' + e.message;
    errorBox.hidden = false;
    showToast('注册失败: ' + e.message, 'error');
  } finally {
    setLoading(btn, false);
  }
}

/* ======== 获取组列表 ======== */
async function fetchGroups() {
  try {
    const groups = await apiGet('/api/unity/groups');
    renderGroups(groups);
  } catch (e) {
    showToast('获取组列表失败: ' + e.message, 'error');
  }
}

/* ======== 渲染组列表 ======== */
function renderGroups(groups) {
  const container = document.getElementById('instance-list');
  if (!groups || groups.length === 0) {
    container.innerHTML = '<div class="empty">暂无活跃组或实例</div>';
    return;
  }

  let html = '';
  for (const group of groups) {
    const collapsed = group.state === 'running' ? '' : 'collapsed';
    let statusColor = '';
    let statusText = '';
    if (group.state === 'running') {
      statusText = group.active + ' 运行中';
    } else if (group.state === 'completed') {
      statusText = '全部完成';
    } else {
      statusText = group.completed + '/' + group.total + ' 完成, ' + group.failed + ' 失败';
    }

    html += `<div class="group-section ${collapsed}">
      <div class="group-header" tabindex="0" role="button" onclick="toggleGroup(this)" onkeydown="if(event.key==='Enter'||event.key===' ')toggleGroup(this)">
        <div class="group-header-info">
          <h4>${escapeHtml(group.group_name || group.group_id)} <span style="font-size:12px;color:var(--color-text-muted);font-weight:400">(${group.group_id})</span></h4>
          <span class="state-badge state-${group.state === 'running' ? 'running' : (group.failed > 0 ? 'failed' : 'completed')}">${group.state}</span>
          <span style="font-size:12px;color:var(--color-text-secondary)">${statusText}</span>
          <span style="font-size:12px;color:var(--color-text-secondary)">${group.total} 个实例</span>
        </div>
        <span class="group-header-chevron">▼</span>
      </div>
      <div class="group-body">
        <table class="group-instance-table">
          <thead><tr>
            <th>名称</th>
            <th>ID</th>
            <th>状态</th>
            <th>进度</th>
            <th>进程</th>
            <th>Agent / Slot</th>
          </tr></thead>
          <tbody>`;

    for (const inst of group.instances) {
      const stateClass = 'state-' + inst.state;
      const percent = Math.round((inst.progress || 0) * 100);
      let progressClass = 'progress-fill';
      if (inst.state === 'running') progressClass += ' running';
      else if (inst.state === 'completed') progressClass += ' completed';
      else if (inst.state === 'failed') progressClass += ' failed';

      let stateHtml = `<span class="state-badge ${stateClass}">${inst.state}</span>`;
      if (inst.ready_id != null && !inst.start_signal_sent) {
        stateHtml += ` <span style="font-size:11px;color:var(--color-text-muted)">#${inst.ready_id}</span>`;
      } else if (inst.start_signal_sent) {
        stateHtml += ` <span style="font-size:11px;color:var(--color-primary)">started</span>`;
      }

      html += `<tr onclick="openDetail('${inst.id}')" tabindex="0" role="button" onkeydown="if(event.key==='Enter'||event.key===' ')openDetail('${inst.id}')">
        <td><strong>${escapeHtml(inst.launch_name || '-')}</strong></td>
        <td style="font-size:12px;color:var(--color-text-secondary)">${inst.id}</td>
        <td>${stateHtml}</td>
        <td class="progress-cell">
          <div class="progress-bar-wrap">
            <div class="progress-bar">
              <div class="${progressClass}" style="width:${percent}%"></div>
            </div>
            <span class="progress-text">${percent}%</span>
          </div>
        </td>
        <td>${inst.process_id || '-'}</td>
        <td style="font-size:12px;color:var(--color-text-secondary)">${escapeHtml(inst.agent_id || '-')} / ${escapeHtml(inst.project_slot_id || '-')}</td>
      </tr>`;
    }

    html += `</tbody></table></div></div>`;
  }

  container.innerHTML = html;
}

function toggleGroup(header) {
  const section = header.closest('.group-section');
  if (section) section.classList.toggle('collapsed');
}

/* ======== 详情弹出 ======== */
async function openDetail(instanceId) {
  currentDetailId = instanceId;
  currentDetailIsGroupHistory = false;
  const overlay = document.getElementById('detail-overlay');
  overlay.classList.remove('is-group-mode', 'is-instance-from-group', 'is-history');
  overlay.hidden = false;
  document.getElementById('detail-back-btn').hidden = true;
  document.getElementById('detail-title').textContent = '实例详情 - ' + instanceId;
  document.getElementById('detail-error').hidden = true;
  // Live instance: show all sections including actions
  document.getElementById('detail-section-progress').style.display = '';
  document.getElementById('detail-section-logs').style.display = '';
  document.getElementById('detail-section-actions').style.display = '';
  document.getElementById('detail-section-result').style.display = '';
  await refreshDetail(instanceId);
}

function closeDetail(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('detail-overlay').hidden = true;
  document.getElementById('detail-overlay').classList.remove('is-group-mode', 'is-instance-from-group');
  document.getElementById('detail-back-btn').hidden = true;
  // Reset all sections to default (visible)
  document.getElementById('detail-section-progress').style.display = '';
  document.getElementById('detail-section-logs').style.display = '';
  document.getElementById('detail-section-actions').style.display = '';
  document.getElementById('detail-section-result').style.display = '';
  currentDetailId = null;
  currentDetailIsGroupHistory = false;
  _groupHistoryData = null;
}

/* ======== 刷新详情 ======== */
async function refreshDetail(instanceId) {
  try {
    const [instance, logResult] = await Promise.all([
      apiGet('/api/unity/' + instanceId),
      apiGet('/api/unity/' + instanceId + '/logs'),
    ]);
    renderDetailInfo(instance);
    renderDetailProgress(instance);
    renderDetailLogs(logResult.logs || []);
    renderDetailResult(instance);
  } catch (e) {
    showToast('获取详情失败: ' + e.message, 'error');
  }
}

function renderDetailInfo(instance) {
  const rows = [
    ['id', instance.id],
    ['state', instance.state],
    ['group_id', instance.group_id || '-'],
    ['group_name', instance.group_name || '-'],
    ['launch_name', instance.launch_name || '-'],
    ['launch_target', instance.launch_target || '-'],
    ['agent_id', instance.agent_id || '-'],
    ['project_id', instance.project_id || '-'],
    ['project_slot_id', instance.project_slot_id || '-'],
    ['process_id', instance.process_id != null ? String(instance.process_id) : '-'],
    ['project_path', instance.project_path],
    ['unity_executable_path', instance.unity_executable_path || '-'],
    ['execute_method', instance.execute_method],
    ['error_message', instance.error_message || '-'],
    ['start_time', instance.start_time || '-'],
    ['connected_time', instance.connected_time || '-'],
    ['end_time', instance.end_time || '-'],
    ['exit_code', instance.exit_code != null ? String(instance.exit_code) : '-'],
  ];

  if (instance.args && Object.keys(instance.args).length) {
    rows.push(['args', '<pre>' + escapeHtml(JSON.stringify(instance.args, null, 2)) + '</pre>']);
  }
  if (instance.launch_command && instance.launch_command.length) {
    rows.push(['launch_command', '<pre>' + escapeHtml(instance.launch_command.join(' \\\n')) + '</pre>']);
  }

  let html = '';
  for (const [key, val] of rows) {
    html += `<tr><td>${key}</td><td>${val}</td></tr>`;
  }
  document.getElementById('detail-info').innerHTML = html;
}

function renderDetailProgress(instance) {
  const percent = Math.round((instance.progress || 0) * 100);
  document.getElementById('detail-progress').innerHTML = `
    <div class="progress-bar-wrap" style="display:flex;align-items:center;gap:10px;padding:8px 0">
      <div class="progress-bar" style="flex:1;height:20px;border-radius:10px">
        <div class="progress-fill" style="width:${percent}%;height:100%;border-radius:10px"></div>
      </div>
      <span class="progress-text" style="font-size:14px;font-weight:600">${percent}%</span>
    </div>
    <div style="font-size:12px;color:#6b7280;margin-top:4px">状态: ${instance.state}</div>
  `;
}

function renderDetailLogs(logs) {
  const container = document.getElementById('detail-logs');
  if (!logs || logs.length === 0) {
    container.innerHTML = '<div class="empty">暂无日志</div>';
    return;
  }
  let html = '';
  for (const log of logs) {
    const level = (log.level || 'info').toLowerCase();
    html += `<div class="log-row log-${level}">
      <span class="log-time">${log.timestamp || ''}</span>
      <span class="log-level">${level}</span>
      <span class="log-message">${escapeHtml(log.message || '')}</span>
    </div>`;
  }
  container.innerHTML = html;
  container.scrollTop = container.scrollHeight;
}

function renderDetailResult(instance) {
  renderResultContent(instance.result, instance.result?.report);
}

function renderHistoryDetailInfo(record) {
  const s = record.summary;
  const rows = [
    ['original_id', s.original_id],
    ['state', s.state],
    ['project_path', s.project_path],
    ['execute_method', s.execute_method],
    ['process_id', s.process_id != null ? String(s.process_id) : '-'],
    ['start_time', s.start_time ? s.start_time.substring(0, 19).replace('T', ' ') : '-'],
    ['end_time', s.end_time ? s.end_time.substring(0, 19).replace('T', ' ') : '-'],
    ['archived_time', s.archived_time ? s.archived_time.substring(0, 19).replace('T', ' ') : '-'],
    ['error_message', s.error_message || '-'],
  ];
  if (record.unity_executable_path) rows.push(['unity_executable_path', record.unity_executable_path]);
  if (record.args && Object.keys(record.args).length) {
    rows.push(['args', '<pre>' + escapeHtml(JSON.stringify(record.args, null, 2)) + '</pre>']);
  }
  if (record.launch_command && record.launch_command.length) {
    rows.push(['launch_command', '<pre>' + escapeHtml(record.launch_command.join(' \\\n')) + '</pre>']);
  }
  let html = '';
  for (const [key, val] of rows) {
    html += `<tr><td>${key}</td><td>${val}</td></tr>`;
  }
  document.getElementById('detail-info').innerHTML = html;
}

function renderHistoryDetailResult(record, reportViewUrl) {
  renderResultContent(record.result, record.report, reportViewUrl);
}

function renderResultContent(result, report, reportViewUrl) {
  const box = document.getElementById('detail-result');
  if (!result && !report) {
    box.innerHTML = '<div class="empty">暂无结果</div>';
    return;
  }
  const resultWithoutReport = result ? { ...result } : null;
  if (resultWithoutReport) delete resultWithoutReport.report;
  let html = '';
  if (resultWithoutReport && Object.keys(resultWithoutReport).length > 0) {
    html += '<pre>' + escapeHtml(JSON.stringify(resultWithoutReport, null, 2)) + '</pre>';
  }
  if (report && reportViewUrl) {
    html += '<div style="margin-top:10px">';
    html += '<button class="btn" onclick="window.open(\'' + reportViewUrl.replace(/'/g, "\\'") + '\', \'_blank\')">查看 Report</button>';
    html += '</div>';
  }
  box.innerHTML = html || '<div class="empty">暂无结果</div>';
}

/* ======== 组历史 ======== */
async function fetchGroupHistory() {
  try {
    const data = await apiGet('/api/unity/history/groups?page=' + _historyPage + '&page_size=' + _historyPageSize);
    _historyTotal = data.total || 0;
    _historyTotalPages = data.total_pages || 0;
    renderGroupHistory(data.items || []);
    renderHistoryPagination();
  } catch (e) {
    showToast('获取组历史失败: ' + e.message, 'error');
  }
}

function goToHistoryPage(page) {
  if (page < 1 || page > _historyTotalPages) return;
  _historyPage = page;
  _selectedHistoryIds.clear();
  fetchGroupHistory();
}

function renderHistoryPagination() {
  const bar = document.getElementById('history-pagination');
  if (_historyTotalPages <= 1) {
    bar.hidden = true;
    return;
  }
  bar.hidden = false;
  document.getElementById('pagination-info').textContent =
    '共 ' + _historyTotal + ' 条，第 ' + _historyPage + '/' + _historyTotalPages + ' 页';
  document.getElementById('pagination-prev').disabled = _historyPage <= 1;
  document.getElementById('pagination-next').disabled = _historyPage >= _historyTotalPages;

  // Page number buttons
  const pagesEl = document.getElementById('pagination-pages');
  let pageBtns = '';
  const maxVis = 5;
  let startPage = Math.max(1, _historyPage - Math.floor(maxVis / 2));
  let endPage = Math.min(_historyTotalPages, startPage + maxVis - 1);
  if (endPage - startPage + 1 < maxVis) {
    startPage = Math.max(1, endPage - maxVis + 1);
  }
  for (let p = startPage; p <= endPage; p++) {
    const active = p === _historyPage ? ' class="pagination-active"' : '';
    pageBtns += '<button type="button" class="btn-sm' + active + '" onclick="goToHistoryPage(' + p + ')">' + p + '</button>';
  }
  pagesEl.innerHTML = pageBtns;
}

function renderGroupHistory(records) {
  const container = document.getElementById('history-groups-list');
  if (!records || records.length === 0) {
    container.innerHTML = '<div class="empty">暂无组历史记录</div>';
    return;
  }
  let html = `<table class="history-group-table">
    <thead><tr>
      <th style="width:40px;text-align:center">选择</th>
      <th>组名称</th>
      <th>状态</th>
      <th>进度</th>
      <th>Report 验证</th>
      <th>战斗服</th>
      <th>归档时间</th>
    </tr></thead><tbody>`;

  for (const rec of records) {
    const stateClass = 'state-' + rec.state;
    let reportBadge = '<span class="report-same report-same-unknown">未知</span>';
    if (rec.report_same === true) {
      reportBadge = '<span class="report-same report-same-yes">全部相同</span>';
    } else if (rec.report_same === false) {
      reportBadge = '<span class="report-same report-same-no">不一致</span>';
    }
    const progressText = rec.completed + '/' + rec.total;
    const historyId = rec.history_id || rec.group_id;
    const checked = _selectedHistoryIds.has(historyId);

    let battleBadge = '<span class="report-same report-same-unknown">未知</span>';
    if (rec.battle_match === true) {
      battleBadge = '<span class="report-same report-same-yes">一致</span>';
    } else if (rec.battle_match === false) {
      battleBadge = '<span class="report-same report-same-no">差异</span>';
    }

    html += `<tr onclick="if(event.target.tagName!=='INPUT')openGroupHistoryDetail('${historyId}')" tabindex="0" role="button" onkeydown="if(event.key==='Enter'||event.key===' ')openGroupHistoryDetail('${historyId}')">
      <td style="width:40px;text-align:center;cursor:default">
        <input type="checkbox" class="history-checkbox" value="${historyId}" ${checked ? 'checked' : ''} onchange="toggleHistorySelection('${historyId}', this.checked)">
      </td>
      <td><strong>${escapeHtml(rec.group_name || rec.group_id)}</strong></td>
      <td><span class="state-badge ${stateClass}" title="${rec.state}">${rec.state}</span></td>
      <td>${progressText}</td>
      <td>${reportBadge}</td>
      <td>${battleBadge}</td>
      <td style="color:var(--color-text-secondary)">${rec.archived_time ? rec.archived_time.substring(0, 19).replace('T', ' ') : '-'}</td>
    </tr>`;
  }

  html += '</tbody></table>';
  container.innerHTML = html;
  updateHistorySelectionCount();
}

/* ======== 历史批量删除 ======== */
function toggleHistorySelection(historyId, checked) {
  if (checked) {
    _selectedHistoryIds.add(historyId);
  } else {
    _selectedHistoryIds.delete(historyId);
  }
  updateHistorySelectionCount();
}

function selectAllHistory() {
  const checkboxes = document.querySelectorAll('.history-checkbox');
  for (const cb of checkboxes) {
    cb.checked = true;
    _selectedHistoryIds.add(cb.value);
  }
  updateHistorySelectionCount();
}

function unselectAllHistory() {
  const checkboxes = document.querySelectorAll('.history-checkbox');
  for (const cb of checkboxes) {
    cb.checked = false;
  }
  _selectedHistoryIds.clear();
  updateHistorySelectionCount();
}

function updateHistorySelectionCount() {
  const el = document.getElementById('history-selected-count');
  if (el) {
    const count = _selectedHistoryIds.size;
    el.textContent = count > 0 ? '已选择 ' + count + ' 项' : '';
  }
}

async function deleteSelectedHistory() {
  const ids = Array.from(_selectedHistoryIds);
  if (ids.length === 0) {
    showToast('请先选择要删除的历史记录', 'error');
    return;
  }
  if (!confirm('确认删除选中的 ' + ids.length + ' 条历史记录？此操作不可恢复。')) return;
  try {
    const res = await fetch('/api/unity/history/groups', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history_ids: ids }),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || JSON.stringify(result));
    const deleted = result.deleted || [];
    const missing = result.missing || [];
    const failed = result.failed || [];
    let msg = '删除完成: ' + deleted.length + ' 条成功';
    if (missing.length > 0) msg += ', ' + missing.length + ' 条不存在';
    if (failed.length > 0) msg += ', ' + failed.length + ' 条失败';
    showToast(msg, deleted.length > 0 ? 'success' : 'error');
    _selectedHistoryIds.clear();
    fetchGroupHistory();
  } catch (e) {
    showToast('批量删除失败: ' + e.message, 'error');
  }
}

/* ======== 组历史详情 ======== */
let _groupHistoryData = null;

async function openGroupHistoryDetail(historyId) {
  const overlay = document.getElementById('detail-overlay');
  currentDetailIsGroupHistory = true;
  overlay.classList.remove('is-instance-from-group', 'is-history');
  overlay.classList.add('is-group-mode');
  overlay.hidden = false;
  // Group history: hide progress, logs, actions — only show info + result
  document.getElementById('detail-section-progress').style.display = 'none';
  document.getElementById('detail-section-logs').style.display = 'none';
  document.getElementById('detail-section-actions').style.display = 'none';
  document.getElementById('detail-section-result').style.display = '';

  try {
    _groupHistoryData = await apiGet('/api/unity/history/groups/' + historyId);
    renderGroupHistoryDetail();
  } catch (e) {
    showToast('获取组历史详情失败: ' + e.message, 'error');
  }
}

async function refreshGroupHistoryDetail(historyId) {
  if (currentDetailIsGroupHistory && _groupHistoryData) {
    try {
      _groupHistoryData = await apiGet('/api/unity/history/groups/' + historyId);
      renderGroupHistoryDetail();
    } catch (e) {
      showToast('刷新组历史详情失败: ' + e.message, 'error');
    }
  }
}

function renderGroupHistoryDetail() {
  const record = _groupHistoryData;
  if (!record) return;

  const s = record.summary;
  const overlay = document.getElementById('detail-overlay');
  overlay.classList.add('is-group-mode');
  overlay.classList.remove('is-instance-from-group');

  document.getElementById('detail-title').textContent = '组历史 - ' + (s.group_name || s.group_id);
  document.getElementById('detail-back-btn').hidden = false;
  document.getElementById('detail-section-progress').style.display = 'none';
  document.getElementById('detail-section-logs').style.display = 'none';
  document.getElementById('detail-section-actions').style.display = 'none';
  document.getElementById('detail-error').hidden = true;

  // Info table
  let html = '<table class="history-group-detail-table">';
  html += `<tr><td>Group ID</td><td>${escapeHtml(s.group_id)}</td></tr>`;
  html += `<tr><td>Group Name</td><td>${escapeHtml(s.group_name || '-')}</td></tr>`;
  html += `<tr><td>State</td><td>${s.state}</td></tr>`;
  html += `<tr><td>Total</td><td>${s.total}</td></tr>`;
  html += `<tr><td>Completed</td><td>${s.completed}</td></tr>`;
  html += `<tr><td>Failed</td><td>${s.failed}</td></tr>`;
  html += `<tr><td>Archived</td><td>${s.archived_time ? s.archived_time.substring(0, 19).replace('T', ' ') : '-'}</td></tr>`;
  html += '</table>';
  document.getElementById('detail-info').innerHTML = html;

  // Report compare section
  let resultHtml = '';

  if (record.report_compare) {
    const rc = record.report_compare;
    const sameText = rc.same ? '全部相同' : '存在差异';
    const sameClass = rc.same ? 'report-same-yes' : 'report-same-no';
    resultHtml += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">';
    resultHtml += '<h4 style="font-size:14px;margin:0">Report 验证: <span class="report-same ' + sameClass + '">' + sameText + '</span></h4>';

    // Diff button — opens compare page with instance selectors
    if (rc.items && rc.items.length >= 2) {
      const instanceIds = rc.items.map(it => it.instance_id).join(',');
      resultHtml += `<button class="btn-sm" onclick="openReportDiff('${s.history_id || s.group_id}', '${instanceIds}')">对比</button>`;
    }
    resultHtml += '</div>';

    resultHtml += '<table class="compare-instances-table"><thead><tr><th>实例</th><th>SHA256</th><th>一致</th></tr></thead><tbody>';
    for (const item of rc.items) {
      const statusClass = item.same_as_baseline ? 'report-same-yes' : 'report-same-no';
      const statusText = item.same_as_baseline ? '是' : '否';
      resultHtml += `<tr>
        <td>${escapeHtml(item.launch_name || item.instance_id)}</td>
        <td style="font-size:11px">${item.sha256.substring(0, 16)}...</td>
        <td><span class="report-same ${statusClass}">${statusText}</span></td>
      </tr>`;
    }
    resultHtml += '</tbody></table>';
  } else {
    resultHtml += '<div style="margin-top:8px;color:var(--color-text-muted)">组内实例数不足或缺失 report，无法验证。</div>';
  }

  // Instance list with clickable rows
  resultHtml += '<h4 style="margin-top:20px;font-size:14px;margin-bottom:10px">组内实例</h4>';
  if (record.instances && record.instances.length > 0) {
    resultHtml += '<table class="compare-instances-table" style="margin-top:8px"><thead><tr><th>名称</th><th>状态</th><th>操作</th></tr></thead><tbody>';
    for (const inst of record.instances) {
      const stateClass = 'state-' + inst.state;
      resultHtml += `<tr tabindex="0" role="button" onkeydown="if(event.key==='Enter')openGroupInstanceHistory('${s.history_id || s.group_id}', '${inst.original_id}')">
        <td><strong>${escapeHtml(inst.original_id)}</strong></td>
        <td><span class="state-badge ${stateClass}">${inst.state}</span></td>
        <td><button class="btn-sm" onclick="event.stopPropagation();openGroupInstanceHistory('${s.history_id || s.group_id}', '${inst.original_id}')">查看详情</button></td>
      </tr>`;
    }
    resultHtml += '</tbody></table>';
  }

  // Battle compare section
  resultHtml += '<h4 style="margin-top:20px;font-size:14px;margin-bottom:10px">战斗服验证</h4>';
  if (record.battle_compare) {
    const bc = record.battle_compare;
    if (bc.battle_log_missing) {
      resultHtml += '<div style="color:var(--color-text-muted);margin-top:6px">部分实例的 BattleLog 缺失。</div>';
    }
    if (bc.battle_room_id) {
      resultHtml += '<div style="font-size:12px;color:var(--color-text-secondary);margin-bottom:8px">RoomId: ' + escapeHtml(bc.battle_room_id) + '</div>';
    }
    const matchText = bc.all_match ? '全部一致' : '存在差异';
    const matchClass = bc.all_match ? 'report-same-yes' : 'report-same-no';
    resultHtml += '<div style="margin-bottom:10px"><span class="report-same ' + matchClass + '">' + matchText + '</span></div>';
    resultHtml += '<table class="compare-instances-table" style="margin-top:4px"><thead><tr><th>实例</th><th>Report SHA</th><th>Battle SHA</th><th>一致</th></tr></thead><tbody>';
    for (const item of bc.items) {
      const statusClass = item.match ? 'report-same-yes' : 'report-same-no';
      const statusText = item.match ? '是' : (item.battle_sha256 ? '否' : '缺');
      resultHtml += `<tr>
        <td>${escapeHtml(item.launch_name || item.instance_id)}</td>
        <td style="font-size:11px">${item.report_sha256.substring(0, 14)}...</td>
        <td style="font-size:11px">${item.battle_sha256 ? item.battle_sha256.substring(0, 14) + '...' : '-'}</td>
        <td><span class="report-same ${statusClass}">${statusText}</span></td>
      </tr>`;
    }
    resultHtml += '</tbody></table>';
  } else {
    resultHtml += '<div style="margin-top:8px;color:var(--color-text-muted)">无战斗服日志或未配置战斗服路径。</div>';
  }

  document.getElementById('detail-result').innerHTML = resultHtml;
}

function openReportDiff(historyId, instanceIds) {
  const url = '/report-diff.html?history_id=' + encodeURIComponent(historyId)
    + '&instances=' + encodeURIComponent(instanceIds)
    + '&left=0&right=1';
  window.open(url, '_blank');
}

function openGroupInstanceHistory(historyId, instanceId) {
  const overlay = document.getElementById('detail-overlay');
  overlay.classList.remove('is-group-mode');
  overlay.classList.add('is-instance-from-group');
  document.getElementById('detail-back-btn').hidden = false;
  document.getElementById('detail-title').textContent = '实例历史 - ' + instanceId;
  // History instance: show progress, logs, result — hide actions
  document.getElementById('detail-section-progress').style.display = '';
  document.getElementById('detail-section-logs').style.display = '';
  document.getElementById('detail-section-actions').style.display = 'none';
  document.getElementById('detail-section-result').style.display = '';

  const apiUrl = '/api/unity/history/groups/' + encodeURIComponent(historyId) + '/instances/' + encodeURIComponent(instanceId);
  apiGet(apiUrl).then(record => {
    renderHistoryDetailInfo(record);
    renderDetailProgress(record.summary);
    renderDetailLogs(record.logs || []);
    const reportViewUrl = '/report-view.html?group_history_id=' + encodeURIComponent(historyId) + '&instance_id=' + encodeURIComponent(instanceId);
    renderHistoryDetailResult(record, reportViewUrl);
  }).catch(e => {
    showToast('获取实例历史失败: ' + e.message, 'error');
  });
}

function backFromInstanceDetail() {
  if (_groupHistoryData) {
    renderGroupHistoryDetail();
  } else {
    closeDetail();
  }
}

/* ======== 详情操作 ======== */
async function sendPing(instanceId) {
  try { await apiPost('/api/unity/' + instanceId + '/message', { type: 'ping', payload: {} }); showToast('已发送 ping', 'success'); } catch (e) { showToast('发送失败: ' + e.message, 'error'); }
}
async function sendShutdown(instanceId) {
  try { await apiPost('/api/unity/' + instanceId + '/message', { type: 'shutdown', payload: {} }); showToast('已发送 shutdown', 'success'); } catch (e) { showToast('发送失败: ' + e.message, 'error'); }
}
async function sendStartTest(instanceId) {
  try { await apiPost('/api/unity/' + instanceId + '/message', { type: 'start_test', payload: {} }); showToast('已发送 start_test', 'success'); } catch (e) { showToast('发送失败: ' + e.message, 'error'); }
}
async function sendStopTest(instanceId) {
  try { await apiPost('/api/unity/' + instanceId + '/message', { type: 'stop_test', payload: {} }); showToast('已发送 stop_test', 'success'); } catch (e) { showToast('发送失败: ' + e.message, 'error'); }
}
async function stopInstance(instanceId) {
  try {
    const result = await apiPost('/api/unity/' + instanceId + '/stop', { force: false });
    showToast('停止结果: ' + result.state, 'success');
    fetchGroups();
  } catch (e) { showToast('停止失败: ' + e.message, 'error'); }
}
async function sendCustomMessage(instanceId) {
  const errorBox = document.getElementById('detail-error');
  errorBox.hidden = true;
  let body;
  try { body = JSON.parse(document.getElementById('inp-custom-message').value); } catch (e) { errorBox.textContent = 'JSON 格式错误: ' + e.message; errorBox.hidden = false; return; }
  try { await apiPost('/api/unity/' + instanceId + '/message', body); showToast('已发送自定义消息', 'success'); } catch (e) { errorBox.textContent = '发送失败: ' + e.message; errorBox.hidden = false; showToast('发送失败: ' + e.message, 'error'); }
}

/* ======== 自动刷新 ======== */
function toggleAutoRefresh() {
  if (document.getElementById('auto-refresh').checked) startAutoRefresh();
  else stopAutoRefresh();
}

function startAutoRefresh() {
  if (autoRefreshInterval) return;
  autoRefreshInterval = setInterval(() => {
    if (refreshTimerRunning) return;
    refreshTimerRunning = true;
    const tabName = document.querySelector('.side-tab.active')?.id?.replace('tab-', '') || 'instances';
    if (tabName === 'instances') fetchGroups();
    if (tabName === 'agents') fetchAgents();
    if (tabName === 'automation') fetchAutomationTasks();
    if (tabName === 'history') fetchGroupHistory();
    // Skip detail refresh when page is hidden (saves CPU)
    if (document.hidden) { refreshTimerRunning = false; return; }
    if (currentDetailId && currentDetailIsGroupHistory) {
      refreshGroupHistoryDetail(currentDetailId).finally(() => { refreshTimerRunning = false; });
    } else if (currentDetailId) {
      refreshDetail(currentDetailId).finally(() => { refreshTimerRunning = false; });
    } else {
      refreshTimerRunning = false;
    }
  }, 5000);
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

async function refreshAll() {
  checkHealth();
  await Promise.all([fetchAgents(), fetchGroups()]);
  fetchGroupHistory();
}

/* ======== 工具函数 ======== */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
