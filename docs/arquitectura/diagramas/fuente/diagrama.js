/* Motor mínimo de diagramas de LiciGT: nodos HTML/SVG, flechas ortogonales entre puertos,
   etiquetas junto al tramo y verificación de maquetación (?verificar).
   Sin dependencias. Las coordenadas son del mapa (px del lienzo). */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const D = { nodos: {}, flechas: [], carriles: [], marcos: [], limites: [], etqs: [], textos: [] };
  let mapa, capa;
  const R = 7;           // radio de esquina de las flechas
  const GAP_PUNTA = 4;   // separación entre la punta y el destino
  const COL = { principal: '#1f2937', datos: '#2563eb', excepcion: '#64748b', revision: '#a16207', jev: '#ea580c' };
  const EST = { ok: 'implementado', pend: 'por implementar', parc: 'parcial' };

  const el = (t, c, p) => { const e = document.createElement(t); if (c) e.className = c; if (p) p.appendChild(e); return e; };
  const sv = (t, a, p) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; };
  const tx = (t, c, p, txt) => { const e = el(t, c + ' tx', p); e.textContent = txt; return e; };

  D.init = function (o) {
    mapa = document.getElementById('mapa');
    mapa.style.height = o.h + 'px';
    capa = sv('svg', { class: 'capa-flechas', width: o.w, height: o.h, viewBox: '0 0 ' + o.w + ' ' + o.h }, mapa);
    const defs = sv('defs', {}, capa);
    Object.keys(COL).forEach(k => {
      const m = sv('marker', { id: 'm-' + k, viewBox: '0 0 10 8', refX: 10, refY: 4, markerWidth: 10, markerHeight: 8, markerUnits: 'userSpaceOnUse', orient: 'auto' }, defs);
      sv('path', { d: 'M0 0 L10 4 L0 8 Z', fill: COL[k] }, m);
    });
    D.w = o.w; D.h = o.h;
  };

  D.carril = function (o) {
    const d = el('div', 'carril', mapa);
    Object.assign(d.style, { left: o.x + 'px', top: o.y + 'px', width: o.w + 'px', height: o.h + 'px' });
    d.id = o.id;
    const t = el('div', 'tab', d); tx('span', '', t, o.tab);
    D.carriles.push(o);
  };
  D.limite = function (o) {
    const d = el('div', 'limite', mapa);
    Object.assign(d.style, { left: o.x + 'px', top: o.y + 'px', width: o.w + 'px', height: o.h + 'px' });
    tx('span', 'limite-etq', d, o.etq);
    D.limites.push(o);
  };
  D.marco = function (o) {
    const d = el('div', 'marco', mapa);
    Object.assign(d.style, { left: o.x + 'px', top: o.y + 'px', width: o.w + 'px', height: o.h + 'px' });
    const c = el('div', 'marco-cab', d);
    const l1 = el('div', '', c);
    tx('span', 'mt', l1, o.titulo);
    pill(l1, o.rol, o.est);
    tx('span', 'campos', c, o.campos);
    c.dataset.tx = '1';
    D.marcos.push(o);
  };

  const GLIFO = { ok: '\u25CF', parc: '\u25D0', pend: '\u25CB' };
  function pill(p, rol, est) {
    const e = tx('span', 'pill est e-' + est, p, rol + ' ' + GLIFO[est]);
    e.title = EST[est];
  }

  const FORMA = { codigo: 'caja', llm: 'caja', decision: 'rombo', datos: 'cil', documento: 'doc', salida: 'par', humano: 'humano', externo: 'ext' };

  function formaSvg(n) {
    const w = n.w, h = n.h, s = sv('svg', { class: 'forma', width: w, height: h, viewBox: '0 0 ' + w + ' ' + h });
    const f = (t, a, c) => sv(t, Object.assign({ class: c || 'f' }, a), s);
    switch (n.forma) {
      case 'caja': f('rect', { x: 1, y: 1, width: w - 2, height: h - 2, rx: 12 }); break;
      case 'rombo': f('polygon', { points: [w / 2, 1, w - 1, h / 2, w / 2, h - 1, 1, h / 2].join(' ') }); break;
      case 'par': { const k = n.sk; f('polygon', { points: [k, 1, w - 1, 1, w - k, h - 1, 1, h - 1].join(' ') }); break; }
      case 'ext': f('rect', { x: 1, y: 1, width: w - 2, height: h - 2, rx: 12 }); f('rect', { x: 7, y: 7, width: w - 14, height: h - 14, rx: 8 }, 'f2'); break;
      case 'cil': {
        const rx = w / 2 - 1, ry = 11;
        f('path', { d: 'M1,' + ry + ' A' + rx + ',' + ry + ' 0 0 1 ' + (w - 1) + ',' + ry + ' V' + (h - ry) + ' A' + rx + ',' + ry + ' 0 0 1 1,' + (h - ry) + ' Z' });
        f('path', { d: 'M1,' + ry + ' A' + rx + ',' + ry + ' 0 0 0 ' + (w - 1) + ',' + ry }, 'f2');
        break;
      }
      case 'doc': f('path', { d: 'M1,1 H' + (w - 1) + ' V' + (h - 16) + ' Q' + (w * 0.75) + ',' + (h - 30) + ' ' + (w / 2) + ',' + (h - 16) + ' T1,' + (h - 16) + ' Z' }); break;
      default: break;
    }
    return s;
  }

  D.nodo = function (o) {
    const n = Object.assign({ sk: 16 }, o);
    n.forma = FORMA[n.tipo];
    n.fp = { x: n.x, y: n.y, w: n.w, h: n.h + (n.forma === 'rombo' ? 30 : 0) };
    const d = el('div', 'nodo t-' + n.tipo + (n.sec ? ' sec' : ''), mapa);
    d.id = n.id;
    Object.assign(d.style, { left: n.x + 'px', top: n.y + 'px', width: n.w + 'px', height: n.h + 'px' });
    if (n.forma !== 'humano') d.appendChild(formaSvg(n));
    const c = el('div', 'cuerpo', d);
    if (n.forma === 'rombo') { c.style.left = '50%'; c.style.right = 'auto'; c.style.width = '116px'; c.style.marginLeft = '-58px'; c.style.padding = '0'; }
    if (n.forma === 'par') { c.style.padding = '6px ' + (n.sk + 10) + 'px'; }
    if (n.forma === 'cil') { c.style.paddingTop = '26px'; c.style.paddingBottom = '14px'; }
    if (n.forma === 'doc') { c.style.paddingBottom = '20px'; }
    if (n.forma === 'ext') { c.style.padding = '12px'; }
    if (n.forma === 'humano') {
      const p = sv('svg', { class: 'persona', viewBox: '0 0 40 40' }, c);
      sv('circle', { cx: 20, cy: 11, r: 7 }, p);
      sv('path', { d: 'M6 37c0-9 6-14 14-14s14 5 14 14' }, p);
    }
    const cab = el('div', 'cab', c);
    if (n.num != null) tx('span', 'num', cab, String(n.num));
    tx('span', 'titulo', cab, n.titulo);
    if (n.linea) tx('div', 'linea', c, n.linea);
    if (n.chips) { const ch = el('div', 'chips', c); n.chips.forEach(t => tx('span', 'chip', ch, t)); }
    if (n.forma === 'rombo') pill(el('div', 'pie-rombo', d), n.rol, n.est);
    else if (n.rol) pill(el('div', 'pie', c), n.rol, n.est);
    D.nodos[n.id] = n;
    return n;
  };

  /* Puerto sobre el borde real de la forma. off: desplazamiento a lo largo del lado. */
  function puerto(n, lado, off) {
    off = off || 0;
    const cx = n.x + n.w / 2, cy = n.y + n.h / 2;
    if (n.forma === 'rombo') {
      if (lado === 'e' || lado === 'w') { const dx = (n.w / 2) * (1 - Math.abs(off) / (n.h / 2)); return { x: lado === 'e' ? cx + dx : cx - dx, y: cy + off }; }
      const dy = (n.h / 2) * (1 - Math.abs(off) / (n.w / 2)); return { x: cx + off, y: lado === 's' ? cy + dy : cy - dy };
    }
    if (n.forma === 'par' && (lado === 'e' || lado === 'w')) {
      const y = cy + off, t = (y - n.y) / n.h;
      return { x: lado === 'e' ? n.x + n.w - n.sk * t : n.x + n.sk * (1 - t), y };
    }
    if (lado === 'e') return { x: n.x + n.w, y: cy + off };
    if (lado === 'w') return { x: n.x, y: cy + off };
    if (lado === 'n') return { x: cx + off, y: n.y };
    return { x: cx + off, y: n.y + n.h };
  }
  D.puerto = puerto;
  const NORM = { n: [0, -1], s: [0, 1], e: [1, 0], w: [-1, 0] };
  const vert = s => s === 'n' || s === 's';

  D.flecha = function (o) { o.tipo = o.tipo || 'principal'; D.flechas.push(o); return o; };

  function ruta(a) {
    const f = D.nodos[a.de], t = D.nodos[a.a];
    if (!f || !t) throw new Error('flecha sin nodo: ' + a.de + '->' + a.a);
    const S = a.sp ? { x: a.sp[0], y: a.sp[1] } : puerto(f, a.ds, a.dof);
    const T = puerto(t, a.as, a.aof), nv = NORM[a.as];
    const E = { x: T.x + nv[0] * GAP_PUNTA, y: T.y + nv[1] * GAP_PUNTA };
    a.S = S; a.E = E; a.T = T;
    let P = [S];
    if (a.via) {
      let prev = S;
      a.via.forEach((v, i) => {
        const q = { x: v[0] == null ? prev.x : v[0], y: v[1] == null ? prev.y : v[1] };
        if (i === 0 && q.x !== S.x && q.y !== S.y) P.push(vert(a.ds) ? { x: S.x, y: q.y } : { x: q.x, y: S.y });
        else if (i > 0 && q.x !== prev.x && q.y !== prev.y) P.push({ x: q.x, y: prev.y });
        P.push(q); prev = q;
      });
      if (prev.x !== E.x && prev.y !== E.y) P.push(vert(a.as) ? { x: E.x, y: prev.y } : { x: prev.x, y: E.y });
      P.push(E);
    } else if (vert(a.ds) && vert(a.as)) {
      if (Math.abs(S.x - E.x) > 0.5) { const my = a.m != null ? a.m : (S.y + E.y) / 2; P.push({ x: S.x, y: my }, { x: E.x, y: my }); }
      P.push(E);
    } else if (!vert(a.ds) && !vert(a.as)) {
      if (Math.abs(S.y - E.y) > 0.5) { const mx = a.m != null ? a.m : (S.x + E.x) / 2; P.push({ x: mx, y: S.y }, { x: mx, y: E.y }); }
      P.push(E);
    } else if (!vert(a.ds)) { P.push({ x: E.x, y: S.y }, E); }
    else { P.push({ x: S.x, y: E.y }, E); }
    // limpiar duplicados y puntos colineales
    const Q = [];
    P.forEach(p => { const l = Q[Q.length - 1]; if (!l || Math.abs(l.x - p.x) > 0.01 || Math.abs(l.y - p.y) > 0.01) Q.push(p); });
    const W = [Q[0]];
    for (let i = 1; i < Q.length - 1; i++) {
      const a0 = W[W.length - 1], b = Q[i], c = Q[i + 1];
      if ((Math.abs(a0.x - b.x) < 0.01 && Math.abs(b.x - c.x) < 0.01) || (Math.abs(a0.y - b.y) < 0.01 && Math.abs(b.y - c.y) < 0.01)) continue;
      W.push(b);
    }
    W.push(Q[Q.length - 1]);
    a.P = W;
    a.segs = [];
    for (let i = 0; i < W.length - 1; i++) a.segs.push({ x1: W[i].x, y1: W[i].y, x2: W[i + 1].x, y2: W[i + 1].y, a });
  }

  function cruces(a, b) {
    const out = [];
    a.segs.forEach((s, si) => b.segs.forEach(t => {
      const sh = Math.abs(s.y1 - s.y2) < 0.01, th = Math.abs(t.y1 - t.y2) < 0.01;
      if (sh === th) return;
      const h = sh ? s : t, v = sh ? t : s;
      const x = v.x1, y = h.y1;
      if (x > Math.min(h.x1, h.x2) + 0.5 && x < Math.max(h.x1, h.x2) - 0.5 && y > Math.min(v.y1, v.y2) + 0.5 && y < Math.max(v.y1, v.y2) - 0.5)
        out.push({ x, y, seg: s, horizontal: sh });
    }));
    return out;
  }

  function trazo(a) {
    const P = a.P, n = P.length, segs = [];
    for (let i = 0; i < n - 1; i++) {
      const dx = P[i + 1].x - P[i].x, dy = P[i + 1].y - P[i].y, len = Math.hypot(dx, dy);
      segs.push({ ux: dx / len, uy: dy / len, len });
    }
    const r = i => Math.min(R, segs[i].len / 2, segs[i + 1] ? segs[i + 1].len / 2 : R);
    const f = v => Math.round(v * 100) / 100;
    let d = '';
    for (let i = 0; i < n - 1; i++) {
      const sg = segs[i];
      const ini = i > 0 ? r(i - 1) : 0, fin = i < n - 2 ? r(i) : 0;
      const sx = P[i].x + sg.ux * ini, sy = P[i].y + sg.uy * ini;
      const ex = P[i + 1].x - sg.ux * fin, ey = P[i + 1].y - sg.uy * fin;
      if (i === 0) d += 'M' + f(sx) + ',' + f(sy);
      // huecos en este segmento
      const gs = (a.huecos || []).filter(g => g.seg === a.segs[i]).map(g => (g.horizontal ? g.x - P[i].x : g.y - P[i].y) * (g.horizontal ? sg.ux : sg.uy)).sort((p, q) => p - q);
      gs.forEach(t => {
        d += ' L' + f(P[i].x + sg.ux * (t - 6)) + ',' + f(P[i].y + sg.uy * (t - 6)) + ' M' + f(P[i].x + sg.ux * (t + 6)) + ',' + f(P[i].y + sg.uy * (t + 6));
      });
      d += ' L' + f(ex) + ',' + f(ey);
      if (i < n - 2) { const rr = r(i); d += ' Q' + f(P[i + 1].x) + ',' + f(P[i + 1].y) + ' ' + f(P[i + 1].x + segs[i + 1].ux * rr) + ',' + f(P[i + 1].y + segs[i + 1].uy * rr); }
    }
    return d;
  }

  function colocarEtiqueta(a, e) {
    const i = e.i || 0, s = a.segs[i], f = e.f == null ? 0.5 : e.f;
    const qx = s.x1 + (s.x2 - s.x1) * f, qy = s.y1 + (s.y2 - s.y1) * f;
    const d = el('div', 'etq tx ' + a.tipo, mapa);
    d.textContent = e.t; d.style.visibility = 'hidden';
    const w = d.offsetWidth, h = d.offsetHeight;
    let x, y;
    const horiz = Math.abs(s.y1 - s.y2) < 0.01;
    if (horiz) { x = qx - w / 2; y = e.l === 'b' ? qy + 8 : qy - 8 - h; }
    else { y = qy - h / 2; x = e.l === 'i' ? qx - 8 - w : qx + 8; }
    x += e.dx || 0; y += e.dy || 0;
    Object.assign(d.style, { left: x + 'px', top: y + 'px', visibility: 'visible' });
    d.dataset.arrow = a.de + '>' + a.a;
    D.etqs.push({ el: d, a, x, y, w, h });
  }

  D.listo = function () {
    D.flechas.forEach(ruta);
    D.flechas.forEach(a => {
      a.huecos = [];
      (a.hueco || []).forEach(idx => { const b = D.flechas[idx]; if (b) cruces(a, b).forEach(c => a.huecos.push(c)); });
    });
    D.flechas.forEach(a => {
      sv('path', { d: trazo(a), class: 'fl ' + a.tipo, 'marker-end': 'url(#m-' + a.tipo + ')' }, capa);
      (a.et || []).forEach(e => colocarEtiqueta(a, e));
    });
    if (location.search.indexOf('verificar') >= 0) verificar();
  };

  D.nota = function (o) {
    const d = el('div', 'etq tx', mapa); d.textContent = o.t; d.style.left = o.x + 'px'; d.style.top = o.y + 'px';
    D.etqs.push({ el: d, a: null, x: o.x, y: o.y, w: d.offsetWidth, h: d.offsetHeight });
  };
  D.indice = function (o) { const i = D.flechas.indexOf(o); return i; };

  /* Leyenda mínima de una línea: estilos de flecha, insignias de estado y estado compartido. */
  D.leyenda = function (id) {
    const c = document.getElementById(id); c.className = 'leyenda-min';
    const ln = (col, w, dash) => '<svg width="46" height="20" viewBox="0 0 46 20"><line x1="2" y1="10" x2="36" y2="10" stroke="' + col + '" stroke-width="' + w + '"' + (dash ? ' stroke-dasharray="' + dash + '"' : '') + '/><path d="M34 6 L44 10 L34 14 Z" fill="' + col + '"/></svg>';
    const it = (h, t) => { const d = el('span', 'it', c); d.insertAdjacentHTML('beforeend', h); const s = el('span', '', d); s.textContent = t; };
    it(ln('#1f2937', 2), 'flujo');
    it(ln('#2563eb', 2), 'datos');
    it(ln('#64748b', 1.5, '7 5'), 'excepción');
    it(ln('#a16207', 1.5, '10 3 2 3'), 'revisión humana');
    it(ln('#ea580c', 1.5, '7 4'), 'JEV');
    it('<svg width="30" height="20"><rect x="2" y="3" width="26" height="14" rx="4" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 3"/></svg>', 'estado compartido');
    it('', 'rol N: responsable');
    it('', '\u25CF implementado');
    it('', '\u25D0 parcial');
    it('', '\u25CB por implementar');
  };

  /* ---------- Verificación ---------- */
  function verificar() {
    const P = [];
    const out = m => { if (P.length < 80) P.push(m); };
    const lienzo = document.getElementById('lienzo');
    const L = lienzo.getBoundingClientRect(), M = mapa.getBoundingClientRect();
    const rel = r => ({ l: r.left - M.left, t: r.top - M.top, r: r.right - M.left, b: r.bottom - M.top });
    const nom = e => { const n = e.closest('.nodo'); return (n ? n.id + '/' : '') + (e.className.split(' ')[0] || e.tagName) + '"' + e.textContent.slice(0, 18) + '"'; };
    const rectsTexto = e => {
      const out = [];
      const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
      let t;
      while ((t = w.nextNode())) { if (!t.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(t); Array.prototype.forEach.call(r.getClientRects(), q => { if (q.width > 0) out.push(rel(q)); }); }
      return out;
    };
    const inter = (a, b, k) => { k = k || 0; return a.l < b.r - k && a.r > b.l + k && a.t < b.b - k && a.b > b.t + k; };
    const segRect = (s, r, k) => {
      const l = Math.min(s.x1, s.x2), rr = Math.max(s.x1, s.x2), t = Math.min(s.y1, s.y2), b = Math.max(s.y1, s.y2);
      return l <= r.r + k && rr >= r.l - k && t <= r.b + k && b >= r.t - k;
    };
    const fp = n => ({ l: n.fp.x, t: n.fp.y, r: n.fp.x + n.fp.w, b: n.fp.y + n.fp.h });
    const segs = []; D.flechas.forEach(a => a.segs.forEach(s => segs.push(s)));

    // textos
    const T = Array.prototype.map.call(mapa.querySelectorAll('.tx'), e => ({ e, rs: rectsTexto(e) }));

    // 1 y 2. desbordes y texto dentro de su nodo
    Object.keys(D.nodos).forEach(id => {
      const n = D.nodos[id], d = document.getElementById(id), c = d.querySelector('.cuerpo');
      if (c.scrollHeight > c.clientHeight + 2 || c.scrollWidth > c.clientWidth + 2) out(id + ' texto desbordado');
      const caja = { l: n.x, t: n.y, r: n.x + n.w, b: n.y + n.h };
      T.filter(q => d.contains(q.e) && !q.e.closest('.pie-rombo')).forEach(q => q.rs.forEach(r => {
        if (r.l < caja.l + 2 || r.r > caja.r - 2 || r.t < caja.t + 2 || r.b > caja.b - 2) out(nom(q.e) + ' sale de ' + id);
        else if (n.forma === 'rombo') {
          const cx = (caja.l + caja.r) / 2, cy = (caja.t + caja.b) / 2;
          [[r.l, r.t], [r.r, r.t], [r.l, r.b], [r.r, r.b]].forEach(p => { if (Math.abs(p[0] - cx) / (n.w / 2) + Math.abs(p[1] - cy) / (n.h / 2) > 1) out(nom(q.e) + ' esquina fuera del rombo ' + id); });
        } else if (n.forma === 'par') {
          [[r.l, r.t], [r.r, r.t], [r.l, r.b], [r.r, r.b]].forEach(p => {
            const t = (p[1] - n.y) / n.h, xl = n.x + n.sk * (1 - t), xr = n.x + n.w - n.sk * t;
            if (p[0] < xl + 2 || p[0] > xr - 2) out(nom(q.e) + ' sale del paralelogramo ' + id);
          });
        }
      }));
    });
    // 2b. texto contra texto
    for (let i = 0; i < T.length; i++) for (let j = i + 1; j < T.length; j++) {
      if (T[i].e.contains(T[j].e) || T[j].e.contains(T[i].e)) continue;
      if (T[i].rs.some(a => T[j].rs.some(b => inter(a, b, 0.5)))) out(nom(T[i].e) + ' solapa ' + nom(T[j].e));
    }
    // contenedores con texto oculto
    Array.prototype.forEach.call(document.querySelectorAll('.marco-cab, .panel, .etq'), e => {
      if (e.scrollHeight > e.clientHeight + 2 || e.scrollWidth > e.clientWidth + 2) out((e.id || e.className) + ' contenido oculto');
    });

    // 4. flechas: diagonales, nodos que cruzan, destino
    D.flechas.forEach(a => {
      const nom2 = a.de + '>' + a.a;
      a.segs.forEach(s => {
        if (Math.abs(s.x1 - s.x2) > 0.01 && Math.abs(s.y1 - s.y2) > 0.01) out('flecha ' + nom2 + ' con tramo diagonal');
        Object.keys(D.nodos).forEach(id => {
          if (id === a.de || id === a.a) return;
          if (segRect(s, fp(D.nodos[id]), 0)) out('flecha ' + nom2 + ' cruza el nodo ' + id);
        });
      });
      const t = D.nodos[a.a], r = fp(t);
      const dx = Math.max(r.l - a.T.x, 0, a.T.x - r.r), dy = Math.max(r.t - a.T.y, 0, a.T.y - r.b);
      if (Math.hypot(dx, dy) > 1 || Math.hypot(a.E.x - a.T.x, a.E.y - a.T.y) < GAP_PUNTA - 0.5) out('flecha ' + nom2 + ' no llega al destino');
    });
    // 3. texto del lienzo contra líneas (incluye etiquetas y la propia)
    T.forEach(q => q.rs.forEach(r => segs.forEach(s => { if (segRect(s, r, 2)) out('línea ' + s.a.de + '>' + s.a.a + ' pasa por texto ' + nom(q.e)); })));
    // etiquetas contra nodos
    D.etqs.forEach(q => {
      const rr = { l: q.x, t: q.y, r: q.x + q.w, b: q.y + q.h };
      Object.keys(D.nodos).forEach(id => { if (inter(rr, fp(D.nodos[id]), 0)) out('etiqueta ' + q.el.textContent + ' solapa nodo ' + id); });
    });
    // texto contra los bordes de límite, carriles y marcos
    const bordes = [];
    D.limites.forEach(b => bordes.push(['limite', b]));
    D.carriles.forEach(b => bordes.push(['carril ' + b.id, b]));
    D.marcos.forEach(b => bordes.push(['marco ' + b.id, b]));
    bordes.forEach(p => {
      const b = p[1], k = 2;
      const lados = [{ l: b.x - k, r: b.x + b.w + k, t: b.y - k, b: b.y + k }, { l: b.x - k, r: b.x + b.w + k, t: b.y + b.h - k, b: b.y + b.h + k },
        { l: b.x - k, r: b.x + k, t: b.y - k, b: b.y + b.h + k }, { l: b.x + b.w - k, r: b.x + b.w + k, t: b.y - k, b: b.y + b.h + k }];
      T.forEach(q => q.rs.forEach(r => { if (lados.some(s => inter(r, s, 0))) out('texto ' + nom(q.e) + ' sobre el borde de ' + p[0]); }));
    });
    // paralelas y cruces
    for (let i = 0; i < D.flechas.length; i++) for (let j = i + 1; j < D.flechas.length; j++) {
      const A = D.flechas[i], B = D.flechas[j];
      const comun = A.de === B.de || A.a === B.a || A.de === B.a || A.a === B.de;
      if (!comun) A.segs.forEach(s => B.segs.forEach(t => {
        const sh = Math.abs(s.y1 - s.y2) < 0.01, th = Math.abs(t.y1 - t.y2) < 0.01;
        if (sh && th) { const ov = Math.min(Math.max(s.x1, s.x2), Math.max(t.x1, t.x2)) - Math.max(Math.min(s.x1, s.x2), Math.min(t.x1, t.x2)); if (ov > 1 && Math.abs(s.y1 - t.y1) < 24) out('paralelas ' + A.de + '>' + A.a + ' y ' + B.de + '>' + B.a + ' a ' + Math.abs(s.y1 - t.y1).toFixed(0) + ' px'); }
        if (!sh && !th) { const ov = Math.min(Math.max(s.y1, s.y2), Math.max(t.y1, t.y2)) - Math.max(Math.min(s.y1, s.y2), Math.min(t.y1, t.y2)); if (ov > 1 && Math.abs(s.x1 - t.x1) < 24) out('paralelas ' + A.de + '>' + A.a + ' y ' + B.de + '>' + B.a + ' a ' + Math.abs(s.x1 - t.x1).toFixed(0) + ' px'); }
      }));
      const c1 = cruces(A, B);
      if (c1.length && !((A.hueco || []).indexOf(j) >= 0 || (B.hueco || []).indexOf(i) >= 0)) out('cruce sin puente ' + A.de + '>' + A.a + ' x ' + B.de + '>' + B.a);
    }
    // puertos
    const pts = {};
    D.flechas.forEach(a => {
      [[a.de, a.ds, a.S, a.sp], [a.a, a.as, a.T]].forEach(p => { if (p[3]) return; const k = p[0] + p[1]; (pts[k] = pts[k] || []).push(vert(p[1]) ? p[2].x : p[2].y); });
    });
    Object.keys(pts).forEach(k => { const v = pts[k].slice().sort((a, b) => a - b); for (let i = 1; i < v.length; i++) { const d = v[i] - v[i - 1]; if (d > 0.5 && d < 16) out('puertos a ' + d.toFixed(0) + ' px en ' + k); } });
    // 3 nodos. separación de 40 px y holgura en carril
    const ids = Object.keys(D.nodos);
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const a = fp(D.nodos[ids[i]]), b = fp(D.nodos[ids[j]]);
      const dx = Math.max(a.l - b.r, b.l - a.r, 0), dy = Math.max(a.t - b.b, b.t - a.b, 0);
      const d = Math.hypot(dx, dy);
      if (d < 40) out('nodos ' + ids[i] + ' y ' + ids[j] + ' a ' + d.toFixed(0) + ' px');
    }
    ids.forEach(id => {
      const n = D.nodos[id], r = fp(n);
      if (n.carril) { const c = D.carriles.filter(k => k.id === n.carril)[0]; if (r.l < c.x + 36 + 24 || r.t < c.y + 24 || r.r > c.x + c.w - 24 || r.b > c.y + c.h - 24) out('nodo ' + id + ' a menos de 24 px del borde de ' + n.carril); }
      if (n.marco) { const c = D.marcos.filter(k => k.id === n.marco)[0]; if (r.l < c.x + 24 || r.t < c.y + 24 || r.r > c.x + c.w - 24 || r.b > c.y + c.h - 24) out('nodo ' + id + ' a menos de 24 px del marco'); }
    });
    // letra mínima y fuera del lienzo
    Array.prototype.forEach.call(lienzo.querySelectorAll('*'), e => {
      const propio = Array.prototype.some.call(e.childNodes, c => c.nodeType === 3 && c.textContent.trim());
      if (!propio) return;
      const fs = parseFloat(getComputedStyle(e).fontSize);
      if (fs < 16) out(nom(e) + ' letra de ' + fs + ' px');
      if (e.classList.contains('titulo') && fs < 18) out(nom(e) + ' nombre de nodo menor de 18 px');
    });
    Array.prototype.forEach.call(lienzo.querySelectorAll('.nodo, .carril, .etq, .tx, .panel'), e => {
      const r = e.getBoundingClientRect();
      if (r.left < L.left - 0.5 || r.right > L.right + 0.5 || r.top < L.top - 0.5 || r.bottom > L.bottom + 0.5) out(nom(e) + ' fuera del lienzo');
    });
    // alto declarado
    const meta = document.querySelector('meta[name="diagrama-tamano"]').content.split('x');
    if (Math.abs(lienzo.offsetHeight - parseInt(meta[1], 10)) > 2) out('alto declarado ' + meta[1] + ' y real ' + lienzo.offsetHeight);
    // vacío por carril (celdas de 20 px; ocupada si un nodo a 30 px, una línea a 20 px o un texto a 10 px)
    D.carriles.forEach(c => {
      let tot = 0, vac = 0;
      for (let x = c.x + 36 + 10; x < c.x + c.w; x += 20) for (let y = c.y + 10; y < c.y + c.h; y += 20) {
        tot++;
        const p = { l: x, r: x, t: y, b: y };
        let oc = ids.some(id => { const r = fp(D.nodos[id]); return x >= r.l - 30 && x <= r.r + 30 && y >= r.t - 30 && y <= r.b + 30; });
        if (!oc) oc = segs.some(s => { const l = Math.min(s.x1, s.x2) - 20, r = Math.max(s.x1, s.x2) + 20, t = Math.min(s.y1, s.y2) - 20, b = Math.max(s.y1, s.y2) + 20; return x >= l && x <= r && y >= t && y <= b; });
        if (!oc) oc = T.some(q => q.rs.some(r => x >= r.l - 10 && x <= r.r + 10 && y >= r.t - 10 && y <= r.b + 10));
        if (!oc) oc = D.marcos.some(m => y < m.y + 56 && y > m.y && x > m.x && x < m.x + m.w);
        if (!oc) vac++;
      }
      const pc = vac / tot;
      c.vacio = pc;
      if (pc > 0.30) out('carril ' + c.id + ' con ' + Math.round(pc * 100) + '% vacío');
    });

    const v = document.getElementById('verificacion');
    v.textContent = P.length ? P.join(' | ') : 'OK';
    v.setAttribute('data-alto', lienzo.scrollHeight);
    v.setAttribute('data-paneles', Array.prototype.map.call(lienzo.querySelectorAll('.panel'), e => Math.round(e.getBoundingClientRect().top - L.top) + '+' + e.offsetHeight + '/' + e.scrollHeight).join(','));
    v.setAttribute('data-doc', lienzo.offsetHeight + '/' + document.documentElement.scrollHeight);
    v.setAttribute('data-vacio', D.carriles.map(c => c.id + ':' + Math.round((c.vacio || 0) * 100)).join(','));
  }

  window.Diagrama = D;
})();
