import streamlit as st

# --- Functions ---
def calculate_bsa(height_cm, weight_kg):
    return round(0.007184 * (height_cm ** 0.725) * (weight_kg ** 0.425), 2)

def calculate_blood_volume(weight_kg):
    return round(weight_kg * 70)  # Avg blood vol = 70 mL/kg

def calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol, prime_hct=0):
    total_vol = blood_vol + prime_vol
    return round(((pre_hct / 100) * blood_vol + (prime_hct / 100) * prime_vol) / total_vol * 100, 1)

def calculate_rbc_units_needed(current_hct, target_hct=25):
    delta = target_hct - current_hct
    return max(0, round(delta / 3, 1))  # Assume 1 unit raises ~3% Hct

def calculate_flow(ci, bsa):
    return round(ci * bsa, 2)

def calculate_do2(flow_L_min, hgb):
    return round(flow_L_min * 10 * (1.34 * hgb * 0.98 + 0.003 * 100), 1)  # mL/min

def get_map_target(comorbidities):
    if "CKD" in comorbidities or "Hypertension" in comorbidities:
        return "70–80 mmHg"
    elif "Aortic Disease" in comorbidities:
        return "80–90 mmHg"
    else:
        return "65–75 mmHg"

# --- Streamlit UI ---
st.title("🫀 Pre-CPB Planning Tool")
st.markdown("Built for perfusionists – enter patient data to instantly calculate flows, Hct, DO₂, and more.")

# --- Patient Info ---
st.header("Patient Data")
col1, col2 = st.columns(2)
with col1:
    height = st.number_input("Height (cm)", value=170)
with col2:
    weight = st.number_input("Weight (kg)", value=70)

pre_hct = st.number_input("Pre-op Hematocrit (%)", value=38.0)
prime_vol = st.number_input("Circuit Prime Volume (mL)", value=1400)

# --- Comorbidities ---
comorbidities = st.multiselect("Comorbidities", [
    "CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"
])

# --- Procedure Type ---
procedure = st.selectbox("Procedure Type", [
    "CABG x1", "CABG x2–3", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", 
    "Full Arch", "Dissection Repair", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"
])

# --- Cannulation & Cardioplegia ---
cannulation = st.selectbox("Cannulation Strategy", [
    "Central (Ao + RA)", "Femoral", "Axillary", "Bicaval", "Dual Stage", "VA ECMO", "None/Other"
])

cardioplegia = st.selectbox("Cardioplegia Method", [
    "Antegrade", "Retrograde", "Ostial", "Combination", "None"
])

# --- Calculations ---
bsa = calculate_bsa(height, weight)
blood_vol = calculate_blood_volume(weight)
post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
rbc_units = calculate_rbc_units_needed(post_hct)
flow_1_8 = calculate_flow(1.8, bsa)
flow_2_4 = calculate_flow(2.4, bsa)
flow_3_0 = calculate_flow(3.0, bsa)
do2 = calculate_do2(flow_2_4, pre_hct * 0.34)  # estimate Hgb from Hct
map_target = get_map_target(comorbidities)

# --- Results ---
st.header("📊 Calculated Outputs")
st.write(f"**BSA:** {bsa} m²")
st.write(f"**Estimated Blood Volume:** {blood_vol} mL")
st.write(f"**Post-Dilution Hematocrit:** {post_hct}%")
st.write(f"**Estimated RBC Units Needed to Reach 25% Hct:** {rbc_units}")
st.write("---")
st.write(f"**Flow Targets:**")
st.write(f"- CI 1.8 = {flow_1_8} L/min")
st.write(f"- CI 2.4 = {flow_2_4} L/min")
st.write(f"- CI 3.0 = {flow_3_0} L/min")
st.write("---")
st.write(f"**Estimated DO₂ @ CI 2.4:** {do2} mL/min")
st.write(f"**Suggested MAP Target:** {map_target}")
