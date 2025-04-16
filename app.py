# app.py — Complete Final Version with All Features

import streamlit as st
import os
import io
import pytz
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))

streamlit_logo_path = "streamlit_logo.png"
pdf_logo_path = "pdf_logo.png"

# ---- Calculation Functions ----
def calculate_bsa(height_cm, weight_kg): return round((height_cm * weight_kg / 3600) ** 0.5, 2)
def calculate_bmi(height_cm, weight_kg): return round(weight_kg / ((height_cm / 100) ** 2), 1)
def calculate_blood_volume(weight_kg): return round(weight_kg * 70)
def calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol, prime_hct=0):
    total_vol = blood_vol + prime_vol
    return round(((pre_hct / 100) * blood_vol + (prime_hct / 100) * prime_vol) / total_vol * 100, 1)
def calculate_rbc_units_needed(current_hct, target_hct): return max(0, round((target_hct - current_hct) / 3, 1))
def calculate_flow(ci, bsa): return round(ci * bsa, 2)
def calculate_do2(flow_L_min, hgb): return round(flow_L_min * 10 * (1.34 * hgb * 0.98 + 0.003 * 100), 1)
def get_map_target(comorbidities):
    if "CKD" in comorbidities or "Hypertension" in comorbidities: return "70–80 mmHg"
    elif "Aortic Disease" in comorbidities: return "80–90 mmHg"
    else: return "65–75 mmHg"
def calculate_heparin_dose(weight_kg): return round(weight_kg * 400)
def calculate_prime_osmolality(additives):
    osmo = 290
    for item in additives:
        if "Mannitol" in item: osmo += 10
        if "Bicarb" in item: osmo += 8
        if "Calcium" in item: osmo += 6
        if "Magnesium" in item: osmo += 4
        if "Albumin" in item: osmo += 2
        if "Heparin" in item: osmo += 1
    return osmo
# ---- Streamlit UI ----
st.title("Bypass Blueprint")
with st.sidebar:
    with open(streamlit_logo_path, "rb") as img_file:
        st.image(img_file.read(), width=250)

    st.markdown("## PDF Includes")

    pdf_height = st.checkbox("Height", True)
    pdf_weight = st.checkbox("Weight", True)
    pdf_bmi = st.checkbox("BMI", True)
    pdf_bsa = st.checkbox("BSA", True)
    pdf_pre_hct = st.checkbox("Pre-op Hct", True)
    pdf_pre_hgb = st.checkbox("Pre-op Hgb", True)
    pdf_prime_vol = st.checkbox("Prime Vol", True)
    pdf_prime_add = st.checkbox("Prime Additives", True)
    pdf_target_hct = st.checkbox("Target Hct", True)
    pdf_ef = st.checkbox("Ejection Fraction", True)
    pdf_comorbid = st.checkbox("Comorbidities / Pathology", True)
    pdf_cardio = st.checkbox("Cardioplegia", True)
    pdf_cabg = st.checkbox("CABG Grafts", True)
    pdf_arrest = st.checkbox("Arrest Plan", True)

unit_system = st.radio("Units", ["Metric (cm/kg)", "Imperial (in/lb)"])
if unit_system == "Imperial (in/lb)":
    height_in = st.number_input("Height (in)", value=67)
    weight_lb = st.number_input("Weight (lb)", value=154)
    height = round(height_in * 2.54, 2)
    weight = round(weight_lb * 0.453592, 2)
else:
    height = st.number_input("Height (cm)", value=170)
    weight = st.number_input("Weight (kg)", value=70)

pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)
prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400) if pdf_prime_vol else 0

base_prime = None
prime_additives = []
prime_osmo = 290
if pdf_prime_vol:
    base_prime = st.selectbox("Base Prime Fluid", ["", "Plasmalyte A", "Normosol-R", "LR", "Other"])
    if base_prime:
        albumin = st.selectbox("Albumin", ["None", "5% Albumin", "25% Albumin"])
        additives = ["Mannitol (g)", "Heparin (units)", "Bicarb (mEq)", "Calcium (mg)", "Magnesium (mg)"]
        additive_amounts = {}
        for item in additives:
            val = st.text_input(f"{item} in Prime", value="")
            if val: additive_amounts[item] = val
        if albumin != "None": prime_additives.append(albumin)
        prime_additives += [f"{k}: {v}" for k, v in additive_amounts.items()]
        prime_osmo = calculate_prime_osmolality(prime_additives)
        if prime_osmo < 270:
            st.warning(f"Osmolality LOW: {prime_osmo} mOsm/kg")
        elif prime_osmo > 310:
            st.warning(f"Osmolality HIGH: {prime_osmo} mOsm/kg")
        else:
            st.success(f"Osmolality normal: {prime_osmo} mOsm/kg")

target_hct = st.number_input("Target Hematocrit (%)", value=25.0)
ef = st.number_input("Ejection Fraction (%)", value=55)
procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])
comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
valve_issues = st.multiselect("Valve Pathology", ["Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis", "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"])
# ---- Arrest Plan ----
if procedure in ["Dissection Repair – Stanford Type A", "Full Arch"] and pdf_arrest:
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])
else:
    arrest_temp = arrest_duration = neuro_strategy = None

# ---- Cardioplegia ----
if pdf_cardio:
    cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
    delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

# ---- CABG Grafts ----
selected_graft_images = []
if procedure == "CABG" and pdf_cabg:
    st.subheader("CABG Graft Planner")
    num_grafts = st.number_input("Number of Grafts", 1, 5)
    graft_image_map = {
        "LAD": "graft_overview_before_after.png",
        "LCx": "rima_lcx_free.png",
        "OM1": "rima_lcx_insitu.png",
        "OM2": "composite_lima_rima_lcx.png",
        "PDA": "rima_rca.png",
        "RCA": "radial_rca.png",
    }
    for i in range(num_grafts):
        target = st.selectbox(f"Graft {i+1} Target", list(graft_image_map), key=f"graft_{i}")
        image_path = graft_image_map.get(target)
        if image_path and os.path.exists(image_path):
            st.image(image_path, width=250)
            selected_graft_images.append(image_path)

# ---- Calculations ----
bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
suggested_ci = 2.4 if ef >= 40 else 2.6 if ef >= 30 else 2.8
flow = calculate_flow(suggested_ci, bsa)
do2 = calculate_do2(flow, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# ---- Outputs ----
st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow @ CI {suggested_ci}: {flow} L/min")
st.write(f"Post Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO2: {do2} | DO2i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")
st.markdown("### CI Comparison")

for ci in [1.8, 2.4, 3.0]:
    flow_ci = calculate_flow(ci, bsa)
    do2_ci = calculate_do2(flow_ci, pre_hgb)
    do2i_ci = round(do2_ci / bsa, 1)

    st.write(f"**CI {ci}** → Flow: {flow_ci} L/min | DO₂: {do2_ci} | DO₂i: {do2i_ci}")
# ---- PDF Export ----
pdf_buffer = io.BytesIO()
doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
styles = getSampleStyleSheet()
formula_style = ParagraphStyle(name='Formula', fontSize=9)
story = []

def formula_block(label, value, formula, calc):
    story.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
    story.append(Paragraph(f"<font size=9>{formula}</font>", formula_style))
    story.append(Paragraph(f"<font size=9><i>{calc}</i></font>", formula_style))
    story.append(Spacer(1, 6))

from reportlab.platypus import Table, TableStyle

title_block = Table([
    [RLImage(pdf_logo_path, width=80, height=80), Paragraph("<b>Perfusion Sentinel Report</b>", styles['Title'])]
], colWidths=[90, 400])
title_block.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))

story.append(title_block)
story.append(Spacer(1, 12))
story.append(Paragraph(f"<b>Procedure:</b> {procedure}", styles["Heading2"]))
story.append(Spacer(1, 8))  # consistent spacing

# Always include patient section if any of its sub-fields are selected
if any([pdf_height, pdf_weight, pdf_bmi, pdf_bsa, pdf_pre_hct, pdf_pre_hgb,
        pdf_prime_vol, pdf_prime_add, pdf_target_hct, pdf_ef, pdf_comorbid]):
    story.append(Paragraph("Patient Data", styles['Heading2']))
    if pdf_height: story.append(Paragraph(f"Height: {height} cm", styles["Normal"]))
    if pdf_weight: story.append(Paragraph(f"Weight: {weight} kg", styles["Normal"]))
    if pdf_bmi: formula_block("BMI", bmi, "BMI = Weight / (Height / 100)^2", f"{weight} / ({height}/100)^2")
    if pdf_bsa: formula_block("BSA", bsa, "BSA = √(Height × Weight / 3600)", f"√({height} × {weight} / 3600)")
    if pdf_pre_hct: story.append(Paragraph(f"Pre-op Hct: {pre_hct}%", styles["Normal"]))
    if pdf_pre_hgb: story.append(Paragraph(f"Pre-op Hgb: {pre_hgb:.2f} g/dL", styles["Normal"]))
    if pdf_prime_vol:
        story.append(Paragraph(f"Prime Volume: {prime_vol} mL", styles["Normal"]))
        story.append(Paragraph(f"Prime Osmolality Estimate: {prime_osmo} mOsm/kg", styles["Normal"]))
    if base_prime: story.append(Paragraph(f"Base Prime: {base_prime}", styles["Normal"]))
    if pdf_prime_add and prime_additives:
        story.append(Paragraph(f"Additives: {', '.join(prime_additives)}", styles["Normal"]))
    if pdf_target_hct: story.append(Paragraph(f"Target Hct: {target_hct}%", styles["Normal"]))
    if pdf_ef: story.append(Paragraph(f"Ejection Fraction: {ef}%", styles["Normal"]))
    if pdf_comorbid: story.append(Paragraph(f"Comorbidities: {', '.join(comorbidities)}", styles["Normal"]))
    if valve_issues: story.append(Paragraph(f"Valve Pathology: {', '.join(valve_issues)}", styles["Normal"]))

if pdf_cardio:
    story.append(Paragraph("Cardioplegia", styles["Heading2"]))
    story.append(Paragraph(f"Type: {cardioplegia_type}", styles["Normal"]))
    story.append(Paragraph(f"Routes: {', '.join(delivery_routes)}", styles["Normal"]))

if pdf_arrest and arrest_temp:
    story.append(Paragraph("Circulatory Arrest Plan", styles["Heading2"]))
    story.append(Paragraph(f"Target Temp: {arrest_temp}°C", styles["Normal"]))
    story.append(Paragraph(f"Duration: {arrest_duration} min", styles["Normal"]))
    story.append(Paragraph(f"Neuro Strategy: {neuro_strategy}", styles["Normal"]))

from reportlab.platypus import Table

if pdf_cabg and selected_graft_images:
    story.append(Paragraph("CABG Grafts", styles["Heading2"]))
    image_cells = [RLImage(img, width=120, height=99) for img in selected_graft_images]
    graft_table = Table([image_cells], hAlign='LEFT')  # 1 row, N columns
    story.append(graft_table)
    story.append(Spacer(1, 12))

story.append(Paragraph("Perfusion Summary", styles["Heading2"]))
# Additional CI comparison block
ci_list = [1.8, 2.4, 3.0]
story.append(Spacer(1, 12))
story.append(Paragraph("<b>Flow / DO2 / DO2i @ Multiple Cardiac Indexes</b>", styles["Normal"]))

for ci in ci_list:
    flow_ci = calculate_flow(ci, bsa)
    do2_ci = calculate_do2(flow_ci, pre_hgb)
    do2i_ci = round(do2_ci / bsa, 1)

    story.append(Paragraph(f"Flow @ CI {ci}: {flow_ci} L/min", styles["Normal"]))
    story.append(Paragraph(f"DO2: {do2_ci} | DO2i: {do2i_ci}", styles["Normal"]))
    story.append(Spacer(1, 6))
formula_block("Blood Volume", f"{blood_vol} mL", "BV = Weight × 70", f"{weight} × 70")
formula_block("Post Hct", f"{post_hct}%", "[(Hct × BV) + (0 × PV)] / (BV + PV)", f"({pre_hct}% × {blood_vol}) / ({blood_vol} + {prime_vol})")
formula_block("RBC Units", f"{rbc_units}", "(Target − Post) ÷ 3", f"({target_hct} − {post_hct}) ÷ 3")
formula_block("Flow", f"{flow} L/min", "CI × BSA", f"{suggested_ci} × {bsa}")
formula_block("DO2", f"{do2}", "Flow × 10 × (1.34 × Hgb × 0.98 + 0.003 × 100)", f"{flow} × 10 × (1.34 × {pre_hgb:.2f} × 0.98 + 0.3)")
formula_block("DO2i", f"{do2i}", "DO2 ÷ BSA", f"{do2} ÷ {bsa}")
formula_block("Heparin Dose", f"{heparin_dose} units", "Weight × 400", f"{weight} × 400")
story.append(Paragraph(f"<b>MAP Target:</b> {map_target}", styles["Normal"]))

timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime('%Y-%m-%d %I:%M %p')
story.append(Spacer(1, 12))
story.append(Paragraph(f"Generated {timestamp}", ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=1)))
doc.build(story)

st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
