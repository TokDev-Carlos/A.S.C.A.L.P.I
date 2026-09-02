const state = {
  page: "dashboard",
  status: null,
  statusSignature: "",
  consoleLines: []
};

const $ = (id) => document.getElementById(id);
const content = () => $("content");

const icons = {
  linux: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5 3 12l5 7 1.7-1.2L6 12l3.7-5.8L8 5Zm8 0-1.7 1.2L18 12l-3.7 5.8L16 19l5-7-5-7Z"/></svg>',
  windows: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5.5 10.5 4v7H3V5.5Zm9-1.8L21 2v9h-9V3.7ZM3 12.5h7.5v7L3 18V12.5Zm9 0h9v9l-9-1.8v-7.2Z"/></svg>',
  repository: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3a3 3 0 0 1 2 5.2V10h6V8.2a3 3 0 1 1 2 0V10a2 2 0 0 1-2 2h-2v3.8a3 3 0 1 1-2 0V12H9a2 2 0 0 1-2-2V8.2A3 3 0 0 1 7 3Z"/></svg>',
  folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h7l2 2h9v12H3V5Zm2 4v8h14V9H5Z"/></svg>',
  terminal: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 6 6 6-6 6 1.6 1.6L13.2 12 5.6 4.4 4 6Zm9 12v2h8v-2h-8Z"/></svg>',
  document: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l5 5v15H6V2Zm8 2H8v16h10V8h-4V4Zm-4 8h6v2h-6v-2Z"/></svg>'
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function statusClass(status) {
  const value = String(status || "").toUpperCase();
  if (["ONLINE", "OPERACIONAL", "PRONTO", "READY", "PASS", "DISPONIVEL", "DISPONÍVEL"].includes(value)) return "ready";
  if (["PAUSADO", "WARNING", "ATENCAO", "ATENÇÃO", "DEGRADADO"].includes(value)) return "warning";
  if (["OFFLINE", "AUSENTE", "INCOMPLETO", "FAIL", "ERRO"].includes(value)) return "offline";
  return "offline";
}

function displayStatus(status) {
  const value = String(status || "").toUpperCase();
  const labels = {
    ONLINE: "Em execução",
    OPERACIONAL: "Operacional",
    PRONTO: "Disponível",
    READY: "Disponível",
    PASS: "Conforme",
    DISPONIVEL: "Disponível",
    "DISPONÍVEL": "Disponível",
    PAUSADO: "Pausado por política",
    WARNING: "Requer atenção",
    ATENCAO: "Requer atenção",
    "ATENÇÃO": "Requer atenção",
    OFFLINE: "Fora de execução",
    AUSENTE: "Não localizado",
    INCOMPLETO: "Configuração incompleta",
    ERRO: "Falha de leitura"
  };
  return labels[value] || "Não verificado";
}

function log(message, type = "info") {
  state.consoleLines.push({
    time: new Date().toLocaleTimeString("pt-BR"),
    message,
    type
  });
  if (state.consoleLines.length > 300) state.consoleLines.shift();
  const box = document.querySelector(".console");
  if (box) renderConsole(box);
}

function renderConsole(box) {
  box.innerHTML = state.consoleLines.length
    ? state.consoleLines.map((line) =>
        `<div class="${escapeHtml(line.type)}">[${escapeHtml(line.time)}] ${escapeHtml(line.message)}</div>`
      ).join("")
    : '<div class="info">[STATUS] Nenhum evento registrado nesta sessão.</div>';
  box.scrollTop = box.scrollHeight;
}

function toast(message, error = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = "toast show" + (error ? " error" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = "toast"; }, 3000);
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(path, {
      ...options,
      signal: options.signal || controller.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    const text = await response.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; }
    catch { data = { raw: text }; }
    if (!response.ok) throw new Error(data.error || data.message || `Falha HTTP ${response.status}`);
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("O servidor local não respondeu no tempo esperado.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function attachButtonMotion(button) {
  if (!button || button.dataset.motionBound === "1") return;
  button.dataset.motionBound = "1";
  button.addEventListener("pointerdown", (event) => {
    if (button.disabled || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    button.classList.add("motion-pressed");
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 1.2;
    const ripple = document.createElement("span");
    ripple.className = "motion-ripple";
    ripple.style.width = `${size}px`;
    ripple.style.height = `${size}px`;
    ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
    button.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
  });
  const release = () => button.classList.remove("motion-pressed");
  button.addEventListener("pointerup", release);
  button.addEventListener("pointercancel", release);
  button.addEventListener("pointerleave", release);
}

function bindMotion(root = document) {
  root.querySelectorAll("button").forEach(attachButtonMotion);
}

function setBusy(button, busy) {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.innerHTML;
    button.classList.add("motion-busy");
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.innerHTML = '<span class="motion-spinner"></span><span>Processando</span>';
  } else {
    button.classList.remove("motion-busy");
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (button.dataset.label) {
      button.innerHTML = button.dataset.label;
      delete button.dataset.label;
      button.dataset.motionBound = "";
      attachButtonMotion(button);
    }
  }
}

function flash(button, ok) {
  if (!button) return;
  button.classList.remove("motion-success", "motion-error");
  void button.offsetWidth;
  button.classList.add(ok ? "motion-success" : "motion-error");
  setTimeout(() => button.classList.remove("motion-success", "motion-error"), 500);
}

function updateConnection(ok) {
  const dot = $("connection-dot");
  dot.className = `dot ${ok ? "online" : "offline"}`;
  $("connection-label").textContent = ok ? "Central ativa" : "Central indisponível";
}

async function refreshStatus(silent = false) {
  try {
    if (!silent) log("Atualizando diagnóstico operacional...");
    const nextStatus = await api("/api/status");
    const nextSignature = JSON.stringify(nextStatus);
    const statusChanged = nextSignature !== state.statusSignature;
    state.status = nextStatus;
    state.statusSignature = nextSignature;
    const global = state.status.global_status || "ATENCAO";
    $("global-status").textContent = displayStatus(global);
    $("environment-chip").textContent = "Estação local";
    $("status-chip").className = `top-chip status-chip ${statusClass(global)}`;
    $("last-sync").textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    updateConnection(true);
    if (!silent || statusChanged) renderPage({ animate: !silent });
    if (!silent) log("Diagnóstico atualizado.", "ok");
    return true;
  } catch (error) {
    $("global-status").textContent = "Indisponível";
    $("status-chip").className = "top-chip status-chip offline";
    $("last-sync").textContent = "Falha na última leitura";
    updateConnection(false);
    log(`Falha de comunicação: ${error.message}`, "err");
    if (!silent) toast(error.message, true);
    return false;
  }
}

async function runAction(action, button = null) {
  setBusy(button, true);
  try {
    log(`Solicitação enviada: ${action}`);
    const result = await api("/api/action", { method: "POST", body: JSON.stringify({ action }) });
    setBusy(button, false);
    flash(button, result.ok !== false);
    log(result.message || "Operação concluída.", result.ok === false ? "err" : "ok");
    toast(result.message || "Operação concluída.", result.ok === false);
    if (result.lines) result.lines.forEach((line) => log(line, "info"));
    if (result.refresh !== false) setTimeout(() => refreshStatus(true), action === "linux.open" ? 1200 : 180);
    return result;
  } catch (error) {
    setBusy(button, false);
    flash(button, false);
    log(`${action}: ${error.message}`, "err");
    toast(error.message, true);
    return null;
  }
}

function topTitle(title, subtitle) {
  $("page-title").textContent = title;
  $("page-subtitle").textContent = subtitle;
}

function consoleCard(open = false) {
  return `<details class="card console-card" ${open ? "open" : ""}>
    <summary>Registro de atividade</summary>
    <div class="console-toolbar"><button class="btn secondary" data-ui-action="clear-console">Limpar registro</button></div>
    <div class="console"></div>
  </details>`;
}

function statusCard(kicker, title, detail, status) {
  const css = statusClass(status);
  return `<article class="card status-card ${css}">
    <span class="status-rail"></span>
    <div class="card-kicker">${escapeHtml(kicker)}</div>
    <div class="card-title">${escapeHtml(title)}</div>
    <div class="card-detail">${escapeHtml(detail || "Informação ainda não disponível.")}</div>
    <div class="badge ${css}">${escapeHtml(displayStatus(status))}</div>
  </article>`;
}

function actionCard(icon, title, detail, attributes) {
  return `<button class="action-card" ${attributes}><span class="action-icon">${icons[icon]}</span><span class="action-copy"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span></span><span class="action-arrow">›</span></button>`;
}

function renderDashboard() {
  topTitle("Visão geral", "Ambientes, governança e evidências em um único ponto de controle.");
  const s = state.status || {};
  const policyGit = s.policy?.github_write ? "Escrita habilitada" : "Escrita bloqueada";
  const policyProd = s.policy?.production_write ? "Escrita habilitada" : "Escrita bloqueada";

  content().innerHTML = `<div class="page">
    <div class="section-heading"><div><h2>Panorama dos ambientes</h2><p>Leitura consolidada dos componentes essenciais da operação CJL.</p></div><span class="section-meta">Atualização automática ativa</span></div>
    <div class="overview-grid">
      ${statusCard("Desenvolvimento", "Linux / 1-Dev", s.linux?.detail, s.linux?.status)}
      ${statusCard("Pipeline", "Compilação", s.compiler?.detail, s.compiler?.status)}
      ${statusCard("Homologação", "Windows / Git_Main", s.git_main?.detail, s.git_main?.status)}
      ${statusCard("Controle de versão", "Repositório local", s.git?.detail, s.git?.status)}
    </div>

    <section class="card operation-banner">
      <div class="operation-copy"><div class="operation-label">Postura operacional</div><h2>${escapeHtml(displayStatus(s.global_status))}</h2><p>${escapeHtml(s.summary || "A central está reunindo os sinais do ambiente local.")}</p></div>
      <div class="policy-grid">
        <div class="policy-pill"><span>Infraestrutura WSL</span><strong>${escapeHtml(displayStatus(s.wsl?.status))}</strong></div>
        <div class="policy-pill"><span>Documentação</span><strong>${escapeHtml(displayStatus(s.docs?.status))}</strong></div>
        <div class="policy-pill"><span>GitHub</span><strong>${escapeHtml(policyGit)}</strong></div>
        <div class="policy-pill"><span>Produção</span><strong>${escapeHtml(policyProd)}</strong></div>
      </div>
    </section>

    <div class="section-heading"><div><h2>Acessos rápidos</h2><p>Abra os ambientes ou consulte o estado do repositório.</p></div></div>
    <div class="quick-actions">
      ${actionCard("linux", "Iniciar ambiente Linux", "Abre ou restaura a sessão de desenvolvimento", 'data-action="linux.open"')}
      ${actionCard("windows", "Abrir homologação Windows", "Inicia o sistema diretamente no Git_Main", 'data-action="gitmain.openSystem"')}
      ${actionCard("repository", "Consultar repositório", "Exibe branch, revisão e alterações locais", 'data-page-link="git"')}
    </div>
    ${consoleCard(false)}
  </div>`;
  afterRender();
}

function renderLinux() {
  topTitle("Desenvolvimento Linux", "Supervisão do ambiente 1-Dev executado sobre WSL.");
  const s = state.status?.linux || {};
  content().innerHTML = `<div class="page">
    <div class="card hero"><div class="hero-row"><div class="hero-status ${statusClass(s.status)}">${escapeHtml(displayStatus(s.status))}</div><div class="hero-message"><h2>Ambiente 1-Dev</h2><p>${escapeHtml(s.detail || "Aguardando diagnóstico do ambiente Linux.")}</p></div></div><div class="info-strip"><span><strong>Inicializador:</strong> <span class="mono">${escapeHtml(s.launcher || "Não localizado")}</span></span><span><strong>Processo:</strong> ${escapeHtml(s.pid || "Não iniciado")}</span><span><strong>Endpoint:</strong> ${escapeHtml(s.url || "Indisponível")}</span></div></div>
    <div class="action-grid"><button class="btn primary" data-action="linux.open">Iniciar ou restaurar ambiente</button><button class="btn secondary" data-action="linux.folder">Abrir diretório 1-Dev</button><button class="btn" data-action="wsl.terminal">Abrir terminal WSL</button></div>
    ${consoleCard(false)}
  </div>`;
  afterRender();
}

function renderGitMain() {
  topTitle("Homologação Windows", "Execução, validação e manutenção controlada do Git_Main.");
  const s = state.status?.git_main || {};
  content().innerHTML = `<div class="page">
    <div class="card hero"><div class="hero-row"><div class="hero-status ${statusClass(s.status)}">${escapeHtml(displayStatus(s.status))}</div><div class="hero-message"><h2>Git_Main / Windows</h2><p>${escapeHtml(s.detail || "Aguardando diagnóstico do ambiente Windows.")}</p></div></div><div class="info-strip"><span><strong>Sistema:</strong> <span class="mono">${escapeHtml(s.system || "Não localizado")}</span></span><span><strong>Processos associados:</strong> ${escapeHtml(s.count ?? 0)}</span></div></div>
    <div class="action-grid"><button class="btn primary" data-action="gitmain.openSystem">Abrir sistema</button><button class="btn dark" data-action="gitmain.openAdmin">Gerenciar instalação</button><button class="btn secondary" data-action="gitmain.folder">Abrir diretório Git_Main</button></div>
    ${consoleCard(false)}
  </div>`;
  afterRender();
}

function renderGit() {
  // ASCALPI_GIT_POLICY_R1
  topTitle("Repositório", "Leitura controlada de LOCAL, Dev-Work e main. Escrita permanece bloqueada.");
  const g = state.status?.git || {};
  const files = Array.isArray(g.changes) ? g.changes : [];
  const dev = g.dev_work || {};
  const main = g.main || {};
  const policy = g.policy || {};
  const info = g.information || {};
  const unavailable = !g.repository;

  const policyRows = [
    ["LOCAL", g.repository || "Caixa Git não localizada"],
    ["Dev-Work", Array.isArray(dev.include) ? dev.include.join(" + ") : "Não informado"],
    ["main", Array.isArray(main.include) ? main.include.join(" + ") : "Não informado"],
    ["Modo Git do Painel", g.mode || "READ_ONLY"],
    ["Escrita GitHub", policy.write_enabled ? "HABILITADA" : "BLOQUEADA"],
    ["Force push", policy.force_push ? "HABILITADO" : "PROIBIDO"],
    ["Preview antes de escrever", policy.require_preview ? "OBRIGATÓRIO" : "Não exigido"],
    ["Aprovação do operador", policy.require_operator_approval ? "OBRIGATÓRIA" : "Não exigida"]
  ];

  const routeLabels = {
    folder_purpose: "Função de pasta",
    operational_rule: "Regra operacional",
    ai_memory: "Memória durável para IA",
    reusable_failure: "Falha/riscos reutilizáveis",
    proven_solution: "Solução técnica comprovada",
    technical_asset: "Ativo técnico útil",
    transient_evidence: "Evidência transitória",
    no_future_value: "Sem valor futuro"
  };

  const routes = info.routes && typeof info.routes === "object"
    ? Object.entries(info.routes)
    : [];

  content().innerHTML = `<div class="page">
    <div class="grid-3">
      ${statusCard("LOCAL", "Repositório operacional / estação", g.detail, g.status)}
      ${statusCard("DEV-WORK", `${escapeHtml(dev.branch || "Dev-Work")} / ${escapeHtml(dev.head_short || "sem leitura")}`, dev.detail || "Ambiente portátil de engenharia.", dev.status)}
      ${statusCard("MAIN", `${escapeHtml(main.branch || "main")} / ${escapeHtml(main.head_short || "sem leitura")}`, main.detail || "Linha homologada.", main.status)}
    </div>

    <div class="card hero">
      <div class="hero-row">
        <div class="hero-status ${statusClass(g.status)}">${escapeHtml(displayStatus(g.status))}</div>
        <div class="hero-message">
          <h2>${escapeHtml(g.repository_full_name || "A.S.C.A.L.P.I")}</h2>
          <p>${escapeHtml(g.repository || "Repositório operacional ainda não localizado.")}</p>
        </div>
      </div>
      <div class="info-strip">
        <span><strong>Branch local:</strong> ${escapeHtml(g.branch || "Não disponível")}</span>
        <span><strong>Revisão local:</strong> <span class="mono">${escapeHtml(g.head_short || "Não disponível")}</span></span>
        <span><strong>Alterações locais:</strong> ${escapeHtml(g.change_count ?? 0)}</span>
      </div>
    </div>

    <div class="action-grid">
      <button class="btn primary" data-action="git.refresh">Revalidar repositório</button>
      <button class="btn secondary" data-action="git.folder" ${unavailable ? "disabled" : ""}>Abrir diretório do repositório</button>
      <button class="btn" data-action="git.terminal" ${unavailable ? "disabled" : ""}>Abrir terminal no repositório</button>
    </div>

    <div class="section-heading"><div><h2>Política Git efetiva</h2><p>Composição das linhas e proteções aplicadas pelo painel.</p></div></div>
    <div class="card table-card">
      <table class="table">
        <thead><tr><th>Regra</th><th>Valor efetivo</th></tr></thead>
        <tbody>${policyRows.map((row) => `<tr><td>${escapeHtml(row[0])}</td><td class="mono">${escapeHtml(row[1])}</td></tr>`).join("")}</tbody>
      </table>
    </div>

    <div class="section-heading"><div><h2>Informação útil</h2><p>Roteamento para documentos existentes, área técnica, evidência local ou descarte.</p></div></div>
    <div class="card table-card">
      <table class="table">
        <thead><tr><th>Tipo</th><th>Destino</th></tr></thead>
        <tbody>${routes.length
          ? routes.map(([key, value]) => `<tr><td>${escapeHtml(routeLabels[key] || key)}</td><td class="mono">${escapeHtml(value)}</td></tr>`).join("")
          : '<tr><td colspan="2" class="empty">Política de informação ainda não carregada.</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="section-heading"><div><h2>Alterações locais</h2><p>Consulta da árvore de trabalho da caixa Git oficial.</p></div></div>
    <div class="card table-card">
      <table class="table">
        <thead><tr><th>Situação</th><th>Arquivo</th></tr></thead>
        <tbody>${files.length
          ? files.map((f) => `<tr><td class="mono">${escapeHtml(f.code)}</td><td class="mono">${escapeHtml(f.path)}</td></tr>`).join("")
          : '<tr><td colspan="2" class="empty">Nenhuma alteração disponível para apresentação.</td></tr>'}
        </tbody>
      </table>
    </div>

    ${consoleCard(false)}
  </div>`;
  afterRender();
}
function renderWsl() {
  topTitle("Infraestrutura WSL", "Disponibilidade da distribuição que sustenta o desenvolvimento Linux.");
  const w = state.status?.wsl || {};
  content().innerHTML = `<div class="page">
    <div class="card hero"><div class="hero-row"><div class="hero-status ${statusClass(w.status)}">${escapeHtml(displayStatus(w.status))}</div><div class="hero-message"><h2>${escapeHtml(w.distribution || "Distribuição configurada")}</h2><p>${escapeHtml(w.detail || "Aguardando diagnóstico da infraestrutura WSL.")}</p></div></div></div>
    <div class="action-grid"><button class="btn primary" data-action="wsl.terminal">Abrir terminal WSL</button><button class="btn secondary" data-action="linux.folder">Abrir diretório 1-Dev</button><button class="btn" data-action="status.refresh">Atualizar diagnóstico</button></div>
    ${consoleCard(false)}
  </div>`;
  afterRender();
}

function renderDocs() {
  topTitle("Documentação", "Integridade dos documentos controlados, eventos e mecanismo documental.");
  const d = state.status?.docs || {};
  content().innerHTML = `<div class="page">
    <div class="grid-3">${statusCard("Acervo controlado", "Documentos mestres", d.detail, d.status)}${statusCard("Rastreabilidade", "Registro de eventos", d.events_detail, d.events_status)}${statusCard("Automação", "Mecanismo documental", d.engine_detail, d.engine_status)}</div>
    <div class="action-grid"><button class="btn primary" data-action="docs.folder">Abrir acervo 5-Docs</button><button class="btn secondary" data-action="docs.engineFolder">Abrir mecanismo documental</button><button class="btn" data-action="status.refresh">Atualizar diagnóstico</button></div>
    ${consoleCard(false)}
  </div>`;
  afterRender();
}

function renderLogs() {
  topTitle("Evidências", "Consulta aos registros operacionais produzidos pela central de controle.");
  content().innerHTML = `<div class="page">
    <div class="section-heading"><div><h2>Rastreabilidade operacional</h2><p>Consulte os registros locais sem alterar os ambientes monitorados.</p></div></div>
    <div class="action-grid"><button class="btn primary" data-action="logs.load">Carregar eventos recentes</button><button class="btn secondary" data-action="logs.folder">Abrir diretório de evidências</button><button class="btn" data-ui-action="clear-console">Limpar registro da sessão</button></div>
    ${consoleCard(true)}
  </div>`;
  afterRender();
}

function renderSettings() {
  topTitle("Configuração", "Escopo, caminhos operacionais e proteções vigentes nesta estação.");
  const s = state.status || {};
  const rows = [
    ["Workspace operacional", s.paths?.workspace_root],
    ["Desenvolvimento Linux", s.paths?.linux_root],
    ["Pipeline de compilação", s.paths?.compiler_root],
    ["Homologação Windows", s.paths?.git_main_root],
    ["Acervo documental", s.paths?.docs_root],
    ["Distribuição WSL", s.wsl?.distribution],
    ["Escrita no GitHub", s.policy?.github_write ? "Habilitada" : "Bloqueada"],
    ["Escrita em produção", s.policy?.production_write ? "Habilitada" : "Bloqueada"]
  ];
  content().innerHTML = `<div class="page"><div class="card table-card"><table class="table"><thead><tr><th>Configuração</th><th>Valor efetivo</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${escapeHtml(row[0])}</td><td class="mono">${escapeHtml(row[1] ?? "Não informado")}</td></tr>`).join("")}</tbody></table></div>${consoleCard(false)}</div>`;
  afterRender();
}

function renderPage({ animate = true } = {}) {
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.page === state.page));
  switch (state.page) {
    case "linux": renderLinux(); break;
    case "gitmain": renderGitMain(); break;
    case "git": renderGit(); break;
    case "wsl": renderWsl(); break;
    case "docs": renderDocs(); break;
    case "logs": renderLogs(); break;
    case "settings": renderSettings(); break;
    default: renderDashboard(); break;
  }
  if (!animate) content().classList.remove("motion-page");
}

function afterRender() {
  bindMotion();
  content().classList.remove("motion-page");
  void content().offsetWidth;
  content().classList.add("motion-page");

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      if (action === "status.refresh" || action === "git.refresh") {
        setBusy(button, true);
        const ok = await refreshStatus();
        setBusy(button, false);
        flash(button, ok);
        return;
      }
      await runAction(action, button);
    });
  });

  document.querySelectorAll("[data-page-link]").forEach((button) => {
    button.addEventListener("click", () => { state.page = button.dataset.pageLink; renderPage(); });
  });

  document.querySelectorAll("[data-ui-action='clear-console']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      state.consoleLines = [];
      const box = document.querySelector(".console");
      if (box) renderConsole(box);
      toast("Registro da sessão limpo.");
    });
  });

  const box = document.querySelector(".console");
  if (box) renderConsole(box);
}

$("nav").addEventListener("click", (event) => {
  const button = event.target.closest("[data-page]");
  if (!button) return;
  state.page = button.dataset.page;
  renderPage();
});

$("refresh-top").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  setBusy(button, true);
  const ok = await refreshStatus();
  setBusy(button, false);
  flash(button, ok);
});

bindMotion();
const updateClock = () => { $("side-clock").textContent = new Date().toLocaleString("pt-BR"); };
updateClock();
setInterval(updateClock, 1000);
setInterval(() => refreshStatus(true), 15000);

log("Central de operações inicializada.");
renderPage({ animate: false });
refreshStatus(true);
