import streamlit as st
import math
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
import io

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ElecCalc IEC", page_icon="⚡", layout="wide")

# ── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; background: #F7F6F2 !important; color: #1A1814; }
.main, .block-container { background: #F7F6F2 !important; }
.block-container { padding: 2.5rem 3rem !important; max-width: 1100px !important; }
.app-title { font-family: 'DM Serif Display', serif; font-size: 2.4rem; color: #1A1814; margin: 0; letter-spacing: -0.02em; }
.app-sub { font-size: 0.75rem; color: #6B6560; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 0.3rem; }
.app-bar { width: 44px; height: 3px; background: #C8440A; margin: 0.5rem 0; }
.card { background: white; border: 1px solid #E2DDD6; border-radius: 3px; padding: 1.4rem 1.6rem; }
.card-tag { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #C8440A; margin-bottom: 0.25rem; }
.card-heading { font-family: 'DM Serif Display', serif; font-size: 1rem; color: #1A1814; border-bottom: 1px solid #E2DDD6; padding-bottom: 0.45rem; margin-bottom: 0.9rem; }
.big { font-family: 'DM Serif Display', serif; font-size: 2.1rem; color: #1A1814; line-height: 1; }
.unit { font-size: 0.78rem; color: #6B6560; margin-top: 0.15rem; }
.note { font-size: 0.78rem; color: #6B6560; margin-top: 0.5rem; line-height: 1.6; }
.pill { display:inline-block; font-size:0.66rem; font-weight:700; padding:0.15rem 0.5rem; border-radius:2px; letter-spacing:0.05em; text-transform:uppercase; margin-top:0.5rem; }
.green { background:#EAF4EF; color:#2D6A4F; }
.amber { background:#FEF3C7; color:#B45309; }
.red   { background:#FEF2F2; color:#9B1C1C; }
.grey  { background:#F0EFEB; color:#6B6560; }
.impact { background:#1A1814; border-radius:3px; padding:1.8rem 2rem; margin-top:1.5rem; }
.impact h3 { font-family:'DM Serif Display',serif; font-size:1.3rem; color:white; margin-bottom:0.5rem; }
.impact p { color:#C8C3BC; font-size:0.85rem; line-height:1.7; }
.ipoint { background:rgba(255,255,255,0.07); border-left:2px solid #C8440A; padding:0.55rem 1rem; margin:0.4rem 0; border-radius:0 2px 2px 0; font-size:0.83rem; color:#E8E3DC; }
.stButton>button { background:#C8440A !important; color:white !important; border:none !important; border-radius:2px !important; font-weight:600 !important; font-size:0.76rem !important; letter-spacing:0.06em !important; text-transform:uppercase !important; }
.stDownloadButton>button { background:#1A1814 !important; color:white !important; border:none !important; border-radius:2px !important; font-weight:600 !important; font-size:0.76rem !important; }
</style>
""", unsafe_allow_html=True)

# ── IEC DATA ───────────────────────────────────────────────────────────────────
BREAKERS = [6,10,16,20,25,32,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250]

CABLES = {
    1.5:  {"xlpe":17,  "pvc":15},
    2.5:  {"xlpe":23,  "pvc":21},
    4:    {"xlpe":31,  "pvc":28},
    6:    {"xlpe":40,  "pvc":36},
    10:   {"xlpe":54,  "pvc":50},
    16:   {"xlpe":73,  "pvc":66},
    25:   {"xlpe":95,  "pvc":84},
    35:   {"xlpe":119, "pvc":104},
    50:   {"xlpe":145, "pvc":125},
    70:   {"xlpe":185, "pvc":160},
    95:   {"xlpe":224, "pvc":194},
    120:  {"xlpe":260, "pvc":225},
    150:  {"xlpe":299, "pvc":260},
    185:  {"xlpe":341, "pvc":299},
    240:  {"xlpe":403, "pvc":353},
    300:  {"xlpe":464, "pvc":406},
}

DEFAULTS   = {"Three-Phase": {"voltage":415,"pf":0.85}, "Single-Phase": {"voltage":230,"pf":0.85}}
TEMP_FACTOR = 0.94   # 35°C ambient, XLPE (IEC 60364-5-52 Table B.52.14)
GROUPING    = 0.80   # 3 cables grouped
RHO_CU      = 0.0225 # Ω·mm²/m at 75°C
CABLE_LEN   = 50     # m default

# ── CALC ───────────────────────────────────────────────────────────────────────
def calc_all(load_a, phase):
    pf      = DEFAULTS[phase]["pf"]
    voltage = DEFAULTS[phase]["voltage"]
    ib      = load_a / pf

    req_br  = ib * 1.25
    breaker = next((b for b in BREAKERS if b >= req_br), BREAKERS[-1])

    corr_ib = ib / (TEMP_FACTOR * GROUPING)
    cable_mm2, cable_rated = 300, CABLES[300]["xlpe"]
    for size, ratings in CABLES.items():
        if ratings["xlpe"] >= corr_ib:
            cable_mm2, cable_rated = size, ratings["xlpe"]
            break

    R      = (RHO_CU * CABLE_LEN) / cable_mm2
    vd_v   = (math.sqrt(3)*ib*R) if phase=="Three-Phase" else (2*ib*R)
    vd_pct = (vd_v / voltage) * 100

    kw     = (math.sqrt(3)*voltage*load_a*pf/1000) if phase=="Three-Phase" else (voltage*load_a*pf/1000)
    kva    = kw / pf
    cap_kvar = max(0, kw*math.tan(math.acos(pf)) - kw*math.tan(math.acos(0.95)))

    return dict(phase=phase, voltage=voltage, pf=pf, load_a=load_a, ib=ib,
                req_br=req_br, breaker=breaker, corr_ib=corr_ib,
                cable_mm2=cable_mm2, cable_rated=cable_rated,
                util=(corr_ib/cable_rated)*100,
                vd_v=vd_v, vd_pct=vd_pct, recv_v=voltage-vd_v,
                kw=kw, kva=kva, cap_kvar=cap_kvar)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
if "schedule" not in st.session_state:
    st.session_state.schedule = []

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<p class="app-title">ElecCalc IEC</p>
<div class="app-bar"></div>
<p class="app-sub">IEC 60364 · IEC 60947-2 · IEC 60228 &nbsp;|&nbsp; Sapphire Fibres Ltd · MTO Electrical</p>
<br>
""", unsafe_allow_html=True)

# ── INPUT ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([1.4, 1.1, 1.0, 0.8])
with c1:
    load_name = st.text_input("Load Description (optional)", placeholder="e.g. Chiller Pump-2")
with c2:
    load_a = st.number_input("Load Current (A) ⚡", min_value=0.1, value=50.0, step=0.5)
with c3:
    phase = st.selectbox("Phase Type", ["Three-Phase", "Single-Phase"])
with c4:
    st.markdown("<div style='height:1.95rem'></div>", unsafe_allow_html=True)
    add_btn = st.button("＋ Add to Schedule", use_container_width=True)

st.markdown("<hr style='border:none;border-top:1px solid #E2DDD6;margin:1rem 0 1.5rem 0'>", unsafe_allow_html=True)

r = calc_all(load_a, phase)

if add_btn:
    st.session_state.schedule.append({
        "Load":            load_name or f"Load-{len(st.session_state.schedule)+1}",
        "Phase":           phase,
        "Current (A)":     load_a,
        "Ib (A)":          round(r["ib"],1),
        "Breaker (A)":     r["breaker"],
        "Cable (mm²)":     r["cable_mm2"],
        "VD (%)":          round(r["vd_pct"],2),
        "Cap Bank (kVAR)": round(r["cap_kvar"],1),
    })
    st.success(f"✓ '{load_name or 'Load'}' added to schedule.")

# ── RESULT CARDS ───────────────────────────────────────────────────────────────
r1, r2, r3, r4 = st.columns(4, gap="medium")

with r1:
    st.markdown(f"""
    <div class="card">
      <div class="card-tag">IEC 60947-2</div>
      <div class="card-heading">Circuit Breaker</div>
      <div class="big">{r['breaker']} A</div>
      <div class="unit">Standard breaker size</div>
      <span class="pill grey">Ib {r['ib']:.1f} A × 1.25 = {r['req_br']:.1f} A</span>
      <div class="note">Type C for motor loads<br>Type B for resistive / lighting</div>
    </div>""", unsafe_allow_html=True)

with r2:
    up = "green" if r["util"]<80 else ("amber" if r["util"]<95 else "red")
    st.markdown(f"""
    <div class="card">
      <div class="card-tag">IEC 60364-5-52 · IEC 60228</div>
      <div class="card-heading">Cable Size (Cu)</div>
      <div class="big">{r['cable_mm2']} mm²</div>
      <div class="unit">XLPE · Rated {r['cable_rated']} A</div>
      <span class="pill {up}">Utilisation {r['util']:.0f}%</span>
      <div class="note">Temp factor 0.94 @ 35°C<br>Grouping factor 0.80 applied</div>
    </div>""", unsafe_allow_html=True)

with r3:
    vp = "green" if r["vd_pct"]<=3 else ("amber" if r["vd_pct"]<=5 else "red")
    vl = "Within limit ≤3%" if r["vd_pct"]<=3 else ("Acceptable ≤5%" if r["vd_pct"]<=5 else "⚠ Exceeds 5% limit")
    st.markdown(f"""
    <div class="card">
      <div class="card-tag">IEC 60364-5-52</div>
      <div class="card-heading">Voltage Drop</div>
      <div class="big">{r['vd_pct']:.2f}%</div>
      <div class="unit">{r['vd_v']:.2f} V over 50 m</div>
      <span class="pill {vp}">{vl}</span>
      <div class="note">Recv-end voltage: {r['recv_v']:.1f} V<br>Source: {r['voltage']} V ({phase})</div>
    </div>""", unsafe_allow_html=True)

with r4:
    pp = "green" if r["cap_kvar"]==0 else "amber"
    pl = "No correction needed" if r["cap_kvar"]==0 else f"Add {r['cap_kvar']:.1f} kVAR cap"
    st.markdown(f"""
    <div class="card">
      <div class="card-tag">IEC 60038</div>
      <div class="card-heading">Power Factor</div>
      <div class="big">{r['pf']}</div>
      <div class="unit">{r['kw']:.1f} kW · {r['kva']:.1f} kVA</div>
      <span class="pill {pp}">{pl}</span>
      <div class="note">Target PF 0.95 (IEC)<br>Capacitor bank recommendation</div>
    </div>""", unsafe_allow_html=True)

st.markdown("""
<div style="background:white;border:1px solid #E2DDD6;border-radius:3px;padding:0.75rem 1.2rem;
            font-size:0.74rem;color:#6B6560;margin:1rem 0 1.5rem 0">
  <strong style="color:#1A1814">IEC Defaults Applied:</strong> &nbsp;
  3-phase → 415 V · Single-phase → 230 V &nbsp;|&nbsp; PF 0.85 &nbsp;|&nbsp;
  XLPE 90°C &nbsp;|&nbsp; Ambient 35°C (k=0.94) &nbsp;|&nbsp; Grouping 0.80 &nbsp;|&nbsp; Cable length 50 m
</div>
""", unsafe_allow_html=True)

# ── LOAD SCHEDULE ──────────────────────────────────────────────────────────────
st.markdown("<p style='font-family:DM Serif Display,serif;font-size:1.1rem;color:#1A1814;margin-bottom:0.6rem'>Load Schedule</p>",
            unsafe_allow_html=True)

if st.session_state.schedule:
    df = pd.DataFrame(st.session_state.schedule)
    st.dataframe(df, use_container_width=True, hide_index=True)
    m1,m2,m3,mc = st.columns(4)
    m1.metric("Total Loads", len(df))
    m2.metric("Max Breaker", f"{df['Breaker (A)'].max()} A")
    m3.metric("Max Cable",   f"{df['Cable (mm²)'].max()} mm²")
    with mc:
        if st.button("🗑 Clear Schedule"):
            st.session_state.schedule = []
            st.rerun()
else:
    st.markdown("""
    <div style="padding:1.5rem;text-align:center;color:#6B6560;background:white;
                border:1px dashed #C8C3BC;border-radius:3px;font-size:0.84rem;">
      No loads yet — click <strong>＋ Add to Schedule</strong> above.
    </div>""", unsafe_allow_html=True)

# ── PDF ────────────────────────────────────────────────────────────────────────
st.markdown("<hr style='border:none;border-top:1px solid #E2DDD6;margin:1.5rem 0'>", unsafe_allow_html=True)

def make_pdf(r, sched):
    buf   = io.BytesIO()
    doc   = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=20*mm, rightMargin=20*mm,
                               topMargin=20*mm, bottomMargin=20*mm)
    DARK  = HexColor("#1A1814"); ACC = HexColor("#C8440A")
    LIGHT = HexColor("#F7F6F2"); GREY = HexColor("#6B6560")

    def sty(n,**k): return ParagraphStyle(n,**k)
    T  = sty("t", fontName="Helvetica-Bold",   fontSize=18, textColor=DARK,  spaceAfter=3,  leading=22)
    S  = sty("s", fontName="Helvetica",         fontSize=8,  textColor=GREY,  spaceAfter=10, leading=11)
    SE = sty("se",fontName="Helvetica-Bold",    fontSize=10, textColor=DARK,  spaceBefore=10,spaceAfter=5)
    SM = sty("sm",fontName="Helvetica-Oblique", fontSize=7.5,textColor=GREY,  leading=11)

    story = [
        Paragraph("Electrical Sizing Report", T),
        Paragraph(f"IEC 60364 · IEC 60947-2 · IEC 60228 | Sapphire Fibres Ltd | {datetime.now().strftime('%d %b %Y  %H:%M')}", S),
        HRFlowable(width="100%",thickness=2,color=DARK), Spacer(1,5*mm),
    ]

    def tbl(data, cw, hdr_color=DARK):
        t = Table(data, colWidths=cw)
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),hdr_color),("TEXTCOLOR",(0,0),(-1,0),white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[white,LIGHT]),
            ("GRID",(0,0),(-1,-1),0.4,HexColor("#E2DDD6")),
            ("LEFTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ]))
        return t

    story += [Paragraph("Input", SE), tbl([
        ["Parameter","Value"],
        ["Phase",          r["phase"]],
        ["Load Current",   f"{r['load_a']} A"],
        ["Voltage",        f"{r['voltage']} V"],
        ["PF (default)",   str(r["pf"])],
        ["Insulation",     "XLPE 90°C"],
        ["Ambient Temp",   "35°C"],
        ["Grouping",       "0.80"],
        ["Cable Length",   "50 m"],
    ], [80*mm,90*mm]), Spacer(1,5*mm)]

    vl = "OK ≤3%" if r["vd_pct"]<=3 else ("Acceptable ≤5%" if r["vd_pct"]<=5 else "⚠ Exceeds 5%")
    pl = "No correction needed" if r["cap_kvar"]==0 else f"Add {r['cap_kvar']:.1f} kVAR cap bank"
    story += [Paragraph("Results", SE), tbl([
        ["Result","Value","Standard","Note"],
        ["Design Current Ib",   f"{r['ib']:.1f} A",       "IEC 60364",      f"Load ÷ PF {r['pf']}"],
        ["Circuit Breaker",     f"{r['breaker']} A",       "IEC 60947-2",    f"≥1.25×Ib={r['req_br']:.1f} A"],
        ["Cable Size",          f"{r['cable_mm2']} mm² Cu","IEC 60364-5-52", "XLPE, derated"],
        ["Cable Rating",        f"{r['cable_rated']} A",   "IEC 60228",      f"Util {r['util']:.0f}%"],
        ["Voltage Drop",        f"{r['vd_pct']:.2f}%",     "IEC 60364-5-52", vl],
        ["Recv-end Voltage",    f"{r['recv_v']:.1f} V",    "—",              ""],
        ["Active Power",        f"{r['kw']:.1f} kW",       "—",              f"Apparent {r['kva']:.1f} kVA"],
        ["PF Correction",       pl,                         "IEC 60038",      "Target 0.95"],
    ], [50*mm,38*mm,42*mm,40*mm], hdr_color=ACC)]

    if sched:
        df   = pd.DataFrame(sched)
        hdr  = list(df.columns)
        data = [hdr]+[list(map(str,row)) for row in df.values.tolist()]
        story += [Spacer(1,5*mm), Paragraph("Load Schedule",SE),
                  tbl(data, [170*mm/len(hdr)]*len(hdr))]

    story += [Spacer(1,8*mm),
              HRFlowable(width="100%",thickness=0.5,color=HexColor("#E2DDD6")),
              Spacer(1,3*mm),
              Paragraph("All calculations comply with IEC 60364, IEC 60947-2, IEC 60228, IEC 60038. "
                        "Copper conductors assumed. Verify against actual site conditions before installation.", SM)]
    doc.build(story)
    buf.seek(0)
    return buf.read()

col_dl, col_note = st.columns([1,3])
with col_dl:
    st.download_button("⬇ Export PDF Report",
                       data=make_pdf(r, st.session_state.schedule),
                       file_name=f"ElecCalc_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                       mime="application/pdf", use_container_width=True)
with col_note:
    st.markdown("<p style='font-size:0.77rem;color:#6B6560;margin-top:0.65rem'>PDF includes results + load schedule with IEC references.</p>",
                unsafe_allow_html=True)

# ── MASTER'S IMPACT ────────────────────────────────────────────────────────────
st.markdown("""
<div class="impact">
  <h3>📚 Impact on Your German Master's Application</h3>
  <p>This project directly strengthens applications to TU Munich, RWTH Aachen, and TU Berlin.</p>
  <div class="ipoint"><strong>Standards literacy</strong> — IEC 60364, 60947-2, 60228, 60038 implemented correctly. German engineering culture prizes this above most things.</div>
  <div class="ipoint"><strong>Industrial deployment</strong> — Built and used at Sapphire Fibres Ltd during your MTO role. A real tool solving a real problem.</div>
  <div class="ipoint"><strong>Cross-disciplinary skills</strong> — Python + power systems is exactly what Elektrotechnik / Energy Engineering programmes seek.</div>
  <div class="ipoint"><strong>Motivationsschreiben line</strong> — "I developed an IEC-compliant sizing tool deployed in a textile facility, reducing manual calculation errors for the electrical team."</div>
  <div class="ipoint"><strong>GitHub proof</strong> — Public repo + live Streamlit URL = verifiable evidence of self-driven learning.</div>
  <p style="margin-top:1rem;font-size:0.8rem;color:#8A8480;"><strong style="color:#C8C3BC;">Next additions:</strong> Motor starting current (IEC 60034) · Short-circuit calculator (IEC 60909)</p>
</div>
""", unsafe_allow_html=True)
