# app.py — Final with Working CABG Grafts and PDF Export

import streamlit as st
import os
import io
import pytz
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

streamlit_logo_path = "streamlit_logo.png"
pdf_logo_path = "pdf_logo.png"

# ---- Calculations ----
def calculate_bsa(height_cm, weight_kg): return round(0.007184 * (height_cm ** 0.725) * (weight_kg ** 0.425), 2)
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

# ---- UI ----
with open(streamlit_logo_path, "rb") as img_file:
    st.image(img_file.read(), width=300)

st.title("Pre-CPB Planning Tool")

# Sidebar checkboxes
with st.sidebar:
    st.markdown("## PDF Includes")
    pdf_patient = st.checkbox("Patient Data", True)
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

# ---- Inputs ----
height = st.number_input("Height (cm)", value=170)
weight = st.number_input("Weight (kg)", value=70)
pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)
prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400) if pdf_prime_vol else 0

prime_additives = []
if pdf_prime_add:
    prime_additives = st.multiselect("Prime Additives", ["Albumin", "Mannitol", "Heparin", "Bicarb", "Calcium", "Magnesium"])

target_hct = st.number_input("Target Hematocrit (%)", value=25.0)
ef = st.number_input("Ejection Fraction (%)", value=55)

bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)

base_prime = st.selectbox("Base Prime Fluid", ["None", "Plasmalyte A", "Normosol-R"])
comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
valve_issues = st.multiselect("Valve Pathology", ["Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis", "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"])
procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])

# ---- Arrest ----
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
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
suggested_ci = 2.4 if ef >= 40 else 2.6 if ef >= 30 else 2.8
flow_suggested = calculate_flow(suggested_ci, bsa)
do2 = calculate_do2(flow_suggested, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# ---- Output ----
st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow @ CI {suggested_ci}: {flow_suggested} L/min")
st.write(f"Post Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO₂: {do2} | DO₂i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")

# ---- PDF Export ----
pdf_buffer = io.BytesIO()
doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
styles = getSampleStyleSheet()
story = []

story.append(RLImage(pdf_logo_path, width=200, height=200))
story.append(Paragraph("Perfusion Sentinel Report", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph(f"Procedure: {procedure}", styles["Normal"]))

if pdf_patient:
    story.append(Paragraph("Patient Data", styles['Heading2']))
    if pdf_height: story.append(Paragraph(f"Height: {height} cm", styles['Normal']))
    if pdf_weight: story.append(Paragraph(f"Weight: {weight} kg", styles['Normal']))
    if pdf_bmi: story.append(Paragraph(f"BMI: {bmi}", styles['Normal']))
    if pdf_bsa: story.append(Paragraph(f"BSA: {bsa} m²", styles['Normal']))
    if pdf_pre_hct: story.append(Paragraph(f"Pre-op Hct: {pre_hct}%", styles['Normal']))
    if pdf_pre_hgb: story.append(Paragraph(f"Pre-op Hgb: {pre_hgb:.2f} g/dL", styles['Normal']))
    if pdf_prime_vol: story.append(Paragraph(f"Prime Volume: {prime_vol} mL", styles['Normal']))
    if pdf_prime_add: story.append(Paragraph(f"Additives: {', '.join(prime_additives) or 'None'}", styles['Normal']))
    if pdf_target_hct: story.append(Paragraph(f"Target Hct: {target_hct}%", styles['Normal']))
    if pdf_ef: story.append(Paragraph(f"Ejection Fraction: {ef}%", styles['Normal']))

if pdf_cardio:
    story.append(Paragraph("Cardioplegia", styles["Heading2"]))
    story.append(Paragraph(f"Type: {cardioplegia_type}", styles["Normal"]))
    story.append(Paragraph(f"Routes: {', '.join(delivery_routes)}", styles["Normal"]))

if pdf_arrest and arrest_temp:
    story.append(Paragraph("Circulatory Arrest Plan", styles["Heading2"]))
    story.append(Paragraph(f"Target Temp: {arrest_temp}°C", styles["Normal"]))
    story.append(Paragraph(f"Duration: {arrest_duration} min", styles["Normal"]))
    story.append(Paragraph(f"Neuro Strategy: {neuro_strategy}", styles["Normal"]))

if pdf_cabg and selected_graft_images:
    story.append(Paragraph("CABG Grafts", styles["Heading2"]))
    for i, img in enumerate(selected_graft_images):
        story.append(RLImage(img, width=200, height=150))
        story.append(Spacer(1, 10))

story.append(Paragraph("Perfusion Summary", styles["Heading2"]))
story.append(Paragraph(f"Flow: {flow_suggested} L/min (CI {suggested_ci})", styles["Normal"]))
story.append(Paragraph(f"DO₂: {do2} | DO₂i: {do2i}", styles["Normal"]))
story.append(Paragraph(f"MAP Target: {map_target}", styles["Normal"]))
story.append(Paragraph(f"Heparin Dose: {heparin_dose}", styles["Normal"]))
story.append(Paragraph(f"Post Hct: {post_hct}% | RBC Units: {rbc_units}", styles["Normal"]))

timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime('%Y-%m-%d %I:%M %p')
footer_style = ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=1)
story.append(Spacer(1, 20))
story.append(Paragraph(f"Generated {timestamp}", footer_style))

doc.build(story)

st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
