"""Verify the palette: WCAG 2.2 ratios, APCA Lc, and colour-vision-deficiency separation (Machado et al. 2009)."""
import json, sys

def rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
def lin(v):
    v /= 255; return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def lum(c): r, g, b = (lin(x) for x in c); return 0.2126 * r + 0.7152 * g + 0.0722 * b
def ratio(a, b):
    x, y = sorted([lum(rgb(a)), lum(rgb(b))], reverse=True); return (x + 0.05) / (y + 0.05)
def apca(txt, bg):
    def Y(c):
        y = 0.2126729 * (c[0] / 255) ** 2.4 + 0.7151522 * (c[1] / 255) ** 2.4 + 0.0721750 * (c[2] / 255) ** 2.4
        return y + (0.022 - y) ** 1.414 if y < 0.022 else y
    yt, yb = Y(rgb(txt)), Y(rgb(bg))
    if abs(yb - yt) < 0.0005: return 0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14; return 0 if s < 0.1 else (s - 0.027) * 100
    s = (yb ** 0.65 - yt ** 0.62) * 1.14; return 0 if s > -0.1 else (s + 0.027) * 100

MACHADO = {  # severity 1.0, applied to linear RGB
    "protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}
def simulate(h, m):
    l = [lin(x) for x in rgb(h)]
    out = [max(0, min(1, sum(m[i][j] * l[j] for j in range(3)))) for i in range(3)]
    enc = lambda v: v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return "#" + "".join(f"{round(enc(v) * 255):02x}" for v in out)
def lab(h):
    r, g, b = (lin(x) for x in rgb(h))
    X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047; Yv = 0.2126 * r + 0.7152 * g + 0.0722 * b; Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(Yv) - 16, 500 * (f(X) - f(Yv)), 200 * (f(Yv) - f(Z))
def de(a, b): return sum((x - y) ** 2 for x, y in zip(lab(a), lab(b))) ** 0.5

P = json.loads(open(sys.argv[1] if len(sys.argv) > 1 else __file__.replace("verificar_paleta.py", "paleta.json"), encoding="utf-8").read())
rows = []
for theme, t in P.items():
    pairs = [  # (foreground, background, minimum WCAG ratio, minimum APCA Lc, use)
        ("ink", "canvas", 7, 90, "texto principal"), ("ink", "surface", 7, 90, "texto principal en tarjetas"),
        ("ink-2", "canvas", 4.5, 75, "texto secundario"), ("ink-2", "surface", 4.5, 75, "texto secundario"), ("ink-2", "surface-2", 4.5, 75, "texto secundario en paneles"),
        ("ink-3", "canvas", 4.5, 60, "ayuda y metadatos"), ("ink-3", "surface", 4.5, 60, "ayuda y metadatos"), ("ink-3", "surface-2", 4.5, 60, "ayuda en paneles"),
        ("forest", "surface", 4.5, 75, "enlaces y acentos Incentiva"), ("forest", "forest-soft", 4.5, 60, "etiqueta Incentiva"), ("forest", "canvas", 4.5, 60, "pestaña activa"),
        ("plum", "surface", 4.5, 75, "acentos Innova"), ("plum", "plum-soft", 4.5, 60, "etiqueta Innova"), ("plum", "canvas", 4.5, 60, "pestaña activa Innova"),
        ("on-accent", "forest", 4.5, 75, "texto de botón Incentiva"), ("on-accent", "plum", 4.5, 75, "texto de botón Innova"),
        ("success", "success-soft", 4.5, 60, "estado publicado"), ("danger", "danger-soft", 4.5, 60, "estado devuelto"), ("danger", "surface", 4.5, 60, "mensajes de error"),
        ("warning", "warning-soft", 4.5, 60, "avisos"), ("gold-text", "gold-soft", 4.5, 60, "pendiente"),
        ("control", "surface", 3, 0, "borde de campos (1.4.11)"), ("control", "canvas", 3, 0, "borde de campos sobre fondo"), ("control", "surface-2", 3, 0, "borde de campos en paneles"),
        ("focus", "canvas", 3, 0, "anillo de foco"), ("focus", "surface", 3, 0, "anillo de foco"), ("focus", "forest-soft", 3, 0, "anillo de foco en zona Incentiva"),
    ]
    for fg, bg, need, lc_need, use in pairs:
        r, lc = ratio(t[fg], t[bg]), abs(apca(t[fg], t[bg]))
        rows.append((theme, use, fg, bg, t[fg], t[bg], round(r, 2), need, round(lc), lc_need, r >= need and lc >= lc_need))
for r in rows:
    print(("OK  " if r[-1] else "BAJO") + f" {r[0]:6} {r[1]:38} {r[4]} / {r[5]}  {r[6]:>5}:1 (≥{r[7]})  Lc {r[8]:>3} (≥{r[9]})")
for theme, t in P.items():
    print(f"\n{theme}: separación Incentiva/Innova y estados (ΔE CIE76; ≥20 se distingue con claridad)")
    for a, b in (("forest", "plum"), ("success", "danger")):
        line = f"  {a}/{b}: normal ΔE {de(t[a], t[b]):.0f}"
        for name, m in MACHADO.items():
            line += f" · {name} {de(simulate(t[a], m), simulate(t[b], m)):.0f}"
        print(line + f" · diferencia de luminosidad L* {abs(lab(t[a])[0] - lab(t[b])[0]):.0f}")
print("\nfallas:", sum(not r[-1] for r in rows))
