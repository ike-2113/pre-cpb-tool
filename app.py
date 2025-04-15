# app.py

import streamlit as st
import os
import io
from datetime import datetime
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

streamlit_logo_path = "streamlit_logo.png"
pdf_logo_path = "pdf_logo.png"

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

with open(streamlit_logo_path, "rb") as img_file:
    st.image(img_file.read(), width=300)

st.title("Pre-CPB Planning Tool")

# --- Section Checkboxes ---
include_patient = st.checkbox("📋 Include Patient Data", value=True)
include_ef = st.checkbox("📋 Include Ejection Fraction", value=True)
include_pathology = st.checkbox("📋 Include Pathology / Comorbidities", value=True)
include_cabg = st.checkbox("📋 Include CABG Grafts", value=True)
include_cardio = st.checkbox("📋 Include Cardioplegia", value=True)
include_arrest = st.checkbox("📋 Include Arrest Planning", value=True)

# --- Patient Info ---
height = st.number_input("Height (cm)", value=170)
weight = st.number_input("Weight (kg)", value=70)
pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)
prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400)
target_hct = st.number_input("Target Hematocrit (%)", value=25.0)
ef = st.number_input("Ejection Fraction (%)", value=55) if include_ef else None
bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)

# --- Other Inputs ---
base_prime = st.selectbox("Base Prime Fluid", ["None", "Plasmalyte A", "Normosol-R"])
prime_additives = st.multiselect("Prime Additives", ["Albumin", "Mannitol", "Heparin", "Bicarb", "Calcium", "Magnesium"])
comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
valve_issues = st.multiselect("Valve Pathology", ["Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis", "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"])
procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])

# --- Arrest Planning ---
if include_arrest and procedure in ["Dissection Repair – Stanford Type A", "Full Arch"]:
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])
else:
    arrest_temp, arrest_duration, neuro_strategy = None, None, None

# --- Cardioplegia ---
if include_cardio:
    cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
    delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

# --- CABG Grafts ---
selected_graft_images = []
if include_cabg and procedure == "CABG":
    num_grafts = st.number_input("Number of Grafts", min_value=1, max_value=5, step=1)
    graft_image_map = {
        "LAD": "graft_overview_before_after.png",
        "LCx": "rima_lcx_free.png",
        "OM1": "rima_lcx_insitu.png",
        "OM2": "composite_lima_rima_lcx.png",
        "PDA": "rima_rca.png",
        "RCA": "radial_rca.png",
    }
    for i in range(int(num_grafts)):
        target = st.selectbox(f"Graft {i+1} Target", list(graft_image_map.keys()), key=f"target_{i}")
        file = graft_image_map.get(target)
        if file and os.path.exists(file):
            st.image(file, width=250)
            selected_graft_images.append(file)

# --- Calculations ---
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
flow_1_8, flow_2_4, flow_3_0 = calculate_flow(1.8, bsa), calculate_flow(2.4, bsa), calculate_flow(3.0, bsa)
suggested_ci = 2.4
if ef and ef < 40: suggested_ci = 2.6
if ef and ef < 30: suggested_ci = 2.8
flow_suggested = calculate_flow(suggested_ci, bsa)
do2 = calculate_do2(flow_suggested, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# --- Output ---
st.header("📊 Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flows: CI 1.8={flow_1_8}, CI 2.4={flow_2_4}, CI 3.0={flow_3_0}")
st.write(f"Suggested CI={suggested_ci}, Flow={flow_suggested} L/min")
st.write(f"Post Hct: {post_hct}% | RBCs Needed: {rbc_units}")
st.write(f"DO₂: {do2} | DO₂i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")

# --- Sidebar Preview ---
with st.sidebar:
    st.markdown("### 📄 PDF Includes")
    st.markdown(f"- Patient Data: {'✅' if include_patient else '❌'}")
    st.markdown(f"  • EF: {'✅' if include_ef else '❌'}")
    st.markdown(f"- CABG Grafts: {'✅' if include_cabg else '❌'}")
    st.markdown(f"- Cardioplegia: {'✅' if include_cardio else '❌'}")
    st.markdown(f"- Arrest Plan: {'✅' if include_arrest else '❌'}")

# --- PDF ---
pdf_buffer = io.BytesIO()
doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
styles = getSampleStyleSheet()
story = []

story.append(RLImage(pdf_logo_path, width=200, height=200))
story.append(Paragraph("<b>Perfusion Sentinel</b>", styles['Title']))
story.append(Spacer(1, 20))
story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
story.append(Paragraph(f"BSA: {bsa} | BMI: {bmi}", styles['Normal']))
story.append(Paragraph(f"Flow: {flow_suggested} (CI {suggested_ci})", styles['Normal']))
story.append(Paragraph(f"DO₂: {do2} | DO₂i: {do2i}", styles['Normal']))
story.append(Paragraph(f"RBC Units: {rbc_units} | Heparin: {heparin_dose} | MAP: {map_target}", styles['Normal']))
story.append(Spacer(1, 12))

if include_cabg and selected_graft_images:
    story.append(Paragraph("<b>Graft Diagrams</b>", styles['Heading2']))
    for i, img in enumerate(selected_graft_images):
        story.append(Paragraph(f"Graft {i+1}", styles['Normal']))
        story.append(RLImage(img, width=200, height=150))
        story.append(Spacer(1, 10))

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
footer_style = ParagraphStyle(name='FooterStyle', fontSize=8, textColor=colors.grey, alignment=1)
story.append(Spacer(1, 30))
story.append(Paragraph(f"Generated on {timestamp} by Perfusion Sentinel", footer_style))
doc.build(story)

st.download_button("📥 Download PDF", data=pdf_buffer.getvalue(), file_name="pre_cpb_summary.pdf", mime="application/pdf")
