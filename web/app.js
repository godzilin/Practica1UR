const $ = (selector) => document.querySelector(selector);
const notice = (text, ok = false) => {
  const box = $('#notice');
  box.textContent = text;
  box.className = `notice${ok ? ' ok' : ''}`;
  if (text) window.setTimeout(() => { box.textContent = ''; }, 4500);
};
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[character]));
const formatOutput = (output) => {
  const lines = output ? output.split('\n') : ['Esperando salida del proceso...'];
  return lines.map((line, index) => `${String(index + 1).padStart(3, '0')} | ${escapeHtml(line)}`).join('\n');
};
function markdownInline(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderMarkdown(source) {
  const lines = source.split(/\r?\n/);
  const result = [];
  let code = false;
  let list = null;
  const closeList = () => { if (list) { result.push(`</${list}>`); list = null; } };
  for (const original of lines) {
    const line = escapeHtml(original);
    if (line.trim().startsWith('```')) {
      if (code) result.push('</code></pre>');
      else result.push('<pre><code>');
      code = !code;
      continue;
    }
    if (code) { result.push(`${line}\n`); continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) { closeList(); result.push(`<h${heading[1].length}>${markdownInline(heading[2])}</h${heading[1].length}>`); continue; }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    const numbered = line.match(/^\d+\.\s+(.+)$/);
    if (bullet || numbered) {
      const tipo = bullet ? 'ul' : 'ol';
      if (list !== tipo) { closeList(); list = tipo; result.push(`<${tipo}>`); }
      result.push(`<li>${markdownInline((bullet || numbered)[1])}</li>`);
      continue;
    }
    closeList();
    if (line.trim()) result.push(`<p>${markdownInline(line)}</p>`);
  }
  closeList();
  if (code) result.push('</code></pre>');
  return result.join('');
}
let procesosActuales = {};
let salidaSeleccionada = '';

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'La operacion no se pudo completar');
  return data;
}

function activateTab(tabName) {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.hidden = panel.dataset.panel !== tabName;
    panel.classList.toggle('active', panel.dataset.panel === tabName);
  });
}

function renderPrograms(data) {
  const running = data.procesos || {};
  const items = Object.entries(data.programas);
  procesosActuales = running;
  $('#running-count').textContent = `${Object.keys(running).length} activos`;
  $('#tab-running-count').textContent = Object.keys(running).length;
  $('#programs').innerHTML = items.map(([key, program], index) => {
    const active = running[key];
    const enMarcha = active && active.salida === null;
    return `<article class="program-card ${enMarcha ? 'running' : ''}">
      <div><span class="card-index">0${index + 1} / MODULE</span><h3>${program.titulo}</h3><p>${program.descripcion}</p></div>
      <div class="card-actions"><span class="status ${enMarcha ? 'active' : ''}">${enMarcha ? `ACTIVO · PID ${active.pid}` : active ? `FINALIZADO · ${active.salida}` : 'EN ESPERA'}</span>
      <button class="action ${enMarcha ? 'stop' : ''}" data-program="${key}" data-action="${enMarcha ? 'stop' : 'start'}">${enMarcha ? 'Detener' : 'Iniciar'}</button></div>
    </article>`;
  }).join('');
  document.querySelectorAll('.action').forEach(button => button.addEventListener('click', () => runProgram(button)));
  renderOutput(data.programas, running);
}

function renderOutput(programas, procesos) {
  const selector = $('#output-program');
  const claves = Object.keys(procesos);
  if (!claves.includes(salidaSeleccionada)) salidaSeleccionada = claves[0] || '';
  selector.innerHTML = claves.length ? claves.map(clave => `<option value="${clave}">${escapeHtml(programas[clave].titulo)}</option>`).join('') : '<option value="">Sin procesos</option>';
  selector.value = salidaSeleccionada;
  selector.disabled = !claves.length;
  const proceso = procesos[salidaSeleccionada];
  $('#output-status').textContent = proceso ? (proceso.salida === null ? `ACTIVO · PID ${proceso.pid}` : `FINALIZADO · codigo ${proceso.salida}`) : '';
  mostrarSalida(proceso);
}

function mostrarSalida(proceso, forzarFinal = false) {
  const consola = $('#output-console');
  const estabaAlFinal = consola.scrollHeight - consola.scrollTop - consola.clientHeight < 24;
  const posicionAnterior = consola.scrollTop;
  consola.innerHTML = proceso ? formatOutput(proceso.salida_texto) : 'No hay procesos iniciados.';
  if (forzarFinal || estabaAlFinal) consola.scrollTop = consola.scrollHeight;
  else consola.scrollTop = posicionAnterior;
}

function renderRobots(robots) {
  $('#robots').innerHTML = robots.map((robot, index) => `<div class="robot-row" data-index="${index}">
    <div><label>Nombre</label><input data-field="nombre" value="${escapeHtml(robot.nombre)}"></div>
    <div><label>Host / IP</label><input data-field="host" value="${escapeHtml(robot.host)}"></div>
    <div><label>Puerto</label><input data-field="puerto" type="number" min="1" max="65535" value="${robot.puerto || 30001}"></div>
    <div><label>Posicion [x, y, z, roll, pitch, yaw]</label><input data-field="posicion" value="${escapeHtml((robot.posicion || []).join(', '))}"></div>
    <button class="remove-robot" type="button" title="Eliminar robot">Eliminar</button>
  </div>`).join('');
  document.querySelectorAll('.remove-robot').forEach(button => button.addEventListener('click', () => {
    if (document.querySelectorAll('.robot-row').length === 1) return notice('Debe quedar al menos un robot.');
    button.closest('.robot-row').remove();
  }));
}

function renderDocuments(documents) {
  $('#documents').innerHTML = documents.map(documento => {
    const pdf = documento.ruta.toLowerCase().endsWith('.pdf');
    return `<button class="document-row" data-url="${documento.url}" data-pdf="${pdf}" data-title="${escapeHtml(documento.nombre)}">
      <span class="document-type">${pdf ? 'PDF' : 'MD'}</span><span>${escapeHtml(documento.nombre)}</span><span class="document-open">Abrir</span>
    </button>`;
  }).join('');
  document.querySelectorAll('.document-row').forEach(button => button.addEventListener('click', () => openDocument(button)));
}

function openDocument(button) {
  activateTab('documentation');
  $('#viewer').hidden = false;
  $('#viewer-title').textContent = button.dataset.title;
  $('#pdf-viewer').hidden = !button.dataset.pdf || button.dataset.pdf === 'false';
  $('#text-viewer').hidden = button.dataset.pdf === 'true';
  if (button.dataset.pdf === 'true') {
    $('#pdf-viewer').src = button.dataset.url;
  } else {
    fetch(button.dataset.url).then(response => response.text()).then(text => { $('#text-viewer').innerHTML = renderMarkdown(text); });
  }
  $('#viewer').scrollIntoView({behavior: 'smooth'});
}

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => activateTab(tab.dataset.tab)));
$('#output-program').addEventListener('change', event => {
  salidaSeleccionada = event.target.value;
  const proceso = procesosActuales[salidaSeleccionada];
  $('#output-status').textContent = proceso ? (proceso.salida === null ? `ACTIVO · PID ${proceso.pid}` : `FINALIZADO · codigo ${proceso.salida}`) : '';
  mostrarSalida(proceso, true);
});
$('#output-latest').addEventListener('click', () => {
  $('#output-console').scrollTop = $('#output-console').scrollHeight;
});

async function refresh() {
  try {
    const [programs, robots, documents] = await Promise.all([api('/api/programas'), api('/api/robots'), api('/api/documentos')]);
    renderPrograms(programs);
    if (!document.querySelector('.robot-row')) renderRobots(robots.robots);
    if (!document.querySelector('.document-row')) renderDocuments(documents.documentos);
  } catch (error) { notice(error.message); }
}

$('#add-robot').addEventListener('click', () => {
  const rows = [...document.querySelectorAll('.robot-row')];
  const position = rows.length;
  const robot = {nombre: `Robot_${position + 1}`, host: '127.0.0.1', puerto: 30001, posicion: [0, 0, 0, 0, 0, 0]};
  renderRobots(rows.map(row => {
    const value = field => row.querySelector(`[data-field="${field}"]`).value;
    return {nombre: value('nombre'), host: value('host'), puerto: Number(value('puerto')),
      posicion: value('posicion').replaceAll(',', ' ').trim().split(/\s+/).map(Number)};
  }).concat(robot));
});

async function runProgram(button) {
  button.disabled = true;
  try {
    const action = button.dataset.action;
    await api(`/api/${action === 'start' ? 'iniciar' : 'detener'}`, {
      method: 'POST', body: JSON.stringify({programa: button.dataset.program})
    });
    await refresh();
    notice(action === 'start' ? 'Proceso iniciado. Consulta la pestaña Salida.' : 'Proceso detenido.', true);
  } catch (error) { notice(error.message); button.disabled = false; }
}

$('#save').addEventListener('click', async () => {
  try {
    const robots = [...document.querySelectorAll('.robot-row')].map(row => {
      const value = field => row.querySelector(`[data-field="${field}"]`).value;
      return {nombre: value('nombre'), host: value('host'), puerto: Number(value('puerto')),
        posicion: value('posicion').replaceAll(',', ' ').trim().split(/\s+/).map(Number)};
    });
    await api('/api/robots', {method: 'POST', body: JSON.stringify({robots})});
    notice('Configuracion guardada correctamente.', true);
  } catch (error) { notice(error.message); }
});
$('#refresh').addEventListener('click', refresh);
$('#close-viewer').addEventListener('click', () => { $('#viewer').hidden = true; $('#pdf-viewer').src = ''; });
refresh();
window.setInterval(refresh, 3000);
