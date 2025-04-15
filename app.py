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

bsa = calculate_bsa(height, weight)
bmi = calculate_bmi(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
suggested_ci = 2.4
if ef < 40: suggested_ci = 2.6
if ef < 30: suggested_ci = 2.8
flow_suggested = calculate_flow(suggested_ci, bsa)
do2 = calculate_do2(flow_suggested, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"]))
heparin_dose = calculate_heparin_dose(weight)

st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow @ CI {suggested_ci}: {flow_suggested} L/min")
st.write(f"Post Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO2: {do2} | DO2i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")

pdf_buffer = io.BytesIO()
doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
styles = getSampleStyleSheet()
header_style = ParagraphStyle(name='Header', fontSize=14, spaceAfter=10, textColor=colors.darkblue)
formula_style = ParagraphStyle(name='Formula', fontSize=9)

story = []
story.append(RLImage(pdf_logo_path, width=200, height=200))
story.append(Paragraph("Perfusion Sentinel Report", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph(f"<b>Procedure:</b> {st.selectbox('Procedure Type', ['CABG', 'AVR', 'MVR', 'Transplant', 'Hemiarch', 'Bentall', 'Full Arch', 'Dissection Repair – Stanford Type A', 'Dissection Repair – Stanford Type B', 'LVAD', 'Off-pump CABG', 'ECMO Cannulation', 'Standby', 'Other'])}", header_style))

if pdf_patient:
    story.append(Paragraph("Patient Data", styles['Heading2']))
    if pdf_height: story.append(Paragraph(f"Height: {height} cm", styles['Normal']))
    if pdf_weight: story.append(Paragraph(f"Weight: {weight} kg", styles['Normal']))
    if pdf_bmi: story.append(Paragraph(f"BMI: {bmi}", styles['Normal']))
    if pdf_bsa: story.append(Paragraph(f"BSA: {bsa} m²", styles['Normal']))
    if pdf_pre_hct: story.append(Paragraph(f"Pre-op Hct: {pre_hct}%", styles['Normal']))
    if pdf_pre_hgb: story.append(Paragraph(f"Pre-op Hgb: {pre_hgb:.2f} g/dL", styles['Normal']))
    if pdf_prime_vol:
        story.append(Paragraph(f"Prime Volume: {prime_vol} mL", styles['Normal']))
        story.append(Paragraph(f"Prime Osmolality Estimate: {prime_osmo} mOsm/kg", styles['Normal']))
        if base_prime: story.append(Paragraph(f"Base Prime: {base_prime}", styles['Normal']))
        if pdf_prime_add and prime_additives:
            story.append(Paragraph(f"Additives: {', '.join(prime_additives)}", styles['Normal']))
    if pdf_target_hct: story.append(Paragraph(f"Target Hct: {target_hct}%", styles['Normal']))
    if pdf_ef: story.append(Paragraph(f"Ejection Fraction: {ef}%", styles['Normal']))
    story.append(Spacer(1, 12))

def formula_paragraph(label, value, formula_str, inputs_str):
    return [
        Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]),
        Paragraph(f"<font size=9>{formula_str}</font>", formula_style),
        Paragraph(f"<font size=9><i>{inputs_str}</i></font>", formula_style),
        Spacer(1, 6),
    ]

story.append(Paragraph("Perfusion Summary", styles["Heading2"]))
story.extend(formula_paragraph("BSA", f"{bsa} m²", "BSA = √(Height × Weight / 3600)", f"= √({height} × {weight} / 3600)"))
story.extend(formula_paragraph("BMI", f"{bmi}", "BMI = Weight / (Height / 100)^2", f"= {weight} / ({height}/100)^2"))
story.extend(formula_paragraph("Blood Volume", f"{blood_vol} mL", "BV = Weight × 70", f"= {weight} × 70"))
story.extend(formula_paragraph("Post Hct", f"{post_hct}%", "= [(Hct × BV) + (0 × PV)] / (BV + PV)", f"= ({pre_hct}% × {blood_vol}) / ({blood_vol} + {prime_vol})"))
story.extend(formula_paragraph("RBC Units", f"{rbc_units}", "= (Target − Post) ÷ 3", f"= ({target_hct} − {post_hct}) ÷ 3"))
story.extend(formula_paragraph("Flow", f"{flow_suggested} L/min", "= CI × BSA", f"= {suggested_ci} × {bsa}"))
story.extend(formula_paragraph("DO2", f"{do2}", "= Flow × 10 × (1.34 × Hgb × 0.98 + 0.003 × 100)", f"= {flow_suggested} × 10 × (1.34 × {pre_hgb:.2f} × 0.98 + 0.3)"))
story.extend(formula_paragraph("DO2i", f"{do2i}", "= DO2 ÷ BSA", f"= {do2} ÷ {bsa}"))
story.extend(formula_paragraph("Heparin Dose", f"{heparin_dose} units", "= Weight × 400", f"= {weight} × 400"))

story.append(Paragraph(f"<b>MAP Target:</b> {map_target}", styles["Normal"]))

story.append(Spacer(1, 12))
timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime('%Y-%m-%d %I:%M %p')
story.append(Paragraph(f"Generated {timestamp}", ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=1)))

doc.build(story)
st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
