
# app.py — Complete Final Version with All Features

import streamlit as st
from PIL import Image
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

# ---- Password Gate ----

st.title("🔐 Secure Access")
PASSWORD = "Emory2025"
user_input = st.text_input("Enter password to access Perfusion Sentinel:", type="password")
if user_input != PASSWORD:
    st.warning("Incorrect password. Please try again.")
    st.stop()

# ---- Main Navigation ----
st.markdown("# Perfusion Sentinel")
st.markdown("Select a tool to begin:")
tool = st.selectbox(
    "Choose a tool:",
    ["-- Select --", "STS Report", "Pre-CPB Tool", "Drug Library"],
    index=0
)
if tool == "-- Select --":
    st.info("Please select a tool above.")
    st.stop()

# ---- STS Report Section ----
if tool == "STS Report":
    with st.expander("STS Report", expanded=True):
        # ...existing code for STS Report section (from previous with st.expander block)...
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
        # ---- Email STS Report (as before) ----
        st.markdown("---")
        st.markdown("### Email STS Report")
        sts_email = st.text_input("Enter email to send STS report to:")
        if sts_email:
            import smtplib
            from email.message import EmailMessage
            import os
            st.info(f"Sending STS report to {sts_email} using perfusionsentinel@gmail.com")
            try:
                # Build STS-only PDF
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                import io
                styles = getSampleStyleSheet()
                sts_pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(sts_pdf_buffer, pagesize=letter)
                story = []
                story.append(Paragraph("<b>Perfusion Sentinel STS Report</b>", styles['Title']))
                story.append(Spacer(1, 12))
                sts_rows = [["ITEM", "DETAIL", ""]]
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
                table = Table(sts_rows, colWidths=[120, 250, 130], hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (1, 1), (1, -1), colors.red),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(table)
                doc.build(story)
                # Email the STS-only PDF
                msg = EmailMessage()
                msg['Subject'] = 'Perfusion Sentinel STS Report'
                msg['From'] = 'perfusionsentinel@gmail.com'
                msg['To'] = sts_email
                msg.set_content('Attached is your STS report PDF.')
                msg.add_attachment(sts_pdf_buffer.getvalue(), maintype='application', subtype='pdf', filename='sts_report.pdf')
                gmail_user = 'perfusionsentinel@gmail.com'
                gmail_app_password = os.environ.get("gmail_app_password")
                if not gmail_app_password:
                    raise RuntimeError("Gmail app password not found in environment variable 'gmail_app_password'. Please set it in your Render dashboard.")
                with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                    smtp.starttls()
                    smtp.login(gmail_user, gmail_app_password)
                    smtp.send_message(msg)
                st.success('Email sent successfully!')
            except Exception as e:
                st.error(f'Error sending email: {e}')
    st.stop()


 # ---- Pre-CPB Tool Section ----


# ---- Pre-CPB Tool Section ----

# ---- Pre-CPB Tool Section ----
if tool == "Pre-CPB Tool":
    # Only show Pre-CPB Tool UI when selected
    # ---- Sidebar ----
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
        pdf_comorbid = st.checkbox("Comorbidities / Pathology", True)
        pdf_cardio = st.checkbox("Cardioplegia", True)
        pdf_cabg = st.checkbox("CABG Grafts", True)
        pdf_arrest = st.checkbox("Arrest Plan", True)
        st.markdown("""<sub><i>
        Medical Disclaimer: The information provided in this application is strictly for educational purposes only and is not intended or implied to be a substitute for medical advice or instruction by a health professional. Information in this application may differ from the opinions of your institution. Consult with a recognized medical professional before making decisions based on the information in this application. The authors are not responsible for the use or interpretation you make of any information provided.
        </i></sub>""", unsafe_allow_html=True)

    # ---- Main Pre-CPB Tool UI ----
    st.title("Bypass Blueprint")
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

    target_hct = st.number_input("Hematocrit Transfusion Threshold (%)", value=25.0)
    procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])
    comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
    valve_issues = st.multiselect("Valve Pathology", ["Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis", "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"])
    blood_type = st.selectbox("Patient Blood Type", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])

    if procedure in ["Dissection Repair – Stanford Type A", "Full Arch"] and pdf_arrest:
        arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)


# ---- Drug Library Section ----
if tool == "Drug Library":
    st.title("Drug Library")
    st.markdown("Search for a drug or select two to compare.")

    # Example drug data structure (replace/add with your real data)
    drug_data = {
        "Heparin": {
            "Class": "Anticoagulant",
            "Indication": "Prevention and treatment of thrombosis",
            "Dose": "300-400 units/kg IV",
            "Onset": "Immediate",
            "Half-life": "1-2 hours",
            "Notes": "Monitor ACT. Reversed with protamine."
        },
        "Protamine": {
            "Class": "Antidote (Heparin reversal)",
            "Indication": "Reversal of heparin anticoagulation",
            "Dose": "1 mg per 100 units heparin remaining",
            "Onset": "5 minutes",
            "Half-life": "7 minutes",
            "Notes": "Give slowly to avoid hypotension/anaphylaxis."
        },
        "Methylene Blue": {
            "Mechanism": "Inhibits nitric oxide (NO) and cyclic GMP activation; promotes methoglobin formation at higher doses.",
            "Indications": "Vasoplegic syndrome (post-CPB), methemoglobinemia.",
            "Effect": "Restores vascular tone (vasoconstriction); improves oxygen delivery by treating methemoglobinemia.",
            "Adverse": "Serotonin syndrome (if on SSRIs), blue urine, reflex hypertension.",
            "Avoid": "Patients on SSRIs (risk of serotonin syndrome).",
            "Adjuvants": "Vasopressors/fluids, supplemental oxygen.",
            "Use": "Intra- or Post-op.",
            "CPB/CNS": "Hemodilution and increased volume can reduce plasma concentration and potency."
        },
        "Statins": {
            "Mechanism": "Inhibit HMG-CoA reductase → reduced cholesterol synthesis.",
            "Indications": "Hyperlipidemia, cardiovascular risk reduction.",
            "Effect": "↓ LDL (30–60%), ↓ triglycerides (30–50%), ↑ HDL (5–15%).",
            "Adverse": "Myopathy, hepatic dysfunction.",
            "Avoid": "Liver dysfunction.",
            "Adjuvants": "Omega-3 (↓ triglycerides), Niacin (↑ HDL).",
            "Use": "Pre-op.",
            "Potency": "High intensity (↓ LDL >50%) vs moderate intensity (↓ LDL 30–49%)."
        },
        "Fibrates": {
            "Mechanism": "Upregulate apolipoprotein activity → ↓ triglyceride production, ↑ HDL.",
            "Indications": "Hypertriglyceridemia.",
            "Effect": "↓ triglycerides, ↑ HDL.",
            "Adverse": "Hepatic dysfunction.",
            "Avoid": "Liver dysfunction, severe renal impairment.",
            "Adjuvants": "Caution when combined with statins or bile acid sequestrants.",
            "Use": "Pre-op."
        },
        "Bile Acid Sequestrants": {
            "Mechanism": "Bind bile acids in gut → increased excretion → ↑ LDL receptor activity.",
            "Indications": "Hypercholesterolemia.",
            "Effect": "↓ LDL.",
            "Adverse": "Constipation, bloating, GI discomfort.",
            "Avoid": "GI disorders.",
            "Adjuvants": "Complementary with statins (↓ LDL synthesis).",
            "Use": "Pre-op.",
            "Potency": "↓ LDL by 15–30%."
        },
        "Niacin": {
            "Mechanism of Action": "Inhibits triglyceride production, enhances lipoprotein lipase activity → ↑ HDL, ↓ triglycerides.",
            "Indications for Use": "Hyperlipidemia, low HDL.",
            "Effect on Patient": "↓ triglycerides, ↑↑↑ HDL.",
            "Adverse Reactions": "Flushing (can be reduced with aspirin pre-treatment), hyperglycemia.",
            "Situations to Avoid": "Liver dysfunction, caution with diabetes.",
            "Adjuvants": "Often combined with statins for broader lipid control.",
            "Use": "Pre-op."
        },
        "Diazepam (Valium)": {
            "Mechanism of Action": "Enhances GABA-A receptor activity → ↑ CNS inhibition.",
            "Indications for Use": "Preoperative sedation, anxiety, seizures.",
            "Effect on Patient": "Sedation, anxiolysis, amnesia.",
            "Adverse Reactions": "Respiratory depression, propylene glycol toxicity.",
            "Situations to Avoid": "Respiratory insufficiency, liver dysfunction, elderly.",
            "Use": "Pre-op.",
            "CPB/CNS Considerations": "Hemodilution may ↓ total plasma concentration but ↑ free drug levels."
        },
        "Lorazepam (Ativan)": {
            "Mechanism of Action": "Same as Diazepam (GABA-A agonist).",
            "Indications for Use": "Anxiety, seizures.",
            "Effect on Patient": "Sedation, anxiolysis, amnesia.",
            "Adverse Reactions": "Respiratory depression, propylene glycol toxicity.",
            "Situations to Avoid": "Respiratory insufficiency, pregnancy, hypotension, elderly.",
            "Use": "Pre-op.",
            "CPB/CNS Considerations": "Same as Diazepam."
        },
        "Midazolam (Versed)": {
            "Mechanism of Action": "Same as Diazepam (GABA-A agonist).",
            "Indications for Use": "Preoperative sedation.",
            "Effect on Patient": "Sedation, anxiolysis, amnesia.",
            "Adverse Reactions": "Respiratory depression, delirium.",
            "Situations to Avoid": "Respiratory insufficiency, liver dysfunction, elderly.",
            "Use": "Pre-op.",
            "CPB/CNS Considerations": "Same as Diazepam."
        },
        "Atropine": {
            "Mechanism of Action": "Muscarinic receptor antagonist → inhibits parasympathetic activity.",
            "Indications for Use": "Bradycardia, AV-node block (prevents reflex bradycardia).",
            "Effect on Patient": "↑ heart rate (chronotropy), ↑ conduction (dromotropy), reduced secretions.",
            "Adverse Reactions": "Tachycardia, delirium, flushing.",
            "Situations to Avoid": "Tachycardia, arrhythmias, heart failure, elderly (delirium risk).",
            "Adjuvants": "Often paired with opioids as premedication.",
            "Use": "Pre-op."
        },
        "Glycopyrrolate (Robinul)": {
            "Mechanism of Action": "Muscarinic receptor antagonist → inhibits acetylcholine at parasympathetic sites.",
            "Indications for Use": "Reduce secretions, treat bradycardia (slower onset than atropine).",
            "Effect on Patient": "↓ secretions, ↑ heart rate.",
            "Adverse Reactions": "Mild tachycardia, constipation.",
            "Situations to Avoid": "Tachycardia, arrhythmias, heart failure.",
            "Adjuvants": "Often paired with opioids as premedication.",
            "Use": "Pre-op."
        },
        "Adenosine": {
            "Mechanism of Action": "A1 receptor → ↓ chronotropy & dromotropy; A2a → vasodilation.",
            "Indications for Use": "Paroxysmal supraventricular tachycardia (PSVT).",
            "Effect on Patient": "Restores normal rhythm.",
            "Adverse Reactions": "Flushing, dyspnea, chest pain, bradycardia, transient AV block.",
            "Situations to Avoid": "Bradycardia, hypotension, shock.",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↓ plasma concentration."
        },
        "Magnesium": {
            "Mechanism of Action": "Stabilizes cell membranes, essential cofactor for Na⁺/K⁺ ATPase, calcium antagonist.",
            "Indications for Use": "Torsades de Pointes, ventricular tachycardia.",
            "Effect on Patient": "Corrects arrhythmias.",
            "Adverse Reactions": "Hypotension, flushing, asystole.",
            "Situations to Avoid": "Renal dysfunction, hypotension.",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↓ plasma concentration."
        },
        "Propofol": {
            "Mechanism of Action": "GABA receptor agonist → ↑ Cl⁻ influx → hyperpolarization of neurons.",
            "Indications for Use": "Induction & maintenance of anesthesia.",
            "Effect on Patient": "Sedation/hypnosis, anxiolysis, amnesia, hypotension, respiratory depression.",
            "Adverse Reactions": "Hypoventilation/apnea, hypotension, hypertriglyceridemia.",
            "Situations to Avoid": "Hypertriglyceridemia, hemodynamic instability, egg/soy allergy.",
            "Adjuvants": "Opioids (analgesia), ketamine (analgesic adjunct).",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↑ unbound drug due to hemodilution → ↑ effect."
        },
        "Dexmedetomidine (Precedex)": {
            "Mechanism of Action": "Selective alpha-2 adrenergic agonist → ↓ norepinephrine release.",
            "Indications for Use": "Sedation of intubated patients.",
            "Effect on Patient": "Sedation, mild analgesia, anxiolysis, hypotension, reflex bradycardia.",
            "Adverse Reactions": "Hypotension, transient hypertension, reflex bradycardia.",
            "Situations to Avoid": "Diabetes, bradycardia, hypotension, shock.",
            "Adjuvants": "Opioids (added analgesia), ketamine (counteract hypotension).",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↑ free drug levels (highly protein-bound) → ↑ anesthetic effect."
        },
        "Etomidate": {
            "Mechanism of Action": "Enhances GABAergic activity → CNS depression.",
            "Indications for Use": "Induction of anesthesia (potent hypnotic, minimal CV effects).",
            "Effect on Patient": "Sedation, hypnosis, amnesia.",
            "Adverse Reactions": "Post-op nausea/vomiting, myoclonus, pain at injection site, adrenal suppression.",
            "Situations to Avoid": "Adrenal dysfunction — consider ketamine or propofol instead.",
            "Adjuvants": "Opioids (analgesia), benzodiazepines (anxiolysis).",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↑ free drug (moderately protein-bound) → ↑ anesthetic effect."
        },
        "Ketamine": {
            "Mechanism of Action": "NMDA receptor antagonist → dissociation, ↑ sympathetic activity.",
            "Indications for Use": "Induction & maintenance of anesthesia, reactive airway disease.",
            "Effect on Patient": "Dissociation, ↑ HR, ↑ BP, ↑ CO, analgesia, psychotomimetic effects.",
            "Adverse Reactions": "Hypertension, hallucinations, emergence delirium.",
            "Situations to Avoid": "Ischemic heart disease — consider etomidate or propofol instead.",
            "Adjuvants": "Opioids (synergistic effect), benzodiazepines (reduce hallucinations).",
            "Use": "Intra-op.",
            "CPB/CNS Considerations": "↑ free drug → ↑ effect."
        },
        "Alfentanil": {
            "Mechanism of Action": "μ-opioid receptor agonist → inhibits pain pathways.",
            "Indications for Use": "Short, intense surgical procedures.",
            "Effect on Patient": "Rapid-onset analgesia, sedation.",
            "Adverse Reactions": "Respiratory depression, sedation, hypotension, bradycardia.",
            "Situations to Avoid": "Respiratory insufficiency, hemodynamic instability, hypotension.",
            "Adjuvants": "Benzodiazepines, induction agents, anticholinergics.",
            "Use": "Intra-op.",
            "Potency": "~0.1–0.5 (relative scale).",
            "CPB/CNS Considerations": "↓ plasma concentration, lipophilic → sequestration."
        },
        "Fentanyl": {
            "Mechanism of Action": "μ-opioid receptor agonist → potent analgesia.",
            "Indications for Use": "Severe pain, anesthesia adjunct.",
            "Effect on Patient": "Analgesia, sedation.",
            "Adverse Reactions": "Respiratory depression, sedation, hypotension, bradycardia.",
            "Situations to Avoid": "Same as above.",
            "Adjuvants": "Same as above.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↓ plasma concentration, highly lipophilic → sequestration."
        },
        "Remifentanil": {
            "Mechanism of Action": "μ-opioid receptor agonist → ultra-short-acting analgesia.",
            "Indications for Use": "Precisely controlled surgical pain relief.",
            "Effect on Patient": "Precise, short-acting analgesia.",
            "Adverse Reactions": "Respiratory depression, sedation, hypotension, bradycardia.",
            "Situations to Avoid": "Non-functional blood/tissue esterases (metabolism is extrahepatic).",
            "Adjuvants": "Same as above.",
            "Use": "Intra-op.",
            "Potency": "Very high.",
            "CPB/CNS Considerations": "No sequestration (rapid metabolism)."
        },
        "Sufentanil": {
            "Mechanism of Action": "μ-opioid receptor agonist → inhibits pain pathways.",
            "Indications for Use": "Surgical pain management.",
            "Effect on Patient": "Profound analgesia, sedation.",
            "Adverse Reactions": "Respiratory depression, sedation, hypotension, bradycardia.",
            "Situations to Avoid": "Respiratory insufficiency, hemodynamic instability, hypotension.",
            "Adjuvants": "Benzodiazepines, induction agents, anticholinergics.",
            "Use": "Intra-op.",
            "Potency": "Very high (~10× fentanyl).",
            "CPB/CNS Considerations": "↓ plasma concentration, highly lipophilic → sequestration."
        },
        "Benzocaine (Ester)": {
            "Mechanism of Action": "Blocks sodium channels (inactive/open state).",
            "Indications for Use": "Temporary pain relief, mucosal numbing.",
            "Effect on Patient": "Localized numbness.",
            "Adverse Reactions": "Methemoglobinemia.",
            "Use": "Topical."
        },
        "Bupivacaine (Amide)": {
            "Mechanism of Action": "Blocks sodium channels (inactive/open state).",
            "Indications for Use": "Regional anesthesia, epidurals, peripheral nerve blocks.",
            "Effect on Patient": "Long-lasting numbness, pain relief.",
            "Adverse Reactions": "Cardiotoxicity (especially if injected intravascularly).",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None specific."
        },
        "Ropivacaine (Amide, S-isomer of Bupivacaine)": {
            "Mechanism of Action": "Blocks sodium channels (inactive/open state).",
            "Indications for Use": "Nerve blocks, regional anesthesia.",
            "Effect on Patient": "Numbness, pain relief.",
            "Adverse Reactions": "Less cardiotoxic than bupivacaine.",
            "Use": "Intra-op.",
            "Potency": "Moderate."
        },
        "Lidocaine (Amide)": {
            "Mechanism of Action": "Blocks sodium channels (inactive/open state).",
            "Indications for Use": "Local or regional anesthesia, also class 1b antiarrhythmic.",
            "Effect on Patient": "Numbness, pain relief, arrhythmia suppression.",
            "Adverse Reactions": "Systemic toxicity (if overdosed).",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Antiarrhythmic effect."
        },
        "Acetaminophen (paracetamol)": {
            "Mechanism of Action": "Weak COX inhibitor, may activate serotonergic pathways.",
            "Indications for Use": "Fever, mild pain.",
            "Effect on Patient": "Reduced pain, mild antipyretic, minimal GI impact.",
            "Adverse Reactions": "Hepatotoxicity (especially >4g/day or with liver disease).",
            "Situations to Avoid": "Hepatic dysfunction.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Ketorolac (NSAID)": {
            "Mechanism of Action": "COX-1 & COX-2 inhibition → ↓ prostaglandin synthesis.",
            "Indications for Use": "Moderate-to-severe pain, anti-inflammatory.",
            "Effect on Patient": "Pain relief, reduced inflammation.",
            "Adverse Reactions": "GI bleeding, renal injury, increased CV risk.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Ibuprofen (NSAID)": {
            "Mechanism of Action": "Same as Ketorolac — COX inhibition.",
            "Indications for Use": "Mild-to-moderate pain, inflammation.",
            "Effect on Patient": "Pain relief, reduced inflammation.",
            "Adverse Reactions": "GI bleeding, renal injury, increased CV risk.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Ketamine (at sub-anesthetic doses)": {
            "Mechanism of Action": "NMDA receptor antagonist.",
            "Indications for Use": "Adjunct pain management.",
            "Effect on Patient": "Analgesia, sedation, dissociation.",
            "Adverse Reactions": "Hallucinations, hypertension, emergence delirium.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Pregabalin (Gabapentinoid)": {
            "Mechanism of Action": "Binds to α2δ subunit of voltage-gated calcium channels → ↓ neurotransmitter release.",
            "Indications for Use": "Neuropathic pain.",
            "Effect on Patient": "Pain relief, anxiolysis (mild).",
            "Adverse Reactions": "Dizziness, sedation.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Gabapentin (Gabapentinoid)": {
            "Mechanism of Action": "Binds α2δ subunit of voltage-gated calcium channels → ↓ neurotransmitter release.",
            "Indications for Use": "Neuropathic pain.",
            "Effect on Patient": "Pain relief.",
            "Adverse Reactions": "Dizziness, sedation.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Dexamethasone (Decadron)": {
            "Mechanism of Action": "Glucocorticoid — anti-inflammatory, immunosuppressive.",
            "Indications for Use": "Anti-inflammatory, reduces opioid use, antiemetic.",
            "Effect on Patient": "↓ pain, ↓ inflammation, ↓ nausea.",
            "Adverse Reactions": "Hyperglycemia, insomnia, anxiety, psychosis, impaired wound healing.",
            "Use": "Post-op.",
            "Potency": "Moderate."
        },
        "Magnesium (as an adjunct)": {
            "Mechanism of Action": "Calcium channel blocker, NMDA antagonist.",
            "Indications for Use": "Torsades de Pointes, ventricular tachycardia, adjunct for analgesia.",
            "Effect on Patient": "Corrects arrhythmias, ↓ pain, ↓ anesthetic requirement.",
            "Adverse Reactions": "Hypotension, bradycardia.",
            "Use": "Intra-op.",
            "Potency": "Moderate."
        },
        "Mitomycin C (MMC)": {
            "Mechanism of Action": "Alkylating antitumor antibiotic → inhibits DNA synthesis.",
            "Indications for Use": "Peritoneal carcinomatosis, cancer.",
            "Effect on Patient": "Cytotoxic — kills tumor cells, slows progression.",
            "Adverse Reactions": "Bone marrow suppression, mucositis, pulmonary fibrosis.",
            "Use": "Intra-op."
        },
        "Oxaliplatin": {
            "Mechanism of Action": "Platinum alkylating agent → DNA crosslinking → cell death.",
            "Indications for Use": "Cancer (peritoneal carcinomatosis).",
            "Effect on Patient": "Cytotoxic — kills tumor cells, slows progression.",
            "Adverse Reactions": "Peripheral neuropathy, bone marrow suppression, cold sensitivity.",
            "Use": "Intra-op."
        },
        "General Antiemetic": {
            "Mechanism of Action": "Broad — various anti-nausea pathways.",
            "Indications for Use": "Prevent or treat nausea/vomiting.",
            "Effect on Patient": "Antiemetic effect.",
            "Adverse Reactions": "Minimal (depends on drug).",
            "Use": "Pre-op, intra-op, or post-op.",
            "CPB/CNS Considerations": "Hemodilution on CPB may require redosing."
        },
        "Granisetron (Sustol)": {
            "Mechanism of Action": "5-HT₃ receptor antagonist (central & peripheral).",
            "Indications for Use": "Postoperative nausea and vomiting (PONV).",
            "Effect on Patient": "Reduces nausea and vomiting.",
            "Adverse Reactions": "Headache, constipation, QT prolongation.",
            "Situations to Avoid": "Patients at risk of QT prolongation.",
            "Adjuvants": "Often combined with dexamethasone or NK-1 antagonists.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Minimal, may need redosing."
        },
        "Palonosetron (Aloxi)": {
            "Mechanism of Action": "Long-acting 5-HT₃ receptor antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Long-lasting antiemetic effect.",
            "Adverse Reactions": "Headache, constipation, QT prolongation.",
            "Situations to Avoid": "Patients at risk of QT prolongation.",
            "Adjuvants": "Often combined with dexamethasone or NK-1 antagonists.",
            "Use": "Pre-op.",
            "Potency": "High, longer half-life.",
            "CPB/CNS Considerations": "Minimal, less redosing required."
        },
        "Aprepitant": {
            "Mechanism of Action": "NK-1 receptor antagonist → blocks substance P.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Reduces nausea and vomiting.",
            "Adverse Reactions": "Fatigue, hiccups, constipation.",
            "Situations to Avoid": "Patients on CYP3A4 substrates or inducers, pregnancy.",
            "Adjuvants": "Often combined with 5-HT₃ antagonists + dexamethasone.",
            "Use": "Pre-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Minimal effect."
        },
        # --- Class I Antiarrhythmics ---
        "Quinidine (Class IA)": {
            "Mechanism of Action": "Blocks fast Na⁺ & K⁺ channels → slows conduction & prolongs action potential (AP).",
            "Indications for Use": "Atrial fibrillation/flutter, ventricular arrhythmias.",
            "Effect on Patient": "Slows rhythm, ↑ AP duration.",
            "Adverse Reactions": "QT prolongation, torsades de pointes, diarrhea.",
            "Situations to Avoid": "Prolonged QT, CHF, AV block.",
            "Adjuvants": "Combine with AV nodal blockers to prevent 1:1 conduction.",
            "Use": "Post-op (rare).",
            "CPB/CNS Considerations": "May require redosing."
        },
        "Procainamide (Class IA)": {
            "Mechanism of Action": "Na⁺ channel blocker → prolongs refractory period & slows conduction.",
            "Indications for Use": "Ventricular tachycardia (VT), supraventricular tachycardia (SVT).",
            "Effect on Patient": "Slows conduction, converts or suppresses arrhythmias.",
            "Adverse Reactions": "Hypotension, torsades, lupus-like syndrome.",
            "Situations to Avoid": "CHF, QT prolongation, lupus.",
            "Adjuvants": "Monitor with continuous ECG.",
            "Use": "Intra- or post-op VT.",
            "CPB/CNS Considerations": "Prolonged due to slowed clearance."
        },
        "Disopyramide (Class IA, strong anticholinergic)": {
            "Mechanism of Action": "Na⁺ & K⁺ channel blocker → prolongs conduction.",
            "Indications for Use": "Ventricular arrhythmias, hypertrophic cardiomyopathy (HCM).",
            "Effect on Patient": "Slows conduction.",
            "Adverse Reactions": "Anticholinergic effects, QT prolongation.",
            "Situations to Avoid": "HF, glaucoma, urinary retention.",
            "Use": "Outpatient HCM (not intra-op).",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        # --- Class IB Antiarrhythmics ---
        "Lidocaine (Class IB)": {
            "Mechanism of Action": "Blocks inactivated Na⁺ channels → shortens AP.",
            "Indications for Use": "Ventricular arrhythmias, VF/VT.",
            "Effect on Patient": "Stabilizes ventricular myocardium.",
            "Adverse Reactions": "CNS toxicity, bradycardia.",
            "Situations to Avoid": "Liver failure, SA/AV block.",
            "Adjuvants": "IV push + drip.",
            "Use": "Intra- or post-op VT/VF.",
            "CPB/CNS Considerations": "↑ distribution → may need bolus."
        },
        "Mexiletine (Class IB)": {
            "Mechanism of Action": "Similar to lidocaine — blocks inactivated Na⁺ channels → shortens AP.",
            "Indications for Use": "Chronic ventricular arrhythmias.",
            "Effect on Patient": "Prevents VT recurrence.",
            "Adverse Reactions": "Tremor, nausea, dizziness.",
            "Situations to Avoid": "Liver dysfunction.",
            "Adjuvants": "Often combined with other antiarrhythmics.",
            "Use": "Outpatient.",
            "CPB/CNS Considerations": "Not specified."
        },
        # --- Class IC Antiarrhythmics ---
        "Flecainide (Class IC)": {
            "Mechanism of Action": "Strong Na⁺ channel blocker.",
            "Indications for Use": "Atrial fibrillation, SVT.",
            "Effect on Patient": "Slows/terminates atrial arrhythmias.",
            "Adverse Reactions": "Blurred vision, dizziness.",
            "Situations to Avoid": "Structural heart disease, MI, CHF.",
            "Adjuvants": "Often combined with beta blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Propafenone (Class IC)": {
            "Mechanism of Action": "Strong Na⁺ channel blocker + mild beta blockade.",
            "Indications for Use": "Atrial arrhythmias.",
            "Effect on Patient": "Rhythm control.",
            "Adverse Reactions": "Metallic taste, bronchospasm, bradycardia.",
            "Situations to Avoid": "Asthma, HF, bradycardia.",
            "Adjuvants": "Often combined with AV nodal blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        # --- Class II Antiarrhythmics (Beta Blockers) ---
        "Metoprolol (Class II)": {
            "Mechanism of Action": "Beta-1 blocker → ↓ HR, ↓ contractility.",
            "Indications for Use": "Afib/flutter, SVT, HTN, post-MI, rate control.",
            "Effect on Patient": "Slows HR, ↓ myocardial O₂ demand.",
            "Adverse Reactions": "Bradycardia, hypotension, fatigue.",
            "Situations to Avoid": "Bradycardia, heart block, decompensated HF.",
            "Adjuvants": "Often combined with amiodarone or digoxin.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "May be held pre-bypass due to bradycardia risk."
        },
        "Esmolol (Class II)": {
            "Mechanism of Action": "Short-acting beta-1 blocker.",
            "Indications for Use": "Acute rate control (Afib, SVT), HTN.",
            "Effect on Patient": "Rapid HR control, fast onset/offset.",
            "Adverse Reactions": "Hypotension, bradycardia, heart block.",
            "Situations to Avoid": "Heart block, asthma, bradycardia.",
            "Adjuvants": "Used with anesthetics for controlled hypotension.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Short half-life → redosing required."
        },
        # --- Class III Antiarrhythmics ---
        "Amiodarone (Class III)": {
            "Mechanism of Action": "Blocks K⁺, Na⁺, Ca²⁺ channels & beta receptors.",
            "Indications for Use": "VT/VF, Afib, SVT.",
            "Effect on Patient": "Slows HR, stabilizes rhythm, suppresses arrhythmias.",
            "Adverse Reactions": "Bradycardia, hypotension, pulmonary fibrosis, thyroid toxicity.",
            "Situations to Avoid": "Bradycardia, iodine allergy.",
            "Adjuvants": "Often used with beta blockers or anticoagulants.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "CPB may ↑ distribution → adjust dose."
        },
        # --- Class III + Beta-Blocker ---
        "Sotalol (Class III + Beta-Blocker)": {
            "Mechanism of Action": "Blocks K⁺ channels & beta receptors → prolongs repolarization.",
            "Indications for Use": "Afib, VT.",
            "Effect on Patient": "Slows rate, prolongs QT.",
            "Adverse Reactions": "Torsades, bradycardia, hypotension.",
            "Situations to Avoid": "QT prolongation, renal failure.",
            "Adjuvants": "Monitor QT & renal function.",
            "Use": "Outpatient/ICU.",
            "Potency": "Moderate to high.",
            "CPB/CNS Considerations": "QT prolongation risk post-CPB."
        },
        # --- Class III ---
        "Dronedarone (Class III)": {
            "Mechanism of Action": "Blocks K⁺, Na⁺, Ca²⁺, mild anti-adrenergic.",
            "Indications for Use": "Non-permanent Afib.",
            "Effect on Patient": "Maintains NSR.",
            "Adverse Reactions": "Liver toxicity, HF exacerbation, GI upset.",
            "Situations to Avoid": "HF, permanent AF.",
            "Adjuvants": "Avoid strong CYP3A inhibitors.",
            "Use": "Outpatient.",
            "Potency": "Lower than amiodarone."
        },
        # --- Class IV Antiarrhythmics (Non-DHP CCBs) ---
        "Verapamil (Class IV)": {
            "Mechanism of Action": "L-type Ca²⁺ blocker → slows SA/AV conduction.",
            "Indications for Use": "SVT, Afib, rate control, angina.",
            "Effect on Patient": "↓ HR & contractility, vasodilation.",
            "Adverse Reactions": "Hypotension, bradycardia, constipation.",
            "Situations to Avoid": "HF, AV block, hypotension.",
            "Adjuvants": "Avoid with beta-blockers.",
            "Use": "Rarely intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hypotension risk post-CPB."
        },
        "Diltiazem (Class IV)": {
            "Mechanism of Action": "Inhibits Ca²⁺ in heart & vessels → ↓ HR & SVR.",
            "Indications for Use": "Afib/flutter rate control, angina, HTN.",
            "Effect on Patient": "Slows AV node, ↓ O₂ demand.",
            "Adverse Reactions": "Bradycardia, hypotension, edema.",
            "Situations to Avoid": "CHF, AV block, hypotension.",
            "Adjuvants": "Use with anticoagulation in AF.",
            "Use": "Pre- & post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Additive hypotension risk post-CPB."
        },
        # --- Other Antiarrhythmic ---
        "Adenosine (Antiarrhythmic)": {
            "Mechanism of Action": "Activates A1 receptor → transient AV node block.",
            "Indications for Use": "SVT termination.",
            "Effect on Patient": "Brief asystole → resets reentrant tachycardia.",
            "Adverse Reactions": "Flushing, chest pain, dyspnea.",
            "Situations to Avoid": "Asthma, 2°/3° AV block.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not specified."
        },
        # --- Rate Control / Inotrope ---
        "Digoxin": {
            "Mechanism of Action": "Inhibits Na⁺/K⁺ ATPase → ↑ intracellular Ca²⁺.",
            "Indications for Use": "Rate control in AF, systolic HF.",
            "Effect on Patient": "Slows AV conduction, ↑ contractility.",
            "Adverse Reactions": "Toxicity, GI upset.",
            "Situations to Avoid": "Renal failure, hypokalemia.",
            "Adjuvants": "Monitor electrolytes.",
            "Use": "Post-op AF management.",
            "CPB/CNS Considerations": "↓ clearance post-CPB → ↑ toxicity risk."
        },
        # --- Electrolyte / Antiarrhythmic ---
        "Magnesium Sulfate": {
            "Mechanism of Action": "Stabilizes myocardium, prolongs refractory period.",
            "Indications for Use": "Torsades, hypomagnesemia.",
            "Effect on Patient": "Suppresses ventricular irritability.",
            "Adverse Reactions": "Hypotension, flushing, bradycardia.",
            "Situations to Avoid": "Hypermagnesemia, MG, heart block.",
            "Use": "All phases.",
            "CPB/CNS Considerations": "Can be added to prime or intra-op."
        },
        # --- Antifibrinolytics ---
        "Tranexamic Acid (TXA)": {
            "Mechanism of Action": "Lysine analogue — inhibits plasminogen activation → ↓ fibrinolysis.",
            "Indications for Use": "Reduce bleeding during & after CPB.",
            "Effect on Patient": "↓ bleeding, ↓ transfusion requirements.",
            "Adverse Reactions": "Rare seizures (high dose), thrombosis.",
            "Situations to Avoid": "Active thrombosis, history of seizures.",
            "Adjuvants": "Used with standard coagulation management.",
            "Use": "Pre-, intra-, and post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Often added to prime; may accumulate if renal dysfunction."
        },
        "Epsilon-Aminocaproic Acid (EACA)": {
            "Mechanism of Action": "Similar to TXA — inhibits fibrinolysis.",
            "Indications for Use": "Reduce bleeding.",
            "Effect on Patient": "↓ bleeding, ↓ transfusion.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Situations to Avoid": "Active thrombosis.",
            "Use": "Pre-, intra-, and post-op."
        },
        # --- Prostacyclin ---
        "Prostacyclin (Epoprostenol)": {
            "Mechanism of Action": "PGI₂ analogue — vasodilates & inhibits platelet aggregation.",
            "Indications for Use": "ECMO or CPB circuits to prevent thrombosis.",
            "Effect on Patient": "↑ circuit patency, ↓ platelet aggregation.",
            "Adverse Reactions": "Hypotension, flushing.",
            "Situations to Avoid": "Hypotension.",
            "Use": "Intra-op (circuit)."
        },
        # --- Vasodilators ---
        "Nitroglycerin": {
            "Mechanism of Action": "NO donor → venodilation & mild arterial dilation.",
            "Indications for Use": "Hypertension, myocardial ischemia during/after CPB.",
            "Effect on Patient": "↓ preload, mild ↓ afterload, ↑ coronary flow.",
            "Adverse Reactions": "Hypotension, headache.",
            "Situations to Avoid": "Severe hypotension.",
            "Use": "Intra- & post-op."
        },
        "Nitroprusside": {
            "Mechanism of Action": "NO donor → potent arterial & venous dilation.",
            "Indications for Use": "Hypertensive crises.",
            "Effect on Patient": "↓ afterload.",
            "Adverse Reactions": "Cyanide toxicity (prolonged use), hypotension.",
            "Use": "Intra-op."
        },
        # --- Vasopressors & Inotropes ---
        "Vasopressin": {
            "Mechanism of Action": "V1 receptor agonist → vasoconstriction without pulmonary vasoconstriction.",
            "Indications for Use": "Vasoplegic syndrome, septic shock.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Ischemia (gut, skin), hyponatremia.",
            "Use": "Intra- & post-op."
        },
        "Phenylephrine": {
            "Mechanism of Action": "Pure alpha-adrenergic agonist → vasoconstriction.",
            "Indications for Use": "Hypotension with low SVR.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Reflex bradycardia.",
            "Use": "Intra-op."
        },
        "Norepinephrine": {
            "Mechanism of Action": "Alpha > beta agonist → vasoconstriction + mild inotropy.",
            "Indications for Use": "Shock states, low SVR.",
            "Effect on Patient": "↑ MAP, modest ↑ CO.",
            "Adverse Reactions": "Arrhythmias, ischemia.",
            "Use": "Intra- & post-op."
        },
        "Epinephrine": {
            "Mechanism of Action": "Beta > alpha agonist (dose-dependent).",
            "Indications for Use": "Cardiac arrest, shock.",
            "Effect on Patient": "↑ HR, ↑ CO, ↑ MAP.",
            "Adverse Reactions": "Arrhythmias, hyperglycemia.",
            "Use": "Intra- & post-op."
        },
        "Milrinone": {
            "Mechanism of Action": "PDE-3 inhibitor → ↑ cAMP → inotropy & vasodilation.",
            "Indications for Use": "Low CO, RV failure.",
            "Effect on Patient": "↑ CO, ↓ PVR & SVR.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Use": "Intra- & post-op."
        },
        "Levosimendan": {
            "Mechanism of Action": "Calcium sensitizer + PDE inhibition.",
            "Indications for Use": "Low-output states.",
            "Effect on Patient": "↑ contractility, mild vasodilation.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Use": "Not widely available in US; intra- or post-op."
        },
        # --- Electrolytes & Osmotic Diuretics ---
        "Calcium Chloride & Gluconate": {
            "Mechanism of Action": "Replenishes ionized calcium.",
            "Indications for Use": "Hypocalcemia, myocardial depression.",
            "Effect on Patient": "↑ contractility, restores normal coagulation.",
            "Adverse Reactions": "Arrhythmias if infused too fast.",
            "Use": "Intra- & post-op.",
            "CPB/CNS Considerations": "Important after CPB due to citrate binding."
        },
        "Mannitol": {
            "Mechanism of Action": "Osmotic diuretic.",
            "Indications for Use": "Renal protection, cerebral edema.",
            "Effect on Patient": "↑ urine output, ↓ ICP.",
            "Adverse Reactions": "Fluid/electrolyte shifts.",
            "Use": "In prime or intra-op."
        },
        # --- Heparin & Protamine (for CPB) ---
        "Heparin (CPB)": {
            "Mechanism of Action": "Potentiates antithrombin → inhibits thrombin & Factor Xa.",
            "Indications for Use": "Anticoagulation on CPB.",
            "Effect on Patient": "Prevents clotting in circuit.",
            "Adverse Reactions": "HIT, bleeding.",
            "Use": "Pre- & intra-op."
        },
        "Protamine (CPB)": {
            "Mechanism of Action": "Binds & neutralizes heparin.",
            "Indications for Use": "Reverse heparin after CPB.",
            "Effect on Patient": "Restores clotting.",
            "Adverse Reactions": "Hypotension, anaphylaxis, pulmonary hypertension.",
            "Use": "Post-CPB."
        },
        # --- Metabolic Regulators ---
        "Insulin (Regular)": {
            "Mechanism of Action": "Promotes glucose & K⁺ uptake.",
            "Indications for Use": "Hyperglycemia, hyperkalemia.",
            "Effect on Patient": "↓ glucose & potassium.",
            "Adverse Reactions": "Hypoglycemia, hypokalemia.",
            "Situations to Avoid": "Hypoglycemia, caution in renal failure.",
            "Adjuvants": "Given with dextrose & K⁺.",
            "Use": "All phases.",
            "CPB/CNS Considerations": "Frequent glucose checks; ↑ sensitivity post-CPB."
        },
        "Dextrose 50% (D50)": {
            "Mechanism of Action": "Provides immediate glucose.",
            "Indications for Use": "Hypoglycemia.",
            "Effect on Patient": "Rapid ↑ in serum glucose.",
            "Adverse Reactions": "Phlebitis, tissue necrosis (if extravasated).",
            "Situations to Avoid": "Hyperosmolar states, severe hyperglycemia.",
            "Adjuvants": "With insulin or glucagon.",
            "Use": "All phases.",
            "CPB/CNS Considerations": "Useful post-CPB."
        },
        "Glucagon": {
            "Mechanism of Action": "Stimulates hepatic glycogenolysis & gluconeogenesis.",
            "Indications for Use": "Severe hypoglycemia, β-blocker or CCB overdose.",
            "Effect on Patient": "↑ blood sugar, ↑ HR & contractility.",
            "Adverse Reactions": "Nausea, hyperglycemia, hypotension.",
            "Situations to Avoid": "Insulinoma, pheochromocytoma.",
            "Adjuvants": "With calcium/glucose for overdose.",
            "Use": "Post-op or emergency.",
            "CPB/CNS Considerations": "Useful in β-blocker overdose post-CPB."
        },
        # --- Reversal Agents & Coagulation ---
        "Vitamin K (Phytonadione)": {
            "Mechanism of Action": "Restores carboxylation of clotting factors.",
            "Indications for Use": "VKA (warfarin) reversal.",
            "Effect on Patient": "Gradual correction of INR.",
            "Adverse Reactions": "Rare anaphylaxis (IV/IM).",
            "Use": "Post-op or emergency."
        },
        "4-Factor PCC (Kcentra)": {
            "Mechanism of Action": "Provides factors II, VII, IX, X.",
            "Indications for Use": "Rapid INR reversal.",
            "Effect on Patient": "Quick clotting factor restoration.",
            "Use": "Emergency reversal."
        },
        "FFP (Fresh Frozen Plasma)": {
            "Mechanism of Action": "Supplies clotting factors & proteins.",
            "Indications for Use": "Coagulopathy, ATIII replacement.",
            "Effect on Patient": "Replaces clotting components.",
            "Adverse Reactions": "TACO, TRALI, allergic reactions."
        },
        # --- Direct Oral Anticoagulants (DOACs) ---
        "Edoxaban (Savaysa) & Betrixaban (Bevyxxa)": {
            "Mechanism of Action": "Oral Factor Xa inhibitors.",
            "Indications for Use": "VTE prevention/treatment, AF.",
            "Effect on Patient": "Anticoagulation."
        },
        # --- Antifibrinolytics ---
        "Tranexamic Acid (TXA)": {
            "Mechanism of Action": "Lysine analogue — inhibits plasminogen activation → ↓ fibrinolysis.",
            "Indications for Use": "Reduce bleeding during & after CPB.",
            "Effect on Patient": "↓ bleeding, ↓ transfusion requirements.",
            "Adverse Reactions": "Rare seizures (high dose), thrombosis.",
            "Situations to Avoid": "Active thrombosis, history of seizures.",
            "Adjuvants": "Used with standard coagulation management.",
            "Use": "Pre-, intra-, and post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Often added to prime; may accumulate if renal dysfunction."
        },
        "Epsilon-Aminocaproic Acid (EACA)": {
            "Mechanism of Action": "Similar to TXA — inhibits fibrinolysis.",
            "Indications for Use": "Reduce bleeding.",
            "Effect on Patient": "↓ bleeding, ↓ transfusion.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Situations to Avoid": "Active thrombosis.",
            "Use": "Pre-, intra-, and post-op."
        },
        # --- Prostacyclin ---
        "Epoprostenol (Prostacyclin)": {
            "Mechanism of Action": "PGI₂ analogue — vasodilates & inhibits platelet aggregation.",
            "Indications for Use": "ECMO or CPB circuits to prevent thrombosis.",
            "Effect on Patient": "↑ circuit patency, ↓ platelet aggregation.",
            "Adverse Reactions": "Hypotension, flushing.",
            "Situations to Avoid": "Hypotension.",
            "Use": "Intra-op (circuit)."
        },
        # --- Vasodilators ---
        "Nitroglycerin": {
            "Mechanism of Action": "NO donor → venodilation & mild arterial dilation.",
            "Indications for Use": "Hypertension, myocardial ischemia during/after CPB.",
            "Effect on Patient": "↓ preload, mild ↓ afterload, ↑ coronary flow.",
            "Adverse Reactions": "Hypotension, headache.",
            "Situations to Avoid": "Severe hypotension.",
            "Use": "Intra- & post-op."
        },
        "Nitroprusside": {
            "Mechanism of Action": "NO donor → potent arterial & venous dilation.",
            "Indications for Use": "Hypertensive crises.",
            "Effect on Patient": "↓ afterload.",
            "Adverse Reactions": "Cyanide toxicity (prolonged use), hypotension.",
            "Use": "Intra-op."
        },
        # --- Vasopressors & Inotropes ---
        "Vasopressin": {
            "Mechanism of Action": "V1 receptor agonist → vasoconstriction without pulmonary vasoconstriction.",
            "Indications for Use": "Vasoplegic syndrome, septic shock.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Ischemia (gut, skin), hyponatremia.",
            "Use": "Intra- & post-op."
        },
        "Phenylephrine": {
            "Mechanism of Action": "Pure alpha-adrenergic agonist → vasoconstriction.",
            "Indications for Use": "Hypotension with low SVR.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Reflex bradycardia.",
            "Use": "Intra-op."
        },
        "Norepinephrine": {
            "Mechanism of Action": "Alpha > beta agonist → vasoconstriction + mild inotropy.",
            "Indications for Use": "Shock states, low SVR.",
            "Effect on Patient": "↑ MAP, modest ↑ CO.",
            "Adverse Reactions": "Arrhythmias, ischemia.",
            "Use": "Intra- & post-op."
        },
        "Epinephrine": {
            "Mechanism of Action": "Beta > alpha agonist (dose-dependent).",
            "Indications for Use": "Cardiac arrest, shock.",
            "Effect on Patient": "↑ HR, ↑ CO, ↑ MAP.",
            "Adverse Reactions": "Arrhythmias, hyperglycemia.",
            "Use": "Intra- & post-op."
        },
        "Milrinone": {
            "Mechanism of Action": "PDE-3 inhibitor → ↑ cAMP → inotropy & vasodilation.",
            "Indications for Use": "Low CO, RV failure.",
            "Effect on Patient": "↑ CO, ↓ PVR & SVR.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Use": "Intra- & post-op."
        },
        "Levosimendan": {
            "Mechanism of Action": "Calcium sensitizer + PDE inhibition.",
            "Indications for Use": "Low-output states.",
            "Effect on Patient": "↑ contractility, mild vasodilation.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Use": "Not widely available in US; intra- or post-op."
        },
        # --- Electrolytes & Osmotic Diuretics ---
        "Calcium Chloride & Gluconate": {
            "Mechanism of Action": "Replenishes ionized calcium.",
            "Indications for Use": "Hypocalcemia, myocardial depression.",
            "Effect on Patient": "↑ contractility, restores normal coagulation.",
            "Adverse Reactions": "Arrhythmias if infused too fast.",
            "Use": "Intra- & post-op.",
            "CPB/CNS Considerations": "Important after CPB due to citrate binding."
        },
        "Mannitol": {
            "Mechanism of Action": "Osmotic diuretic.",
            "Indications for Use": "Renal protection, cerebral edema.",
            "Effect on Patient": "↑ urine output, ↓ ICP.",
            "Adverse Reactions": "Fluid/electrolyte shifts.",
            "Use": "In prime or intra-op."
        },
    # --- Class I Antiarrhythmics ---
    "Quinidine (Class IA)": {
        "Mechanism of Action": "Blocks fast Na⁺ & K⁺ channels → slows conduction & prolongs action potential (AP).",
        "Indications for Use": "Atrial fibrillation/flutter, ventricular arrhythmias.",
        "Effect on Patient": "Slows rhythm, ↑ AP duration.",
        "Adverse Reactions": "QT prolongation, torsades de pointes, diarrhea.",
        "Situations to Avoid": "Prolonged QT, CHF, AV block.",
        "Adjuvants": "Combine with AV nodal blockers to prevent 1:1 conduction.",
        "Use": "Post-op (rare).",
        "CPB/CNS Considerations": "May require redosing."
    },
    "Procainamide (Class IA)": {
        "Mechanism of Action": "Na⁺ channel blocker → prolongs refractory period & slows conduction.",
        "Indications for Use": "Ventricular tachycardia (VT), supraventricular tachycardia (SVT).",
        "Effect on Patient": "Slows conduction, converts or suppresses arrhythmias.",
        "Adverse Reactions": "Hypotension, torsades, lupus-like syndrome.",
        "Situations to Avoid": "CHF, QT prolongation, lupus.",
        "Adjuvants": "Monitor with continuous ECG.",
        "Use": "Intra- or post-op VT.",
        "CPB/CNS Considerations": "Prolonged due to slowed clearance."
    },
    "Disopyramide (Class IA, strong anticholinergic)": {
        "Mechanism of Action": "Na⁺ & K⁺ channel blocker → prolongs conduction.",
        "Indications for Use": "Ventricular arrhythmias, hypertrophic cardiomyopathy (HCM).",
        "Effect on Patient": "Slows conduction.",
        "Adverse Reactions": "Anticholinergic effects, QT prolongation.",
        "Situations to Avoid": "HF, glaucoma, urinary retention.",
        "Use": "Outpatient HCM (not intra-op).",
        "CPB/CNS Considerations": "Not used intra-op."
    },
    # --- Class IB Antiarrhythmics ---
    "Lidocaine (Class IB)": {
        "Mechanism of Action": "Blocks inactivated Na⁺ channels → shortens AP.",
        "Indications for Use": "Ventricular arrhythmias, VF/VT.",
        "Effect on Patient": "Stabilizes ventricular myocardium.",
        "Adverse Reactions": "CNS toxicity, bradycardia.",
        "Situations to Avoid": "Liver failure, SA/AV block.",
        "Adjuvants": "IV push + drip.",
        "Use": "Intra- or post-op VT/VF.",
        "CPB/CNS Considerations": "↑ distribution → may need bolus."
    },
    "Mexiletine (Class IB)": {
        "Mechanism of Action": "Similar to lidocaine — blocks inactivated Na⁺ channels → shortens AP.",
        "Indications for Use": "Chronic ventricular arrhythmias.",
        "Effect on Patient": "Prevents VT recurrence.",
        "Adverse Reactions": "Tremor, nausea, dizziness.",
        "Situations to Avoid": "Liver dysfunction.",
        "Adjuvants": "Often combined with other antiarrhythmics.",
        "Use": "Outpatient.",
        "CPB/CNS Considerations": "Not specified."
    },
        "Dexamethasone (Decadron) [Antiemetic]": {
            "Mechanism of Action": "Glucocorticoid receptor agonist → ↓ prostaglandins & cytokines.",
            "Indications for Use": "PONV prophylaxis, cerebral edema, anti-inflammatory.",
            "Effect on Patient": "Enhanced antiemetic effect, ↓ inflammation.",
            "Adverse Reactions": "Hyperglycemia.",
            "Situations to Avoid": "Uncontrolled diabetes.",
            "Adjuvants": "Often used with 5-HT₃ antagonists or aprepitant.",
            "Use": "Pre-op, intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Redosing may be required; beneficial anti-inflammatory effects."
        },
        "Amisulpride": {
            "Mechanism of Action": "Selective D₂/D₃ receptor antagonist.",
            "Indications for Use": "PONV & rescue antiemetic.",
            "Effect on Patient": "Reduces nausea & vomiting.",
            "Adverse Reactions": "QT prolongation, hypotension.",
            "Situations to Avoid": "QT prolongation, Parkinson’s disease, bradyarrhythmias.",
            "Adjuvants": "Used with 5-HT₃ antagonists + dexamethasone.",
            "Use": "Intra-op or post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Minimal effect."
        },
        "Droperidol": {
            "Mechanism of Action": "D₂ receptor antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Antiemetic, mild sedative & tranquilizer.",
            "Adverse Reactions": "QT prolongation, hypotension.",
            "Situations to Avoid": "Prolonged QT, Parkinson’s disease, hypotension.",
            "Adjuvants": "Used with 5-HT₃ antagonists + dexamethasone.",
            "Use": "Intra-op or post-op.",
            "Potency": "High at small doses.",
            "CPB/CNS Considerations": "Minimal, may need redosing."
        },
        "Haloperidol (Haldol)": {
            "Mechanism of Action": "D₂ receptor antagonist.",
            "Indications for Use": "PONV (off-label), sedation.",
            "Effect on Patient": "Antiemetic, sedative effect.",
            "Adverse Reactions": "QT prolongation, hypotension, risk in elderly with dementia.",
            "Situations to Avoid": "Parkinson’s, QT prolongation, elderly with dementia.",
            "Adjuvants": "Can be paired with benzodiazepines.",
            "Use": "Post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Minimal."
        },
        "Dimenhydrinate (Dramamine)": {
            "Mechanism of Action": "H₁ receptor blocker + anticholinergic effects.",
            "Indications for Use": "PONV, motion sickness, vertigo.",
            "Effect on Patient": "Reduces nausea & vomiting.",
            "Adverse Reactions": "Sedation, dry mouth, dizziness, blurred vision.",
            "Situations to Avoid": "Elderly, glaucoma.",
            "Use": "Pre-op or post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Not specified."
        },
        "Promethazine": {
            "Mechanism of Action": "H₁ receptor blocker + weak D₂ antagonist.",
            "Indications for Use": "PONV, motion sickness.",
            "Effect on Patient": "Reduces nausea, strong sedative.",
            "Adverse Reactions": "Sedation, hypotension.",
            "Situations to Avoid": "Elderly, children <2 years (respiratory depression risk).",
            "Adjuvants": "Can potentiate opioids & propofol.",
            "Use": "Pre-op or post-op.",
            "Potency": "High (sedative), moderate (antiemetic)."
        },
        "Succinylcholine (Anectine)": {
            "Mechanism of Action": "Mimics acetylcholine → depolarizes neuromuscular junction → sustained paralysis.",
            "Indications for Use": "Rapid intubation, short-term paralysis.",
            "Effect on Patient": "Complete muscle paralysis (including diaphragm).",
            "Adverse Reactions": "Hyperkalemia, malignant hyperthermia, bradycardia.",
            "Situations to Avoid": "Burns, trauma, renal failure.",
            "Adjuvants": "Requires sedation & analgesia prior.",
            "Use": "Induction.",
            "Potency": "Very high, rapid onset.",
            "CPB/CNS Considerations": "Often used prior to CPB."
        },
        "Pancuronium": {
            "Mechanism of Action": "Competitive acetylcholine antagonist at NMJ.",
            "Indications for Use": "Maintenance of paralysis.",
            "Effect on Patient": "Long-lasting muscle paralysis.",
            "Adverse Reactions": "Tachycardia, hypertension, delayed emergence.",
            "Situations to Avoid": "Pre-existing tachycardia, hypertensive patients.",
            "Adjuvants": "Requires sedation & analgesia prior.",
            "Use": "Induction.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Prolonged effect prior to bypass."
        },
        "Vecuronium": {
            "Mechanism of Action": "Competitive acetylcholine antagonist.",
            "Indications for Use": "Paralysis for general anesthesia & intubation.",
            "Effect on Patient": "Smooth onset & offset of paralysis.",
            "Adverse Reactions": "Bradycardia, prolonged block in liver/renal disease.",
            "Situations to Avoid": "Liver/renal impairment.",
            "Adjuvants": "Requires sedation & analgesia prior.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Prolonged duration due to ↓ clearance."
        },
        "Rocuronium": {
            "Mechanism of Action": "Competitive acetylcholine antagonist.",
            "Indications for Use": "Rapid intubation, intra-op muscle relaxation.",
            "Effect on Patient": "Rapid-onset muscle relaxation.",
            "Adverse Reactions": "Hypersensitivity, anaphylaxis, prolonged block.",
            "Situations to Avoid": "Known sensitivity.",
            "Adjuvants": "Requires sedation & analgesia.",
            "Use": "Pre-op & intra-op.",
            "Potency": "High, reversible with sugammadex.",
            "CPB/CNS Considerations": "Fast onset, possible prolongation on bypass."
        },
        "Atracurium": {
            "Mechanism of Action": "Competitive acetylcholine antagonist at NMJ.",
            "Indications for Use": "Intra-op paralysis; preferred in hepatic/renal impairment.",
            "Effect on Patient": "Smooth paralysis.",
            "Adverse Reactions": "Histamine release → hypotension, flushing.",
            "Situations to Avoid": "Asthma, histamine sensitivity.",
            "Adjuvants": "Used with propofol, benzodiazepines, opioids.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hofmann elimination continues on CPB → predictable duration."
        },
        "Cisatracurium (Nimbex)": {
            "Mechanism of Action": "Same as atracurium — competitive NMJ blocker.",
            "Indications for Use": "Muscle relaxation, renal/liver failure patients.",
            "Effect on Patient": "Predictable paralysis, minimal histamine release.",
            "Adverse Reactions": "Minimal.",
            "Use": "Intra-op.",
            "Potency": "Moderate to high.",
            "CPB/CNS Considerations": "Unaffected."
        },
        "Mivacurium": {
            "Mechanism of Action": "Competitive acetylcholine antagonist.",
            "Indications for Use": "Short surgeries.",
            "Effect on Patient": "Fast onset, short duration paralysis.",
            "Adverse Reactions": "Histamine release → hypotension, bronchospasm.",
            "Situations to Avoid": "Pseudocholinesterase deficiency, asthma, allergy.",
            "Use": "Intra-op.",
            "Potency": "Low (vs. rocuronium).",
            "CPB/CNS Considerations": "Prolonged effect."
        },
        "Neostigmine": {
            "Mechanism of Action": "Inhibits acetylcholinesterase → ↑ acetylcholine at NMJ.",
            "Indications for Use": "Reversal of non-depolarizing NMBAs (e.g., vecuronium, rocuronium).",
            "Effect on Patient": "Restores NMJ function.",
            "Adverse Reactions": "Bradycardia, ↑ secretions, bronchospasm.",
            "Situations to Avoid": "Bradycardia, GI obstruction.",
            "Adjuvants": "Must be paired with glycopyrrolate or atropine to offset muscarinic effects.",
            "Use": "Post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Onset may be delayed by hypothermia/hemodilution."
        },
        "Edrophonium": {
            "Mechanism of Action": "Same as neostigmine — inhibits acetylcholinesterase.",
            "Indications for Use": "Reversal of NMB; diagnosis of myasthenia gravis.",
            "Effect on Patient": "Transient return of muscle strength.",
            "Adverse Reactions": "Bradycardia, cholinergic symptoms (salivation, diarrhea).",
            "Situations to Avoid": "Asthma, bradyarrhythmias.",
            "Adjuvants": "Given with atropine.",
            "Use": "Rarely post-op.",
            "Potency": "Short-acting.",
            "CPB/CNS Considerations": "Rapid metabolism → limited impact."
        },
        "Sugammadex": {
            "Mechanism of Action": "Encapsulates rocuronium/vecuronium in plasma → inactivates them.",
            "Indications for Use": "Rapid reversal of rocuronium or vecuronium.",
            "Effect on Patient": "Fast, complete reversal of paralysis.",
            "Adverse Reactions": "Bradycardia, hypotension, rare anaphylaxis.",
            "Situations to Avoid": "If non-steroidal NMBAs (e.g., atracurium) were used.",
            "Use": "Post-op, intra-op.",
            "Potency": "Very high.",
            "CPB/CNS Considerations": "Effective post-CPB, unaffected by bypass."
        },
        "Cortisol (Hydrocortisone)": {
            "Mechanism of Action": "Binds intracellular glucocorticoid receptors → alters gene expression.",
            "Indications for Use": "Adrenal insufficiency, sepsis, inflammation.",
            "Effect on Patient": "Supports BP, glucose metabolism, stress response.",
            "Adverse Reactions": "Hyperglycemia, fluid retention, immune suppression.",
            "Situations to Avoid": "Uncontrolled diabetes, active infection.",
            "Adjuvants": "Often used with vasopressors in septic shock.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Supports hemodynamics during CPB."
        },
        "Dexamethasone (Decadron) [Glucocorticoid]": {
            "Mechanism of Action": "Suppresses cytokines & prostaglandins.",
            "Indications for Use": "PONV, cerebral edema, allergy, inflammation.",
            "Effect on Patient": "↓ inflammation, ↓ nausea.",
            "Adverse Reactions": "Hyperglycemia, insomnia, mood changes.",
            "Situations to Avoid": "Uncontrolled diabetes.",
            "Adjuvants": "Used with 5-HT₃ antagonists (antiemetic).",
            "Use": "Pre-, intra-, post-op.",
            "Potency": "Very high.",
            "CPB/CNS Considerations": "Helpful anti-inflammatory effects on CPB."
        },
        "Methylprednisolone": {
            "Mechanism of Action": "Alters inflammatory gene expression.",
            "Indications for Use": "Inflammation suppression, spinal injury, neuroprotection.",
            "Effect on Patient": "Potent anti-inflammatory.",
            "Adverse Reactions": "Hyperglycemia, infection risk, delayed healing.",
            "Situations to Avoid": "Diabetes, immunosuppression.",
            "Adjuvants": "Often combined with mannitol.",
            "Use": "Intra- or post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Blunts inflammatory response during CPB."
        },
        "Fludrocortisone": {
            "Mechanism of Action": "Mineralocorticoid → ↑ sodium & water reabsorption in kidney.",
            "Indications for Use": "Adrenal insufficiency, orthostatic hypotension.",
            "Effect on Patient": "↑ BP via volume expansion.",
            "Adverse Reactions": "Hypertension, hypokalemia, edema.",
            "Situations to Avoid": "CHF, hypertension, fluid overload.",
            "Adjuvants": "Used with hydrocortisone.",
            "Use": "Pre-op (if adrenal insufficiency).",
            "Potency": "High (mineralocorticoid).",
            "CPB/CNS Considerations": "Minimal effect."
        },
        "Cisplatin": {
            "Mechanism of Action": "Platinum alkylating agent → DNA crosslinking → cell death.",
            "Indications for Use": "Peritoneal carcinomatosis, cancer.",
            "Effect on Patient": "Cytotoxic — kills tumor cells, slows progression.",
            "Adverse Reactions": "Nephrotoxicity, peripheral neuropathy, nausea, vomiting.",
            "Use": "Intra-op."
        },
        "Oxaliplatin": {
            "Mechanism of Action": "Platinum alkylating agent → DNA crosslinking → cell death.",
            "Indications for Use": "Cancer (peritoneal carcinomatosis).",
            "Effect on Patient": "Cytotoxic — kills tumor cells, slows progression.",
            "Adverse Reactions": "Peripheral neuropathy, bone marrow suppression, cold sensitivity.",
            "Use": "Intra-op."
        },
        "General Antiemetic": {
            "Mechanism of Action": "Broad — various anti-nausea pathways.",
            "Indications for Use": "Prevent or treat nausea/vomiting.",
            "Effect on Patient": "Antiemetic effect.",
            "Adverse Reactions": "Minimal (depends on drug).",
            "Use": "Pre-op, intra-op, or post-op.",
            "CPB/CNS Considerations": "Hemodilution on CPB may require redosing."
        },
        "Granisetron (Sustol)": {
            "Mechanism of Action": "5-HT₃ receptor antagonist (central & peripheral).",
            "Indications for Use": "Postoperative nausea and vomiting (PONV).",
            "Effect on Patient": "Reduces nausea and vomiting.",
            "Adverse Reactions": "Headache, constipation, QT prolongation.",
            "Situations to Avoid": "Patients at risk of QT prolongation.",
            "Adjuvants": "Often combined with dexamethasone or NK-1 antagonists.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Minimal, may need redosing."
        },
        "Palonosetron (Aloxi)": {
            "Mechanism of Action": "Long-acting 5-HT₃ receptor antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Long-lasting antiemetic effect.",
            "Adverse Reactions": "Headache, constipation, QT prolongation.",
            "Situations to Avoid": "Patients at risk of QT prolongation.",
            "Adjuvants": "Often combined with dexamethasone or NK-1 antagonists.",
            "Use": "Pre-op.",
            "Potency": "High, longer half-life.",
            "CPB/CNS Considerations": "Minimal, less redosing required."
        },
        "Aprepitant": {
            "Mechanism of Action": "NK-1 receptor antagonist → blocks substance P.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Reduces nausea and vomiting.",
            "Adverse Reactions": "Fatigue, hiccups, constipation.",
            "Situations to Avoid": "Patients on CYP3A4 substrates or inducers, pregnancy.",
            "Adjuvants": "Often combined with 5-HT₃ antagonists + dexamethasone.",
            "Use": "Pre-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Minimal effect."
        },
    }


    drug_names = list(drug_data.keys())


    # --- Drug Library UI ---
    # Search bar and dropdown for drug selection
    search = st.text_input("Search for a drug:")
    filtered = [d for d in drug_names if search.lower() in d.lower()] if search else drug_names

    selected_drug = st.selectbox("Select a drug to view details:", filtered, key="drug_select")
    if selected_drug:
        st.subheader(selected_drug)
        for k, v in drug_data[selected_drug].items():
            st.write(f"**{k}:** {v}")

    st.markdown("---")
    st.markdown("### Compare Drugs")
    compare = st.multiselect("Select up to 2 drugs to compare:", filtered, max_selections=2, key="compare_select")
    if len(compare) == 2:
        st.write(f"#### {compare[0]} vs {compare[1]}")
        col1, col2 = st.columns(2)
        for key in set(drug_data[compare[0]].keys()).union(drug_data[compare[1]].keys()):
            with col1:
                st.write(f"**{key}:** {drug_data[compare[0]].get(key, '-')}")
            with col2:
                st.write(f"**{key}:** {drug_data[compare[1]].get(key, '-')}")

    # ---- Sidebar ----
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
        pdf_comorbid = st.checkbox("Comorbidities / Pathology", True)
        pdf_cardio = st.checkbox("Cardioplegia", True)
        pdf_cabg = st.checkbox("CABG Grafts", True)
        pdf_arrest = st.checkbox("Arrest Plan", True)
        st.markdown("""<sub><i>
        Medical Disclaimer: The information provided in this application is strictly for educational purposes only and is not intended or implied to be a substitute for medical advice or instruction by a health professional. Information in this application may differ from the opinions of your institution. Consult with a recognized medical professional before making decisions based on the information in this application. The authors are not responsible for the use or interpretation you make of any information provided.
        </i></sub>""", unsafe_allow_html=True)

    # ---- Main Pre-CPB Tool UI ----
    st.title("Bypass Blueprint")
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

    target_hct = st.number_input("Hematocrit Transfusion Threshold (%)", value=25.0)
    procedure = st.selectbox("Procedure Type", ["CABG", "AVR", "MVR", "Transplant", "Hemiarch", "Bentall", "Full Arch", "Dissection Repair – Stanford Type A", "Dissection Repair – Stanford Type B", "LVAD", "Off-pump CABG", "ECMO Cannulation", "Standby", "Other"])
    comorbidities = st.multiselect("Comorbidities", ["CKD", "Hypertension", "Jehovah’s Witness", "Anemia", "Aortic Disease", "Diabetes", "Redo Sternotomy", "None"])
    valve_issues = st.multiselect("Valve Pathology", ["Aortic Stenosis", "Aortic Insufficiency", "Mitral Stenosis", "Mitral Regurgitation", "Tricuspid Regurgitation", "Valve Prolapse"])
    blood_type = st.selectbox("Patient Blood Type", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])

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

    protocol_note = "No specific protocol provided."

    bsa = calculate_bsa(height, weight)
    bmi = calculate_bmi(height, weight)
    blood_vol = calculate_blood_volume(weight)
    post_hct = calculate_post_dilution_hct(pre_hct, blood_vol, prime_vol)
    rbc_units = calculate_rbc_units_needed(post_hct, target_hct)
    suggested_ci = 2.4
    flow = calculate_flow(suggested_ci, bsa)
    do2 = calculate_do2(flow, pre_hgb)
    do2i = round(do2 / bsa, 1)
    map_target = get_map_target(comorbidities)
    heparin_dose = calculate_heparin_dose(weight)

    blood_compatibility = get_compatible_blood_products(blood_type)

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
        patient_rows = [["PARAMETER", "VALUE", "NOTES / FORMULA"]]
        if pdf_height: patient_rows.append(["Height", f"{height} cm", "–"])
        if pdf_weight: patient_rows.append(["Weight", f"{weight} kg", "–"])
        if pdf_bmi: patient_rows.append(["BMI", f"{bmi}", "Weight / (Height/100)^2"])
        if pdf_bsa: patient_rows.append(["BSA", f"{bsa} m²", "√(Height × Weight / 3600)"])
        if pdf_pre_hct: patient_rows.append(["Pre-op Hct", f"{pre_hct}%", "Baseline"])
        if pdf_pre_hgb: patient_rows.append(["Pre-op Hgb", f"{pre_hgb:.2f} g/dL", "–"])
        if pdf_target_hct: patient_rows.append(["Hematocrit Transfusion Threshold", f"{target_hct}%", "Transfusion threshold during CPB"])
        if pdf_comorbid: patient_rows.append(["Comorbidities", ", ".join(comorbidities), "–"])
        if valve_issues: patient_rows.append(["Valve Pathology", ", ".join(valve_issues), "–"])
        build_parameter_table(story, "BODY METRICS & VOLUMES", patient_rows)

        if pdf_prime_vol:
            prime_rows = [["PARAMETER", "VALUE", "NOTES / FORMULA"]]
            prime_rows.append(["Prime Volume", f"{prime_vol} mL", "CPB circuit prime"])
            prime_rows.append(["Prime Osmolality", f"{prime_osmo} mOsm/kg", "Normal estimate"])
            if base_prime: prime_rows.append(["Base Prime", base_prime, "–"])
            if pdf_prime_add and prime_additives:
                prime_rows.append(["Additives", ", ".join(prime_additives), "–"])
            build_parameter_table(story, "PRIME COMPOSITION", prime_rows)

        if pdf_cardio:
            cardio_rows = [["ITEM", "DETAIL", ""]]
            cardio_rows.append(["Cardioplegia", cardioplegia_type, ""])
            cardio_rows.append(["Delivery Routes", ", ".join(delivery_routes), ""])
            build_parameter_table(story, "CARDIOPLEGIA", cardio_rows)

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
    story.append(Spacer(1, 8))
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
    if selected_graft_images:
        story.append(Spacer(1, 12))
        story.append(Paragraph("CABG Graft Images", styles["Heading2"]))
        story.append(Spacer(1, 6))
        for img_path in selected_graft_images:
            if os.path.exists(img_path):
                graft_img = RLImage(img_path, width=250, height=150)
                story.append(graft_img)
                story.append(Spacer(1, 6))
    transfusion_rows = [["PRODUCT", "COMPATIBLE TYPES", ""]]
    for product in ["PRBC", "FFP", "Cryo", "Whole Blood"]:
        transfusion_rows.append([product, ", ".join(blood_compatibility[product]), ""])
    build_parameter_table(story, "TRANSFUSION COMPATIBILITY", transfusion_rows)
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
    doc.build(story)
    st.download_button("Download PDF", data=pdf_buffer.getvalue(), file_name="precpb_summary.pdf", mime="application/pdf")
