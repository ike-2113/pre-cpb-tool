# app.py

import streamlit as st
import os
import io
import pathlib
from PIL import Image
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# --- Logo Paths ---
streamlit_logo_path = "/mnt/data/Screenshot 2025-04-01 at 2.42.36 PM.png"
pdf_logo_path = "/mnt/data/Screenshot 2025-04-01 at 2.42.36 PM-modified.png"

# --- Functions ---
def calculate_bsa(height_cm, weight_kg):
    return round(0.007184 * (height_cm ** 0.725) * (weight_kg ** 0.425), 2)

def calculate_bmi(height_cm, weight_kg):
    return round(weight_kg / ((height_cm / 100) ** 2), 1)

def calculate_blood_volume(weight_kg):
    return round(weight_kg * 70)

def calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol, prime_hct=0):
    total_vol = blood_vol + prime_vol
    return round(((pre_hct / 100) * blood_vol + (prime_hct / 100) * prime_vol) / total_vol * 100, 1)

def calculate_rbc_units_needed(current_hct, target_hct):
    delta = target_hct - current_hct
    return max(0, round(delta / 3, 1))

def calculate_flow(ci, bsa):
    return round(ci * bsa, 2)

def calculate_do2(flow_L_min, hgb):
    return round(flow_L_min * 10 * (1.34 * hgb * 0.98 + 0.003 * 100), 1)

def get_map_target(comorbidities):
    if "CKD" in comorbidities or "Hypertension" in comorbidities:
        return "70–80 mmHg"
    elif "Aortic Disease" in comorbidities:
        return "80–90 mmHg"
    else:
        return "65–75 mmHg"

def calculate_heparin_dose(weight_kg):
    return round(weight_kg * 400)

# --- UI ---
st.image(streamlit_logo_path, width=300)
st.title("Pre-CPB Planning Tool")

# --- Section Toggles ---
show_patient = st.checkbox("Patient Data", value=True)
show_circulatory = st.checkbox("Circulatory Arrest Planning", value=True)
show_cardioplegia = st.checkbox("Cardioplegia", value=True)
show_cabg = st.checkbox("CABG Grafts", value=True)
show_neo = st.checkbox("Phenylephrine", value=True)
show_calc = st.checkbox("Calculated Outputs", value=True)

# --- Patient Info ---
if show_patient:
    st.header("Patient Data")
    col1, col2 = st.columns(2)
    with col1:
        height = st.number_input("Height (cm)", value=170)
        weight = st.number_input("Weight (kg)", value=70)
        ef = st.number_input("Ejection Fraction (%)", value=55)
    with col2:
        pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
        pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)

    bmi = calculate_bmi(height, weight)
    bsa = calculate_bsa(height, weight)

    prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400)
    base_prime = st.selectbox("Base Prime Fluid", ["None", "Plasmalyte A", "Normosol-R"])
    prime_additives = st.multiselect("Prime Additives", ["Albumin", "Mannitol", "Heparin", "Bicarb", "Calcium", "Magnesium"])
    target_hct = st.number_input("Target Hematocrit (%)", value=25.0)

    comorbidities = st.multiselect("Comorbidities", [
        "CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"
    ])
    valve_issues = st.multiselect("Valve Pathology", [
        "Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis",
        "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"
    ])
    procedure = st.selectbox("Procedure Type", [
        "CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", 
        "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B",
        "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"
    ])

# --- Arrest Planning ---
if show_circulatory and procedure in ["Dissection Repair – Stanford Type A", "Full Arch"]:
    st.subheader("Circulatory Arrest Planning")
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])
else:
    arrest_temp = None

# --- Cardioplegia ---
if show_cardioplegia:
    st.subheader("Cardioplegia Selection")
    cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
    delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

# --- CABG ---
selected_graft_images = []
if show_cabg and procedure == "CABG":
    st.subheader("CABG Graft Planner")
    num_grafts = st.number_input("Number of Grafts", min_value=1, max_value=5, step=1)
    image_dir = pathlib.Path(__file__).parent / "images"
    for i in range(int(num_grafts)):
        target = st.selectbox(f"Graft {i+1} Target", ["LAD", "LCx", "OM1", "OM2", "PDA", "RCA"], key=f"target_{i}")
        matched_images = [img for img in os.listdir(image_dir) if target.lower() in img.lower()] if image_dir.exists() else []
        if matched_images:
            selected_file = matched_images[0]
            selected_graft_images.append(selected_file)
            st.image(image_dir / selected_file, width=250, caption=f"{target} Graft Diagram")
        uploaded_file = st.file_uploader(f"Or upload custom image for Graft {i+1}", type=["png", "jpg"], key=f"upload_{i}")
        if uploaded_file:
            st.image(uploaded_file, width=250, caption=f"Custom Upload for {target}")

# --- Neo ---
if show_neo:
    st.subheader("Phenylephrine Dilution")
    neo_dose = st.number_input("Total Drug Dose (mg)", value=10.0)
    neo_vol = st.number_input("Total Volume (mL)", value=100.0)
    if neo_vol > 0:
        conc = round((neo_dose * 1000) / neo_vol, 1)
        st.write(f"**Concentration:** {conc} mcg/mL")

# --- Calculations & Output ---
if show_patient and show_calc:
    blood_vol = calculate_blood_volume(weight)
    post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
    rbc_units = calculate_rbc_units_needed(post_hct, target_hct)

    flow_1_8 = calculate_flow(1.8, bsa)
    flow_2_4 = calculate_flow(2.4, bsa)
    flow_3_0 = calculate_flow(3.0, bsa)

    suggested_ci = 2.4
    if ef < 40: suggested_ci = 2.6
    if ef < 30: suggested_ci = 2.8
    if arrest_temp and arrest_temp < 22: suggested_ci -= 0.2

    flow_suggested = calculate_flow(suggested_ci, bsa)
    do2 = calculate_do2(flow_suggested, pre_hgb)
    do2i = round(do2 / bsa, 1)

    map_target = get_map_target(comorbidities)
    heparin_dose = calculate_heparin_dose(weight)

    st.header("📊 Calculated Outputs")
    st.write(f"BMI: {bmi} | BSA: {bsa} m²")
    st.write(f"Flow @ CI 1.8: {flow_1_8} L/min")
    st.write(f"Flow @ CI 2.4: {flow_2_4} L/min")
    st.write(f"Flow @ CI 3.0: {flow_3_0} L/min")
    st.write(f"Target Flow: {flow_suggested} L/min (CI {suggested_ci})")
    st.write(f"Post-Dilution Hct: {post_hct}% | RBC Units: {rbc_units}")
    st.write(f"DO₂: {do2} mL/min | DO₂i: {do2i} mL/min/m²")
    st.write(f"MAP Target: {map_target}")
    st.write(f"Heparin Dose: {heparin_dose} units")

    if do2i < 280:
        st.warning(f"⚠️ DO₂i below safe threshold: {do2i} mL/min/m²")
    if post_hct < 21:
        st.warning("⚠️ Post-dilution Hct is critically low")

# --- PDF Export ---
if show_patient:
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []

    story.append(RLImage(pdf_logo_path, width=200, height=200))
    story.append(Paragraph("<b>Perfusion Sentinel</b>", styles['Title']))
    story.append(Paragraph("<i>Precision Innovation</i>", styles['Normal']))
    story.append(Spacer(1, 20))

    if show_calc:
        story.append(Paragraph("<b>Perfusion Summary</b>", styles['Heading2']))
        story.append(Paragraph(f"BSA: {bsa} m² | BMI: {bmi}", styles['Normal']))
        story.append(Paragraph(f"Flow Target: {flow_suggested} L/min (CI {suggested_ci})", styles['Normal']))
        story.append(Paragraph(f"DO₂: {do2} | DO₂i: {do2i}", styles['Normal']))
        story.append(Paragraph(f"RBC Units Needed: {rbc_units}", styles['Normal']))
        story.append(Spacer(1, 10))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer_style = ParagraphStyle(name='FooterStyle', fontSize=8, textColor=colors.grey, alignment=1)
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Generated on {timestamp} by Perfusion Sentinel", footer_style))

    doc.build(story)
    st.download_button("Download PDF Summary", data=pdf_buffer.getvalue(), file_name="pre_cpb_summary.pdf", mime="application/pdf")
