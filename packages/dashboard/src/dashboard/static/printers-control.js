/* PrintFlow — Printer Control page logic */

// activePrinter is the numeric DB id; activePrinterType is 'dtg'/'dtf'/'uv'
var activePrinter = null;
var activePrinterType = null;

/* Called by HTMX when /api/printers/tabs partial is loaded */
document.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target && evt.detail.target.id === 'printer-tabs') {
    var firstTab = document.querySelector('.printer-tab');
    if (firstTab) {
      firstTab.click();
      document.getElementById('control-grid').style.display = '';
      document.getElementById('no-printers-msg').style.display = 'none';
    } else {
      document.getElementById('control-grid').style.display = 'none';
      document.getElementById('no-printers-msg').style.display = '';
    }
  }
});

function selectPrinterTab(id, ptype, btn) {
  activePrinter = id;
  activePrinterType = ptype;
  document.querySelectorAll('.printer-tab').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  var labels = {dtg:'DTG', dtf:'DTF', uv:'UV'};
  document.getElementById('active-printer-badge').textContent = labels[ptype] || ptype.toUpperCase();
  document.getElementById('z-controls').style.display = ptype === 'uv' ? 'flex' : 'none';
  /* Show/hide print mode section for UV printers */
  var pmSection = document.getElementById('print-mode-section');
  if (ptype === 'uv') {
    pmSection.style.display = '';
    loadPrintModes();
  } else {
    pmSection.style.display = 'none';
  }
}

function sendMove(axis, dir) {
  var moveMap = {
    'X+': 'move_right', 'X-': 'move_left',
    'Y+': 'move_ahead', 'Y-': 'move_back',
    'Z+': 'z_up',       'Z-': 'z_down'
  };
  var cmd = moveMap[axis + dir];
  if (cmd) sendControl(cmd);
}

function sendControl(cmd, extra) {
  if (!activePrinter) return;
  fetch('/api/printers/' + activePrinter + '/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.assign({command: cmd}, extra || {}))
  }).catch(function() {});
}

/* Poll printer status every 2s via JSON (not HTMX — needs explicit Accept header) */
setInterval(function() {
  if (!activePrinter) return;
  fetch('/api/printers', { headers: { 'Accept': 'application/json' } })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!Array.isArray(data)) return;
      var p = data.find(function(d) { return d.id === activePrinter; });
      if (!p) return;

      var px = document.getElementById('pos-x');
      var py = document.getElementById('pos-y');
      if (px) px.textContent = formatPos(p.position_x, 5);
      if (py) py.textContent = formatPos(p.position_y, 5);

      /* Connection banner */
      var banner = document.getElementById('conn-banner');
      var label  = document.getElementById('conn-label');
      if (banner && label) {
        var connected = p.connected || false;
        banner.className = 'conn-banner ' + (connected ? 'connected' : 'disconnected');
        var protocol = (p.printer_type === 'dtg') ? 'TCP 9100' : 'DLL Injection';
        label.textContent = connected ? 'Connected \u2014 ' + protocol : 'Disconnected';
      }

      /* Update printing status */
      var badge = document.getElementById('active-printer-badge');
      if (badge && p.printing) {
        badge.className = 'badge badge-green';
        badge.textContent = 'PRINTING';
      } else if (badge) {
        badge.className = 'badge badge-blue';
        var labels = {dtg:'DTG', dtf:'DTF', uv:'UV'};
        badge.textContent = labels[p.printer_type] || p.printer_type;
      }
    })
    .catch(function() {});
}, 2000);

function formatPos(val, len) {
  var s = (val != null ? parseFloat(val).toFixed(1) : '0.0');
  return s.padStart(len, '0');
}

/* ── Print Mode (UV only) ─────────────────────────────── */

function loadPrintModes() {
  if (!activePrinter) return;
  fetch('/api/printers/' + activePrinter + '/print-mode')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.available) return;
      var sel = document.getElementById('print-mode-select');
      sel.innerHTML = '';
      (data.presets || []).forEach(function(p) {
        var opt = document.createElement('option');
        opt.value = p.name;
        opt.textContent = p.name + ' — ' + p.desc;
        sel.appendChild(opt);
      });
      /* Select current active preset */
      if (data.current && data.current.active_preset) {
        sel.value = data.current.active_preset;
      }
      /* Show current info */
      var info = document.getElementById('print-mode-info');
      if (data.current) {
        info.textContent = data.current.direction + ' | Mirror: ' + data.current.mirror + ' | Speed: ' + data.current.speed + '%';
      }
    })
    .catch(function() {});
}

function applyPrintMode(preset) {
  if (!activePrinter || !preset) return;
  var statusEl = document.getElementById('print-mode-status');
  statusEl.textContent = 'Applying…';
  fetch('/api/printers/' + activePrinter + '/print-mode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({preset: preset})
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        statusEl.textContent = 'Applied: ' + (data.desc || preset);
        var info = document.getElementById('print-mode-info');
        info.textContent = data.ink_applied ? 'Ink channels updated' : 'INI updated (ink set on next inject)';
      } else {
        statusEl.textContent = 'Error: ' + (data.error || 'unknown');
      }
      setTimeout(function() { statusEl.textContent = ''; }, 3000);
    })
    .catch(function() {
      statusEl.textContent = 'Failed — agent unreachable';
      setTimeout(function() { statusEl.textContent = ''; }, 3000);
    });
}
