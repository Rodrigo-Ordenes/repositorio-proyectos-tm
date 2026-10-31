// Auditoría de contraste de varias vistas, en modo claro y oscuro.
// Uso: entrar al sitio como administración, abrir la consola de DevTools, pegar este archivo y esperar el resultado.
// Recorre las vistas con la navegación interna (go), revisa cada texto visible contra su fondo efectivo (WCAG 2.2 AA),
// el texto y las barras de los gráficos, y los bordes de los campos (3:1).
(async () => {
  const audit = () => {
    const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
    const blend = (t, b) => { const a = t[3]; return [0, 1, 2].map(i => t[i] * a + b[i] * (1 - a)).concat(1); };
    const lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    const lum = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
    const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
    const rootBg = parse(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1];
    const bgOf = el => { const L = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c[3] > 0) { L.push(c); if (c[3] >= 1) break; } } let b = rootBg; for (let i = L.length - 1; i >= 0; i--) b = blend(L[i], b); return b; };
    const hidden = el => { for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return true; if (s.clip === 'rect(0px, 0px, 0px, 0px)' || (e.offsetWidth <= 1 && e.offsetHeight <= 1 && s.overflow === 'hidden')) return true; } return false; };
    const seen = new Set(), fails = []; let n = 0;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const node = w.currentNode; if (!node.textContent.trim()) continue; const el = node.parentElement; if (!el || hidden(el) || el.closest('svg, .code-item.inactive')) continue;
      const s = getComputedStyle(el), f0 = parse(s.color); if (!f0) continue; const bg = bgOf(el), fg = f0[3] < 1 ? blend(f0, bg) : f0;
      const size = parseFloat(s.fontSize), bold = Number(s.fontWeight) >= 700, r = ratio(fg, bg), key = s.color + bg + size; if (seen.has(key)) continue; seen.add(key); n++;
      if (r < ((size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5)) fails.push(`${el.className || el.tagName} «${node.textContent.trim().slice(0, 30)}» ${r.toFixed(2)}:1`);
    }
    document.querySelectorAll('.bar-chart text').forEach(t => { const f = parse(getComputedStyle(t).fill), bg = bgOf(t.closest('svg')); if (f && ratio(f, bg) < 4.5) fails.push(`texto de gráfico ${ratio(f, bg).toFixed(2)}:1`); });
    document.querySelectorAll('.bar-chart rect').forEach(r => { const f = parse(getComputedStyle(r).fill), bg = bgOf(r.closest('svg')); if (f && ratio(f, bg) < 3) fails.push(`barra ${ratio(f, bg).toFixed(2)}:1`); });
    let borders = 0; document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea').forEach(el => { if (hidden(el)) return; const s = getComputedStyle(el), b = parse(s.borderTopColor); if (b && parseFloat(s.borderTopWidth) > 0 && ratio(b, bgOf(el.parentElement)) < 3) borders++; });
    return { n, fails, borders };
  };
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const views = [['portada', () => go('/')], ['Incentiva y guía', async () => { go('/incentiva'); await wait(400); document.querySelector('.toolkit').open = true; }],
    ['entrega', () => document.querySelector('[data-tab=deliver]').click()], ['foro', () => document.querySelector('[data-tab=forum]').click()],
    ['tiquetes', () => document.querySelector('[data-tab=tickets]').click()], ['Innova', () => go('/innova')],
    ['panel docente', async () => { go('/admin'); await wait(1200); document.querySelectorAll('details').forEach(d => d.open = true); }],
    ['informe', () => go('/informe/innova')], ['proyección', () => go('/proyeccion/incentiva')], ['kit', () => go('/kit/innova')],
    ['ayuda', () => go('/ayuda')], ['privacidad', () => go('/privacidad')]];
  const out = {};
  for (const theme of ['light', 'dark']) {
    document.documentElement.setAttribute('data-theme', theme);
    for (const [name, open] of views) { await open(); await wait(900); const r = audit(); out[`${theme} · ${name}`] = `${r.n} textos · ${r.fails.length} fallas · ${r.borders} bordes bajo 3:1${r.fails.length ? ' · ' + r.fails.join(' | ') : ''}`; }
  }
  document.documentElement.removeAttribute('data-theme');
  console.table(out);
  return out;
})();
