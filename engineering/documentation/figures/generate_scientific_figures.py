"""Generate the CALM scientific SVG figure suite.

The legacy recipes remain available as design inputs during the greenfield
documentation rebuild. They render to the ignored build tree until the new visual
system assigns an explicit public owner and committed asset path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "build" / "documentation-figures" / "scientific"
WIDTH = 1440
HEIGHT = 780


@dataclass
class SVG:
    title: str
    desc: str
    width: int = WIDTH
    height: int = HEIGHT
    body: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)

    def add(self, value: str) -> None:
        self.body.append(value)

    def add_def(self, value: str) -> None:
        self.defs.append(value)

    def text(
        self,
        x: float,
        y: float,
        value: str,
        cls: str = "body",
        *,
        anchor: str | None = None,
        transform: str | None = None,
    ) -> None:
        attrs = [f'x="{x:g}"', f'y="{y:g}"', f'class="{cls}"']
        if anchor:
            attrs.append(f'text-anchor="{anchor}"')
        if transform:
            attrs.append(f'transform="{transform}"')
        self.add(f"<text {' '.join(attrs)}>{escape(value)}</text>")

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        cls: str = "line",
        *,
        marker_end: str | None = None,
        marker_start: str | None = None,
    ) -> None:
        attrs = [
            f'x1="{x1:g}"',
            f'y1="{y1:g}"',
            f'x2="{x2:g}"',
            f'y2="{y2:g}"',
            f'class="{cls}"',
        ]
        if marker_end:
            attrs.append(f'marker-end="url(#{marker_end})"')
        if marker_start:
            attrs.append(f'marker-start="url(#{marker_start})"')
        self.add(f"<line {' '.join(attrs)}/>")

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        cls: str = "panel",
        *,
        rx: float = 16,
        extra: str = "",
    ) -> None:
        self.add(
            f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'rx="{rx:g}" class="{cls}" {extra}/>'
        )

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        cls: str,
        *,
        extra: str = "",
    ) -> None:
        self.add(
            f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" class="{cls}" {extra}/>'
        )

    def polygon(self, points: Iterable[tuple[float, float]], cls: str, *, extra: str = "") -> None:
        value = " ".join(f"{x:g},{y:g}" for x, y in points)
        self.add(f'<polygon points="{value}" class="{cls}" {extra}/>' )

    def path(self, d: str, cls: str, *, extra: str = "") -> None:
        self.add(f'<path d="{d}" class="{cls}" {extra}/>' )

    def render(self) -> str:
        defs = "\n".join(self.defs)
        body = "\n".join(self.body)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {self.width} {self.height}" data-calm-figure-version="2">
<title id="title">{escape(self.title)}</title>
<desc id="desc">{escape(self.desc)}</desc>
<style>{STYLE}</style>
<defs>
{COMMON_DEFS}
{defs}
</defs>
<rect class="canvas" width="{self.width}" height="{self.height}" rx="24"/>
{body}
</svg>
'''


STYLE = r'''
  .canvas { fill: #fcfdff; }
  .panel { fill: #f5f7fb; stroke: #cbd3e1; stroke-width: 1.6; }
  .panel-white { fill: #ffffff; stroke: #cbd3e1; stroke-width: 1.6; }
  .panel-a { fill: #e0f2f0; stroke: #007c78; stroke-width: 2; }
  .panel-b { fill: #e8eefb; stroke: #3563c4; stroke-width: 2; }
  .panel-violet { fill: #efeafb; stroke: #6c4ccf; stroke-width: 2; }
  .panel-amber { fill: #faead8; stroke: #c97619; stroke-width: 2; }
  .panel-red { fill: #f8e6e4; stroke: #b34e45; stroke-width: 2; }
  .ink { stroke: #172033; stroke-width: 2.2; fill: none; }
  .line { stroke: #536078; stroke-width: 1.8; fill: none; }
  .line-heavy { stroke: #172033; stroke-width: 3; fill: none; }
  .line-a { stroke: #007c78; stroke-width: 3; fill: none; }
  .line-b { stroke: #3563c4; stroke-width: 3; fill: none; }
  .line-violet { stroke: #6c4ccf; stroke-width: 3; fill: none; }
  .line-amber { stroke: #c97619; stroke-width: 3; fill: none; }
  .line-red { stroke: #b34e45; stroke-width: 3; fill: none; }
  .line-muted { stroke: #aab4c4; stroke-width: 1.3; fill: none; }
  .dash { stroke-dasharray: 9 7; }
  .dot { stroke-dasharray: 3 6; }
  .grid { stroke: #dce2ec; stroke-width: 1; }
  .grid-strong { stroke: #bdc7d7; stroke-width: 1.4; }
  .atom-a { fill: #ffffff; stroke: #007c78; stroke-width: 2.2; }
  .atom-b { fill: #ffffff; stroke: #3563c4; stroke-width: 2.2; }
  .atom-neutral { fill: #ffffff; stroke: #637087; stroke-width: 1.8; }
  .point-front { fill: #ffffff; stroke: #007c78; stroke-width: 3; }
  .point-dominated { fill: #ffffff; stroke: #b34e45; stroke-width: 3; }
  .point-selected { fill: #6c4ccf; stroke: #ffffff; stroke-width: 2; }
  .fill-a { fill: #62b9b4; fill-opacity: 0.34; stroke: #007c78; stroke-width: 2.4; }
  .fill-b { fill: #7f9ddd; fill-opacity: 0.28; stroke: #3563c4; stroke-width: 2.4; }
  .fill-violet { fill: #9e86df; fill-opacity: 0.25; stroke: #6c4ccf; stroke-width: 2.4; }
  .fill-amber { fill: #e5a153; fill-opacity: 0.28; stroke: #c97619; stroke-width: 2.4; }
  .fill-red { fill: #d88881; fill-opacity: 0.22; stroke: #b34e45; stroke-width: 2.4; }
  .surface-plane { fill: #e5a153; fill-opacity: 0.34; stroke: #c97619; stroke-width: 2.2; }
  .vacuum { fill: url(#vacuum-hatch); stroke: #aab4c4; stroke-width: 1.4; }
  .badge { fill: #ffffff; stroke: #bdc7d7; stroke-width: 1.4; }
  .title { font: 700 28px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #172033; letter-spacing: -0.25px; }
  .panel-title { font: 700 19px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #172033; }
  .label { font: 650 16px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #172033; }
  .body { font: 15.5px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #38445a; }
  .small { font: 13.5px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #5c677b; }
  .tiny { font: 12px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #68748a; }
  .math { font: italic 17px Cambria, Georgia, 'Times New Roman', serif; fill: #172033; }
  .math-small { font: italic 14px Cambria, Georgia, 'Times New Roman', serif; fill: #38445a; }
  .step { font: 700 14px Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #ffffff; }
  .white { fill: #ffffff; }
  .a-text { fill: #006e6a; }
  .b-text { fill: #2d55aa; }
  .violet-text { fill: #5f40b8; }
  .amber-text { fill: #a95d10; }
  .red-text { fill: #963d36; }
'''

COMMON_DEFS = r'''
  <marker id="arrow-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#172033"/></marker>
  <marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#536078"/></marker>
  <marker id="arrow-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#007c78"/></marker>
  <marker id="arrow-b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#3563c4"/></marker>
  <marker id="arrow-violet" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#6c4ccf"/></marker>
  <marker id="arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#c97619"/></marker>
  <marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#b34e45"/></marker>
  <pattern id="vacuum-hatch" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="12" height="12" fill="#f8fafc"/><line x1="0" y1="0" x2="0" y2="12" stroke="#dce2ec" stroke-width="3"/></pattern>
  <pattern id="dominated-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#f8e6e4" fill-opacity="0.55"/><line x1="0" y1="0" x2="0" y2="10" stroke="#d88881" stroke-width="2"/></pattern>
'''


def step_badge(svg: SVG, x: float, y: float, number: int, color: str) -> None:
    svg.circle(x, y, 16, "", extra=f'fill="{color}" stroke="none"')
    svg.text(x, y + 5, str(number), "step", anchor="middle")


def draw_panel_header(svg: SVG, x: float, y: float, number: int, title: str, color: str) -> None:
    step_badge(svg, x + 22, y + 22, number, color)
    svg.text(x + 52, y + 29, title, "panel-title")


def lattice_points(
    svg: SVG,
    x0: float,
    y0: float,
    nx: int,
    ny: int,
    dx: float,
    dy: float,
    cls_a: str = "atom-a",
    cls_b: str | None = None,
    radius: float = 5,
) -> None:
    for j in range(ny):
        for i in range(nx):
            cls = cls_a if cls_b is None or (i + j) % 2 == 0 else cls_b
            svg.circle(x0 + i * dx, y0 + j * dy, radius, cls)


def grid(svg: SVG, x0: float, y0: float, nx: int, ny: int, dx: float, dy: float) -> None:
    for i in range(nx):
        svg.line(x0 + i * dx, y0, x0 + i * dx, y0 + (ny - 1) * dy, "grid")
    for j in range(ny):
        svg.line(x0, y0 + j * dy, x0 + (nx - 1) * dx, y0 + j * dy, "grid")


def surface_construction() -> SVG:
    svg = SVG(
        "From a bulk plane to a finite oriented slab",
        "A three-stage diagram separates the exact crystallographic selection of a Miller plane and primitive in-plane lattice from finite slab choices such as termination, thickness, and vacuum.",
    )
    svg.text(56, 52, "From bulk crystallography to a finite slab model", "title")
    panels = [(44, 86, 420, 622), (510, 86, 420, 622), (976, 86, 420, 622)]
    for x, y, w, h in panels:
        svg.rect(x, y, w, h)
    draw_panel_header(svg, 62, 104, 1, "Select the Miller plane", "#c97619")
    draw_panel_header(svg, 528, 104, 2, "Recover the primitive surface net", "#007c78")
    draw_panel_header(svg, 994, 104, 3, "Choose the finite slab model", "#3563c4")

    # Panel 1: isometric lattice cube and selected plane.
    ox, oy = 220, 500
    vx = (55, -28)
    vy = (-38, -54)
    vz = (22, 42)
    # cube edges and lattice points
    corners: dict[tuple[int, int, int], tuple[float, float]] = {}
    for i in range(4):
        for j in range(4):
            for k in range(4):
                x = ox + i * vx[0] + j * vy[0] + k * vz[0]
                y = oy + i * vx[1] + j * vy[1] + k * vz[1]
                corners[(i, j, k)] = (x, y)
                if i < 3:
                    x2, y2 = (x + vx[0], y + vx[1])
                    svg.line(x, y, x2, y2, "grid")
                if j < 3:
                    x2, y2 = (x + vy[0], y + vy[1])
                    svg.line(x, y, x2, y2, "grid")
                if k < 3:
                    x2, y2 = (x + vz[0], y + vz[1])
                    svg.line(x, y, x2, y2, "grid")
    # The (110) plane satisfies i + j = 3 in this finite lattice sketch.
    plane = [corners[(0, 3, 0)], corners[(3, 0, 0)], corners[(3, 0, 3)], corners[(0, 3, 3)]]
    svg.polygon(plane, "surface-plane")
    for idx, (x, y) in corners.items():
        svg.circle(x, y, 4.3, "atom-a" if sum(idx) % 2 == 0 else "atom-b")
    svg.text(254, 574, "selected (110) plane family", "label", anchor="middle")
    svg.line(355, 318, 405, 262, "line-amber", marker_end="arrow-amber")
    svg.text(407, 256, "n ∥ a* + b*", "math-small", anchor="end")
    svg.rect(86, 620, 336, 56, "panel-white", rx=12)
    svg.text(104, 645, "Crystallographic input", "label amber-text")
    svg.text(104, 666, "bulk lattice + Miller covector", "small")

    # Panel 2: projected plane and primitive basis.
    x0, y0, dx, dy = 570, 230, 54, 54
    grid(svg, x0, y0, 6, 7, dx, dy)
    lattice_points(svg, x0, y0, 6, 7, dx, dy, "atom-a", None, 5.2)
    # primitive cell as skewed parallelogram
    p0 = (x0 + dx, y0 + 5 * dy)
    p1 = (p0[0] + 2 * dx, p0[1])
    p2 = (p1[0] + dx, p1[1] - 2 * dy)
    p3 = (p0[0] + dx, p0[1] - 2 * dy)
    svg.polygon([p0, p1, p2, p3], "fill-a")
    svg.line(*p0, *p1, "line-a", marker_end="arrow-a")
    svg.line(*p0, *p3, "line-a", marker_end="arrow-a")
    svg.text((p0[0] + p1[0]) / 2, p0[1] + 31, "u", "math", anchor="middle")
    svg.text(p0[0] + 26, (p0[1] + p3[1]) / 2 - 8, "v", "math", anchor="middle")
    svg.text(720, 574, "u, v span the primitive surface net", "label", anchor="middle")
    svg.rect(552, 620, 336, 56, "panel-white", rx=12)
    svg.text(570, 645, "Periodic output", "label a-text")
    svg.text(570, 666, "primitive 2D lattice + stacking translation", "small")

    # Panel 3: side-view slab with termination and vacuum.
    slab_x, slab_w = 1030, 310
    svg.rect(slab_x, 190, slab_w, 100, "vacuum", rx=8)
    svg.rect(slab_x, 500, slab_w, 100, "vacuum", rx=8)
    svg.text(1185, 224, "vacuum", "small", anchor="middle")
    svg.text(1185, 534, "vacuum", "small", anchor="middle")
    # slab layers
    for row, y in enumerate([320, 365, 410, 455]):
        svg.line(slab_x + 16, y, slab_x + slab_w - 16, y, "grid-strong")
        for i in range(7):
            cls = "atom-a" if (i + row) % 2 == 0 else "atom-b"
            svg.circle(slab_x + 35 + i * 40, y, 8, cls)
    svg.line(1357, 455, 1357, 320, "line-b", marker_end="arrow-b")
    svg.text(1374, 391, "z ∥ n", "math-small", transform="rotate(-90 1374 391)", anchor="middle")
    svg.line(1018, 320, 1018, 455, "line-violet", marker_start="arrow-violet", marker_end="arrow-violet")
    svg.text(996, 392, "thickness", "small", transform="rotate(-90 996 392)", anchor="middle")
    svg.text(1185, 302, "selected top termination", "label b-text", anchor="middle")
    svg.rect(1018, 620, 336, 56, "panel-white", rx=12)
    svg.text(1036, 645, "Modeling choices", "label b-text")
    svg.text(1036, 666, "termination, thickness, vacuum, centering", "small")

    # Process connectors.
    svg.line(466, 390, 504, 390, "line-heavy", marker_end="arrow-ink")
    svg.line(932, 390, 970, 390, "line-heavy", marker_end="arrow-ink")
    return svg


def coherent_misfit() -> SVG:
    svg = SVG(
        "Relative metric and principal coherent strains",
        "A square cell A and slightly wider, shorter cell B are compared on a common origin. The relative metric yields orthogonal principal stretches of 1.02 and 0.98, corresponding to tensile and compressive Hencky strains while the area ratio remains nearly one.",
    )
    svg.text(56, 52, "The relative metric converts cell-shape mismatch into principal coherent strains", "title")

    # Left comparison panel.
    svg.rect(44, 92, 620, 610)
    svg.text(72, 132, "1 · Compare the two metric cells", "panel-title")
    svg.text(72, 160, "same origin and orientation; different lengths", "small")
    origin = (170, 575)
    scale = 115
    # A square 3 x 3 and B rectangle 3.06 x 2.94.
    a_pts = [origin, (origin[0] + 3 * scale, origin[1]), (origin[0] + 3 * scale, origin[1] - 3 * scale), (origin[0], origin[1] - 3 * scale)]
    b_pts = [origin, (origin[0] + 3.06 * scale, origin[1]), (origin[0] + 3.06 * scale, origin[1] - 2.94 * scale), (origin[0], origin[1] - 2.94 * scale)]
    svg.polygon(a_pts, "fill-a")
    svg.polygon(b_pts, "fill-b")
    svg.line(origin[0], origin[1] + 25, origin[0] + 3.06 * scale, origin[1] + 25, "line", marker_start="arrow-muted", marker_end="arrow-muted")
    svg.text(origin[0] + 1.53 * scale, origin[1] + 52, "3.06 Å", "small b-text", anchor="middle")
    svg.line(origin[0] - 25, origin[1], origin[0] - 25, origin[1] - 3 * scale, "line", marker_start="arrow-muted", marker_end="arrow-muted")
    svg.text(origin[0] - 48, origin[1] - 1.5 * scale, "3.00 Å", "small a-text", transform=f"rotate(-90 {origin[0]-48} {origin[1]-1.5*scale})", anchor="middle")
    svg.rect(78, 625, 254, 46, "panel-a", rx=23)
    svg.text(205, 655, "A: 3.00 × 3.00 Å", "label a-text", anchor="middle")
    svg.rect(350, 625, 254, 46, "panel-b", rx=23)
    svg.text(477, 655, "B: 3.06 × 2.94 Å", "label b-text", anchor="middle")

    # Center formula connector.
    svg.line(678, 392, 756, 392, "line-violet", marker_end="arrow-violet")
    svg.text(717, 340, "basis-independent", "small violet-text", anchor="middle")
    svg.text(717, 366, "relative metric", "label violet-text", anchor="middle")
    svg.add(
        '<text x="717" y="430" class="math-small" text-anchor="middle">'
        'M = G<tspan baseline-shift="sub" font-size="70%">A</tspan>'
        '<tspan baseline-shift="super" font-size="70%">−1/2</tspan>'
        ' · G<tspan baseline-shift="sub" font-size="70%">B</tspan> · G'
        '<tspan baseline-shift="sub" font-size="70%">A</tspan>'
        '<tspan baseline-shift="super" font-size="70%">−1/2</tspan>'
        '</text>'
    )

    # Right result panel.
    svg.rect(772, 92, 624, 610)
    svg.text(800, 132, "2 · Diagonalize M to obtain principal stretches", "panel-title")
    svg.text(800, 160, "orthogonal directions separate extension from compression", "small")
    cx, cy = 1045, 430
    # Nearly area-preserving rectangle and eigenvectors.
    svg.rect(895, 275, 330, 310, "panel-white", rx=12)
    svg.polygon([(945, 520), (1195, 520), (1195, 300), (945, 300)], "fill-violet")
    svg.line(cx, cy, cx + 190, cy, "line-a", marker_end="arrow-a")
    svg.line(cx, cy, cx, cy - 170, "line-b", marker_end="arrow-b")
    svg.text(cx + 105, cy - 16, "stretch 1.02", "label a-text", anchor="middle")
    svg.text(cx + 18, cy - 95, "stretch 0.98", "label b-text", transform=f"rotate(-90 {cx+18} {cy-95})", anchor="middle")
    svg.circle(cx, cy, 5, "point-selected")
    svg.rect(820, 607, 260, 62, "panel-a", rx=12)
    svg.text(950, 635, "ε₁ = ln(1.02)", "math", anchor="middle")
    svg.text(950, 659, "+1.98% tensile", "label a-text", anchor="middle")
    svg.rect(1092, 607, 260, 62, "panel-b", rx=12)
    svg.text(1222, 635, "ε₂ = ln(0.98)", "math", anchor="middle")
    svg.text(1222, 659, "−2.02% compressive", "label b-text", anchor="middle")
    svg.rect(902, 198, 374, 48, "panel-white", rx=24)
    svg.text(1089, 229, "area ratio = 1.02 × 0.98 = 0.9996", "label", anchor="middle")
    svg.text(1089, 258, "shape changes while area is almost preserved", "small", anchor="middle")
    return svg


def pareto_front() -> SVG:
    svg = SVG(
        "Search-wide strain-size Pareto selection",
        "A chart of interface atom count versus cell mismatch shows candidates A, B, and D on the nondominated Pareto front. Candidate C is dominated by B because B is both smaller and lower mismatch. A lower-left dominance region and the ranking-after-membership sequence are shown.",
    )
    svg.text(56, 52, "Pareto membership preserves every nondominated size–mismatch compromise", "title")
    svg.rect(44, 92, 980, 620)
    svg.rect(1052, 92, 344, 620, "panel-white")

    # Chart.
    x0, y0, w, h = 130, 625, 820, 430
    for i in range(6):
        x = x0 + i * w / 5
        svg.line(x, y0, x, y0 - h, "grid")
    for j in range(6):
        y = y0 - j * h / 5
        svg.line(x0, y, x0 + w, y, "grid")
    svg.line(x0, y0, x0 + w + 20, y0, "line-heavy", marker_end="arrow-ink")
    svg.line(x0, y0, x0, y0 - h - 20, "line-heavy", marker_end="arrow-ink")
    svg.text(x0 + w / 2, 682, "interface atom count → larger model", "label", anchor="middle")
    svg.text(75, y0 - h / 2, "cell mismatch d_cell", "label", transform=f"rotate(-90 75 {y0-h/2})", anchor="middle")
    svg.text(118, 186, "lower", "small", anchor="end")
    svg.text(118, 205, "is better", "small", anchor="end")
    svg.text(208, 660, "80", "small", anchor="middle")
    svg.text(402, 660, "100", "small", anchor="middle")
    svg.text(596, 660, "120", "small", anchor="middle")
    svg.text(790, 660, "140", "small", anchor="middle")
    for label, value, y in [("0.060", 0.06, 195), ("0.045", 0.045, 302), ("0.030", 0.03, 410), ("0.015", 0.015, 517), ("0.000", 0.0, 625)]:
        svg.text(118, y + 5, label, "small", anchor="end")

    points = {
        "A": (260, 260),
        "B": (435, 430),
        "C": (610, 360),
        "D": (865, 555),
    }
    # dominated region from B (upper-right is worse on both objectives)
    bx, by = points["B"]
    svg.add(f'<path d="M {bx} {by} H {x0+w} V {y0-h} H {bx} Z" fill="url(#dominated-hatch)" opacity="0.42"/>')
    svg.text(760, 235, "region dominated by B", "small red-text", anchor="middle")
    svg.path(f"M {points['A'][0]} {points['A'][1]} Q 340 350 {points['B'][0]} {points['B'][1]} Q 640 515 {points['D'][0]} {points['D'][1]}", "line-a")
    # domination arrows from B toward C with orthogonal components
    svg.line(bx, by, points["C"][0], by, "line-red dash", marker_end="arrow-red")
    svg.line(points["C"][0], by, points["C"][0], points["C"][1], "line-red dash", marker_end="arrow-red")
    svg.text(525, by + 28, "larger", "small red-text", anchor="middle")
    svg.text(points["C"][0] + 18, 398, "higher mismatch", "small red-text", transform=f"rotate(-90 {points['C'][0]+18} 398)", anchor="middle")
    for name in ("A", "B", "D"):
        x, y = points[name]
        svg.circle(x, y, 10, "point-front")
        svg.text(x, y - 20, name, "label a-text", anchor="middle")
    x, y = points["C"]
    svg.circle(x, y, 10, "point-dominated")
    svg.text(x, y - 20, "C", "label red-text", anchor="middle")
    svg.text(650, 585, "search-wide Pareto front", "label a-text", anchor="middle")

    # Right sequence panel.
    svg.text(1080, 136, "Selection order", "panel-title")
    steps = [
        ("1", "finite candidate set", "exact search bounds"),
        ("2", "Pareto membership", "remove dominated C"),
        ("3", "ranking / truncation", "applied only afterward"),
    ]
    y = 190
    colors = ["#3563c4", "#007c78", "#6c4ccf"]
    for i, (n, head, sub) in enumerate(steps):
        svg.circle(1090, y, 18, "", extra=f'fill="{colors[i]}" stroke="none"')
        svg.text(1090, y + 5, n, "step", anchor="middle")
        svg.text(1125, y - 2, head, "label")
        svg.text(1125, y + 22, sub, "small")
        if i < len(steps) - 1:
            svg.line(1090, y + 24, 1090, y + 90, "line-muted", marker_end="arrow-muted")
        y += 125
    svg.rect(1078, 565, 292, 110, "panel-amber", rx=14)
    svg.text(1098, 594, "What the front does not rank", "label amber-text")
    svg.text(1098, 622, "elastic energy · interface energy", "small")
    svg.text(1098, 646, "chemistry · registry · termination", "small")
    return svg


def registry_torus() -> SVG:
    svg = SVG(
        "Periodic registry coordinates on a translation torus",
        "A proposal in the unit translation cell crosses the right and bottom boundaries and wraps to the equivalent point on the left and top edges. Opposite edges are identified, so the stored representative changes while the physical rigid translation remains equivalent.",
    )
    svg.text(56, 52, "Registry translations live on a torus: opposite edges are identified", "title")
    svg.rect(44, 92, 860, 620)
    svg.rect(934, 92, 462, 620, "panel-white")

    # Fundamental cell chart.
    x0, y0, size = 165, 170, 500
    for i in range(11):
        x = x0 + i * size / 10
        y = y0 + i * size / 10
        svg.line(x, y0, x, y0 + size, "grid")
        svg.line(x0, y, x0 + size, y, "grid")
    # Paired edges: same color and arrow direction.
    svg.line(x0, y0, x0 + size, y0, "line-b")
    svg.line(x0, y0 + size, x0 + size, y0 + size, "line-b")
    svg.line(x0, y0, x0, y0 + size, "line-a")
    svg.line(x0 + size, y0, x0 + size, y0 + size, "line-a")
    svg.text(x0 + size / 2, y0 - 18, "q₂ = 1 ≡ 0", "label b-text", anchor="middle")
    svg.text(x0 + size / 2, y0 + size + 34, "q₂ = 0 ≡ 1", "label b-text", anchor="middle")
    svg.text(x0 - 42, y0 + size / 2, "q₁ = 0 ≡ 1", "label a-text", transform=f"rotate(-90 {x0-42} {y0+size/2})", anchor="middle")
    svg.text(x0 + size + 42, y0 + size / 2, "q₁ = 1 ≡ 0", "label a-text", transform=f"rotate(-90 {x0+size+42} {y0+size/2})", anchor="middle")

    start = (x0 + 0.95 * size, y0 + 0.90 * size)
    raw = (x0 + 1.05 * size, y0 + 1.15 * size)
    wrapped = (x0 + 0.05 * size, y0 + 0.15 * size)
    svg.circle(*start, 9, "point-selected")
    svg.text(start[0] - 12, start[1] - 18, "start (0.95, 0.10)", "label violet-text", anchor="end")
    svg.line(start[0], start[1], raw[0], raw[1], "line-violet dash", marker_end="arrow-violet")
    svg.text(710, 667, "raw proposal", "small violet-text")
    # wrapped split path entering opposite corner
    svg.line(x0, y0 + 0.15 * size, wrapped[0], wrapped[1], "line-violet", marker_end="arrow-violet")
    svg.circle(*wrapped, 10, "point-front")
    svg.text(wrapped[0] + 18, wrapped[1] - 18, "stored (0.05, 0.85)", "label a-text")
    # corner equivalence glyphs
    svg.path(f"M {x0+size+14} {y0+size-20} C {x0+size+65} {y0+size-20}, {x0+size+65} {y0-20}, {x0+size+14} {y0-20}", "line-a", extra='marker-end="url(#arrow-a)"')
    svg.path(f"M {x0+size-20} {y0+size+14} C {x0+size-20} {y0+size+65}, {x0-20} {y0+size+65}, {x0-20} {y0+size+14}", "line-b", extra='marker-end="url(#arrow-b)"')
    svg.text(64, 132, "fundamental translation cell [0,1)²", "panel-title")

    # Right conceptual panel.
    svg.text(966, 132, "What changes—and what does not", "panel-title")
    items = [
        ("coordinate representative", "changes after modulo wrapping", "#6c4ccf"),
        ("physical rigid translation", "unchanged modulo lattice vectors", "#007c78"),
        ("common cell and atom geometry", "fixed during translation-only search", "#3563c4"),
    ]
    y = 190
    for head, sub, color in items:
        svg.circle(982, y, 7, "", extra=f'fill="{color}" stroke="none"')
        svg.text(1004, y + 5, head, "label")
        svg.text(1004, y + 30, sub, "small")
        y += 92
    # Stylized torus topology.
    svg.add('<ellipse cx="1165" cy="545" rx="145" ry="82" fill="#e8eefb" stroke="#3563c4" stroke-width="2.4"/>')
    svg.add('<ellipse cx="1165" cy="545" rx="56" ry="31" fill="#fcfdff" stroke="#3563c4" stroke-width="2.4"/>')
    svg.path("M 1020 545 C 1070 470, 1260 470, 1310 545", "line-a")
    svg.path("M 1020 545 C 1070 620, 1260 620, 1310 545", "line-b")
    svg.circle(1235, 500, 9, "point-selected")
    svg.text(1165, 665, "the square is a coordinate chart for the torus", "small", anchor="middle")
    return svg


def energy_cycles() -> SVG:
    svg = SVG(
        "Three interfacial energy reference processes",
        "A central coherent interface is connected to three distinct reference states: coherently strained bulks, cleaved unrelaxed surfaces, and independently relaxed fixed-cell surfaces. Each path answers a different scientific question and uses area and interface multiplicity normalization.",
    )
    svg.text(56, 52, "Interfacial quantities differ because their reference processes differ", "title")

    # Central interface state.
    svg.rect(485, 92, 470, 190, "panel-violet")
    svg.text(720, 128, "coherent interface state", "panel-title violet-text", anchor="middle")
    svg.text(720, 154, "E_int · common in-plane cell · n_int interfaces", "small", anchor="middle")
    # cartoon: A/B layers.
    for y in (188, 214):
        for i in range(9):
            svg.circle(565 + 38 * i, y, 7, "atom-a")
    svg.line(545, 228, 895, 228, "line-violet")
    for y in (244, 270):
        for i in range(9):
            svg.circle(565 + 38 * i, y, 7, "atom-b")
    svg.text(530, 209, "A", "label a-text", anchor="end")
    svg.text(530, 263, "B", "label b-text", anchor="end")

    refs = [
        (44, "strained-bulk references", "interface excess energy", "panel-a", "a-text", "E_int − m_A μ_A − m_B μ_B"),
        (495, "cleaved unrelaxed surfaces", "work of separation", "panel-amber", "amber-text", "E_A^unrel + E_B^unrel − E_int"),
        (946, "independently relaxed surfaces", "work of adhesion", "panel-b", "b-text", "E_A^rel + E_B^rel − E_int"),
    ]
    # Branch lines from central state.
    branch_x = [245, 720, 1195]
    for x, marker_cls in zip(branch_x, ["arrow-a", "arrow-amber", "arrow-b"]):
        color_cls = {"arrow-a":"line-a", "arrow-amber":"line-amber", "arrow-b":"line-b"}[marker_cls]
        svg.path(f"M 720 282 C 720 330, {x} 330, {x} 386", color_cls, extra=f'marker-end="url(#{marker_cls})"')

    for x, title, quantity, panel_cls, text_cls, numerator in refs:
        svg.rect(x, 390, 400, 300, panel_cls)
        svg.text(x + 200, 430, title, "panel-title " + text_cls, anchor="middle")
        svg.text(x + 200, 458, quantity, "label", anchor="middle")
        if "bulk" in title:
            # two bulk blocks
            svg.rect(x + 45, 492, 130, 82, "panel-white", rx=8)
            svg.rect(x + 225, 492, 130, 82, "panel-white", rx=8)
            for i in range(4):
                svg.circle(x + 68 + i * 28, 520, 6, "atom-a")
                svg.circle(x + 248 + i * 28, 548, 6, "atom-b")
            svg.text(x + 110, 598, "compatible strained A", "small", anchor="middle")
            svg.text(x + 290, 598, "compatible strained B", "small", anchor="middle")
        else:
            # surfaces separated with or without relaxation indication
            svg.line(x + 55, 520, x + 175, 520, "line-a")
            svg.line(x + 225, 548, x + 345, 548, "line-b")
            for i in range(4):
                svg.circle(x + 72 + i * 28, 505, 6, "atom-a")
                svg.circle(x + 242 + i * 28, 563, 6, "atom-b")
            if "relaxed" in title and "unrelaxed" not in title:
                svg.path(f"M {x+55} 520 Q {x+115} 506 {x+175} 520", "line-a")
                svg.path(f"M {x+225} 548 Q {x+285} 562 {x+345} 548", "line-b")
                svg.text(x + 200, 598, "two converged fixed-cell relaxations", "small", anchor="middle")
            else:
                svg.text(x + 200, 598, "same coordinates immediately after cleavage", "small", anchor="middle")
        svg.text(x + 200, 635, numerator, "math-small", anchor="middle")
        svg.text(x + 200, 663, "divide by A × n_int", "label", anchor="middle")

    svg.text(720, 742, "Raw total energies are saved separately; the convention determines the derived thermodynamic quantity.", "body", anchor="middle")
    return svg


def project_lineage() -> SVG:
    svg = SVG(
        "Saved scientific lineage through the CALM workflow",
        "A directed graph shows how saved materials and surfaces lead to searches, candidates, interfaces, calculations, datasets, and campaigns. A side panel distinguishes the reopenable project from exported tables, structures, plots, and reports.",
    )
    svg.text(56, 52, "A CALM project connects each result to the choices that produced it", "title")
    svg.rect(44, 92, 1030, 620)
    svg.rect(1102, 92, 294, 620, "panel-white")

    # Lanes.
    lanes = [
        ("MODEL SETUP", 145, "#007c78", "a-text"),
        ("CALCULATION", 345, "#6c4ccf", "violet-text"),
        ("ANALYSIS", 545, "#3563c4", "b-text"),
    ]
    for name, y, color, cls in lanes:
        svg.text(75, y, name, "small " + cls)
        svg.line(155, y - 5, 1040, y - 5, "line-muted")

    nodes = {
        "material": (170, 178, 140, 64, "panel-a", "material"),
        "surface": (352, 178, 140, 64, "panel-a", "surface"),
        "search": (534, 178, 140, 64, "panel-a", "search"),
        "candidate": (716, 178, 140, 64, "panel-a", "candidate"),
        "interface": (898, 178, 140, 64, "panel-a", "interface"),
        "relax": (534, 378, 160, 64, "panel-violet", "relaxation"),
        "energy": (744, 378, 140, 64, "panel-violet", "raw energy"),
        "thermo": (908, 378, 150, 64, "panel-violet", "derived quantity"),
        "dataset": (552, 578, 150, 64, "panel-b", "dataset"),
        "campaign": (780, 578, 150, 64, "panel-b", "campaign"),
    }
    for key, (x, y, w, h, cls, label) in nodes.items():
        svg.rect(x, y, w, h, cls, rx=12)
        text_cls = "label"
        if cls == "panel-a":
            text_cls += " a-text"
        elif cls == "panel-b":
            text_cls += " b-text"
        else:
            text_cls += " violet-text"
        svg.text(x + w / 2, y + 36, label, text_cls, anchor="middle")
        svg.text(x + w / 2, y + 55, "saved object", "tiny", anchor="middle")

    # Main lineage edges.
    main = ["material", "surface", "search", "candidate", "interface"]
    for a, b in zip(main, main[1:]):
        xa, ya, wa, ha, *_ = nodes[a]
        xb, yb, wb, hb, *_ = nodes[b]
        svg.line(xa + wa, ya + ha / 2, xb, yb + hb / 2, "line-a", marker_end="arrow-a")
    # Interface to calculations.
    ix, iy, iw, ih, *_ = nodes["interface"]
    rx, ry, rw, rh, *_ = nodes["relax"]
    ex, ey, ew, eh, *_ = nodes["energy"]
    tx, ty, tw, th, *_ = nodes["thermo"]
    svg.path(f"M {ix+iw/2} {iy+ih} V 320 H {rx+rw/2} V {ry}", "line-violet", extra='marker-end="url(#arrow-violet)"')
    svg.line(rx + rw, ry + rh / 2, ex, ey + eh / 2, "line-violet", marker_end="arrow-violet")
    svg.line(ex + ew, ey + eh / 2, tx, ty + th / 2, "line-violet", marker_end="arrow-violet")
    # Candidate/interface/thermo to aggregation.
    dx, dy, dw, dh, *_ = nodes["dataset"]
    cx, cy, cw, ch, *_ = nodes["campaign"]
    candx, candy, candw, candh, *_ = nodes["candidate"]
    svg.path(
        f"M {candx+candw/2} {candy+candh} V 305 H 500 V 520 H {dx+dw/2} V {dy}",
        "line-b",
        extra='marker-end="url(#arrow-b)"',
    )
    svg.path(f"M {tx+tw/2} {ty+th} V 520 H {dx+dw/2} V {dy}", "line-b", extra='marker-end="url(#arrow-b)"')
    svg.line(dx + dw, dy + dh / 2, cx, cy + ch / 2, "line-b", marker_end="arrow-b")

    # Side explanation and export relationship.
    svg.text(1130, 136, "Saved study and exports", "panel-title")
    svg.rect(1130, 164, 238, 164, "panel-violet", rx=14)
    svg.text(1150, 195, "CALM project", "label violet-text")
    svg.text(1150, 222, "inputs + settings", "body")
    svg.text(1150, 247, "structures + results", "body")
    svg.text(1150, 272, "lineage + artifacts", "body")
    svg.text(1150, 297, "workflow status", "body")
    svg.rect(1130, 374, 238, 164, "panel-amber", rx=14)
    svg.text(1150, 405, "Exports", "label amber-text")
    svg.text(1150, 432, "tables · structures", "body")
    svg.text(1150, 457, "plots · reports", "body")
    svg.text(1150, 486, "useful for analysis", "body")
    svg.text(1150, 511, "project needed to resume", "body")
    svg.path(
        f"M {tx+tw} {ty+th/2} C 1080 {ty+th/2}, 1080 456, 1124 456",
        "line-amber dash",
        extra='marker-end="url(#arrow-amber)"',
    )
    svg.text(1150, 594, "Reproducibility uses", "label")
    svg.text(1150, 621, "project + artifacts +", "body")
    svg.text(1150, 646, "declared software and", "body")
    svg.text(1150, 671, "calculator information.", "body")
    return svg


def main() -> None:
    figures = rendered_figures()
    for filename, content in figures.items():
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / filename).write_text(content, encoding="utf-8")
    print(f"wrote {len(figures)} SVG figures to {OUT.relative_to(ROOT)}")


def rendered_figures() -> dict[str, str]:
    figures = {
        "surface-construction-workflow.svg": surface_construction(),
        "coherent-misfit-principal-strain.svg": coherent_misfit(),
        "pareto-strain-size.svg": pareto_front(),
        "registry-translation-torus.svg": registry_torus(),
        "interface-energy-reference-cycles.svg": energy_cycles(),
        "project-lineage.svg": project_lineage(),
    }
    return {filename: svg.render() for filename, svg in figures.items()}


if __name__ == "__main__":
    main()
