"""Процедурные пиксельные спрайты питомца. Чистый Python, без Kivy.

Персонаж собирается из прямоугольников (ноги, торс, руки, голова, одежда),
размеры и экипировка зависят от формы (tier 0..4). Позже любую форму можно
заменить на нарисованный вручную спрайт, не трогая остальной код:
нужно лишь вернуть тот же объект Frame.
"""
from functools import lru_cache

GW, GH = 32, 48      # размер холста в «пикселях арта»
CX = GW // 2         # вертикальная ось персонажа
FOOT = 1             # строка, на которой стоят ноги (0 — для контура)

ANIMS = {"idle": 2, "walk": 4, "run": 4, "fly": 2, "eat": 4, "held": 2, "fall": 2, "happy": 2}
FPS = {"idle": 2, "walk": 6, "run": 12, "fly": 6, "eat": 5, "held": 6, "fall": 6, "happy": 6}


def C(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def shade(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k), c[3])


OUT = C("#1d1230")
EYE = C("#1d1a2b")
MOUTH = C("#7a2b3a")
TONGUE = C("#d9606f")
GOLD = C("#f2c94c")
GOLD_L = C("#ffe38a")
STEEL = C("#aab4c6")
STEEL_L = C("#d3dbe8")

# геометрия форм: H — рост, tw — ширина торса, hw — головы, lw — ноги, aw — руки
TIERS = [
    dict(H=17, tw=4, hw=5, lw=2, aw=1, gap=0),
    dict(H=21, tw=5, hw=6, lw=2, aw=1, gap=1),
    dict(H=26, tw=7, hw=7, lw=3, aw=2, gap=1),
    dict(H=31, tw=9, hw=8, lw=3, aw=2, gap=1),
    dict(H=36, tw=11, hw=10, lw=4, aw=3, gap=1),
]

STYLE = [
    dict(skin=C("#f0cdb0"), hair=C("#6b4a33"), shirt=C("#9a9aa6"), sleeve=2, sleeve_c=C("#9a9aa6"),
         glove=0, glove_c=None, pants=C("#7a5a43"), pants_k=0.5, shoe_h=0, shoe_c=None),
    dict(skin=C("#ffd2a8"), hair=C("#3b2a22"), shirt=C("#4a7be0"), sleeve=3, sleeve_c=C("#4a7be0"),
         glove=0, glove_c=None, pants=C("#bfa070"), pants_k=1.0, shoe_h=2, shoe_c=C("#ececf2")),
    dict(skin=C("#ffd2a8"), hair=C("#1c1c2b"), shirt=C("#2f3146"), sleeve=0, sleeve_c=None,
         glove=2, glove_c=C("#6b4528"), pants=C("#46465c"), pants_k=1.0, shoe_h=3, shoe_c=C("#503323")),
    dict(skin=C("#ffd2a8"), hair=C("#d9dce8"), shirt=STEEL, sleeve=3, sleeve_c=STEEL,
         glove=3, glove_c=STEEL, pants=C("#373750"), pants_k=1.0, shoe_h=3, shoe_c=C("#2a2a35")),
    dict(skin=C("#ffd2a8"), hair=C("#f4e8c0"), shirt=C("#7a3cb0"), sleeve=3, sleeve_c=GOLD,
         glove=3, glove_c=GOLD, pants=C("#46246a"), pants_k=1.0, shoe_h=4, shoe_c=C("#4a3418")),
]


class Frame:
    __slots__ = ("w", "h", "rgba", "mouth", "bbox")

    def __init__(self, w, h, rgba, mouth, bbox):
        self.w, self.h, self.rgba, self.mouth, self.bbox = w, h, rgba, mouth, bbox


class Grid:
    def __init__(self):
        self.p = [[None] * GW for _ in range(GH)]

    def set(self, x, y, c):
        if 0 <= x < GW and 0 <= y < GH:
            self.p[y][x] = c

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.set(x, y, c)


def pose_for(anim, frame, ll):
    p = dict(bob=0, dxl=0, dxr=0, dal=0, dar=0, arms="hang", mouth="closed",
             lean=0, tuck=False, flap=frame % 2, blink=False)
    k = max(1, round(ll * 0.28))
    if anim == "idle":
        p["bob"] = frame % 2
        p["blink"] = frame % 2 == 1
    elif anim in ("walk", "run"):
        kk = k if anim == "walk" else max(2, round(k * 1.7))
        seq = [(kk, -kk), (0, 0), (-kk, kk), (0, 0)][frame % 4]
        p["dxl"], p["dxr"] = seq
        p["dal"], p["dar"] = int(-seq[0] / 2), int(-seq[1] / 2)
        p["bob"] = 1 if frame % 2 == 1 else 0
        p["lean"] = 1 if anim == "run" else 0
    elif anim == "fly":
        p.update(arms="up", tuck=True, bob=frame % 2)
    elif anim == "eat":
        mouth = ["open", "closed", "open", "closed"][frame % 4]
        p.update(arms="mouth", mouth=mouth, bob=1 if mouth == "closed" else 0)
    elif anim in ("held", "fall"):
        p.update(arms="up", mouth="o")
        p["dxl"], p["dxr"] = (1, -1) if frame % 2 else (-1, 1)
    elif anim == "happy":
        p.update(arms="up", mouth="open", bob=frame % 2)
    return p


def build(tier, anim, frame, face=1):
    t, st = TIERS[tier], STYLE[tier]
    H, tw, hw, lw, aw, gap = t["H"], t["tw"], t["hw"], t["lw"], t["aw"], t["gap"]
    ll, hh = round(H * 0.32), round(H * 0.30)
    th = H - ll - hh
    p = pose_for(anim, frame, ll)
    g = Grid()

    bd = -face                       # «назад» относительно взгляда
    b = p["bob"]
    x0 = CX - tw // 2
    x1 = x0 + tw
    span = 2 * lw + gap
    lx0 = CX - span // 2
    yb = FOOT + (ll // 3 if p["tuck"] else 0)   # низ ног
    yt0 = FOOT + ll + b                         # низ торса
    yt1 = yt0 + th
    hy0, hy1 = yt1, yt1 + hh
    hx0 = CX - hw // 2 + p["lean"] * face
    hx1 = hx0 + hw
    al = max(3, round(th * 0.8))                # длина руки
    flap = p["flap"]

    # ---------- плащ (за спиной) ----------
    if tier == 4:
        cape, cape_d = C("#6e2a9a"), C("#4f1d73")
        flow = 0.5 if anim == "fly" else 0.12
        for y in range(FOOT + 2, yt1):
            sh = int((yt1 - 1 - y) * flow) + (flap if y < yt1 - th else 0)
            cs = bd * sh
            g.rect(x0 - 1 + cs, y, x1 + 1 + cs, y + 1, cape)
            g.set(x0 - 1 + cs + (tw + 2) // 2, y, cape_d)

    # ---------- ноги ----------
    pl = -(-int(st["pants_k"] * ll * 100) // 100) if st["pants_k"] < 1 else ll  # ceil
    pl = max(pl, 1)
    ymid = yb + (yt0 - yb) // 2
    for x_leg, dx in ((lx0, p["dxl"]), (lx0 + lw + gap, p["dxr"])):
        for y in range(yb, yt0):
            kt = yt0 - 1 - y
            if st["shoe_c"] is not None and y - yb < st["shoe_h"]:
                col = st["shoe_c"]
            elif kt < pl:
                col = st["pants"]
            else:
                col = st["skin"]
            sx = x_leg + (dx if y < ymid else 0)
            g.rect(sx, y, sx + lw, y + 1, col)

    # ---------- торс и одежда ----------
    if tier == 0:
        g.rect(x0, yt0, x1, yt1, st["shirt"])
        for x in range(x0, x1):                       # рваный подол
            if (x - x0) % 2 == 0:
                g.set(x, yt0, st["skin"])
        g.set(x0 + 1, yt1 - 3, st["skin"])            # дырка на груди
    elif tier == 1:
        g.rect(x0, yt0, x1, yt1, st["shirt"])
        g.rect(CX - 1, yt1 - 1, CX + 1, yt1, st["skin"])
    elif tier == 2:
        g.rect(x0, yt0, x1, yt1, st["shirt"])
        vest = C("#8a5632")
        pw = max(2, tw // 3)
        g.rect(x0, yt0 + 1, x0 + pw, yt1, vest)
        g.rect(x1 - pw, yt0 + 1, x1, yt1, vest)
        g.rect(x0, yt0, x1, yt0 + 1, C("#28202a"))     # ремень
        g.rect(CX - 1, yt0, CX + 1, yt0 + 1, GOLD)
    elif tier == 3:
        g.rect(x0, yt0, x1, yt1, st["shirt"])
        g.rect(x0, yt1 - 1, x1, yt1, STEEL_L)
        g.rect(x1 - 1, yt0, x1, yt1 - 1, shade(STEEL, 0.75))
        g.rect(x0, yt0, x1, yt0 + 1, C("#3c3c52"))
        g.rect(CX - 1, yt0, CX + 1, yt0 + 1, STEEL_L)
        g.rect(CX - 1, yt1 - 4, CX + 1, yt1 - 2, C("#d23c48"))   # эмблема
    else:
        g.rect(x0, yt0, x1, yt1, st["shirt"])
        g.rect(x0, yt1 - 1, x1, yt1, GOLD)
        g.rect(x0, yt0, x0 + 1, yt1, GOLD)
        g.rect(x1 - 1, yt0, x1, yt1, GOLD)
        g.rect(x0, yt0, x1, yt0 + 2, GOLD)
        g.rect(CX - 1, yt1 - 6, CX + 1, yt1 - 4, C("#52e0ff"))   # светящийся камень
        g.set(CX - 1, yt1 - 4, C("#c9f6ff"))

    # ---------- руки ----------
    def arm(side, mode):
        ax0 = x0 - aw if side < 0 else x1
        if mode == "up" or (mode == "mouth" and side == face):
            ln = al if mode == "up" else max(3, al * 3 // 4)
            ax = ax0 + side
            for i in range(ln):
                y = yt1 - 2 + i
                m = ln - 1 - i                     # расстояние от ладони (она сверху)
                _arm_cell(ax, y, m, ln - 1 - m)
        else:
            d = p["dal"] if side < 0 else p["dar"]
            for i in range(al):
                y = yt1 - 1 - i
                m = al - 1 - i                     # ладонь внизу
                sx = ax0 + (d if y < yt1 - al // 2 else 0)
                _arm_cell(sx, y, m, al - 1 - m)

    def _arm_cell(ax, y, m, s):
        if st["glove"] and m < st["glove"]:
            col = st["glove_c"]
        elif st["sleeve"] and s < st["sleeve"]:
            col = st["sleeve_c"]
        else:
            col = st["skin"]
        g.rect(ax, y, ax + aw, y + 1, col)

    arm(-1, p["arms"])
    arm(+1, p["arms"])

    # наплечники
    if tier >= 3:
        pad = STEEL_L if tier == 3 else GOLD_L
        padd = shade(STEEL, 0.8) if tier == 3 else shade(GOLD, 0.85)
        for xs in (x0 - aw - 1, x1 - 1):
            g.rect(xs, yt1 - 3, xs + aw + 2, yt1, padd)
            g.rect(xs, yt1 - 1, xs + aw + 2, yt1, pad)

    # ---------- голова ----------
    g.rect(hx0, hy0, hx1, hy1, st["skin"])
    if tier >= 1:
        g.rect(hx1 - 1, hy0, hx1, hy1, C("#e6b78d"))

    # волосы
    hair = st["hair"]
    if tier == 0:
        g.rect(hx0, hy1 - 1, hx1, hy1, hair)
        g.set(hx0 + 1, hy1, hair)
        g.set(hx0 + 3, hy1, hair)
        g.set(hx0 + (0 if bd < 0 else hw - 1), hy1 - 2, hair)
    elif tier == 1:
        g.rect(hx0, hy1 - 2, hx1, hy1, hair)
        g.rect(hx0, hy1 - 3, hx1, hy1 - 2, C("#e0443c"))        # повязка
        tx = hx0 - 1 if bd < 0 else hx1
        g.set(tx, hy1 - 3, C("#e0443c"))
        g.set(tx + bd, hy1 - 3 - flap, C("#e0443c"))
    elif tier == 2:
        g.rect(hx0, hy1 - 2, hx1, hy1, hair)
        for sx in (hx0 + 1, hx0 + hw // 2, hx1 - 2):
            g.rect(sx, hy1, sx + 1, hy1 + 2, hair)
        g.set(hx0 + hw // 2, hy1 + 1, C("#4a5cff"))
        g.rect(hx0, hy0 + hh // 2, hx0 + 1, hy1 - 2, hair)
        g.rect(hx1 - 1, hy0 + hh // 2, hx1, hy1 - 2, hair)
    else:
        g.rect(hx0, hy1 - 2, hx1, hy1, hair)
        g.rect(hx0, hy0 + 1, hx0 + 1, hy1 - 2, hair)
        g.rect(hx1 - 1, hy0 + 1, hx1, hy1 - 2, hair)
        bx = hx0 - 2 if bd < 0 else hx1 + 1
        for i in range(hh - 2):                                 # хвост / развевающиеся пряди
            g.rect(bx + bd * (flap if i < 3 else 0) * (1 if bd < 0 else -1) * -1, hy1 - 3 - i, bx + 2, hy1 - 2 - i, hair) \
                if False else g.rect(bx, hy1 - 3 - i, bx + 2, hy1 - 2 - i, hair)

    # лицо
    ex_c = hx0 + hw // 2
    e = max(1, hw // 3)
    fs = face if hw >= 5 else 0
    ey = hy0 + max(2, hh // 2)
    eh = 1 if (hh <= 6 or p["blink"] or p["mouth"] == "open") else 2
    exl = max(hx0, min(hx1 - 1, ex_c - e + fs))
    exr = max(hx0, min(hx1 - 1, ex_c + e + fs))
    for ex in (exl, exr):
        g.rect(ex, ey, ex + 1, ey + eh, EYE)
    if tier >= 2:
        g.rect(exl, ey + eh, min(exl + 2, hx1), ey + eh + 1, hair if tier != 4 else shade(hair, 0.6))
        g.rect(max(exr - 1, hx0), ey + eh, exr + 1, ey + eh + 1, hair if tier != 4 else shade(hair, 0.6))
    my = hy0 + max(1, hh // 4)
    mw = 1 if hh <= 5 else (2 if hh <= 7 else 3)
    mx = max(hx0, min(hx1 - mw, ex_c - mw // 2 + (fs if hw >= 6 else 0)))
    mt = p["mouth"]
    if mt == "closed":
        g.rect(mx, my, mx + mw, my + 1, MOUTH)
    elif mt in ("open", "o"):
        ow = max(2 if mt == "open" else 1, mw)
        mx = max(hx0, min(hx1 - ow, mx))
        g.rect(mx, my, mx + ow, my + 2, MOUTH)
        if hh >= 8 and mt == "open":
            g.set(mx + ow // 2, my, TONGUE)
    mouth_pos = (mx + mw / 2.0 if mt == "closed" else mx + 1.0, my + 0.5)

    # ---------- аксессуары поверх ----------
    if tier == 3:
        sc = C("#d23c48")
        g.rect(x0 - 1, yt1 - 2, x1 + 1, yt1, sc)
        tx = x1 + 1 if bd > 0 else x0 - 3
        for i in range(4):
            sh = (flap if i >= 2 else 0) * bd
            g.rect(tx + sh, yt1 - 3 - i, tx + sh + 2, yt1 - 2 - i, sc)
    if tier == 4:
        g.rect(hx0 + 1, hy1, hx1 - 1, hy1 + 2, GOLD)
        for sx, sh in ((hx0 + 1, 2), (hx0 + hw // 2, 3), (hx1 - 2, 2)):
            g.rect(sx, hy1 + 2, sx + 1, hy1 + sh, GOLD)
        g.set(hx0 + hw // 2, hy1, C("#e0344c"))
        g.set(hx0 + hw // 2, hy1 + 2, GOLD_L)

    return _finalize(g, mouth_pos)


def _finalize(g, mouth):
    src = g.p
    out = [row[:] for row in src]
    for y in range(GH):
        for x in range(GW):
            if src[y][x] is None:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GW and 0 <= ny < GH and src[ny][nx] is not None:
                        out[y][x] = OUT
                        break
    buf = bytearray()
    xs, ys = [], []
    for y in range(GH):                       # строка 0 — низ (так её ждёт OpenGL)
        for x in range(GW):
            c = out[y][x]
            if c is None:
                buf += b"\x00\x00\x00\x00"
            else:
                buf += bytes(c)
                xs.append(x)
                ys.append(y)
    bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    return Frame(GW, GH, bytes(buf), mouth, bbox)


@lru_cache(maxsize=None)
def frame(tier, anim, idx, face):
    return build(tier, anim, idx % ANIMS[anim], face)


def meta(tier):
    """Габариты формы (по стоящей позе)."""
    f = frame(tier, "idle", 0, 1)
    return f
