// ASCALPI Produção — tela web (JS puro, módulo ES, sem build e sem bibliotecas).
// Telas: Painel, Nova O.P., Ordens (+ gaveta da O.P.), Saldos, Modelos e Configuração.

// ================================================================== utilidades
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ic = n => `<svg aria-hidden="true"><use href="#i-${n}"/></svg>`;
const norm = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
const num = v => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) : esc(v);
};
const dataBR = iso => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '';
const dataHoraBR = iso => iso ? `${dataBR(iso)} ${iso.slice(11, 16)}` : '';
const plural = (n, um, varios) => `${num(n)} ${Number(n) === 1 ? um : varios}`;
const hojeISO = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
const nodo = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };

function lerNumero(v) {
  let s = String(v ?? '').trim();
  if (!s) return 0;
  if (s.includes(',') && s.includes('.')) s = s.replace(/\./g, '').replace(',', '.');
  else s = s.replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

// localStorage pode falhar (modo privado, bloqueio): nunca quebra a tela
const memoria = {
  ler(k, padrao = null) { try { const v = localStorage.getItem('ascalpi.' + k); return v == null ? padrao : JSON.parse(v); } catch { return padrao; } },
  gravar(k, v) { try { localStorage.setItem('ascalpi.' + k, JSON.stringify(v)); } catch { /* sem memória local */ } },
  apagar(k) { try { localStorage.removeItem('ascalpi.' + k); } catch { /* idem */ } },
};

function tempoRelativo(iso) {
  if (!iso) return '';
  const min = Math.round((Date.now() - new Date(iso)) / 6e4);
  if (min < 1) return 'AGORA';
  if (min < 60) return `HÁ ${min} MIN`;
  const h = Math.round(min / 60);
  if (h < 24) return `HÁ ${h} H`;
  const d = Math.round(h / 24);
  return d < 8 ? `HÁ ${d} ${d === 1 ? 'DIA' : 'DIAS'}` : dataBR(iso);
}

// ================================================================== situação da O.P.
const ESTADO = {
  ATRASADA: { rot: 'ATRASADA', ic: 'alert' },
  PROXIMA: { rot: 'PRAZO PRÓXIMO', ic: 'clock' },
  NO_PRAZO: { rot: 'NO PRAZO', ic: 'calendar' },
  SEM_DATA: { rot: 'SEM DATA', ic: 'calendar-q' },
  NA_OBRA: { rot: 'NA OBRA', ic: 'truck' },
  INSTALADA: { rot: 'INSTALADA', ic: 'check' },
  CANCELADA: { rot: 'CANCELADA', ic: 'x-circle' },
};
const EM_PRODUCAO = 'ATRASADA,PROXIMA,NO_PRAZO,SEM_DATA';
const pilula = e => `<span class="pilula e-${e}">${ic(ESTADO[e].ic)}${ESTADO[e].rot}</span>`;
const prazoTexto = o => o.prazo_efetivo ? dataBR(o.prazo_efetivo) : (o.prazo_texto || 'DEFINIR');

function prazoDias(o) {
  if (['CANCELADA', 'INSTALADA', 'NA_OBRA'].includes(o.estado) || o.dias == null) return ESTADO[o.estado].rot;
  if (o.dias < 0) return `HÁ ${plural(-o.dias, 'DIA', 'DIAS')}`;
  if (o.dias === 0) return 'ENTREGA HOJE';
  if (o.dias === 1) return 'AMANHÃ';
  return `EM ${o.dias} DIAS`;
}

// ================================================================== API, barra de progresso e status
const statusEl = $('#status-sistema');
let pendentes = 0;
let semConexao = false;
let vigia = null;

function marcarStatus(classe, texto) {
  statusEl.className = 'system-status' + (classe ? ' ' + classe : '');
  statusEl.querySelector('b').textContent = texto;
}

function vigiarConexao() {
  if (vigia) return;
  vigia = setInterval(async () => {
    try {
      const r = await fetch('/api/ops/proximo', { cache: 'no-store' });
      if (!r.ok) return;
      clearInterval(vigia); vigia = null; semConexao = false;
      marcarStatus('', 'SISTEMA PRONTO');
      aviso('CONEXÃO RESTABELECIDA.', 'ok');
    } catch { /* continua tentando */ }
  }, 8000);
}

async function api(caminho, { metodo = 'GET', corpo } = {}) {
  pendentes++;
  document.body.classList.remove('carregou');
  document.body.classList.add('carregando');
  if (!semConexao) marcarStatus('ocupado', 'PROCESSANDO');
  try {
    let r;
    try {
      r = await fetch(caminho, {
        method: metodo,
        headers: corpo ? { 'Content-Type': 'application/json' } : {},
        body: corpo ? JSON.stringify(corpo) : undefined,
        cache: 'no-store',
      });
    } catch {
      semConexao = true;
      marcarStatus('erro', 'SEM CONEXÃO');
      vigiarConexao();
      throw new Error('SEM CONEXÃO COM O SERVIDOR. CONFIRA SE O ASCALPI PRODUÇÃO ESTÁ ABERTO.');
    }
    const dados = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(dados.erro || `ERRO ${r.status} NO SERVIDOR.`);
    return dados;
  } finally {
    if (--pendentes === 0) {
      document.body.classList.replace('carregando', 'carregou');
      setTimeout(() => { if (!pendentes) document.body.classList.remove('carregou'); }, 650);
      if (!semConexao) marcarStatus('', 'SISTEMA PRONTO');
    }
  }
}

// botão ocupado (aria-busy) enquanto a ação roda
async function ocupado(botao, acao) {
  if (botao) botao.setAttribute('aria-busy', 'true');
  try { return await acao(); } finally { if (botao) botao.removeAttribute('aria-busy'); }
}

// ================================================================== aviso e diálogo
let avisoT;
function aviso(msg, tipo = 'ok') {
  const t = $('#toast');
  t.className = 'toast ' + tipo;
  t.innerHTML = ic(tipo === 'erro' ? 'alert' : 'check') + `<span>${esc(msg)}</span>`;
  requestAnimationFrame(() => t.classList.add('mostrar'));
  clearTimeout(avisoT);
  avisoT = setTimeout(() => t.classList.remove('mostrar'), tipo === 'erro' ? 6500 : 3800);
}
const falha = e => aviso(e?.message || String(e), 'erro');

const dlg = $('#dlg');
const dlgForm = dlg.querySelector('form');
let dlgValidar = null;

dlgForm.addEventListener('submit', e => {
  if (e.submitter?.value !== 'sim' || !dlgValidar) return;
  const erro = dlgValidar($('#dlg-corpo'));
  if (erro) { e.preventDefault(); aviso(erro, 'erro'); }
});
// Enter num campo confirma (o 1º botão do formulário é o "fechar")
dlgForm.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.matches('input') && !$('#dlg-sim').closest('footer').hidden) {
    e.preventDefault();
    $('#dlg-sim').click();
  }
});

function dialogo({ titulo, sub = '', corpo = '', rotulo = 'CONFIRMAR', perigo = false, largo = false, semRodape = false, validar = null }) {
  return new Promise(resolver => {
    $('#dlg-titulo').textContent = titulo;
    const p = $('#dlg-sub');
    p.textContent = sub; p.hidden = !sub;
    const c = $('#dlg-corpo');
    if (typeof corpo === 'string') c.innerHTML = corpo; else c.replaceChildren(corpo);
    const sim = $('#dlg-sim');
    sim.textContent = rotulo;
    sim.className = 'btn ' + (perigo ? 'danger' : 'primary');
    dlg.classList.toggle('largo', largo);
    dlg.querySelector('footer').hidden = semRodape;
    dlgValidar = validar;
    dlg.returnValue = '';
    dlg.addEventListener('close', () => { dlgValidar = null; resolver(dlg.returnValue === 'sim' ? c : null); }, { once: true });
    dlg.showModal();
    const primeiro = c.querySelector('input:not([type=hidden]),textarea,select');
    if (primeiro) primeiro.focus();
  });
}

function verFoto(src, titulo) {
  dialogo({ titulo, corpo: `<div class="foto-grande"><img src="${esc(src)}" alt="${esc(titulo)}"></div>`, largo: true, semRodape: true });
}

// ================================================================== interações globais
// onda no clique (UStracker)
document.addEventListener('pointerdown', e => {
  const b = e.target.closest('.btn, .segmentado button, .opcao, .contador button, .pref');
  if (!b || b.disabled) return;
  const r = b.getBoundingClientRect();
  const d = Math.max(r.width, r.height);
  const s = document.createElement('span');
  s.className = 'onda';
  s.style.cssText = `width:${d}px;height:${d}px;left:${e.clientX - r.left - d / 2}px;top:${e.clientY - r.top - d / 2}px`;
  b.appendChild(s);
  s.addEventListener('animationend', () => s.remove());
});

// imagem que falhar vira ícone
document.addEventListener('error', e => {
  const img = e.target;
  if (img.tagName !== 'IMG') return;
  img.replaceWith(nodo(ic(img.dataset.icone || 'image')));
}, true);

// dica flutuante dos gráficos (hover e foco)
const tip = $('#tip');
function mostrarTip(alvo, x, y) {
  const d = alvo.dataset;
  tip.innerHTML = `<small>${esc(d.tipTitulo)}</small><strong>${esc(d.tipValor)}</strong>` +
    (d.tipExtra ? `<div class="linha-chave" style="--cor:${esc(d.tipCor || 'var(--blue)')}"><i></i>${esc(d.tipExtra)}</div>` : '');
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, x - w / 2)) + 'px';
  tip.style.top = Math.max(8, y - h - 14) + 'px';
}
document.addEventListener('pointerover', e => {
  const a = e.target.closest('[data-tip-titulo]');
  if (a) mostrarTip(a, e.clientX, e.clientY);
});
document.addEventListener('pointermove', e => {
  const a = e.target.closest('[data-tip-titulo]');
  if (a) mostrarTip(a, e.clientX, e.clientY); else tip.hidden = true;
});
document.addEventListener('focusin', e => {
  const a = e.target.closest?.('[data-tip-titulo]');
  if (!a) return;
  const r = a.getBoundingClientRect();
  mostrarTip(a, r.left + r.width / 2, r.top);
});
document.addEventListener('focusout', () => { tip.hidden = true; });
addEventListener('scroll', () => { tip.hidden = true; }, { passive: true });

// ================================================================== rotas por hash
const app = $('#app');
let baseAtual = null;
let geracao = 0;

function lerRota() {
  const h = location.hash.replace(/^#\/?/, '');
  const [caminho, qs = ''] = h.split('?');
  const partes = caminho.split('/').filter(Boolean);
  return { tela: partes[0] || 'painel', arg: partes[1], q: Object.fromEntries(new URLSearchParams(qs)) };
}

function montarHash(tela, arg, q = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== '' && v != null) p.set(k, v);
  const s = p.toString();
  return '#/' + tela + (arg ? '/' + arg : '') + (s ? '?' + s : '');
}

// muda os filtros na URL sem redesenhar a tela
function trocarQuery(novos) {
  const r = lerRota();
  const q = { ...r.q, ...novos };
  history.replaceState(null, '', montarHash(r.tela, r.arg, q));
  const { op, ...resto } = q;
  baseAtual = montarHash(r.tela, r.arg, resto);
}

function linkOP(id) {
  const r = lerRota();
  return montarHash(r.tela, r.arg, { ...r.q, op: id });
}
const abrirOP = id => { location.hash = linkOP(id); };

const TELAS = {};
const ABA_DA_TELA = { editar: 'nova' };

async function rotear() {
  const r = lerRota();
  const { op, ...resto } = r.q;
  const base = montarHash(r.tela, r.arg, resto);
  if (base !== baseAtual) {
    baseAtual = base;
    await desenharTela(r);
  }
  if (op) abrirGaveta(Number(op)); else fecharGavetaVisual();
}

async function desenharTela(r, { manterRolagem = false } = {}) {
  const fn = TELAS[r.tela] || TELAS.painel;
  const aba = ABA_DA_TELA[r.tela] || (TELAS[r.tela] ? r.tela : 'painel');
  $$('.module-tab').forEach(a => {
    const ativa = a.dataset.tela === aba;
    a.classList.toggle('ativa', ativa);
    if (ativa) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  const minha = ++geracao;
  const rolagem = scrollY;
  const tela = document.createElement('section');
  tela.className = 'tela';
  try {
    await fn(tela, r.arg, r.q, () => minha === geracao);
    if (minha !== geracao) return;
    app.replaceChildren(tela);
    if (manterRolagem) scrollTo(0, rolagem); else scrollTo(0, 0);
  } catch (e) {
    if (minha !== geracao) return;
    tela.innerHTML = `<div class="vazio">${ic('alert')}<b>NÃO FOI POSSÍVEL ABRIR ESTA TELA</b>${esc(e.message)}
      <div><button class="btn primary" type="button" data-acao="tentar">${ic('refresh')}TENTAR DE NOVO</button></div></div>`;
    tela.querySelector('[data-acao=tentar]').addEventListener('click', () => recarregar());
    app.replaceChildren(tela);
  }
}

// redesenha a tela de fundo (ex.: depois de salvar o acompanhamento na gaveta)
function atualizarFundo() {
  const r = lerRota();
  if (['painel', 'ordens'].includes(r.tela)) desenharTela(r, { manterRolagem: true });
}

async function atualizarProxima() {
  try { $('#proxima-num').textContent = (await api('/api/ops/proximo')).numero; } catch { /* status já avisa */ }
}

async function recarregar() {
  baseAtual = null;
  esquecerOPs();
  await Promise.all([rotear(), atualizarProxima()]);
}

// ================================================================== lista de O.P. (cache curto, busca sem acento)
let cacheOPs = null;
async function todasOPs() {
  if (cacheOPs && Date.now() - cacheOPs.t < 20000) return cacheOPs.lista;
  const lista = await api('/api/ops');
  lista.forEach(o => { o._busca = norm([o.numero, o.cliente, o.obra, o.solicitante, o.tipo, o.ata].join(' ')); });
  cacheOPs = { t: Date.now(), lista };
  return lista;
}
const esquecerOPs = () => { cacheOPs = null; };
function filtrarTexto(lista, texto) {
  const termos = norm(texto).split(/\s+/).filter(Boolean);
  return termos.length ? lista.filter(o => termos.every(t => o._busca.includes(t))) : lista;
}

// ================================================================== busca global
const buscaInput = $('#busca-global');
const buscaRes = $('#busca-resultados');
let buscaT = null, buscaSel = -1;

function fecharBusca() {
  buscaRes.hidden = true;
  buscaRes.innerHTML = '';
  buscaSel = -1;
  buscaInput.setAttribute('aria-expanded', 'false');
  buscaInput.removeAttribute('aria-activedescendant');
}

function marcarBusca(i) {
  const itens = $$('.busca-item', buscaRes);
  if (!itens.length) return;
  buscaSel = (i + itens.length) % itens.length;
  itens.forEach((el, n) => el.setAttribute('aria-selected', String(n === buscaSel)));
  buscaInput.setAttribute('aria-activedescendant', itens[buscaSel].id);
  itens[buscaSel].scrollIntoView({ block: 'nearest' });
}

async function buscar(texto) {
  let lista;
  try { lista = filtrarTexto(await todasOPs(), texto); } catch (e) { falha(e); return; }
  if (buscaInput.value.trim() !== texto) return;
  const itens = lista.slice(0, 8).map((o, i) => `
    <a class="busca-item e-${o.estado}" id="bi-${i}" role="option" aria-selected="false" href="${linkOP(o.id)}">
      <i></i><b>${esc(o.numero)}</b>
      <span><strong>${esc(o.obra || 'SEM OBRA')}</strong><small>${esc(o.cliente)} · ${esc(o.solicitante || '—')} · ${esc(prazoTexto(o))}</small></span>
      ${pilula(o.estado)}
    </a>`).join('');
  buscaRes.innerHTML = itens || `<div class="busca-vazio">NENHUMA O.P. ENCONTRADA PARA “${esc(texto)}”.</div>`;
  if (lista.length > 8) {
    buscaRes.insertAdjacentHTML('beforeend', `<a class="busca-vazio" href="#/ordens?texto=${encodeURIComponent(texto)}">VER TODOS OS ${lista.length} RESULTADOS EM ORDENS</a>`);
  }
  buscaRes.hidden = false;
  buscaInput.setAttribute('aria-expanded', 'true');
  if (lista.length) marcarBusca(0);
}

buscaInput.setAttribute('aria-expanded', 'false');
buscaInput.addEventListener('input', () => {
  clearTimeout(buscaT);
  const t = buscaInput.value.trim();
  if (!t) { fecharBusca(); return; }
  buscaT = setTimeout(() => buscar(t), 180);
});
buscaInput.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') { e.preventDefault(); marcarBusca(buscaSel + 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); marcarBusca(buscaSel - 1); }
  else if (e.key === 'Enter') {
    e.preventDefault();
    const item = $$('.busca-item', buscaRes)[buscaSel];
    const t = buscaInput.value.trim();
    if (item) location.hash = item.getAttribute('href');
    else if (t) location.hash = '#/ordens?texto=' + encodeURIComponent(t);
    fecharBusca(); buscaInput.blur();
  } else if (e.key === 'Escape') { fecharBusca(); buscaInput.blur(); }
});
buscaInput.addEventListener('focus', () => { if (buscaInput.value.trim() && buscaRes.innerHTML) { buscaRes.hidden = false; } });
buscaRes.addEventListener('click', e => { if (e.target.closest('a')) { fecharBusca(); buscaInput.blur(); } });
document.addEventListener('pointerdown', e => { if (!e.target.closest('.busca-global')) fecharBusca(); });

// ================================================================== atalhos
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (fecharFiltroColuna()) return;
    if (!buscaRes.hidden) { fecharBusca(); buscaInput.blur(); return; }
    if (gavetaAberta() && !dlg.open) { e.preventDefault(); fecharGaveta(); return; }
  }
  if (dlg.open || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest?.('input, textarea, select, [contenteditable]')) return;
  if (e.key === '/') { e.preventDefault(); buscaInput.focus(); buscaInput.select(); }
  else if (e.key === 'n' || e.key === 'N') { location.hash = '#/nova'; }
  else if (e.key === 'r' || e.key === 'R') { recarregar(); }
});

$('#b-atualizar').addEventListener('click', e => ocupado(e.currentTarget, recarregar));

// ================================================================== pedaços comuns
function heroi({ classe = '', olho, titulo, texto = '', icone = 'chart', acoes = '' }) {
  return `<header class="heroi ${classe}">
    <div><div class="olho">${esc(olho)}</div><h1>${esc(titulo)}</h1>${texto ? `<p>${texto}</p>` : ''}</div>
    <div class="heroi-acoes">${acoes}<span class="heroi-icone">${ic(icone)}</span></div>
  </header>`;
}

const vazio = (titulo, texto = '', icone = 'search', extra = '') =>
  `<div class="vazio">${ic(icone)}<b>${esc(titulo)}</b>${esc(texto)}${extra ? `<div>${extra}</div>` : ''}</div>`;

const logoPref = (p, alt = '') => p && p.logo
  ? `<img src="/api/prefeituras/${p.id}/logo" alt="${esc(alt)}" data-icone="building" loading="lazy">`
  : ic('building');

let contouUmaVez = false;
function animarContagem(raiz) {
  if (contouUmaVez || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  contouUmaVez = true;
  $$('[data-contar]', raiz).forEach(el => {
    const fim = Number(el.dataset.contar);
    if (!fim) return;
    const t0 = performance.now();
    const passo = t => {
      const k = Math.min(1, (t - t0) / 700);
      el.textContent = Math.round(fim * (1 - Math.pow(1 - k, 3))).toLocaleString('pt-BR');
      if (k < 1) requestAnimationFrame(passo);
    };
    el.textContent = '0';
    requestAnimationFrame(passo);
  });
}

const CAMPO_ACOMP = { status_instalacao: 'INSTALAÇÃO', material_obra: 'MATERIAL NA OBRA', entrega_atualizada: 'ENTREGA', fotografico: 'FOTOGRÁFICO', obs: 'OBS' };

function descreverEvento(ev) {
  const d = ev.dados || {};
  const o = ev.op;
  const opTxt = o ? `O.P. ${o.numero}` : 'O.P.';
  const sub = o ? `${o.obra || ''} · ${o.cliente || ''}` : '';
  const mapa = {
    OP_CRIADA: ['plus', 'NO_PRAZO', `${opTxt} CRIADA`, sub],
    OP_REVISADA: ['edit', 'PROXIMA', `${opTxt} REVISADA (REV ${d.rev ?? ''})`, sub],
    OP_CANCELADA: ['x-circle', 'ATRASADA', `${opTxt} CANCELADA`, d.motivo || sub],
    OP_ACOMPANHAMENTO: ['clipboard', 'NA_OBRA', `ACOMPANHAMENTO DA ${opTxt}`,
      Object.entries(d).filter(([k]) => k !== 'op').map(([k, v]) => `${CAMPO_ACOMP[k] || k}: ${k === 'entrega_atualizada' && /^\d{4}-/.test(v) ? dataBR(v) : (v || '—')}`).join(' · ')],
    OP_PUBLICADA: [d.pdf_erro ? 'alert' : 'send', d.pdf_erro ? 'ATRASADA' : 'INSTALADA', `${opTxt} PUBLICADA`, d.pdf_erro ? 'PDF FALHOU: ' + d.pdf_erro : sub],
    SALDO_AJUSTADO: ['scale', 'SEM_DATA', `SALDO AJUSTADO · ITEM ${d.codigo ?? ''}`, d.motivo || ''],
    MODELO_ALTERADO: ['layers', 'SEM_DATA', 'MODELO ALTERADO', d.ativo === false ? 'DESATIVADO' : d.ativo === true ? 'ATIVADO' : 'CONTRATO DO SALDO'],
    IMPORTAR_LIVRO: ['download', 'SEM_DATA', 'LIVRO IMPORTADO', d.cliente || d.arquivo || ''],
    IMPORTAR_CONTROLE: ['download', 'SEM_DATA', 'CONTROLE IMPORTADO', d.ops != null ? `${d.ops} O.P. NO HISTÓRICO` : ''],
  };
  const [icone, estado, titulo, texto] = mapa[ev.acao] || ['history', 'SEM_DATA', ev.acao.replace(/_/g, ' '), ''];
  return { icone, estado, titulo, texto, href: o ? linkOP(o.id) : null };
}

function itemAtividade(ev) {
  const x = descreverEvento(ev);
  const tag = x.href ? 'a' : 'div';
  return `<${tag} class="atividade-item e-${x.estado}"${x.href ? ` href="${x.href}" style="text-decoration:none"` : ''}>
    <span class="ic">${ic(x.icone)}</span>
    <span><b>${esc(x.titulo)}</b><small>${esc(x.texto)}</small></span>
    <time datetime="${esc(ev.momento)}" title="${esc(dataHoraBR(ev.momento))}">${esc(tempoRelativo(ev.momento))}</time>
  </${tag}>`;
}

function fichaLinha(o) {
  return `<a class="ficha-linha e-${o.estado}" href="${linkOP(o.id)}" data-op="${o.id}">
    <i></i><b>${esc(o.numero)}</b>
    <span><strong>${esc(o.obra || 'SEM OBRA')}</strong><small>${esc(o.cliente)} · PRAZO ${esc(prazoTexto(o))}</small></span>
    <span class="pilula e-${o.estado}">${ic(ESTADO[o.estado].ic)}${esc(prazoDias(o))}</span>
  </a>`;
}

// ================================================================== tela: PAINEL
TELAS.painel = async (tela, arg, q, vivo) => {
  const d = await api('/api/painel');
  if (!vivo()) return;
  $('#proxima-num').textContent = d.proximo_numero;
  const agora = new Date();
  const hora = agora.getHours();
  const saudacao = hora < 12 ? 'BOM DIA' : hora < 18 ? 'BOA TARDE' : 'BOA NOITE';
  const hoje = agora.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).toUpperCase();
  const c = d.contagem;
  const ano = d.ano;
  const kpis = [
    { e: 'NO_PRAZO', rot: 'EM PRODUÇÃO', v: d.em_producao, ic: 'factory', sub: `${d.total_ano} O.P. VÁLIDAS EM ${ano}`, q: { estado: EM_PRODUCAO } },
    { e: 'ATRASADA', rot: 'ATRASADAS', v: c.ATRASADA, ic: 'alert', sub: 'PRAZO VENCIDO', q: { estado: 'ATRASADA', ordem: 'prazo' } },
    { e: 'PROXIMA', rot: 'ENTREGA EM 7 DIAS', v: d.semana, ic: 'clock', sub: `${c.PROXIMA} EM ATÉ 3 DIAS`, q: { estado: 'PROXIMA,NO_PRAZO', dias: 7, ordem: 'prazo' } },
    { e: 'SEM_DATA', rot: 'SEM DATA', v: c.SEM_DATA, ic: 'calendar-q', sub: 'PRAZO A DEFINIR', q: { estado: 'SEM_DATA' } },
    { e: 'NA_OBRA', rot: 'NA OBRA', v: c.NA_OBRA, ic: 'truck', sub: 'AGUARDANDO INSTALAÇÃO', q: { estado: 'NA_OBRA' } },
    { e: 'INSTALADA', rot: 'INSTALADAS', v: c.INSTALADA, ic: 'check', sub: `CONCLUÍDAS EM ${ano}`, q: { estado: 'INSTALADA' } },
  ];

  // O.P. por mês (uma série azul; rótulo só no mês atual e no maior)
  const meses = d.por_mes;
  const maior = Math.max(...meses.map(m => m.ops));
  const passoY = maior <= 4 ? 1 : Math.ceil(maior / 4);
  const topo = Math.max(passoY * 4, 1);
  const mesAtual = agora.getFullYear() === ano ? agora.getMonth() : -1;
  const iMaior = maior ? meses.findIndex(m => m.ops === maior) : -1;
  const grade = [0, 1, 2, 3, 4].map(k => `<i style="top:${100 - k * 25}%"></i><em style="top:${100 - k * 25}%">${num(passoY * k)}</em>`).join('');
  const colunas = meses.map((m, i) => {
    const h = (m.ops / topo) * 100;
    const rot = i === mesAtual || i === iMaior;
    return `<div class="coluna${m.ops ? '' : ' zero'}${i === mesAtual ? ' atual' : ''}" style="--h:${h}%" tabindex="0"
      data-tip-titulo="${m.mes} ${ano}" data-tip-valor="${plural(m.ops, 'O.P.', 'O.P.')}" aria-label="${m.mes}: ${m.ops} O.P.">
      <i style="height:${h}%"></i>${rot && m.ops ? `<b>${m.ops}</b>` : ''}<span>${m.mes}</span></div>`;
  }).join('');
  const tabelaMes = `<table class="sr"><caption>O.P. por mês em ${ano}</caption><tr><th>MÊS</th><th>O.P.</th></tr>
    ${meses.map(m => `<tr><td>${m.mes}</td><td>${m.ops}</td></tr>`).join('')}</table>`;

  // prefeituras com mais O.P.
  const maxPref = Math.max(1, ...d.por_prefeitura.map(p => p.ops));
  const barras = d.por_prefeitura.map(p => {
    const w = (p.ops / maxPref) * 100;
    const attrs = `data-tip-titulo="${esc(p.nome)}" data-tip-valor="${plural(p.ops, 'O.P.', 'O.P.')}"`;
    const miolo = `<span>${esc(p.nome)}</span><div class="trilho"><i style="width:${w}%"></i></div><b>${p.ops}</b>`;
    return p.outras
      ? `<div class="barra-h outras" tabindex="0" ${attrs}>${miolo}</div>`
      : `<a class="barra-h" href="${montarHash('ordens', null, { texto: p.nome, ano })}" ${attrs}>${miolo}</a>`;
  }).join('');
  const tabelaPref = `<table class="sr"><caption>Prefeituras com mais O.P. em ${ano}</caption><tr><th>PREFEITURA</th><th>O.P.</th></tr>
    ${d.por_prefeitura.map(p => `<tr><td>${esc(p.nome)}</td><td>${p.ops}</td></tr>`).join('')}</table>`;

  const alertas = d.alertas_saldo.map(a => `
    <a class="alerta-saldo" href="${montarHash('saldos', null, { p: a.prefeitura_id, c: a.contrato_id })}">
      <span class="cod">${esc(a.codigo)}</span>
      <span><strong>${esc(a.equipamento)}</strong><small>${esc(a.prefeitura)} · ATA ${esc(a.ata)} · MONTANTE ${num(a.montante)}</small></span>
      ${a.saldo === 'ACABOU' ? '<span class="badge purple">ACABOU</span>' : `<span class="badge red">${num(a.saldo)}</span>`}
    </a>`).join('');

  const listas = { proximas: d.proximas, atrasadas: d.atrasadas, sem_data: d.sem_data };
  let aba = memoria.ler('painel.entregas', 'proximas');
  if (!listas[aba]) aba = 'proximas';
  const listaEntregas = k => listas[k].length
    ? listas[k].map(fichaLinha).join('')
    : vazio(k === 'atrasadas' ? 'NENHUMA O.P. ATRASADA' : k === 'sem_data' ? 'NENHUMA O.P. SEM DATA' : 'NENHUMA ENTREGA PRÓXIMA',
      k === 'atrasadas' ? 'TUDO EM DIA.' : '', k === 'atrasadas' ? 'check' : 'calendar');
  const segEntregas = [['proximas', 'PRÓXIMAS', 'NO_PRAZO', d.proximas.length], ['atrasadas', 'ATRASADAS', 'ATRASADA', c.ATRASADA],
    ['sem_data', 'SEM DATA', 'SEM_DATA', c.SEM_DATA]]
    .map(([k, r, e, n]) => `<button type="button" class="e-${e}" data-entregas="${k}" aria-pressed="${k === aba}"><span class="ponto"></span>${r}<span class="conta">${n}</span></button>`).join('');

  tela.innerHTML = `
    ${heroi({
      olho: `PAINEL DA PRODUÇÃO · ${ano}`, titulo: `${saudacao}, EQUIPE`, icone: 'chart',
      texto: `${esc(hoje)} · ${d.em_producao} O.P. EM PRODUÇÃO, ${c.ATRASADA} ATRASADA${c.ATRASADA === 1 ? '' : 'S'}.`,
      acoes: `<div class="numero-heroi"><small>PRÓXIMA O.P.</small>${esc(d.proximo_numero)}</div>
        <a class="btn branco large" href="#/nova">${ic('plus')}NOVA O.P.</a>
        <a class="btn claro large" href="#/ordens">${ic('clipboard')}VER ORDENS</a>`,
    })}
    <div class="kpis">
      ${kpis.map(k => `<a class="kpi e-${k.e}" href="${montarHash('ordens', null, { ...k.q, ano })}">
        <div class="kpi-topo"><span>${k.rot}</span>${ic(k.ic)}</div>
        <strong data-contar="${k.v}">${num(k.v)}</strong><small>${esc(k.sub)}</small></a>`).join('')}
    </div>
    <div class="painel-grade">
      <section class="card" aria-labelledby="t-entregas">
        <div class="card-head">
          <div><div class="kicker">PRODUÇÃO</div><h2 id="t-entregas">ENTREGAS</h2><p>O.P. ORDENADAS PELO PRAZO EFETIVO (A ENTREGA ATUALIZADA SUBSTITUI O PRAZO).</p></div>
          <a class="btn ghost small" href="${montarHash('ordens', null, { estado: EM_PRODUCAO, ordem: 'prazo', ano })}">VER TODAS</a>
        </div>
        <div class="segmentado" role="group" aria-label="Entregas" style="margin-bottom:12px">${segEntregas}</div>
        <div class="lista-fichas" id="p-entregas">${listaEntregas(aba)}</div>
      </section>
      <div class="pilha">
      <section class="card" aria-labelledby="t-mes">
        <div class="card-head"><div><div class="kicker">VOLUME</div><h2 id="t-mes">O.P. POR MÊS</h2><p>O.P. VÁLIDAS SOLICITADAS EM ${ano}.</p></div>
          <span class="badge blue">${plural(d.total_ano, 'O.P.', 'O.P.')}</span></div>
        <div class="grafico colunas" role="img" aria-label="Gráfico de O.P. por mês">
          <div class="grade-y" aria-hidden="true">${grade}</div><div class="barras">${colunas}</div>
        </div>${tabelaMes}
      </section>
      <section class="card" aria-labelledby="t-pref">
        <div class="card-head"><div><div class="kicker">CLIENTES</div><h2 id="t-pref">PREFEITURAS COM MAIS O.P.</h2><p>CLIQUE PARA VER AS ORDENS DA PREFEITURA.</p></div></div>
        ${barras ? `<div class="barras-h grafico" aria-hidden="true">${barras}</div>${tabelaPref}` : vazio('NENHUMA O.P. EM ' + ano)}
      </section>
      </div>
    </div>
    <div class="painel-grade">
      <section class="card" aria-labelledby="t-ativ">
      <div class="card-head"><div><div class="kicker">HISTÓRICO</div><h2 id="t-ativ">ATIVIDADE RECENTE</h2><p>ÚLTIMAS AÇÕES REGISTRADAS NO SISTEMA.</p></div>
        <a class="btn ghost small" href="#/config">VER TUDO</a></div>
      <div class="atividade">${d.eventos.map(itemAtividade).join('') || vazio('SEM ATIVIDADE AINDA', '', 'history')}</div>
    </section>
      <section class="card" aria-labelledby="t-alertas">
        <div class="card-head"><div><div class="kicker">CONTRATOS</div><h2 id="t-alertas">ALERTAS DE SALDO</h2><p>ITENS COM SALDO NEGATIVO OU ENCERRADO.</p></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
            <span class="badge red">${plural(d.saldo_negativos, 'NEGATIVO', 'NEGATIVOS')}</span>
            <span class="badge purple">${plural(d.saldo_encerrados, 'ENCERRADO', 'ENCERRADOS')}</span></div></div>
        ${alertas ? `<div>${alertas}</div>` : vazio('NENHUM ALERTA DE SALDO', 'TODOS OS CONTRATOS COM SALDO.', 'shield')}
      </section>
    </div>`;

  tela.addEventListener('click', e => {
    const b = e.target.closest('[data-entregas]');
    if (!b) return;
    aba = b.dataset.entregas;
    memoria.gravar('painel.entregas', aba);
    $$('[data-entregas]', tela).forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('#p-entregas', tela).innerHTML = listaEntregas(aba);
  });
  requestAnimationFrame(() => animarContagem(tela));
};

// ================================================================== tela: NOVA O.P. (3 passos) e EDITAR
const RASCUNHO = 'op.rascunho';
const baseCodigo = c => { c = String(c ?? '').trim().replace(',', '.'); return c.startsWith('0.') ? c : c.split('.')[0]; };
const ehBonus = c => String(c ?? '').trim().startsWith('0.');

function detectarMaterial(nomes, tipo) {
  if (norm(tipo).includes('INOX')) return 'CARBONO+INOX';
  let inox = false, carbono = false;
  nomes.forEach(n => { if (!String(n || '').trim()) return; if (norm(n).includes('INOX')) inox = true; else carbono = true; });
  return inox && carbono ? 'CARBONO+INOX' : inox ? 'INOX' : 'CARBONO';
}

function maiusculas(el) {
  const p = el.selectionStart;
  const v = el.value.toUpperCase();
  if (v !== el.value) { el.value = v; try { el.setSelectionRange(p, p); } catch { /* campo sem cursor */ } }
}

TELAS.nova = (tela, arg, q, vivo) => telaNova(tela, null, q, vivo);
TELAS.editar = (tela, arg, q, vivo) => telaNova(tela, Number(arg), q, vivo);

async function telaNova(tela, editId, q, vivo) {
  const est = {
    editId, origem: null, prefs: [], pref: null, modelos: [], modelo: null, solicitantes: [],
    cab: { obra: '', solicitante: '', tipo: '', modoPrazo: 'data', prazo: '', motivo: '' },
    qtd: {}, filtro: '', soCom: false, proximo: '', restaurado: null,
  };
  const [prefs, prox] = await Promise.all([api('/api/prefeituras'), api('/api/ops/proximo')]);
  est.prefs = prefs;
  est.proximo = prox.numero;
  let prefId = null, modeloId = null;
  const idOrigem = editId || (q.de ? Number(q.de) : null);
  if (idOrigem) {
    const o = await api('/api/ops/' + idOrigem);
    if (o.origem !== 'SISTEMA' || !o.modelo_id) throw new Error('O.P. DO HISTÓRICO LEGADO: SÓ O ACOMPANHAMENTO PODE SER ALTERADO.');
    if (editId && o.situacao !== 'ATIVA') throw new Error('O.P. CANCELADA NÃO PODE SER ALTERADA.');
    est.origem = o;
    est.cab = { obra: o.obra || '', solicitante: o.solicitante || '', tipo: o.tipo || '', modoPrazo: o.prazo_data ? 'data' : 'definir', prazo: o.prazo_data || '', motivo: '' };
    o.itens.forEach(i => { est.qtd[i.linha] = { q: String(i.quantidade).replace('.', ','), inaug: i.inauguracao || '', obs: i.observacao || '' }; });
    prefId = o.prefeitura_id; modeloId = o.modelo_id;
  } else {
    const r = memoria.ler(RASCUNHO);
    if (r && r.pref_id) {
      prefId = r.pref_id; modeloId = r.modelo_id || null;
      est.cab = { ...est.cab, ...(r.cab || {}) };
      est.qtd = r.qtd || {};
      est.restaurado = r.salvo_em || '';
    }
  }
  est.pref = prefs.find(p => p.id === prefId) || null;
  if (est.pref) await carregarPref(est);
  if (est.pref && modeloId) {
    try { est.modelo = await api(`/api/modelos/${modeloId}` + (editId ? `?excluir_op=${editId}` : '')); }
    catch { est.modelo = null; est.qtd = {}; }
  }
  if (!vivo()) return;

  const titulo = editId ? `O.P. ${est.origem.numero} · REV ${est.origem.rev + 1}` : est.origem ? `CÓPIA DA O.P. ${est.origem.numero}` : 'NOVA O.P.';
  tela.innerHTML = `
    ${heroi({
      classe: 'nova', olho: editId ? 'EDITAR ORDEM DE PRODUÇÃO' : 'GERAR ORDEM DE PRODUÇÃO', titulo, icone: editId ? 'edit' : 'plus',
      texto: editId ? 'AO SALVAR, A O.P. GANHA UMA NOVA REVISÃO E OS ARQUIVOS SÃO REPUBLICADOS.'
        : 'ESCOLHA A PREFEITURA E O MODELO, PREENCHA OS DADOS E AS QUANTIDADES. O SALDO DO CONTRATO É CONFERIDO NA HORA.',
      acoes: `<div class="numero-heroi"><small>${editId ? 'EDITANDO' : 'NÚMERO DA O.P.'}</small>${esc(editId ? est.origem.numero : est.proximo)}</div>`,
    })}
    <div id="n-rascunho"></div>
    <section class="passo" id="n-p1"><header><h2><span class="n">1</span>PREFEITURA E MODELO</h2><p>DE ONDE SAEM O LOGO, OS EQUIPAMENTOS E O CONTRATO.</p></header><div class="passo-corpo" id="n-p1c"></div></section>
    <section class="passo" id="n-p2" hidden><header><h2><span class="n">2</span>DADOS DA O.P.</h2><p>OBRA, SOLICITANTE, PRAZO E TIPO.</p></header><div class="passo-corpo" id="n-p2c"></div></section>
    <section class="passo" id="n-p3" hidden><header><h2><span class="n">3</span>EQUIPAMENTOS</h2><p id="n-p3-sub"></p></header><div class="passo-corpo" id="n-p3c"></div></section>
    <div class="resumo-op" id="n-resumo"></div>`;

  // ---------------------------------------------------------------- desenho dos passos
  function desenharRascunho() {
    $('#n-rascunho', tela).innerHTML = est.restaurado != null && !editId
      ? `<div class="aviso-rascunho">${ic('history')}<span style="flex:1">RASCUNHO RESTAURADO${est.restaurado ? ` (SALVO ${esc(tempoRelativo(est.restaurado))})` : ''}. CONTINUE DE ONDE PAROU.</span>
        <button class="btn ghost small" type="button" data-acao="descartar">${ic('close')}DESCARTAR</button></div>` : '';
  }

  function desenharP1() {
    const c = $('#n-p1c', tela);
    $('#n-p1', tela).classList.toggle('feito', !!est.modelo);
    if (!est.pref) {
      c.innerHTML = `<label class="busca">${ic('search')}<input id="n-busca-pref" type="search" placeholder="Buscar prefeitura" aria-label="Buscar prefeitura" autocomplete="off"></label>
        <div class="prefs">${est.prefs.map(p => `<button type="button" class="pref" data-pref="${p.id}" aria-pressed="false" data-busca="${esc(norm(p.nome))}">
          <span class="logo">${logoPref(p)}</span><b>${esc(p.nome)}</b><small>${plural(p.modelos, 'MODELO', 'MODELOS')} · ${plural(p.ops_ano, 'O.P.', 'O.P.')} EM ${new Date().getFullYear()}</small></button>`).join('')
          || vazio('NENHUMA PREFEITURA IMPORTADA', 'USE O IMPORTAR_LEGADO.CMD PARA TRAZER OS LIVROS DAS PREFEITURAS.', 'building')}</div>`;
      return;
    }
    const p = est.pref;
    const chips = est.modelos.map(m => `<button type="button" class="modelo-chip" data-modelo="${m.id}" aria-pressed="${est.modelo?.id === m.id}"${editId && est.modelo?.id !== m.id ? ' disabled hidden' : ''}>
      <b>${esc(m.aba)}</b><small>${esc(m.titulo || 'SEM ATA')} · ${plural(m.equipamentos, 'EQUIP.', 'EQUIP.')}${m.contrato_id ? '' : ' · SEM CONTRATO'}</small></button>`).join('');
    const faltaModelo = est.modelo && !est.modelos.some(m => m.id === est.modelo.id)
      ? `<button type="button" class="modelo-chip" aria-pressed="true" disabled><b>${esc(est.modelo.aba)}</b><small>MODELO DESATIVADO</small></button>` : '';
    c.innerHTML = `<div class="pref-escolhida">
        <span class="logo">${logoPref(p, p.nome)}</span>
        <div><h3>${esc(p.nome)}</h3><p>${plural(est.modelos.length, 'MODELO ATIVO', 'MODELOS ATIVOS')} · ${plural(p.contratos, 'CONTRATO', 'CONTRATOS')} · ${plural(p.ops, 'O.P.', 'O.P.')} NO TOTAL</p></div>
        ${editId ? '' : `<button type="button" class="btn ghost small" data-acao="trocar">${ic('refresh')}TROCAR PREFEITURA</button>`}
      </div>
      <div class="modelos-chips" role="group" aria-label="Modelo">${chips}${faltaModelo}</div>
      ${!est.modelos.length && !est.modelo ? vazio('PREFEITURA SEM MODELO ATIVO', 'ATIVE UM MODELO NA TELA MODELOS.', 'layers') : ''}`;
  }

  function desenharP2() {
    const sec = $('#n-p2', tela);
    sec.hidden = !est.modelo;
    if (!est.modelo) return;
    const cab = est.cab;
    $('#n-p2c', tela).innerHTML = `<div class="campos">
      <label class="campo largo">OBRA<input id="n-obra" data-cab="obra" value="${esc(cab.obra)}" maxlength="140" autocomplete="off" placeholder="EX.: PRAÇA DA MATRIZ"></label>
      <label class="campo">SOLICITANTE<input id="n-solic" data-cab="solicitante" list="n-solics" value="${esc(cab.solicitante)}" maxlength="80" autocomplete="off" placeholder="QUEM PEDIU"></label>
      <div class="prazo-campo"><span class="rotulo-campo" id="n-prazo-rot">PRAZO</span>
        <div class="prazo-linha">
          <div class="segmentado" role="group" aria-labelledby="n-prazo-rot">
            <button type="button" data-prazo-modo="data" aria-pressed="${cab.modoPrazo === 'data'}">${ic('calendar')}DATA</button>
            <button type="button" data-prazo-modo="definir" aria-pressed="${cab.modoPrazo === 'definir'}">${ic('calendar-q')}DEFINIR</button>
          </div>
          <input id="n-prazo" type="date" value="${esc(cab.prazo)}" aria-labelledby="n-prazo-rot"${cab.modoPrazo === 'definir' ? ' disabled' : ''}>
        </div></div>
      <label class="campo">TIPO<input id="n-tipo" data-cab="tipo" list="n-tipos" value="${esc(cab.tipo || est.modelo.tipo_padrao || '')}" maxlength="30" autocomplete="off" placeholder="MOB, ABRIGO, PLACA"></label>
      ${editId ? `<label class="campo largo">MOTIVO DA REVISÃO<input id="n-motivo" data-cab="motivo" value="${esc(cab.motivo)}" maxlength="140" autocomplete="off" placeholder="EX.: INCLUÍDO 1 BALANÇO"></label>` : ''}
      <datalist id="n-solics">${est.solicitantes.map(s => `<option value="${esc(s)}">`).join('')}</datalist>
      <datalist id="n-tipos"><option value="MOB"><option value="ABRIGO"><option value="PLACA"></datalist>
    </div>`;
    if (!cab.tipo) cab.tipo = est.modelo.tipo_padrao || '';
    marcarP2();
  }

  function marcarP2() {
    const c = est.cab;
    $('#n-p2', tela).classList.toggle('feito', !!(c.obra.trim() && c.solicitante.trim() && (c.modoPrazo === 'definir' || c.prazo)));
  }

  function desenharP3() {
    const sec = $('#n-p3', tela);
    sec.hidden = !est.modelo;
    if (!est.modelo) return;
    const m = est.modelo;
    $('#n-p3-sub', tela).textContent = `${m.linhas.length} EQUIPAMENTOS NO MODELO ${m.aba}${m.contrato_id ? '' : ' · SEM CONTRATO DE SALDO'}`;
    const cartoes = m.linhas.map(l => {
      const v = est.qtd[l.linha] || { q: '', inaug: '', obs: '' };
      const nome = esc(l.equipamento);
      return `<article class="equip" data-linha="${l.linha}" data-busca="${esc(norm(l.codigo + ' ' + l.equipamento))}">
        <div class="equip-foto"${l.foto ? ` data-foto="${l.linha}" title="AMPLIAR FOTO"` : ''}>
          ${l.foto ? `<img src="/api/modelos/${m.id}/foto/${l.linha}" alt="" loading="lazy">` : ic('image')}
          <span class="cod${ehBonus(l.codigo) ? ' bonus' : ''}">${esc(l.codigo || '—')}</span><span class="equip-qtd-selo" aria-hidden="true"></span>
        </div>
        <div class="equip-corpo">
          <h3 title="${nome}">${nome}</h3>
          <div class="equip-saldo" data-saldo></div>
          <div class="contador">
            <button type="button" data-passo="-1" aria-label="DIMINUIR ${nome}">${ic('minus')}</button>
            <input data-campo="q" inputmode="decimal" autocomplete="off" value="${esc(v.q)}" placeholder="0" aria-label="QUANTIDADE DE ${nome}">
            <button type="button" data-passo="1" aria-label="AUMENTAR ${nome}">${ic('plus')}</button>
          </div>
          <div class="equip-extra"><div>
            <label class="campo">INAUGURAÇÃO<input data-campo="inaug" value="${esc(v.inaug)}" maxlength="40" autocomplete="off" placeholder="DATA OU TEXTO"></label>
            <label class="campo">OBSERVAÇÃO<input data-campo="obs" value="${esc(v.obs)}" maxlength="200" autocomplete="off"></label>
          </div></div>
        </div>
      </article>`;
    }).join('');
    $('#n-p3c', tela).innerHTML = `
      ${m.contrato_id ? '' : `<div class="nota-legado">${ic('alert')}<span>ESTE MODELO NÃO TEM CONTRATO DE SALDO VINCULADO: AS QUANTIDADES NÃO SÃO CONFERIDAS. VINCULE O CONTRATO NA TELA MODELOS.</span></div>`}
      <div class="equip-barra">
        <label class="busca">${ic('search')}<input id="n-busca-eq" type="search" placeholder="Buscar equipamento ou código" aria-label="Buscar equipamento" autocomplete="off" value="${esc(est.filtro)}"></label>
        <div class="segmentado" role="group" aria-label="Mostrar">
          <button type="button" data-so="0" aria-pressed="${!est.soCom}">TODOS<span class="conta" id="n-conta-todos">${m.linhas.length}</span></button>
          <button type="button" data-so="1" aria-pressed="${est.soCom}">COM QUANTIDADE<span class="conta" id="n-conta-com">0</span></button>
        </div>
        ${m.contrato_id ? `<div class="legenda" aria-label="Legenda do saldo">
          <span><i style="--cor:var(--serie-real)"></i>REALIZADO</span><span><i style="--cor:var(--serie-prev)"></i>PREVISÃO</span>
          <span><i class="esta-amostra"></i>ESTA O.P.</span><span><i style="--cor:var(--red)" class="exc-amostra"></i>EXCEDENTE</span>
          <span><i class="trilho-amostra"></i>DISPONÍVEL</span></div>` : ''}
      </div>
      <div class="equips">${cartoes || vazio('MODELO SEM EQUIPAMENTOS', '', 'box')}</div>`;
    atualizarEquips();
  }

  // saldo de cada linha: 2 e 2.1 consomem o mesmo item 2; 0.x não é conferido
  function contasSaldo() {
    const porBase = {};
    est.modelo.linhas.forEach(l => {
      const b = baseCodigo(l.codigo);
      porBase[b] = (porBase[b] || 0) + lerNumero(est.qtd[l.linha]?.q);
    });
    return porBase;
  }

  function saldoLinha(l, nesta) {
    if (ehBonus(l.codigo)) return { tipo: 'bonus' };
    if (!est.modelo.contrato_id) return { tipo: 'semcontrato' };
    if (l.montante == null) return { tipo: 'fora' };
    const disp = l.montante > 0 ? l.montante - l.consumido : 0;
    return { tipo: 'conta', disp, depois: disp - nesta, nesta };
  }

  function medidor(l, nesta) {
    const M = Math.max(0, l.montante || 0), R = l.realizado || 0, P = l.previsao || 0;
    const total = R + P + nesta;
    const escala = Math.max(M, total) || 1;
    const r1 = Math.min(R, M), p1 = Math.min(P, M - r1), e1 = Math.min(nesta, M - r1 - p1), exc = total - r1 - p1 - e1;
    const w = v => `${(v / escala) * 100}%`;
    return `<div class="medidor mini" aria-hidden="true">${r1 ? `<i class="real" style="width:${w(r1)}"></i>` : ''}${p1 ? `<i class="prev" style="width:${w(p1)}"></i>` : ''}${e1 ? `<i class="esta" style="width:${w(e1)}"></i>` : ''}${exc > 0 ? `<i class="exc" style="width:${w(exc)}"></i>` : ''}</div>`;
  }

  const clsSaldo = v => v < 0 ? 'neg' : v === 0 ? 'acabou' : '';

  function atualizarEquips() {
    if (!est.modelo) return;
    const porBase = contasSaldo();
    const termos = norm(est.filtro).split(/\s+/).filter(Boolean);
    let com = 0;
    est.modelo.linhas.forEach(l => {
      const card = $(`.equip[data-linha="${l.linha}"]`, tela);
      if (!card) return;
      const q = lerNumero(est.qtd[l.linha]?.q);
      const nesta = porBase[baseCodigo(l.codigo)] || 0;
      const s = saldoLinha(l, nesta);
      if (q > 0) com++;
      card.classList.toggle('tem', q > 0);
      card.classList.toggle('estoura', s.tipo === 'conta' && nesta > 0 && s.depois < 0);
      $('.equip-qtd-selo', card).textContent = q > 0 ? num(q) : '';
      $('.equip-extra', card).inert = !(q > 0);
      let html;
      if (s.tipo === 'bonus') html = `<div class="linha"><span>BONIFICADO</span><b class="acabou">SEM CONFERÊNCIA</b></div>`;
      else if (s.tipo === 'semcontrato') html = `<div class="linha"><span>SALDO</span><b>SEM CONTRATO</b></div>`;
      else if (s.tipo === 'fora') html = `<div class="linha"><span>CÓDIGO</span><b class="neg">FORA DO CONTRATO</b></div>`;
      else {
        html = medidor(l, nesta) + `<div class="linha"><span>SALDO <b class="${clsSaldo(s.disp)}">${s.disp === 0 ? 'ACABOU' : num(s.disp)}</b></span>` +
          (nesta > 0 ? `<span>→ DEPOIS <b class="${clsSaldo(s.depois)}">${s.depois === 0 ? 'ACABA' : num(s.depois)}</b></span>` : `<span>MONTANTE <b>${num(l.montante)}</b></span>`) + '</div>';
      }
      $('[data-saldo]', card).innerHTML = html;
      const visivel = (!est.soCom || q > 0) && termos.every(t => card.dataset.busca.includes(t));
      card.hidden = !visivel;
    });
    const conta = $('#n-conta-com', tela);
    if (conta) conta.textContent = com;
    $('#n-p3', tela).classList.toggle('feito', com > 0);
    desenharResumo();
  }

  function situacaoSaldo() {
    const m = est.modelo;
    if (!m) return '';
    if (!m.contrato_id) return '<span class="badge gray">SEM CONTRATO</span>';
    const porBase = contasSaldo();
    let neg = 0, acaba = 0, fora = 0;
    const vistos = new Set();
    m.linhas.forEach(l => {
      const b = baseCodigo(l.codigo);
      if (vistos.has(b) || !(porBase[b] > 0)) return;
      vistos.add(b);
      const s = saldoLinha(l, porBase[b]);
      if (s.tipo === 'fora') fora++;
      else if (s.tipo === 'conta') { if (s.depois < 0) neg++; else if (s.depois === 0) acaba++; }
    });
    if (fora) return `<span class="badge red">${ic('alert')}${plural(fora, 'CÓDIGO FORA DO CONTRATO', 'CÓDIGOS FORA DO CONTRATO')}</span>`;
    if (neg) return `<span class="badge red">${ic('alert')}SALDO NEGATIVO EM ${plural(neg, 'ITEM', 'ITENS')}</span>`;
    if (acaba) return `<span class="badge purple">${ic('scale')}ENCERRA O SALDO DE ${plural(acaba, 'ITEM', 'ITENS')}</span>`;
    return `<span class="badge green">${ic('shield')}SALDO OK</span>`;
  }

  function desenharResumo() {
    const m = est.modelo;
    const linhas = m ? m.linhas.filter(l => lerNumero(est.qtd[l.linha]?.q) > 0) : [];
    const pecas = linhas.reduce((t, l) => t + lerNumero(est.qtd[l.linha].q), 0);
    const material = linhas.length ? detectarMaterial(linhas.map(l => l.equipamento), est.cab.tipo) : '';
    const numero = editId ? est.origem.numero : est.proximo;
    $('#n-resumo', tela).innerHTML = `
      <div class="resumo-ficha">
        <span><small>${editId ? `REV ${est.origem.rev + 1}` : 'PRÓXIMA O.P.'}</small><b>${esc(numero)}</b></span>
        <span><small>${esc(est.pref?.nome || 'ESCOLHA A PREFEITURA')}</small><strong>${esc(m ? `${m.aba}${m.titulo ? ' · ' + m.titulo : ''}` : 'E O MODELO')}</strong></span>
      </div>
      <div class="resumo-chips">
        ${m ? `<span class="badge blue">${ic('box')}${plural(linhas.length, 'EQUIPAMENTO', 'EQUIPAMENTOS')}</span>
        <span class="badge slate">${plural(pecas, 'PEÇA', 'PEÇAS')}</span>
        ${material ? `<span class="badge teal">${ic('layers')}${esc(material)}</span>` : ''}
        ${linhas.length ? situacaoSaldo() : ''}` : '<span class="badge gray">PASSO 1: ESCOLHA A PREFEITURA E O MODELO</span>'}
      </div>
      <div class="resumo-acoes">
        <button class="btn ghost" type="button" data-acao="limpar">${ic(editId ? 'history' : 'close')}${editId ? 'DESFAZER' : 'LIMPAR'}</button>
        <button class="btn success large" type="button" data-acao="gerar"${m ? '' : ' disabled'}>${ic(editId ? 'save' : 'check')}${editId ? `SALVAR REV ${est.origem.rev + 1}` : 'GERAR O.P.'}</button>
      </div>`;
  }

  // ---------------------------------------------------------------- rascunho
  let rascunhoT = null;
  function salvarRascunho() {
    if (editId) return;
    clearTimeout(rascunhoT);
    rascunhoT = setTimeout(() => {
      if (!est.pref) { memoria.apagar(RASCUNHO); return; }
      memoria.gravar(RASCUNHO, { pref_id: est.pref.id, modelo_id: est.modelo?.id || null, cab: est.cab, qtd: est.qtd, salvo_em: new Date().toISOString() });
    }, 350);
  }

  const temQuantidade = () => Object.values(est.qtd).some(v => lerNumero(v.q) > 0);

  // ---------------------------------------------------------------- ações
  async function escolherPref(id) {
    est.pref = est.prefs.find(p => p.id === id);
    est.modelo = null; est.qtd = {};
    await carregarPref(est);
    if (est.modelos.length === 1) await escolherModelo(est.modelos[0].id, true);
    else { desenharTudo(); salvarRascunho(); }
  }

  async function escolherModelo(id, semPergunta = false) {
    if (est.modelo?.id === id) return;
    if (!semPergunta && temQuantidade()) {
      const ok = await dialogo({ titulo: 'TROCAR O MODELO?', sub: 'AS QUANTIDADES JÁ PREENCHIDAS SERÃO APAGADAS.', rotulo: 'TROCAR MODELO', perigo: true });
      if (!ok) return;
    }
    est.modelo = await api(`/api/modelos/${id}`);
    est.qtd = {};
    est.cab.tipo = est.cab.tipo || est.modelo.tipo_padrao || '';
    desenharTudo();
    salvarRascunho();
    $('#n-p2', tela).scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function marcarErro(el, msg) {
    aviso(msg, 'erro');
    if (!el) return;
    el.classList.remove('erro'); void el.offsetWidth; el.classList.add('erro');
    el.focus();
    el.addEventListener('input', () => el.classList.remove('erro'), { once: true });
  }

  async function gerar(botao, confirmar = false) {
    const m = est.modelo, c = est.cab;
    if (!m) return marcarErro(null, 'ESCOLHA A PREFEITURA E O MODELO.');
    if (!c.obra.trim()) return marcarErro($('#n-obra', tela), 'INFORME A OBRA.');
    if (!c.solicitante.trim()) return marcarErro($('#n-solic', tela), 'INFORME O SOLICITANTE.');
    if (c.modoPrazo === 'data' && !c.prazo) return marcarErro($('#n-prazo', tela), 'INFORME A DATA DO PRAZO OU ESCOLHA "DEFINIR".');
    const itens = m.linhas.filter(l => lerNumero(est.qtd[l.linha]?.q) > 0).map(l => ({
      linha: l.linha, quantidade: lerNumero(est.qtd[l.linha].q), inauguracao: est.qtd[l.linha].inaug || '', observacao: est.qtd[l.linha].obs || '',
    }));
    if (!itens.length) return marcarErro($('.equip input[data-campo=q]', tela), 'A O.P. PRECISA DE PELO MENOS 1 EQUIPAMENTO COM QUANTIDADE.');
    const corpo = {
      modelo_id: m.id, obra: c.obra, solicitante: c.solicitante, tipo: c.tipo, prazo: c.modoPrazo === 'data' ? c.prazo : 'DEFINIR',
      itens, motivo: c.motivo, confirmar_negativo: confirmar,
    };
    let r;
    try {
      r = await ocupado(botao, () => api(editId ? `/api/ops/${editId}` : '/api/ops', { metodo: editId ? 'PUT' : 'POST', corpo }));
    } catch (e) { falha(e); return; }
    if (r.precisa_confirmacao) {
      if (await dialogoNegativo(r.simulacao)) return gerar(botao, true);
      return;
    }
    if (!editId) memoria.apagar(RASCUNHO);
    clearTimeout(rascunhoT);
    esquecerOPs();
    atualizarProxima();
    aviso(editId ? `O.P. ${r.op.numero} SALVA NA REV ${r.op.rev}.` : `O.P. ${r.op.numero} GERADA.`, 'ok');
    if (r.publicacao?.pdf_erro) setTimeout(() => aviso('XLSX PUBLICADO, MAS O PDF FALHOU: ' + r.publicacao.pdf_erro, 'erro'), 1600);
    location.hash = `#/ordens?op=${r.op_id}`;
  }

  async function limpar() {
    if (editId) { baseAtual = null; rotear(); return; }
    const ok = await dialogo({ titulo: 'LIMPAR A O.P.?', sub: 'APAGA OS DADOS, AS QUANTIDADES E O RASCUNHO. A PREFEITURA E O MODELO CONTINUAM ESCOLHIDOS.', rotulo: 'LIMPAR', perigo: true });
    if (!ok) return;
    est.cab = { obra: '', solicitante: '', tipo: est.modelo?.tipo_padrao || '', modoPrazo: 'data', prazo: '', motivo: '' };
    est.qtd = {}; est.restaurado = null;
    memoria.apagar(RASCUNHO);
    desenharTudo();
    salvarRascunho();
  }

  function desenharTudo() {
    desenharRascunho(); desenharP1(); desenharP2(); desenharP3();
    if (!est.modelo) desenharResumo();
  }

  // ---------------------------------------------------------------- eventos
  tela.addEventListener('click', async e => {
    const alvo = e.target.closest('button, [data-foto]');
    if (!alvo || alvo.disabled) return;
    try {
      if (alvo.dataset.pref) await escolherPref(Number(alvo.dataset.pref));
      else if (alvo.dataset.modelo) await escolherModelo(Number(alvo.dataset.modelo));
      else if (alvo.dataset.acao === 'trocar') {
        if (temQuantidade() && !await dialogo({ titulo: 'TROCAR A PREFEITURA?', sub: 'O MODELO E AS QUANTIDADES SERÃO APAGADOS.', rotulo: 'TROCAR', perigo: true })) return;
        est.pref = null; est.modelo = null; est.qtd = {};
        desenharTudo(); salvarRascunho();
        $('#n-busca-pref', tela)?.focus();
      } else if (alvo.dataset.prazoModo) {
        est.cab.modoPrazo = alvo.dataset.prazoModo;
        $$('[data-prazo-modo]', tela).forEach(b => b.setAttribute('aria-pressed', String(b === alvo)));
        const inp = $('#n-prazo', tela);
        inp.disabled = est.cab.modoPrazo === 'definir';
        if (!inp.disabled) inp.focus();
        marcarP2(); salvarRascunho();
      } else if (alvo.dataset.passo) {
        const card = alvo.closest('.equip');
        const linha = Number(card.dataset.linha);
        const v = est.qtd[linha] || (est.qtd[linha] = { q: '', inaug: '', obs: '' });
        const novo = Math.max(0, Math.floor(lerNumero(v.q)) + Number(alvo.dataset.passo));
        v.q = novo ? String(novo) : '';
        $('input[data-campo=q]', card).value = v.q;
        atualizarEquips(); salvarRascunho();
      } else if (alvo.dataset.foto) {
        const l = est.modelo.linhas.find(x => x.linha === Number(alvo.dataset.foto));
        verFoto(`/api/modelos/${est.modelo.id}/foto/${l.linha}`, `${l.codigo} · ${l.equipamento}`);
      } else if (alvo.dataset.so) {
        est.soCom = alvo.dataset.so === '1';
        $$('[data-so]', tela).forEach(b => b.setAttribute('aria-pressed', String(b === alvo)));
        atualizarEquips();
      } else if (alvo.dataset.acao === 'descartar') {
        memoria.apagar(RASCUNHO);
        est.pref = null; est.modelo = null; est.qtd = {}; est.restaurado = null;
        est.cab = { obra: '', solicitante: '', tipo: '', modoPrazo: 'data', prazo: '', motivo: '' };
        desenharTudo();
        aviso('RASCUNHO DESCARTADO.', 'ok');
      } else if (alvo.dataset.acao === 'limpar') await limpar();
      else if (alvo.dataset.acao === 'gerar') await gerar(alvo);
    } catch (erro) { falha(erro); }
  });

  tela.addEventListener('input', e => {
    const el = e.target;
    if (el.id === 'n-busca-pref') {
      const t = norm(el.value);
      $$('.pref', tela).forEach(b => { b.hidden = !b.dataset.busca.includes(t); });
    } else if (el.dataset.cab) {
      maiusculas(el);
      est.cab[el.dataset.cab] = el.value;
      marcarP2();
      if (el.dataset.cab === 'tipo') desenharResumo();
      salvarRascunho();
    } else if (el.id === 'n-busca-eq') {
      est.filtro = el.value; atualizarEquips();
    } else if (el.dataset.campo) {
      const linha = Number(el.closest('.equip').dataset.linha);
      const v = est.qtd[linha] || (est.qtd[linha] = { q: '', inaug: '', obs: '' });
      if (el.dataset.campo === 'q') { el.value = el.value.replace(/[^\d,.]/g, ''); v.q = el.value; atualizarEquips(); }
      else { if (el.dataset.campo === 'inaug') maiusculas(el); v[el.dataset.campo] = el.value; }
      salvarRascunho();
    }
  });
  tela.addEventListener('change', e => {
    if (e.target.id === 'n-prazo') { est.cab.prazo = e.target.value; marcarP2(); salvarRascunho(); }
  });
  tela.addEventListener('keydown', e => {
    if (e.target.dataset?.campo === 'q' && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault();
      e.target.closest('.contador').querySelector(`[data-passo="${e.key === 'ArrowUp' ? 1 : -1}"]`).click();
    }
  });

  desenharTudo();
}

async function carregarPref(est) {
  const [modelos, ops] = await Promise.all([api('/api/modelos?prefeitura_id=' + est.pref.id), todasOPs()]);
  est.modelos = modelos;
  est.solicitantes = [...new Set(ops.filter(o => o.prefeitura_id === est.pref.id && o.solicitante).map(o => o.solicitante))].sort();
}

function dialogoNegativo(sim) {
  const fmt = v => typeof v === 'number' ? num(v) : esc(String(v).split(' ')[0]);
  const linhas = [...sim.negativos.map(a => [a, true]), ...sim.encerrados.map(a => [a, false])];
  return dialogo({
    titulo: 'SALDO NEGATIVO NO CONTRATO',
    sub: 'ESTA O.P. CONSOME MAIS DO QUE O SALDO DISPONÍVEL. CONFIRA ANTES DE CONTINUAR.',
    corpo: `<table class="tabela-mini"><thead><tr><th>CÓD.</th><th>EQUIPAMENTO</th><th class="num">ANTES</th><th class="num">ESTA O.P.</th><th class="num">DEPOIS</th></tr></thead>
      <tbody>${linhas.map(([a, neg]) => `<tr><td><span class="cod">${esc(a.codigo)}</span></td><td>${esc(a.equipamento)}</td>
        <td class="num">${a.antes === 'ACABOU' ? 'ACABOU' : fmt(a.antes)}</td><td class="num">${num(a.quantidade)}</td>
        <td class="num" style="font-weight:850;color:var(${neg ? '--red' : '--purple'})">${neg ? fmt(a.depois) : 'ACABA'}</td></tr>`).join('')}</tbody></table>
      <p class="mudo" style="margin:0;font-size:12px">A O.P. FICA MARCADA COMO "SALDO NEGATIVO CONFIRMADO".</p>`,
    rotulo: 'CONTINUAR COM SALDO NEGATIVO', perigo: true, largo: true,
  });
}

// ================================================================== tela: ORDENS
const GRUPOS_ESTADO = [
  ['', 'TODAS', null], [EM_PRODUCAO, 'EM PRODUÇÃO', 'NO_PRAZO'], ['ATRASADA', 'ATRASADAS', 'ATRASADA'], ['PROXIMA', 'PRAZO PRÓXIMO', 'PROXIMA'],
  ['SEM_DATA', 'SEM DATA', 'SEM_DATA'], ['NA_OBRA', 'NA OBRA', 'NA_OBRA'], ['INSTALADA', 'INSTALADAS', 'INSTALADA'], ['CANCELADA', 'CANCELADAS', 'CANCELADA'],
];
const ORDEM_ESTADO = Object.keys(ESTADO);
const COLUNAS_OP = [
  { k: 'estado', rot: 'SITUAÇÃO', v: o => ESTADO[o.estado].rot, ord: o => ORDEM_ESTADO.indexOf(o.estado) },
  { k: 'numero', rot: 'O.P.', v: o => o.numero, ord: o => o.ano * 1e4 + o.seq },
  { k: 'cliente', rot: 'CLIENTE', v: o => o.cliente || '' },
  { k: 'obra', rot: 'OBRA', v: o => o.obra || '' },
  { k: 'solicitante', rot: 'SOLICITANTE', v: o => o.solicitante || '' },
  { k: 'tipo', rot: 'TIPO', v: o => o.tipo || '' },
  { k: 'material', rot: 'MATERIAL', v: o => o.material || '' },
  { k: 'prazo', rot: 'PRAZO', v: prazoTexto, ord: o => o.prazo_efetivo || '9999' },
  { k: 'itens', rot: 'EQUIP.', v: o => String(o.itens), ord: o => o.itens, num: true },
  { k: 'pecas', rot: 'PEÇAS', v: o => num(o.pecas), ord: o => o.pecas, num: true },
  { k: 'rev', rot: 'REV', v: o => o.origem === 'SISTEMA' ? String(o.rev) : '—', ord: o => o.rev, num: true },
  { k: 'origem', rot: 'ORIGEM', v: o => o.origem === 'SISTEMA' ? 'SISTEMA' : 'HISTÓRICO' },
];
const COLUNA = Object.fromEntries(COLUNAS_OP.map(c => [c.k, c]));
const filtroColunas = {};
let ordemColuna = null;

function ficha(o) {
  const legado = o.origem !== 'SISTEMA';
  return `<a class="ficha e-${o.estado}" href="${linkOP(o.id)}" data-op="${o.id}">
    <div class="ficha-topo"><div class="ficha-num">${esc(o.numero)}<small>${esc(o.cliente)}</small></div>${pilula(o.estado)}</div>
    <div class="ficha-obra">${esc(o.obra || 'SEM OBRA')}<small>${esc(o.solicitante || '—')} · ${esc(o.tipo || '—')}${o.material ? ' · ' + esc(o.material) : ''}</small></div>
    <div class="ficha-picote" aria-hidden="true"></div>
    <div class="ficha-rodape">
      <div><span>PRAZO</span><b>${esc(prazoTexto(o))}</b></div>
      <div><span>EQUIPAMENTOS</span><b>${legado ? '—' : `${o.itens} · ${num(o.pecas)} PÇ`}</b></div>
      <div>${legado ? '' : `<span>REV</span><b>${o.rev}</b>`}</div>
    </div>
    ${legado ? '<span class="legado">HISTÓRICO</span>' : ''}
  </a>`;
}

TELAS.ordens = async (tela, arg, q, vivo) => {
  const [lista, prefs] = await Promise.all([todasOPs(), api('/api/prefeituras')]);
  if (!vivo()) return;
  const f = { estado: q.estado || '', texto: q.texto || '', p: q.p || '', ano: q.ano || '', ordem: q.ordem || 'recentes', dias: q.dias || '' };
  let vista = memoria.ler('ordens.vista', 'blocos');
  let limite = 120;
  const anos = [...new Set(lista.map(o => o.ano))].sort((a, b) => b - a);
  if (f.ano && !anos.includes(Number(f.ano))) anos.unshift(Number(f.ano));
  const sistema = lista.filter(o => o.origem === 'SISTEMA').length;

  tela.innerHTML = `
    ${heroi({
      classe: 'ordens', olho: 'CONTROLE E ACOMPANHAMENTO', titulo: 'ORDENS DE PRODUÇÃO', icone: 'clipboard',
      texto: `${plural(lista.length, 'O.P.', 'O.P.')} · ${sistema} GERADAS NO SISTEMA · ${lista.length - sistema} DO HISTÓRICO DO CONTROLE. CLIQUE NUMA O.P. PARA VER E ACOMPANHAR.`,
      acoes: `<a class="btn branco large" href="#/nova">${ic('plus')}NOVA O.P.</a>`,
    })}
    <div class="filtros-estado"><div class="segmentado" role="group" aria-label="Situação" id="o-estados"></div></div>
    <div class="filtros">
      <label class="busca">${ic('search')}<input id="o-texto" type="search" autocomplete="off" placeholder="Buscar número, obra, cliente ou solicitante" value="${esc(f.texto)}" aria-label="Buscar O.P."></label>
      <select id="o-pref" aria-label="Prefeitura"><option value="">TODAS AS PREFEITURAS</option>${prefs.map(p => `<option value="${p.id}"${String(p.id) === f.p ? ' selected' : ''}>${esc(p.nome)}</option>`).join('')}</select>
      <select id="o-ano" aria-label="Ano"><option value="">TODOS OS ANOS</option>${anos.map(a => `<option${String(a) === f.ano ? ' selected' : ''}>${a}</option>`).join('')}</select>
      <select id="o-ordem" aria-label="Ordenar">${[['recentes', 'MAIS RECENTES'], ['prazo', 'PRAZO MAIS PRÓXIMO'], ['numero', 'NÚMERO CRESCENTE']].map(([v, r]) => `<option value="${v}"${v === f.ordem ? ' selected' : ''}>${r}</option>`).join('')}</select>
      <div class="segmentado" role="group" aria-label="Exibição">
        <button type="button" data-vista="blocos" aria-pressed="${vista === 'blocos'}">${ic('grid')}BLOCOS</button>
        <button type="button" data-vista="tabela" aria-pressed="${vista === 'tabela'}">${ic('rows')}TABELA</button>
      </div>
    </div>
    <div id="o-avisos"></div>
    <p class="contagem-lista" id="o-conta" aria-live="polite"></p>
    <div id="o-lista"></div>`;

  const porEstado = (l, est) => { if (!est) return l; const s = est.split(','); return l.filter(o => s.includes(o.estado)); };
  function base() {
    let l = filtrarTexto(lista, f.texto);
    if (f.p) l = l.filter(o => String(o.prefeitura_id) === f.p);
    if (f.ano) l = l.filter(o => String(o.ano) === f.ano);
    if (f.dias) l = l.filter(o => o.dias != null && o.dias >= 0 && o.dias <= Number(f.dias));
    return l;
  }
  const porColunas = (l, exceto) => l.filter(o => Object.entries(filtroColunas).every(([k, s]) => k === exceto || s.has(COLUNA[k].v(o))));
  function ordenar(l) {
    const c = [...l];
    const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
    if (ordemColuna) {
      const col = COLUNA[ordemColuna.k];
      const val = col.ord || (o => norm(col.v(o)));
      return c.sort((a, b) => cmp(val(a), val(b)) * ordemColuna.dir);
    }
    if (f.ordem === 'prazo') return c.sort((a, b) => cmp(a.prazo_efetivo || '9999', b.prazo_efetivo || '9999') || a.seq - b.seq);
    if (f.ordem === 'numero') return c.sort((a, b) => a.ano - b.ano || a.seq - b.seq);
    return c;
  }
  let atuais = [];

  function desenhar() {
    const b = base();
    $('#o-estados', tela).innerHTML = GRUPOS_ESTADO.map(([k, r, e]) => `<button type="button"${e ? ` class="e-${e}"` : ''} data-estado="${k}" aria-pressed="${k === f.estado}">
      ${e ? '<span class="ponto"></span>' : ''}${r}<span class="conta">${porEstado(b, k).length}</span></button>`).join('');
    const doEstado = porEstado(b, f.estado);
    atuais = ordenar(porColunas(doEstado));
    const avisos = [];
    if (f.dias) avisos.push(`<div class="tf-aviso">${ic('clock')}<span>SÓ ENTREGAS NOS PRÓXIMOS ${esc(f.dias)} DIAS.</span><button type="button" data-tirar="dias">MOSTRAR TODAS</button></div>`);
    const nCol = Object.keys(filtroColunas).length;
    if (nCol || ordemColuna) {
      avisos.push(`<div class="tf-aviso">${ic('filter')}<span>${nCol ? `FILTRO EM ${plural(nCol, 'COLUNA', 'COLUNAS')}: ${Object.keys(filtroColunas).map(k => COLUNA[k].rot).join(', ')}` : ''}${nCol && ordemColuna ? ' · ' : ''}${ordemColuna ? `ORDENADO POR ${COLUNA[ordemColuna.k].rot} ${ordemColuna.dir > 0 ? '↑' : '↓'}` : ''}</span><button type="button" data-tirar="colunas">LIMPAR</button></div>`);
    }
    $('#o-avisos', tela).innerHTML = avisos.join('');
    $('#o-conta', tela).textContent = `${plural(atuais.length, 'O.P.', 'O.P.')}${atuais.length !== lista.length ? ` DE ${lista.length}` : ''}`;
    const mostrar = atuais.slice(0, limite);
    const resto = atuais.length - mostrar.length;
    const mais = resto > 0 ? `<div style="text-align:center;margin-top:14px"><button class="btn ghost" type="button" data-mais>${ic('plus')}MOSTRAR MAIS (${resto} RESTANTES)</button></div>` : '';
    const el = $('#o-lista', tela);
    if (!atuais.length) {
      el.innerHTML = vazio('NENHUMA O.P. COM ESTES FILTROS', 'TROQUE A SITUAÇÃO OU LIMPE A BUSCA.', 'search',
        `<button class="btn soft" type="button" data-tirar="tudo">${ic('refresh')}LIMPAR FILTROS</button>`);
    } else if (vista === 'blocos') {
      el.innerHTML = `<div class="fichas">${mostrar.map(ficha).join('')}</div>${mais}`;
    } else {
      el.innerHTML = `<div class="tabela-wrap"><table class="tabela"><thead><tr>${COLUNAS_OP.map(c => {
        const ativo = filtroColunas[c.k] || ordemColuna?.k === c.k;
        const seta = ordemColuna?.k === c.k ? (ordemColuna.dir > 0 ? '▲' : '▼') : '▾';
        const sort = ordemColuna?.k === c.k ? ` aria-sort="${ordemColuna.dir > 0 ? 'ascending' : 'descending'}"` : '';
        return `<th scope="col" class="${ativo ? 'tf-ativo' : ''}${c.num ? ' num' : ''}"${sort}>${c.rot}<button type="button" class="tf-btn" data-tf="${c.k}" aria-label="FILTRAR E ORDENAR ${c.rot}" aria-haspopup="dialog">${seta}</button></th>`;
      }).join('')}</tr></thead>
        <tbody>${mostrar.map(o => `<tr class="e-${o.estado}" data-op="${o.id}" tabindex="0">
          <td class="estado-cel">${pilula(o.estado)}</td><td><b>${esc(o.numero)}</b></td><td>${esc(o.cliente)}</td><td><b>${esc(o.obra)}</b></td>
          <td>${esc(o.solicitante)}</td><td>${esc(o.tipo)}</td><td>${esc(o.material)}</td><td>${esc(prazoTexto(o))}</td>
          <td class="num">${o.itens}</td><td class="num">${num(o.pecas)}</td><td class="num">${o.origem === 'SISTEMA' ? o.rev : '—'}</td>
          <td>${o.origem === 'SISTEMA' ? '<span class="badge blue">SISTEMA</span>' : '<span class="badge gray">HISTÓRICO</span>'}</td></tr>`).join('')}</tbody></table></div>${mais}`;
    }
    marcarSelecionada();
  }

  let textoT = null;
  tela.addEventListener('input', e => {
    if (e.target.id !== 'o-texto') return;
    clearTimeout(textoT);
    textoT = setTimeout(() => { f.texto = e.target.value.trim(); limite = 120; trocarQuery({ texto: f.texto }); desenhar(); }, 140);
  });
  tela.addEventListener('change', e => {
    const mapa = { 'o-pref': 'p', 'o-ano': 'ano', 'o-ordem': 'ordem' };
    const k = mapa[e.target.id];
    if (!k) return;
    f[k] = e.target.value;
    if (k === 'ordem') ordemColuna = null;
    limite = 120;
    trocarQuery({ [k]: f[k] });
    desenhar();
  });
  tela.addEventListener('click', e => {
    const b = e.target.closest('button, tr[data-op]');
    if (!b) return;
    if (b.matches('tr[data-op]')) { abrirOP(Number(b.dataset.op)); return; }
    if (b.dataset.estado != null) { f.estado = b.dataset.estado; f.dias = ''; limite = 120; trocarQuery({ estado: f.estado, dias: '' }); desenhar(); }
    else if (b.dataset.vista) {
      vista = b.dataset.vista; memoria.gravar('ordens.vista', vista);
      $$('[data-vista]', tela).forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      desenhar();
    } else if (b.dataset.tf) {
      const col = COLUNA[b.dataset.tf];
      abrirFiltroColuna(b, col, porColunas(porEstado(base(), f.estado), col.k), desenhar);
    } else if (b.dataset.tirar) {
      if (b.dataset.tirar === 'dias') { f.dias = ''; trocarQuery({ dias: '' }); }
      if (b.dataset.tirar === 'colunas' || b.dataset.tirar === 'tudo') { Object.keys(filtroColunas).forEach(k => delete filtroColunas[k]); ordemColuna = null; }
      if (b.dataset.tirar === 'tudo') {
        Object.assign(f, { estado: '', texto: '', p: '', ano: '', dias: '' });
        $('#o-texto', tela).value = ''; $('#o-pref', tela).value = ''; $('#o-ano', tela).value = '';
        trocarQuery({ estado: '', texto: '', p: '', ano: '', dias: '' });
      }
      desenhar();
    } else if (b.hasAttribute('data-mais')) { limite += 120; desenhar(); }
  });
  tela.addEventListener('keydown', e => {
    const tr = e.target.closest?.('tr[data-op]');
    if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); abrirOP(Number(tr.dataset.op)); }
  });
  desenhar();
};

// ---------------------------------------------------------------- filtro por coluna (estilo planilha)
let popTF = null;
function fecharFiltroColuna() {
  if (!popTF) return false;
  const volta = popTF.botao;
  popTF.remove(); popTF = null;
  if (volta?.isConnected) volta.focus();
  return true;
}
document.addEventListener('pointerdown', e => { if (popTF && !e.target.closest('.tf-pop, .tf-btn')) fecharFiltroColuna(); });
addEventListener('resize', () => fecharFiltroColuna());

function abrirFiltroColuna(botao, col, linhas, aoMudar) {
  const reabrindo = popTF?.botao === botao;
  fecharFiltroColuna();
  if (reabrindo) return;
  const conta = new Map();
  linhas.forEach(o => { const v = col.v(o); conta.set(v, (conta.get(v) || 0) + 1); });
  const valores = [...conta.keys()].sort((a, b) => col.ord
    ? col.ord(linhas.find(o => col.v(o) === a)) - col.ord(linhas.find(o => col.v(o) === b)) || 0
    : String(a).localeCompare(String(b), 'pt-BR', { numeric: true }));
  const marcados = filtroColunas[col.k];
  const pop = nodo(`<div class="tf-pop" role="dialog" aria-label="FILTRO DA COLUNA ${esc(col.rot)}">
    <div class="tf-titulo">${esc(col.rot)}</div>
    <div class="tf-ordem">
      <button type="button" data-o="1">↑ ORDENAR CRESCENTE</button>
      <button type="button" data-o="-1">↓ ORDENAR DECRESCENTE</button>
    </div>
    <input type="search" placeholder="Buscar valor" aria-label="Buscar valor" autocomplete="off">
    <div class="tf-lista">
      <label><input type="checkbox" data-todos${!marcados ? ' checked' : ''}><span><b>(SELECIONAR TODOS)</b></span></label>
      ${valores.map(v => `<label data-v="${esc(norm(v))}"><input type="checkbox" value="${esc(v)}"${!marcados || marcados.has(v) ? ' checked' : ''}><span>${esc(v || '(VAZIO)')}</span><small>${conta.get(v)}</small></label>`).join('')}
    </div>
    <div class="tf-acoes"><button type="button" class="btn ghost small" data-limpar>LIMPAR</button><button type="button" class="btn primary small" data-aplicar>APLICAR</button></div>
  </div>`);
  pop.botao = botao;
  document.body.appendChild(pop);
  popTF = pop;
  const r = botao.getBoundingClientRect();
  const h = pop.offsetHeight;
  pop.style.left = Math.max(8, Math.min(innerWidth - pop.offsetWidth - 8, r.left - 12)) + 'px';
  pop.style.top = (r.bottom + 6 + h > innerHeight ? Math.max(8, r.top - h - 6) : r.bottom + 6) + 'px';
  const busca = $('input[type=search]', pop);
  busca.focus();
  const caixas = () => $$('label[data-v]', pop).filter(l => !l.hidden).map(l => $('input', l));
  busca.addEventListener('input', () => {
    const t = norm(busca.value);
    $$('label[data-v]', pop).forEach(l => { l.hidden = !l.dataset.v.includes(t); });
  });
  $('[data-todos]', pop).addEventListener('change', e => caixas().forEach(c => { c.checked = e.target.checked; }));
  pop.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.o) ordemColuna = { k: col.k, dir: Number(b.dataset.o) };
    else if (b.hasAttribute('data-limpar')) { delete filtroColunas[col.k]; if (ordemColuna?.k === col.k) ordemColuna = null; }
    else if (b.hasAttribute('data-aplicar')) {
      const todas = $$('label[data-v] input', pop);
      const sel = todas.filter(c => c.checked).map(c => c.value);
      if (sel.length === todas.length) delete filtroColunas[col.k]; else filtroColunas[col.k] = new Set(sel);
    } else return;
    fecharFiltroColuna();
    aoMudar();
  });
  pop.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target === busca) { e.preventDefault(); $('[data-aplicar]', pop).click(); } });
}

// ================================================================== gaveta da O.P.
const gaveta = $('#gaveta');
const gavetaFundo = $('#gaveta-fundo');
const gavetaConteudo = $('#gaveta-conteudo');
const gav = { id: null, op: null, aba: null, modelo: null, foco: null };
const gavetaAberta = () => gaveta.classList.contains('aberta');

function marcarSelecionada() {
  $$('.ficha[data-op]', app).forEach(el => el.classList.toggle('selecionada', gavetaAberta() && Number(el.dataset.op) === gav.id));
}

function fecharGavetaVisual() {
  if (!gavetaAberta()) return;
  gaveta.classList.remove('aberta');
  gaveta.setAttribute('aria-hidden', 'true');
  gaveta.inert = true;
  gavetaFundo.hidden = true;
  gav.id = null; gav.op = null; gav.modelo = null;
  marcarSelecionada();
  if (gav.foco?.isConnected) gav.foco.focus();
}

function fecharGaveta() {
  const r = lerRota();
  const { op, ...resto } = r.q;
  location.hash = montarHash(r.tela, r.arg, resto);
}
gavetaFundo.addEventListener('click', fecharGaveta);
gaveta.inert = true;

async function abrirGaveta(id) {
  if (!gavetaAberta()) gav.foco = document.activeElement;
  if (gav.id !== id) { gav.aba = null; gav.modelo = null; gav.op = null; }
  gav.id = id;
  gaveta.inert = false;
  gaveta.classList.add('aberta');
  gaveta.setAttribute('aria-hidden', 'false');
  gavetaFundo.hidden = false;
  marcarSelecionada();
  if (!gav.op) gavetaConteudo.innerHTML = `<div class="g-corpo"><button class="icon-button" type="button" data-g="fechar" aria-label="Fechar" style="float:right">${ic('close')}</button>${vazio('CARREGANDO O.P.…', '', 'clipboard')}</div>`;
  let o;
  try { o = await api('/api/ops/' + id); } catch (e) {
    if (gav.id !== id) return;
    gavetaConteudo.innerHTML = `<div class="g-corpo"><button class="icon-button" type="button" data-g="fechar" aria-label="Fechar" style="float:right">${ic('close')}</button>${vazio('NÃO FOI POSSÍVEL ABRIR A O.P.', e.message, 'alert')}</div>`;
    return;
  }
  if (gav.id !== id) return;
  const primeira = !gav.op;
  gav.op = o;
  if (!gav.aba) gav.aba = o.origem === 'SISTEMA' ? 'resumo' : 'acomp';
  desenharGaveta();
  if (primeira) $('[data-g=fechar]', gavetaConteudo)?.focus();
}

const detalhe = (rot, val, largo = false) => `<div class="detalhe${largo ? ' largo' : ''}"><span>${rot}</span><b>${val || '—'}</b></div>`;
const up = v => String(v || '').trim().toUpperCase();

function seloSaldo(s) {
  return {
    SALDO_OK: '<span class="badge green">SALDO OK</span>',
    SALDO_ENCERRADO: '<span class="badge purple">ENCERROU O SALDO</span>',
    SALDO_NEGATIVO_CONFIRMADO: `<span class="badge red">${ic('alert')}SALDO NEGATIVO CONFIRMADO</span>`,
    SEM_CONTRATO: '<span class="badge gray">SEM CONTRATO</span>',
  }[s] || '';
}

function desenharGaveta() {
  const o = gav.op;
  const sistema = o.origem === 'SISTEMA';
  const ativa = o.situacao === 'ATIVA';
  const abas = sistema
    ? [['resumo', 'RESUMO', 'file'], ['equip', 'EQUIPAMENTOS', 'box'], ['acomp', 'ACOMPANHAMENTO', 'clipboard'], ['revs', 'REVISÕES', 'history']]
    : [['acomp', 'ACOMPANHAMENTO', 'clipboard']];
  if (!abas.some(a => a[0] === gav.aba)) gav.aba = abas[0][0];
  const pdf = `/api/ops/${o.id}/documento.pdf`;
  const acoes = sistema ? `<div class="g-acoes">
      <a class="btn primary small" href="${pdf}" target="_blank" rel="noopener">${ic('eye')}VER PDF</a>
      <a class="btn ghost small" href="/api/ops/${o.id}/documento.xlsx" download>${ic('download')}XLSX</a>
      <a class="btn ghost small" href="${pdf}?baixar=1" download>${ic('download')}PDF</a>
      ${ativa ? `<a class="btn soft small" href="#/editar/${o.id}">${ic('edit')}EDITAR → REV ${o.rev + 1}</a>` : ''}
      <a class="btn ghost small" href="#/nova?de=${o.id}">${ic('copy')}DUPLICAR</a>
      ${ativa ? `<button class="btn ghost small" type="button" data-g="publicar">${ic('send')}REPUBLICAR</button>
      <button class="btn danger small" type="button" data-g="cancelar">${ic('x-circle')}CANCELAR</button>` : ''}
    </div>` : '';
  gavetaConteudo.innerHTML = `
    <header class="g-cab e-${o.estado}">
      <div class="g-cab-topo">
        <h2 id="g-titulo">${esc(o.numero)}<small>${sistema ? `REV ${o.rev}` : 'HISTÓRICO'}</small></h2>
        <button class="icon-button" type="button" data-g="fechar" aria-label="Fechar (Esc)">${ic('close')}</button>
      </div>
      <p class="obra">${esc(o.obra || 'SEM OBRA')}</p>
      <div class="cliente">${esc(o.cliente)}${o.solicitante ? ` · ${esc(o.solicitante)}` : ''}</div>
      <div class="selos">${pilula(o.estado)}
        ${o.tipo ? `<span class="badge blue">${esc(o.tipo)}</span>` : ''}${o.material ? `<span class="badge teal">${esc(o.material)}</span>` : ''}
        ${o.modelo ? `<span class="badge slate">${ic('layers')}${esc(o.modelo)}</span>` : ''}${seloSaldo(o.saldo_status)}
        <span class="badge gray">${ic('calendar')}PRAZO ${esc(prazoTexto(o))}</span>
      </div>
    </header>
    ${acoes}
    <nav class="g-menu" role="tablist" aria-label="Seções da O.P.">${abas.map(([k, r, i]) => `<button type="button" role="tab" id="g-aba-${k}" aria-controls="g-painel" aria-selected="${k === gav.aba}" data-g-aba="${k}">${ic(i)}${r}</button>`).join('')}</nav>
    <div class="g-corpo"><div class="g-painel" id="g-painel" role="tabpanel" aria-labelledby="g-aba-${gav.aba}"></div></div>`;
  desenharAbaGaveta();
}

async function desenharAbaGaveta() {
  const o = gav.op;
  const p = $('#g-painel', gavetaConteudo);
  if (!p) return;
  if (gav.aba === 'resumo') {
    const arq = o.arquivos || {};
    const arquivos = arq.xlsx || arq.pdf || arq.pdf_erro ? `<div class="arquivos">
      ${arq.xlsx ? `<span class="arquivo">${ic('file')}${esc(arq.xlsx)}</span>` : ''}${arq.pdf ? `<span class="arquivo">${ic('file')}${esc(arq.pdf)}</span>` : ''}
      ${arq.pdf_erro ? `<span class="arquivo" style="color:var(--red)">${ic('alert')}PDF FALHOU: ${esc(arq.pdf_erro)}</span>` : ''}</div>` : '<small>AINDA NÃO PUBLICADA (REPUBLICAR GERA OS ARQUIVOS).</small>';
    const prazoOriginal = o.prazo_data ? dataBR(o.prazo_data) : (o.prazo_texto || 'DEFINIR');
    const novaEntrega = /^\d{4}-/.test(o.entrega_atualizada || '') ? ` <small>· NOVA ENTREGA ${dataBR(o.entrega_atualizada)}</small>` : '';
    p.innerHTML = `<div class="detalhes">
      ${detalhe('CLIENTE', esc(o.cliente))}${detalhe('SOLICITANTE', esc(o.solicitante))}
      ${detalhe('OBRA', esc(o.obra), true)}
      ${detalhe('TIPO', esc(o.tipo))}${detalhe('MATERIAL', esc(o.material))}
      ${detalhe('PRAZO', esc(prazoOriginal) + novaEntrega + ` <small>· ${esc(prazoDias(o))}</small>`)}${detalhe('SITUAÇÃO', esc(ESTADO[o.estado].rot) + (o.situacao === 'CANCELADA' ? ' <small>(CANCELADA NO SISTEMA)</small>' : ''))}
      ${detalhe('SOLICITADA EM', esc(dataHoraBR(o.solicitado_em)))}${detalhe('ATUALIZADA EM', esc(dataHoraBR(o.atualizado_em)))}
      ${detalhe('MODELO', esc(o.modelo))}${detalhe('EQUIPAMENTOS', `${o.itens.length} <small>· ${num(o.itens.reduce((t, i) => t + i.quantidade, 0))} PEÇAS</small>`)}
      ${detalhe('ARQUIVOS PUBLICADOS', arquivos, true)}
      ${o.obs ? detalhe('OBSERVAÇÕES', esc(o.obs), true) : ''}
    </div>`;
  } else if (gav.aba === 'equip') {
    if (!gav.modelo && o.modelo_id) {
      p.innerHTML = vazio('CARREGANDO EQUIPAMENTOS…', '', 'box');
      try { gav.modelo = await api(`/api/modelos/${o.modelo_id}`); } catch { gav.modelo = { linhas: [] }; }
      if (gav.op !== o || gav.aba !== 'equip') return;
    }
    const comFoto = new Set((gav.modelo?.linhas || []).filter(l => l.foto).map(l => l.linha));
    p.innerHTML = `<div class="itens-op">${o.itens.map(i => {
      const foto = comFoto.has(i.linha);
      const extra = [i.inauguracao && `INAUGURAÇÃO: ${i.inauguracao}`, i.observacao && `OBS: ${i.observacao}`].filter(Boolean).join(' · ');
      return `<div class="item-op">
        <span class="mini"${foto ? ` data-foto="${i.linha}" style="cursor:zoom-in" title="AMPLIAR FOTO"` : ''}>${foto ? `<img src="/api/modelos/${o.modelo_id}/foto/${i.linha}" alt="" loading="lazy">` : ic('image')}</span>
        <span><b><span class="cod${ehBonus(i.codigo) ? ' bonus' : ''}">${esc(i.codigo || '—')}</span> ${esc(i.equipamento)}</b><small>${esc(extra || 'SEM INAUGURAÇÃO OU OBSERVAÇÃO')}</small></span>
        <span class="qtd">${num(i.quantidade)}</span></div>`;
    }).join('') || vazio('SEM EQUIPAMENTOS', '', 'box')}</div>`;
  } else if (gav.aba === 'acomp') {
    p.innerHTML = desenharEtapas(o);
  } else if (gav.aba === 'revs') {
    const arq = o.arquivos || {};
    p.innerHTML = `<div class="revisoes">${[...o.revisoes].reverse().map(r => `<div class="revisao">
        <span class="rev">REV<br>${r.rev}</span>
        <span><b>${esc(r.resumo || (r.rev ? 'EDITADA' : 'CRIADA'))}</b><small>${esc(dataHoraBR(r.momento))}${r.usuario ? ' · ' + esc(r.usuario) : ''}</small></span>
        ${r.rev === o.rev ? '<span class="badge green">ATUAL</span>' : '<span class="badge gray">ANTERIOR</span>'}</div>`).join('') || vazio('SEM REVISÕES', '', 'history')}</div>
      ${arq.xlsx || arq.pdf ? `<h4 style="margin:18px 0 6px;font-size:11px;letter-spacing:.06em;color:var(--muted)">ARQUIVOS DA REVISÃO ATUAL</h4>
        <div class="arquivos">${arq.xlsx ? `<span class="arquivo">${ic('file')}${esc(arq.xlsx)}</span>` : ''}${arq.pdf ? `<span class="arquivo">${ic('file')}${esc(arq.pdf)}</span>` : ''}</div>` : ''}`;
  }
}

function desenharEtapas(o) {
  const sistema = o.origem === 'SISTEMA';
  const st = up(o.status_instalacao), mo = up(o.material_obra), ea = up(o.entrega_atualizada), fo = up(o.fotografico);
  const dataNova = /^\d{4}-\d{2}-\d{2}$/.test(ea) ? ea : '';
  const producao = EM_PRODUCAO.split(',').includes(o.estado);
  const op = (campo, valor, atual, rot, classe = '', icone = 'check') =>
    `<button type="button" class="opcao ${classe}" data-campo="${campo}" data-valor="${valor}" aria-pressed="${atual === valor}">${ic(icone)}${rot}</button>`;
  const etapa = (n, estado, titulo, texto, opcoes = '') => {
    const marca = estado === 'feita' ? ic('check') : estado === 'atencao' ? ic('alert') : n;
    return `<li class="etapa ${estado}"><span class="marca" aria-hidden="true">${marca}</span><div><h4>${titulo}</h4><p>${texto}</p>${opcoes ? `<div class="opcoes">${opcoes}</div>` : ''}</div></li>`;
  };
  const prazoOriginal = o.prazo_data ? dataBR(o.prazo_data) : (o.prazo_texto || 'DEFINIR');
  const cancelada = ['CANCELADO', 'CANCELADA', 'DUPLICADO'].includes(st);
  return `${sistema ? '' : `<div class="nota-legado">${ic('lock')}<span>O.P. DO HISTÓRICO DO CONTROLE (LEGADO): SÓ O ACOMPANHAMENTO PODE SER ALTERADO AQUI. O DOCUMENTO ORIGINAL FICA NA PASTA ANTIGA.</span></div>`}
    ${o.situacao === 'CANCELADA' ? `<div class="nota-legado">${ic('x-circle')}<span>O.P. CANCELADA NO SISTEMA. O SALDO FOI DEVOLVIDO AO CONTRATO.</span></div>` : ''}
    <ol class="etapas">
      ${etapa(1, 'feita', 'SOLICITADA', esc(`${dataHoraBR(o.solicitado_em) || 'SEM DATA'}${o.solicitante ? ' · ' + o.solicitante : ''}`))}
      ${etapa(2, o.estado === 'ATRASADA' ? 'atencao' : producao ? 'atual' : 'feita', 'PRAZO', esc(`${prazoOriginal} · ${prazoDias(o)}`))}
      ${etapa(3, ea === 'OK' ? 'feita' : ea === 'FALTA' ? 'atencao' : dataNova ? 'atual' : '', 'ENTREGA',
        ea === 'OK' ? 'ENTREGUE.' : ea === 'FALTA' ? 'ENTREGA COM FALTA DE MATERIAL.' : dataNova ? `NOVA DATA DE ENTREGA: ${dataBR(dataNova)} (SUBSTITUI O PRAZO).` : 'AGUARDANDO ENTREGA.',
        op('entrega_atualizada', 'OK', ea, 'OK') + op('entrega_atualizada', 'FALTA', ea, 'FALTA', 'ruim', 'alert') +
        `<label class="opcao${dataNova ? '" aria-pressed="true' : ''}" style="padding:2px 4px 2px 9px">${ic('calendar')}NOVA DATA
          <input type="date" data-campo="entrega_atualizada" value="${dataNova}" aria-label="NOVA DATA DE ENTREGA"></label>`)}
      ${etapa(4, mo === 'OK' ? 'feita' : '', 'MATERIAL NA OBRA', mo === 'OK' ? 'MATERIAL ENTREGUE NA OBRA.' : 'AINDA NÃO ESTÁ NA OBRA.',
        op('material_obra', 'OK', mo, 'OK'))}
      ${etapa(5, st === 'OK' ? 'feita' : cancelada ? 'atencao' : '', 'INSTALAÇÃO',
        st === 'OK' ? 'INSTALADA. A QUANTIDADE PASSA DE PREVISÃO PARA REALIZADO NO SALDO.' : cancelada ? `MARCADA COMO ${st}.` : 'AGUARDANDO INSTALAÇÃO.',
        op('status_instalacao', 'OK', st, 'OK') + (sistema ? '' : op('status_instalacao', 'CANCELADO', st, 'CANCELADO', 'ruim', 'x-circle')))}
      ${etapa(6, fo === 'OK' ? 'feita' : '', 'FOTOGRÁFICO', fo === 'OK' ? 'FOTOS DA INSTALAÇÃO RECEBIDAS.' : 'SEM FOTOS AINDA.', op('fotografico', 'OK', fo, 'OK', '', 'camera'))}
      ${etapa(7, o.obs ? 'feita' : '', 'OBSERVAÇÕES', 'ANOTAÇÕES DO ACOMPANHAMENTO (IGUAL À COLUNA OBS DO CONTROLE).',
        `<textarea id="g-obs" rows="3" style="width:100%" aria-label="OBSERVAÇÕES">${esc(o.obs)}</textarea>
         <button type="button" class="btn soft small" data-g="obs">${ic('save')}SALVAR OBSERVAÇÃO</button>`)}
    </ol>`;
}

async function salvarAcomp(campos, alvo) {
  const o = gav.op;
  if (alvo) alvo.disabled = true;
  try {
    const novo = await ocupado(alvo?.classList.contains('btn') ? alvo : null, () => api(`/api/ops/${o.id}/acompanhamento`, { metodo: 'POST', corpo: campos }));
    if (gav.id !== o.id) return;
    gav.op = novo;
    desenharGaveta();
    esquecerOPs();
    atualizarFundo();
    aviso(`ACOMPANHAMENTO DA O.P. ${novo.numero} SALVO.`, 'ok');
  } catch (e) { falha(e); if (alvo) alvo.disabled = false; }
}

gavetaConteudo.addEventListener('click', async e => {
  const b = e.target.closest('button, [data-foto]');
  if (!b || b.disabled) return;
  const o = gav.op;
  if (b.dataset.g === 'fechar') return fecharGaveta();
  if (!o) return;
  if (b.dataset.gAba) {
    gav.aba = b.dataset.gAba;
    $$('[data-g-aba]', gavetaConteudo).forEach(x => x.setAttribute('aria-selected', String(x === b)));
    $('#g-painel', gavetaConteudo).setAttribute('aria-labelledby', b.id);
    desenharAbaGaveta();
  } else if (b.dataset.campo && b.matches('button')) {
    const atual = up(o[b.dataset.campo]);
    await salvarAcomp({ [b.dataset.campo]: atual === b.dataset.valor ? '' : b.dataset.valor }, b);
  } else if (b.dataset.g === 'obs') {
    await salvarAcomp({ obs: $('#g-obs', gavetaConteudo).value }, b);
  } else if (b.dataset.foto) {
    const i = o.itens.find(x => x.linha === Number(b.dataset.foto));
    verFoto(`/api/modelos/${o.modelo_id}/foto/${i.linha}`, `${i.codigo} · ${i.equipamento}`);
  } else if (b.dataset.g === 'publicar') {
    try {
      const r = await ocupado(b, () => api(`/api/ops/${o.id}/publicar`, { metodo: 'POST' }));
      if (r.pdf_erro) aviso('XLSX PUBLICADO, MAS O PDF FALHOU: ' + r.pdf_erro, 'erro'); else aviso(`O.P. ${o.numero} REPUBLICADA (XLSX E PDF).`, 'ok');
      gav.op = await api('/api/ops/' + o.id);
      desenharGaveta();
    } catch (erro) { falha(erro); }
  } else if (b.dataset.g === 'cancelar') {
    const c = await dialogo({
      titulo: `CANCELAR A O.P. ${o.numero}?`, sub: 'O SALDO CONSUMIDO VOLTA PARA O CONTRATO. A O.P. CONTINUA NO HISTÓRICO.',
      corpo: `<label class="campo">MOTIVO DO CANCELAMENTO<textarea id="d-motivo" maxlength="200" placeholder="EX.: DUPLICADA, OBRA SUSPENSA"></textarea></label>`,
      rotulo: 'CANCELAR O.P.', perigo: true,
      validar: c => $('#d-motivo', c).value.trim() ? null : 'INFORME O MOTIVO DO CANCELAMENTO.',
    });
    if (!c) return;
    try {
      gav.op = await ocupado(b, () => api(`/api/ops/${o.id}/cancelar`, { metodo: 'POST', corpo: { motivo: $('#d-motivo', c).value.trim().toUpperCase() } }));
      aviso(`O.P. ${o.numero} CANCELADA. SALDO DEVOLVIDO AO CONTRATO.`, 'ok');
      desenharGaveta(); esquecerOPs(); atualizarFundo();
    } catch (erro) { falha(erro); }
  }
});
gavetaConteudo.addEventListener('change', e => {
  const el = e.target;
  if (el.matches('input[type=date][data-campo]')) salvarAcomp({ [el.dataset.campo]: el.value || '' }, null);
});
// foco preso dentro da gaveta enquanto aberta
gaveta.addEventListener('keydown', e => {
  if (e.key !== 'Tab') return;
  const focaveis = $$('a[href], button:not([disabled]), input, textarea, select, [tabindex="0"]', gaveta).filter(x => x.offsetParent);
  if (!focaveis.length) return;
  const [primeiro, ultimo] = [focaveis[0], focaveis[focaveis.length - 1]];
  if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
  else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
});

// ================================================================== tela: SALDOS
function classeSaldo(it) {
  if (it.saldo === 'ACABOU') return 'acabou';
  if (typeof it.saldo === 'number' && it.saldo < 0) return 'neg';
  if (!(it.montante > 0)) return 'zero';
  return 'ok';
}

function cartaoSaldo(it) {
  const M = Math.max(0, it.montante || 0), R = it.quant || 0, P = it.previsao || 0;
  const total = R + P;
  // sem montante (bonificado ou item zerado) não há excedente a mostrar: só a proporção realizado/previsão
  const controlado = M > 0 && !ehBonus(it.codigo);
  const escala = (controlado ? Math.max(M, total) : total) || 1;
  const r1 = controlado ? Math.min(R, M) : R, p1 = controlado ? Math.min(P, M - r1) : P, exc = controlado ? Math.max(0, total - M) : 0;
  const w = v => `${(v / escala) * 100}%`;
  const cls = classeSaldo(it);
  const valor = it.saldo === 'ACABOU' ? 'ACABOU' : num(it.saldo);
  const usado = M ? Math.round((total / M) * 100) : null;
  const bonus = ehBonus(it.codigo);
  return `<article class="saldo-card ${cls}" data-codigo="${esc(it.codigo)}">
    <div class="saldo-cab">
      <span class="cod${bonus ? ' bonus' : ''}">${esc(it.codigo)}</span>
      <h3>${esc(it.equipamento)}${bonus ? ' <span class="badge purple">BONIFICADO</span>' : ''}</h3>
      <div class="saldo-valor"><strong>${valor}</strong><small>${cls === 'zero' ? 'SEM MONTANTE' : 'SALDO'}</small></div>
    </div>
    <div class="medidor" role="img" aria-label="REALIZADO ${num(R)}, PREVISÃO ${num(P)}, MONTANTE ${num(M)}${exc ? `, EXCEDENTE ${num(exc)}` : ''}"
      data-tip-titulo="ITEM ${esc(it.codigo)}${usado != null ? ` · ${usado}% USADO` : ''}" data-tip-valor="${esc(valor)} DE ${num(M)}"
      data-tip-extra="REALIZADO ${num(R)} · PREVISÃO ${num(P)}${exc ? ` · EXCEDENTE ${num(exc)}` : ''}" data-tip-cor="var(--serie-real)">
      ${r1 ? `<i class="real" style="width:${w(r1)}"></i>` : ''}${p1 ? `<i class="prev" style="width:${w(p1)}"></i>` : ''}${exc ? `<i class="exc" style="width:${w(exc)}"></i>` : ''}
    </div>
    <div class="saldo-numeros">
      <div><span>MONTANTE</span><b>${num(M)}</b></div>
      <div><span><i style="--cor:var(--serie-real)"></i>REALIZADO</span><b>${num(R)}</b></div>
      <div><span><i style="--cor:var(--serie-prev)"></i>PREVISÃO</span><b>${num(P)}</b></div>
    </div>
    <div class="saldo-pe">${it.ajuste ? `<span class="ajuste-nota">AJUSTE MANUAL ${it.ajuste > 0 ? '+' : ''}${num(it.ajuste)}</span>` : ''}
      ${it.sistema_previsao || it.sistema_instalado ? `<span class="mudo" style="font-size:10.5px;font-weight:700">SISTEMA: ${num(it.sistema_previsao)} PREV. · ${num(it.sistema_instalado)} INST.</span>` : ''}</div>
    <button class="btn ghost small ajustar" type="button" data-ajustar="${esc(it.codigo)}">${ic('sliders')}AJUSTAR</button>
  </article>`;
}

TELAS.saldos = async (tela, arg, q, vivo) => {
  const prefs = await api('/api/prefeituras');
  if (!vivo()) return;
  const comContrato = prefs.filter(p => p.contratos > 0);
  let pref = prefs.find(p => String(p.id) === q.p) || comContrato[0] || prefs[0];
  let contratos = pref ? await api('/api/contratos?prefeitura_id=' + pref.id) : [];
  let contrato = contratos.find(c => String(c.id) === q.c) || contratos[0];
  let itens = contrato ? await api(`/api/contratos/${contrato.id}/saldo`) : [];
  if (!vivo()) return;
  let filtro = memoria.ler('saldos.filtro', 'todos');
  let texto = '';

  tela.innerHTML = `
    ${heroi({
      classe: 'saldos', olho: 'CONTRATOS E ATAS', titulo: 'SALDOS DOS CONTRATOS', icone: 'scale',
      texto: 'SALDO = MONTANTE − (REALIZADO + PREVISÃO). O.P. INSTALADA CONTA EM REALIZADO; AS DEMAIS EM PREVISÃO. CANCELAR DEVOLVE O SALDO.',
    })}
    <div class="prefs-linha" role="group" aria-label="Prefeitura" id="s-prefs"></div>
    <div id="s-contratos"></div>
    <div id="s-corpo"></div>`;

  function desenharPrefs() {
    $('#s-prefs', tela).innerHTML = prefs.map(p => `<button type="button" class="pref-mini" data-pref="${p.id}" aria-pressed="${p.id === pref?.id}">
      ${p.logo ? `<img src="/api/prefeituras/${p.id}/logo" alt="" data-icone="building" loading="lazy">` : ic('building')}${esc(p.nome)}</button>`).join('')
      || vazio('NENHUMA PREFEITURA IMPORTADA', '', 'building');
  }

  function desenharContratos() {
    $('#s-contratos', tela).innerHTML = contratos.length ? `<div class="saldos-topo">
      <div class="segmentado" role="group" aria-label="Contrato">${contratos.map(c => `<button type="button" data-contrato="${c.id}" aria-pressed="${c.id === contrato?.id}">${ic('file')}ATA ${esc(c.ata)}<span class="conta">${c.itens}</span></button>`).join('')}</div>
      ${contrato ? `<span class="mudo" style="font-size:11.5px;font-weight:700">${esc(contrato.nome || '')}${contrato.descricao ? ' · ' + esc(contrato.descricao) : ''}${contrato.importado_em ? ' · IMPORTADO EM ' + esc(dataBR(contrato.importado_em)) : ''}</span>` : ''}
    </div>` : '';
  }

  function desenharCorpo() {
    const c = $('#s-corpo', tela);
    if (!contrato) { c.innerHTML = vazio('PREFEITURA SEM CONTRATO', 'OS CONTRATOS VÊM DA IMPORTAÇÃO DOS LIVROS DAS PREFEITURAS.', 'scale'); return; }
    const neg = itens.filter(i => classeSaldo(i) === 'neg').length;
    const acabou = itens.filter(i => classeSaldo(i) === 'acabou').length;
    const comSaldo = itens.filter(i => classeSaldo(i) === 'ok').length;
    const montante = itens.reduce((t, i) => t + Math.max(0, i.montante || 0), 0);
    const usado = itens.reduce((t, i) => t + (i.montante > 0 ? i.quant + i.previsao : 0), 0);
    const pct = montante ? Math.round((usado / montante) * 100) : 0;
    const termos = norm(texto).split(/\s+/).filter(Boolean);
    const lista = itens.filter(i => {
      const k = classeSaldo(i);
      if (filtro === 'negativos' && k !== 'neg') return false;
      if (filtro === 'encerrados' && k !== 'acabou') return false;
      if (filtro === 'com' && k !== 'ok') return false;
      const alvo = norm(i.codigo + ' ' + i.equipamento);
      return termos.every(t => alvo.includes(t));
    });
    const seg = [['todos', 'TODOS', itens.length, ''], ['negativos', 'NEGATIVOS', neg, 'ATRASADA'], ['encerrados', 'ENCERRADOS', acabou, 'CANCELADA'], ['com', 'COM SALDO', comSaldo, 'NA_OBRA']]
      .map(([k, r, n, e]) => `<button type="button" data-filtro="${k}" aria-pressed="${k === filtro}"${e ? ` class="e-${e}"` : ''}>${e ? '<span class="ponto"></span>' : ''}${r}<span class="conta">${n}</span></button>`).join('');
    c.innerHTML = `
      <div class="kpis">
        <div class="kpi e-NO_PRAZO"><div class="kpi-topo"><span>ITENS NO CONTRATO</span>${ic('list')}</div><strong>${itens.length}</strong><small>ATA ${esc(contrato.ata)}</small></div>
        <div class="kpi e-ATRASADA"><div class="kpi-topo"><span>SALDO NEGATIVO</span>${ic('alert')}</div><strong>${neg}</strong><small>CONSUMIU MAIS QUE O MONTANTE</small></div>
        <div class="kpi" style="--estado:var(--purple)"><div class="kpi-topo"><span>ENCERRADOS</span>${ic('lock')}</div><strong>${acabou}</strong><small>SALDO EXATAMENTE ZERO</small></div>
        <div class="kpi e-NA_OBRA"><div class="kpi-topo"><span>USADO DO CONTRATO</span>${ic('chart')}</div><strong>${pct}%</strong><small>${num(usado)} DE ${num(montante)} UNIDADES</small></div>
      </div>
      <div class="saldos-topo">
        <div class="segmentado" role="group" aria-label="Filtrar itens">${seg}</div>
        <label class="busca" style="flex:1;min-width:220px;max-width:380px">${ic('search')}<input id="s-busca" type="search" autocomplete="off" placeholder="Buscar item ou código" aria-label="Buscar item" value="${esc(texto)}"></label>
        <div class="legenda"><span><i style="--cor:var(--serie-real)"></i>REALIZADO</span><span><i style="--cor:var(--serie-prev)"></i>PREVISÃO</span>
          <span><i style="--cor:var(--red)" class="exc-amostra"></i>EXCEDENTE</span><span><i class="trilho-amostra"></i>DISPONÍVEL</span></div>
      </div>
      <div class="saldos-cards">${lista.map(cartaoSaldo).join('') || vazio('NENHUM ITEM NESTE FILTRO', '', 'search')}</div>
      <table class="sr"><caption>SALDO DOS ITENS DA ATA ${esc(contrato.ata)}</caption>
        <tr><th>CÓDIGO</th><th>EQUIPAMENTO</th><th>MONTANTE</th><th>REALIZADO</th><th>PREVISÃO</th><th>SALDO</th></tr>
        ${lista.map(i => `<tr><td>${esc(i.codigo)}</td><td>${esc(i.equipamento)}</td><td>${num(i.montante)}</td><td>${num(i.quant)}</td><td>${num(i.previsao)}</td><td>${esc(i.saldo)}</td></tr>`).join('')}</table>`;
  }

  async function trocarPref(id) {
    pref = prefs.find(p => p.id === id);
    contratos = await api('/api/contratos?prefeitura_id=' + id);
    contrato = contratos[0];
    itens = contrato ? await api(`/api/contratos/${contrato.id}/saldo`) : [];
    trocarQuery({ p: id, c: contrato?.id || '' });
    desenharPrefs(); desenharContratos(); desenharCorpo();
  }

  async function ajustar(codigo, botao) {
    const it = itens.find(i => i.codigo === codigo);
    const c = await dialogo({
      titulo: `AJUSTAR ITEM ${it.codigo}`, sub: `${it.equipamento} · ATA ${contrato.ata}. O AJUSTE FICA REGISTRADO NA ATIVIDADE COM O MOTIVO.`,
      corpo: `<div class="grade-2">
          <label class="campo">MONTANTE (TOTAL DO CONTRATO)<input id="d-montante" inputmode="decimal" value="${esc(String(it.montante).replace('.', ','))}"></label>
          <label class="campo">AJUSTE MANUAL (+ CONSOME / − DEVOLVE)<input id="d-ajuste" inputmode="decimal" value="${esc(String(it.ajuste).replace('.', ','))}"></label>
        </div>
        <p class="mudo" style="margin:0;font-size:11.5px">HOJE: REALIZADO ${num(it.quant)} · PREVISÃO ${num(it.previsao)} (JÁ INCLUI O AJUSTE ${num(it.ajuste)}) · SALDO ${esc(it.saldo === 'ACABOU' ? 'ACABOU' : num(it.saldo))}</p>
        <label class="campo">MOTIVO (OBRIGATÓRIO)<textarea id="d-motivo" maxlength="200" placeholder="EX.: ADITIVO DE 25% NO CONTRATO"></textarea></label>`,
      rotulo: 'SALVAR AJUSTE',
      validar: c => {
        const ok = v => /^-?\d+([.,]\d+)?$/.test(v.trim());
        if (!ok($('#d-montante', c).value)) return 'MONTANTE INVÁLIDO.';
        if (!ok($('#d-ajuste', c).value)) return 'AJUSTE INVÁLIDO (USE NÚMERO, PODE SER NEGATIVO).';
        if (!$('#d-motivo', c).value.trim()) return 'INFORME O MOTIVO DO AJUSTE.';
        return null;
      },
    });
    if (!c) return;
    const n = v => Number(v.trim().replace(',', '.'));
    try {
      itens = await ocupado(botao, () => api(`/api/contratos/${contrato.id}/ajuste`, {
        metodo: 'POST', corpo: { codigo, montante: n($('#d-montante', c).value), ajuste: n($('#d-ajuste', c).value), motivo: $('#d-motivo', c).value.trim().toUpperCase() },
      }));
      desenharCorpo();
      aviso(`SALDO DO ITEM ${codigo} AJUSTADO.`, 'ok');
    } catch (e) { falha(e); }
  }

  tela.addEventListener('click', async e => {
    const b = e.target.closest('button');
    if (!b) return;
    try {
      if (b.dataset.pref) await trocarPref(Number(b.dataset.pref));
      else if (b.dataset.contrato) {
        contrato = contratos.find(c => c.id === Number(b.dataset.contrato));
        itens = await api(`/api/contratos/${contrato.id}/saldo`);
        trocarQuery({ c: contrato.id });
        desenharContratos(); desenharCorpo();
      } else if (b.dataset.filtro) {
        filtro = b.dataset.filtro; memoria.gravar('saldos.filtro', filtro); desenharCorpo();
      } else if (b.dataset.ajustar) await ajustar(b.dataset.ajustar, b);
    } catch (erro) { falha(erro); }
  });
  tela.addEventListener('input', e => {
    if (e.target.id !== 's-busca') return;
    texto = e.target.value;
    const pos = e.target.selectionStart;
    desenharCorpo();
    const novo = $('#s-busca', tela);
    novo.focus(); novo.setSelectionRange(pos, pos);
  });
  desenharPrefs(); desenharContratos(); desenharCorpo();
  requestAnimationFrame(() => $('.pref-mini[aria-pressed=true]', tela)?.scrollIntoView({ inline: 'center', block: 'nearest' }));
};

// ================================================================== tela: MODELOS
TELAS.modelos = async (tela, arg, q, vivo) => {
  const [modelos, prefs, contratos] = await Promise.all([api('/api/modelos?todos=1'), api('/api/prefeituras'), api('/api/contratos')]);
  if (!vivo()) return;
  const ativos = modelos.filter(m => m.ativo).length;
  const semContrato = modelos.filter(m => m.ativo && !m.contrato_id).length;
  let texto = '';

  tela.innerHTML = `
    ${heroi({
      classe: 'modelos', olho: 'PREFEITURAS E FOTOS', titulo: 'MODELOS DE O.P.', icone: 'layers',
      texto: `${plural(modelos.length, 'MODELO', 'MODELOS')} (ABAS "OP-" DOS LIVROS) · ${ativos} ATIVOS${semContrato ? ` · ${semContrato} SEM CONTRATO DE SALDO` : ''}. AS FOTOS E O LOGO SAEM DO PRÓPRIO MODELO.`,
    })}
    <div class="filtros"><label class="busca">${ic('search')}<input id="m-busca" type="search" autocomplete="off" placeholder="Buscar prefeitura, modelo ou ATA" aria-label="Buscar modelo"></label></div>
    <div id="m-lista"></div>`;

  function cartao(m) {
    const opcoes = contratos.filter(c => c.prefeitura_id === m.prefeitura_id)
      .map(c => `<option value="${c.id}"${c.id === m.contrato_id ? ' selected' : ''}>ATA ${esc(c.ata)} · ${c.itens} ITENS</option>`).join('');
    const fotos = [0, 1, 2, 3].map(i => {
      const l = m.fotos[i];
      return `<span>${l != null ? `<img src="/api/modelos/${m.id}/foto/${l}" alt="" loading="lazy">` : ic('image')}</span>`;
    }).join('');
    return `<article class="modelo-card${m.ativo ? '' : ' inativo'}" data-modelo="${m.id}" data-busca="${esc(norm([m.prefeitura, m.aba, m.titulo, m.ata].join(' ')))}">
      <div class="modelo-fotos" data-galeria="${m.id}" role="button" tabindex="0" aria-label="VER EQUIPAMENTOS DO MODELO ${esc(m.aba)}">${fotos}</div>
      <div class="modelo-info">
        <h3>${esc(m.aba)}</h3>
        <div class="linha">
          ${m.titulo ? `<span class="badge blue">${esc(m.titulo)}</span>` : ''}
          <span class="badge slate">${ic('box')}${plural(m.equipamentos, 'EQUIP.', 'EQUIP.')}</span>
          <span class="badge ${m.com_foto ? 'teal' : 'gray'}">${ic('camera')}${m.com_foto} COM FOTO</span>
          <span class="badge purple">${ic('clipboard')}${plural(m.ops, 'O.P.', 'O.P.')}</span>
          ${m.tipo_padrao ? `<span class="badge gray">${esc(m.tipo_padrao)}</span>` : ''}
          ${m.contrato_id ? '' : `<span class="badge orange">${ic('alert')}SEM CONTRATO</span>`}
        </div>
        <button class="btn soft small" type="button" data-galeria="${m.id}" style="justify-self:start">${ic('eye')}VER EQUIPAMENTOS</button>
      </div>
      <div class="modelo-acoes">
        <select data-contrato-de="${m.id}" aria-label="CONTRATO DO SALDO DO MODELO ${esc(m.aba)}"><option value="0"${m.contrato_id ? '' : ' selected'}>SEM CONTRATO</option>${opcoes}</select>
        <label class="interruptor"><input type="checkbox" data-ativo="${m.id}"${m.ativo ? ' checked' : ''}><span>${m.ativo ? 'ATIVO' : 'INATIVO'}</span></label>
      </div>
    </article>`;
  }

  function desenhar() {
    const termos = norm(texto).split(/\s+/).filter(Boolean);
    const grupos = prefs.map(p => ({ p, ms: modelos.filter(m => m.prefeitura_id === p.id && termos.every(t => norm([m.prefeitura, m.aba, m.titulo, m.ata].join(' ')).includes(t))) }))
      .filter(g => g.ms.length);
    $('#m-lista', tela).innerHTML = grupos.map(({ p, ms }) => `<section class="grupo-pref" aria-labelledby="gp-${p.id}">
      <header><span class="logo">${logoPref(p)}</span><div><h2 id="gp-${p.id}">${esc(p.nome)}</h2>
        <p>${plural(ms.length, 'MODELO', 'MODELOS')} · ${plural(p.contratos, 'CONTRATO', 'CONTRATOS')} · ${plural(p.ops, 'O.P.', 'O.P.')}</p></div></header>
      <div class="modelos-grade">${ms.map(cartao).join('')}</div></section>`).join('')
      || vazio('NENHUM MODELO ENCONTRADO', texto ? 'TENTE OUTRA BUSCA.' : 'USE O IMPORTAR_LEGADO.CMD PARA TRAZER AS ABAS "OP-" DOS LIVROS.', 'layers');
  }

  async function galeria(id) {
    const m = await api('/api/modelos/' + id);
    const figuras = m.linhas.map(l => `<figure>
      <div>${l.foto ? `<img src="/api/modelos/${m.id}/foto/${l.linha}" alt="${esc(l.equipamento)}" loading="lazy">` : ic('image')}</div>
      <figcaption><span class="cod${ehBonus(l.codigo) ? ' bonus' : ''}">${esc(l.codigo || '—')}</span><span>${esc(l.equipamento)}</span></figcaption></figure>`).join('');
    dialogo({
      titulo: `${m.aba} · ${m.prefeitura}`, sub: `${plural(m.linhas.length, 'EQUIPAMENTO', 'EQUIPAMENTOS')} · ${m.linhas.filter(l => l.foto).length} COM FOTO`,
      corpo: `<div class="galeria">${figuras || vazio('MODELO SEM EQUIPAMENTOS', '', 'box')}</div>`, largo: true, semRodape: true,
    });
  }

  async function salvar(id, campos, el) {
    const m = modelos.find(x => x.id === id);
    try {
      const novo = await api('/api/modelos/' + id, { metodo: 'PATCH', corpo: campos });
      m.ativo = novo.ativo; m.contrato_id = novo.contrato_id;
      const c = contratos.find(x => x.id === m.contrato_id);
      m.ata = c?.ata || null;
      const card = el.closest('.modelo-card');
      card.replaceWith(nodo(cartao(m)));
      aviso(campos.ativo != null ? `MODELO ${m.aba} ${m.ativo ? 'ATIVADO' : 'DESATIVADO'}.` : `CONTRATO DO SALDO DE ${m.aba} ALTERADO.`, 'ok');
    } catch (e) {
      falha(e);
      if (el.type === 'checkbox') el.checked = !el.checked; else el.value = String(m.contrato_id || 0);
    }
  }

  tela.addEventListener('click', e => {
    const g = e.target.closest('[data-galeria]');
    if (g) galeria(Number(g.dataset.galeria)).catch(falha);
  });
  tela.addEventListener('keydown', e => {
    const g = e.target.closest?.('.modelo-fotos[data-galeria]');
    if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); galeria(Number(g.dataset.galeria)).catch(falha); }
  });
  tela.addEventListener('change', e => {
    const el = e.target;
    if (el.dataset.ativo) salvar(Number(el.dataset.ativo), { ativo: el.checked }, el);
    else if (el.dataset.contratoDe) salvar(Number(el.dataset.contratoDe), { contrato_id: Number(el.value) }, el);
  });
  tela.addEventListener('input', e => { if (e.target.id === 'm-busca') { texto = e.target.value; desenhar(); } });
  desenhar();
};

// ================================================================== tela: CONFIGURAÇÃO
TELAS.config = async (tela, arg, q, vivo) => {
  const [cfg, resumo, eventos] = await Promise.all([api('/api/config'), api('/api/resumo'), api('/api/eventos')]);
  if (!vivo()) return;
  const indisponivel = String(resumo.motor_pdf).startsWith('INDISPONÍVEL');
  let quantos = 40;

  tela.innerHTML = `
    ${heroi({
      classe: 'config', olho: 'PASTAS E PDF', titulo: 'CONFIGURAÇÃO', icone: 'gear',
      texto: 'ONDE OS ARQUIVOS DAS O.P. SÃO PUBLICADOS E QUAL PROGRAMA GERA O PDF. A SENHA DOS .XLSX FICA SÓ NO CONFIG.JSON DESTE COMPUTADOR.',
    })}
    <div class="config-grade">
      <form class="card" id="c-form" novalidate>
        <div class="card-head" style="margin-bottom:0"><div><div class="kicker">PUBLICAÇÃO</div><h2>ARQUIVOS DAS O.P.</h2><p>CADA O.P. NOVA OU REVISADA GERA O .XLSX BLOQUEADO E O .PDF.</p></div></div>
        <label class="interruptor"><input type="checkbox" id="c-publicar"${cfg.publicar ? ' checked' : ''}><span>PUBLICAR AUTOMATICAMENTE AO GERAR OU EDITAR</span></label>
        <label class="campo">PASTA DOS .XLSX<input id="c-xlsx" value="${esc(cfg.pasta_xlsx)}" placeholder="${esc(resumo.pastas[0])}" autocomplete="off"></label>
        <label class="campo">PASTA DOS .PDF<input id="c-pdf" value="${esc(cfg.pasta_pdf)}" placeholder="${esc(resumo.pastas[1])}" autocomplete="off"></label>
        <label class="campo">MOTOR DE PDF<select id="c-motor">
          ${[['auto', 'AUTOMÁTICO (EXCEL NO WINDOWS, SENÃO LIBREOFFICE)'], ['excel', 'MICROSOFT EXCEL (IGUAL AO VBA)'], ['libreoffice', 'LIBREOFFICE']]
            .map(([v, r]) => `<option value="${v}"${cfg.motor_pdf === v ? ' selected' : ''}>${r}</option>`).join('')}</select></label>
        <p class="mudo" style="margin:0;font-size:11.5px;font-weight:600">DEIXE A PASTA EM BRANCO PARA USAR O PADRÃO (DADOS\\DOCUMENTOS).</p>
        <div><button class="btn primary" type="submit" id="c-salvar">${ic('save')}SALVAR CONFIGURAÇÃO</button></div>
      </form>
      <section class="card">
        <div class="card-head" style="margin-bottom:0"><div><div class="kicker">SITUAÇÃO</div><h2>COMO ESTÁ AGORA</h2><p>VALORES EFETIVOS USADOS PELO SERVIDOR.</p></div>
          <span class="badge ${indisponivel ? 'red' : 'green'}">${ic(indisponivel ? 'alert' : 'check')}PDF: ${esc(indisponivel ? 'INDISPONÍVEL' : String(resumo.motor_pdf).toUpperCase())}</span></div>
        ${indisponivel ? `<div class="nota-legado" style="background:var(--red-soft);color:var(--red)">${ic('alert')}<span>${esc(resumo.motor_pdf)}</span></div>` : ''}
        <div class="caminho"><b>.XLSX PUBLICADOS EM</b>${esc(resumo.pastas[0])}</div>
        <div class="caminho"><b>.PDF PUBLICADOS EM</b>${esc(resumo.pastas[1])}</div>
        <div class="kpis" style="margin:0;grid-template-columns:repeat(2,minmax(0,1fr))">
          <div class="kpi e-NO_PRAZO"><div class="kpi-topo"><span>PRÓXIMA O.P.</span>${ic('clipboard')}</div><strong>${esc(resumo.proximo_numero)}</strong><small>NUMERAÇÃO REINICIA TODO ANO</small></div>
          <div class="kpi e-NA_OBRA"><div class="kpi-topo"><span>O.P. ATIVAS EM ${resumo.ano}</span>${ic('factory')}</div><strong>${resumo.ops_ano}</strong><small>${resumo.ops_sistema} GERADAS NO SISTEMA</small></div>
          <div class="kpi e-INSTALADA"><div class="kpi-topo"><span>PREFEITURAS</span>${ic('building')}</div><strong>${resumo.prefeituras}</strong><small>IMPORTADAS DOS LIVROS</small></div>
          <div class="kpi" style="--estado:var(--purple)"><div class="kpi-topo"><span>MODELOS ATIVOS</span>${ic('layers')}</div><strong>${resumo.modelos}</strong><small>ABAS "OP-"</small></div>
        </div>
      </section>
    </div>
    <section class="card" style="margin-top:18px" aria-labelledby="c-ativ">
      <div class="card-head"><div><div class="kicker">HISTÓRICO</div><h2 id="c-ativ">ATIVIDADE</h2><p>TUDO QUE FOI FEITO NO SISTEMA (O.P., ACOMPANHAMENTO, SALDO, MODELOS, IMPORTAÇÃO).</p></div>
        <span class="badge slate">${plural(eventos.length, 'REGISTRO', 'REGISTROS')}</span></div>
      <div class="atividade" id="c-lista"></div>
    </section>`;

  function desenharAtividade() {
    const mais = eventos.length > quantos ? `<div style="text-align:center;margin-top:10px"><button class="btn ghost small" type="button" data-mais>${ic('plus')}MOSTRAR MAIS</button></div>` : '';
    $('#c-lista', tela).innerHTML = (eventos.slice(0, quantos).map(itemAtividade).join('') || vazio('SEM ATIVIDADE AINDA', '', 'history')) + mais;
  }

  $('#c-form', tela).addEventListener('submit', async e => {
    e.preventDefault();
    const corpo = { publicar: $('#c-publicar', tela).checked, pasta_xlsx: $('#c-xlsx', tela).value.trim(), pasta_pdf: $('#c-pdf', tela).value.trim(), motor_pdf: $('#c-motor', tela).value };
    try {
      await ocupado($('#c-salvar', tela), () => api('/api/config', { metodo: 'PUT', corpo }));
      aviso('CONFIGURAÇÃO SALVA.', 'ok');
      baseAtual = null; desenharTela(lerRota(), { manterRolagem: true });
    } catch (erro) { falha(erro); }
  });
  tela.addEventListener('click', e => { if (e.target.closest('[data-mais]')) { quantos += 60; desenharAtividade(); } });
  desenharAtividade();
};

// ================================================================== início
addEventListener('hashchange', rotear);
if (!location.hash) history.replaceState(null, '', '#/painel');
rotear();
atualizarProxima();
