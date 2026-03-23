/* PrintFlow — Dashboard: Add Printer + Delete Printer modal logic */

function openAddPrinterModal() {
  document.getElementById('add-printer-modal').style.display = 'flex';
  document.getElementById('ap-test-result').textContent = '';
  document.getElementById('add-printer-form').reset();
  lucide.createIcons();
}

function closeAddPrinterModal(evt) {
  if (!evt || evt.target === document.getElementById('add-printer-modal')) {
    document.getElementById('add-printer-modal').style.display = 'none';
  }
}

function testConnection() {
  var url  = document.getElementById('ap-url').value.trim();
  var hint = document.getElementById('ap-test-result');
  if (!url) {
    hint.textContent = 'Enter an agent URL first.';
    hint.style.color = 'var(--text-mut)';
    return;
  }
  hint.textContent = 'Testing\u2026';
  hint.style.color = 'var(--text-mut)';

  fetch(url.replace(/\/$/, '') + '/health', {method: 'GET'})
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(d) {
      hint.textContent = 'Connected \u2014 ' + (d.printer_name || '') + ' (' + (d.printer_type || '?').toUpperCase() + ')';
      hint.style.color = 'var(--success)';
      if (d.printer_type) document.getElementById('ap-type').value = d.printer_type;
    })
    .catch(function() {
      hint.textContent = 'Could not reach agent. Check the URL.';
      hint.style.color = 'var(--danger)';
    });
}

function submitAddPrinter(evt) {
  evt.preventDefault();
  var btn  = document.getElementById('ap-submit');
  var hint = document.getElementById('ap-test-result');
  btn.disabled = true;
  hint.textContent = 'Registering\u2026';
  hint.style.color = 'var(--text-mut)';

  var payload = {
    name:         document.getElementById('ap-name').value.trim(),
    agent_url:    document.getElementById('ap-url').value.trim(),
    printer_type: document.getElementById('ap-type').value,
  };

  fetch('/api/printers', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  .then(function(r) {
    if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || 'Error'); });
    return r.json();
  })
  .then(function() {
    closeAddPrinterModal();
    htmx.trigger('#printer-cards', 'load');
  })
  .catch(function(e) {
    hint.textContent = e.message;
    hint.style.color = 'var(--danger)';
    btn.disabled = false;
  });
}

/* ── Delete Printer Modal ─────────────────────────────────── */

var _deletePrinterId = null;

function openDeleteModal(id, name) {
  _deletePrinterId = id;
  document.getElementById('del-printer-name').textContent = name;
  document.getElementById('delete-printer-modal').style.display = 'flex';
  lucide.createIcons();
}

function closeDeleteModal(evt) {
  if (!evt || evt.target === document.getElementById('delete-printer-modal')) {
    document.getElementById('delete-printer-modal').style.display = 'none';
    _deletePrinterId = null;
  }
}

function confirmDeletePrinter() {
  if (!_deletePrinterId) return;
  var btn = document.getElementById('del-confirm-btn');
  btn.disabled = true;

  fetch('/api/printers/' + _deletePrinterId, {method: 'DELETE'})
    .then(function(r) {
      if (!r.ok) throw new Error('Delete failed');
      closeDeleteModal();
      htmx.trigger('#printer-cards', 'load');
      htmx.trigger('#printer-tabs', 'load');
    })
    .catch(function() {
      btn.disabled = false;
    });
}
