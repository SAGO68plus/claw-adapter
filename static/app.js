const API = '';

function toast(msg, ok) {
  if (ok === undefined) ok = true;
  var el = document.createElement('div');
  el.className = 'toast ' + (ok ? 'toast-ok' : 'toast-err');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function() { el.remove(); }, 3000);
}

async function api(path, opts) {
  opts = opts || {};
  var res = await fetch(API + path, {
    headers: opts.headers || { 'Content-Type': 'application/json' },
    method: opts.method || 'GET',
    body: opts.body ? (opts.raw ? opts.body : JSON.stringify(opts.body)) : undefined,
  });
  if (!res.ok) {
    var err = await res.json().catch(function() { return {}; });
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function uploadIcon(fileInput) {
  var file = fileInput.files[0];
  if (!file) return null;
  var form = new FormData();
  form.append('file', file);
  var res = await fetch(API + '/api/upload/icon', { method: 'POST', body: form });
  if (!res.ok) {
    var err = await res.json().catch(function() { return {}; });
    throw new Error(err.detail || 'Upload failed');
  }
  var data = await res.json();
  return data.url;
}

var SVG_EYE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
var SVG_EYE_OFF = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
var SVG_COPY = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function closeModal() { document.querySelectorAll('.modal-overlay').forEach(function(m) { m.classList.add('hidden'); }); }

// ── Confirm dialog ──
var _confirmCallback = null;
function showConfirm(msg, cb) {
  _confirmCallback = cb;
  document.getElementById('confirm-text').textContent = msg;
  document.getElementById('modal-confirm').classList.remove('hidden');
}
function closeConfirm() {
  _confirmCallback = null;
  document.getElementById('modal-confirm').classList.add('hidden');
}
function doConfirm() {
  var cb = _confirmCallback;
  closeConfirm();
  if (cb) cb();
}

// ── Sidebar ──

function toggleSidebar() {
  var sb = document.getElementById('sidebar');
  var btn = document.getElementById('collapse-btn');
  sb.classList.toggle('collapsed');
  btn.textContent = sb.classList.contains('collapsed') ? '»' : '«';
  if (topoChart) setTimeout(function() { topoChart.resize(); }, 250);
}

function switchTab(name) {
  document.querySelectorAll('.nav-item').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('active'); });
  document.querySelector('.nav-item[data-tab="' + name + '"]').classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'adapters') loadAdapters();
  if (name === 'home') loadHome();
}

// ── Key visibility & copy ──
var _keyCache = {};

async function toggleKeyVisibility(kid) {
  var el = document.getElementById('key-display-' + kid);
  var btn = document.getElementById('key-toggle-' + kid);
  if (el.dataset.visible === '1') {
    el.textContent = el.dataset.masked;
    el.dataset.visible = '0';
    btn.innerHTML = SVG_EYE;
    return;
  }
  try {
    if (!_keyCache[kid]) {
      var res = await api('/api/keys/' + kid + '/reveal');
      _keyCache[kid] = res.api_key;
    }
    el.textContent = _keyCache[kid];
    el.dataset.visible = '1';
    btn.innerHTML = SVG_EYE_OFF;
  } catch (e) { toast(e.message, false); }
}

async function copyKey(kid) {
  try {
    if (!_keyCache[kid]) {
      var res = await api('/api/keys/' + kid + '/reveal');
      _keyCache[kid] = res.api_key;
    }
    await navigator.clipboard.writeText(_keyCache[kid]);
    toast('已复制');
  } catch (e) { toast('复制失败', false); }
}

function clearKeyCache(kid) { delete _keyCache[kid]; }

function renderIcon(url, fallback, extraClass) {
  if (url) return '<img class="entity-icon" src="' + esc(url) + '" alt="">';
  return '<div class="icon-placeholder ' + (extraClass || '') + '">' + (fallback || '🔑') + '</div>';
}

function setIconPreview(previewId, url) {
  var el = document.getElementById(previewId);
  if (url) { el.innerHTML = '<img src="' + esc(url) + '">'; } else { el.textContent = '上传'; }
}

var vendors = [], adapters = [], bindings = [], allProviders = [];

// ── Dropdown helper ──
function toggleDropdown(el) {
  var menu = el.nextElementSibling;
  var wasOpen = menu.classList.contains('open');
  document.querySelectorAll('.dropdown-menu.open').forEach(function(m) { m.classList.remove('open'); });
  if (!wasOpen) menu.classList.add('open');
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('.dropdown')) {
    document.querySelectorAll('.dropdown-menu.open').forEach(function(m) { m.classList.remove('open'); });
  }
});

async function loadBindings() { bindings = await api('/api/sync/bindings'); }
function getBindingsForProvider(pid) { return bindings.filter(function(b) { return b.provider_id === pid; }); }
function getBindingsForAdapter(aid) { return bindings.filter(function(b) { return b.adapter_id === aid; }); }

function renderBindingTags(list) {
  if (!list.length) return '<span style="color:var(--muted-strong);font-size:0.75rem;">未绑定</span>';
  return list.map(function(b) {
    var sync = b.auto_sync ? '<span class="binding-sync">⟳</span>' : '<span class="binding-nosync">○</span>';
    var app = b.adapter_label || b.adapter_id;
    var target = b.target_provider_name || '';
    var label = target ? app + ' / ' + target : app;
    return '<span class="binding-tag">' + sync + ' → ' + esc(label) +
      ' <span class="unbind" onclick="unbind(' + b.id + ')">×</span></span>';
  }).join('');
}

function renderBindingTagsForAdapter(list) {
  if (!list.length) return '';
  return list.map(function(b) {
    var sync = b.auto_sync ? '<span class="binding-sync">⟳</span>' : '<span class="binding-nosync">○</span>';
    var target = b.target_provider_name || '(default)';
    var source = b.provider_name || ('Provider #' + b.provider_id);
    var vendorName = '';
    vendors.forEach(function(v) { v.providers.forEach(function(p) { if (p.name === source) vendorName = v.name; }); });
    var sourceLabel = vendorName ? vendorName + ' / ' + source : source;
    return '<span class="binding-tag">' + sync + ' ' + esc(sourceLabel) + ' → ' + esc(target) +
      ' <span class="unbind" onclick="unbind(' + b.id + ')">×</span></span>';
  }).join('');
}

async function unbind(id) {
  showConfirm('解除此绑定？', async function() {
    try {
      await api('/api/sync/bindings/' + id, { method: 'DELETE' });
      toast('已解绑');
      await loadBindings();
      loadVendors();
    } catch (e) { toast(e.message, false); }
  });
}

// ── Icon Upload ──

async function uploadVendorIcon(input) {
  try {
    var url = await uploadIcon(input);
    if (url) { document.getElementById('f-v-icon').value = url; setIconPreview('vendor-icon-preview', url); }
  } catch (e) { toast(e.message, false); }
}

async function uploadAdapterIcon(input) {
  try {
    var url = await uploadIcon(input);
    if (url) { document.getElementById('f-adapter-icon').value = url; setIconPreview('adapter-icon-preview', url); }
  } catch (e) { toast(e.message, false); }
}

// ── Vendor Key + Provider grouped rendering ──

function renderProviderItem(p, vid) {
  var pBindings = getBindingsForProvider(p.id);
  return '<div class="provider-item">' +
    '<div class="card-header">' +
      '<span class="card-title" style="font-size:0.88rem;">' + esc(p.name) + '</span>' +
      '<div class="btn-group">' +
        '<button class="btn btn-sm" onclick="showPush(' + p.id + ')">推送</button>' +
        '<button class="btn btn-sm" onclick="showBind(' + p.id + ')">绑定</button>' +
        '<button class="btn btn-sm" onclick="editProvider(' + p.id + ',' + vid + ')">编辑</button>' +
        '<div class="dropdown">' +
          '<button class="dropdown-trigger" onclick="toggleDropdown(this)">⋮</button>' +
          '<div class="dropdown-menu">' +
            '<button class="dropdown-item dropdown-item-danger" onclick="delProvider(' + p.id + ')">删除配置</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div class="card-meta">' + esc(p.base_url) + '</div>' +
    (p.notes ? '<div class="card-meta" style="margin-top:4px;">' + esc(p.notes) + '</div>' : '') +
    '<div style="margin-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">' +
      '<span style="color:var(--muted);font-size:0.72rem;">绑定:</span>' + renderBindingTags(pBindings) +
    '</div>' +
  '</div>';
}

function renderKeyGroup(k, providers, vid) {
  var statusBadge = k.status === 'active'
    ? '<span class="badge badge-ok">正常</span>'
    : '<span class="badge badge-muted">' + esc(k.status) + '</span>';
  var balanceInfo = '';
  if (k.balance !== null && k.balance !== undefined) {
    balanceInfo += '<span style="color:var(--muted);font-size:0.75rem;margin-left:8px;">余额: $' + k.balance.toFixed(2) + '</span>';
  }
  if (k.quota !== null && k.quota !== undefined) {
    balanceInfo += '<span style="color:var(--muted);font-size:0.75rem;margin-left:8px;">配额: $' + k.quota.toFixed(2) + '</span>';
  }
  var provHtml = providers.length
    ? providers.map(function(p) { return renderProviderItem(p, vid); }).join('')
    : '<div class="card-meta" style="margin-top:6px;padding-left:4px;">暂无配置</div>';
  return '<div style="margin-bottom:12px;padding:12px;background:var(--bg-accent);border:1px solid var(--border);border-radius:var(--radius);">' +
    '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px;">' +
      '<div style="display:flex;align-items:center;gap:8px;flex:1;min-width:0;">' +
        '<span style="font-size:1rem;">🔑</span>' +
        '<span class="badge badge-accent">' + esc(k.label) + '</span>' +
        statusBadge + balanceInfo +
        '<span class="key-display" id="key-display-' + k.id + '" data-visible="0" data-masked="' + esc(k.api_key_masked) + '">' + esc(k.api_key_masked) + '</span>' +
        '<button class="btn-icon" id="key-toggle-' + k.id + '" onclick="toggleKeyVisibility(' + k.id + ')" title="显示/隐藏">' + SVG_EYE + '</button>' +
        '<button class="btn-icon" onclick="copyKey(' + k.id + ')" title="复制">' + SVG_COPY + '</button>' +
      '</div>' +
      '<div class="btn-group">' +
        '<button class="btn btn-ghost-accent btn-sm" onclick="showAddProviderForKey(' + vid + ',' + k.id + ')">+ 配置</button>' +
        '<button class="btn btn-sm" onclick="editKey(' + k.id + ')">编辑</button>' +
        '<button class="btn btn-sm btn-ghost-danger" onclick="delKey(' + k.id + ')">删除</button>' +
      '</div>' +
    '</div>' +
    provHtml +
  '</div>';
}

// ── Vendors ──

async function loadVendors() {
  vendors = await api('/api/vendors');
  await loadBindings();
  var el = document.getElementById('vendor-list');
  document.getElementById('vendor-count').textContent = '共 ' + vendors.length + ' 个服务商';
  if (!vendors.length) {
    el.innerHTML = '<div class="empty">还没有添加任何服务商<br><br>可以去「服务适配」页面从现有服务导入</div>';
    return;
  }
  el.innerHTML = vendors.map(function(v) {
    var iconHtml = renderIcon(v.icon, v.name.charAt(0).toUpperCase());
    // Group providers by key
    var keyGroups = v.keys.map(function(k) {
      var kProviders = v.providers.filter(function(p) { return p.vendor_key_id === k.id; });
      return renderKeyGroup(k, kProviders, v.id);
    }).join('');
    // Unlinked providers (no key)
    var unlinked = v.providers.filter(function(p) { return !p.vendor_key_id; });
    var unlinkedHtml = '';
    if (unlinked.length) {
      unlinkedHtml = '<div style="margin-bottom:12px;padding:12px;background:var(--bg-accent);border:1px solid var(--border);border-radius:var(--radius);border-style:dashed;">' +
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">' +
          '<span style="color:var(--muted);font-size:0.82rem;">未关联 Key 的配置</span>' +
        '</div>' +
        unlinked.map(function(p) { return renderProviderItem(p, v.id); }).join('') +
      '</div>';
    }
    var bodyContent = keyGroups + unlinkedHtml;
    if (!v.keys.length && !v.providers.length) {
      bodyContent = '<div class="card-meta">暂无 Key 和配置，点击上方按钮添加</div>';
    } else if (!v.keys.length && v.providers.length) {
      bodyContent = unlinkedHtml;
    }
    return '<div class="vendor-card">' +
      '<div class="vendor-header">' +
        '<div class="card-header">' +
          '<div style="display:flex;align-items:center;gap:10px;">' +
            iconHtml +
            '<div>' +
              '<span class="card-title">' + esc(v.name) + '</span>' +
              (v.domain ? ' <a href="https://' + esc(v.domain) + '" target="_blank" rel="noopener" class="badge badge-info" style="text-decoration:none;cursor:pointer;">' + esc(v.domain) + '</a>' : '') +
            '</div>' +
          '</div>' +
          '<div class="btn-group">' +
            '<button class="btn btn-ghost-teal btn-sm" onclick="showAddKey(' + v.id + ')">+ Key</button>' +
            '<button class="btn btn-sm" onclick="editVendor(' + v.id + ')">编辑</button>' +
            '<div class="dropdown">' +
              '<button class="dropdown-trigger" onclick="toggleDropdown(this)">⋮</button>' +
              '<div class="dropdown-menu">' +
                '<button class="dropdown-item dropdown-item-danger" onclick="delVendor(' + v.id + ')">删除服务商</button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +
        (v.notes ? '<div class="card-meta" style="margin-top:4px;">' + esc(v.notes) + '</div>' : '') +
      '</div>' +
      '<div class="vendor-body">' + bodyContent + '</div>' +
    '</div>';
  }).join('');
  allProviders = [];
  vendors.forEach(function(v) { v.providers.forEach(function(p) { allProviders.push(p); }); });
}

// ── Vendor CRUD ──

function showAddVendor() {
  document.getElementById('modal-vendor-title').textContent = '添加服务商';
  document.getElementById('edit-vendor-id').value = '';
  document.getElementById('f-v-name').value = '';
  document.getElementById('f-v-domain').value = '';
  document.getElementById('f-v-icon').value = '';
  document.getElementById('f-v-notes').value = '';
  setIconPreview('vendor-icon-preview', '');
  document.getElementById('modal-vendor').classList.remove('hidden');
}

function editVendor(id) {
  var v = vendors.find(function(x) { return x.id === id; });
  if (!v) return;
  document.getElementById('modal-vendor-title').textContent = '编辑服务商';
  document.getElementById('edit-vendor-id').value = id;
  document.getElementById('f-v-name').value = v.name;
  document.getElementById('f-v-domain').value = v.domain;
  document.getElementById('f-v-icon').value = v.icon || '';
  document.getElementById('f-v-notes').value = v.notes;
  setIconPreview('vendor-icon-preview', v.icon);
  document.getElementById('modal-vendor').classList.remove('hidden');
}

async function saveVendor() {
  var id = document.getElementById('edit-vendor-id').value;
  var data = {
    name: document.getElementById('f-v-name').value.trim(),
    domain: document.getElementById('f-v-domain').value.trim(),
    icon: document.getElementById('f-v-icon').value,
    notes: document.getElementById('f-v-notes').value.trim(),
  };
  if (!data.name) { toast('名称不能为空', false); return; }
  try {
    if (id) {
      await api('/api/vendors/' + id, { method: 'PUT', body: data });
      toast('已更新');
    } else {
      await api('/api/vendors', { method: 'POST', body: data });
      toast('已添加');
    }
    closeModal();
    loadVendors();
  } catch (e) { toast(e.message, false); }
}

async function delVendor(id) {
  showConfirm('确定删除该服务商？其下所有 Key、配置和绑定都会一起删除。', async function() {
    try {
      await api('/api/vendors/' + id, { method: 'DELETE' });
      toast('已删除');
      loadVendors();
    } catch (e) { toast(e.message, false); }
  });
}

// ── Key CRUD ──

function showAddKey(vendorId) {
  document.getElementById('modal-key-title').textContent = '添加 Key';
  document.getElementById('edit-key-id').value = '';
  document.getElementById('f-k-vendor-id').value = vendorId;
  document.getElementById('f-k-label').value = '';
  document.getElementById('f-k-key').value = '';
  document.getElementById('f-k-key').placeholder = 'sk-...';
  document.getElementById('f-k-notes').value = '';
  document.getElementById('modal-key').classList.remove('hidden');
}

function editKey(kid) {
  var key = null;
  vendors.forEach(function(v) { v.keys.forEach(function(k) { if (k.id === kid) key = k; }); });
  if (!key) return;
  document.getElementById('modal-key-title').textContent = '编辑 Key';
  document.getElementById('edit-key-id').value = kid;
  document.getElementById('f-k-vendor-id').value = '';
  document.getElementById('f-k-label').value = key.label;
  document.getElementById('f-k-key').value = '';
  document.getElementById('f-k-key').placeholder = key.api_key_masked + ' (留空不修改)';
  document.getElementById('f-k-notes').value = key.notes;
  document.getElementById('modal-key').classList.remove('hidden');
}

async function saveKey() {
  var id = document.getElementById('edit-key-id').value;
  var vendorId = document.getElementById('f-k-vendor-id').value;
  var label = document.getElementById('f-k-label').value.trim() || 'default';
  var apiKey = document.getElementById('f-k-key').value;
  var notes = document.getElementById('f-k-notes').value.trim();
  try {
    if (id) {
      var body = { label: label, notes: notes };
      if (apiKey) body.api_key = apiKey;
      await api('/api/keys/' + id, { method: 'PUT', body: body });
      clearKeyCache(parseInt(id));
      toast('已更新');
    } else {
      if (!apiKey) { toast('API Key 不能为空', false); return; }
      await api('/api/keys', { method: 'POST', body: { vendor_id: parseInt(vendorId), label: label, api_key: apiKey, notes: notes } });
      toast('已添加');
    }
    closeModal();
    loadVendors();
  } catch (e) { toast(e.message, false); }
}

async function delKey(kid) {
  showConfirm('确定删除该 Key？使用此 Key 的配置将取消关联。', async function() {
    try {
      await api('/api/keys/' + kid, { method: 'DELETE' });
      toast('已删除');
      loadVendors();
    } catch (e) { toast(e.message, false); }
  });
}

// ── Provider CRUD ──

function showAddProvider(vendorId) {
  document.getElementById('modal-provider-title').textContent = '添加配置';
  document.getElementById('edit-provider-id').value = '';
  document.getElementById('f-p-vendor-id').value = vendorId;
  document.getElementById('f-p-name').value = '';
  document.getElementById('f-p-url').value = '';
  document.getElementById('f-p-notes').value = '';
  // Populate key selector
  var v = vendors.find(function(x) { return x.id === vendorId; });
  var sel = document.getElementById('f-p-key');
  sel.innerHTML = '<option value="">请选择 Key</option>';
  if (v) v.keys.forEach(function(k) {
    sel.innerHTML += '<option value="' + k.id + '">' + esc(k.label) + ' (' + esc(k.api_key_masked) + ')</option>';
  });
  document.getElementById('modal-provider').classList.remove('hidden');
}

function showAddProviderForKey(vendorId, keyId) {
  showAddProvider(vendorId);
  document.getElementById('f-p-key').value = String(keyId);
}

function editProvider(id, vendorId) {
  var p = null, v = null;
  vendors.forEach(function(vv) { vv.providers.forEach(function(pp) { if (pp.id === id) { p = pp; v = vv; } }); });
  if (!p) return;
  document.getElementById('modal-provider-title').textContent = '编辑配置';
  document.getElementById('edit-provider-id').value = id;
  document.getElementById('f-p-vendor-id').value = '';
  document.getElementById('f-p-name').value = p.name;
  document.getElementById('f-p-url').value = p.base_url;
  document.getElementById('f-p-notes').value = p.notes;
  var sel = document.getElementById('f-p-key');
  sel.innerHTML = '<option value="">请选择 Key</option>';
  if (v) v.keys.forEach(function(k) {
    sel.innerHTML += '<option value="' + k.id + '"' + (p.vendor_key_id === k.id ? ' selected' : '') + '>' + esc(k.label) + ' (' + esc(k.api_key_masked) + ')</option>';
  });
  document.getElementById('modal-provider').classList.remove('hidden');
}

async function saveProvider() {
  var id = document.getElementById('edit-provider-id').value;
  var vendorId = document.getElementById('f-p-vendor-id').value;
  var keyId = document.getElementById('f-p-key').value;
  var data = {
    name: document.getElementById('f-p-name').value.trim(),
    base_url: document.getElementById('f-p-url').value.trim(),
    notes: document.getElementById('f-p-notes').value.trim(),
  };
  if (!keyId) { toast('请选择关联的 Key', false); return; }
  data.vendor_key_id = parseInt(keyId);
  if (!data.name || !data.base_url) { toast('名称和 URL 不能为空', false); return; }
  try {
    if (id) {
      await api('/api/providers/' + id, { method: 'PUT', body: data });
      toast('已更新');
    } else {
      data.vendor_id = parseInt(vendorId);
      await api('/api/providers', { method: 'POST', body: data });
      toast('已添加');
    }
    closeModal();
    loadVendors();
  } catch (e) { toast(e.message, false); }
}

async function delProvider(id) {
  showConfirm('确定删除该配置？', async function() {
    try {
      await api('/api/providers/' + id, { method: 'DELETE' });
      toast('已删除');
      loadVendors();
    } catch (e) { toast(e.message, false); }
  });
}

// ── Adapters ──

async function loadAdapters() {
  adapters = await api('/api/sync/adapters');
  await loadBindings();
  var el = document.getElementById('adapter-list');
  if (!adapters.length) {
    el.innerHTML = '<div class="empty">没有注册的服务适配器</div>';
    return;
  }
  var details = await Promise.all(adapters.map(function(a) {
    return api('/api/sync/adapters/' + a.id + '/current').catch(function() { return {}; });
  }));
  el.innerHTML = adapters.map(function(a, i) {
    var cur = details[i] || {};
    var aBindings = getBindingsForAdapter(a.id);
    var iconHtml = renderIcon(a.icon, '⚙', 'icon-placeholder-adapter');
    var providerBlocks = '';
    if (cur && cur.providers && cur.providers.length) {
      providerBlocks = cur.providers.map(function(p) {
        var matchedBindings = aBindings.filter(function(b) { return b.target_provider_name === p.provider_name; });
        var bindHtml = matchedBindings.length ? renderBindingTagsForAdapter(matchedBindings) : '<span style="color:var(--muted-strong);font-size:0.72rem;">未绑定</span>';
        return '<div class="info-block">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
            '<span style="color:var(--text-strong);font-weight:600;font-size:0.85rem;">' + esc(p.provider_name) + '</span>' +
            '<div style="display:flex;align-items:center;gap:4px;">' + bindHtml + '</div>' +
          '</div>' +
          '<div class="info-row"><span class="info-label">Base URL</span><span class="info-value">' + esc(p.base_url) + '</span></div>' +
          '<div class="info-row"><span class="info-label">API Key</span><span class="key-display">' + esc(p.api_key_masked) + '</span></div>' +
          (p.api ? '<div class="info-row"><span class="info-label">API Type</span><span class="info-value">' + esc(p.api) + '</span></div>' : '') +
          (p.models && p.models.length ? '<div class="info-row"><span class="info-label">Models</span><span class="info-value">' + esc(p.models.join(', ')) + '</span></div>' : '') +
        '</div>';
      }).join('');
    } else if (cur && (cur.base_url || cur.api_key_masked)) {
      providerBlocks = '<div class="info-block">';
      if (cur.base_url) providerBlocks += '<div class="info-row"><span class="info-label">Base URL</span><span class="info-value">' + esc(cur.base_url) + '</span></div>';
      if (cur.api_key_masked) providerBlocks += '<div class="info-row"><span class="info-label">API Key</span><span class="key-display">' + esc(cur.api_key_masked) + '</span></div>';
      if (cur.main_api) providerBlocks += '<div class="info-row"><span class="info-label">Main API</span><span class="info-value">' + esc(cur.main_api) + '</span></div>';
      providerBlocks += '</div>';
    } else {
      providerBlocks = '<div class="card-meta" style="margin-top:8px;">暂无配置信息</div>';
    }
    var matchedTargets = (cur && cur.providers) ? cur.providers.map(function(p) { return p.provider_name; }) : [];
    var unmatchedBindings = aBindings.filter(function(b) { return matchedTargets.indexOf(b.target_provider_name) === -1; });
    if (unmatchedBindings.length) {
      providerBlocks += '<div style="margin-top:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">' +
        '<span style="color:var(--muted);font-size:0.72rem;">其他绑定:</span>' + renderBindingTagsForAdapter(unmatchedBindings) + '</div>';
    }
    return '<div class="card">' +
      '<div class="card-header">' +
        '<div style="display:flex;align-items:center;gap:10px;">' +
          iconHtml +
          '<span class="dot ' + (a.enabled ? 'dot-green' : 'dot-gray') + '"></span>' +
          '<span class="card-title">' + esc(a.label) + '</span>' +
          '<span class="badge ' + (a.enabled ? 'badge-ok' : 'badge-muted') + '">' + (a.enabled ? '已启用' : '已禁用') + '</span>' +
        '</div>' +
        '<div class="btn-group">' +
          '<button class="btn btn-sm" onclick="doImport(\'' + a.id + '\')">导入</button>' +
          '<button class="btn btn-sm" onclick="editAdapterPath(\'' + a.id + '\', \'' + esc(a.config_path) + '\', \'' + esc(a.icon || '') + '\')">编辑</button>' +
          '<button class="btn btn-sm" onclick="toggleAdapter(\'' + a.id + '\', ' + (!a.enabled) + ')">' + (a.enabled ? '禁用' : '启用') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="card-meta">配置路径: ' + esc(a.config_path) + '</div>' +
      providerBlocks +
    '</div>';
  }).join('');
}

async function toggleAdapter(id, enabled) {
  try {
    await api('/api/sync/adapters/' + id, { method: 'PUT', body: { enabled: enabled } });
    toast(enabled ? '已启用' : '已禁用');
    loadAdapters();
  } catch (e) { toast(e.message, false); }
}

function editAdapterPath(id, currentPath, currentIcon) {
  document.getElementById('adapter-edit-id').value = id;
  document.getElementById('f-adapter-path').value = currentPath;
  document.getElementById('f-adapter-icon').value = currentIcon || '';
  setIconPreview('adapter-icon-preview', currentIcon);
  document.getElementById('modal-adapter').classList.remove('hidden');
}

async function saveAdapterPath() {
  var id = document.getElementById('adapter-edit-id').value;
  var path = document.getElementById('f-adapter-path').value.trim();
  var icon = document.getElementById('f-adapter-icon').value;
  try {
    await api('/api/sync/adapters/' + id, { method: 'PUT', body: { config_path: path, icon: icon } });
    toast('已更新');
    closeModal();
    loadAdapters();
  } catch (e) { toast(e.message, false); }
}

async function doImport(adapterId) {
  if (!confirm('从 ' + adapterId + ' 导入当前 API 配置？\n导入后会自动创建服务商、Key、配置和绑定关系。')) return;
  try {
    var res = await api('/api/sync/import/' + adapterId, { method: 'POST' });
    toast('已导入 ' + res.imported.length + ' 个配置并建立绑定');
    loadVendors();
  } catch (e) { toast(e.message, false); }
}

// ── Push & Bind ──

function showPush(providerId) {
  document.getElementById('push-provider-id').value = providerId;
  var el = document.getElementById('push-targets');
  el.innerHTML = adapters.length ? adapters.map(function(a) {
    return '<label style="display:flex;align-items:center;gap:8px;padding:8px 0;cursor:pointer;">' +
      '<input type="checkbox" value="' + a.id + '"' + (a.enabled ? ' checked' : '') + '>' +
      '<span>' + esc(a.label) + '</span></label>';
  }).join('') : '<div class="empty">没有可用的适配器</div>';
  document.getElementById('modal-push').classList.remove('hidden');
}

async function doPush() {
  var pid = document.getElementById('push-provider-id').value;
  var checks = document.querySelectorAll('#push-targets input:checked');
  if (!checks.length) { toast('请选择至少一个服务', false); return; }
  var ok = 0, fail = 0;
  for (var j = 0; j < checks.length; j++) {
    try {
      await api('/api/sync/push/' + checks[j].value + '/' + pid, { method: 'POST' });
      ok++;
    } catch(e) { fail++; }
  }
  closeModal();
  toast('推送完成: ' + ok + ' 成功' + (fail ? ', ' + fail + ' 失败' : ''));
  await loadBindings();
  loadVendors();
}

function showBind(providerId) {
  var provSel = document.getElementById('f-bind-provider');
  provSel.innerHTML = '';
  vendors.forEach(function(v) {
    v.providers.forEach(function(p) {
      provSel.innerHTML += '<option value="' + p.id + '"' + (p.id === providerId ? ' selected' : '') + '>' + esc(v.name + ' / ' + p.name) + '</option>';
    });
  });
  var adaSel = document.getElementById('f-bind-adapter');
  adaSel.innerHTML = adapters.map(function(a) {
    return '<option value="' + a.id + '">' + esc(a.label) + '</option>';
  }).join('');
  document.getElementById('f-bind-target').value = '';
  document.getElementById('f-bind-autosync').checked = true;
  document.getElementById('modal-bind').classList.remove('hidden');
}

async function saveBind() {
  var data = {
    provider_id: parseInt(document.getElementById('f-bind-provider').value),
    adapter_id: document.getElementById('f-bind-adapter').value,
    target_provider_name: document.getElementById('f-bind-target').value.trim(),
    auto_sync: document.getElementById('f-bind-autosync').checked,
  };
  try {
    await api('/api/sync/bindings', { method: 'POST', body: data });
    toast('绑定已创建');
    closeModal();
    await loadBindings();
    loadVendors();
  } catch (e) { toast(e.message, false); }
}

// ── Init ──

loadVendors();
loadVendors().then(function() {
  return api('/api/sync/adapters');
}).then(function(a) {
  adapters = a;
  loadHome();
}).catch(function() {
  loadHome();
});

function loadHome() {
  loadOverview();
  loadUsageChart();
  loadDistChart();
  loadTopology();
  loadLogs();
}

// ── Dashboard filter state ──
var dashFilter = {};

function setDashboardFilter(filter) {
  dashFilter = filter;
  var ctx = document.getElementById('dashboard-context');
  var btn = document.getElementById('btn-reset-filter');
  if (filter.label) {
    ctx.textContent = filter.label;
    btn.style.display = '';
  } else {
    ctx.textContent = '全局概览';
    btn.style.display = 'none';
  }
  loadUsageChart();
  loadDistChart();
  loadLogs();
}

function resetDashboardFilter() { setDashboardFilter({}); }

// ── Overview stats cards ──

async function loadOverview() {
  try {
    var s = await api('/api/stats/overview');
    document.getElementById('stats-cards').innerHTML =
      statCard(s.vendors, '服务商', 'var(--accent)') +
      statCard(s.keys, 'Key (' + s.keys_active + ' 活跃)', 'var(--warn)') +
      statCard(s.providers, '端点配置', 'var(--text-strong)') +
      statCard(s.adapters, '运行服务', 'var(--text-strong)') +
      statCard(s.bindings, '服务内端点', 'var(--text-strong)') +
      statCard(s.total_requests, '总请求', 'var(--text-strong)') +
      statCard(fmtTokens(s.total_input_tokens + s.total_output_tokens), '总 Tokens', 'var(--text-strong)') +
      statCard('$' + s.total_cost.toFixed(2), '总花费', 'var(--accent)');
  } catch(e) { console.warn('Overview failed:', e); }
}

function statCard(value, label, color) {
  return '<div class="stat-card"><div class="stat-value" style="color:' + color + ';">' + value + '</div><div class="stat-label">' + label + '</div></div>';
}

function fmtTokens(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}

// ── Usage chart (time series) ──

var usageChart = null;

async function loadUsageChart() {
  try {
    var range = document.getElementById('usage-range').value;
    var qs = '?range=' + range;
    if (dashFilter.vendor_id) qs += '&vendor_id=' + dashFilter.vendor_id;
    if (dashFilter.vendor_key_id) qs += '&vendor_key_id=' + dashFilter.vendor_key_id;
    if (dashFilter.provider_id) qs += '&provider_id=' + dashFilter.provider_id;
    if (dashFilter.adapter_id) qs += '&adapter_id=' + dashFilter.adapter_id;
    var data = await api('/api/stats/usage' + qs);
    var el = document.getElementById('usage-chart');
    if (!usageChart) usageChart = echarts.init(el, null, { renderer: 'canvas' });
    var days = data.map(function(d) { return d.day; });
    usageChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['请求数', 'Tokens'], textStyle: { color: '#71717a', fontSize: 11 }, top: 0 },
      grid: { left: 45, right: 15, top: 35, bottom: 25 },
      xAxis: { type: 'category', data: days, axisLabel: { color: '#71717a', fontSize: 10 }, axisLine: { lineStyle: { color: '#27272a' } } },
      yAxis: [
        { type: 'value', axisLabel: { color: '#71717a', fontSize: 10 }, splitLine: { lineStyle: { color: '#27272a' } } },
        { type: 'value', axisLabel: { color: '#71717a', fontSize: 10 }, splitLine: { show: false } }
      ],
      series: [
        { name: '请求数', type: 'bar', data: data.map(function(d) { return d.requests; }), itemStyle: { color: '#ff5c5c', borderRadius: [3,3,0,0] }, barMaxWidth: 20 },
        { name: 'Tokens', type: 'line', yAxisIndex: 1, data: data.map(function(d) { return d.input_tokens + d.output_tokens; }), itemStyle: { color: '#e4e4e7' }, lineStyle: { width: 2, color: '#e4e4e7' }, smooth: true, symbol: 'circle', symbolSize: 4 }
      ]
    }, true);
  } catch(e) {
    console.warn('Usage chart failed:', e);
    var el = document.getElementById('usage-chart');
    if (!usageChart) el.innerHTML = '<div style="text-align:center;padding:60px 0;color:#52525b;font-size:0.82rem;">暂无用量数据</div>';
  }
}

// ── Distribution chart (pie) ──

var distChart = null;

async function loadDistChart() {
  try {
    var endpoint = '/api/stats/by-vendor';
    if (dashFilter.vendor_id) endpoint = '/api/stats/by-key?vendor_id=' + dashFilter.vendor_id;
    else if (dashFilter.vendor_key_id) endpoint = '/api/stats/by-model';
    var data = await api(endpoint);
    var el = document.getElementById('dist-chart');
    if (!distChart) distChart = echarts.init(el, null, { renderer: 'canvas' });
    var pieColors = ['#ff5c5c','#ff8a8a','#d4d4d8','#fafafa','#ffbdbd','#e4e4e7','#ff7070','#f0f0f2'];
    var pieData = data.map(function(d) {
      return { name: d.vendor_name || d.key_label || d.model || 'unknown', value: d.requests };
    });
    var title = '按服务商分布';
    if (dashFilter.vendor_id) title = '按 Key 分布';
    else if (dashFilter.vendor_key_id) title = '按模型分布';
    distChart.setOption({
      backgroundColor: 'transparent',
      title: { text: title, textStyle: { color: '#71717a', fontSize: 12, fontWeight: 400 }, left: 'center', top: 0 },
      tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
      color: pieColors,
      series: [{ type: 'pie', radius: ['40%', '70%'], center: ['50%', '55%'], data: pieData,
        label: { color: '#e4e4e7', fontSize: 10 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } }
      }]
    }, true);
  } catch(e) {
    console.warn('Dist chart failed:', e);
    var el = document.getElementById('dist-chart');
    if (!distChart) el.innerHTML = '<div style="text-align:center;padding:60px 0;color:#52525b;font-size:0.82rem;">暂无分布数据</div>';
  }
}

// ── Request logs ──

var logState = { page: 1, total: 0 };

async function loadLogs() {
  try {
    var qs = '?page=' + logState.page + '&limit=20';
    if (dashFilter.vendor_id) qs += '&vendor_id=' + dashFilter.vendor_id;
    if (dashFilter.vendor_key_id) qs += '&vendor_key_id=' + dashFilter.vendor_key_id;
    if (dashFilter.provider_id) qs += '&provider_id=' + dashFilter.provider_id;
    var data = await api('/api/stats/logs' + qs);
    logState.total = data.total;
    var totalPages = Math.max(1, Math.ceil(data.total / data.limit));
    document.getElementById('log-page-info').textContent = logState.page + ' / ' + totalPages + ' (' + data.total + ' 条)';
    document.getElementById('log-prev').disabled = logState.page <= 1;
    document.getElementById('log-next').disabled = logState.page >= totalPages;
    var wrap = document.getElementById('log-table-wrap');
    if (!data.items.length) {
      wrap.innerHTML = '<div style="text-align:center;padding:30px;color:#52525b;font-size:0.82rem;">暂无请求日志</div>';
      return;
    }
    wrap.innerHTML = '<table class="log-table"><thead><tr>' +
      '<th>时间</th><th>服务商</th><th>Key</th><th>配置</th><th>模型</th><th>输入</th><th>输出</th><th>花费</th><th>延迟</th><th>状态</th>' +
      '</tr></thead><tbody>' +
      data.items.map(function(r) {
        var sc = r.status_code < 400 ? 'status-ok' : 'status-err';
        return '<tr>' +
          '<td>' + esc(r.created_at || '').replace('T',' ').slice(0,19) + '</td>' +
          '<td>' + esc(r.vendor_name) + '</td>' +
          '<td>' + esc(r.key_label) + '</td>' +
          '<td>' + esc(r.provider_name) + '</td>' +
          '<td>' + esc(r.model) + '</td>' +
          '<td>' + r.input_tokens + '</td>' +
          '<td>' + r.output_tokens + '</td>' +
          '<td>$' + r.cost.toFixed(4) + '</td>' +
          '<td>' + r.latency_ms + 'ms</td>' +
          '<td class="' + sc + '">' + r.status_code + '</td>' +
        '</tr>';
      }).join('') +
      '</tbody></table>';
  } catch(e) {
    console.warn('Logs failed:', e);
    document.getElementById('log-table-wrap').innerHTML = '<div style="text-align:center;padding:30px;color:#52525b;">加载日志失败</div>';
  }
}

function logPage(delta) {
  logState.page = Math.max(1, logState.page + delta);
  loadLogs();
}

// ── Topology (ECharts Sankey) ──

var topoChart = null;
var _topoNodes = [], _topoLinks = [];

// Build adjacency maps for path tracing
function buildAdj(nodes, links) {
  var fwd = {}, rev = {};
  nodes.forEach(function(n) { fwd[n.name] = []; rev[n.name] = []; });
  links.forEach(function(l, i) {
    if (fwd[l.source]) fwd[l.source].push({ node: l.target, idx: i });
    if (rev[l.target]) rev[l.target].push({ node: l.source, idx: i });
  });
  return { fwd: fwd, rev: rev };
}

// Compute leaf-count weight bottom-up
function computeWeights(nodes, links) {
  var adj = buildAdj(nodes, links);
  var weights = {};
  function getWeight(name) {
    if (weights[name] !== undefined) return weights[name];
    var children = adj.fwd[name] || [];
    if (!children.length) { weights[name] = 1; return 1; }
    var sum = 0;
    children.forEach(function(c) { sum += getWeight(c.node); });
    weights[name] = sum;
    return sum;
  }
  nodes.forEach(function(n) { getWeight(n.name); });
  // Set link values = weight of target node
  links.forEach(function(l) { l.value = weights[l.target] || 1; });
  return weights;
}

// Trace full path from a node (both directions)
function traceFullPath(nodeName, nodes, links) {
  var adj = buildAdj(nodes, links);
  var pathNodes = {}, pathLinks = {};
  // Trace backward (to sources)
  function traceBack(name) {
    if (pathNodes[name]) return;
    pathNodes[name] = true;
    (adj.rev[name] || []).forEach(function(r) { pathLinks[r.idx] = true; traceBack(r.node); });
  }
  // Trace forward (to targets)
  function traceFwd(name) {
    if (pathNodes[name]) return;
    pathNodes[name] = true;
    (adj.fwd[name] || []).forEach(function(f) { pathLinks[f.idx] = true; traceFwd(f.node); });
  }
  pathNodes[nodeName] = true;
  // Go backward first (without marking start as visited for fwd)
  (adj.rev[nodeName] || []).forEach(function(r) { pathLinks[r.idx] = true; traceBack(r.node); });
  (adj.fwd[nodeName] || []).forEach(function(f) { pathLinks[f.idx] = true; traceFwd(f.node); });
  return { nodes: pathNodes, links: pathLinks };
}

async function loadTopology() {
  try {
    var data = await api('/api/sync/topology');
    var nodes = [], links = [], nodeSet = {};

    // Layer 0: Vendors (only show vendors that have keys)
    var vendorHasKey = {};
    (data.keys || []).forEach(function(k) { vendorHasKey[k.vendor_id] = true; });
    data.vendors.forEach(function(v) {
      if (!vendorHasKey[v.id]) return; // skip vendors without keys
      var key = 'v_' + v.id;
      nodes.push({ name: key, displayName: v.name, depth: 0 });
      nodeSet[key] = true;
    });
    // Layer 1: Keys
    (data.keys || []).forEach(function(k) {
      var key = 'k_' + k.id;
      nodes.push({ name: key, displayName: '🔑 ' + k.label, depth: 1 });
      nodeSet[key] = true;
      var vKey = 'v_' + k.vendor_id;
      if (nodeSet[vKey]) links.push({ source: vKey, target: key, value: 1 });
    });
    // Layer 2: Providers (must have key)
    data.providers.forEach(function(p) {
      var key = 'p_' + p.id;
      if (!p.vendor_key_id) return; // skip providers without key
      var kKey = 'k_' + p.vendor_key_id;
      if (!nodeSet[kKey]) return; // skip if key node missing
      nodes.push({ name: key, displayName: p.name, depth: 2 });
      nodeSet[key] = true;
      links.push({ source: kKey, target: key, value: 1 });
    });
    // Layer 3: Adapters
    data.adapters.forEach(function(a) {
      var key = 'a_' + a.id;
      nodes.push({ name: key, displayName: a.label, depth: 3 });
      nodeSet[key] = true;
    });

    // Layer 4: Services — strict 5-layer topology
    // All links must flow: vendor→key→provider→adapter→service (no skipping)
    var serviceNodes = {};

    // Create service nodes from adapter.services and bindings
    data.adapters.forEach(function(a) {
      (a.services || []).forEach(function(svc) {
        var key = 's_' + a.id + '_' + svc;
        if (!serviceNodes[key]) {
          serviceNodes[key] = a.id;
          nodes.push({ name: key, displayName: svc, depth: 4 });
          nodeSet[key] = true;
        }
      });
    });
    data.bindings.forEach(function(b) {
      if (b.target_provider_name) {
        var key = 's_' + b.adapter_id + '_' + b.target_provider_name;
        if (!serviceNodes[key]) {
          serviceNodes[key] = b.adapter_id;
          nodes.push({ name: key, displayName: b.target_provider_name, depth: 4 });
          nodeSet[key] = true;
        }
      }
    });

    // Build provider→adapter and adapter→service links from bindings
    // Track weights: how many services each provider maps to through an adapter
    var paLinks = {}; // "p_X|a_Y" → count
    var asLinks = {}; // "a_X|s_Y" → count

    data.bindings.forEach(function(b) {
      var pKey = 'p_' + b.provider_id;
      var aKey = 'a_' + b.adapter_id;
      if (!nodeSet[pKey] || !nodeSet[aKey]) return;

      // provider → adapter
      var paKey = pKey + '|' + aKey;
      if (!paLinks[paKey]) paLinks[paKey] = 0;

      if (b.target_provider_name) {
        var sKey = 's_' + b.adapter_id + '_' + b.target_provider_name;
        if (nodeSet[sKey]) {
          paLinks[paKey] += 1;
          var asKey = aKey + '|' + sKey;
          asLinks[asKey] = (asLinks[asKey] || 0) + 1;
        }
      } else {
        // Binding without target: just connect provider→adapter with weight 1
        paLinks[paKey] = Math.max(paLinks[paKey], 1);
      }
    });

    // Emit provider→adapter links
    Object.keys(paLinks).forEach(function(k) {
      var parts = k.split('|');
      links.push({ source: parts[0], target: parts[1], value: Math.max(paLinks[k], 1) });
    });

    // Emit adapter→service links (bound ones with weight from bindings)
    Object.keys(asLinks).forEach(function(k) {
      var parts = k.split('|');
      links.push({ source: parts[0], target: parts[1], value: asLinks[k] });
    });

    // Unbound services: adapter→service with value 1
    Object.keys(serviceNodes).forEach(function(sKey) {
      var aid = serviceNodes[sKey];
      var aKey = 'a_' + aid;
      var alreadyLinked = Object.keys(asLinks).some(function(k) { return k === aKey + '|' + sKey; });
      if (!alreadyLinked && nodeSet[aKey]) {
        links.push({ source: aKey, target: sKey, value: 1 });
      }
    });

    // Compute weights so node heights and link widths match
    computeWeights(nodes, links);
    _topoNodes = nodes;
    _topoLinks = links;

    var maxN = Math.max(data.vendors.length, (data.keys || []).length, data.providers.length, data.adapters.length, Object.keys(serviceNodes).length);
    var el = document.getElementById('topology-chart');
    el.style.height = Math.max(400, maxN * 36 + 80) + 'px';
    if (!topoChart) { topoChart = echarts.init(el, null, { renderer: 'canvas' }); } else { topoChart.resize(); }

    topoChart.setOption({
      backgroundColor: 'transparent',
      graphic: (function() {
        var labels = ['服务商', 'Key', '端点配置', '运行服务', '服务内端点'];
        var chartLeft = 40, chartRight = 140;
        var w = el.clientWidth || 900;
        var usable = w - chartLeft - chartRight;
        return labels.map(function(t, i) {
          return { type: 'text', left: chartLeft + (usable * i / 4), top: 6, style: { text: t, fill: '#a1a1aa', fontSize: 12.5, fontWeight: 500 } };
        });
      })(),
      tooltip: { trigger: 'item', formatter: function(p) {
        if (p.dataType === 'node') return p.data.displayName;
        if (p.dataType === 'edge') {
          var s = nodes.find(function(n) { return n.name === p.data.source; });
          var t = nodes.find(function(n) { return n.name === p.data.target; });
          return (s ? s.displayName : p.data.source) + ' → ' + (t ? t.displayName : p.data.target);
        }
        return '';
      }},
      series: [{ type: 'sankey', left: 40, right: 140, top: 30, bottom: 30,
        nodeWidth: 16, nodeGap: 14, layoutIterations: 64,
        orient: 'horizontal',
        levels: [
          { depth: 0, itemStyle: { color: '#ff5c5c' }, lineStyle: { color: 'rgba(255,92,92,0.45)', opacity: 0.45 } },
          { depth: 1, itemStyle: { color: '#ff7a7a' }, lineStyle: { color: 'rgba(255,92,92,0.4)', opacity: 0.4 } },
          { depth: 2, itemStyle: { color: '#ff9e9e' }, lineStyle: { color: 'rgba(212,212,216,0.45)', opacity: 0.4, type: 'dashed' } },
          { depth: 3, itemStyle: { color: '#d4d4d8' }, lineStyle: { color: 'rgba(212,212,216,0.35)', opacity: 0.35 } },
          { depth: 4, itemStyle: { color: '#f0f0f2' }, lineStyle: { color: 'rgba(212,212,216,0.3)', opacity: 0.3 } }
        ],
        emphasis: { disabled: true },
        lineStyle: { curveness: 0.5 },
        label: { show: true, color: '#fafafa', fontSize: 11, formatter: function(p) { return p.data.displayName; } },
        data: nodes, links: links }]
    }, true);

    window.removeEventListener('resize', handleResize);
    window.addEventListener('resize', handleResize);

    // Full-path highlight on hover
    topoChart.off('mouseover');
    topoChart.off('mouseout');
    topoChart.on('mouseover', function(params) {
      if (params.dataType !== 'node') return;
      var path = traceFullPath(params.data.name, _topoNodes, _topoLinks);
      var newNodes = _topoNodes.map(function(n) {
        return Object.assign({}, n, { itemStyle: { opacity: path.nodes[n.name] ? 1 : 0.15 } });
      });
      var newLinks = _topoLinks.map(function(l, i) {
        return Object.assign({}, l, { lineStyle: path.links[i] ? { opacity: 0.6 } : { opacity: 0.03 } });
      });
      topoChart.setOption({ series: [{ data: newNodes, links: newLinks }] });
    });
    topoChart.on('mouseout', function(params) {
      if (params.dataType !== 'node') return;
      var newNodes = _topoNodes.map(function(n) {
        return Object.assign({}, n, { itemStyle: { opacity: 1 } });
      });
      var newLinks = _topoLinks.map(function(l) {
        return Object.assign({}, l, { lineStyle: { opacity: undefined } });
      });
      topoChart.setOption({ series: [{ data: newNodes, links: newLinks }] });
    });

    // Click node → filter dashboard
    topoChart.off('click');
    topoChart.on('click', function(params) {
      if (params.dataType !== 'node') return;
      var name = params.data.name;
      var display = params.data.displayName;
      if (name.indexOf('v_') === 0) {
        setDashboardFilter({ vendor_id: parseInt(name.slice(2)), label: '服务商: ' + display });
      } else if (name.indexOf('k_') === 0) {
        setDashboardFilter({ vendor_key_id: parseInt(name.slice(2)), label: 'Key: ' + display });
      } else if (name.indexOf('p_') === 0) {
        setDashboardFilter({ provider_id: parseInt(name.slice(2)), label: '端点配置: ' + display });
      } else if (name.indexOf('a_') === 0) {
        setDashboardFilter({ adapter_id: name.slice(2), label: '运行服务: ' + display });
      } else if (name.indexOf('s_') === 0) {
        // s_{adapter_id}_{service_name} → filter by adapter_id
        var parts = name.slice(2);
        var idx = parts.indexOf('_');
        var aid = idx >= 0 ? parts.slice(0, idx) : parts;
        setDashboardFilter({ adapter_id: aid, label: '服务内端点: ' + display });
      }
    });
  } catch (e) {
    console.warn('Topology load failed:', e.message);
    var el = document.getElementById('topology-chart');
    if (el && !topoChart) el.innerHTML = '<div style="text-align:center;padding:40px;color:#71717a;">加载拓扑数据失败，请刷新重试</div>';
  }
}
function handleResize() {
  if (topoChart) topoChart.resize();
  if (usageChart) usageChart.resize();
  if (distChart) distChart.resize();
}
