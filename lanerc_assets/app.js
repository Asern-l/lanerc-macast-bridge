const state = {
  app: { name: 'Lanerc Cast', version: '2.0.1' },
  service: { state: 'starting', control_port: 4380, active_backend: null },
  mode: 'local',
  player: 'potplayer',
  selected_tv: '',
  selected_tv_name: '',
  tv_audio: 'tv',
  audio_delay: 2,
  auto_sync: false,
  devices: [],
  availability: {},
  discovery: {},
  warnings: [],
};

let saved = null;
let scanning = false;
let toastTimer = null;
const $ = id => document.getElementById(id);

function editableSnapshot(source = state) {
  return {
    mode: source.mode,
    player: source.player,
    selected_tv: source.selected_tv,
    tv_audio: source.tv_audio,
    audio_delay: Number(source.audio_delay),
    auto_sync: Boolean(source.auto_sync),
  };
}

function isDirty() {
  return saved && JSON.stringify(editableSnapshot()) !== JSON.stringify(saved);
}

function setMessage(text = '', kind = '') {
  const target = $('message');
  target.textContent = text;
  target.className = `message${kind ? ` ${kind}` : ''}`;
}

function showToast(text) {
  const toast = $('toast');
  toast.textContent = text;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2800);
}

async function request(url, options) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch (_) {
    throw new Error('服务返回了无法识别的数据');
  }
  if (!response.ok || !payload.ok) {
    throw new Error(payload?.error?.message || '请求失败');
  }
  return payload;
}

function renderService() {
  const ready = state.service?.state === 'ready';
  const target = $('service-state');
  target.className = `service-state ${ready ? 'ready' : 'error'}`;
  target.lastElementChild.textContent = ready ? 'Macast 服务正常' : '服务正在启动';
  $('app-version').textContent = state.app?.version || '2.0.1';
}

function renderWarnings() {
  const target = $('warning-list');
  target.replaceChildren();
  (state.warnings || []).forEach(text => {
    const notice = document.createElement('div');
    notice.className = 'notice';
    notice.textContent = text;
    target.appendChild(notice);
  });
}

function renderModes() {
  const local = state.mode === 'local';
  $('mode-local').classList.toggle('selected', local);
  $('mode-tv').classList.toggle('selected', !local);
  $('mode-local').setAttribute('aria-checked', String(local));
  $('mode-tv').setAttribute('aria-checked', String(!local));
  $('local-panel').hidden = !local;
  $('tv-panel').hidden = local;
}

function renderPlayer() {
  const select = $('player');
  select.value = state.player;
  select.options[0].disabled = !state.availability?.potplayer;
  const target = $('player-state');
  if (state.availability?.potplayer) {
    target.className = 'inline-state ok';
    target.textContent = 'PotPlayer 已就绪';
  } else {
    target.className = 'inline-state missing';
    target.textContent = '未检测到 PotPlayer，将使用内置播放器';
  }
}

function createDeviceButton(device) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `device${state.selected_tv === device.host ? ' selected' : ''}`;
  button.setAttribute('aria-pressed', String(state.selected_tv === device.host));

  const mark = document.createElement('span');
  mark.className = 'device-mark';
  mark.setAttribute('aria-hidden', 'true');
  const copy = document.createElement('span');
  const name = document.createElement('strong');
  name.textContent = device.name || 'DLNA 播放设备';
  const host = document.createElement('small');
  host.textContent = device.host;
  copy.append(name, host);
  const check = document.createElement('span');
  check.className = 'device-check';
  check.textContent = '已选择';
  button.append(mark, copy, check);
  button.addEventListener('click', () => {
    state.selected_tv = device.host;
    state.selected_tv_name = device.name;
    render();
  });
  return button;
}

function renderDevices() {
  const target = $('devices');
  target.replaceChildren();
  if (state.devices?.length) {
    state.devices.forEach(device => target.appendChild(createDeviceButton(device)));
  } else {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    const title = document.createElement('strong');
    title.textContent = scanning ? '正在扫描局域网' : '暂未发现电视';
    const copy = document.createElement('span');
    copy.textContent = scanning
      ? '通常需要几秒钟，请保持电视投屏功能开启。'
      : '确认电视和电脑位于同一网络，然后重新扫描。';
    empty.append(title, copy);
    target.appendChild(empty);
  }
  const scan = state.discovery?.last_scan;
  $('scan-meta').textContent = scan ? `上次扫描：${scan.replace('T', ' ')}` : '';
  $('refresh').disabled = scanning;
  $('refresh').textContent = scanning ? '正在扫描…' : '重新扫描';
}

function renderAudio() {
  document.querySelectorAll('input[name="tv-audio"]').forEach(input => {
    input.checked = input.value === state.tv_audio;
  });
  $('sync-panel').hidden = state.tv_audio !== 'computer';
  $('auto-sync').checked = Boolean(state.auto_sync);
  $('audio-delay').value = Number(state.audio_delay);
  $('audio-delay-value').value = `${Number(state.audio_delay).toFixed(1)} 秒`;
}

function renderDiagnostics() {
  $('diag-potplayer').textContent = state.availability?.potplayer
    ? state.availability.potplayer_path || '已就绪'
    : '未安装';
  $('diag-ffmpeg').textContent = state.availability?.ffmpeg
    ? state.availability.ffmpeg_path || '已就绪'
    : '未安装';
  $('diag-service').textContent = state.service?.control_port
    ? `http://127.0.0.1:${state.service.control_port}/`
    : '正在启动';
}

function renderActions() {
  const dirty = isDirty();
  $('reset').disabled = !dirty;
  $('save').disabled = !dirty || (state.mode === 'tv' && !state.selected_tv);
  if (dirty) setMessage('有尚未保存的更改');
  else if (!$('message').classList.contains('error')) setMessage('设置已保存');
}

function render() {
  renderService();
  renderWarnings();
  renderModes();
  renderPlayer();
  renderDevices();
  renderAudio();
  renderDiagnostics();
  renderActions();
}

async function loadStatus() {
  setMessage('正在读取运行状态', 'loading');
  try {
    const payload = await request('/api/status');
    Object.assign(state, payload.data);
    saved = editableSnapshot();
    setMessage('设置已保存');
    render();
  } catch (error) {
    setMessage(error.message, 'error');
    $('service-state').className = 'service-state error';
    $('service-state').lastElementChild.textContent = '控制服务不可用';
  }
}

async function scanDevices({ announce = true } = {}) {
  if (scanning) return;
  scanning = true;
  if (announce) setMessage('正在扫描局域网设备', 'loading');
  renderDevices();
  try {
    const payload = await request('/api/devices');
    Object.assign(state, payload.data);
    if (announce) showToast(`发现 ${state.devices.length} 台可用设备`);
  } catch (error) {
    if (announce) setMessage(error.message, 'error');
  } finally {
    scanning = false;
    render();
  }
}

async function saveSettings() {
  if (!isDirty()) return;
  setMessage('正在保存设置', 'loading');
  $('save').disabled = true;
  try {
    const payload = await request('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editableSnapshot()),
    });
    Object.assign(state, payload.data);
    saved = editableSnapshot();
    setMessage('设置已保存');
    showToast(payload.message || '设置已应用');
  } catch (error) {
    setMessage(error.message, 'error');
  } finally {
    render();
  }
}

$('mode-local').addEventListener('click', () => { state.mode = 'local'; render(); });
$('mode-tv').addEventListener('click', () => {
  state.mode = 'tv';
  render();
  if (!state.devices.length) scanDevices({ announce: false });
});
$('player').addEventListener('change', event => { state.player = event.target.value; render(); });
document.querySelectorAll('input[name="tv-audio"]').forEach(input => {
  input.addEventListener('change', event => { state.tv_audio = event.target.value; render(); });
});
$('auto-sync').addEventListener('change', event => { state.auto_sync = event.target.checked; render(); });
$('audio-delay').addEventListener('input', event => {
  state.audio_delay = Number(event.target.value);
  render();
});
$('refresh').addEventListener('click', () => scanDevices());
$('reset').addEventListener('click', () => {
  if (!saved) return;
  Object.assign(state, saved);
  setMessage('已恢复已保存设置');
  render();
});
$('save').addEventListener('click', saveSettings);

window.addEventListener('beforeunload', event => {
  if (!isDirty()) return;
  event.preventDefault();
  event.returnValue = '';
});

setInterval(() => {
  if (state.mode === 'tv' && !document.hidden) scanDevices({ announce: false });
}, 20000);

loadStatus().then(() => scanDevices({ announce: false }));
