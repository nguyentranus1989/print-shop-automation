/* PrintFlow — Printer Control page logic */

// activePrinter is the numeric DB id; activePrinterType is 'dtg'/'dtf'/'uv'
var activePrinter = null;
var activePrinterType = null;
var stepSize = '1.0';

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
}

function setStep(val, btn) {
  stepSize = val;
  document.querySelectorAll('.step-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
}

function sendMove(axis, dir) {
  sendControl('move', {axis: axis, dir: dir, step: stepSize});
}

function sendControl(cmd, extra) {
  if (!activePrinter) return;
  fetch('/api/printers/' + activePrinter + '/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.assign({command: cmd}, extra || {}))
  }).catch(function() {});
}

/* pos-readout HTMX callback — reads from /api/printers/cards (JSON list) */
function updatePosFromCards(evt) {
  try {
    var data = JSON.parse(evt.detail.xhr.responseText);
    if (!Array.isArray(data)) return;
    var p = data.find(function(d) { return d.id === activePrinter; });
    if (!p) return;
    var px = document.getElementById('pos-x');
    var py = document.getElementById('pos-y');
    if (px) px.textContent = formatPos(p.position_x, 5);
    if (py) py.textContent = formatPos(p.position_y, 5);

    /* Update connection banner */
    var banner = document.getElementById('conn-banner');
    var label  = document.getElementById('conn-label');
    if (banner && label) {
      var connected = p.connected || false;
      banner.className = 'conn-banner ' + (connected ? 'connected' : 'disconnected');
      label.textContent = connected ? 'Connected \u2014 TCP 9100' : 'Disconnected';
      lucide.createIcons();
    }
  } catch(e) {}
}

function formatPos(val, len) {
  var s = (val != null ? parseFloat(val).toFixed(1) : '0.0');
  return s.padStart(len, '0');
}
