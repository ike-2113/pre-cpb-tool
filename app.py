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

pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))

streamlit_logo_path = "streamlit_logo.png"
pdf_logo_path = "pdf_logo.png"

def calculate_bsa(height_cm, weight_kg): return round(((height_cm * weight_kg) / 3600) ** 0.5, 2)
def calculate_bmi(height_cm, weight_kg): return round(weight_kg / ((height_cm / 100) ** 2), 1)
def calculate_blood_volume(weight_kg): return round(weight_kg * 70)
def calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol, prime_hct=0): return round(((pre_hct / 100) * blood_vol + (prime_hct / 100) * prime_vol) / (blood_vol + prime_vol) * 100, 1)
def calculate_rbc_units_needed(current_hct, target_hct): return max(0, round((target_hct - current_hct) / 3, 1))
def calculate_flow(ci, bsa): return round(ci * bsa, 2)
def calculate_do2(flow, hgb): return round(flow * 10 * (1.34 * hgb * 0.98 + 0.003 * 100), 1)
def get_map_target(comorbidities):
    if "CKD" in comorbidities or "Hypertension" in comorbidities: return "70–80 mmHg"
    elif "Aortic Disease" in comorbidities: return "80–90 mmHg"
    return "65–75 mmHg"
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

unit_system = st.radio("Units", ["Metric (cm/kg)", "Imperial (in/lb)"])
if unit_system == "Imperial (in/lb)":
    height = round(st.number_input("Height (in)", value=67) * 2.54, 2)
    weight = round(st.number_input("Weight (lb)", value=154) * 0.453592, 2)
else:
    height = st.number_input("Height (cm)", value=170)
    weight = st.number_input("Weight (kg)", value=70)

pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)
prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400)

# Prime fluid
base_prime = st.selectbox("Base Prime Fluid", ["", "Plasmalyte A", "Normosol-R", "LR", "Other"])
albumin = st.selectbox("Albumin", ["None", "5% Albumin", "25% Albumin"])
additives = [ "Mannitol (g)", "Heparin (units)", "Bicarb (mEq)", "Calcium (mg)", "Magnesium (mg)" ]
additive_inputs = {}
for a in additives:
    val = st.text_input(f"{a} in Prime", "")
    if val: additive_inputs[a] = val
prime_additives = [albumin] if albumin != "None" else []
prime_additives += [f"{k}: {v}" for k, v in additive_inputs.items()]
prime_osmo = calculate_prime_osmolality(prime_additives)
if prime_osmo < 270: st.warning(f"Osmolality LOW: {prime_osmo} mOsm/kg")
elif prime_osmo > 310: st.warning(f"Osmolality HIGH: {prime_osmo} mOsm/kg")
else: st.success(f"Osmolality normal: {prime_osmo} mOsm/kg")

target_hct = st.number_input("Target Hematocrit (%)", value=25.0)
ef = st.number_input("Ejection Fraction (%)", value=55)

comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])

arrest_temp = arrest_duration = neuro_strategy = None
if procedure in ["Dissection Repair – Stanford Type A", "Full Arch"]:
    arrest_temp = st.number_input("Target Arrest Temp (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])

cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

# CABG grafts
selected_graft_images = []
if procedure == "CABG":
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

# Final Calcs
bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
flow_low = calculate_flow(1.8, bsa)
flow_target = calculate_flow(2.4, bsa)
flow_high = calculate_flow(3.0, bsa)
ci_used = 2.8 if ef < 30 else 2.6 if ef < 40 else 2.4
flow_suggested = calculate_flow(ci_used, bsa)
do2 = calculate_do2(flow_suggested, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# Output
st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow Index Range: Low 1.8 → {flow_low} L/min | Target 2.4 → {flow_target} L/min | High 3.0 → {flow_high} L/min")
st.write(f"Flow @ CI {ci_used}: {flow_suggested} L/min")
st.write(f"Post Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO2: {do2} | DO2i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")

# Generate PDF
if st.button("Generate PDF"):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    story.append(RLImage(pdf_logo_path, width=180, height=180))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Procedure:</b> {procedure}", styles['Heading1']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Flow Range:</b> 1.8 → {flow_low} | 2.4 → {flow_target} | 3.0 → {flow_high}", styles['Normal']))
    story.append(Paragraph(f"<b>MAP Target:</b> {map_target}", styles['Normal']))
    story.append(Paragraph(f"<b>DO2:</b> {do2} | <b>DO2i:</b> {do2i}", styles['Normal']))
    story.append(Paragraph(f"<b>Post Hct:</b> {post_hct}% | <b>RBC Units:</b> {rbc_units}", styles['Normal']))
    story.append(Paragraph(f"<b>Heparin Dose:</b> {heparin_dose} units", styles['Normal']))
    story.append(Paragraph(f"<b>Prime Osmolality:</b> {prime_osmo} mOsm/kg", styles['Normal']))
    story.append(Spacer(1, 10))
    for i, img in enumerate(selected_graft_images):
        story.append(RLImage(img, width=200, height=150))
        story.append(Spacer(1, 6))
    footer = ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=1)
    timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime('%Y-%m-%d %I:%M %p')
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated {timestamp}", footer))
    doc.build(story)
    st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
