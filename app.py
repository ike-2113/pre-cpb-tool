# app.py

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
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))

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

with open(streamlit_logo_path, "rb") as img_file:
    st.image(img_file.read(), width=300)

st.title("Pre-CPB Planning Tool")

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

unit_system = st.radio("Units", ["Metric (cm/kg)", "Imperial (in/lb)"])
if unit_system == "Imperial (in/lb)":
    height = round(st.number_input("Height (in)", value=67) * 2.54, 2)
    weight = round(st.number_input("Weight (lb)", value=154) * 0.453592, 2)
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
            if val:
                additive_amounts[item] = val
        if albumin != "None":
            prime_additives.append(albumin)
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

bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)

comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])

if procedure in ["Dissection Repair – Stanford Type A", "Full Arch"] and pdf_arrest:
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])
else:
    arrest_temp = arrest_duration = neuro_strategy = None

if pdf_cardio:
    cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
    delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

selected_graft_images = []
if procedure == "CABG" and pdf_cabg:
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

blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
suggested_ci = 2.4 if ef >= 40 else 2.6 if ef >= 30 else 2.8
flow_suggested = calculate_flow(suggested_ci, bsa)
do2 = calculate_do2(flow_suggested, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow @ CI {suggested_ci}: {flow_suggested} L/min")
st.write(f"Post Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO₂: {do2} | DO₂i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")

# --- Perfusion Guidelines ---
st.subheader("🧠 Perfusion Guidelines")
if procedure.startswith("Dissection") or procedure.startswith("Full Arch"):
    if neuro_strategy == "ACP":
        st.info(f"ACP Flow: {int(weight*10)} mL/min | Pressure: 50–70 mmHg")
    if neuro_strategy == "RCP":
        st.info("RCP Max Sinus Pressure: ≤ 25 mmHg")
if "Retrograde" in delivery_routes:
    st.info("Retrograde Plegia: Sinus pressure ≤ 40 mmHg")
if "Antegrade" in delivery_routes:
    st.info("Antegrade Plegia: ≈ 200 mmHg line pressure")
if "Ostial" in delivery_routes:
    st.info("Ostial: 1 = 100–150 mmHg | 2 = ≈ 200 mmHg")
if procedure == "CABG":
    st.info("Vein Graft Test Flow: 50–70 mL/min @ ≈100 mmHg")

# --- Lab Reference Chart ---
st.subheader("🧪 Normal ABG & Electrolyte Ranges")
st.table({
    "Parameter": ["pH", "pCO₂", "pO₂", "HCO₃⁻", "Base Excess", "Lactate", "Ionized Ca²⁺", "Na⁺", "K⁺", "Cl⁻", "Mg²⁺", "Glucose"],
    "Range": ["7.35–7.45", "35–45 mmHg", "80–100 mmHg", "22–26 mmol/L", "-2 to +2", "0.5–2.0", "1.0–1.3 mmol/L", "135–145", "3.5–5.0", "95–105", "1.7–2.2", "110–180 (on bypass)"]
})

# --- Phenylephrine Calculator ---
st.subheader("💉 Phenylephrine Dilution")
neo_dose = st.number_input("Total Drug Dose (mg)", value=10.0)
neo_vol = st.number_input("Total Volume (mL)", value=100.0)
if neo_vol > 0:
    neo_conc = round((neo_dose * 1000) / neo_vol, 1)
    st.write(f"**Concentration:** {neo_conc} mcg/mL")
    st.write("**Bolus Dose:** 40–100 mcg | **Infusion:** 0.2–1 mcg/kg/min")

# --- Quick PDF Summary ---
st.subheader("📥 Download Quick Summary")
pdf_buffer = io.BytesIO()
pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
pdf.drawString(50, 750, "Pre-CPB Summary Report")
pdf.drawString(50, 730, f"BSA: {bsa} m² | DO₂i: {do2i} mL/min/m²")
pdf.drawString(50, 710, f"Hct: {post_hct}% | RBC Units: {rbc_units}")
pdf.drawString(50, 690, f"MAP Target: {map_target}")
pdf.drawString(50, 670, f"Prime: {base_prime} + {', '.join(prime_additives)}")
pdf.save()
st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="pre_cpb_summary.pdf", mime="application/pdf")
