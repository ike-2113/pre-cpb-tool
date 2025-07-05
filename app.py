# app.py — Complete Final Version with All Features

import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Perfusion Sentinel",
    page_icon=Image.open("pdf_logo.png"),
    layout="centered"
)

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

# ---- Password Gate ----
st.title("🔐 Secure Access")

PASSWORD = "Emory2025"
user_input = st.text_input("Enter password to access Perfusion Sentinel:", type="password")

if user_input != PASSWORD:
    st.warning("Incorrect password. Please try again.")
    st.stop()

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
# ---- Hospital & Surgeon Select ----
## Removed hospital and surgeon selection
# ---- STS Report Section ----
with st.expander("STS Report", expanded=True):
    sts_date = st.date_input("Date of Procedure")
    sts_procedure = st.selectbox("Procedure Type (STS)", [
        "CABG", "Mitral", "Aortic", "Mitral + CABG",
        "Aortic + CABG", "Mitral Repair vs Replace + CABG"
    ])

    cross_clamp_time = st.number_input("Cross Clamp Time (min)", min_value=0, value=0)
    bypass_time = st.number_input("Bypass Time (min)", min_value=0, value=0)

    plegia_type = st.selectbox("Cardioplegia Type", ["4:1", "Del Nido", "Microplegia"])
    plegia_volume = st.number_input("Crystalloid Plegia Volume (mL)", min_value=0, value=0)

    st.markdown("### Transfusion")
    transfusion_given = st.radio("Was transfusion given?", ["No", "Yes"])
    transfusion_volume = st.text_input("Transfusion Volume (mL)", value="") if transfusion_given == "Yes" else ""

    st.markdown("### Hemoconcentrator")
    hemo_used = st.radio("Used Hemoconcentrator?", ["No", "Yes"])
    hemo_volume = st.text_input("Volume Removed (mL)", value="") if hemo_used == "Yes" else ""

    st.markdown("### Use of IMA")
    ima_used = st.radio("IMA Used?", ["No", "Yes"])

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
    
    st.markdown("""<sub><i>
    Medical Disclaimer: The information provided in this application is strictly for educational purposes only and is not intended or implied to be a substitute for medical advice or instruction by a health professional. Information in this application may differ from the opinions of your institution. Consult with a recognized medical professional before making decisions based on the information in this application. The authors are not responsible for the use or interpretation you make of any information provided.
    </i></sub>""", unsafe_allow_html=True)

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
# ---- Allergies removed ----
blood_type = st.selectbox("Patient Blood Type", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
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
# ---- Surgeon Protocols ----
## Removed surgeon protocols and protocol_note
protocol_note = "No specific protocol provided."
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

def get_compatible_blood_products(blood_type):
    compatibility = {
        "A+": {"PRBC": ["A+", "A-", "O+", "O-"], "FFP": ["A+", "AB+", "A-", "AB-"]},
        "A-": {"PRBC": ["A-", "O-"], "FFP": ["A-", "AB-"]},
        "B+": {"PRBC": ["B+", "B-", "O+", "O-"], "FFP": ["B+", "AB+", "B-", "AB-"]},
        "B-": {"PRBC": ["B-", "O-"], "FFP": ["B-", "AB-"]},
        "AB+": {"PRBC": ["A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"], "FFP": ["AB+"]},
        "AB-": {"PRBC": ["A-", "B-", "O-", "AB-"], "FFP": ["AB-"]},
        "O+": {"PRBC": ["O+", "O-"], "FFP": ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]},
        "O-": {"PRBC": ["O-"], "FFP": ["O-", "A-", "B-", "AB-"]},
    }
    return {
        "Blood Type": blood_type,
        "PRBC": compatibility[blood_type]["PRBC"],
        "FFP": compatibility[blood_type]["FFP"],
        "Cryo": compatibility[blood_type]["FFP"],
        "Whole Blood": compatibility[blood_type]["PRBC"]
    }

blood_compatibility = get_compatible_blood_products(blood_type)

# ---- Outputs ----
st.subheader("Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Flow @ CI {suggested_ci}: {flow} L/min")
st.write(f"Post Dilutional Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"DO2: {do2} | DO2i: {do2i}")
st.write(f"MAP Target: {map_target} | Heparin Dose: {heparin_dose} units")
st.markdown("### Transfusion Compatibility")
st.write(f"**Blood Type:** {blood_type}")
for product, compatible in blood_compatibility.items():
    if product != "Blood Type":
        st.write(f"**{product} Compatible:** {', '.join(compatible)}")
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
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

def build_parameter_table(story, title, rows):
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))
    table = Table(rows, colWidths=[120, 250, 130], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 1), (1, -1), colors.red),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

def build_all_summary_tables(story):
    # Patient Data
    patient_rows = [["PARAMETER", "VALUE", "NOTES / FORMULA"]]
    if pdf_height: patient_rows.append(["Height", f"{height} cm", "–"])
    if pdf_weight: patient_rows.append(["Weight", f"{weight} kg", "–"])
    if pdf_bmi: patient_rows.append(["BMI", f"{bmi}", "Weight / (Height/100)^2"])
    if pdf_bsa: patient_rows.append(["BSA", f"{bsa} m²", "√(Height × Weight / 3600)"])
    if pdf_pre_hct: patient_rows.append(["Pre-op Hct", f"{pre_hct}%", "Baseline"])
    if pdf_pre_hgb: patient_rows.append(["Pre-op Hgb", f"{pre_hgb:.2f} g/dL", "–"])
    if pdf_target_hct: patient_rows.append(["Target Hct", f"{target_hct}%", "Target during CPB"])
    if pdf_ef: patient_rows.append(["Ejection Fraction", f"{ef}%", "LV function"])
    if pdf_comorbid: patient_rows.append(["Comorbidities", ", ".join(comorbidities), "–"])
    if valve_issues: patient_rows.append(["Valve Pathology", ", ".join(valve_issues), "–"])
    build_parameter_table(story, "BODY METRICS & VOLUMES", patient_rows)

    # Prime Data
    if pdf_prime_vol:
        prime_rows = [["PARAMETER", "VALUE", "NOTES / FORMULA"]]
        prime_rows.append(["Prime Volume", f"{prime_vol} mL", "CPB circuit prime"])
        prime_rows.append(["Prime Osmolality", f"{prime_osmo} mOsm/kg", "Normal estimate"])
        if base_prime: prime_rows.append(["Base Prime", base_prime, "–"])
        if pdf_prime_add and prime_additives:
            prime_rows.append(["Additives", ", ".join(prime_additives), "–"])
        build_parameter_table(story, "PRIME COMPOSITION", prime_rows)

    # Cardioplegia Table
    if pdf_cardio:
        cardio_rows = [["ITEM", "DETAIL", ""]]
        cardio_rows.append(["Cardioplegia", cardioplegia_type, ""])
        cardio_rows.append(["Delivery Routes", ", ".join(delivery_routes), ""])
        build_parameter_table(story, "CARDIOPLEGIA", cardio_rows)

    # Arrest Plan Table
    if pdf_arrest and arrest_temp:
        arrest_rows = [["ITEM", "DETAIL", ""]]
        arrest_rows.append(["Target Temperature", f"{arrest_temp}°C", ""])
        arrest_rows.append(["Arrest Duration", f"{arrest_duration} min", ""])
        arrest_rows.append(["Neuro Strategy", neuro_strategy, ""])
        build_parameter_table(story, "CIRCULATORY ARREST PLAN", arrest_rows)
formula_style = ParagraphStyle(name='Formula', fontSize=9)
story = []

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

# -- Define Your Table Rows --
perfusion_table = [
    ["PARAMETER", "VALUE", "NOTES / FORMULAS"],
    ["BSA", f"{bsa} m²", "√(Height × Weight / 3600)"],
    ["MAP Target", map_target, "Based on comorbidities"],
    ["Heparin Dose", f"{heparin_dose} units", "Weight × 400"],
    ["Flow @ CI 1.8", f"{calculate_flow(1.8, bsa)} L/min", "CI × BSA"],
    ["Flow @ CI 2.4", f"{calculate_flow(2.4, bsa)} L/min", "–"],
    ["Flow @ CI 3.0", f"{calculate_flow(3.0, bsa)} L/min", "–"],
    ["DO2/DO2i @ CI 1.8", f"{calculate_do2(calculate_flow(1.8, bsa), pre_hgb)} / {round(calculate_do2(calculate_flow(1.8, bsa), pre_hgb) / bsa, 1)}", "Flow × CaO2 / ÷ BSA"],
    ["DO2/DO2i @ CI 2.4", f"{do2} / {do2i}", "–"],
    ["DO2/DO2i @ CI 3.0", f"{calculate_do2(calculate_flow(3.0, bsa), pre_hgb)} / {round(calculate_do2(calculate_flow(3.0, bsa), pre_hgb) / bsa, 1)}", "–"],
    ["Post Dilutional Hct", f"{post_hct}%", "(Hct × BV) / (BV + PV)"],
    ["RBC Units", f"{rbc_units}", "(Target − Post) ÷ 3"],
]
build_parameter_table(story, "CRITICAL PERFUSION PARAMETERS – CASE SUMMARY", perfusion_table)

build_all_summary_tables(story)
# ---- Graft Images Section ----
if selected_graft_images:
    story.append(Spacer(1, 12))
    story.append(Paragraph("CABG Graft Images", styles["Heading2"]))
    story.append(Spacer(1, 6))
    for img_path in selected_graft_images:
        if os.path.exists(img_path):
            graft_img = RLImage(img_path, width=250, height=150)  # adjust size as needed
            story.append(graft_img)
            story.append(Spacer(1, 6))

# Add transfusion compatibility section
transfusion_rows = [["PRODUCT", "COMPATIBLE TYPES", ""]]
for product in ["PRBC", "FFP", "Cryo", "Whole Blood"]:
    transfusion_rows.append([product, ", ".join(blood_compatibility[product]), ""])
build_parameter_table(story, "TRANSFUSION COMPATIBILITY", transfusion_rows)
# ---- Surgeon Protocol PDF Section ----
# Removed hospital & surgeon protocol section from PDF

# ---- STS Report PDF Section ----
sts_rows = [["ITEM", "DETAIL", ""]]
from reportlab.lib.utils import simpleSplit
def wrap(text):
    return Paragraph(text, styles["Normal"])

sts_rows.append(["Date of Procedure", wrap(str(sts_date)), ""])
sts_rows.append(["STS Procedure", wrap(sts_procedure), ""])
sts_rows.append(["Cross Clamp Time", wrap(f"{cross_clamp_time} min"), ""])
sts_rows.append(["Bypass Time", wrap(f"{bypass_time} min"), ""])
sts_rows.append(["Plegia Type", wrap(plegia_type), ""])
sts_rows.append(["Crystalloid Plegia Volume", wrap(f"{plegia_volume} mL"), ""])
sts_rows.append(["Transfusion Given", wrap(transfusion_given), ""])
if transfusion_given == "Yes":
    sts_rows.append(["Transfusion Volume", wrap(f"{transfusion_volume} mL"), ""])
sts_rows.append(["Hemoconcentrator Used", wrap(hemo_used), ""])
if hemo_used == "Yes":
    sts_rows.append(["Hemoconcentrator Volume", wrap(f"{hemo_volume} mL"), ""])
sts_rows.append(["IMA Used", wrap(ima_used), ""])

build_parameter_table(story, "STS REPORT – PERFUSION SUMMARY", sts_rows)
from reportlab.lib.enums import TA_RIGHT

footer_style = ParagraphStyle(
    name='FooterRight',
    fontSize=8,
    textColor=colors.grey,
    alignment=TA_RIGHT,
    rightIndent=12
)

timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime('%Y-%m-%d %I:%M %p')
story.append(Spacer(1, 12))
story.append(Paragraph(f"Generated {timestamp}", footer_style))

# Add disclaimer
story.append(Spacer(1, 12))
disclaimer_text = (
    "Medical Disclaimer: The information provided in this application is strictly for educational purposes only and "
    "is not intended or implied to be a substitute for medical advice or instruction by a health professional. "
    "Information in this application may differ from the opinions of your institution. Consult with a recognized medical professional "
    "before making decisions based on the information in this application. The authors are not responsible for the use or interpretation "
    "you make of any information provided. Though we strive to make sure all of the information is current and reliable, we cannot guarantee "
    "accuracy, adequacy, completeness, legality, or usefulness of any information provided."
)
story.append(Paragraph(disclaimer_text, ParagraphStyle(name='Disclaimer', fontSize=6, textColor=colors.grey, alignment=1)))

# Finalize PDF
doc.build(story)

st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
