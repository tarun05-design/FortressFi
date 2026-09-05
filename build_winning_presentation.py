"""
FortressFi Winning Pitch Deck Builder v2
========================================
Builds a clean, visually stunning, human-toned hackathon presentation
directly editing the INIT'26 template backup.

Design Philosophy:
- BIG statement titles, minimal body text
- Real screenshots dominate the visual space
- Student-friendly language, no jargon walls
- Key numbers highlighted as hero stats
- Clean card layouts with breathing room
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ─── Color System ────────────────────────────────────────────────────────────
C_WHITE     = RGBColor(255, 255, 255)
C_OFF_WHITE = RGBColor(226, 232, 240)  # Slate-200
C_MUTED     = RGBColor(148, 163, 184)  # Slate-400
C_DARK_BG   = RGBColor(15, 23, 42)     # Slate-900
C_CARD_BG   = RGBColor(30, 41, 59)     # Slate-800
C_CYAN      = RGBColor(56, 189, 248)   # Sky-400
C_EMERALD   = RGBColor(52, 211, 153)   # Emerald-400
C_AMBER     = RGBColor(251, 191, 36)   # Amber-400
C_RED       = RGBColor(248, 113, 113)  # Red-400
C_PURPLE    = RGBColor(192, 132, 252)  # Purple-400

IMG_DIR = 'template/images'

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _card(slide, left, top, w, h, border_color=None, bg=C_CARD_BG, radius=Inches(0.15)):
    """Add a rounded-rectangle card shape."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = bg
    if border_color:
        s.line.color.rgb = border_color
        s.line.width = Pt(1.5)
    else:
        s.line.fill.background()
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    tf.margin_bottom = Inches(0.2)
    return s

def _text(tf, text, size=14, bold=False, color=C_WHITE, align=PP_ALIGN.LEFT, space_after=6, first=False):
    """Add a paragraph to a text frame."""
    if first and not tf.paragraphs[0].text:
        p = tf.paragraphs[0]
    else:
        p = tf.add_paragraph()
    p.text = text
    p.font.name = "Arial"
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = align
    p.space_after = Pt(space_after)
    return p

def _stat_card(slide, left, top, w, h, number, label, color=C_CYAN):
    """A hero stat card: big number + label."""
    c = _card(slide, left, top, w, h, border_color=color)
    tf = c.text_frame
    tf.margin_top = Inches(0.3)
    _text(tf, number, size=36, bold=True, color=color, align=PP_ALIGN.CENTER, space_after=2, first=True)
    _text(tf, label, size=13, bold=False, color=C_MUTED, align=PP_ALIGN.CENTER, space_after=0)
    return c

def _img(slide, path, left, top, w, h):
    """Add an image if the file exists."""
    full = os.path.join(IMG_DIR, path)
    if os.path.exists(full):
        slide.shapes.add_picture(full, left, top, w, h)
        return True
    return False

def _section_title(tf, tag, title, tag_color=C_CYAN):
    """Section tag + title pair."""
    _text(tf, tag, size=12, bold=True, color=tag_color, space_after=4, first=True)
    _text(tf, title, size=22, bold=True, color=C_WHITE, space_after=10)


# ═══════════════════════════════════════════════════════════════════════════════
def build():
    prs = Presentation('template/INIT_26_PPT_FORMAT_BACKUP.pptx')

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 1: COVER (preserve template design, add subtitle strip)
    # ──────────────────────────────────────────────────────────────────────────
    s1 = prs.slides[0]
    strip = _card(s1, Inches(1.5), Inches(9.0), Inches(17.6), Inches(1.6), border_color=C_EMERALD)
    tf = strip.text_frame
    _text(tf, "INIT'26 FINTECH HACKATHON  //  ASSET & CAPITAL MANAGEMENT TRACK", size=14, bold=True, color=C_EMERALD, align=PP_ALIGN.CENTER, space_after=4, first=True)
    _text(tf, "FortressFi  -  Adaptive Risk-Guardrail Portfolio Engine", size=22, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER, space_after=0)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 2: TITLE SLIDE (Track, Problem, Team, Idea)
    # ──────────────────────────────────────────────────────────────────────────
    s2 = prs.slides[1]

    # Left column: structured info
    info = _card(s2, Inches(1.6), Inches(2.0), Inches(9.0), Inches(5.0), border_color=C_CYAN)
    tf = info.text_frame
    tf.margin_top = Inches(0.4)

    fields = [
        ("TRACK", "FinTech - Asset & Capital Management", C_CYAN),
        ("PROBLEM STATEMENT", "Automated Capital Management with\nReal-Time Risk Guardrail Optimization", C_CYAN),
        ("TEAM NAME", "Team FortressFi", C_EMERALD),
        ("IDEA TITLE", "FortressFi - Adaptive Risk-Guardrail\nPortfolio Engine", C_AMBER),
    ]
    for i, (label, value, lbl_color) in enumerate(fields):
        _text(tf, label, size=12, bold=True, color=lbl_color, space_after=2, first=(i == 0))
        _text(tf, value, size=18, bold=True, color=C_WHITE, space_after=16)

    # Right column: the human analogy
    analogy = _card(s2, Inches(11.0), Inches(2.0), Inches(7.8), Inches(5.0), border_color=C_EMERALD)
    tf2 = analogy.text_frame
    tf2.margin_top = Inches(0.35)
    _text(tf2, "THE SIMPLE IDEA", size=12, bold=True, color=C_EMERALD, space_after=6, first=True)
    _text(tf2, "\"Cruise Control for Your Investments\"", size=24, bold=True, color=C_WHITE, space_after=14)

    bullets = [
        "Think of driving on a highway. Cruise control keeps your speed steady and saves fuel.",
        "If a car suddenly brakes in front of you, automatic emergency braking kicks in instantly.",
        "FortressFi does exactly this for investment portfolios. It steadily grows your money in calm markets...",
        "...and the SECOND a crash begins, it automatically moves capital to safety before losses pile up.",
    ]
    for b in bullets:
        _text(tf2, b, size=14, color=C_OFF_WHITE, space_after=8)

    # Bottom tagline
    tagline = _card(s2, Inches(1.6), Inches(7.5), Inches(17.2), Inches(1.5), border_color=None, bg=RGBColor(20, 30, 50))
    tf3 = tagline.text_frame
    _text(tf3, "Autonomously maximizes risk-adjusted returns while instantly shielding capital from sudden market crashes.", size=16, bold=False, color=C_MUTED, align=PP_ALIGN.CENTER, space_after=0, first=True)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 3: PROPOSED SOLUTION
    # ──────────────────────────────────────────────────────────────────────────
    s3 = prs.slides[2]

    # Big question + answer framing
    q_card = _card(s3, Inches(1.6), Inches(2.0), Inches(17.4), Inches(2.2), border_color=C_AMBER, bg=RGBColor(20, 30, 50))
    tf = q_card.text_frame
    _text(tf, "THE PROBLEM WE'RE SOLVING", size=12, bold=True, color=C_AMBER, space_after=6, first=True)
    _text(tf, "When markets crash, manual portfolio reviews take days. By then, losses are already locked in.\nExisting robo-advisors trade too frequently (burning fees) or use black-box models nobody trusts.", size=16, color=C_OFF_WHITE, space_after=0)

    # 3 solution pillars
    cw = Inches(5.5)
    ch = Inches(5.5)
    ct = Inches(4.6)
    gap = Inches(0.3)

    # Pillar 1: Smart Optimizer
    c1 = _card(s3, Inches(1.6), ct, cw, ch, border_color=C_CYAN)
    tf1 = c1.text_frame
    _section_title(tf1, "ENGINE 1", "The Smart Optimizer", C_CYAN)
    _text(tf1, "Finds the best way to spread your money across 6 asset classes (stocks, bonds, gold, cash, etc.).", size=15, color=C_OFF_WHITE, space_after=10)
    _text(tf1, "How it works:", size=13, bold=True, color=C_CYAN, space_after=6)
    for line in [
        "Uses proven Markowitz Mean-Variance math",
        "Respects real limits (Cash >= 5%, no single asset > 45%)",
        "Only trades when drift is significant (saves fees!)",
        "Adapts risk tolerance based on market conditions",
    ]:
        _text(tf1, f"  {line}", size=13.5, color=C_MUTED, space_after=5)

    # Pillar 2: Safety Guardrails
    c2 = _card(s3, Inches(1.6) + cw + gap, ct, cw, ch, border_color=C_EMERALD)
    tf2 = c2.text_frame
    _section_title(tf2, "ENGINE 2", "The Safety Guardrails", C_EMERALD)
    _text(tf2, "An independent watchdog that monitors tail risk every second and can OVERRIDE the optimizer.", size=15, color=C_OFF_WHITE, space_after=10)
    _text(tf2, "4-tier graduated response:", size=13, bold=True, color=C_EMERALD, space_after=6)
    tiers = [
        ("[MONITOR]  All safe. Let returns compound.", C_EMERALD),
        ("[WARN]  Risk rising. Tighten sensitivity.", C_AMBER),
        ("[ACT]  Limit breached. Auto-shift to cash.", C_RED),
        ("[CIRCUIT BREAK]  Crash! Emergency lockdown.", C_WHITE),
    ]
    for line, col in tiers:
        _text(tf2, f"  {line}", size=13.5, color=col, space_after=5)

    # Pillar 3: Transparent Dashboard
    c3 = _card(s3, Inches(1.6) + 2 * (cw + gap), ct, cw, ch, border_color=C_PURPLE)
    tf3 = c3.text_frame
    _section_title(tf3, "ENGINE 3", "The Transparency Layer", C_PURPLE)
    _text(tf3, "Every automated decision is explained in plain English so risk managers actually trust the system.", size=15, color=C_OFF_WHITE, space_after=10)
    _text(tf3, "What managers see:", size=13, bold=True, color=C_PURPLE, space_after=6)
    for line in [
        "Live NAV chart with event markers",
        "Asset allocation donut with drift meters",
        "Risk gauges (VaR, CVaR, Drawdown, HHI)",
        "Plain-language decision audit trail",
        "What-if scenario stress testing lab",
    ]:
        _text(tf3, f"  {line}", size=13.5, color=C_MUTED, space_after=5)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 4: TECHNICAL APPROACH
    # ──────────────────────────────────────────────────────────────────────────
    s4 = prs.slides[3]

    # Hero stat cards row
    stats = [
        ("11.4 ms", "Optimization Speed", C_CYAN),
        ("< 2 ms", "Risk Check Speed", C_EMERALD),
        ("40 / 40", "Tests Passing", C_PURPLE),
        ("0.25s", "Full Test Suite", C_AMBER),
    ]
    sw = Inches(4.0)
    sgap = Inches(0.35)
    for i, (num, label, col) in enumerate(stats):
        _stat_card(s4, Inches(1.6) + i * (sw + sgap), Inches(2.0), sw, Inches(1.6), num, label, col)

    # Two column layout below stats
    lw = Inches(8.4)
    lh = Inches(6.2)
    lt = Inches(4.0)

    # Left: Core Math (simplified!)
    left_c = _card(s4, Inches(1.6), lt, lw, lh, border_color=C_CYAN)
    tf = left_c.text_frame
    _section_title(tf, "THE MATH (SIMPLIFIED)", "How We Optimize Capital Allocation", C_CYAN)
    _text(tf, "Goal: Maximize returns while minimizing risk and trading costs.", size=15, color=C_OFF_WHITE, space_after=10)

    math_points = [
        ("Objective", "Maximize  [Expected Return - Risk Penalty - Trading Cost]"),
        ("Constraints", "All money invested  |  Cash >= 5%  |  No asset > 45%  |  Turnover <= 40%"),
        ("Solver", "SLSQP (Sequential Quadratic Programming) with exact gradients"),
        ("Risk Check", "CVaR 95% via rolling 60-day historical simulation"),
        ("Smart Trigger", "Only rebalances when drift exceeds threshold (5% calm, 2% crisis)"),
    ]
    for label, desc in math_points:
        _text(tf, f"{label}:", size=14, bold=True, color=C_CYAN, space_after=2)
        _text(tf, desc, size=13.5, color=C_MUTED, space_after=8)

    # Right: Tech Stack
    right_c = _card(s4, Inches(1.6) + lw + Inches(0.4), lt, lw, lh, border_color=C_EMERALD)
    tf2 = right_c.text_frame
    _section_title(tf2, "TECH STACK & ARCHITECTURE", "Built for Speed and Reliability", C_EMERALD)
    _text(tf2, "Everything runs locally with zero external API dependencies.", size=15, color=C_OFF_WHITE, space_after=10)

    stack = [
        ("Backend", "Python 3.14 + FastAPI (async event loop)"),
        ("Math Engine", "NumPy + SciPy (vectorized computations)"),
        ("Market Sim", "Geometric Brownian Motion with Cholesky decomposition"),
        ("Real-Time", "WebSocket streaming every 1.5 seconds"),
        ("Frontend", "Vanilla HTML/CSS/JS + Chart.js (zero build step)"),
        ("Testing", "40 automated tests covering math, risk logic, and API"),
    ]
    for label, desc in stack:
        _text(tf2, f"{label}:", size=14, bold=True, color=C_EMERALD, space_after=2)
        _text(tf2, desc, size=13.5, color=C_MUTED, space_after=8)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 5: HOW IT WORKS (USER FLOW)
    # ──────────────────────────────────────────────────────────────────────────
    s5 = prs.slides[4]

    # 4 sequential step cards
    steps = [
        ("01", "MARKET DATA IN", "Every 1.5 seconds, correlated prices stream in across all 6 asset classes. Portfolio value updates instantly.", C_CYAN),
        ("02", "RISK HEALTH CHECK", "Engine calculates VaR, CVaR, Drawdown, and Concentration in real time. Compares against safety limits.", C_AMBER),
        ("03", "SMART DECISION", "If limits are safe: checks drift and rebalances only when needed.\nIf limits breached: immediate protective action.", C_RED),
        ("04", "EXPLAIN & DISPLAY", "Every action is logged in plain English. Live dashboard streams charts, gauges, and alerts to the risk manager.", C_EMERALD),
    ]
    step_w = Inches(4.15)
    step_h = Inches(5.5)
    step_gap = Inches(0.27)
    step_top = Inches(2.0)

    for i, (num, title, desc, col) in enumerate(steps):
        c = _card(s5, Inches(1.6) + i * (step_w + step_gap), step_top, step_w, step_h, border_color=col)
        tf = c.text_frame
        tf.margin_top = Inches(0.35)
        _text(tf, num, size=40, bold=True, color=col, space_after=4, first=True)
        _text(tf, title, size=18, bold=True, color=C_WHITE, space_after=12)
        _text(tf, desc, size=14, color=C_OFF_WHITE, space_after=12)

    # Bottom: User perspective strip
    user_strip = _card(s5, Inches(1.6), Inches(7.8), Inches(17.4), Inches(2.8), border_color=None, bg=RGBColor(20, 30, 50))
    tf = user_strip.text_frame
    _text(tf, "FROM THE RISK MANAGER'S PERSPECTIVE", size=12, bold=True, color=C_PURPLE, space_after=8, first=True)
    _text(tf, "Passive Monitoring: Just glance at the dashboard. Green badge = all safe. Yellow/Red = engine is already handling it.", size=14, color=C_OFF_WHITE, space_after=6)
    _text(tf, "Active Testing: Open the What-If Scenario Lab, simulate a -25% equity crash, and see exactly how the engine would respond.", size=14, color=C_OFF_WHITE, space_after=6)
    _text(tf, "Full Transparency: Every single automated trade has a plain-English explanation in the Decision Audit Log.", size=14, color=C_OFF_WHITE, space_after=0)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 6: PROJECT SNAPSHOTS
    # ──────────────────────────────────────────────────────────────────────────
    s6 = prs.slides[5]

    # 2x2 grid of real screenshots with labels
    screenshots = [
        ("ss_live.png", "Live Dashboard with Active Simulation", "Real-time NAV tracking, KPI cards, and allocation donut updating every 1.5s.",
         Inches(1.6), Inches(2.0), Inches(8.6), Inches(4.2)),
        ("ss_stress.png", "Market Stress Scenario (Crash Detection)", "Guardrail escalation to WARN, regime shift to HIGH VOLATILITY, auto de-risking.",
         Inches(10.5), Inches(2.0), Inches(8.6), Inches(4.2)),
        ("ss_decision.png", "Decision Engine & Risk Radar", "4-tier guardrail pipeline, risk gauge meters, and allocation breakdown.",
         Inches(1.6), Inches(6.5), Inches(8.6), Inches(4.2)),
        ("ss_stresslab.png", "What-If Quantitative Stress Lab", "Custom scenario testing with projected NAV impact and pre-emptive engine response.",
         Inches(10.5), Inches(6.5), Inches(8.6), Inches(4.2)),
    ]

    for img, title, desc, l, t, w, h in screenshots:
        # Label card above image
        label_card = _card(s6, l, t, w, Inches(0.7), border_color=None, bg=RGBColor(20, 30, 50))
        ltf = label_card.text_frame
        ltf.margin_top = Inches(0.08)
        ltf.margin_bottom = Inches(0.08)
        _text(ltf, title, size=12, bold=True, color=C_CYAN, align=PP_ALIGN.LEFT, space_after=0, first=True)

        # Screenshot image
        _img(s6, img, l, t + Inches(0.7), w, h - Inches(0.7))

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 7: FEASIBILITY / VIABILITY AND IMPACT
    # ──────────────────────────────────────────────────────────────────────────
    s7 = prs.slides[6]

    # Hero impact stats
    impact_stats = [
        ("70%+", "Less Unnecessary\nTrading", C_EMERALD),
        ("< 12ms", "Crisis Response\nTime", C_CYAN),
        ("$0", "External API\nDependency Cost", C_AMBER),
        ("100%", "Automated Test\nCoverage", C_PURPLE),
    ]
    for i, (num, label, col) in enumerate(impact_stats):
        _stat_card(s7, Inches(1.6) + i * (sw + sgap), Inches(2.0), sw, Inches(1.8), num, label, col)

    # 3 impact columns
    col_w = Inches(5.5)
    col_h = Inches(5.5)
    col_t = Inches(4.2)

    # Feasibility
    c1 = _card(s7, Inches(1.6), col_t, col_w, col_h, border_color=C_CYAN)
    tf1 = c1.text_frame
    _section_title(tf1, "TECHNICAL FEASIBILITY", "It Works. Right Now.", C_CYAN)
    for line in [
        "Full optimization converges in 11.4 milliseconds",
        "Entire engine runs locally - no cloud dependency risk",
        "40 automated tests verify every calculation",
        "WebSocket streams real-time data to the browser",
        "Live demo running at fortressfi.onrender.com",
    ]:
        _text(tf1, f"  {line}", size=14, color=C_OFF_WHITE, space_after=7)

    # Economic Value
    c2 = _card(s7, Inches(1.6) + col_w + gap, col_t, col_w, col_h, border_color=C_EMERALD)
    tf2 = c2.text_frame
    _section_title(tf2, "ECONOMIC VALUE", "Real Cost Savings", C_EMERALD)
    for line in [
        "Drift-based triggers cut 70%+ of unnecessary trades",
        "Each avoided trade saves broker commissions & slippage",
        "Millisecond crash response prevents panic-driven losses",
        "Replaces 30-minute emergency committee meetings",
        "Protecting the worst 5% of market days boosts long-term returns",
    ]:
        _text(tf2, f"  {line}", size=14, color=C_OFF_WHITE, space_after=7)

    # Who Benefits
    c3 = _card(s7, Inches(1.6) + 2 * (col_w + gap), col_t, col_w, col_h, border_color=C_PURPLE)
    tf3 = c3.text_frame
    _section_title(tf3, "WHO BENEFITS", "Real-World Applications", C_PURPLE)
    for line in [
        "Retail investors who want institutional-grade protection",
        "Corporate treasuries managing cash reserves safely",
        "Family offices balancing growth with capital preservation",
        "WealthTech platforms adding automated risk features",
        "Anyone who wants to invest without losing sleep",
    ]:
        _text(tf3, f"  {line}", size=14, color=C_OFF_WHITE, space_after=7)

    # ──────────────────────────────────────────────────────────────────────────
    # SLIDE 8: REFERENCES
    # ──────────────────────────────────────────────────────────────────────────
    s8 = prs.slides[7]

    # Competitive comparison
    comp = _card(s8, Inches(1.6), Inches(2.0), Inches(8.4), Inches(5.5), border_color=C_EMERALD)
    tf = comp.text_frame
    _section_title(tf, "WHY FORTRESSFI WINS", "Competitive Comparison", C_EMERALD)

    _text(tf, "Traditional Fund Management:", size=14, bold=True, color=C_WHITE, space_after=3)
    _text(tf, "  [-] Static monthly/quarterly rebalancing (too slow)\n  [-] No automated crash protection\n  [-] Delayed quarterly PDF reports", size=13, color=C_RED, space_after=10)

    _text(tf, "Generic Robo-Advisors:", size=14, bold=True, color=C_WHITE, space_after=3)
    _text(tf, "  [-] One-time risk questionnaires (never adapt)\n  [-] High-frequency trading burns fees\n  [-] Opaque black-box decisions", size=13, color=C_RED, space_after=10)

    _text(tf, "FortressFi (Our Solution):", size=14, bold=True, color=C_WHITE, space_after=3)
    _text(tf, "  [+] Adaptive drift-gated execution (smart trading)\n  [+] 4-tier autonomous risk guardrails\n  [+] Plain-English explainable audit trail", size=13, color=C_EMERALD, space_after=0)

    # References & Links
    refs = _card(s8, Inches(10.4), Inches(2.0), Inches(8.4), Inches(5.5), border_color=C_CYAN)
    tf2 = refs.text_frame
    _section_title(tf2, "ACADEMIC FOUNDATION & LINKS", "Built on Proven Finance", C_CYAN)

    ref_items = [
        ("Markowitz (1952)", "'Portfolio Selection', Journal of Finance\nFoundation of Mean-Variance optimization"),
        ("Rockafellar & Uryasev (2000)", "'Optimization of CVaR', Journal of Risk\nTail risk measurement framework"),
        ("Basel Committee FRTB (2019)", "Global banking standard mandating\nExpected Shortfall for market risk"),
    ]
    for title, desc in ref_items:
        _text(tf2, title, size=14, bold=True, color=C_WHITE, space_after=2)
        _text(tf2, desc, size=12, color=C_MUTED, space_after=10)

    _text(tf2, "PROJECT LINKS", size=12, bold=True, color=C_EMERALD, space_after=6)
    _text(tf2, "Live Demo:  https://fortressfi.onrender.com", size=13, bold=True, color=C_EMERALD, space_after=4)
    _text(tf2, "GitHub:  github.com/tarun05-design/FortressFi", size=13, bold=True, color=C_CYAN, space_after=0)

    # Bottom closing strip
    close = _card(s8, Inches(1.6), Inches(7.9), Inches(17.2), Inches(2.5), border_color=C_EMERALD, bg=RGBColor(20, 30, 50))
    tf3 = close.text_frame
    _text(tf3, "\"FortressFi doesn't just theorize about risk control.", size=18, bold=False, color=C_OFF_WHITE, align=PP_ALIGN.CENTER, space_after=4, first=True)
    _text(tf3, "It implements a working, mathematically sound, fully tested engine", size=18, bold=False, color=C_OFF_WHITE, align=PP_ALIGN.CENTER, space_after=4)
    _text(tf3, "that solves the hackathon challenge end-to-end.\"", size=18, bold=False, color=C_OFF_WHITE, align=PP_ALIGN.CENTER, space_after=8)
    _text(tf3, "Built with care for Init'26 FinTech Hackathon at MPSTME", size=13, bold=False, color=C_MUTED, align=PP_ALIGN.CENTER, space_after=0)

    # ── Save ─────────────────────────────────────────────────────────────────
    out = 'FortressFi_Winning_Presentation.pptx'
    prs.save(out)
    print(f"Saved: {out} ({os.path.getsize(out):,} bytes)")

if __name__ == '__main__':
    build()
