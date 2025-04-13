import streamlit as st
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os
import io

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
st.title("🫀 Pre-CPB Planning Tool")

# --- Patient Info ---
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

# --- Procedure Type ---
procedure = st.selectbox("Procedure Type", [
    "CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", 
    "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B",
    "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"
])

# --- Arrest Strategy ---
if "Dissection Repair – Stanford Type A" in procedure or "Full Arch" in procedure:
    st.subheader("Circulatory Arrest Planning")
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])

# --- Cardioplegia ---
st.subheader("Cardioplegia Selection")
cardioplegia_type = st.selectbox("Cardioplegia Type", ["Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"])
delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

# --- Custom Plegia ---
if cardioplegia_type == "Custom":
    st.text_input("Custom Ratio (Blood:Crystalloid)", value="4:1")
    st.number_input("Custom Volume (mL)", value=1000)
    with st.expander("Additives"):
        st.number_input("K⁺ [mEq]", value=0)
        st.number_input("Mg²⁺ [mEq]", value=0)
        st.number_input("HCO₃⁻ [mEq]", value=0)

# --- CABG Graft Planner ---
selected_graft_images = []
if procedure == "CABG":
    st.subheader("CABG Graft Planner")
    num_grafts = st.number_input("Number of Grafts", min_value=1, max_value=5, step=1)
    image_dir = "images"

    for i in range(int(num_grafts)):
        target = st.selectbox(f"Graft {i+1} Target", ["LAD", "LCx", "OM1", "OM2", "PDA", "RCA"], key=f"target_{i}")
        if os.path.isdir(image_dir):
            matched = [img for img in os.listdir(image_dir) if target.lower() in img.lower()]
            selected = st.selectbox(f"Select Diagram for {target}", matched, key=f"select_{i}") if matched else None
            if selected:
                selected_graft_images.append(selected)
                st.image(os.path.join(image_dir, selected), width=200, caption=selected)
        uploaded_file = st.file_uploader(f"Or upload custom image for Graft {i+1}", type=["png", "jpg"], key=f"upload_{i}")
        if uploaded_file:
            st.image(uploaded_file, width=200, caption="Custom Upload")

# --- Phenylephrine ---
st.subheader("Phenylephrine Dilution")
neo_dose = st.number_input("Total Drug Dose (mg)", value=10.0)
neo_vol = st.number_input("Total Volume (mL)", value=100.0)
if neo_vol > 0:
    conc = round((neo_dose * 1000) / neo_vol, 1)
    st.write(f"**Concentration:** {conc} mcg/mL")

# --- Calculations ---
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
flow_1_8 = calculate_flow(1.8, bsa)
flow_2_4 = calculate_flow(2.4, bsa)
flow_3_0 = calculate_flow(3.0, bsa)
do2 = calculate_do2(flow_2_4, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# --- Output ---
st.header("📊 Calculated Outputs")
st.write(f"BMI: {bmi} | BSA: {bsa} m²")
st.write(f"Estimated Blood Volume: {blood_vol} mL")
st.write(f"Post-Dilution Hct: {post_hct}% | RBC Units Needed: {rbc_units}")
st.write(f"Flow @ CI 1.8: {flow_1_8} L/min")
st.write(f"Flow @ CI 2.4: {flow_2_4} L/min")
st.write(f"Flow @ CI 3.0: {flow_3_0} L/min")
st.write(f"DO₂: {do2} mL/min | DO₂i: {do2i} mL/min/m²")
st.write(f"MAP Target: {map_target}")
st.write(f"Heparin Dose: {heparin_dose} units")

# --- PDF Export ---
pdf_buffer = io.BytesIO()
pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
pdf.drawString(50, 750, "🫀 Pre-CPB Summary Report")
pdf.drawString(50, 735, f"BMI: {bmi} | BSA: {bsa} m² | DO₂i: {do2i} mL/min/m²")
pdf.drawString(50, 720, f"Hct: {post_hct}% | RBC Units: {rbc_units}")
pdf.drawString(50, 705, f"Flow CI 1.8: {flow_1_8}  2.4: {flow_2_4}  3.0: {flow_3_0}")
pdf.drawString(50, 690, f"MAP Target: {map_target} | Heparin: {heparin_dose} units")
pdf.drawString(50, 675, f"EF: {ef}% | Valve: {', '.join(valve_issues)}")
pdf.drawString(50, 660, f"Comorbidities: {', '.join(comorbidities)}")
pdf.drawString(50, 645, f"Cardioplegia: {cardioplegia_type} via {', '.join(delivery_routes)}")
pdf.drawString(50, 630, f"Prime: {base_prime} + {', '.join(prime_additives)}")
for i, img in enumerate(selected_graft_images):
    pdf.drawString(50, 615 - (i * 15), f"Graft {i+1} Diagram: {img}")
pdf.save()

st.download_button("📥 Download PDF", data=pdf_buffer.getvalue(), file_name="pre_cpb_summary.pdf", mime="application/pdf")
