import streamlit as st
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os
import io

# --- Functions ---
def calculate_bsa(height_cm, weight_kg):
    return round(0.007184 * (height_cm ** 0.725) * (weight_kg ** 0.425), 2)

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

# --- Streamlit UI ---
st.title("🫀 Pre-CPB Planning Tool")

# --- Patient Info ---
st.header("Patient Data")
col1, col2 = st.columns(2)
with col1:
    height = st.number_input("Height (cm)", value=170)
    weight = st.number_input("Weight (kg)", value=70)
with col2:
    pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
    pre_hgb = st.number_input("Pre-op Hemoglobin (g/dL)", value=pre_hct * 0.34)

prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400)
base_prime = st.selectbox("Base Prime Fluid", ["None", "Plasmalyte A", "Normosol-R"])
prime_additives = st.multiselect("Prime Additives", ["Albumin", "Mannitol", "Heparin", "Bicarb", "Calcium", "Magnesium"])
target_hct = st.number_input("Target Hematocrit (%)", value=25.0)

# --- Comorbidities ---
comorbidities = st.multiselect("Comorbidities", [
    "CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"
])

# --- Procedure Type ---
procedure = st.selectbox("Procedure Type", [
    "CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", 
    "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B",
    "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"
])

# --- Circulatory Arrest ---
if "Dissection Repair – Stanford Type A" in procedure or "Full Arch" in procedure:
    st.subheader("Circulatory Arrest Planning")
    arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    arrest_duration = st.number_input("Expected Arrest Duration (min)", value=30)
    neuro_strategy = st.selectbox("Neuroprotection Strategy", ["None", "RCP", "ACP"])

# --- Cardioplegia ---
st.subheader("Cardioplegia Selection")
cardioplegia_type = st.selectbox("Cardioplegia Type", [
    "Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"
])
delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])

if cardioplegia_type == "Custom":
    st.text_input("Custom Ratio (Blood:Crystalloid)", value="4:1")
    st.number_input("Custom Volume (mL)", value=1000)
    with st.expander("Additives"):
        st.number_input("K⁺ [mEq]", value=0)
        st.number_input("Mg²⁺ [mEq]", value=0)
        st.number_input("HCO₃⁻ [mEq]", value=0)

# --- CABG Graft Planner ---
if procedure == "CABG":
    st.subheader("CABG Graft Planner")
    num_grafts = st.number_input("Number of Grafts", min_value=1, max_value=5, step=1)
    image_dir = "images"
    for i in range(int(num_grafts)):
        target = st.selectbox(f"Graft {i+1} Target", ["LAD", "LCx", "OM1", "OM2", "PDA", "RCA"], key=f"target_{i}")
        
        if os.path.isdir(image_dir):
            images = [img for img in os.listdir(image_dir) if target.lower() in img.lower()]
            if images:
                for img in images:
                    st.image(os.path.join(image_dir, img), width=200, caption=img)
            else:
                st.info("No matching diagrams found. Upload your own below.")
        else:
            st.warning("⚠️ Diagram folder not found. Upload a custom image below.")
        
        uploaded_file = st.file_uploader(
            f"Optional: Upload custom diagram for Graft {i+1}",
            type=["png", "jpg", "jpeg"],
            key=f"upload_{i}"
        )
        if uploaded_file:
            st.image(uploaded_file, width=200, caption="Custom Upload")

# --- Phenylephrine Calculator ---
st.subheader("Phenylephrine Dilution")
neo_dose = st.number_input("Total Drug Dose (mg)", value=10.0)
neo_vol = st.number_input("Total Volume (mL)", value=100.0)
if neo_vol > 0:
    neo_conc = round((neo_dose * 1000) / neo_vol, 1)
    st.write(f"**Concentration:** {neo_conc} mcg/mL")
    st.write("**Bolus Dose:** 40–100 mcg | **Infusion:** 0.2–1 mcg/kg/min")

# --- Calculations ---
bsa = calculate_bsa(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
flow = calculate_flow(2.4, bsa)
do2 = calculate_do2(flow, pre_hgb)
do2i = round(do2 / bsa, 1)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# --- Recommendation ---
if "Albumin" not in prime_additives and (pre_hct < 30 or weight < 60 or any(x in comorbidities for x in ["CKD", "Jehovah’s Witness", "Anemia"])):
    st.warning("💡 Consider Albumin in prime for volume support and oncotic pressure.")

# --- Results ---
st.header("📊 Calculated Outputs")
st.write(f"BSA: {bsa} m²")
st.write(f"Estimated Blood Volume: {blood_vol} mL")
st.write(f"Post-Dilution Hct: {post_hct}%")
st.write(f"RBC Units Needed: {rbc_units}")
st.write(f"DO₂: {do2} mL/min | DO₂i: {do2i} mL/min/m²")
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

# --- PDF Report Download ---
st.subheader("📥 Download Report")
pdf_buffer = io.BytesIO()
pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
pdf.drawString(50, 750, "Pre-CPB Summary Report")
pdf.drawString(50, 730, f"BSA: {bsa} m² | DO₂i: {do2i} mL/min/m²")
pdf.drawString(50, 710, f"Hct: {post_hct}% | RBC Units: {rbc_units}")
pdf.drawString(50, 690, f"MAP Target: {map_target}")
pdf.drawString(50, 670, f"Prime: {base_prime} + {', '.join(prime_additives)}")
pdf.save()
st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="pre_cpb_summary.pdf", mime="application/pdf")
