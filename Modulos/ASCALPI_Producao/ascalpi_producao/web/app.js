"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => (v === null || v === undefined || v === "" ? "" : typeof v === "number" ? v.toLocaleString("pt-BR") : esc(v));
const dataBR = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "");
const prazoOP = (o) => (o.prazo_data ? dataBR(o.prazo_data) : esc(o.prazo_texto || ""));

async function api(metodo, url, corpo) {
  const r = await fetch(url, { method: metodo, headers: corpo ? { "Content-Type": "application/json" } : {}, body: corpo ? JSON.stringify(corpo) : undefined });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || `ERRO ${r.status}`);
  return dados;
}
function aviso(msg, erro = false) {
  const a = $("#aviso");
  a.textContent = msg; a.className = "aviso mostrar" + (erro ? " erro" : "");
  clearTimeout(aviso.t); aviso.t = setTimeout(() => (a.className = "aviso"), erro ? 6000 : 3000);
}
function classeSaldo(s) {
  if (s === "ACABOU") return "acabou";
  if (typeof s === "number" && s < 0) return "neg";
  if (s === 0) return "zero";
  return "";
}
function confirmar(titulo, html, rotulo = "Confirmar") {
  return new Promise((ok) => {
    const d = $("#dlg");
    $("#dlg-titulo").textContent = titulo; $("#dlg-corpo").innerHTML = html; $("#dlg-sim").textContent = rotulo;
    const fim = (v) => { d.close(); $("#dlg-sim").onclick = $("#dlg-nao").onclick = null; ok(v); };
    $("#dlg-sim").onclick = () => fim(true); $("#dlg-nao").onclick = () => fim(false);
    d.showModal();
  });
}

// ---------------------------------------------------------------- navegação
const telas = { painel: carregarPainel, nova: () => {}, controle: carregarControle, saldos: carregarSaldos, modelos: carregarModelos, config: carregarConfig };
function irPara(nome) {
  $$("#abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  $$(".tela").forEach((t) => t.classList.toggle("ativa", t.id === "tela-" + nome));
  telas[nome]();
}
$$("#abas button").forEach((b) => (b.onclick = () => { if (b.dataset.tela === "nova") novaOP(); irPara(b.dataset.tela); }));

let PREFEITURAS = [];
async function prefeituras() {
  if (!PREFEITURAS.length) PREFEITURAS = await api("GET", "/api/prefeituras");
  return PREFEITURAS;
}
function opcoes(lista, valor, rotulo, vazio) {
  return (vazio ? `<option value="">${esc(vazio)}</option>` : "") + lista.map((x) => `<option value="${x.id}" ${String(x.id) === String(valor) ? "selected" : ""}>${esc(rotulo(x))}</option>`).join("");
}

// ---------------------------------------------------------------- painel
async function carregarPainel() {
  const r = await api("GET", "/api/resumo");
  $("#cards").innerHTML = [
    ["Próxima O.P.", r.proximo_numero], [`O.P. ativas ${r.ano}`, r.ops_ano], ["Sem data (Definir)", r.sem_data],
    ["Prefeituras", r.prefeituras], ["Modelos", r.modelos], ["Motor de PDF", r.motor_pdf],
  ].map(([t, v]) => `<div class="card"><span>${esc(t)}</span><b>${esc(v)}</b></div>`).join("");
  const ops = (await api("GET", "/api/ops?ano=" + r.ano)).slice(0, 12);
  $("#ultimas").innerHTML = cabecalhoOps() + `<tbody>${ops.map(linhaOp).join("")}</tbody>`;
  $("#ultimas").classList.add("clicavel");
  ligarLinhasOps($("#ultimas"));
}

// ---------------------------------------------------------------- nova / editar O.P.
const estado = { opId: null, modelo: null, sim: null, timer: null };

async function novaOP() {
  estado.opId = null; estado.modelo = null;
  $("#op-titulo").textContent = "Nova O.P.";
  $("#b-salvar").textContent = "Gerar O.P.";
  $("#l-motivo").classList.add("oculto");
  $("#f-prefeitura").disabled = $("#f-modelo").disabled = false;
  ["#f-obra", "#f-solicitante", "#f-tipo", "#f-motivo"].forEach((s) => ($(s).value = ""));
  $("#f-prazo-data").value = ""; $("#f-prazo-definir").checked = false; $("#f-prazo-texto").value = "DEFINIR"; trocarPrazo();
  const p = await prefeituras();
  $("#f-prefeitura").innerHTML = opcoes(p.filter((x) => x.modelos > 0), "", (x) => x.nome, "Escolha a prefeitura");
  $("#f-modelo").innerHTML = "";
  $("#itens").innerHTML = ""; $("#info-modelo").textContent = ""; $("#sim-status").innerHTML = "";
  $("#op-numero").textContent = "Próxima: " + (await api("GET", "/api/ops/proximo")).numero;
}

$("#f-prefeitura").onchange = async () => {
  const pid = $("#f-prefeitura").value;
  const ms = pid ? await api("GET", "/api/modelos?prefeitura_id=" + pid) : [];
  $("#f-modelo").innerHTML = opcoes(ms, ms.length === 1 ? ms[0].id : "", (m) => `${m.aba}${m.ata ? "" : "  (sem contrato)"}`, ms.length === 1 ? null : "Escolha o modelo");
  if (ms.length === 1) await carregarModelo(ms[0].id);
  else { $("#itens").innerHTML = ""; estado.modelo = null; }
};
$("#f-modelo").onchange = () => $("#f-modelo").value && carregarModelo($("#f-modelo").value);

async function carregarModelo(id, op) {
  const m = await api("GET", `/api/modelos/${id}` + (op ? `?excluir_op=${op.id}` : ""));
  estado.modelo = m;
  if (!op && !$("#f-tipo").value) $("#f-tipo").value = m.tipo_padrao || "";
  const pref = PREFEITURAS.find((p) => p.id === m.prefeitura_id) || {};
  $("#info-modelo").textContent = [m.titulo, m.contrato_id ? "" : "Modelo sem contrato: o saldo não é controlado.",
    pref.cores_aparelhos ? "Cores dos aparelhos: " + pref.cores_aparelhos.replace(/\n/g, " · ") : "",
    pref.cores_canoplas ? "Canoplas/fixador: " + pref.cores_canoplas.replace(/\n/g, " · ") : ""].filter(Boolean).join("\n");
  const itens = {}; (op?.itens || []).forEach((i) => (itens[i.linha] = i));
  $("#itens").innerHTML = `<thead><tr><th>Cód.</th><th>Equipamento</th><th class="num">Saldo</th><th>Quantidade</th><th>Inauguração</th><th>Observação</th><th class="num">Depois</th></tr></thead><tbody>` +
    m.linhas.map((l) => {
      const it = itens[l.linha] || {};
      return `<tr data-linha="${l.linha}" data-codigo="${esc(l.codigo)}">
        <td class="c">${esc(l.codigo)}</td><td>${esc(l.equipamento)}</td>
        <td class="num ${classeSaldo(l.saldo)}">${l.saldo === null ? "—" : num(l.saldo)}</td>
        <td class="q"><input inputmode="decimal" class="qtd" value="${it.quantidade != null ? String(it.quantidade).replace(".", ",") : ""}"></td>
        <td class="i"><input class="inaug" value="${esc(it.inauguracao || "")}"></td>
        <td><input class="obs" value="${esc(it.observacao || "")}"></td>
        <td class="num depois"></td></tr>`;
    }).join("") + "</tbody>";
  $$("#itens input").forEach((i) => (i.oninput = () => { marcarLinhas(); agendarSimulacao(); }));
  marcarLinhas(); simular();
}
function marcarLinhas() {
  const so = $("#f-so-qtd").checked;
  $$("#itens tbody tr").forEach((tr) => {
    const tem = $(".qtd", tr).value.trim() !== "" && $(".qtd", tr).value.trim() !== "0";
    tr.classList.toggle("tem", tem); tr.classList.toggle("oculto", so && !tem);
  });
}
$("#f-so-qtd").onchange = marcarLinhas;
function itensForm() {
  return $$("#itens tbody tr").map((tr) => ({ linha: +tr.dataset.linha, quantidade: $(".qtd", tr).value.trim(), inauguracao: $(".inaug", tr).value.trim(), observacao: $(".obs", tr).value.trim() }))
    .filter((i) => i.quantidade !== "" && i.quantidade !== "0");
}
function agendarSimulacao() { clearTimeout(estado.timer); estado.timer = setTimeout(simular, 300); }
async function simular() {
  if (!estado.modelo) return;
  const itens = itensForm();
  $$("#itens .depois").forEach((td) => (td.textContent = ""));
  if (!itens.length) { $("#sim-status").innerHTML = '<span class="mudo">Informe a quantidade dos equipamentos desta O.P.</span>'; return; }
  try {
    const s = await api("POST", "/api/simular", { modelo_id: estado.modelo.id, itens, op_id: estado.opId });
    estado.sim = s;
    const porCod = {};
    [...s.negativos, ...s.encerrados].forEach((a) => (porCod[a.codigo] = a));
    const base = (c) => (c.startsWith("0.") ? c : c.split(".")[0]);
    $$("#itens tbody tr").forEach((tr) => {
      const a = porCod[base(tr.dataset.codigo || "")];
      if (a && $(".qtd", tr).value.trim()) { const td = $(".depois", tr); td.textContent = typeof a.depois === "number" ? a.depois.toLocaleString("pt-BR") : a.depois; td.className = "num depois " + (typeof a.depois === "number" && a.depois === 0 ? "zero" : "neg"); }
    });
    const n = itens.length;
    const txt = { SALDO_OK: ["ok", "Saldo OK"], SEM_CONTRATO: ["alerta", "Sem contrato"], SALDO_ENCERRADO: ["alerta", "Encerra saldo de " + s.encerrados.length + " item(ns)"],
      SALDO_NEGATIVO: ["erro", "Saldo negativo em " + s.negativos.length + " item(ns) — exige confirmação"], ESTRUTURA_INVALIDA: ["erro", s.erros.join(" ")] }[s.status] || ["", s.status];
    $("#sim-status").innerHTML = `<span class="selo ${txt[0]}">${esc(txt[1])}</span> <span class="mudo">${n} equipamento(s) na O.P.</span>`;
  } catch (e) { $("#sim-status").innerHTML = `<span class="selo erro">${esc(e.message)}</span>`; }
}

function trocarPrazo() {
  const sem = $("#f-prazo-definir").checked;
  $("#f-prazo-data").classList.toggle("oculto", sem); $("#f-prazo-texto").classList.toggle("oculto", !sem);
}
$("#f-prazo-definir").onchange = trocarPrazo;

function dadosForm() {
  return {
    modelo_id: estado.modelo?.id, obra: $("#f-obra").value, solicitante: $("#f-solicitante").value, tipo: $("#f-tipo").value,
    prazo: $("#f-prazo-definir").checked ? $("#f-prazo-texto").value || "DEFINIR" : $("#f-prazo-data").value,
    itens: itensForm(), motivo: $("#f-motivo").value,
  };
}
$("#b-limpar").onclick = () => (estado.opId ? abrirEdicao(estado.opId) : novaOP());
$("#b-salvar").onclick = async () => {
  if (!estado.modelo) return aviso("ESCOLHA A PREFEITURA E O MODELO.", true);
  const b = $("#b-salvar"); b.disabled = true;
  try {
    const corpo = dadosForm();
    const url = estado.opId ? `/api/ops/${estado.opId}` : "/api/ops", met = estado.opId ? "PUT" : "POST";
    let r = await api(met, url, corpo);
    if (r.precisa_confirmacao) {
      const linhas = r.simulacao.negativos.map((a) => `<tr><td>${esc(a.codigo)}</td><td>${esc(a.equipamento)}</td><td class="num">${num(a.antes)}</td><td class="num">${num(a.quantidade)}</td><td class="num neg">${num(a.depois)}</td></tr>`).join("");
      const ok = await confirmar("Saldo negativo no contrato", `<p>Esta O.P. deixa o contrato com saldo negativo:</p><table class="grade"><thead><tr><th>Cód.</th><th>Equipamento</th><th class="num">Antes</th><th class="num">O.P.</th><th class="num">Depois</th></tr></thead><tbody>${linhas}</tbody></table><p>Deseja continuar mesmo assim?</p>`, "Continuar com saldo negativo");
      if (!ok) return;
      r = await api(met, url, { ...corpo, confirmar_negativo: true });
    }
    const pub = r.publicacao || {};
    aviso(`O.P. ${r.op.numero} REV ${r.op.rev} SALVA` + (pub.pdf_erro ? " (PDF NÃO GERADO: " + pub.pdf_erro + ")" : ""), !!pub.pdf_erro);
    PREFEITURAS = [];
    irPara("controle"); abrirOp(r.op_id);
  } catch (e) { aviso(e.message, true); } finally { b.disabled = false; }
};

async function abrirEdicao(id) {
  const o = await api("GET", `/api/ops/${id}`);
  await prefeituras();
  estado.opId = o.id;
  irPara("nova");
  $("#op-titulo").textContent = `Editar O.P. ${o.numero}`;
  $("#op-numero").textContent = `REV ${o.rev} → ${o.rev + 1}`;
  $("#b-salvar").textContent = "Salvar revisão";
  $("#l-motivo").classList.remove("oculto");
  $("#f-prefeitura").innerHTML = opcoes(PREFEITURAS, o.prefeitura_id, (x) => x.nome);
  $("#f-modelo").innerHTML = `<option value="${o.modelo_id}">${esc(o.modelo)}</option>`;
  $("#f-prefeitura").disabled = $("#f-modelo").disabled = true;
  $("#f-obra").value = o.obra; $("#f-solicitante").value = o.solicitante; $("#f-tipo").value = o.tipo || ""; $("#f-motivo").value = "";
  $("#f-prazo-definir").checked = !o.prazo_data; $("#f-prazo-data").value = o.prazo_data || ""; $("#f-prazo-texto").value = o.prazo_texto || "DEFINIR"; trocarPrazo();
  await carregarModelo(o.modelo_id, o);
}

// ---------------------------------------------------------------- controle
function cabecalhoOps() {
  return `<thead><tr><th>Nº</th><th>Cliente</th><th>Obra</th><th>Solicitante</th><th>Tipo</th><th>Material</th><th>Solicitação</th><th>Entrega</th><th>Atualizada</th><th>Instalação</th><th>Rev</th><th></th></tr></thead>`;
}
function linhaOp(o) {
  const sit = o.situacao === "CANCELADA" ? '<span class="selo erro">CANCELADA</span>' : o.origem === "LEGADO" ? '<span class="selo">LEGADO</span>' : "";
  return `<tr data-id="${o.id}"><td><b>${esc(o.numero)}</b></td><td>${esc(o.cliente)}</td><td>${esc(o.obra)}</td><td>${esc(o.solicitante)}</td><td>${esc(o.tipo)}</td><td>${esc(o.material)}</td>
    <td>${dataBR(o.solicitado_em)}</td><td>${prazoOP(o)}</td><td>${o.entrega_atualizada && /^\d{4}-/.test(o.entrega_atualizada) ? dataBR(o.entrega_atualizada) : esc(o.entrega_atualizada)}</td>
    <td>${esc(o.status_instalacao)}</td><td class="num">${o.origem === "SISTEMA" ? o.rev : ""}</td><td>${sit}</td></tr>`;
}
function ligarLinhasOps(tabela) { $$("tbody tr", tabela).forEach((tr) => (tr.onclick = () => abrirOp(+tr.dataset.id))); }

async function carregarControle() {
  const p = await prefeituras();
  if (!$("#c-prefeitura").dataset.ok) {
    $("#c-prefeitura").innerHTML = opcoes(p, "", (x) => x.nome, "Todas as prefeituras");
    const ano = new Date().getFullYear();
    $("#c-ano").innerHTML = `<option value="">Todos os anos</option>` + [ano, ano - 1, ano - 2].map((a) => `<option ${a === ano ? "selected" : ""}>${a}</option>`).join("");
    $("#c-prefeitura").dataset.ok = 1;
    ["#c-prefeitura", "#c-ano", "#c-situacao"].forEach((s) => ($(s).onchange = listarOps));
    $("#c-texto").oninput = () => { clearTimeout(listarOps.t); listarOps.t = setTimeout(listarOps, 250); };
  }
  await listarOps();
}
async function listarOps() {
  const q = new URLSearchParams({ texto: $("#c-texto").value, ano: $("#c-ano").value, prefeitura_id: $("#c-prefeitura").value, situacao: $("#c-situacao").value });
  const ops = await api("GET", "/api/ops?" + q);
  $("#lista-ops").innerHTML = cabecalhoOps() + `<tbody>${ops.map(linhaOp).join("") || '<tr><td colspan="12" class="mudo">Nenhuma O.P.</td></tr>'}</tbody>`;
  ligarLinhasOps($("#lista-ops"));
}

async function abrirOp(id) {
  const o = await api("GET", `/api/ops/${id}`);
  $("#g-titulo").textContent = `O.P. ${o.numero}` + (o.origem === "SISTEMA" ? ` · REV ${o.rev}` : " · histórico legado");
  const sistema = o.origem === "SISTEMA", ativa = o.situacao === "ATIVA";
  const acomp = [["status_instalacao", "Status instalação"], ["entrega_atualizada", "Entrega atualizada"], ["material_obra", "Material obra"], ["fotografico", "Fotográfico"], ["obs", "Obs."]];
  $("#g-corpo").innerHTML = `
    ${o.situacao === "CANCELADA" ? '<p><span class="selo erro">CANCELADA</span></p>' : ""}
    <dl><dt>Cliente</dt><dd>${esc(o.cliente)}</dd><dt>Obra</dt><dd>${esc(o.obra)}</dd><dt>Solicitante</dt><dd>${esc(o.solicitante)}</dd>
    <dt>Modelo</dt><dd>${esc(o.modelo || "—")}</dd><dt>Tipo / material</dt><dd>${esc(o.tipo)} · ${esc(o.material)}</dd>
    <dt>Prazo</dt><dd>${prazoOP(o)}</dd><dt>Solicitação</dt><dd>${dataBR(o.solicitado_em)}</dd>
    ${o.saldo_status ? `<dt>Saldo</dt><dd>${esc(o.saldo_status)}</dd>` : ""}
    ${o.arquivos?.xlsx ? `<dt>Publicado</dt><dd class="mudo">${esc(o.arquivos.xlsx)}${o.arquivos.pdf ? "<br>" + esc(o.arquivos.pdf) : ""}${o.arquivos.pdf_erro ? '<br><span class="neg">PDF: ' + esc(o.arquivos.pdf_erro) + "</span>" : ""}</dd>` : ""}</dl>
    ${sistema ? `<div class="acoes">
      <a href="/api/ops/${o.id}/documento.pdf" target="_blank"><button>Ver PDF</button></a>
      <a href="/api/ops/${o.id}/documento.xlsx"><button class="sec">Baixar XLSX</button></a>
      <a href="/api/ops/${o.id}/documento.pdf?baixar=1"><button class="sec">Baixar PDF</button></a>
      ${ativa ? `<button class="sec" id="g-editar">Editar (nova REV)</button><button class="sec" id="g-publicar">Republicar</button><button class="perigo" id="g-cancelar">Cancelar O.P.</button>` : ""}
    </div>` : ""}
    ${o.itens.length ? `<h2>Equipamentos</h2><table class="grade"><thead><tr><th>Cód.</th><th>Equipamento</th><th class="num">Qtd.</th><th>Inaug.</th><th>Obs.</th></tr></thead><tbody>
      ${o.itens.map((i) => `<tr><td>${esc(i.codigo)}</td><td>${esc(i.equipamento)}</td><td class="num">${num(i.quantidade)}</td><td>${esc(i.inauguracao)}</td><td>${esc(i.observacao)}</td></tr>`).join("")}</tbody></table>` : ""}
    <h2 style="margin-top:16px">Acompanhamento</h2>
    <div class="form-grade">${acomp.map(([k, t]) => `<label>${t}<input data-campo="${k}" value="${esc(o[k] || "")}"></label>`).join("")}</div>
    <button id="g-acomp">Salvar acompanhamento</button>
    ${o.revisoes.length ? `<h2 style="margin-top:16px">Revisões</h2><table class="grade"><tbody>${o.revisoes.map((r) => `<tr><td>REV ${r.rev}</td><td>${esc(r.momento.replace("T", " "))}</td><td>${esc(r.resumo)}</td></tr>`).join("")}</tbody></table>` : ""}`;
  $("#gaveta").classList.add("aberta");
  $("#g-acomp").onclick = async () => {
    const c = {}; $$("#g-corpo [data-campo]").forEach((i) => (c[i.dataset.campo] = i.value));
    try { await api("POST", `/api/ops/${o.id}/acompanhamento`, c); aviso("ACOMPANHAMENTO SALVO"); listarOps(); } catch (e) { aviso(e.message, true); }
  };
  const ed = $("#g-editar"); if (ed) ed.onclick = () => { $("#gaveta").classList.remove("aberta"); abrirEdicao(o.id); };
  const pb = $("#g-publicar"); if (pb) pb.onclick = async () => { pb.disabled = true; try { await api("POST", `/api/ops/${o.id}/publicar`); aviso("ARQUIVOS REPUBLICADOS"); abrirOp(o.id); } catch (e) { aviso(e.message, true); } finally { pb.disabled = false; } };
  const cn = $("#g-cancelar"); if (cn) cn.onclick = async () => {
    const ok = await confirmar(`Cancelar O.P. ${o.numero}`, `<p>O saldo desta O.P. volta para o contrato. O número não é reaproveitado.</p><label>Motivo<input id="dlg-motivo"></label>`, "Cancelar O.P.");
    if (!ok) return;
    try { await api("POST", `/api/ops/${o.id}/cancelar`, { motivo: $("#dlg-motivo").value }); aviso("O.P. CANCELADA"); abrirOp(o.id); listarOps(); } catch (e) { aviso(e.message, true); }
  };
}
$("#g-fechar").onclick = () => $("#gaveta").classList.remove("aberta");

// ---------------------------------------------------------------- saldos
async function carregarSaldos() {
  const p = await prefeituras();
  if (!$("#s-prefeitura").dataset.ok) {
    $("#s-prefeitura").innerHTML = opcoes(p, "", (x) => x.nome, "Escolha a prefeitura");
    $("#s-prefeitura").dataset.ok = 1;
    $("#s-prefeitura").onchange = async () => {
      const cs = $("#s-prefeitura").value ? await api("GET", "/api/contratos?prefeitura_id=" + $("#s-prefeitura").value) : [];
      $("#s-contrato").innerHTML = opcoes(cs, cs[0]?.id, (c) => `${c.ata} — ${c.nome}`);
      mostrarSaldo();
    };
    $("#s-contrato").onchange = mostrarSaldo;
  }
}
async function mostrarSaldo() {
  const cid = $("#s-contrato").value;
  if (!cid) { $("#saldo").innerHTML = ""; return; }
  const itens = await api("GET", `/api/contratos/${cid}/saldo`);
  const c = $("#s-contrato").selectedOptions[0]?.textContent || "";
  $("#s-desc").textContent = c;
  $("#saldo").innerHTML = `<thead><tr><th>Cód.</th><th>Equipamento</th><th class="num">Montante</th><th class="num">Quant. (medido+instalado)</th><th class="num">Previsão</th><th class="num">Saldo</th><th>Ajuste manual</th></tr></thead><tbody>` +
    itens.map((i) => `<tr data-codigo="${esc(i.codigo)}"><td>${esc(i.codigo)}</td><td>${esc(i.equipamento)}</td><td class="num">${num(i.montante)}</td><td class="num">${num(i.quant)}</td>
      <td class="num">${num(i.previsao)}</td><td class="num ${classeSaldo(i.saldo)}">${num(i.saldo)}</td>
      <td class="ajuste"><input value="${i.ajuste ? String(i.ajuste).replace(".", ",") : ""}" title="Soma na previsão (+ consome, - devolve)"> <button class="sec">OK</button></td></tr>`).join("") + "</tbody>";
  $$("#saldo tbody tr").forEach((tr) => ($("button", tr).onclick = async () => {
    const v = $("input", tr).value.replace(",", ".") || "0";
    const ok = await confirmar("Ajuste manual de saldo", `<p>Item ${esc(tr.dataset.codigo)}: ajuste = ${esc(v)}</p><label>Motivo<input id="dlg-motivo"></label>`);
    if (!ok) return;
    try { await api("POST", `/api/contratos/${cid}/ajuste`, { codigo: tr.dataset.codigo, ajuste: +v, motivo: $("#dlg-motivo").value }); aviso("AJUSTE SALVO"); mostrarSaldo(); } catch (e) { aviso(e.message, true); }
  }));
}

// ---------------------------------------------------------------- modelos
async function carregarModelos() {
  const ms = await api("GET", "/api/modelos?todos=1");
  const cs = await api("GET", "/api/contratos");
  $("#lista-modelos").innerHTML = `<thead><tr><th>Prefeitura</th><th>Modelo (aba)</th><th>Título</th><th class="num">Equip.</th><th>Contrato do saldo</th><th>Ativo</th></tr></thead><tbody>` +
    ms.map((m) => `<tr data-id="${m.id}"><td>${esc(m.prefeitura)}</td><td>${esc(m.aba)}</td><td>${esc(m.titulo)}</td><td class="num">${m.equipamentos}</td>
      <td><select class="m-contrato">${opcoes(cs.filter((c) => c.prefeitura_id === m.prefeitura_id), m.contrato_id, (c) => `${c.ata} — ${c.nome}`, "Sem contrato")}</select></td>
      <td><input type="checkbox" class="m-ativo" ${m.ativo ? "checked" : ""}></td></tr>`).join("") + "</tbody>";
  $$("#lista-modelos tbody tr").forEach((tr) => {
    $(".m-contrato", tr).onchange = async (e) => { try { await api("PATCH", `/api/modelos/${tr.dataset.id}`, { contrato_id: +e.target.value || 0 }); aviso("MODELO ATUALIZADO"); } catch (er) { aviso(er.message, true); } };
    $(".m-ativo", tr).onchange = async (e) => { try { await api("PATCH", `/api/modelos/${tr.dataset.id}`, { ativo: e.target.checked }); PREFEITURAS = []; aviso("MODELO ATUALIZADO"); } catch (er) { aviso(er.message, true); } };
  });
}

// ---------------------------------------------------------------- configuração
async function carregarConfig() {
  const c = await api("GET", "/api/config");
  $("#cfg-publicar").checked = !!c.publicar; $("#cfg-xlsx").value = c.pasta_xlsx; $("#cfg-pdf").value = c.pasta_pdf; $("#cfg-motor").value = c.motor_pdf;
  const ev = await api("GET", "/api/eventos");
  $("#eventos").innerHTML = "<tbody>" + ev.slice(0, 60).map((e) => `<tr><td>${esc(e.momento.replace("T", " "))}</td><td>${esc(e.acao)}</td><td class="mudo">${esc(e.detalhe).slice(0, 160)}</td></tr>`).join("") + "</tbody>";
}
$("#b-cfg").onclick = async () => {
  try { await api("PUT", "/api/config", { publicar: $("#cfg-publicar").checked, pasta_xlsx: $("#cfg-xlsx").value.trim(), pasta_pdf: $("#cfg-pdf").value.trim(), motor_pdf: $("#cfg-motor").value }); aviso("CONFIGURAÇÃO SALVA"); }
  catch (e) { aviso(e.message, true); }
};

irPara("painel");
