import streamlit as st
from PIL import Image
import os

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
st.markdown("Built for perfusionists – enter patient data to instantly calculate flows, Hct, DO₂, and more.")

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
    if neuro_strategy == "ACP":
        delivery_site = st.selectbox("ACP Delivery Site", ["Right SVC", "Innominate Artery", "Axillary Artery"])

# --- Cardioplegia ---
st.subheader("Cardioplegia Selection")
cardioplegia_type = st.selectbox("Cardioplegia Type", [
    "Del Nido", "Buckberg", "Custodial (HTK)", "Blood Cardioplegia", "Custom"
])
delivery_routes = st.multiselect("Delivery Routes", ["Antegrade", "Retrograde", "Ostial"])
if cardioplegia_type == "Custom":
    custom_ratio = st.text_input("Enter Custom Ratio (e.g., 4:1)")
    custom_volume = st.number_input("Enter Custom Volume (mL)", value=1000)

# --- CABG Graft Planner ---
if procedure == "CABG":
    st.subheader("CABG Graft Planner")
    num_grafts = st.number_input("Number of Grafts", min_value=1, max_value=5, step=1)

    for i in range(int(num_grafts)):
        st.markdown(f"**Graft {i+1}**")
        origin = st.selectbox(f"Graft {i+1} Origin", ["LIMA", "RIMA", "SVG", "Radial"], key=f"origin_{i}")
        target = st.selectbox(f"Graft {i+1} Target", ["LAD", "LCx", "OM1", "OM2", "PDA", "RCA"], key=f"target_{i}")
        graft_type = st.selectbox(f"Graft Type", ["in situ", "free", "composite", "none"], key=f"type_{i}")

        filename = None
        if graft_type == "composite" and origin == "RIMA" and target == "LCx":
            filename = "composite_lima_rima_lcx.png"
        elif origin == "Radial" and target == "RCA":
            filename = "radial_rca.png"
        elif origin == "RIMA" and target == "LCx" and graft_type == "free":
            filename = "rima_lcx_free.png"
        elif origin == "RIMA" and target == "LCx" and graft_type == "in situ":
            filename = "rima_lcx_insitu.png"
        elif origin == "RIMA" and target == "RCA":
            filename = "rima_rca.png"
        elif origin == "SVG" and target == "LAD":
            filename = "graft_overview_before_after.png"

        if filename and os.path.exists(filename):
            image = Image.open(filename)
            st.image(image, caption=f"{origin} → {target} ({graft_type})", use_column_width=True)
        else:
            st.warning(f"No diagram found for {origin} → {target} ({graft_type})")

# --- Calculations ---
bsa = calculate_bsa(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
flow_1_8 = calculate_flow(1.8, bsa)
flow_2_4 = calculate_flow(2.4, bsa)
flow_3_0 = calculate_flow(3.0, bsa)
do2 = calculate_do2(flow_2_4, pre_hgb)
map_target = get_map_target(comorbidities)
heparin_dose = calculate_heparin_dose(weight)

# --- Results ---
st.header("📊 Calculated Outputs")
st.write(f"**BSA:** {bsa} m²")
st.write(f"**Estimated Blood Volume:** {blood_vol} mL")
st.write(f"**Post-Dilution Hematocrit:** {post_hct}%")
st.write(f"**Estimated RBC Units Needed to Reach {target_hct}% Hct:** {rbc_units}")
st.write("---")
st.write("**Flow Targets:**")
st.write(f"- CI 1.8 = {flow_1_8} L/min")
st.write(f"- CI 2.4 = {flow_2_4} L/min")
st.write(f"- CI 3.0 = {flow_3_0} L/min")
st.write("---")
st.write(f"**Estimated DO₂ @ CI 2.4:** {do2} mL/min")
st.write(f"**Suggested MAP Target:** {map_target}")
st.write(f"**Heparin Dose (400 units/kg):** {heparin_dose} units")
