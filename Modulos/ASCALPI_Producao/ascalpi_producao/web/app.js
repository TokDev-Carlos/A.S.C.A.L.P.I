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

// ================================================================== telas das próximas etapas
for (const t of ['nova', 'editar', 'ordens', 'saldos', 'modelos', 'config']) {
  TELAS[t] = TELAS[t] || (async tela => { tela.innerHTML = vazio('EM CONSTRUÇÃO', 'ESTA TELA CHEGA NA PRÓXIMA ETAPA.', 'hammer'); });
}

// ================================================================== gaveta da O.P. (etapa 2)
const gaveta = $('#gaveta');
const gavetaFundo = $('#gaveta-fundo');
const gavetaAberta = () => gaveta.classList.contains('aberta');
function fecharGavetaVisual() {
  gaveta.classList.remove('aberta');
  gaveta.setAttribute('aria-hidden', 'true');
  gavetaFundo.hidden = true;
}
function fecharGaveta() {
  const r = lerRota();
  const { op, ...resto } = r.q;
  location.hash = montarHash(r.tela, r.arg, resto);
}
async function abrirGaveta() { /* etapa 2 */ }
function fecharFiltroColuna() { return false; }
gavetaFundo.addEventListener('click', fecharGaveta);

// ================================================================== início
addEventListener('hashchange', rotear);
if (!location.hash) history.replaceState(null, '', '#/painel');
rotear();
atualizarProxima();
