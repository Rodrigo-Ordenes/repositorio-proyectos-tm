// Uso: abrir el sitio, pegar este archivo en la consola de DevTools (pestaña Console) y revisar el resultado.
// Contrast audit of the rendered page: every visible text run against its effective background (WCAG 2.2 + APCA),
// plus 3:1 non-text contrast for form-control borders.
(() => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const blend = (top, bottom) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + bottom[i] * (1 - a)).concat(1); };
  const lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const lum = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const apca = (txt, bg) => {
    const Y = c => { let y = 0.2126729 * (c[0] / 255) ** 2.4 + 0.7151522 * (c[1] / 255) ** 2.4 + 0.0721750 * (c[2] / 255) ** 2.4; return y < 0.022 ? y + (0.022 - y) ** 1.414 : y; };
    const yt = Y(txt), yb = Y(bg); if (Math.abs(yb - yt) < 0.0005) return 0;
    if (yb > yt) { const s = (yb ** 0.56 - yt ** 0.57) * 1.14; return s < 0.1 ? 0 : (s - 0.027) * 100; }
    const s = (yb ** 0.65 - yt ** 0.62) * 1.14; return s > -0.1 ? 0 : (s + 0.027) * 100;
  };
  const bgOf = el => { const layers = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } } let base = [255, 255, 255, 1]; for (let i = layers.length - 1; i >= 0; i--) base = blend(layers[i], base); return base; };
  const hidden = el => { for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return true; if (s.clip === 'rect(0px, 0px, 0px, 0px)' || (e.offsetWidth <= 1 && e.offsetHeight <= 1 && s.overflow === 'hidden')) return true; } return false; };
  const name = el => (el.id ? '#' + el.id : el.tagName.toLowerCase()) + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '');
  const seen = new Map(), fails = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode; if (!node.textContent.trim()) continue;
    const el = node.parentElement; if (!el || hidden(el)) continue;
    const s = getComputedStyle(el), fg0 = parse(s.color); if (!fg0) continue;
    const bg = bgOf(el), fg = fg0[3] < 1 ? blend(fg0, bg) : fg0;
    const size = parseFloat(s.fontSize), bold = Number(s.fontWeight) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const r = ratio(fg, bg), lc = Math.abs(apca(fg, bg));
    const key = name(el) + '|' + s.color + '|' + bg.join(',');
    if (seen.has(key)) continue; seen.set(key, 1);
    const need = large ? 3 : 4.5;
    const lcNeed = size >= 24 ? 45 : size >= 16 ? 60 : size >= 14 ? 75 : 90;
    if (r < need || lc < lcNeed - 15) fails.push({ el: name(el), text: node.textContent.trim().slice(0, 40), fg: s.color, bg: `rgb(${bg.slice(0, 3).map(Math.round).join(',')})`, size, ratio: +r.toFixed(2), need, apca: Math.round(lc), apcaTarget: lcNeed });
  }
  const borders = [];
  document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea, .button.secondary').forEach(el => {
    if (hidden(el)) return; const s = getComputedStyle(el), b = parse(s.borderTopColor); if (!b || parseFloat(s.borderTopWidth) === 0) return;
    const outside = bgOf(el.parentElement), r = ratio(b[3] < 1 ? blend(b, outside) : b, outside);
    if (r < 3) borders.push({ el: name(el), border: s.borderTopColor, ratio: +r.toFixed(2) });
  });
  return { page: location.pathname, textChecked: seen.size, textFails: fails, borderFails: [...new Map(borders.map(b => [b.el + b.border, b])).values()] };
})()
