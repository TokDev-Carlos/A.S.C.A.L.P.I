const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);
const money = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
const number = value => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(Number(value || 0));
const dateBr = value => {
  if (!value) return "—";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
};
const today = () => new Date().toLocaleDateString("en-CA");
const icon = name => `<svg><use href="#i-${name}"/></svg>`;
const upper = value => String(value || "").trim().replace(/\s+/g, " ").toLocaleUpperCase("pt-BR");
const statusClass = value => upper(value).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, "-");

const app = {
  unidades: [], obras: [], pracas: [], carregamentos: [], viagens: [], receitas: [],
  equipamentos: [], clientes: [], caminhoes: [], fabrica: null, system: null, logs: [], finance: null,
  financeChart: null,
  routePlan: null, routePlans: [], resources: [], updateStatus: null, masterPatches: null,
  auth: null, usuarios: [], exclusoes: [], auditoria: [],
};

let csrfToken = "";

let busyDepth = 0;
let editingLoadId = null;
let editingItem = null;
let detailLoadId = null;
let loadWorkSequence = 0;
let itemPickerCard = null;
let pickerDraft = new Map();
let pickerMeta = new Map();
let mapTargetCard = null;
let mapInstance = null;
let mapMarker = null;
let mapResolvedAddress = null;
let mapApplyCallback = null;
let tripCostSummary = { personnel: 0, freight: 0, total: 0, base: 0 };
let editingClient = null;
let editingVehicle = null;
let pendingItemImage = "";
let routeMap = null;
let routeLayer = null;
let routeManualOrder = [];
let routeDraftActive = false;
let offlineMapGeoJson = null;
const offlinePreparedMaps = new WeakSet();

const COST_MODE_LABELS = {
  FIXO: "FIXO",
  POR_FUNCIONARIO: "POR FUNCIONÁRIO",
  POR_DIA: "POR DIA",
  POR_HORA: "POR HORA",
  POR_UNIDADE: "POR UNIDADE",
};
const NEW_COST_MODES = ["FIXO", "POR_DIA", "POR_HORA"];
const MONTH_LABELS = {
  "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO", "04": "ABRIL",
  "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO",
  "09": "SETEMBRO", "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO",
};
const ADMIN_FINANCE_CHARTS = [
  ["FINANCEIRO_MENSAL", "GERADO, PAGO E CUSTO POR MÊS"],
  ["RESULTADO_POR_OBRA", "RESULTADO GERADO POR OBRA"],
];
const OPERATIONAL_FINANCE_CHARTS = [
  ["VALOR_REAL_MENSAL", "VALOR REAL POR MÊS"],
  ["CAMINHOES_MAIS_USADOS", "CAMINHÕES MAIS USADOS"],
  ["DIAS_MAIOR_CARREGAMENTO", "DIAS COM MAIS CARREGAMENTOS"],
  ["VIAGENS_MAIORES_CUSTOS", "VIAGENS COM MAIORES CUSTOS"],
];

const DEFAULT_PERSONNEL_COSTS = [
  { grupo: "PESSOAL", descricao: "CAFÉ", modo: "POR_FUNCIONARIO", valor_unitario: 12, ativo: true },
  { grupo: "PESSOAL", descricao: "JANTAR", modo: "POR_FUNCIONARIO", valor_unitario: 40, ativo: true },
  { grupo: "PESSOAL", descricao: "ALMOÇO", modo: "POR_FUNCIONARIO", valor_unitario: 40, ativo: true },
  { grupo: "PESSOAL", descricao: "PERNOITE", modo: "POR_FUNCIONARIO", valor_unitario: 75, ativo: false },
  { grupo: "PESSOAL", descricao: "BONIFICAÇÃO DE VIAGEM", modo: "POR_FUNCIONARIO", valor_unitario: 110, ativo: false },
  { grupo: "PESSOAL", descricao: "OUTRAS DESPESAS", modo: "POR_FUNCIONARIO", valor_unitario: 0, ativo: false },
];

const DEFAULT_FREIGHT_COSTS = [
  { grupo: "FRETE", descricao: "PEDÁGIO", modo: "FIXO", valor_unitario: 0, ativo: true },
  { grupo: "FRETE", descricao: "COMBUSTÍVEL", modo: "FIXO", valor_unitario: 0, ativo: true },
  { grupo: "FRETE", descricao: "DIÁRIA", modo: "POR_DIA", valor_unitario: 1500, ativo: false },
  { grupo: "FRETE", descricao: "HORA EXTRA", modo: "POR_HORA", valor_unitario: 0, quantidade: 0, ajuste_manual: true, ativo: false },
  { grupo: "FRETE", descricao: "OUTRAS DESPESAS", modo: "FIXO", valor_unitario: 0, ativo: false },
];

const UF_CENTERS = {
  AC: [-9.97, -67.81], AL: [-9.66, -35.74], AP: [0.03, -51.05], AM: [-3.12, -60.02],
  BA: [-12.97, -38.50], CE: [-3.72, -38.54], DF: [-15.79, -47.88], ES: [-20.32, -40.34],
  GO: [-16.68, -49.25], MA: [-2.53, -44.30], MT: [-15.60, -56.10], MS: [-20.47, -54.62],
  MG: [-19.92, -43.94], PA: [-1.46, -48.49], PB: [-7.12, -34.86], PR: [-25.43, -49.27],
  PE: [-8.05, -34.88], PI: [-5.09, -42.80], RJ: [-22.91, -43.17], RN: [-5.79, -35.21],
  RS: [-30.03, -51.23], RO: [-8.76, -63.90], RR: [2.82, -60.67], SC: [-27.59, -48.55],
  SP: [-23.55, -46.63], SE: [-10.91, -37.07], TO: [-10.18, -48.33],
};

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = upper(message);
  element.className = `toast show ${error ? "error" : "success"}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { element.className = "toast"; }, 3800);
}

function setBusy(active, label = "PROCESSANDO...") {
  busyDepth = Math.max(0, busyDepth + (active ? 1 : -1));
  const visible = busyDepth > 0;
  $("#busyOverlay").classList.toggle("show", visible);
  $("#busyOverlay").setAttribute("aria-hidden", String(!visible));
  $("#busyLabel").textContent = upper(label);
  $("#systemStatus").classList.toggle("busy", visible);
  $("#systemStatus b").textContent = visible ? upper(label) : "SISTEMA PRONTO";
}

async function api(url, options = {}) {
  const init = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  const method = String(init.method || "GET").toUpperCase();
  if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes(method)) init.headers["X-CJL-CSRF"] = csrfToken;
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  let response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    const error = new Error("A CONEXÃO LOCAL COM O CJL System FOI INTERROMPIDA. AGUARDE ALGUNS SEGUNDOS E TENTE NOVAMENTE.");
    error.code = "LOCAL_FETCH_FAILED";
    error.cause = cause;
    throw error;
  }
  const payload = await response.json().catch(() => ({ error: "RESPOSTA INVÁLIDA DO SISTEMA." }));
  if (!response.ok || payload.error) {
    const error = new Error(payload.error || "NÃO FOI POSSÍVEL CONCLUIR A OPERAÇÃO.");
    error.status = response.status;
    if ([423, 426].includes(response.status) && typeof checkCriticalState === "function") {
      setTimeout(() => checkCriticalState().catch(() => {}), 0);
    }
    throw error;
  }
  return payload;
}

function hasPermission(name) {
  return Boolean(app.auth?.user?.permissoes?.[name]);
}

function applyPermissions() {
  $$('[data-permission]').forEach(element => {
    element.hidden = !hasPermission(element.dataset.permission);
  });
  const user = app.auth?.user;
  $("#currentUser b").textContent = user ? `${user.nome} · ${user.perfil}` : "—";
  const administrative = hasPermission("FINANCE_ADMIN");
  $("#financeOperationalBlock").hidden = administrative;
  $("#financePageTitle").textContent = administrative
    ? "RESULTADO DA EMPRESA POR PERÍODO E ESTADO"
    : "INDICADORES OPERACIONAIS POR PERÍODO E ESTADO";
  $("#financePageSubtitle").textContent = administrative
    ? "VISÃO ADMINISTRATIVA E LOGÍSTICA DE CARREGAMENTOS, PAGAMENTOS E CUSTOS."
    : "VALOR CARREGADO, CUSTO DE VIAGENS E VALOR REAL — SEM DADOS ADMINISTRATIVOS.";
  const chart = $("#financeChartType");
  const previous = chart.value;
  const options = administrative
    ? [...ADMIN_FINANCE_CHARTS, ...OPERATIONAL_FINANCE_CHARTS]
    : OPERATIONAL_FINANCE_CHARTS;
  chart.innerHTML = options.map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("");
  chart.value = options.some(([value]) => value === previous)
    ? previous
    : (administrative ? "FINANCEIRO_MENSAL" : "VALOR_REAL_MENSAL");
}

function showLogin(message = "") {
  app.auth = null;
  csrfToken = "";
  document.body.classList.remove("authenticated", "auth-changing");
  document.body.classList.add("auth-pending");
  $("#loginForm").hidden = false;
  $("#changePasswordForm").hidden = true;
  $("#loginForm").reset();
  $("#loginMessage").textContent = message || "A ESTAÇÃO PODE LER O CACHE QUANDO A REDE ESTIVER INDISPONÍVEL.";
  $("#loginMessage").className = `login-message${message ? " error" : ""}`;
  setTimeout(() => $('#loginForm input[name="senha"]').focus(), 50);
  if (!$("#loginResourcesPanel")?.hidden) loadLoginResources();
  checkStationUpdate(false);
}

async function completeAuthentication(payload) {
  app.auth = { user: payload.user, csrf: payload.csrf };
  csrfToken = payload.csrf || "";
  applyPermissions();
  if (payload.user.trocar_senha) {
    document.body.classList.remove("auth-pending", "authenticated");
    document.body.classList.add("auth-changing");
    $("#loginForm").hidden = true;
    $("#changePasswordForm").hidden = false;
    $("#loginMessage").textContent = "O NOVO PIN DEVE TER SOMENTE NÚMEROS E PELO MENOS 4 DÍGITOS.";
    $("#loginMessage").className = "login-message";
    setTimeout(() => $('#changePasswordForm input[name="nova_senha"]').focus(), 50);
    return;
  }
  document.body.classList.remove("auth-pending", "auth-changing");
  document.body.classList.add("authenticated");
  if (payload.offline) {
    $("#loginMessage").textContent = "MODO OFFLINE: CONSULTA LIBERADA; ALTERAÇÕES OFICIAIS BLOQUEADAS.";
    $("#loginMessage").className = "login-message offline";
  }
  await loadAll();
  await Promise.all([loadLoginResources(), checkStationUpdate(false)]);
  resetLoadForm();
  showLoadView("editor", false);
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function normalizeForm(form) {
  $$('[data-upper]', form).forEach(input => { input.value = upper(input.value); });
}

document.addEventListener("focusout", event => {
  if (event.target.matches?.("[data-upper]")) event.target.value = upper(event.target.value);
});
document.addEventListener("keydown", event => {
  if (event.key !== "Enter" || event.defaultPrevented || event.isComposing || event.ctrlKey || event.altKey || event.metaKey) return;
  const target = event.target;
  if (!target.matches?.("input,select") || target.matches("textarea,button,[type=checkbox],[type=radio],[type=submit],[type=file]")) return;
  const form = target.closest("form");
  if (!form || form.matches("#loginForm,#changePasswordForm")) return;
  const fields = $$('input:not([type="hidden"]):not([type="file"]),select,textarea,button[type="submit"]', form)
    .filter(field => !field.disabled && !field.hidden && field.getClientRects().length > 0);
  const next = fields[fields.indexOf(target) + 1];
  event.preventDefault();
  if (next) {
    next.focus();
    if (next.matches("input:not([type=date]):not([type=time]),textarea")) next.select?.();
  }
});
document.addEventListener("pointerdown", event => event.target.closest(".btn,.module-tab,.subtab")?.classList.add("pressed"));
document.addEventListener("pointerup", () => $$(".pressed").forEach(button => button.classList.remove("pressed")));

function switchModule(name) {
  $$(".module-tab").forEach(button => button.classList.toggle("active", button.dataset.module === name));
  $$(".module").forEach(module => module.classList.toggle("active", module.id === `module-${name}`));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (name === "rotas") setTimeout(renderRouteMap, 120);
}

$$(".module-tab").forEach(button => { button.onclick = () => switchModule(button.dataset.module); });
$$(".subtab").forEach(button => {
  button.onclick = () => {
    $$(".subtab").forEach(item => item.classList.toggle("active", item === button));
    $$(".cad-panel").forEach(panel => panel.classList.toggle("active", panel.dataset.cadPanel === button.dataset.cadTab));
  };
});

function unitOptions(selected = "") {
  return app.unidades.map(unit => `<option value="${escapeHtml(unit.id)}" ${unit.id === selected ? "selected" : ""}>${escapeHtml(unit.uf)} · ${escapeHtml(unit.nome)}</option>`).join("");
}

function workOptions(selected = "", uf = "") {
  const rows = app.obras.filter(work => !uf || work.uf === uf);
  return `<option value="">+ NOVA OBRA</option>${rows.map(work => `<option value="${work.id}" ${work.id === selected ? "selected" : ""}>${escapeHtml(work.nome)}${work.municipio ? ` · ${escapeHtml(work.municipio)}` : ""}</option>`).join("")}`;
}

function allWorkOptions(selected = "") {
  return `<option value="">SELECIONE...</option>${app.obras.map(work => `<option value="${work.id}" ${work.id === selected ? "selected" : ""}>${escapeHtml(work.uf)} · ${escapeHtml(work.nome)}${work.municipio ? ` · ${escapeHtml(work.municipio)}` : ""}</option>`).join("")}`;
}

function stateSelectOptions(selected = "RJ") {
  return `${app.unidades.map(unit => `<option value="${escapeHtml(unit.uf)}" data-unit-id="${escapeHtml(unit.id)}" ${unit.uf === selected ? "selected" : ""}>${escapeHtml(unit.uf)} · ${escapeHtml(unit.nome)}</option>`).join("")}<option value="OUTRO">OUTRO ESTADO / UNIDADE...</option>`;
}

function stateName(uf) {
  return app.unidades.find(unit => unit.uf === uf)?.nome || uf;
}

function fillGlobalSelects() {
  const revenue = $('#revenueForm select[name="obra_id"]');
  const oldRevenue = revenue.value;
  revenue.innerHTML = allWorkOptions(oldRevenue);

  const workUnit = $('#workForm select[name="unidade_id"]');
  const oldUnit = workUnit.value;
  workUnit.innerHTML = unitOptions(oldUnit);
  $("#clientNames").innerHTML = app.clientes.filter(client => client.ativo).map(client => `<option value="${escapeHtml(client.nome)}"></option>`).join("");

  const vehicleOptions = app.caminhoes.filter(vehicle => vehicle.ativo).map(vehicle => `<option value="${escapeHtml(vehicle.id)}">${vehicle.cadastro_pendente ? "PENDENTE" : escapeHtml(vehicle.placa)} · ${escapeHtml(vehicle.apelido || vehicle.modelo)} · ${vehicle.cadastro_pendente ? "CADASTRO INCOMPLETO" : `${number(vehicle.eixos || 2)} EIXOS`}</option>`).join("");
  const loadVehicle = $("#loadVehicleSelect");
  const oldLoadVehicle = loadVehicle.value;
  loadVehicle.innerHTML = `<option value="">PREENCHIMENTO MANUAL</option>${vehicleOptions}`;
  loadVehicle.value = oldLoadVehicle;
  const routeVehicle = $("#routeVehicleSelect");
  const oldRouteVehicle = routeVehicle.value;
  routeVehicle.innerHTML = `<option value="">SELECIONE O VEÍCULO</option>${vehicleOptions}`;
  routeVehicle.value = oldRouteVehicle;
  const routeLoad = $("#routeLoadSelect");
  const oldRouteLoad = routeLoad.value;
  routeLoad.innerHTML = `<option value="">NOVO CARREGAMENTO</option>${app.carregamentos.filter(load => load.status !== "CANCELADO").map(load => `<option value="${escapeHtml(load.id)}">${escapeHtml(load.id)} · ${dateBr(load.data)} · ${escapeHtml((load.obras || []).map(work => work.nome).join(" + "))}</option>`).join("")}`;
  routeLoad.value = oldRouteLoad;

  const ufOptions = app.unidades.map(unit => `<option value="${unit.uf}">${unit.uf} · ${escapeHtml(unit.nome)}</option>`).join("");
  const profitUf = $("#profitUf");
  const previousProfitUf = profitUf.value;
  profitUf.innerHTML = `<option value="">TODOS</option>${ufOptions}`;
  profitUf.value = previousProfitUf;

  ["#loadUfFilter", "#workUfFilter"].forEach(selector => {
    const select = $(selector);
    const value = select.value;
    select.innerHTML = `<option value="">TODOS OS ESTADOS</option>${ufOptions}`;
    select.value = value;
  });

  const years = new Set([String(new Date().getFullYear())]);
  app.carregamentos.forEach(load => years.add(String(load.data).slice(0, 4)));
  app.viagens.forEach(trip => years.add(String(trip.data_saida).slice(0, 4)));
  app.receitas.forEach(row => years.add(String(row.data_competencia).slice(0, 4)));
  const yearSelect = $("#profitYear");
  const selectedYear = yearSelect.value || String(new Date().getFullYear());
  yearSelect.innerHTML = [...years].sort().reverse().map(year => `<option ${year === selectedYear ? "selected" : ""}>${year}</option>`).join("");
  const loadYearSelect = $("#loadYearFilter");
  const selectedLoadYear = loadYearSelect.value || String(new Date().getFullYear());
  loadYearSelect.innerHTML = [...years].sort().reverse().map(year => `<option ${year === selectedLoadYear ? "selected" : ""}>${year}</option>`).join("");
  refreshLoadWorkOptions();
}

function addLoadWork(prefill = {}, rebalance = true) {
  loadWorkSequence += 1;
  const card = document.createElement("article");
  const uf = prefill.uf || "RJ";
  card.className = "load-work-card";
  card.dataset.workIndex = String(loadWorkSequence);
  card._items = (prefill.itens || []).map(item => ({
    equipamento_codigo: String(item.equipamento_codigo || item.codigo || ""),
    quantidade: Number(item.quantidade || 0),
    praca_id: item.praca_id || "",
    unidade: item.unidade || "UN",
    observacao: item.observacao || "",
    valor_unitario: Number(item.valor_unitario ?? item.valor_unit ?? 0),
  }));
  card._existingAttachments = (prefill.anexos || []).map(item => ({ ...item }));
  card._pendingAttachments = [];
  card._allocation = {
    valor_obra: Number(prefill.valor_obra || 0),
    percentual_rateio: Number(prefill.percentual_rateio || 0),
  };
  card.innerHTML = `
    <div class="load-work-card-head">
      <div><span class="work-order">1</span><div><b class="load-work-title">NOVA OBRA</b><div class="work-summary-badges"><span class="badge blue work-items-badge">0 ITENS</span><span class="badge green work-value-badge">R$ 0,00</span><span class="badge orange work-cost-badge">R$ 0,00</span></div></div></div>
      <button type="button" class="remove-work" title="REMOVER OBRA">${icon("close")}</button>
    </div>
    <div class="load-work-body">
      <div class="load-work-grid">
        <label class="span-2">CLIENTE<input data-field="cliente_nome" list="clientNames" data-upper placeholder="SE VAZIO, SERÁ USADO O MUNICÍPIO"></label><input type="hidden" data-field="cliente_id">
        <label>ESTADO<select data-field="uf">${stateSelectOptions(uf)}</select></label>
        <label>OBRA CADASTRADA<select data-field="obra_id">${workOptions(prefill.obra_id || "", uf)}</select></label>
        <div class="custom-state" hidden><label>SIGLA<input data-field="custom_uf" maxlength="5" data-upper placeholder="UF"></label><label>NOME DO ESTADO<input data-field="custom_estado" data-upper placeholder="ESTADO / UNIDADE"></label></div>
        <label>MUNICÍPIO<input data-field="municipio" data-upper required placeholder="MUNICÍPIO"></label>
        <label>ORDEM DE PRODUÇÃO<input data-field="op_numero" data-upper required placeholder="EX.: OP 2458"></label>
        <label>REFERÊNCIA / CONTRATO<input data-field="referencia_contrato" data-upper placeholder="CONTRATO, PEDIDO OU MEDIÇÃO"></label>
        <label>PREVISÃO DE ENTREGA<input data-field="previsao_entrega" type="date"></label>
        <label class="span-2">NOME DA OBRA<input data-field="nome" data-upper required placeholder="NOME DA OBRA"></label>
        <label class="span-2">LOCALIZAÇÃO OPCIONAL<div class="geo-control"><div><b data-geo-title>SEM LOCALIZAÇÃO</b><small data-geo-address>PESQUISE OU MARQUE NO MAPA</small></div><button type="button" class="compact-button open-map">${icon("pin")}MAPA</button></div><input type="hidden" data-field="endereco"><input type="hidden" data-field="latitude"><input type="hidden" data-field="longitude"></label>
        <label class="span-2">ITENS DO CARREGAMENTO<div class="item-control"><div><b data-item-title>NENHUM ITEM SELECIONADO</b><small data-item-summary>USE O CHECKLIST PARA INFORMAR AS QUANTIDADES</small></div><button type="button" class="compact-button open-items">${icon("list")}CHECKLIST</button></div></label>
        <label class="span-2">ANEXOS DA OBRA / OP<div class="attachment-control"><div><b data-attachment-title>NENHUM ANEXO</b><small>XLSX, XLS, PDF OU DOCX · ATÉ 10 MB CADA · 10 POR CARREGAMENTO</small></div><button type="button" class="compact-button open-attachments">${icon("folder")}ADICIONAR</button><input class="work-attachment-input" type="file" accept=".xlsx,.xls,.pdf,.docx" multiple hidden></div><div class="work-attachment-list"></div></label>
        <label class="span-2">OBSERVAÇÃO DA OBRA<input data-field="observacao" data-upper placeholder="INFORMAÇÃO ESPECÍFICA DESTA OBRA"></label>
      </div>
    </div>`;
  $("#loadWorks").append(card);
  bindLoadWork(card);

  if (prefill.obra_id) fillWorkFromExisting(card, prefill.obra_id);
  const assignments = ["cliente_id", "cliente_nome", "municipio", "op_numero", "referencia_contrato", "previsao_entrega", "nome", "endereco", "latitude", "longitude", "observacao"];
  assignments.forEach(field => {
    if (prefill[field] !== undefined && prefill[field] !== null) card.querySelector(`[data-field="${field}"]`).value = prefill[field];
  });
  if (prefill.uf) card.querySelector('[data-field="uf"]').value = prefill.uf;
  renderGeoLabel(card);
  renderCardAttachments(card);
  renderWorkSummary(card);
  updateLoadWorkNumbers(rebalance);
  return card;
}

function bindLoadWork(card) {
  const ufSelect = card.querySelector('[data-field="uf"]');
  const workSelect = card.querySelector('[data-field="obra_id"]');
  ufSelect.onchange = () => {
    const custom = ufSelect.value === "OUTRO";
    card.querySelector(".custom-state").hidden = !custom;
    workSelect.innerHTML = custom ? '<option value="">+ NOVA OBRA</option>' : workOptions("", ufSelect.value);
    clearWorkIdentity(card);
    renderWorkSummary(card);
    renderAllocationRows(false);
  };
  workSelect.onchange = () => {
    if (workSelect.value) fillWorkFromExisting(card, workSelect.value);
    else clearWorkIdentity(card);
    renderWorkSummary(card);
    renderAllocationRows(false);
  };
  card.querySelector(".remove-work").onclick = () => {
    if ($$(".load-work-card", $("#loadWorks")).length === 1) {
      toast("O CARREGAMENTO PRECISA TER PELO MENOS UMA OBRA.", true);
      return;
    }
    card.remove();
    updateLoadWorkNumbers(true);
  };
  card.querySelector(".open-map").onclick = () => openMapForCard(card);
  card.querySelector(".open-items").onclick = () => openItemPicker(card);
  const attachmentInput = card.querySelector(".work-attachment-input");
  card.querySelector(".open-attachments").onclick = () => attachmentInput.click();
  attachmentInput.onchange = () => queueWorkAttachments(card, [...(attachmentInput.files || [])]);
  ["nome", "op_numero"].forEach(field => {
    card.querySelector(`[data-field="${field}"]`).addEventListener("input", () => {
      renderWorkSummary(card);
      refreshAllocationValues();
    });
  });
  card.querySelector('[data-field="cliente_nome"]').addEventListener("input", () => {
    card.querySelector('[data-field="cliente_id"]').value = "";
  });
}

function totalEditorAttachments() {
  const stored = editingLoadId
    ? (app.carregamentos.find(item => item.id === editingLoadId)?.anexos || []).length
    : 0;
  const pending = $$(".load-work-card", $("#loadWorks")).reduce(
    (total, card) => total + (card._pendingAttachments?.length || 0), 0,
  );
  return stored + pending;
}

function renderCardAttachments(card) {
  const existing = card._existingAttachments || [];
  const pending = card._pendingAttachments || [];
  const total = existing.length + pending.length;
  card.querySelector("[data-attachment-title]").textContent = total
    ? `${total} ANEXO${total === 1 ? "" : "S"} NESTA OBRA / OP`
    : "NENHUM ANEXO";
  card.querySelector(".work-attachment-list").innerHTML = [
    ...existing.map(item => `<span class="work-attachment saved"><a href="${escapeHtml(item.download_url)}" target="_blank" rel="noopener">${escapeHtml(item.nome_original)}</a><small>SALVO</small></span>`),
    ...pending.map((item, index) => `<span class="work-attachment pending"><b>${escapeHtml(item.nome_original)}</b><small>AGUARDANDO SALVAR</small><button type="button" data-remove-pending-attachment="${index}" aria-label="REMOVER ${escapeHtml(item.nome_original)}">${icon("close")}</button></span>`),
  ].join("");
  $$('[data-remove-pending-attachment]', card).forEach(button => {
    button.onclick = () => {
      card._pendingAttachments.splice(Number(button.dataset.removePendingAttachment), 1);
      renderCardAttachments(card);
    };
  });
}

async function queueWorkAttachments(card, files) {
  const input = card.querySelector(".work-attachment-input");
  try {
    for (const file of files) {
      if (totalEditorAttachments() >= 10) throw new Error("O CARREGAMENTO ACEITA NO MÁXIMO 10 ANEXOS.");
      const extension = String(file.name || "").toLowerCase().match(/\.[^.]+$/)?.[0] || "";
      if (![".xlsx", ".xls", ".pdf", ".docx"].includes(extension)) {
        throw new Error(`ARQUIVO ${file.name}: USE XLSX, XLS, PDF OU DOCX.`);
      }
      if (!file.size || file.size > 10 * 1024 * 1024) {
        throw new Error(`ARQUIVO ${file.name}: O LIMITE É 10 MB.`);
      }
      const duplicate = [...(card._existingAttachments || []), ...(card._pendingAttachments || [])]
        .some(item => item.nome_original === file.name && Number(item.tamanho || item.size || 0) === file.size);
      if (duplicate) continue;
      card._pendingAttachments.push({
        nome_original: file.name,
        mime: file.type || "application/octet-stream",
        tamanho: file.size,
        data_base64: await attachmentToDataUrl(file),
      });
    }
    renderCardAttachments(card);
  } catch (error) {
    toast(error.message, true);
  } finally {
    input.value = "";
  }
}

function clearWorkIdentity(card) {
  const name = card.querySelector('[data-field="nome"]');
  name.readOnly = false;
  name.value = "";
  card.querySelector('[data-field="municipio"]').value = "";
  card.querySelector('[data-field="op_numero"]').value = "";
  card.querySelector('[data-field="endereco"]').value = "";
  card.querySelector('[data-field="latitude"]').value = "";
  card.querySelector('[data-field="longitude"]').value = "";
  card.querySelector('[data-field="cliente_id"]').value = "";
  card.querySelector('[data-field="cliente_nome"]').value = "";
  if (card._allocation) card._allocation.valor_obra = 0;
  renderGeoLabel(card);
}

function fillWorkFromExisting(card, id) {
  const work = app.obras.find(item => item.id === id);
  if (!work) return;
  card.querySelector('[data-field="uf"]').value = work.uf;
  card.querySelector('[data-field="obra_id"]').innerHTML = workOptions(id, work.uf);
  const name = card.querySelector('[data-field="nome"]');
  name.value = work.nome;
  name.readOnly = true;
  card.querySelector('[data-field="municipio"]').value = work.municipio || "";
  card.querySelector('[data-field="op_numero"]').value = work.op_padrao || "";
  card.querySelector('[data-field="endereco"]').value = work.endereco || "";
  card.querySelector('[data-field="latitude"]').value = work.latitude ?? "";
  card.querySelector('[data-field="longitude"]').value = work.longitude ?? "";
  card.querySelector('[data-field="cliente_id"]').value = work.cliente_id || "";
  card.querySelector('[data-field="cliente_nome"]').value = work.cliente_nome || work.municipio || "";
  renderGeoLabel(card);
  renderWorkSummary(card);
}

function refreshLoadWorkOptions() {
  $$(".load-work-card", $("#loadWorks")).forEach(card => {
    const uf = card.querySelector('[data-field="uf"]').value;
    const selected = card.querySelector('[data-field="obra_id"]').value;
    if (uf !== "OUTRO") card.querySelector('[data-field="obra_id"]').innerHTML = workOptions(selected, uf);
  });
}

function updateLoadWorkNumbers(rebalance = false) {
  $$(".load-work-card", $("#loadWorks")).forEach((card, index) => {
    card.querySelector(".work-order").textContent = String(index + 1);
  });
  renderAllocationRows(rebalance);
}

function renderGeoLabel(card) {
  const latitude = card.querySelector('[data-field="latitude"]').value;
  const longitude = card.querySelector('[data-field="longitude"]').value;
  const address = card.querySelector('[data-field="endereco"]').value;
  card.querySelector("[data-geo-title]").textContent = latitude && longitude ? `${Number(latitude).toFixed(5)}, ${Number(longitude).toFixed(5)}` : "SEM LOCALIZAÇÃO";
  card.querySelector("[data-geo-address]").textContent = address || "PESQUISE OU MARQUE NO MAPA";
}

function renderWorkSummary(card) {
  const name = card.querySelector('[data-field="nome"]').value || "NOVA OBRA";
  const totalQuantity = (card._items || []).reduce((sum, item) => sum + Number(item.quantidade || 0), 0);
  const share = Number(card._allocation?.percentual_rateio || 0);
  const cost = tripCostSummary.total * share / 100;
  const value = workItemValue(card);
  card._allocation = card._allocation || { valor_obra: 0, percentual_rateio: 0 };
  card._allocation.valor_obra = value;
  card.querySelector(".load-work-title").textContent = upper(name);
  card.querySelector(".work-items-badge").textContent = `${number(totalQuantity)} ITENS`;
  card.querySelector(".work-value-badge").textContent = `OBRA ${money(value)}`;
  card.querySelector(".work-cost-badge").textContent = money(cost);
  card.querySelector("[data-item-title]").textContent = card._items.length ? `${card._items.length} TIPOS SELECIONADOS` : "NENHUM ITEM SELECIONADO";
  card.querySelector("[data-item-summary]").textContent = card._items.length ? `${number(totalQuantity)} UNIDADES NO TOTAL` : "USE O CHECKLIST PARA INFORMAR AS QUANTIDADES";
}

function itemCatalogValue(code) {
  return Number(app.equipamentos.find(item => String(item.codigo) === String(code))?.valor_unit || 0);
}

function workItemValue(card) {
  return Math.round((card._items || []).reduce((sum, item) => {
    return sum + Math.max(0, Number(item.quantidade || 0)) * Math.max(0, itemCatalogValue(item.equipamento_codigo));
  }, 0) * 100) / 100;
}

function collectLoadWorks() {
  return $$(".load-work-card", $("#loadWorks")).map(card => {
    let uf = card.querySelector('[data-field="uf"]').value;
    let state = stateName(uf);
    if (uf === "OUTRO") {
      uf = upper(card.querySelector('[data-field="custom_uf"]').value);
      state = upper(card.querySelector('[data-field="custom_estado"]').value);
    }
    const get = field => card.querySelector(`[data-field="${field}"]`).value;
    return {
      obra_id: get("obra_id"), uf, estado: state, nome: upper(get("nome")),
      cliente_id: get("cliente_id"), cliente_nome: upper(get("cliente_nome")),
      municipio: upper(get("municipio")), op_numero: upper(get("op_numero")),
      referencia_contrato: upper(get("referencia_contrato")), previsao_entrega: get("previsao_entrega"),
      endereco: upper(get("endereco")), latitude: get("latitude"), longitude: get("longitude"),
      valor_obra: Number(card._allocation?.valor_obra || 0),
      percentual_rateio: Number(card._allocation?.percentual_rateio || 0),
      observacao: upper(get("observacao")), itens: card._items.map(item => ({ ...item })),
    };
  });
}

function costModeOptions(selected = "FIXO") {
  const modes = NEW_COST_MODES.includes(selected) ? NEW_COST_MODES : [...NEW_COST_MODES, selected];
  return modes.map(value => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(COST_MODE_LABELS[value] || value)}${NEW_COST_MODES.includes(value) ? "" : " · HISTÓRICO"}</option>`).join("");
}

function addCostRow(group, prefill = {}, recalculate = true) {
  const row = document.createElement("div");
  const mode = upper(prefill.modo || (group === "PESSOAL" ? "POR_FUNCIONARIO" : "FIXO"));
  row.className = "cost-row";
  row.dataset.costGroup = group;
  row.dataset.quantityManual = prefill.ajuste_manual ? "1" : "0";
  const enabled = prefill.ativo !== false && prefill.ativo !== 0 && prefill.ativo !== "0";
  const days = Math.max(0, Number($("#loadForm").elements.dias_viagem.value || 0));
  const initialQuantity = prefill.quantidade !== undefined && prefill.quantidade !== null
    ? Number(prefill.quantidade || 0) : (group === "PESSOAL" || mode === "POR_DIA" ? days : mode === "FIXO" ? 1 : 0);
  const modeControl = group === "PESSOAL"
    ? `<span class="cost-mode-display">POR FUNCIONÁRIO / DIA</span><input data-cost-field="modo" type="hidden" value="POR_FUNCIONARIO">`
    : `<select data-cost-field="modo" aria-label="BASE DE CÁLCULO">${costModeOptions(mode)}</select>`;
  row.innerHTML = `
    <input data-cost-field="descricao" data-upper aria-label="DESCRIÇÃO DA DESPESA" value="${escapeHtml(prefill.descricao || "NOVA DESPESA")}">
    <span class="cost-mode-control">${modeControl}</span>
    <input data-cost-field="valor_unitario" type="number" min="0" step="0.01" aria-label="VALOR UNITÁRIO" value="${Number(prefill.valor_unitario || 0)}">
    <input data-cost-field="quantidade" type="number" min="0" step="0.5" aria-label="DIAS OU HORAS APLICADOS" value="${initialQuantity}">
    <label class="cost-toggle" title="ATIVAR OU DESATIVAR ESTA DESPESA"><input data-cost-field="ativo" type="checkbox" ${enabled ? "checked" : ""}><span>USAR</span></label>
    <span class="cost-line-total">R$ 0,00</span>
    <button class="remove-cost" type="button" aria-label="REMOVER DESPESA">${icon("close")}</button>`;
  const container = group === "PESSOAL" ? $("#personnelCostRows") : $("#freightCostRows");
  container.append(row);
  const quantityInput = row.querySelector('[data-cost-field="quantidade"]');
  $$('input,select', row).filter(input => input !== quantityInput).forEach(input => input.addEventListener("input", renderTripCosts));
  quantityInput.addEventListener("input", () => { row.dataset.quantityManual = "1"; renderTripCosts(); });
  const modeInput = row.querySelector('[data-cost-field="modo"]');
  modeInput.addEventListener("change", () => {
    row.dataset.quantityManual = modeInput.value === "POR_HORA" ? "1" : "0";
    renderTripCosts();
  });
  row.querySelector(".remove-cost").onclick = () => { row.remove(); renderTripCosts(); };
  if (recalculate) renderTripCosts();
  return row;
}

function costRows(group = "") {
  const selector = group ? `[data-cost-group="${group}"]` : "[data-cost-group]";
  return $$(selector, $("#loadForm"));
}

function calculateCostRow(row) {
  const mode = row.querySelector('[data-cost-field="modo"]').value;
  const unit = Math.max(0, Number(row.querySelector('[data-cost-field="valor_unitario"]').value || 0));
  const quantityInput = row.querySelector('[data-cost-field="quantidade"]');
  const employees = Math.max(0, Number($("#loadForm").elements.funcionarios.value || 0));
  const tripDays = Math.max(0, Number($("#loadForm").elements.dias_viagem.value || 0));
  const enabled = row.querySelector('[data-cost-field="ativo"]').checked;
  let quantity = Math.max(0, Number(quantityInput.value || 0));
  let total = 0;
  const manual = row.dataset.quantityManual === "1";
  if (row.dataset.costGroup === "PESSOAL") {
    if (!manual) quantity = tripDays;
    total = unit * employees * quantity;
    quantityInput.readOnly = false;
    quantityInput.title = `${employees} FUNCIONÁRIO(S) × ${quantity} DIA(S)`;
  } else if (mode === "FIXO") {
    quantity = 1;
    total = unit;
    quantityInput.readOnly = true;
  } else if (mode === "POR_DIA") {
    if (!manual) quantity = tripDays;
    total = unit * quantity;
    quantityInput.readOnly = false;
  } else if (mode === "POR_HORA") {
    total = unit * quantity;
    quantityInput.readOnly = false;
  } else {
    total = unit * quantity;
    quantityInput.readOnly = false;
  }
  if (!enabled) total = 0;
  quantityInput.value = quantity;
  total = Math.round(total * 100) / 100;
  row.dataset.total = String(total);
  row.classList.toggle("inactive", !enabled);
  row.querySelector(".cost-line-total").textContent = money(total);
  return { mode, unit, quantity, total, enabled, manual };
}

function renderTripCosts() {
  const personnelRows = costRows("PESSOAL");
  const freightRows = costRows("FRETE");
  const personnelValues = personnelRows.map(calculateCostRow);
  const freightValues = freightRows.map(calculateCostRow);
  const personnel = personnelValues.reduce((sum, row) => sum + row.total, 0);
  const freight = freightValues.reduce((sum, row) => sum + row.total, 0);
  const base = personnelValues.reduce((sum, row) => sum + (row.enabled && row.mode === "POR_FUNCIONARIO" ? row.unit : 0), 0);
  tripCostSummary = {
    personnel: Math.round(personnel * 100) / 100,
    freight: Math.round(freight * 100) / 100,
    total: Math.round((personnel + freight) * 100) / 100,
    base: Math.round(base * 100) / 100,
  };
  $("#personnelBaseTotal").textContent = money(tripCostSummary.base);
  $("#personnelCostTotal").textContent = money(tripCostSummary.personnel);
  $("#freightRowsCount").textContent = String(freightRows.length);
  $("#freightCostTotal").textContent = money(tripCostSummary.freight);
  $("#summaryPersonnelCost").textContent = money(tripCostSummary.personnel);
  $("#summaryFreightCost").textContent = money(tripCostSummary.freight);
  $("#summaryTripCost").textContent = money(tripCostSummary.total);
  const enabledCount = [...personnelValues, ...freightValues].filter(row => row.enabled).length;
  $("#costCalculationBadge").textContent = `${enabledCount} DESPESAS ATIVAS · AUTOMÁTICO`;
  refreshAllocationValues();
}

function collectTripCosts() {
  return costRows().map(row => ({
    grupo: row.dataset.costGroup,
    descricao: upper(row.querySelector('[data-cost-field="descricao"]').value),
    modo: row.querySelector('[data-cost-field="modo"]').value,
    valor_unitario: Number(row.querySelector('[data-cost-field="valor_unitario"]').value || 0),
    quantidade: Number(row.querySelector('[data-cost-field="quantidade"]').value || 0),
    ajuste_manual: row.dataset.quantityManual === "1",
    ativo: row.querySelector('[data-cost-field="ativo"]').checked,
  }));
}

function resetCostComposition(costs = null) {
  $("#personnelCostRows").innerHTML = "";
  $("#freightCostRows").innerHTML = "";
  const rows = Array.isArray(costs) && costs.length ? costs : [...DEFAULT_PERSONNEL_COSTS, ...DEFAULT_FREIGHT_COSTS];
  rows.forEach(row => addCostRow(row.grupo, row, false));
  renderTripCosts();
}

function rebalanceWorkAllocations() {
  const cards = $$(".load-work-card", $("#loadWorks"));
  if (!cards.length) return;
  const values = cards.map(card => Math.max(0, Number(card._allocation?.valor_obra || 0)));
  const totalValue = values.reduce((sum, value) => sum + value, 0);
  let used = 0;
  cards.forEach((card, index) => {
    const value = totalValue > 0 && values.every(item => item > 0)
      ? (index === cards.length - 1 ? Math.round((100 - used) * 1000000) / 1000000 : Math.round(values[index] / totalValue * 1000000) / 10000)
      : 0;
    card._allocation = card._allocation || { valor_obra: 0, percentual_rateio: 0 };
    card._allocation.percentual_rateio = value;
    used += value;
  });
}

function renderAllocationRows(rebalance = false) {
  const cards = $$(".load-work-card", $("#loadWorks"));
  rebalanceWorkAllocations();
  $("#allocationRows").innerHTML = cards.map((card, index) => {
    const allocation = card._allocation || { valor_obra: 0, percentual_rateio: 0 };
    return `<div class="allocation-row" data-allocation-index="${index}">
      <div class="allocation-work"><b data-allocation-work>OBRA ${index + 1}</b><small data-allocation-op>AGUARDANDO IDENTIFICAÇÃO</small></div>
      <strong class="calculated-work-value" data-allocation-value>${money(allocation.valor_obra)}</strong>
      <input type="number" min="0" max="100" step="0.01" data-allocation-share aria-label="PERCENTUAL AUTOMÁTICO DA OBRA ${index + 1}" value="${Number(allocation.percentual_rateio || 0)}" readonly>
      <span class="allocation-value" data-allocation-freight>R$ 0,00</span>
      <span class="allocation-value" data-allocation-total>R$ 0,00</span>
      <div class="allocation-percentages"><span data-allocation-freight-percent>FRETE 0%</span><span data-allocation-total-percent>TOTAL 0%</span></div>
    </div>`;
  }).join("");
  refreshAllocationValues();
}

function allocatedParts(total, shares) {
  const valid = Math.abs(shares.reduce((sum, value) => sum + value, 0) - 100) <= 0.01;
  let used = 0;
  return shares.map((share, index) => {
    const value = valid && index === shares.length - 1
      ? Math.round((total - used) * 100) / 100
      : Math.round(total * share) / 100;
    used = Math.round((used + value) * 100) / 100;
    return value;
  });
}

function refreshAllocationValues() {
  const cards = $$(".load-work-card", $("#loadWorks"));
  const rows = $$(".allocation-row", $("#allocationRows"));
  if (rows.length !== cards.length) return;
  cards.forEach(card => {
    card._allocation = card._allocation || { valor_obra: 0, percentual_rateio: 0 };
    card._allocation.valor_obra = workItemValue(card);
  });
  rebalanceWorkAllocations();
  const shares = cards.map(card => Number(card._allocation?.percentual_rateio || 0));
  const personnelParts = allocatedParts(tripCostSummary.personnel, shares);
  const freightParts = allocatedParts(tripCostSummary.freight, shares);
  const sum = shares.reduce((total, value) => total + value, 0);
  const valid = cards.length > 0 && cards.every(card => Number(card._allocation?.valor_obra || 0) > 0) && Math.abs(sum - 100) <= 0.01;
  $("#allocationStatus").textContent = valid ? "ITENS SOMADOS · 100%" : "ITENS SEM VALOR";
  $("#allocationStatus").classList.toggle("invalid", !valid);
  rows.forEach((row, index) => {
    const card = cards[index];
    const value = Number(card._allocation?.valor_obra || 0);
    const freight = freightParts[index] || 0;
    const total = Math.round(((personnelParts[index] || 0) + freight) * 100) / 100;
    const name = card.querySelector('[data-field="nome"]').value || `OBRA ${index + 1}`;
    const op = card.querySelector('[data-field="op_numero"]').value || "SEM OP";
    row.querySelector("[data-allocation-work]").textContent = upper(name);
    row.querySelector("[data-allocation-value]").textContent = money(value);
    row.querySelector("[data-allocation-share]").value = Number(card._allocation?.percentual_rateio || 0) === 0 ? "" : Number(card._allocation.percentual_rateio).toFixed(2);
    row.querySelector("[data-allocation-op]").textContent = upper(op);
    row.querySelector("[data-allocation-freight]").textContent = money(freight);
    row.querySelector("[data-allocation-total]").textContent = money(total);
    row.querySelector("[data-allocation-freight-percent]").textContent = value ? `FRETE ${number(freight / value * 100)}%` : "FRETE —";
    row.querySelector("[data-allocation-total-percent]").textContent = value ? `TOTAL ${number(total / value * 100)}%` : "TOTAL —";
    renderWorkSummary(card);
  });
}

$("#addLoadWork").onclick = () => addLoadWork({}, true);
$("#addPersonnelCost").onclick = () => addCostRow("PESSOAL", { descricao: "OUTRAS DESPESAS", modo: "POR_FUNCIONARIO", valor_unitario: 0, ativo: true });
$("#addFreightCost").onclick = () => addCostRow("FRETE", { descricao: "OUTRAS DESPESAS", modo: "FIXO", valor_unitario: 0, ativo: true });
$("#loadForm").elements.funcionarios.addEventListener("input", renderTripCosts);
$("#loadForm").elements.dias_viagem.addEventListener("input", renderTripCosts);
$("#loadVehicleSelect").onchange = event => {
  const vehicle = app.caminhoes.find(item => item.id === event.target.value);
  if (!vehicle) return;
  const form = $("#loadForm");
  form.elements.veiculo.value = vehicle.modelo || "";
  form.elements.placa.value = vehicle.placa || "";
  form.elements.propriedade.value = vehicle.propriedade || "PROPRIO";
  form.elements.transportadora.value = vehicle.transportadora || "";
  if (!form.elements.motorista.value) form.elements.motorista.value = vehicle.motorista_padrao || "";
};

function openItemPicker(card) {
  itemPickerCard = card;
  pickerDraft = new Map((card._items || []).map(item => [String(item.equipamento_codigo), Number(item.quantidade || 0)]));
  pickerMeta = new Map((card._items || []).map(item => [String(item.equipamento_codigo), {
    unidade: item.unidade || "UN", observacao: item.observacao || "", praca_id: item.praca_id || "",
  }]));
  $("#pickerSearch").value = "";
  const groups = [...new Set(app.equipamentos.filter(item => item.ativo).map(item => item.grupo).filter(Boolean))].sort();
  $("#pickerGroup").innerHTML = `<option value="">TODOS OS GRUPOS</option>${groups.map(group => `<option>${escapeHtml(group)}</option>`).join("")}`;
  $("#itemPickerTitle").textContent = `ITENS · ${upper(card.querySelector('[data-field="nome"]').value || "NOVA OBRA")}`;
  renderItemPicker();
  $("#itemPickerDialog").showModal();
}

function renderItemPicker() {
  const query = upper($("#pickerSearch").value);
  const group = $("#pickerGroup").value;
  const rows = app.equipamentos.filter(item => item.ativo && (!group || item.grupo === group) && (!query || upper(`${item.codigo} ${item.grupo} ${item.nome}`).includes(query)));
  $("#itemPickerList").innerHTML = rows.map(item => {
    const selected = pickerDraft.has(String(item.codigo));
    const priced = Number(item.valor_unit || 0) > 0;
    const picture = item.imagem_url ? `<button type="button" class="picker-thumb image-click" data-image-url="${escapeHtml(item.imagem_url)}" data-image-title="${escapeHtml(item.codigo)} · ${escapeHtml(item.nome)}"><img src="${escapeHtml(item.imagem_url)}" alt="${escapeHtml(item.nome)}"></button>` : `<span class="picker-thumb">${icon("image")}</span>`;
    return `<div class="picker-item ${selected ? "selected" : ""} ${priced ? "" : "unpriced"}" data-picker-row="${escapeHtml(item.codigo)}">${picture}<input type="checkbox" aria-label="SELECIONAR ${escapeHtml(item.nome)}" data-picker-code="${escapeHtml(item.codigo)}" ${selected ? "checked" : ""} ${priced ? "" : "disabled"}><span><b>${escapeHtml(item.codigo)} · ${escapeHtml(item.nome)}</b><small>${escapeHtml(item.grupo || "SEM GRUPO")} · ${priced ? money(item.valor_unit) : "CADASTRE UM VALOR POSITIVO"}</small></span><input type="number" aria-label="QUANTIDADE DE ${escapeHtml(item.nome)}" min="1" max="1000" step="1" inputmode="numeric" data-picker-qty="${escapeHtml(item.codigo)}" value="${selected ? pickerDraft.get(String(item.codigo)) : 1}" ${selected && priced ? "" : "disabled"}></div>`;
  }).join("") || '<div class="empty-state"><b>NENHUM ITEM ENCONTRADO</b><span>AJUSTE A PESQUISA OU O GRUPO.</span></div>';
  $$('[data-picker-code]', $("#itemPickerList")).forEach(checkbox => {
    checkbox.onchange = () => {
      const code = checkbox.dataset.pickerCode;
      const quantity = $(`[data-picker-qty="${CSS.escape(code)}"]`, checkbox.closest(".picker-item"));
      if (checkbox.checked) {
        pickerDraft.set(code, Number(quantity.value || 1));
        if (!pickerMeta.has(code)) pickerMeta.set(code, { unidade: "UN", observacao: "", praca_id: "" });
      } else {
        pickerDraft.delete(code);
        pickerMeta.delete(code);
      }
      renderItemPicker();
    };
  });
  $$('[data-picker-qty]', $("#itemPickerList")).forEach(input => {
    input.oninput = () => {
      const value = Number(input.value);
      pickerDraft.set(input.dataset.pickerQty, Number.isFinite(value) ? value : 0);
      input.setCustomValidity(Number.isInteger(value) && value >= 1 && value <= 1000 ? "" : "USE UM INTEIRO ENTRE 1 E 1000.");
      updatePickerCounter();
    };
    input.onblur = () => {
      const value = Math.min(1000, Math.max(1, Math.trunc(Number(input.value) || 1)));
      input.value = String(value);
      input.setCustomValidity("");
      pickerDraft.set(input.dataset.pickerQty, value);
      updatePickerCounter();
    };
  });
  $$("[data-picker-row]", $("#itemPickerList")).forEach(row => {
    row.onclick = event => {
      if (event.target.closest('input,button')) return;
      const checkbox = row.querySelector('[data-picker-code]');
      if (checkbox.disabled) {
        toast("CADASTRE UM VALOR UNITÁRIO POSITIVO PARA USAR ESTE ITEM.", true);
        return;
      }
      checkbox.checked = !checkbox.checked;
      checkbox.dispatchEvent(new Event("change"));
    };
  });
  $$("[data-image-url]", $("#itemPickerList")).forEach(button => {
    button.onclick = event => { event.stopPropagation(); openImage(button.dataset.imageUrl, button.dataset.imageTitle); };
  });
  updatePickerCounter();
}

function updatePickerCounter() {
  const total = [...pickerDraft.values()].reduce((sum, value) => sum + Number(value || 0), 0);
  $("#pickerCounter").textContent = `${pickerDraft.size} TIPOS · ${number(total)} UNIDADES`;
}

$("#pickerSearch").oninput = renderItemPicker;
$("#pickerGroup").onchange = renderItemPicker;
$("#cancelItemPicker").onclick = () => $("#itemPickerDialog").close();
$("#applyItemPicker").onclick = () => {
  if (!itemPickerCard) return;
  const invalid = [...pickerDraft.values()].find(value => !Number.isInteger(Number(value)) || Number(value) < 1 || Number(value) > 1000);
  if (invalid !== undefined) {
    toast("AS QUANTIDADES DEVEM SER NÚMEROS INTEIROS ENTRE 1 E 1000.", true);
    return;
  }
  itemPickerCard._items = [...pickerDraft.entries()].map(([code, quantity]) => ({
    equipamento_codigo: code, quantidade: quantity,
    unidade: pickerMeta.get(code)?.unidade || "UN",
    observacao: pickerMeta.get(code)?.observacao || "",
    praca_id: pickerMeta.get(code)?.praca_id || "",
  }));
  renderWorkSummary(itemPickerCard);
  refreshAllocationValues();
  $("#itemPickerDialog").close();
  toast("CHECKLIST DE ITENS APLICADO.");
};

function offlineGridLayer() {
  const LocalGrid = L.GridLayer.extend({
    createTile(coords) {
      const tile = L.DomUtil.create("canvas", "leaflet-tile");
      const size = this.getTileSize();
      tile.width = size.x;
      tile.height = size.y;
      const context = tile.getContext("2d");
      context.fillStyle = "#e8f0f3";
      context.fillRect(0, 0, size.x, size.y);
      context.strokeStyle = "#cad9df";
      context.lineWidth = 1;
      context.strokeRect(0.5, 0.5, size.x - 1, size.y - 1);
      context.fillStyle = "#9bb0ba";
      context.font = "11px Segoe UI, Arial";
      context.fillText(`MAPA LOCAL · Z${coords.z}`, 12, 22);
      return tile;
    },
  });
  return new LocalGrid({ minZoom: 3, maxZoom: 18, attribution: "MAPA LOCAL" });
}

async function prepareOfflineMap(map) {
  if (!window.L || offlinePreparedMaps.has(map)) return;
  offlinePreparedMaps.add(map);
  offlineGridLayer().addTo(map);
  try {
    const config = await fetch("vendor/mapa/config.json", { cache: "no-store" }).then(response => response.json());
    const offlineResource = (app.resources || []).find(item => item.id === "MAPA_OFFLINE_BR");
    if (offlineResource?.installed) {
      const localLayer = L.tileLayer("/api/resources/map-tile/{z}/{x}/{y}.png", {
        minZoom: Number(config.tile_min_zoom || 4), maxZoom: Number(config.tile_max_zoom || 16),
        attribution: "MAPA LOCAL CJL System", errorTileUrl: "",
      });
      localLayer.on("load", () => { $("#offlineMapStatus").textContent = "MAPA OFFLINE LOCAL"; });
      localLayer.addTo(map);
    }
    const tileUrl = String(config.tile_url || "").trim();
    if (tileUrl) {
      const tileLayer = L.tileLayer(tileUrl, {
        minZoom: Number(config.tile_min_zoom || 4), maxZoom: Number(config.tile_max_zoom || 16),
        attribution: escapeHtml(config.atribuicao || "MAPA ONLINE"), errorTileUrl: "",
      });
      tileLayer.on("load", () => {
        if (!offlineResource?.installed) $("#offlineMapStatus").textContent = "MAPA ONLINE";
      });
      tileLayer.on("tileerror", () => {
        $("#offlineMapStatus").textContent = offlineResource?.installed ? "MAPA OFFLINE LOCAL" : "FALLBACK LOCAL";
      });
      tileLayer.addTo(map);
    }
    if (!offlineMapGeoJson) {
      offlineMapGeoJson = await fetch(config.geojson || "vendor/mapa/brasil.geojson").then(response => response.json());
    }
    L.geoJSON(offlineMapGeoJson, {
      interactive: false,
      style: { color: "#8aa8b5", weight: 1.4, fillColor: "#dbe8e5", fillOpacity: 0.35 },
    }).addTo(map);
  } catch (_) {
    $("#offlineMapStatus").textContent = "GRADE LOCAL";
  }
}

function openMapForCard(card) {
  mapApplyCallback = null;
  mapTargetCard = card;
  mapResolvedAddress = null;
  const get = field => card.querySelector(`[data-field="${field}"]`).value;
  const uf = get("uf") === "OUTRO" ? get("custom_uf") : get("uf");
  const center = UF_CENTERS[uf] || [-14.24, -51.93];
  const latitude = Number(get("latitude"));
  const longitude = Number(get("longitude"));
  const hasCoordinates = Number.isFinite(latitude) && Number.isFinite(longitude) && get("latitude") !== "" && get("longitude") !== "";
  const start = hasCoordinates ? [latitude, longitude] : center;
  const query = [get("endereco"), get("nome"), get("municipio"), stateName(uf), "BRASIL"].filter(Boolean).join(", ");
  $("#mapSearch").value = query;
  $("#mapLat").value = hasCoordinates ? latitude : "";
  $("#mapLng").value = hasCoordinates ? longitude : "";
  $("#mapDialog").showModal();
  setTimeout(async () => {
    initMap(start[0], start[1], hasCoordinates ? 15 : 7);
    if (!hasCoordinates && get("municipio")) await searchMap();
  }, 100);
}

function parseCoordinatePair(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  const decimalComma = text.match(/^\s*(-?\d{1,3}[.,]\d+)\s*[,; ]+\s*(-?\d{1,3}[.,]\d+)\s*$/);
  if (!decimalComma) return null;
  const normalize = part => Number(String(part).replace(",", "."));
  const latitude = normalize(decimalComma[1]);
  const longitude = normalize(decimalComma[2]);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  return { latitude, longitude };
}

function openMapForCoordinateInput(input, label = "LOCALIZAÇÃO") {
  mapTargetCard = null;
  mapResolvedAddress = null;
  mapApplyCallback = ({ latitude, longitude, cleared = false }) => {
    input.value = cleared ? "" : `${Number(latitude).toFixed(6)}, ${Number(longitude).toFixed(6)}`;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const parsed = parseCoordinatePair(input.value);
  const start = parsed ? [parsed.latitude, parsed.longitude] : [-14.24, -51.93];
  $("#mapSearch").value = input.value || label;
  $("#mapLat").value = parsed?.latitude ?? "";
  $("#mapLng").value = parsed?.longitude ?? "";
  $("#mapDialog").showModal();
  setTimeout(() => initMap(start[0], start[1], parsed ? 15 : 4), 100);
}

function initMap(latitude, longitude, zoom = 13) {
  const status = $("#mapStatus");
  if (!window.L) {
    status.textContent = "BIBLIOTECA LOCAL DO MAPA INDISPONÍVEL. INFORME AS COORDENADAS MANUALMENTE.";
    return;
  }
  if (!mapInstance) {
    mapInstance = L.map("miniMap").setView([latitude, longitude], zoom);
    prepareOfflineMap(mapInstance);
    mapInstance.on("click", event => selectMapPoint(event.latlng.lat, event.latlng.lng, true));
  } else {
    mapInstance.invalidateSize();
    mapInstance.setView([latitude, longitude], zoom);
  }
  if ($("#mapLat").value && $("#mapLng").value) selectMapPoint(Number($("#mapLat").value), Number($("#mapLng").value), false);
  status.textContent = "PESQUISE NOS CADASTROS LOCAIS OU CLIQUE EM UM PONTO DO MAPA.";
}

function selectMapPoint(latitude, longitude, reverse = false) {
  $("#mapLat").value = Number(latitude).toFixed(6);
  $("#mapLng").value = Number(longitude).toFixed(6);
  if (mapInstance) {
    if (mapMarker) mapMarker.setLatLng([latitude, longitude]);
    else mapMarker = L.marker([latitude, longitude]).addTo(mapInstance);
  }
  if (reverse) {
    mapResolvedAddress = null;
    $("#mapStatus").textContent = "PONTO SELECIONADO NO MAPA LOCAL. CONFIRA O ENDEREÇO INFORMADO.";
  }
}

async function searchMap() {
  const query = $("#mapSearch").value.trim();
  if (!query) return;
  $("#mapStatus").textContent = "PESQUISANDO NOS CADASTROS LOCAIS...";
  try {
    const parsed = await api(`/api/geo/parse?value=${encodeURIComponent(query)}`);
    selectMapPoint(parsed.latitude, parsed.longitude, false);
    mapInstance?.setView([parsed.latitude, parsed.longitude], 15);
    mapResolvedAddress = null;
    $("#mapStatus").textContent = `${parsed.format} INTERPRETADO: ${parsed.latitude}, ${parsed.longitude}.`;
    return;
  } catch (_) { }
  const normalized = upper(query);
  const found = app.obras.find(work => {
    if (work.latitude == null || work.longitude == null) return false;
    return [work.nome, work.municipio, work.endereco, work.uf]
      .filter(Boolean)
      .some(value => normalized.includes(upper(value)) || upper(value).includes(normalized));
  });
  if (!found) {
    $("#mapStatus").textContent = "PESQUISANDO ENDEREÇO NO MAPA ONLINE...";
    try {
      const online = await api(`/api/geo/search?q=${encodeURIComponent(query)}`);
      const result = online.results?.[0];
      if (!result) throw new Error("ENDEREÇO NÃO ENCONTRADO.");
      selectMapPoint(Number(result.latitude), Number(result.longitude), false);
      mapInstance?.setView([Number(result.latitude), Number(result.longitude)], 16);
      $("#mapSearch").value = upper(result.label || query);
      mapResolvedAddress = { state_code: result.state_code || "", city: result.city || "" };
      $("#mapStatus").textContent = "ENDEREÇO LOCALIZADO. CLIQUE NO MAPA PARA AJUSTAR O PONTO.";
      return;
    } catch (_) {
      $("#mapStatus").textContent = "ENDEREÇO NÃO ENCONTRADO. INFORME LATITUDE/LONGITUDE OU CLIQUE NO MAPA.";
      return;
    }
  }
  selectMapPoint(Number(found.latitude), Number(found.longitude), false);
  mapInstance?.setView([Number(found.latitude), Number(found.longitude)], 15);
  $("#mapSearch").value = upper([found.endereco, found.nome, found.municipio, found.uf].filter(Boolean).join(", "));
  mapResolvedAddress = { state_code: found.uf, city: found.municipio };
  $("#mapStatus").textContent = "REFERÊNCIA LOCAL ENCONTRADA. CLIQUE NO MAPA PARA AJUSTAR O PONTO.";
}

$("#mapSearchButton").onclick = searchMap;
$("#mapSearch").onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); searchMap(); } };
$("#openOnlineMap").onclick = () => {
  const latitude = $("#mapLat").value, longitude = $("#mapLng").value;
  const query = latitude && longitude ? `${latitude},${longitude}` : $("#mapSearch").value;
  window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`, "_blank", "noopener");
};
$("#clearMap").onclick = () => {
  if (mapTargetCard) {
    ["endereco", "latitude", "longitude"].forEach(field => { mapTargetCard.querySelector(`[data-field="${field}"]`).value = ""; });
    renderGeoLabel(mapTargetCard);
  } else if (mapApplyCallback) {
    mapApplyCallback({ latitude: "", longitude: "", cleared: true });
  }
  mapApplyCallback = null;
  $("#mapDialog").close();
};

function applyResolvedMapAddress(card) {
  if (!card || !mapResolvedAddress) return;
  const rawUf = mapResolvedAddress["ISO3166-2-lvl4"] || mapResolvedAddress.state_code || "";
  const uf = upper(rawUf).split("-").pop();
  const municipality = mapResolvedAddress.city || mapResolvedAddress.town || mapResolvedAddress.municipality
    || mapResolvedAddress.village || mapResolvedAddress.county || "";
  if (UF_CENTERS[uf]) {
    const ufSelect = card.querySelector('[data-field="uf"]');
    const workSelect = card.querySelector('[data-field="obra_id"]');
    const selectedWork = workSelect.value;
    ufSelect.value = uf;
    card.querySelector(".custom-state").hidden = true;
    workSelect.innerHTML = workOptions(selectedWork, uf);
  }
  if (municipality) card.querySelector('[data-field="municipio"]').value = upper(municipality);
}

$("#applyMap").onclick = () => {
  const latitude = $("#mapLat").value;
  const longitude = $("#mapLng").value;
  if (!latitude || !longitude) {
    toast("SELECIONE UM PONTO OU USE A OPÇÃO SEM LOCALIZAÇÃO.", true);
    return;
  }
  if (mapTargetCard) {
    mapTargetCard.querySelector('[data-field="latitude"]').value = latitude;
    mapTargetCard.querySelector('[data-field="longitude"]').value = longitude;
    mapTargetCard.querySelector('[data-field="endereco"]').value = upper($("#mapSearch").value);
    applyResolvedMapAddress(mapTargetCard);
    renderGeoLabel(mapTargetCard);
    toast("LOCALIZAÇÃO APLICADA À OBRA.");
  } else if (mapApplyCallback) {
    mapApplyCallback({ latitude, longitude });
    toast("LOCALIZAÇÃO APLICADA.");
  } else {
    return;
  }
  mapApplyCallback = null;
  $("#mapDialog").close();
};

function resetLoadForm() {
  const form = $("#loadForm");
  form.reset();
  editingLoadId = null;
  form.elements.carregamento_id.value = "";
  form.elements.data.value = today();
  form.elements.status.value = "PLANEJADO";
  form.elements.propriedade.value = "PROPRIO";
  form.elements.caminhao_id.value = "";
  form.elements.funcionarios.value = "";
  form.elements.dias_viagem.value = "";
  form.elements.distancia_km.value = "";
  $("#loadWorks").innerHTML = "";
  addLoadWork({ uf: "RJ" }, true);
  resetCostComposition();
  $("#loadFormKicker").textContent = "NOVO REGISTRO";
  $("#loadFormTitle").textContent = "CRIAR CARREGAMENTO";
  $("#loadFormBadge").textContent = "CADASTRO";
  $("#saveLoadButton").innerHTML = `${icon("save")}CRIAR CARREGAMENTO`;
  $("#cancelLoadEdit").hidden = true;
}

function loadIntoEditor(id) {
  const load = app.carregamentos.find(item => item.id === id);
  if (!load) return;
  if (!load.pode_editar) {
    toast("SOMENTE O CRIADOR DESTE REGISTRO OU UM ADMINISTRADOR PODE EDITÁ-LO.", true);
    return;
  }
  editingLoadId = id;
  const form = $("#loadForm");
  const fields = ["data", "hora", "status", "caminhao_id", "motorista", "veiculo", "placa", "propriedade", "transportadora", "data_saida", "hora_saida", "data_retorno", "solicitante", "funcionarios", "dias_viagem", "distancia_km", "observacao"];
  fields.forEach(field => { const value = load[field] ?? ""; form.elements[field].value = ["funcionarios","dias_viagem","distancia_km"].includes(field) && Number(value || 0) === 0 ? "" : value; });
  form.elements.carregamento_id.value = id;
  $("#loadWorks").innerHTML = "";
  load.obras.forEach((work, index) => addLoadWork({
    ...work,
    obra_id: work.id,
    itens: load.itens.filter(item => item.obra_id === work.id),
    anexos: (load.anexos || []).filter(item => item.obra_id === work.id || (!item.obra_id && index === 0)),
  }, false));
  $$(".load-work-card", $("#loadWorks")).forEach((card, index) => {
    card._allocation.valor_obra = Number(load.obras[index]?.valor_obra || 0);
    card._allocation.percentual_rateio = Number(load.obras[index]?.percentual_rateio || 0);
  });
  resetCostComposition(load.custos || []);
  renderAllocationRows(false);
  $("#loadFormKicker").textContent = "EDIÇÃO AUTORIZADA";
  $("#loadFormTitle").textContent = `EDITAR ${id}`;
  $("#loadFormBadge").textContent = load.status;
  $("#saveLoadButton").innerHTML = `${icon("save")}SALVAR ALTERAÇÕES`;
  $("#cancelLoadEdit").hidden = false;
  switchModule("carregamentos");
  showLoadView("editor");
}

function showLoadView(view, scroll = true) {
  const registry = view === "registry";
  $("#loadEditorCard").hidden = registry;
  $("#loadRegistryCard").hidden = !registry;
  $("#openLoadsView").classList.toggle("active-view", registry);
  $("#focusNewLoad").classList.toggle("active-view", !registry);
  if (scroll) (registry ? $("#loadRegistryCard") : $("#loadEditorCard")).scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#cancelLoadEdit").onclick = () => { resetLoadForm(); showLoadView("registry"); };
$("#focusNewLoad").onclick = () => { resetLoadForm(); showLoadView("editor"); };
$("#openLoadsView").onclick = () => showLoadView("registry");

function confirmExpeditionAction() {
  const dialog = $("#expeditionConfirmDialog");
  const acknowledgement = $("#expeditionAcknowledgement");
  const confirmButton = $("#confirmExpedition");
  const cancelButton = $("#cancelExpedition");
  acknowledgement.checked = false;
  confirmButton.disabled = true;
  dialog.returnValue = "cancel";
  acknowledgement.onchange = () => { confirmButton.disabled = !acknowledgement.checked; };
  cancelButton.onclick = () => dialog.close("cancel");
  confirmButton.onclick = () => {
    if (acknowledgement.checked) dialog.close("confirm");
  };
  dialog.showModal();
  return new Promise(resolve => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
  });
}

async function uploadPendingAttachments(savedLoad, batches) {
  let uploaded = 0;
  for (let index = 0; index < batches.length; index += 1) {
    const work = savedLoad.obras?.[index];
    for (const attachment of batches[index]) {
      await api(`/api/carregamentos/${encodeURIComponent(savedLoad.id)}/anexos`, {
        method: "POST",
        body: {
          nome_original: attachment.nome_original,
          mime: attachment.mime,
          data_base64: attachment.data_base64,
          obra_id: work?.id || "",
          op_numero: work?.op_numero || "",
        },
      });
      uploaded += 1;
    }
  }
  return uploaded;
}

$("#loadForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  const payload = formObject(event.target);
  payload.obras = collectLoadWorks();
  payload.custos = collectTripCosts();
  const invalidWork = payload.obras.find(work => !work.uf || !work.municipio || (!work.obra_id && !work.nome) || !work.op_numero);
  if (invalidWork) {
    toast("EM CADA OBRA, INFORME ESTADO, MUNICÍPIO, NOME/SELEÇÃO E ORDEM DE PRODUÇÃO.", true);
    return;
  }
  const planningOnly = payload.status === "PLANEJADO";
  if (!planningOnly && payload.obras.some(work => !work.itens.length)) {
    toast("SELECIONE PELO MENOS UM ITEM EM CADA OBRA.", true);
    return;
  }
  const invalidPriceItem = planningOnly ? null : payload.obras.flatMap(work => work.itens).find(item => itemCatalogValue(item.equipamento_codigo) <= 0);
  if (invalidPriceItem) {
    toast(`O ITEM ${invalidPriceItem.equipamento_codigo} PRECISA DE VALOR UNITÁRIO POSITIVO NO CATÁLOGO.`, true);
    return;
  }
  if (!planningOnly && payload.obras.some(work => Number(work.valor_obra || 0) <= 0)) {
    toast("TODOS OS ITENS SELECIONADOS PRECISAM TER VALOR UNITÁRIO POSITIVO NO CATÁLOGO.", true);
    return;
  }
  const cards = $$(".load-work-card", $("#loadWorks"));
  const attachmentBatches = cards.map(card => (card._pendingAttachments || []).map(item => ({ ...item })));
  const pendingAttachmentCount = attachmentBatches.reduce((total, rows) => total + rows.length, 0);
  const requestedExpedition = payload.status === "EXPEDIDO";
  if (requestedExpedition && !(await confirmExpeditionAction())) return;
  if (requestedExpedition && pendingAttachmentCount) {
    payload.status = app.carregamentos.find(item => item.id === editingLoadId)?.status || "CARREGADO";
  }
  payload.confirmar_expedicao = requestedExpedition && pendingAttachmentCount === 0;
  setBusy(true, editingLoadId ? "SALVANDO ALTERAÇÕES..." : "CRIANDO CARREGAMENTO...");
  let loadSaved = false;
  try {
    const id = editingLoadId;
    const saved = id
      ? await api(`/api/carregamentos/${id}`, { method: "PATCH", body: payload })
      : await api("/api/carregamentos", { method: "POST", body: payload });
    loadSaved = true;
    if (pendingAttachmentCount) {
      setBusy(true, `ENVIANDO ${pendingAttachmentCount} ANEXO(S)...`);
      try { await uploadPendingAttachments(saved, attachmentBatches); }
      finally { setBusy(false); }
    }
    if (requestedExpedition && pendingAttachmentCount) {
      await api(`/api/carregamentos/${encodeURIComponent(saved.id)}`, {
        method: "PATCH", body: { status: "EXPEDIDO", confirmar_expedicao: true },
      });
    }
    resetLoadForm();
    await loadAll(false);
    showLoadView("registry");
    toast(`${id ? "CARREGAMENTO ATUALIZADO" : "CARREGAMENTO CRIADO"}${pendingAttachmentCount ? ` COM ${pendingAttachmentCount} ANEXO(S)` : ""}.`);
  } catch (error) {
    if (loadSaved) await loadAll(false).catch(() => {});
    toast(loadSaved ? `CARREGAMENTO SALVO, MAS A ETAPA SEGUINTE FALHOU: ${error.message}` : error.message, true);
  } finally {
    setBusy(false);
  }
};

function filteredLoads() {
  const query = upper($("#loadSearch").value);
  const year = $("#loadYearFilter").value;
  const month = $("#loadMonthFilter").value;
  const status = $("#loadStatusFilter").value;
  const uf = $("#loadUfFilter").value;
  return app.carregamentos.filter(load => {
    const loadDate = String(load.data || "");
    if (year && loadDate.slice(0, 4) !== year) return false;
    if (month && loadDate.slice(5, 7) !== month) return false;
    if (status && load.status !== status) return false;
    if (uf && !(load.obras || []).some(work => work.uf === uf)) return false;
    const haystack = upper(`${load.id} ${load.motorista} ${load.veiculo} ${load.placa} ${(load.obras || []).map(work => `${work.nome} ${work.municipio} ${work.op_numero} ${work.uf}`).join(" ")}`);
    return !query || haystack.includes(query);
  });
}

function renderLoads() {
  const rows = filteredLoads();
  $("#loadsBadge").textContent = `${rows.length} REGISTRO${rows.length === 1 ? "" : "S"}`;
  if (!rows.length) {
    $("#loadsGrid").innerHTML = `<div class="empty-state">${icon("truck")}<b>NENHUM CARREGAMENTO ENCONTRADO</b><span>CRIE UM NOVO REGISTRO OU AJUSTE OS FILTROS.</span></div>`;
    return;
  }
  const statusOrder = ["PLANEJADO", "EM CARREGAMENTO", "CARREGADO", "EXPEDIDO", "CANCELADO"];
  const selectedYear = $("#loadYearFilter").value;
  const selectedMonth = $("#loadMonthFilter").value;
  const currentMonth = new Date().toLocaleDateString("en-CA").slice(5, 7);
  const years = [...new Set(rows.map(load => String(load.data).slice(0, 4)))].sort().reverse();
  const loadCard = load => {
      const works = load.obras || [];
      const routes = works.map(work => `<div class="route-line"><span>${escapeHtml(work.uf)}</span><b>${escapeHtml(work.nome)}</b><small>${escapeHtml(work.op_numero || "SEM OP")} · VALOR DA OBRA ${money(work.valor_obra)}</small></div>`).join("");
      return `<article class="load-card status-${statusClass(load.status)}" data-load-id="${load.id}" tabindex="0" role="button" aria-label="ABRIR ${load.id}">
        <div class="load-card-top"><div><h4 class="load-card-id">${escapeHtml(load.id)}</h4><span class="load-card-date">${dateBr(load.data)} ${escapeHtml(load.hora || "")} · ${load.propriedade === "ALUGADO" ? "CAMINHÃO ALUGADO" : "CAMINHÃO PRÓPRIO"}</span></div><span class="status-pill ${statusClass(load.status)}">${escapeHtml(load.status)}</span></div>
        ${load.aguardando_complementacao ? `<div class="ownership-note">${icon("route")}AGUARDANDO COMPLEMENTAÇÃO DE ITENS / DOCUMENTOS / FOTOS</div>` : ""}
        <div class="load-card-route">${routes}</div>
        <div class="load-card-vehicle"><div class="mini-info"><span>MOTORISTA</span><b>${escapeHtml(load.motorista || "NÃO INFORMADO")}</b></div><div class="mini-info"><span>CAMINHÃO / PLACA</span><b>${escapeHtml(load.veiculo || "NÃO INFORMADO")} · ${escapeHtml(load.placa || "SEM PLACA")}</b></div></div>
        <div class="load-card-footer"><div class="load-metric"><span>OBRAS</span><b>${works.length}</b></div><div class="load-metric"><span>ITENS</span><b>${number(load.quantidade_total)}</b></div><div class="load-metric value"><span>VALOR DA CARGA</span><b>${money(load.valor_carga)}</b></div><div class="load-metric"><span>CUSTO</span><b>${money(load.custo_total)}</b></div></div>
      </article>`;
  };
  $("#loadsGrid").innerHTML = years.map(year => {
    const yearly = rows.filter(load => String(load.data).slice(0, 4) === year);
    const months = [...new Set(yearly.map(load => String(load.data).slice(5, 7)))].sort().reverse();
    const yearOpen = year === selectedYear || years.length === 1;
    const monthGroups = months.map((month, monthIndex) => {
      const monthly = yearly.filter(load => String(load.data).slice(5, 7) === month);
      const monthOpen = selectedMonth
        ? month === selectedMonth
        : ((year === String(new Date().getFullYear()) && month === currentMonth) || monthIndex === 0);
      const statusGroups = statusOrder.map(status => {
        const grouped = monthly.filter(load => load.status === status);
        if (!grouped.length) return "";
        const cards = grouped.map(loadCard).join("");
        return `<details class="load-status-group status-${statusClass(status)}" open><summary><span>${escapeHtml(status)}</span><b>${grouped.length} CARREGAMENTO${grouped.length === 1 ? "" : "S"}</b></summary><div class="load-cards-grid">${cards}</div></details>`;
      }).join("");
      return `<details class="load-month-group" ${monthOpen ? "open" : ""}><summary><span>${escapeHtml(MONTH_LABELS[month] || month)}</span><b>${monthly.length} REGISTRO${monthly.length === 1 ? "" : "S"}</b></summary><div class="load-month-body">${statusGroups}</div></details>`;
    }).join("");
    return `<details class="load-year-group" ${yearOpen ? "open" : ""}><summary><span>ANO ${escapeHtml(year)}</span><b>${yearly.length} REGISTRO${yearly.length === 1 ? "" : "S"}</b></summary><div class="load-year-body">${monthGroups}</div></details>`;
  }).join("");
  $$(".load-card", $("#loadsGrid")).forEach(card => {
    card.onclick = () => openLoadDetail(card.dataset.loadId);
    card.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openLoadDetail(card.dataset.loadId); } };
  });
}

function detailBox(label, value, css = "") {
  return `<div class="detail-box ${css}"><span>${escapeHtml(label)}</span><b>${escapeHtml(value || "—")}</b></div>`;
}

async function requestDeletion(kind, id, label) {
  const reason = window.prompt(`MOTIVO DA EXCLUSÃO DE ${label}:`, "");
  if (reason === null) return;
  setBusy(true, "ENVIANDO PARA A FILA DE EXCLUSÃO...");
  try {
    const routes = { CLIENTE: "clientes", OBRA: "obras", CARREGAMENTO: "carregamentos" };
    await api(`/api/${routes[kind]}/${encodeURIComponent(id)}`, { method: "DELETE", body: { motivo: reason } });
    $("#loadDetailDialog").open && $("#loadDetailDialog").close();
    await loadAll(false);
    toast("REGISTRO OCULTADO E ENVIADO PARA REVISÃO DO ADMINISTRADOR.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}

function detailCostTable(title, rows) {
  const activeRows = rows.filter(row => row.ativo !== 0);
  return `<section class="detail-cost-table"><h4>${escapeHtml(title)}</h4>${activeRows.length ? activeRows.map(row => {
    const rule = row.grupo === "PESSOAL" && row.modo === "POR_FUNCIONARIO"
      ? `${number(row.funcionarios_aplicados)} FUNC. × ${number(row.quantidade)} DIAS`
      : row.modo === "POR_DIA" ? `${number(row.quantidade)} DIAS`
      : row.modo === "POR_HORA" ? `${number(row.quantidade)} HORAS` : "VALOR FIXO";
    return `<div class="detail-cost-line"><span><b>${escapeHtml(row.descricao)}</b><br><small class="muted">${escapeHtml(rule)}${row.ajuste_manual ? " · AJUSTADO" : ""}</small></span><span>${money(row.valor_unitario)}</span><span>${money(row.total)}</span></div>`;
  }).join("") : '<div class="detail-cost-line"><span>SEM DESPESAS ATIVAS</span><span>—</span><span>R$ 0,00</span></div>'}</section>`;
}

function fileSize(value) {
  const bytes = Number(value || 0);
  if (bytes >= 1024 * 1024) return `${number(bytes / 1024 / 1024)} MB`;
  return `${number(bytes / 1024)} KB`;
}

function openLoadDetail(id) {
  const load = app.carregamentos.find(item => item.id === id);
  if (!load) return;
  detailLoadId = id;
  $("#loadDetailTitle").textContent = `${load.id} · ${load.status}`;
  $("#loadDetailSubtitle").textContent = `${dateBr(load.data)} ${load.hora || ""} · ${load.obras.length} OBRA(S) · ${number(load.quantidade_total)} ITENS`;
  $("#loadDetailSummary").innerHTML = `<div class="detail-grid">
    ${detailBox("STATUS", load.status)}${detailBox("DATA / HORA", `${dateBr(load.data)} ${load.hora || ""}`)}${detailBox("DATA / HORA DE SAÍDA", `${dateBr(load.data_saida)} ${load.hora_saida || ""}`)}${detailBox("RETORNO PREVISTO", dateBr(load.data_retorno))}
    ${detailBox("REGISTRO / REVISÃO", `${load.id} · REV. ${load.revisao_operacional || 1}`)}${detailBox("CRIADO POR", load.criador_usuario_nome || "ADMIN", "wide")}${detailBox("SOLICITANTE", load.solicitante || "NÃO INFORMADO", "wide")}
    ${detailBox("MOTORISTA", load.motorista || "NÃO INFORMADO", "wide")}${detailBox("CAMINHÃO", load.veiculo || "NÃO INFORMADO")}${detailBox("PLACA", load.placa || "NÃO INFORMADA")}
    ${detailBox("PROPRIEDADE", load.propriedade === "ALUGADO" ? "ALUGADO" : "PRÓPRIO")}${detailBox("TRANSPORTADORA / LOCADOR", load.transportadora || "NÃO INFORMADO", "wide")}${detailBox("VALOR DA CARGA", money(load.valor_carga))}${detailBox("CUSTO TOTAL", money(load.custo_total))}
    ${detailBox("OBSERVAÇÃO", load.observacao || "SEM OBSERVAÇÃO", "full")}
  </div>`;
  $("#loadDetailWorks").innerHTML = load.obras.map(work => {
    const items = load.itens.filter(item => item.obra_id === work.id);
    return `<section class="detail-work"><div class="detail-work-head"><b>${escapeHtml(work.uf)} · ${escapeHtml(work.nome)} · ${escapeHtml(work.op_numero)}</b><div class="detail-work-actions"><span class="badge blue">${number(items.reduce((sum, item) => sum + Number(item.quantidade), 0))} ITENS</span><span class="badge green">INCLUÍDA NO PACOTE DOCUMENTAL</span></div></div><div class="detail-work-body"><div class="detail-grid">${detailBox("CLIENTE", work.cliente_nome || work.municipio || "NÃO INFORMADO", "wide")}${detailBox("MUNICÍPIO", work.municipio)}${detailBox("CONTRATO / REFERÊNCIA", work.referencia_contrato || "NÃO INFORMADO")}${detailBox("PREVISÃO DE ENTREGA", dateBr(work.previsao_entrega))}${detailBox("ENDEREÇO", work.endereco || "NÃO INFORMADO", "wide")}${detailBox("COORDENADAS", work.latitude != null && work.longitude != null ? `${work.latitude}, ${work.longitude}` : "NÃO INFORMADA")}${detailBox("VALOR DA OBRA", money(work.valor_obra))}${detailBox("RATEIO DA VIAGEM", `${number(work.percentual_rateio)}%`)}${detailBox("CUSTO RATEADO", money(work.custo_viagem), "wide")}</div><div class="detail-items">${items.length ? items.map(item => {
      const imageUrl = item.imagem_arquivo ? `/api/equipamentos/${encodeURIComponent(item.equipamento_codigo)}/imagem?v=${encodeURIComponent(item.imagem_atualizada_em || "")}` : "";
      const picture = imageUrl ? `<button type="button" class="detail-item-thumb image-click" data-image-url="${imageUrl}" data-image-title="${escapeHtml(item.equipamento_codigo)} · ${escapeHtml(item.equipamento_nome)}"><img src="${imageUrl}" alt="${escapeHtml(item.equipamento_nome)}"></button>` : `<span class="detail-item-thumb">${icon("image")}</span>`;
      return `<div class="detail-item-row">${picture}<b>${escapeHtml(item.equipamento_codigo)}</b><span>${escapeHtml(item.equipamento_nome)}<br><small class="muted">${escapeHtml(item.unidade || "UN")}${item.observacao ? ` · ${escapeHtml(item.observacao)}` : ""}</small></span><b class="num">${number(item.quantidade)}</b></div>`;
    }).join("") : '<span class="muted">SEM ITENS.</span>'}</div></div></section>`;
  }).join("");
  const costSummary = load.custos_resumo || { tarifa_base_pessoal: 0, custo_pessoal: 0, custo_frete: 0, custo_total: load.custo_total || 0 };
  const personnelCosts = (load.custos || []).filter(row => row.grupo === "PESSOAL");
  const freightCosts = (load.custos || []).filter(row => row.grupo === "FRETE");
  const allocations = load.obras.map(work => `<div class="detail-allocation-row"><span><b>${escapeHtml(work.uf)} · ${escapeHtml(work.nome)}</b><br><small class="muted">VALOR ${money(work.valor_obra)} · FRETE ${number(work.percentual_frete_obra)}% · TOTAL ${number(work.percentual_total_obra)}%</small></span><b>${number(work.percentual_rateio)}%</b><b>${money(work.custo_frete)}</b><b>${money(work.custo_viagem)}</b></div>`).join("");
  $("#loadDetailTrip").innerHTML = `<div class="detail-grid">${detailBox("FUNCIONÁRIOS", number(load.funcionarios))}${detailBox("DIAS DE VIAGEM", number(load.dias_viagem))}${detailBox("DISTÂNCIA TOTAL", `${number(load.distancia_km)} KM`)}${detailBox("TARIFA-BASE PESSOAL", money(costSummary.tarifa_base_pessoal))}${detailBox("CUSTO DE PESSOAL", money(costSummary.custo_pessoal))}${detailBox("CUSTO DO FRETE", money(costSummary.custo_frete))}${detailBox("CUSTO TOTAL DA VIAGEM", money(costSummary.custo_total), "wide")}</div><div class="detail-cost-columns">${detailCostTable("GASTO POR FUNCIONÁRIO", personnelCosts)}${detailCostTable("CUSTO DO FRETE", freightCosts)}</div><section class="detail-work detail-allocation"><div class="detail-work-head"><b>RATEIO POR OBRA</b><span class="badge purple">100%</span></div><div class="detail-allocation-row"><b>OBRA / INDICADORES</b><b>RATEIO</b><b>FRETE</b><b>TOTAL</b></div>${allocations}</section>`;
  const evidences = load.evidencias || [];
  const photoStage = (stage, label, canUpload) => {
    const rows = evidences.filter(item => item.etapa === stage);
    return `<section class="photo-stage"><div class="photo-stage-head"><div><b>${label}</b><small>${rows.length} DE 50 FOTOS</small></div>${canUpload ? `<button class="btn primary small add-photo" type="button" data-stage="${stage}">${icon("image")}ADICIONAR FOTOS</button><input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden data-photo-input="${stage}">` : `<span class="badge purple">LIBERADO APÓS EXPEDIDO</span>`}</div><div class="photo-grid">${rows.length ? rows.map(item => `<article class="photo-card"><a href="${escapeHtml(item.download_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(item.download_url)}" alt="${escapeHtml(item.nome_original)}"></a><div><small>${escapeHtml(item.nome_original)}</small><small>SHA-256 ${escapeHtml(String(item.sha256).slice(0,12))}…</small><div class="photo-actions"><a class="btn soft small" href="${escapeHtml(item.download_url)}">BAIXAR</a>${load.status !== "EXPEDIDO" || app.auth?.user?.perfil === "ADMIN" ? `<button class="btn danger small remove-photo" data-evidence-id="${escapeHtml(item.id)}">REMOVER</button>` : ""}</div></div></article>`).join("") : '<div class="empty-state"><b>NENHUMA FOTO</b><span>AS EVIDÊNCIAS FICAM SEPARADAS DOS DOCUMENTOS.</span></div>'}</div></section>`;
  };
  $("#loadDetailPhotos").innerHTML = photoStage("CARREGAMENTO", "FOTOS DO CARREGAMENTO", true) + photoStage("DESCARREGAMENTO", "FOTOS DO DESCARREGAMENTO", load.status === "EXPEDIDO");
  const attachments = load.anexos || [];
  $("#loadDetailAttachments").innerHTML = `<div class="attachment-detail-head"><div><b>ARQUIVOS VINCULADOS AO CARREGAMENTO</b><small>${attachments.length} DE 10 ANEXOS UTILIZADOS</small></div><span class="badge blue">XLSX · XLS · PDF · DOCX</span></div><div class="attachment-detail-list">${attachments.length ? attachments.map(item => {
    const work = load.obras.find(row => row.id === item.obra_id);
    return `<article class="attachment-detail-row"><span class="attachment-file-icon">${icon("folder")}</span><div><b>${escapeHtml(item.nome_original)}</b><small>${escapeHtml(work ? `${work.uf} · ${work.nome}` : "CARREGAMENTO GERAL")} · ${escapeHtml(item.op_numero || "SEM OP")} · ${fileSize(item.tamanho)}<br>SHA-256 ${escapeHtml(String(item.sha256 || "").slice(0, 16))}… · ${escapeHtml(item.usuario_nome || "SISTEMA")}</small></div><a class="btn soft small" href="${escapeHtml(item.download_url)}">BAIXAR</a>${load.status === "EXPEDIDO" ? `<span class="badge purple">BLOQUEADO</span>` : `<button class="btn danger small remove-attachment" type="button" data-attachment-id="${escapeHtml(item.id)}">REMOVER</button>`}</article>`;
  }).join("") : '<div class="empty-state"><b>NENHUM ANEXO</b><span>ADICIONE ARQUIVOS AO EDITAR O CARREGAMENTO.</span></div>'}</div>`;
  const documents = load.documentos || [];
  $("#loadDetailDocuments").innerHTML = `<div class="document-actions"><div><b>PACOTE OFICIAL DO CARREGAMENTO</b><small>EXCEL É GERADO SEMPRE. PDFs SÃO GERADOS QUANDO O LIBREOFFICE OPCIONAL ESTIVER DISPONÍVEL NO RUNTIME ASSINADO.</small></div><button class="btn primary" type="button" id="generateLoadDocuments">${icon("save")}GERAR NOVA REVISÃO</button></div><div class="document-revision-list">${documents.length ? documents.map(document => `<section class="document-revision"><div class="document-revision-head"><div><b>REVISÃO ${String(document.revisao).padStart(3, "0")}</b><small>${escapeHtml(String(document.gerado_em || "").replace("T", " "))} · ${escapeHtml(document.usuario_nome || "SISTEMA")} · ${escapeHtml(document.estacao_id || "—")}</small></div><span class="badge green">HASH ${escapeHtml(String(document.workbook_sha256 || "").slice(0, 12))}…</span></div><div class="document-files">${(document.arquivos || []).map(file => `<a class="document-file" href="${escapeHtml(file.download_url)}"><span class="attachment-file-icon">${icon(file.tipo === "PDF" ? "save" : "folder")}</span><span><b>${escapeHtml(file.nome)}</b><small>${escapeHtml(file.tipo)} · ${fileSize(file.tamanho)} · SHA-256 ${escapeHtml(String(file.sha256 || "").slice(0, 12))}…</small></span><strong>BAIXAR</strong></a>`).join("")}</div></section>`).join("") : '<div class="empty-state"><b>NENHUM DOCUMENTO GERADO</b><span>CLIQUE EM GERAR NOVA REVISÃO. O EXCEL NÃO DEPENDE DO LIBREOFFICE.</span></div>'}</div>`;
  $("#generateLoadDocuments").onclick = async () => {
    setBusy(true, "GERANDO DOCUMENTOS...");
    try {
      const generated = await api(`/api/carregamentos/${encodeURIComponent(id)}/documentos`, { method: "POST", body: {} });
      $("#loadDetailDialog").close();
      await loadAll(false);
      openLoadDetail(id);
      toast(generated.aviso || "NOVA REVISÃO DOCUMENTAL GERADA E VALIDADA.", Boolean(generated.aviso));
    } catch (error) { toast(error.message, true); }
    finally { setBusy(false); }
  };

  if (load.status === "EXPEDIDO" && !load.pode_editar) {
    $("#loadStatusAction").innerHTML = `<span class="locked-note">${icon("lock")}EXPEDIDO · REGISTRO BLOQUEADO</span>`;
    $("#editLoadFromDetail").disabled = true;
  } else {
    $("#loadStatusAction").innerHTML = `<select id="quickLoadStatus">${["PLANEJADO", "EM CARREGAMENTO", "CARREGADO", "EXPEDIDO", "CANCELADO"].map(status => `<option ${status === load.status ? "selected" : ""}>${status}</option>`).join("")}</select><button class="btn soft" type="button" id="saveQuickStatus">SALVAR STATUS</button>`;
    $("#editLoadFromDetail").disabled = !load.pode_editar;
    $("#saveQuickStatus").onclick = async () => {
      const status = $("#quickLoadStatus").value;
      if (status === "EXPEDIDO" && !(await confirmExpeditionAction())) return;
      setBusy(true, "ATUALIZANDO STATUS...");
      try {
        await api(`/api/carregamentos/${id}`, { method: "PATCH", body: { status, confirmar_expedicao: status === "EXPEDIDO" } });
        await loadAll(false);
        $("#loadDetailDialog").close();
        toast("STATUS ATUALIZADO.");
      } catch (error) { toast(error.message, true); }
      finally { setBusy(false); }
    };
  }
  $$(".detail-menu button").forEach((button, index) => button.classList.toggle("active", index === 0));
  $$("[data-detail-panel]").forEach((panel, index) => panel.classList.toggle("active", index === 0));
  $$("#loadDetailWorks [data-image-url]").forEach(button => {
    button.onclick = () => openImage(button.dataset.imageUrl, button.dataset.imageTitle);
  });
  $$("#loadDetailAttachments .remove-attachment").forEach(button => {
    button.onclick = async () => {
      setBusy(true, "REMOVENDO ANEXO...");
      try {
        await api(`/api/anexos/${encodeURIComponent(button.dataset.attachmentId)}`, { method: "DELETE", body: {} });
        $("#loadDetailDialog").close();
        await loadAll(false);
        openLoadDetail(id);
        toast("ANEXO REMOVIDO DO CARREGAMENTO.");
      } catch (error) { toast(error.message, true); }
      finally { setBusy(false); }
    };
  });
  $$("#loadDetailPhotos .add-photo").forEach(button => {
    const input = $(`[data-photo-input="${button.dataset.stage}"]`, $("#loadDetailPhotos"));
    button.onclick = () => input.click();
    input.onchange = async () => {
      const files = [...(input.files || [])];
      if (!files.length) return;
      setBusy(true, `ENVIANDO ${files.length} FOTO(S)...`);
      try {
        for (const file of files) await api(`/api/carregamentos/${encodeURIComponent(id)}/evidencias`, { method: "POST", body: { etapa: button.dataset.stage, nome_original: file.name, imagem_base64: await attachmentToDataUrl(file) } });
        await loadAll(false); $("#loadDetailDialog").close(); openLoadDetail(id); toast("FOTOS REGISTRADAS COM HASH E AUTORIA.");
      } catch (error) { toast(error.message, true); }
      finally { setBusy(false); }
    };
  });
  $$("#loadDetailPhotos .remove-photo").forEach(button => { button.onclick = async () => {
    setBusy(true, "REMOVENDO FOTO...");
    try { await api(`/api/evidencias/${encodeURIComponent(button.dataset.evidenceId)}`, { method: "DELETE", body: {} }); await loadAll(false); $("#loadDetailDialog").close(); openLoadDetail(id); toast("FOTO REMOVIDA DA VISUALIZAÇÃO."); }
    catch (error) { toast(error.message, true); } finally { setBusy(false); }
  }; });
  $("#loadDetailDialog").showModal();
}

$$(".detail-menu button").forEach(button => {
  button.onclick = () => {
    $$(".detail-menu button").forEach(item => item.classList.toggle("active", item === button));
    $$("[data-detail-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.detailPanel === button.dataset.detailTab));
  };
});
$("#editLoadFromDetail").onclick = () => { $("#loadDetailDialog").close(); loadIntoEditor(detailLoadId); };
$("#deleteLoadFromDetail").onclick = () => {
  const load = app.carregamentos.find(item => item.id === detailLoadId);
  if (load) requestDeletion("CARREGAMENTO", load.id, load.id);
};
$("#loadSearch").oninput = renderLoads;
$("#loadYearFilter").onchange = renderLoads;
$("#loadMonthFilter").onchange = renderLoads;
$("#loadStatusFilter").onchange = renderLoads;
$("#loadUfFilter").onchange = renderLoads;

function renderWorks() {
  const query = upper($("#workSearch").value);
  const uf = $("#workUfFilter").value;
  const status = $("#workStatusFilter").value;
  const rows = app.obras.filter(work => (!uf || work.uf === uf) && (!status || work.status === status) && (!query || upper(`${work.id} ${work.uf} ${work.nome} ${work.municipio} ${work.op_padrao} ${work.codigo}`).includes(query)));
  const usedStates = new Set(app.obras.map(work => work.uf));
  $("#worksCount").textContent = String(app.obras.length);
  $("#activeWorksCount").textContent = String(app.obras.filter(work => work.status === "ATIVA").length);
  $("#workStatesCount").textContent = String(usedStates.size);
  $("#worksBadge").textContent = `${rows.length} OBRA${rows.length === 1 ? "" : "S"}`;
  $("#worksTable").innerHTML = rows.map(work => {
    const loads = app.carregamentos.filter(load => load.obras.some(item => item.id === work.id));
    const latest = loads.map(load => load.data).sort().reverse()[0] || "";
    return `<tr><td><b>${escapeHtml(work.id)}</b></td><td><span class="badge blue">${escapeHtml(work.uf)}</span></td><td><b>${escapeHtml(work.nome)}</b><br><small class="muted">CLIENTE: ${escapeHtml(work.cliente_nome || work.municipio || "—")} · ${escapeHtml(work.codigo || "SEM CÓDIGO")}</small></td><td>${escapeHtml(work.municipio || "—")}</td><td>${escapeHtml(work.op_padrao || "—")}</td><td><span class="status-dot ${work.status === "ATIVA" ? "" : "inactive"}">${escapeHtml(work.status)}</span></td><td class="num"><b>${loads.length}</b></td><td>${latest ? dateBr(latest) : "—"}</td><td class="num"><div class="admin-list-actions"><button class="btn soft small edit-work" data-id="${work.id}">${icon("edit")}EDITAR</button><button class="btn danger small delete-work" data-id="${work.id}" data-label="${escapeHtml(work.nome)}">${icon("close")}EXCLUIR</button></div></td></tr>`;
  }).join("") || '<tr><td colspan="9" class="muted">NENHUMA OBRA ENCONTRADA.</td></tr>';
  $$(".edit-work").forEach(button => { button.onclick = () => openWorkDialog(button.dataset.id); });
  $$(".delete-work").forEach(button => { button.onclick = () => requestDeletion("OBRA", button.dataset.id, button.dataset.label); });
}

function openWorkDialog(id = "") {
  const form = $("#workForm");
  form.reset();
  form.elements.unidade_id.innerHTML = unitOptions();
  form.elements.obra_id.value = id;
  const work = app.obras.find(item => item.id === id);
  if (work) {
    $("#workDialogTitle").textContent = `EDITAR ${work.id}`;
    form.elements.unidade_id.value = work.unidade_id;
    form.elements.unidade_id.disabled = true;
    ["nome", "municipio", "codigo", "status", "endereco", "latitude", "longitude", "op_padrao", "cliente_nome"].forEach(field => { form.elements[field].value = work[field] ?? ""; });
    form.elements.cliente_id.value = work.cliente_id || "";
  } else {
    $("#workDialogTitle").textContent = "NOVA OBRA";
    form.elements.unidade_id.disabled = false;
    const rj = app.unidades.find(unit => unit.uf === "RJ");
    if (rj) form.elements.unidade_id.value = rj.id;
    form.elements.status.value = "ATIVA";
  }
  $("#workDialog").showModal();
}

$("#workForm").elements.cliente_nome.addEventListener("input", () => {
  $("#workForm").elements.cliente_id.value = "";
});

$("#newWorkButton").onclick = () => openWorkDialog();
$("#workSearch").oninput = renderWorks;
$("#workUfFilter").onchange = renderWorks;
$("#workStatusFilter").onchange = renderWorks;
$("#workForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  const payload = formObject(event.target);
  const id = event.target.elements.obra_id.value;
  setBusy(true, id ? "SALVANDO OBRA..." : "CRIANDO OBRA...");
  try {
    if (id) await api(`/api/obras/${id}`, { method: "PATCH", body: payload });
    else await api("/api/obras", { method: "POST", body: payload });
    $("#workDialog").close();
    await loadAll(false);
    toast(id ? "OBRA ATUALIZADA." : "OBRA CRIADA.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

function openImage(url, title = "EQUIPAMENTO") {
  if (!url) return;
  $("#imageDialogTitle").textContent = title;
  $("#imageDialogContent").src = url;
  $("#imageDialog").showModal();
}

function setItemImagePreview(url = "") {
  pendingItemImage = url && url.startsWith("data:") ? url : "";
  $("#itemImagePreview").hidden = !url;
  $("#itemImagePlaceholder").hidden = Boolean(url);
  $("#itemImagePreview").src = url || "";
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve("");
    if (file.size > 4 * 1024 * 1024) return reject(new Error("A IMAGEM DEVE TER NO MÁXIMO 4 MB."));
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("NÃO FOI POSSÍVEL LER A IMAGEM."));
    reader.readAsDataURL(file);
  });
}

function attachmentToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve("");
    if (file.size > 10 * 1024 * 1024) return reject(new Error("O ANEXO DEVE TER NO MÁXIMO 10 MB."));
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("NÃO FOI POSSÍVEL LER O ANEXO."));
    reader.readAsDataURL(file);
  });
}

function renderItems() {
  const query = upper($("#itemSearch").value);
  const mode = $("#itemStatusFilter").value;
  const rows = app.equipamentos.filter(item => {
    if (mode === "active" && !item.ativo) return false;
    if (mode === "inactive" && item.ativo) return false;
    return !query || upper(`${item.codigo} ${item.grupo} ${item.nome}`).includes(query);
  });
  $("#itemsBadge").textContent = `${rows.length} ITENS`;
  $("#itemsTable").innerHTML = rows.map(item => {
    const picture = item.imagem_url ? `<button type="button" class="catalog-thumb image-click" data-image-url="${escapeHtml(item.imagem_url)}" data-image-title="${escapeHtml(item.codigo)} · ${escapeHtml(item.nome)}"><img src="${escapeHtml(item.imagem_url)}" alt="${escapeHtml(item.nome)}"></button>` : `<span class="catalog-thumb">${icon("image")}</span>`;
    return `<tr><td>${picture}</td><td><b>${escapeHtml(item.codigo)}</b></td><td>${escapeHtml(item.grupo || "—")}</td><td>${escapeHtml(item.nome)}</td><td class="num">${item.valor_unit == null ? "—" : money(item.valor_unit)}</td><td><span class="status-dot ${item.ativo ? "" : "inactive"}">${item.ativo ? "ATIVO" : "INATIVO"}</span></td><td class="num"><button class="btn soft small edit-item" data-code="${escapeHtml(item.codigo)}">${icon("edit")}EDITAR</button></td></tr>`;
  }).join("") || '<tr><td colspan="7" class="muted">NENHUM ITEM ENCONTRADO.</td></tr>';
  $$(".edit-item").forEach(button => { button.onclick = () => openItemDialog(button.dataset.code); });
  $$("#itemsTable [data-image-url]").forEach(button => { button.onclick = () => openImage(button.dataset.imageUrl, button.dataset.imageTitle); });
}

function openItemDialog(code = "") {
  const form = $("#itemForm");
  form.reset();
  pendingItemImage = "";
  editingItem = app.equipamentos.find(item => item.codigo === code) || null;
  if (editingItem) {
    $("#itemDialogTitle").textContent = `EDITAR ITEM ${editingItem.codigo}`;
    ["codigo", "grupo", "nome", "valor_unit", "observacao"].forEach(field => { form.elements[field].value = editingItem[field] ?? ""; });
    form.elements.ativo.value = editingItem.ativo ? "1" : "0";
    form.elements.codigo.disabled = true;
    setItemImagePreview(editingItem.imagem_url || "");
  } else {
    $("#itemDialogTitle").textContent = "NOVO ITEM";
    form.elements.codigo.disabled = false;
    form.elements.ativo.value = "1";
    setItemImagePreview("");
  }
  $("#itemDialog").showModal();
}

$("#newItemButton").onclick = () => openItemDialog();
$("#itemSearch").oninput = renderItems;
$("#itemStatusFilter").onchange = renderItems;
$("#itemForm").elements.imagem.onchange = async event => {
  try { setItemImagePreview(await fileToDataUrl(event.target.files?.[0])); }
  catch (error) { event.target.value = ""; toast(error.message, true); }
};
$("#itemImagePreviewButton").onclick = () => {
  const url = $("#itemImagePreview").src;
  if (!$("#itemImagePreview").hidden && url) openImage(url, editingItem ? `${editingItem.codigo} · ${editingItem.nome}` : "NOVA IMAGEM");
};
$("#itemForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  const payload = formObject(event.target);
  delete payload.imagem;
  payload.ativo = payload.ativo === "1";
  payload.remover_imagem = payload.remover_imagem === "1";
  payload.imagem_base64 = pendingItemImage;
  setBusy(true, editingItem ? "SALVANDO ITEM..." : "CRIANDO ITEM...");
  try {
    if (editingItem) await api(`/api/equipamentos/${editingItem.codigo}`, { method: "PATCH", body: payload });
    else await api("/api/equipamentos", { method: "POST", body: payload });
    $("#itemDialog").close();
    await loadAll(false);
    toast(editingItem ? "ITEM ATUALIZADO." : "ITEM CRIADO.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

function renderClients() {
  const query = upper($("#clientSearch").value);
  const rows = app.clientes.filter(client => !query || upper(`${client.id} ${client.nome} ${client.documento} ${client.contato} ${client.telefone}`).includes(query));
  $("#clientsBadge").textContent = `${rows.length} CLIENTES`;
  $("#clientsTable").innerHTML = rows.map(client => `<tr><td><b>${escapeHtml(client.id)}</b></td><td><b>${escapeHtml(client.nome)}</b></td><td>${escapeHtml(client.documento || "—")}</td><td>${escapeHtml(client.contato || "—")}</td><td>${escapeHtml(client.telefone || "—")}</td><td>${escapeHtml(client.email || "—")}</td><td><span class="status-dot ${client.ativo ? "" : "inactive"}">${client.ativo ? "ATIVO" : "INATIVO"}</span></td><td class="num"><div class="admin-list-actions"><button class="btn soft small edit-client" data-id="${client.id}">${icon("edit")}EDITAR</button><button class="btn danger small delete-client" data-id="${client.id}" data-label="${escapeHtml(client.nome)}">${icon("close")}EXCLUIR</button></div></td></tr>`).join("") || '<tr><td colspan="8" class="muted">NENHUM CLIENTE ENCONTRADO.</td></tr>';
  $$(".edit-client").forEach(button => { button.onclick = () => openClientDialog(button.dataset.id); });
  $$(".delete-client").forEach(button => { button.onclick = () => requestDeletion("CLIENTE", button.dataset.id, button.dataset.label); });
}

function openClientDialog(id = "") {
  const form = $("#clientForm"); form.reset();
  editingClient = app.clientes.find(client => client.id === id) || null;
  form.elements.cliente_id.value = id;
  if (editingClient) {
    $("#clientDialogTitle").textContent = `EDITAR ${editingClient.id}`;
    ["nome", "documento", "contato", "telefone", "email", "observacao"].forEach(field => { form.elements[field].value = editingClient[field] || ""; });
    form.elements.ativo.value = editingClient.ativo ? "1" : "0";
  } else { $("#clientDialogTitle").textContent = "NOVO CLIENTE"; form.elements.ativo.value = "1"; }
  $("#clientDialog").showModal();
}

$("#newClientButton").onclick = () => openClientDialog();
$("#clientSearch").oninput = renderClients;
$("#clientForm").onsubmit = async event => {
  event.preventDefault(); normalizeForm(event.target);
  const payload = formObject(event.target); payload.ativo = payload.ativo === "1";
  const id = payload.cliente_id; delete payload.cliente_id;
  setBusy(true, id ? "SALVANDO CLIENTE..." : "CRIANDO CLIENTE...");
  try { if (id) await api(`/api/clientes/${id}`, {method:"PATCH",body:payload}); else await api("/api/clientes", {method:"POST",body:payload}); $("#clientDialog").close(); await loadAll(false); toast(id ? "CLIENTE ATUALIZADO." : "CLIENTE CRIADO."); }
  catch (error) { toast(error.message, true); } finally { setBusy(false); }
};

const VEHICLE_STATUS_LABELS = { DISPONIVEL:"DISPONÍVEL", EM_ROTA:"EM ROTA", MANUTENCAO:"MANUTENÇÃO", INATIVO:"INATIVO" };
const blankZero = value => Number(value || 0) === 0 ? "" : value;

function renderVehicles() {
  $("#vehiclesBadge").textContent = `${app.caminhoes.length} VEÍCULOS`;
  $("#vehiclesTable").innerHTML = app.caminhoes.map(vehicle => {
    const pending = Boolean(vehicle.cadastro_pendente);
    const consumption = Number(vehicle.consumo_km_l || 0);
    const axes = Number(vehicle.eixos || 0);
    return `<tr>
      <td><span class="badge ${vehicle.tipo === "CARRO_PASSEIO" ? "blue" : "orange"}">${vehicle.tipo === "CARRO_PASSEIO" ? "CARRO" : "CAMINHÃO"}</span></td>
      <td><b>${escapeHtml(vehicle.porte || "—")}</b><br><small class="muted">${pending ? "EIXOS A CONFIRMAR" : `${axes} EIXOS`}</small></td>
      <td><b>${pending ? "PENDENTE" : escapeHtml(vehicle.placa)}</b></td>
      <td>${escapeHtml(vehicle.apelido || vehicle.modelo || "—")}</td>
      <td><b>${escapeHtml(vehicle.combustivel || "—")}</b><br><small class="muted">${consumption > 0 ? `${number(consumption)} KM/${vehicle.combustivel === "ELETRICO" ? "KWH" : "L"}` : "CÁLCULO MANUAL"}</small></td>
      <td>${escapeHtml(vehicle.motorista_padrao || "—")}</td>
      <td>${vehicle.propriedade === "ALUGADO" ? "ALUGADO" : "PRÓPRIO"}</td>
      <td><span class="status-dot ${vehicle.status === "INATIVO" || !vehicle.ativo ? "inactive" : ""}">${escapeHtml(VEHICLE_STATUS_LABELS[vehicle.status] || vehicle.status)}</span></td>
      <td><span class="badge ${pending ? "orange" : "green"}">${pending ? "PENDENTE" : "COMPLETO"}</span></td>
      <td class="num"><button class="btn soft small edit-vehicle" data-id="${vehicle.id}">${icon("edit")}${pending ? "COMPLETAR" : "EDITAR"}</button></td>
    </tr>`;
  }).join("") || '<tr><td colspan="10" class="muted">NENHUM VEÍCULO CADASTRADO.</td></tr>';
  $$(".edit-vehicle").forEach(button => { button.onclick = () => openVehicleDialog(button.dataset.id); });
}

function openVehicleDialog(id = "") {
  const form = $("#vehicleForm");
  form.reset();
  editingVehicle = app.caminhoes.find(vehicle => vehicle.id === id) || null;
  form.elements.caminhao_id.value = id;
  if (editingVehicle) {
    $("#vehicleDialogTitle").textContent = `${editingVehicle.cadastro_pendente ? "COMPLETAR" : "EDITAR"} ${editingVehicle.id}`;
    ["propriedade","tipo","perfil_codigo","status","apelido","carroceria","porte","eixos","placa","modelo","combustivel","consumo_km_l","tanque_litros","transportadora","motorista_padrao","capacidade","observacao"].forEach(field => {
      if (form.elements[field]) form.elements[field].value = blankZero(editingVehicle[field] ?? "");
    });
    if (editingVehicle.cadastro_pendente && String(editingVehicle.placa || "").startsWith("PEND-")) form.elements.placa.value = "";
    form.elements.ativo.value = editingVehicle.ativo ? "1" : "0";
  } else {
    $("#vehicleDialogTitle").textContent = "NOVO VEÍCULO";
    form.elements.tipo.value = "CAMINHAO_TRANSPORTE";
    form.elements.status.value = "DISPONIVEL";
    form.elements.porte.value = "PESADO";
    form.elements.eixos.value = "2";
    form.elements.combustivel.value = "DIESEL";
    form.elements.ativo.value = "1";
  }
  $("#vehicleDialog").showModal();
}

$("#newVehicleButton").onclick = () => openVehicleDialog();
$("#vehicleForm").elements.tipo.onchange = event => {
  if (editingVehicle) return;
  const form = $("#vehicleForm");
  const car = event.target.value === "CARRO_PASSEIO";
  form.elements.porte.value = car ? "LEVE" : "PESADO";
  form.elements.eixos.value = "2";
  form.elements.combustivel.value = car ? "FLEX" : "DIESEL";
};
$("#vehicleForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  const payload = formObject(event.target);
  payload.ativo = payload.ativo === "1";
  const id = payload.caminhao_id;
  delete payload.caminhao_id;
  setBusy(true, id ? "SALVANDO VEÍCULO..." : "CRIANDO VEÍCULO...");
  try {
    if (id) await api(`/api/caminhoes/${id}`, {method:"PATCH",body:payload});
    else await api("/api/caminhoes", {method:"POST",body:payload});
    $("#vehicleDialog").close();
    await loadAll(false);
    toast(id ? "VEÍCULO ATUALIZADO." : "VEÍCULO CRIADO.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

$("#newPendingVehicleButton").onclick = () => {
  $("#pendingVehicleForm").reset();
  $("#pendingVehicleDialog").showModal();
};
$("#pendingVehicleForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  setBusy(true, "CRIANDO VEÍCULO PENDENTE...");
  try {
    const vehicle = await api("/api/caminhoes/pendente", { method: "POST", body: formObject(event.target) });
    $("#pendingVehicleDialog").close();
    await loadAll(false);
    $("#routeVehicleSelect").value = vehicle.id;
    enforceVehicleRouteModes();
    toast("VEÍCULO CRIADO COMO PENDENTE. COMPLETE A FICHA DEPOIS; NESTA ROTA OS CUSTOS DEVEM SER INFORMADOS MANUALMENTE.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

function routeMarkerIcon(kind) {
  const symbol = kind === "factory" ? "factory" : "building";
  return L.divIcon({className:"map-pin-custom",html:`<div class="map-pin-body ${kind}">${icon(symbol)}</div>`,iconSize:[42,42],iconAnchor:[14,38],popupAnchor:[6,-36]});
}

function selectedDraftWorkIds() {
  return $$('[data-route-draft-work]:checked', $("#routeDraftWorks")).map(input => input.value);
}

function renderRouteDraftWorks() {
  const panel = $("#routeNewLoadPanel");
  panel.hidden = !routeDraftActive;
  if (!routeDraftActive) return;
  const previous = new Set(selectedDraftWorkIds());
  const candidates = app.obras.filter(work => work.status !== "CONCLUÍDA" || work.latitude != null || work.longitude != null);
  $("#routeDraftWorks").innerHTML = candidates.length ? candidates.map(work => {
    const located = work.latitude != null && work.longitude != null && work.latitude !== "" && work.longitude !== "";
    const checked = previous.has(work.id) ? "checked" : "";
    return `<label class="route-draft-work ${located ? "" : "missing-location"}"><input type="checkbox" data-route-draft-work value="${escapeHtml(work.id)}" ${checked} ${located ? "" : "disabled"}><span><b>${escapeHtml(work.nome)}</b><small>${escapeHtml(work.municipio || "")} · ${escapeHtml(work.uf || "")} · ${escapeHtml(work.op_padrao || "OP PENDENTE")}</small>${located ? "" : "<em>SEM COORDENADAS — COMPLETE A LOCALIZAÇÃO ANTES DA ROTA.</em>"}</span></label>`;
  }).join("") : '<span class="muted">NENHUMA OBRA CADASTRADA.</span>';
  $$('[data-route-draft-work]', $("#routeDraftWorks")).forEach(input => {
    input.onchange = () => { routeManualOrder = selectedDraftWorkIds(); renderManualRouteOrder(); renderRouteMap(); };
  });
}

function startNewRoutePlanning() {
  routeDraftActive = true;
  $("#routeLoadSelect").value = "";
  app.routePlan = null;
  app.routePlans = [];
  routeManualOrder = [];
  renderRouteDraftWorks();
  renderRoutePlan();
  renderManualRouteOrder();
  renderRouteMap();
  $("#routeNewLoadPanel").scrollIntoView({ behavior: "smooth", block: "center" });
}

$("#newRoutePlanning").onclick = () => { switchModule("rotas"); startNewRoutePlanning(); };

function routeWorks() {
  const loadId = $("#routeLoadSelect").value;
  let source;
  if (loadId) source = app.carregamentos.find(load => load.id === loadId)?.obras || [];
  else {
    const selected = new Set(selectedDraftWorkIds());
    source = app.obras.filter(work => selected.has(work.id));
  }
  const located = source.filter(work => work.latitude != null && work.longitude != null && work.latitude !== "" && work.longitude !== "");
  if (!loadId || app.routePlan?.carregamento_id !== loadId) return located;
  const byId = new Map(located.map(work => [work.id, work]));
  return (app.routePlan.paradas || []).filter(stop => stop.tipo === "OBRA").map(stop => byId.get(stop.id)).filter(Boolean);
}

function routeOrderWorks() {
  const loadId = $("#routeLoadSelect").value;
  if (loadId) return app.carregamentos.find(item => item.id === loadId)?.obras || [];
  const selected = new Set(selectedDraftWorkIds());
  return app.obras.filter(work => selected.has(work.id));
}

function renderManualRouteOrder() {
  const panel = $("#routeManualOrder");
  const manual = $("#routeOrderMode").value === "MANUAL";
  panel.hidden = !manual;
  const works = routeOrderWorks();
  const expected = new Set(works.map(work => work.id));
  if (routeManualOrder.length !== expected.size || routeManualOrder.some(id => !expected.has(id))) routeManualOrder = works.map(work => work.id);
  if (!manual) return;
  const byId = new Map(works.map(work => [work.id, work]));
  panel.innerHTML = routeManualOrder.length ? routeManualOrder.map((id, index) => {
    const work = byId.get(id) || {};
    return `<div class="manual-route-row"><span>${index + 1}</span><div><b>${escapeHtml(work.nome || id)}</b><small>${escapeHtml(work.municipio || "")} · ${escapeHtml(work.op_numero || work.op_padrao || "OP PENDENTE")}</small></div><button type="button" data-route-up="${index}" ${index === 0 ? "disabled" : ""} aria-label="SUBIR">↑</button><button type="button" data-route-down="${index}" ${index === routeManualOrder.length - 1 ? "disabled" : ""} aria-label="DESCER">↓</button></div>`;
  }).join("") : '<span class="muted">SELECIONE AS OBRAS / PONTOS DE PARADA.</span>';
  $$('[data-route-up]', panel).forEach(button => {
    button.onclick = () => { const index = Number(button.dataset.routeUp); [routeManualOrder[index - 1], routeManualOrder[index]] = [routeManualOrder[index], routeManualOrder[index - 1]]; renderManualRouteOrder(); };
  });
  $$('[data-route-down]', panel).forEach(button => {
    button.onclick = () => { const index = Number(button.dataset.routeDown); [routeManualOrder[index + 1], routeManualOrder[index]] = [routeManualOrder[index], routeManualOrder[index + 1]]; renderManualRouteOrder(); };
  });
}

function formatTravelTime(minutes) {
  const total = Math.max(0, Math.round(Number(minutes || 0)));
  const hours = Math.floor(total / 60), mins = total % 60;
  if (!hours) return `${mins} MIN`;
  return `${hours} H ${String(mins).padStart(2, "0")} MIN`;
}

function renderRoutePlan() {
  const plan = app.routePlan;
  const summary = $("#routePlanSummary");
  if (!plan) {
    summary.innerHTML = '<div class="empty-state"><b>NENHUMA ROTA CALCULADA</b><span>CRIE UM NOVO CARREGAMENTO OU SELECIONE UM PLANEJADO EXISTENTE.</span></div>';
  } else {
    const electric = upper(plan.veiculo?.combustivel) === "ELETRICO";
    summary.innerHTML = `<div class="route-metrics">
      <article><span>DISTÂNCIA DA ROTA</span><b>${number(plan.distancia_adotada_km)} KM</b><small>${escapeHtml(plan.distancia_fonte || plan.distancia_modo)}</small></article>
      <article><span>TEMPO ESTIMADO</span><b>${formatTravelTime(plan.tempo_estimado_min)}</b><small>${escapeHtml(plan.motor_rota || "MOTOR LOCAL")}</small></article>
      <article><span>CONSUMO DA ROTA</span><b>${Number(plan.litros_estimados || 0) ? number(plan.litros_estimados) : "—"} ${electric ? "KWH" : "L"}</b><small>${escapeHtml(plan.combustivel_modo)}</small></article>
      <article><span>COMBUSTÍVEL</span><b>${money(plan.custo_combustivel)}</b><small>${escapeHtml(plan.formula_combustivel || "")}</small></article>
      <article><span>PEDÁGIO</span><b>${money(plan.custo_pedagio)}</b><small>${Number(plan.pracas_pedagio || 0)} PONTO(S) · ${escapeHtml(plan.base_pedagios_versao || "BASE LOCAL PENDENTE")}</small></article>
      <article><span>CUSTO LOGÍSTICO DA ROTA</span><b>${money(plan.custo_total)}</b><small>COMBUSTÍVEL + PEDÁGIO</small></article>
    </div><div class="route-formulas"><span>${escapeHtml(plan.formula_distancia)}</span><span>${escapeHtml(plan.formula_pedagio)}</span></div>`;
  }
  $("#routePlanHistory").innerHTML = app.routePlans.length ? `<div class="route-history-head"><b>REVISÕES DE PLANEJAMENTO</b><small>CADA CÁLCULO É PRESERVADO.</small></div><div class="route-history-buttons">${app.routePlans.map(item => `<button type="button" class="${item.id === plan?.id ? "active" : ""}" data-route-plan-id="${escapeHtml(item.id)}">REV. ${String(item.revisao).padStart(3, "0")} · ${number(item.distancia_adotada_km)} KM · ${formatTravelTime(item.tempo_estimado_min)}</button>`).join("")}</div>` : "";
  $$('[data-route-plan-id]', $("#routePlanHistory")).forEach(button => {
    button.onclick = () => { app.routePlan = app.routePlans.find(item => item.id === button.dataset.routePlanId) || null; renderRoutePlan(); renderRouteMap(); };
  });
}

async function loadRoutePlans() {
  const loadId = $("#routeLoadSelect").value;
  if (!loadId) { app.routePlans = []; app.routePlan = null; renderRoutePlan(); return; }
  const payload = await api(`/api/rotas/planejamentos?carregamento_id=${encodeURIComponent(loadId)}`);
  app.routePlans = payload.planejamentos || [];
  app.routePlan = app.routePlans[0] || null;
  if (app.routePlan) $("#routeVehicleSelect").value = app.routePlan.caminhao_id;
  renderRoutePlan();
}

function renderRouteSideMenus(works) {
  const factory = app.fabrica || {};
  $("#routeOriginsMenu").innerHTML = factory.nome ? `<button type="button" class="route-side-item" data-map-factory><b>${escapeHtml(factory.nome)}</b><small>${escapeHtml(factory.endereco || (factory.latitude != null ? `${factory.latitude}, ${factory.longitude}` : "SEM LOCALIZAÇÃO"))}</small></button>` : '<span class="muted">ORIGEM NÃO CADASTRADA.</span>';
  $("#routeWorksMenu").innerHTML = works.length ? works.map(work => `<button type="button" class="route-side-item" data-map-work="${escapeHtml(work.id)}"><b>${escapeHtml(work.nome)}</b><small>${escapeHtml(work.municipio || "")} · ${escapeHtml(work.op_numero || work.op_padrao || "OP PENDENTE")}</small></button>`).join("") : '<span class="muted">SELECIONE OBRAS / LOCAIS.</span>';
  $('[data-map-factory]')?.addEventListener("click", () => { if (routeMap && factory.latitude != null) routeMap.setView([Number(factory.latitude), Number(factory.longitude)], 15); });
  $$('[data-map-work]').forEach(button => button.onclick = () => { const work=works.find(item=>item.id===button.dataset.mapWork); if(routeMap && work?.latitude!=null) routeMap.setView([Number(work.latitude),Number(work.longitude)],15); });
}

function renderRouteMap() {
  if (!window.L || !$("#module-rotas").classList.contains("active")) {
    if (!window.L) $("#offlineMapStatus").textContent = "MAPA LOCAL INDISPONÍVEL";
    return;
  }
  if (!routeMap) { routeMap = L.map("routeMap").setView([-14.24,-51.93],4); prepareOfflineMap(routeMap); }
  routeMap.invalidateSize();
  if (routeLayer) routeLayer.remove();
  routeLayer = L.layerGroup().addTo(routeMap);
  const bounds = [];
  const displayedStops = [];
  const factory = app.fabrica || {};
  if (factory.latitude != null && factory.longitude != null) {
    const point=[Number(factory.latitude),Number(factory.longitude)]; bounds.push(point);
    L.marker(point,{icon:routeMarkerIcon("factory")}).bindPopup(`<b>${escapeHtml(factory.nome)}</b><br>${escapeHtml(factory.endereco || "ORIGEM")}`).addTo(routeLayer);
  }
  const works = routeWorks();
  renderRouteSideMenus(works);
  works.forEach(work => {
    const point=[Number(work.latitude),Number(work.longitude)]; bounds.push(point);
    L.marker(point,{icon:routeMarkerIcon("work")}).bindPopup(`<b>${escapeHtml(work.nome)}</b><br>${escapeHtml(work.municipio || "")}<br>${escapeHtml(work.endereco || "")}`).addTo(routeLayer);
  });
  const loadId = $("#routeLoadSelect").value;
  const planActive = Boolean(app.routePlan && (!loadId || app.routePlan.carregamento_id === loadId));
  const planStops = planActive ? (app.routePlan.paradas || []) : [];
  const geometry = planActive ? (app.routePlan.rota_geometria || []) : [];
  const routePoints = geometry.length > 1
    ? geometry.map(point => [Number(point.latitude), Number(point.longitude)])
    : (planStops.length ? planStops.map(stop => [Number(stop.latitude), Number(stop.longitude)]) : [factory.latitude != null ? [Number(factory.latitude),Number(factory.longitude)] : null, ...works.map(work => [Number(work.latitude),Number(work.longitude)])].filter(Boolean));
  if (routePoints.length > 1) {
    L.polyline(routePoints,{color:"#0f5da8",weight:4,dashArray:planActive ? "" : "8 7",opacity:.86}).addTo(routeLayer);
    if (geometry.length) routePoints.filter((_, index) => index % Math.max(1, Math.floor(routePoints.length / 100)) === 0).forEach(point => bounds.push(point));
  }
  if (planStops.length) {
    planStops.forEach((stop, index) => {
      const segment = index ? app.routePlan.trechos?.[index - 1] : null;
      displayedStops.push({ name: stop.nome, detail: segment ? `${number(segment.distancia_adotada_km)} KM DESDE ${segment.origem}` : "PONTO DE PARTIDA" });
    });
  } else {
    if (factory.latitude != null) displayedStops.push({name:factory.nome,detail:"FÁBRICA / ORIGEM"});
    works.forEach(work => displayedStops.push({name:work.nome,detail:`${work.municipio || ""} · ${work.op_numero || work.op_padrao || "OP PENDENTE"}`}));
  }
  if (bounds.length) routeMap.fitBounds(bounds,{padding:[35,35],maxZoom:15}); else routeMap.setView([-14.24,-51.93],4);
  $("#routePointsBadge").textContent = `${Math.max(0, displayedStops.length - 1)} PONTO(S) DE PARADA`;
  $("#routeStops").innerHTML = displayedStops.map((stop,index)=>`<div class="route-stop"><b>${index+1}. ${escapeHtml(stop.name)}</b><small>${escapeHtml(stop.detail)}</small></div>`).join("") || '<span class="muted">SELECIONE AS OBRAS / PONTOS DE PARADA.</span>';
}

function toggleRouteManualFields() {
  $("#routeManualDistanceField").hidden = $("#routeDistanceMode").value !== "MANUAL";
  $("#routeManualFuelField").hidden = $("#routeFuelMode").value !== "MANUAL";
  $("#routeManualTollField").hidden = $("#routeTollMode").value !== "MANUAL";
}

function enforceVehicleRouteModes() {
  const vehicle = app.caminhoes.find(item => item.id === $("#routeVehicleSelect").value);
  if (vehicle?.cadastro_pendente || Number(vehicle?.consumo_km_l || 0) <= 0) {
    $("#routeFuelMode").value = "MANUAL";
    $("#routeTollMode").value = "MANUAL";
  }
  toggleRouteManualFields();
}

$("#routeDistanceMode").onchange = toggleRouteManualFields;
$("#routeFuelMode").onchange = toggleRouteManualFields;
$("#routeTollMode").onchange = toggleRouteManualFields;

$("#routeLoadSelect").onchange = async () => {
  const loadId = $("#routeLoadSelect").value;
  routeDraftActive = !loadId;
  renderRouteDraftWorks();
  const load = app.carregamentos.find(item => item.id === loadId);
  if (load?.caminhao_id) $("#routeVehicleSelect").value = load.caminhao_id;
  routeManualOrder = (load?.obras || []).map(work => work.id);
  renderManualRouteOrder();
  try { await loadRoutePlans(); }
  catch (error) { app.routePlans = []; app.routePlan = null; renderRoutePlan(); toast(error.message, true); }
  enforceVehicleRouteModes();
  renderRouteMap();
};
$("#routeVehicleSelect").onchange = () => { enforceVehicleRouteModes(); renderRouteMap(); };
$("#routeOrderMode").onchange = renderManualRouteOrder;
$("#fitRouteMap").onclick = renderRouteMap;
$("#openGoogleRoute").onclick = () => {
  const planStops = app.routePlan?.paradas || [];
  const fallback = [app.fabrica?.latitude != null ? `${app.fabrica.latitude},${app.fabrica.longitude}` : "", ...routeWorks().map(work => `${work.latitude},${work.longitude}`)].filter(Boolean);
  const points = planStops.length ? planStops.map(stop => `${stop.latitude},${stop.longitude}`) : fallback;
  if (points.length < 2) { toast("INFORME A LOCALIZAÇÃO DA ORIGEM E DE PELO MENOS UMA OBRA.", true); return; }
  const origin=points[0],destination=points[points.length-1],waypoints=points.slice(1,-1).join("|");
  const url=`https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}${waypoints?`&waypoints=${encodeURIComponent(waypoints)}`:""}`;
  window.open(url,"_blank","noopener");
};

$("#routePlannerForm").onsubmit = async event => {
  event.preventDefault();
  const payload = formObject(event.target);
  payload.carregamento_id = $("#routeLoadSelect").value;
  payload.caminhao_id = $("#routeVehicleSelect").value;
  payload.retorno_origem = payload.retorno_origem === "1";
  payload.ordem_obras = payload.ordem_modo === "MANUAL" ? [...routeManualOrder] : [];
  if (!payload.caminhao_id) { toast("SELECIONE UM VEÍCULO OU CRIE UM VEÍCULO RÁPIDO.", true); return; }
  const creating = !payload.carregamento_id;
  if (creating) {
    const selected = new Set(selectedDraftWorkIds());
    const works = app.obras.filter(work => selected.has(work.id));
    if (!works.length) { toast("SELECIONE PELO MENOS UMA OBRA / PONTO DE PARADA.", true); return; }
    payload.obras = works.map(work => ({ obra_id: work.id, op_numero: work.op_padrao || "" }));
    payload.data = today();
  }
  setBusy(true, creating ? "CALCULANDO ROTA E CRIANDO CARREGAMENTO PLANEJADO..." : "RECALCULANDO E REGISTRANDO ROTA...");
  try {
    if (creating) {
      const created = await api("/api/rotas/criar-planejado", { method: "POST", body: payload });
      await loadAll(false);
      routeDraftActive = false;
      $("#routeLoadSelect").value = created.carregamento.id;
      app.routePlan = created.planejamento;
      app.routePlans = [created.planejamento];
      renderRouteDraftWorks();
      renderRoutePlan();
      renderRouteMap();
      toast(`${created.carregamento.id} CRIADO COMO PLANEJADO E ENVIADO PARA CARREGAMENTOS AGUARDANDO COMPLEMENTAÇÃO.`);
    } else {
      const plan = await api("/api/rotas/planejar", { method: "POST", body: payload });
      app.routePlans = [plan, ...app.routePlans.filter(item => item.id !== plan.id)];
      app.routePlan = plan;
      renderRoutePlan();
      renderRouteMap();
      toast(`ROTA REV. ${String(plan.revisao).padStart(3, "0")} CALCULADA E SALVA.`);
    }
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

$("#factoryForm").onsubmit = async event => {
  event.preventDefault(); normalizeForm(event.target); setBusy(true,"SALVANDO ORIGEM...");
  try { app.fabrica=await api("/api/rota/fabrica",{method:"POST",body:formObject(event.target)}); app.routePlan=null; renderRoutePlan(); renderRouteMap(); toast("FÁBRICA / ORIGEM ATUALIZADA. RECALCULE A ROTA QUANDO NECESSÁRIO."); }
  catch(error){toast(error.message,true);} finally{setBusy(false);}
};
$("#factoryMapButton").onclick = () => openMapForCoordinateInput($("#factoryLocation"), "FÁBRICA / ORIGEM");

function showFinanceView(view, scroll = true) {
  const works = view === "works";
  $("#financeOverviewView").hidden = works;
  $("#financeWorksView").hidden = !works;
  $("#openFinanceOverview").classList.toggle("active-view", !works);
  $("#openFinanceWorks").classList.toggle("active-view", works);
  if (scroll) (works ? $("#financeWorksView") : $("#financeOverviewView")).scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#openFinanceOverview").onclick = () => showFinanceView("overview");
$("#openFinanceWorks").onclick = () => showFinanceView("works");

function renderProfit() {
  const finance = app.finance || { modo: "OPERACIONAL", totais: {}, obras: [] };
  const total = finance.totais || {};
  const works = finance.obras || [];
  const administrative = finance.modo === "ADMINISTRATIVO";
  if (administrative) {
    $("#kpiGenerated").textContent = money(total.receita_gerada);
    $("#kpiPaid").textContent = money(total.receita_paga);
    $("#kpiReceivable").textContent = money(total.saldo_receber);
    $("#kpiCost").textContent = money(total.custo);
    $("#kpiProfitGenerated").textContent = money(total.lucro_gerado);
    $("#kpiProfitPaid").textContent = money(total.lucro_pago);
    $("#profitWorksKicker").textContent = "OBRA · VALOR · PAGO";
    $("#profitWorksTitle").textContent = "VALORES GERADOS E PAGOS POR OBRA";
    $("#profitWorksSubtitle").textContent = "O VALOR É GERADO PELOS CARREGAMENTOS EXPEDIDOS; O PAGO É INFORMADO PELO ADMINISTRADOR.";
    $("#profitTableHead").innerHTML = '<th>ESTADO</th><th>OBRA</th><th>MUNICÍPIO</th><th class="num">VALOR GERADO</th><th class="num">PAGO</th><th class="num">A RECEBER</th><th class="num">CUSTO</th><th class="num">RESULTADO GERADO</th>';
    $("#profitTable").innerHTML = works.map(row => `<tr><td><span class="badge blue">${escapeHtml(row.uf)}</span></td><td><b>${escapeHtml(row.obra_nome)}</b><br><small class="muted">${escapeHtml(row.obra_id)}</small></td><td>${escapeHtml(row.municipio || "—")}</td><td class="num"><b>${money(row.receita_gerada)}</b></td><td class="num">${money(row.receita_paga)}</td><td class="num">${money(row.saldo_receber)}</td><td class="num">${money(row.custo)}</td><td class="num"><b>${money(row.lucro_gerado)}</b></td></tr>`).join("") || '<tr><td colspan="8" class="muted">SEM MOVIMENTO NO PERÍODO SELECIONADO.</td></tr>';
  } else {
    $("#kpiLoaded").textContent = money(total.valor_carregado);
    $("#kpiOperationalCost").textContent = money(total.custo_viagens);
    $("#kpiRealValue").textContent = money(total.valor_real);
    $("#profitWorksKicker").textContent = "OBRA · CARREGADO · CUSTO";
    $("#profitWorksTitle").textContent = "VALORES OPERACIONAIS POR OBRA";
    $("#profitWorksSubtitle").textContent = "RESUMO LOGÍSTICO SEM PAGAMENTOS, VALORES A RECEBER OU RESULTADOS ADMINISTRATIVOS.";
    $("#profitTableHead").innerHTML = '<th>ESTADO</th><th>OBRA</th><th>MUNICÍPIO</th><th class="num">VALOR CARREGADO</th><th class="num">CUSTO DE VIAGENS</th><th class="num">VALOR REAL</th>';
    $("#profitTable").innerHTML = works.map(row => `<tr><td><span class="badge blue">${escapeHtml(row.uf)}</span></td><td><b>${escapeHtml(row.obra_nome)}</b><br><small class="muted">${escapeHtml(row.obra_id)}</small></td><td>${escapeHtml(row.municipio || "—")}</td><td class="num"><b>${money(row.valor_carregado)}</b></td><td class="num">${money(row.custo_viagens)}</td><td class="num"><b>${money(row.valor_real)}</b></td></tr>`).join("") || '<tr><td colspan="6" class="muted">SEM MOVIMENTO NO PERÍODO SELECIONADO.</td></tr>';
  }
  $("#profitPeriodBadge").textContent = [$("#profitYear").value, $("#profitMonth").selectedOptions[0]?.text, $("#profitUf").value].filter(Boolean).join(" · ");
  $("#profitRowsBadge").textContent = `${works.length} OBRA${works.length === 1 ? "" : "S"}`;
  renderChart(app.financeChart);
}

function renderChart(data) {
  const chart = $("#profitChart");
  const points = data?.pontos || [];
  const series = data?.series || [];
  $("#profitChartTitle").textContent = data?.titulo || "INDICADOR DO PERÍODO";
  $("#profitChartSubtitle").textContent = data?.subtitulo || "SELECIONE UM GRÁFICO PARA COMPARAR OS DADOS.";
  if (!points.length || !series.length) {
    chart.innerHTML = '<div class="empty-state"><b>SEM DADOS PARA O GRÁFICO</b><span>AJUSTE O PERÍODO OU REGISTRE CARREGAMENTOS E CUSTOS.</span></div>';
    return;
  }
  const maximum = Math.max(...points.flatMap(point => series.map(item => Math.abs(Number(point[item.chave] || 0)))), 1);
  const formatter = data.unidade === "MOEDA" ? money : number;
  const safeColor = value => /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : "#3988cd";
  const groups = points.map(point => {
    const bars = series.map(item => {
      const value = Number(point[item.chave] || 0);
      const title = `${item.rotulo}: ${formatter(value)}`;
      return `<div class="bar generic${value < 0 ? " negative" : ""}" title="${escapeHtml(title)}" style="height:${Math.max(2, Math.abs(value) / maximum * 180)}px;background:${safeColor(item.cor)}"></div>`;
    }).join("");
    return `<div class="chart-group generic-group">${bars}<span class="chart-label" title="${escapeHtml(point.rotulo)}">${escapeHtml(point.rotulo)}</span></div>`;
  }).join("");
  const legend = `<div class="chart-legend generic-legend">${series.map(item => `<span><i style="background:${safeColor(item.cor)}"></i>${escapeHtml(item.rotulo)}</span>`).join("")}</div>`;
  chart.innerHTML = groups + legend;
}

async function loadProfit() {
  const filters = {
    ano: $("#profitYear").value || "",
    mes: $("#profitMonth").value || "",
    uf: $("#profitUf").value || "",
  };
  const summaryQuery = new URLSearchParams(filters);
  const chartQuery = new URLSearchParams({ ...filters, tipo: $("#financeChartType").value || "" });
  [app.finance, app.financeChart] = await Promise.all([
    api(`/api/financeiro/resumo?${summaryQuery}`),
    api(`/api/financeiro/grafico?${chartQuery}`),
  ]);
  renderProfit();
}

$("#applyProfit").onclick = () => loadProfit().catch(error => toast(error.message, true));
$("#financeChartType").onchange = () => loadProfit().catch(error => toast(error.message, true));
$("#revenueForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  setBusy(true, "REGISTRANDO PAGAMENTO...");
  try {
    await api("/api/pagamentos", { method: "POST", body: formObject(event.target) });
    event.target.reset();
    event.target.elements.data_competencia.value = today();
    await loadAll(false);
    toast("PAGAMENTO REGISTRADO.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

function renderSystem() {
  const system = app.system;
  if (!system) return;
  const labels = { unidades: "ESTADOS", clientes: "CLIENTES", obras: "OBRAS", pracas: "PRAÇAS", carregamentos: "CARREGAMENTOS", caminhoes: "VEÍCULOS", viagens: "VIAGENS LEGADAS", receitas: "PAGAMENTOS", equipamentos: "ITENS" };
  $("#systemKpis").innerHTML = Object.entries(system.counts).slice(0, 4).map(([key, value], index) => `<article class="kpi ${["kpi-blue", "kpi-green", "kpi-purple", "kpi-orange"][index]}"><span>${labels[key] || key}</span><strong>${value}</strong><small>REGISTRADOS</small></article>`).join("");
  $("#systemPaths").innerHTML = Object.entries(system.paths || {}).map(([key, value]) => `<div class="path-row"><b>${escapeHtml(key)}</b><code>${escapeHtml(value)}</code></div>`).join("");
  $("#protectedList").innerHTML = (system.protected || []).map(value => `<div class="protected-item">${icon("shield")}${escapeHtml(value)}</div>`).join("");
  const online = Boolean(system.repository?.online);
  $("#systemStatus").classList.toggle("offline", !online);
  $("#systemStatus b").textContent = online ? `REDE OK · REV. ${system.repository.network_revision || 0}` : "MODO OFFLINE · SOMENTE LEITURA";
}

function renderLogs() {
  $("#logsList").innerHTML = app.logs.length ? app.logs.map(row => `<div class="log-row"><span>${escapeHtml(String(row.at || "").replace("T", " "))}</span><code>${escapeHtml(row.event || "")}</code><span>${escapeHtml(Object.entries(row).filter(([key]) => !["at", "event"].includes(key)).map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · "))}</span></div>`).join("") : '<div class="muted" style="padding:14px">SEM EVENTOS RECENTES.</div>';
}

function isMasterAdminSession() {
  return upper(app.auth?.user?.nome) === "ADMIN" && upper(app.auth?.user?.perfil) === "ADMIN";
}

function renderUsers() {
  $("#usersBadge").textContent = `${app.usuarios.length} USUÁRIOS`;
  $("#usersList").innerHTML = app.usuarios.map(user => {
    const master = upper(user.nome) === "ADMIN" && upper(user.perfil) === "ADMIN";
    return `<div class="admin-list-row"><div><b>${escapeHtml(user.nome)} · ${escapeHtml(user.perfil)}</b><small>${user.ativo ? "ATIVO" : "INATIVO"} · ${user.senha_definida ? "PIN DEFINIDO" : "PIN REVOGADO / NÃO DEFINIDO"}${user.trocar_senha ? " · TROCA OBRIGATÓRIA" : ""}${master ? " · ADMINISTRADOR MESTRE" : ""}</small></div><div class="admin-list-actions"><button class="btn soft small edit-user" data-id="${escapeHtml(user.id)}">${icon("edit")}EDITAR</button>${master ? "" : `<button class="btn soft small reset-user-pin" data-id="${escapeHtml(user.id)}">${icon("lock")}RESETAR PIN</button><button class="btn danger small revoke-user-pin" data-id="${escapeHtml(user.id)}">REVOGAR PIN</button>`}</div></div>`;
  }).join("") || '<div class="muted">SEM USUÁRIOS.</div>';
  $$(".edit-user").forEach(button => {
    button.onclick = () => {
      const user = app.usuarios.find(item => item.id === button.dataset.id);
      if (!user) return;
      const form = $("#userForm");
      form.elements.usuario_id.value = user.id;
      form.elements.nome.value = user.nome;
      form.elements.perfil.value = user.perfil;
      form.elements.ativo.value = user.ativo ? "1" : "0";
      form.elements.senha.value = "";
      form.elements.nome.focus();
    };
  });
  $$(".reset-user-pin").forEach(button => {
    button.onclick = async () => {
      const pin = window.prompt("INFORME O NOVO PIN PROVISÓRIO NUMÉRICO (MÍNIMO 4 DÍGITOS):", "");
      if (pin == null) return;
      if (!/^\d{4,32}$/.test(pin)) { toast("O PIN DEVE CONTER SOMENTE NÚMEROS E TER DE 4 A 32 DÍGITOS.", true); return; }
      setBusy(true, "RESETANDO PIN...");
      try { await api(`/api/usuarios/${encodeURIComponent(button.dataset.id)}/reset-pin`, { method:"POST", body:{ pin } }); await loadAdminData(); toast("PIN PROVISÓRIO REDEFINIDO. O USUÁRIO DEVERÁ TROCAR NO PRÓXIMO LOGIN."); }
      catch (error) { toast(error.message, true); }
      finally { setBusy(false); }
    };
  });
  $$(".revoke-user-pin").forEach(button => {
    button.onclick = async () => {
      if (!confirm("REVOGAR O PIN E DESATIVAR O ACESSO DESTE USUÁRIO? AS SESSÕES ATUAIS TAMBÉM SERÃO ENCERRADAS.")) return;
      setBusy(true, "REVOGANDO PIN...");
      try { await api(`/api/usuarios/${encodeURIComponent(button.dataset.id)}/revoke-pin`, { method:"POST", body:{} }); await loadAdminData(); toast("PIN REVOGADO E ACESSO DESATIVADO."); }
      catch (error) { toast(error.message, true); }
      finally { setBusy(false); }
    };
  });
}

function renderDeletions() {
  const pending = app.exclusoes.filter(row => row.status === "PENDENTE");
  $("#deletionsBadge").textContent = `${pending.length} PENDENTE${pending.length === 1 ? "" : "S"}`;
  $("#deletionsList").innerHTML = app.exclusoes.map(row => `<div class="admin-list-row"><div><b>${escapeHtml(row.entidade_tipo)} · ${escapeHtml(row.entidade_rotulo)}</b><small>${escapeHtml(row.id)} · ${escapeHtml(row.status)}<br>SOLICITADO POR ${escapeHtml(row.solicitante_nome || "SISTEMA")} EM ${escapeHtml(String(row.solicitado_em || "").replace("T", " "))}<br>${escapeHtml(row.motivo || "SEM MOTIVO INFORMADO")}</small></div>${row.status === "PENDENTE" ? `<div class="admin-list-actions"><button class="btn soft small revoke-deletion" data-id="${escapeHtml(row.id)}">REVOGAR</button><button class="btn danger small approve-deletion" data-id="${escapeHtml(row.id)}">APROVAR</button></div>` : ""}</div>`).join("") || '<div class="muted">SEM SOLICITAÇÕES DE EXCLUSÃO.</div>';
  $$(".revoke-deletion").forEach(button => { button.onclick = () => reviewDeletion(button.dataset.id, "REVOGAR"); });
  $$(".approve-deletion").forEach(button => { button.onclick = () => reviewDeletion(button.dataset.id, "APROVAR"); });
}

function renderOfficialAudit() {
  $("#officialAuditList").innerHTML = app.auditoria.length ? app.auditoria.map(row => `<div class="log-row"><span>${escapeHtml(String(row.ocorrido_em || "").replace("T", " "))}</span><code>${escapeHtml(row.evento || "")}</code><span>${escapeHtml(row.usuario_nome || "SISTEMA")} · ${escapeHtml(row.estacao_id || "—")} · ${escapeHtml(row.entidade_id || "")}</span></div>`).join("") : '<div class="muted" style="padding:14px">SEM EVENTOS OFICIAIS.</div>';
}

async function loadAdminData() {
  if (!hasPermission("SYSTEM_ADMIN")) return;
  const userRequest = isMasterAdminSession() ? api("/api/usuarios") : Promise.resolve({ usuarios: [] });
  const [users, deletions, audit] = await Promise.all([userRequest, api("/api/exclusoes"), api("/api/auditoria")]);
  app.usuarios = users.usuarios || [];
  app.exclusoes = deletions.solicitacoes || [];
  app.auditoria = audit.eventos || [];
  const form = $("#userForm");
  if (form) form.closest("section").hidden = !isMasterAdminSession();
  renderUsers();
  renderDeletions();
  renderOfficialAudit();
}

async function reviewDeletion(id, action) {
  const warning = action === "APROVAR" ? "APROVAR A EXCLUSÃO DEFINITIVA AGORA?" : "REVOGAR E RESTAURAR O REGISTRO?";
  if (!window.confirm(warning)) return;
  setBusy(true, "REVISANDO EXCLUSÃO...");
  try {
    await api(`/api/exclusoes/${encodeURIComponent(id)}`, { method: "PATCH", body: { acao: action } });
    await loadAll(false);
    toast(action === "APROVAR" ? "EXCLUSÃO APROVADA." : "REGISTRO RESTAURADO.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}

$("#userForm").onsubmit = async event => {
  event.preventDefault();
  normalizeForm(event.target);
  const payload = formObject(event.target);
  const id = payload.usuario_id;
  delete payload.usuario_id;
  payload.ativo = payload.ativo === "1";
  setBusy(true, "SALVANDO USUÁRIO...");
  try {
    if (id) await api(`/api/usuarios/${encodeURIComponent(id)}`, { method: "PATCH", body: payload });
    else await api("/api/usuarios", { method: "POST", body: payload });
    event.target.reset();
    event.target.elements.usuario_id.value = "";
    await loadAdminData();
    toast("USUÁRIO SALVO.");
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

$("#refreshOfficialAudit").onclick = () => loadAdminData().catch(error => toast(error.message, true));


function renderMasterPatchStatus() {
  const box = $("#masterPatchStatus");
  const state = app.masterPatches;
  if (!box) return;
  const importButton = $("#importMasterPatch");
  const validateButton = $("#validateMasterPatch");
  const applyButton = $("#applyMasterPatch");
  const removeButton = $("#removeMasterPatch");
  if (!state?.available || !state?.direct_master) {
    $("#masterPatchCard").hidden = true;
    return;
  }
  $("#masterPatchCard").hidden = false;
  const current = state.current || {};
  const ids = current.patches || {};
  $("#masterPatchVersion").textContent = `${current.version || "?"} · ${ids.structural || ""} · ${ids.incremental || ""} · ${ids.security || ""}`;
  const patches = state.patches || [];
  const patch = patches[0] || null;
  const hasOne = patches.length === 1 && patch?.valid_manifest !== false;
  importButton.disabled = patches.length > 0;
  validateButton.disabled = !hasOne;
  applyButton.disabled = !hasOne;
  removeButton.disabled = patches.length !== 1;
  if (!patch) {
    box.innerHTML = `
      <div class="path-row"><b>FILA</b><code>VAZIA</code></div>
      <div class="path-row"><b>SM_REPO</b><code>${escapeHtml(state.sm_repo || "—")}</code></div>
      <div class="path-row"><b>REGRA</b><code>1 PATCH POR VEZ · VALIDAR ANTES DE APLICAR</code></div>`;
    return;
  }
  if (patch.valid_manifest === false) {
    box.innerHTML = `
      <div class="path-row"><b>ARQUIVO</b><code>${escapeHtml(patch.arquivo || "—")}</code></div>
      <div class="path-row"><b>STATUS</b><code>MANIFESTO INVÁLIDO</code></div>
      <div class="path-row"><b>ERRO</b><code>${escapeHtml(patch.error || "PATCH NÃO RECONHECIDO")}</code></div>`;
    return;
  }
  const src = patch.source || {};
  const dst = patch.target || {};
  const gate = patch.security_gate || {};
  box.innerHTML = `
    <div class="path-row"><b>PATCH</b><code>${escapeHtml(patch.patch_id || patch.arquivo)}</code></div>
    <div class="path-row"><b>TIPO</b><code>${escapeHtml(patch.type || "—")}</code></div>
    <div class="path-row"><b>ORIGEM</b><code>${escapeHtml(src.version || "?")} · BUILD ${escapeHtml(src.build || "?")}</code></div>
    <div class="path-row"><b>DESTINO</b><code>${escapeHtml(dst.version || "?")} · BUILD ${escapeHtml(dst.build || "?")}</code></div>
    <div class="path-row"><b>SECURITY GATE</b><code>${gate.reviewed ? "REVISADO" : "PENDENTE"}${gate.security_changed ? " · SEGURANÇA ALTERADA" : ""}</code></div>
    <div class="path-row"><b>SHA-256</b><code>${escapeHtml(patch.sha256 || "—")}</code></div>`;
}

async function loadMasterPatchStatus(showErrors = false) {
  if (!hasPermission("SYSTEM_ADMIN")) return null;
  try {
    const state = await api("/api/system/master-patches");
    app.masterPatches = state;
    renderMasterPatchStatus();
    return state;
  } catch (error) {
    if (error.status === 403) {
      $("#masterPatchCard").hidden = true;
      return null;
    }
    if (showErrors) toast(error.message, true);
    return null;
  }
}

async function uploadMasterPatch(file) {
  if (!file) return;
  if (!String(file.name || "").toLowerCase().endsWith(".zip")) {
    toast("SELECIONE UM PATCH .ZIP.", true);
    return;
  }
  setBusy(true, "IMPORTANDO PATCH...");
  try {
    const response = await fetch("/api/system/master-patch/import", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/zip",
        "X-CJL-CSRF": csrfToken,
        "X-CJL-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    const payload = await response.json().catch(() => ({ error: "RESPOSTA INVÁLIDA DO SISTEMA." }));
    if (!response.ok || payload.error) throw Object.assign(new Error(payload.error || "FALHA AO IMPORTAR PATCH."), { status: response.status });
    toast(`PATCH IMPORTADO: ${payload.patch?.patch_id || file.name}`);
    await loadMasterPatchStatus(true);
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); $("#masterPatchFile").value = ""; }
}

$("#importMasterPatch").onclick = () => $("#masterPatchFile").click();
$("#masterPatchFile").onchange = event => uploadMasterPatch(event.target.files?.[0]);
$("#validateMasterPatch").onclick = async () => {
  const patch = app.masterPatches?.patches?.[0];
  if (!patch) return;
  setBusy(true, "VALIDANDO PATCH...");
  try {
    const result = await api("/api/system/master-patch/validate", { method:"POST", body:{ arquivo: patch.arquivo } });
    toast(`PATCH VALIDADO: ${result.patch?.patch_id || patch.patch_id}`);
    await loadMasterPatchStatus(false);
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};
$("#removeMasterPatch").onclick = async () => {
  const patch = app.masterPatches?.patches?.[0];
  if (!patch || !confirm(`REMOVER ${patch.patch_id || patch.arquivo} DA FILA DE ATUALIZAÇÃO?`)) return;
  setBusy(true, "REMOVENDO PATCH DA FILA...");
  try {
    await api("/api/system/master-patch/remove", { method:"POST", body:{ arquivo: patch.arquivo } });
    toast("PATCH REMOVIDO DA FILA.");
    await loadMasterPatchStatus(false);
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};
$("#applyMasterPatch").onclick = async () => {
  const patch = app.masterPatches?.patches?.[0];
  if (!patch) return;
  const target = patch.target?.version || "NOVA VERSÃO";
  if (!confirm(`APLICAR ${patch.patch_id || patch.arquivo}?\n\nDESTINO: ${target}\n\nO MESTRE SERÁ ENCERRADO, ATUALIZADO E VALIDADO. SE O PATCH CONCLUIR COM SUCESSO, O SISTEMA SERÁ REABERTO AUTOMATICAMENTE.`)) return;
  setBusy(true, "PREPARANDO PATCH DO MESTRE...");
  try {
    const result = await api("/api/system/master-patch/apply", { method:"POST", body:{ arquivo: patch.arquivo } });
    if (!result.restart) throw new Error("O PATCH NÃO INICIOU O CICLO DE REINICIALIZAÇÃO.");
    $("#closedScreen").hidden = false;
    $("#closedScreen").classList.add("update-restart");
    $("#closedScreen h2").textContent = "ATUALIZANDO CJL System MESTRE";
    $("#closedScreen p").textContent = `APLICANDO ${patch.patch_id || "PATCH"}. O SISTEMA SERÁ VALIDADO E O SNAPSHOT ANTERIOR IRÁ PARA O SM_REPO. EM SUCESSO, O MESTRE REABRIRÁ AUTOMATICAMENTE; EM FALHA, O REINÍCIO SERÁ BLOQUEADO PARA PROTEGER A BASELINE.`;
    document.body.classList.add("system-closed");
  } catch (error) {
    setBusy(false);
    toast(error.message, true);
  }
};

async function backup() {
  setBusy(true, "CRIANDO BACKUP...");
  try {
    const result = await api("/api/system/backup", { method: "POST", body: {} });
    toast(`BACKUP CRIADO: ${result.arquivo}`);
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}

$("#backupTop").onclick = backup;
$("#backupSystem").onclick = backup;
$("#openData").onclick = async () => {
  try {
    const result = await api("/api/system/open-data", { method: "POST", body: {} });
    toast(result.opened ? "PASTA DE DADOS ABERTA." : `CAMINHO: ${result.path}`);
  } catch (error) { toast(error.message, true); }
};
$("#refreshLogs").onclick = async () => {
  try { const result = await api("/api/logs"); app.logs = result.logs; renderLogs(); }
  catch (error) { toast(error.message, true); }
};

async function terminalShutdown(endpoint, body = {}) {
  document.body.classList.add("terminal-shutdown");
  setBusy(true, "ENCERRANDO SISTEMA...");
  try {
    await api(endpoint, { method: "POST", body });
  } catch (error) {
    // Se o backend encerrou entre a resposta HTTP e o fetch, o objetivo já foi
    // atingido. Outros erros continuam sendo mostrados e a janela permanece.
    if (error.code !== "LOCAL_FETCH_FAILED") {
      document.body.classList.remove("terminal-shutdown");
      setBusy(false);
      toast(error.message, true);
      return;
    }
  }
  setTimeout(() => {
    try { window.close(); } catch (_) {}
  }, 80);
}

$("#shutdownSystem").onclick = () => terminalShutdown("/api/shutdown", {});


$("#aboutSystem").onclick = async () => {
  try {
    const about = await api("/api/about");
    const ids = about.patches || {};
    alert(`${about.product} · VERSION ${about.version}\n${ids.structural || ""} · ${ids.incremental || ""} · ${ids.security || ""}\n\nCRIADOR E TITULAR EXCLUSIVO:\n${about.creator} — ${about.public_id}\n${about.official_contact}\n\n${about.copyright}\n\nLICENÇA PROPRIETÁRIA. O ACESSO AO CÓDIGO-FONTE NÃO O TRANSFORMA EM SOFTWARE ABERTO.\n\nMESTRE: ${about.master_id}\nBUILD: ${about.build}`);
  } catch (error) { toast(error.message, true); }
};

const lifecycleClientId = (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).replace(/[^a-zA-Z0-9_-]/g, "");
async function loadLoginResources() {
  try {
    const payload = await api("/api/resources");
    app.resources = payload.resources || [];
    const visible = app.resources.filter(resource => Boolean(resource.user_visible));
    const section = $("#loginResourcesSection");
    const list = $("#loginResourcesList");
    if (section) section.hidden = visible.length === 0;
    list.innerHTML = visible.length ? visible.map(resource => {
      const ready = Boolean(resource.ready ?? (resource.installed && !resource.needs_update));
      const canInstall = Boolean(resource.package_available);
      const action = resource.needs_update ? "ATUALIZAR" : "INSTALAR";
      const state = ready ? "INSTALADO" : resource.needs_update ? "ATUALIZAÇÃO DISPONÍVEL" : "DISPONÍVEL";
      return `<article class="resource-row compact"><div><b>${escapeHtml(resource.name)}</b><small>${escapeHtml(state)}</small></div><div>${ready ? `<span class="badge green">PRONTO</span>` : canInstall ? `<button class="btn primary small install-resource" data-resource-id="${escapeHtml(resource.id)}">${action}</button>` : ""}</div></article>`;
    }).join("") : "";
    $$(".install-resource", list).forEach(button => {
      button.onclick = async () => {
        const definition = app.resources.find(item => item.id === button.dataset.resourceId);
        if (!definition) return;
        setBusy(true, `INSTALANDO ${definition.name}...`);
        try {
          await api("/api/resources/install", { method:"POST", body:{ resource_id: definition.id, client: lifecycleClientId } });
          await loadLoginResources();
          toast(`${definition.name} INSTALADO NESTA ESTAÇÃO.`);
        } catch (error) { toast(error.message, true); }
        finally { setBusy(false); }
      };
    });
  } catch (error) {
    $("#loginResourcesList").innerHTML = `<span class="muted">RECURSOS INDISPONÍVEIS: ${escapeHtml(error.message)}</span>`;
  }
}


$("#toggleLoginResources").onclick = async () => {
  const panel = $("#loginResourcesPanel");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) await loadLoginResources();
};

async function checkStationUpdate(showErrors = false) {
  try {
    const status = await api("/api/system/update-status");
    app.updateStatus = status;
    const banner = $("#updateBanner");
    if (!status.station || !status.available) {
      banner.hidden = true;
      return status;
    }
    const localIds = status.local?.patches || {};
    const masterIds = status.master?.patches || {};
    $("#updateBannerText").textContent = `ESTAÇÃO: ${status.local?.version || "?"} · ${localIds.business || ""}/${localIds.structural || ""}/${localIds.incremental || ""}/${localIds.security || ""} · MESTRE: ${status.master?.version || "?"} · ${masterIds.business || ""}/${masterIds.structural || ""}/${masterIds.incremental || ""}/${masterIds.security || ""}${status.mandatory ? " · ATUALIZAÇÃO OBRIGATÓRIA" : ""}.`;
    banner.hidden = false;
    return status;
  } catch (error) {
    if (showErrors) toast(error.message, true);
    return null;
  }
}

async function requestStationUpdate(requireConfirmation = true) {
  if (requireConfirmation && !confirm("ATUALIZAR ESTA ESTAÇÃO AGORA? O CJL System SERÁ ENCERRADO, ATUALIZADO E REABERTO AUTOMATICAMENTE.")) return;
  setBusy(true, "PREPARANDO ATUALIZAÇÃO DA ESTAÇÃO...");
  try {
    const result = await api("/api/system/apply-update", { method:"POST", body:{ client: lifecycleClientId } });
    if (!result.restart) {
      setBusy(false);
      $("#updateBanner").hidden = true;
      toast("ESTAÇÃO JÁ ESTÁ ATUALIZADA.");
      return;
    }
    $("#closedScreen").hidden = false;
    $("#closedScreen").classList.add("update-restart");
    $("#closedScreen h2").textContent = "ATUALIZANDO CJL System";
    $("#closedScreen p").textContent = "A ESTAÇÃO SERÁ ATUALIZADA A PARTIR DO MESTRE E O SISTEMA REABRIRÁ AUTOMATICAMENTE.";
    document.body.classList.add("system-closed");
  } catch (error) {
    setBusy(false);
    toast(error.message, true);
  }
}

$("#applyStationUpdate").onclick = () => requestStationUpdate(true);
$("#loginCloseSystem").onclick = () => terminalShutdown("/api/lifecycle/shutdown", { client: lifecycleClientId });

function showCriticalMaintenance(state = {}, update = null) {
  app.auth = null;
  csrfToken = "";
  const screen = $("#maintenanceScreen");
  const active = Boolean(state.active);
  const minimumVersion = String(update?.minimum_station_version || state.minimum_station_version || state.target_version || "");
  const localVersion = String(update?.local?.version || "");
  document.body.classList.add("maintenance-disconnected");
  screen.hidden = false;
  $("#maintenanceTitle").textContent = active
    ? "ATUALIZAÇÃO CRÍTICA DO MESTRE"
    : "ATUALIZAÇÃO CRÍTICA CONCLUÍDA";
  $("#maintenanceText").textContent = active
    ? "ESTA ESTAÇÃO FOI DESLOGADA E DESCONECTADA PARA PROTEGER O BANCO E O REPOSITÓRIO OFICIAL."
    : "O MESTRE JÁ FOI LIBERADO, MAS ESTA ESTAÇÃO PRECISA SER ATUALIZADA ANTES DE RECONECTAR.";
  $("#maintenanceDetail").textContent = active
    ? `${state.patch_id || state.target_version || "ATUALIZAÇÃO"} · ${upper(state.phase || "EM APLICAÇÃO")} · AGUARDE A LIBERAÇÃO.`
    : `ESTAÇÃO ${localVersion || "?"} · MÍNIMO EXIGIDO ${minimumVersion || "?"}.`;
  const button = $("#maintenanceUpdateButton");
  button.hidden = active || !update?.available;
}

function hideCriticalMaintenance() {
  $("#maintenanceScreen").hidden = true;
  document.body.classList.remove("maintenance-disconnected");
}

async function checkCriticalState() {
  let maintenance = null;
  try { maintenance = await api("/api/system/maintenance-status"); } catch (_) {}
  if (maintenance?.active) {
    showCriticalMaintenance(maintenance, app.updateStatus);
    return maintenance;
  }
  const update = await checkStationUpdate(false);
  if (update?.blocked_by_critical) {
    showCriticalMaintenance(maintenance || update.maintenance || {}, update);
    return update;
  }
  if (!$("#maintenanceScreen").hidden) {
    hideCriticalMaintenance();
    showLogin("ATUALIZAÇÃO CRÍTICA CONCLUÍDA. INFORME SEU PIN PARA RECONECTAR.");
  }
  return update;
}

$("#maintenanceUpdateButton").onclick = () => requestStationUpdate(false);


const lifecyclePulse = () => fetch(`/api/lifecycle/pulse?client=${encodeURIComponent(lifecycleClientId)}`, {
  method: "GET", cache: "no-store", credentials: "same-origin",
}).catch(() => {});
lifecyclePulse();
setInterval(lifecyclePulse, 3000);
checkCriticalState().catch(() => {});
setInterval(() => checkCriticalState().catch(() => {}), 2000);
setInterval(() => checkStationUpdate(false), 60000);
window.addEventListener("pagehide", () => {
  fetch("/api/lifecycle/close", {
    method: "POST", keepalive: true, credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client: lifecycleClientId }),
  }).catch(() => {});
});

async function loadAll(showBusy = true) {
  if (showBusy) setBusy(true, "CARREGANDO SISTEMA...");
  try {
    const logsRequest = hasPermission("SYSTEM_ADMIN") ? api("/api/logs") : Promise.resolve({ logs: [] });
    const [base, catalog, system, logs] = await Promise.all([api("/api/state"), api("/api/catalogo"), api("/api/system"), logsRequest]);
    Object.assign(app, base);
    app.equipamentos = catalog.equipamentos;
    app.system = system;
    app.logs = logs.logs;
    fillGlobalSelects();
    renderLoads();
    renderWorks();
    renderItems();
    renderClients();
    renderVehicles();
    const factoryForm = $("#factoryForm");
    ["origem_tipo", "nome", "endereco"].forEach(field => { factoryForm.elements[field].value = app.fabrica?.[field] ?? ""; });
    factoryForm.elements.localizacao.value = app.fabrica?.latitude != null && app.fabrica?.longitude != null
      ? `${Number(app.fabrica.latitude).toFixed(6)}, ${Number(app.fabrica.longitude).toFixed(6)}` : "";
    renderRouteDraftWorks();
    if ($("#module-rotas").classList.contains("active")) renderRouteMap();
    renderSystem();
    renderLogs();
    await loadProfit();
    await loadAdminData();
  } finally {
    if (showBusy) setBusy(false);
  }
}

$("#refreshTop").onclick = async () => {
  setBusy(true, "ATUALIZANDO SISTEMA...");
  try { await loadAll(false); toast("DADOS ATUALIZADOS."); }
  catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
};

$("#loginForm").onsubmit = async event => {
  event.preventDefault();
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  $("#loginMessage").textContent = "VALIDANDO ACESSO...";
  $("#loginMessage").className = "login-message";
  try {
    const payload = await api("/api/auth/login", { method: "POST", body: formObject(event.target) });
    await completeAuthentication(payload);
  } catch (error) {
    $("#loginMessage").textContent = upper(error.message);
    $("#loginMessage").className = "login-message error";
    event.target.elements.senha.select();
  } finally { button.disabled = false; }
};

$("#changePasswordForm").onsubmit = async event => {
  event.preventDefault();
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const payload = await api("/api/auth/change-password", { method: "POST", body: formObject(event.target) });
    await completeAuthentication(payload);
    toast("PIN DEFINITIVO CADASTRADO.");
  } catch (error) {
    $("#loginMessage").textContent = upper(error.message);
    $("#loginMessage").className = "login-message error";
  } finally { button.disabled = false; }
};

$("#logoutSystem").onclick = async () => {
  try { await api("/api/auth/logout", { method: "POST", body: {} }); }
  catch (error) { console.warn(error); }
  showLogin("SESSÃO ENCERRADA. INFORME SEU PIN PARA ENTRAR NOVAMENTE.");
};

async function initializeAuthentication() {
  try {
    const payload = await api("/api/auth/me");
    await completeAuthentication(payload);
  } catch (error) {
    showLogin(error.status === 401 ? "" : error.message);
  }
}

$$(".dialog-close").forEach(button => { button.onclick = () => button.closest("dialog")?.close(); });
$$('.dialog').forEach(dialog => dialog.addEventListener("click", event => {
  if (event.target === dialog) dialog.close();
}));

$("#revenueForm").elements.data_competencia.value = today();
initializeAuthentication().catch(error => { setBusy(false); showLogin(error.message); console.error(error); });
