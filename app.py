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

if tool == "Pre-CPB Tool":
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

    # Cardioplegia/Arrest/Images Inputs
    cardioplegia_type = st.selectbox("Cardioplegia Type", ["4:1", "Del Nido", "Microplegia", "Other"])
    delivery_routes = st.multiselect("Cardioplegia Delivery Routes", ["Antegrade", "Retrograde", "Ostial", "Direct Coronary"], default=["Antegrade"])
    arrest_duration = st.number_input("Arrest Duration (min)", value=45)
    neuro_strategy = st.text_input("Neuroprotection Strategy", value="")
    selected_graft_images = st.file_uploader("Upload CABG Graft Images", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

    if procedure in ["Dissection Repair – Stanford Type A", "Full Arch"] and pdf_arrest:
        arrest_temp = st.number_input("Target Arrest Temperature (°C)", value=18)
    else:
        arrest_temp = None

    # ---- Calculations ----
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
        for img_file in selected_graft_images:
            graft_img = RLImage(img_file, width=250, height=150)
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

# ---- Drug Library Section ----
if tool == "Drug Library":


    # Drug Library is a completely separate entity. No Bypass Blueprint or Pre-CPB Tool code or UI here.
    # Example drug data structure (replace/add with your real data)
    drug_data = {
        # --- Updated and new drugs from user list ---
        "Methylene Blue": {
            "Mechanism of Action": "Inhibits nitric oxide & cGMP pathway, forms methemoglobin at higher doses.",
            "Indications for Use": "Vasoplegic syndrome, methemoglobinemia.",
            "Effect on Patient": "Restores vascular tone, treats methemoglobinemia.",
            "Adverse Reactions": "Serotonin syndrome, blue urine, hypertension.",
            "Situations to Avoid": "SSRIs.",
            "Adjuvants": "Vasopressors, oxygen.",
            "Use": "Intra- or post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Hemodilution may ↓ concentration."
        },
        "Statins": {
            "Mechanism of Action": "HMG-CoA reductase inhibitor → ↓ cholesterol synthesis.",
            "Indications for Use": "Hyperlipidemia, CV risk reduction.",
            "Effect on Patient": "↓ LDL, ↓ triglycerides, ↑ HDL.",
            "Adverse Reactions": "Myopathy, liver dysfunction.",
            "Situations to Avoid": "Liver disease.",
            "Adjuvants": "Omega-3, niacin.",
            "Use": "Pre-op.",
            "Potency": "Moderate–high.",
            "CPB/CNS Considerations": "None."
        },
        "Fibrates": {
            "Mechanism of Action": "Upregulates lipoprotein lipase → ↓ TGs, ↑ HDL.",
            "Indications for Use": "Hypertriglyceridemia.",
            "Effect on Patient": "↓ TGs, ↑ HDL.",
            "Adverse Reactions": "Hepatic dysfunction.",
            "Situations to Avoid": "Liver & renal dysfunction.",
            "Adjuvants": "Caution with statins.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Bile Acid Sequestrants": {
            "Mechanism of Action": "Binds bile acids → ↑ excretion → ↑ LDL receptor.",
            "Indications for Use": "Hypercholesterolemia.",
            "Effect on Patient": "↓ LDL.",
            "Adverse Reactions": "Constipation, bloating.",
            "Situations to Avoid": "GI disorders.",
            "Adjuvants": "Statins.",
            "Use": "Pre-op.",
            "Potency": "Low–moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Niacin": {
            "Mechanism of Action": "↓ TG synthesis, ↑ HDL via lipoprotein lipase.",
            "Indications for Use": "Hyperlipidemia.",
            "Effect on Patient": "↑ HDL, ↓ TG.",
            "Adverse Reactions": "Flushing, hyperglycemia.",
            "Situations to Avoid": "Liver disease, diabetes.",
            "Adjuvants": "Statins.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Diazepam": {
            "Mechanism of Action": "GABA-A agonist → CNS depression.",
            "Indications for Use": "Sedation, anxiety.",
            "Effect on Patient": "Sedation, amnesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Elderly, respiratory compromise.",
            "Adjuvants": "Opioids.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hemodilution ↑ free drug."
        },
        "Lorazepam": {
            "Mechanism of Action": "GABA-A agonist.",
            "Indications for Use": "Anxiety, seizures.",
            "Effect on Patient": "Sedation, amnesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Pregnancy, elderly.",
            "Adjuvants": "Opioids.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hemodilution ↑ free drug."
        },
        "Midazolam": {
            "Mechanism of Action": "GABA-A agonist.",
            "Indications for Use": "Sedation.",
            "Effect on Patient": "Sedation, amnesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Elderly, respiratory compromise.",
            "Adjuvants": "Opioids.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hemodilution ↑ free drug."
        },
        "Atropine": {
            "Mechanism of Action": "Muscarinic antagonist → ↓ parasympathetic tone.",
            "Indications for Use": "Bradycardia.",
            "Effect on Patient": "↑ HR, ↓ secretions.",
            "Adverse Reactions": "Tachycardia, delirium.",
            "Situations to Avoid": "Tachyarrhythmias, elderly.",
            "Adjuvants": "Opioids.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Glycopyrrolate": {
            "Mechanism of Action": "Muscarinic antagonist.",
            "Indications for Use": "Reduce secretions, mild bradycardia.",
            "Effect on Patient": "↑ HR, ↓ secretions.",
            "Adverse Reactions": "Mild tachycardia.",
            "Situations to Avoid": "Arrhythmias.",
            "Adjuvants": "Opioids.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Adenosine": {
            "Mechanism of Action": "A1 receptor agonist → AV block.",
            "Indications for Use": "SVT.",
            "Effect on Patient": "Restores sinus rhythm.",
            "Adverse Reactions": "Flushing, chest pain.",
            "Situations to Avoid": "Asthma, AV block.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↓ plasma concentration."
        },
        "Magnesium": {
            "Mechanism of Action": "Stabilizes myocardium, ↓ Ca²⁺ influx.",
            "Indications for Use": "Torsades, VT.",
            "Effect on Patient": "Corrects arrhythmias.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Renal failure.",
            "Adjuvants": "Electrolyte repletion.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↓ plasma concentration."
        },
        "Propofol": {
            "Mechanism of Action": "GABA-A agonist → CNS depression.",
            "Indications for Use": "Induction/maintenance of anesthesia.",
            "Effect on Patient": "Sedation, ↓ BP.",
            "Adverse Reactions": "Hypotension, apnea.",
            "Situations to Avoid": "Egg/soy allergy, instability.",
            "Adjuvants": "Opioids.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ free drug."
        },
        "Dexmedetomidine": {
            "Mechanism of Action": "α2 agonist → ↓ NE release.",
            "Indications for Use": "Sedation of intubated patients.",
            "Effect on Patient": "Sedation, mild analgesia.",
            "Adverse Reactions": "Hypotension, bradycardia.",
            "Situations to Avoid": "Shock, diabetes.",
            "Adjuvants": "Opioids.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ free drug."
        },
        "Etomidate": {
            "Mechanism of Action": "GABAergic CNS depression.",
            "Indications for Use": "Induction with minimal CV depression.",
            "Effect on Patient": "Sedation.",
            "Adverse Reactions": "Adrenal suppression.",
            "Situations to Avoid": "Adrenal insufficiency.",
            "Adjuvants": "Opioids.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ free drug."
        },
        "Ketamine": {
            "Mechanism of Action": "NMDA antagonist.",
            "Indications for Use": "Induction, reactive airway disease.",
            "Effect on Patient": "Dissociation, ↑ HR, ↑ BP.",
            "Adverse Reactions": "Hallucinations, hypertension.",
            "Situations to Avoid": "Ischemic heart disease.",
            "Adjuvants": "Benzodiazepines.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ free drug."
        },
        "Alfentanil": {
            "Mechanism of Action": "μ-opioid agonist.",
            "Indications for Use": "Short intense procedures.",
            "Effect on Patient": "Rapid analgesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Respiratory failure.",
            "Adjuvants": "Benzos.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "↓ concentration."
        },
        "Fentanyl": {
            "Mechanism of Action": "μ-opioid agonist.",
            "Indications for Use": "Severe pain, adjunct.",
            "Effect on Patient": "Analgesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Same as above.",
            "Adjuvants": "Benzos.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↓ concentration."
        },
        "Remifentanil": {
            "Mechanism of Action": "μ-opioid agonist.",
            "Indications for Use": "Precisely controlled analgesia.",
            "Effect on Patient": "Rapid-onset, short-acting.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Esterase deficiency.",
            "Adjuvants": "Benzos.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not sequestered."
        },
        "Sufentanil": {
            "Mechanism of Action": "μ-opioid agonist.",
            "Indications for Use": "Surgical analgesia.",
            "Effect on Patient": "Profound analgesia.",
            "Adverse Reactions": "Respiratory depression.",
            "Situations to Avoid": "Same as above.",
            "Adjuvants": "Benzos.",
            "Use": "Intra-op.",
            "Potency": "Very high.",
            "CPB/CNS Considerations": "↓ concentration."
        },
        "Benzocaine": {
            "Mechanism of Action": "Na⁺ channel blocker (ester).",
            "Indications for Use": "Topical mucosal anesthesia.",
            "Effect on Patient": "Local numbness.",
            "Adverse Reactions": "Methemoglobinemia.",
            "Use": "Topical.",
            "Potency": "Low.",
            "CPB/CNS Considerations": "None."
        },
        "Bupivacaine": {
            "Mechanism of Action": "Na⁺ channel blocker (amide).",
            "Indications for Use": "Regional/epidural anesthesia.",
            "Effect on Patient": "Long-lasting numbness.",
            "Adverse Reactions": "Cardiotoxicity.",
            "Situations to Avoid": "Intravascular injection.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Ropivacaine": {
            "Mechanism of Action": "Na⁺ channel blocker (amide).",
            "Indications for Use": "Nerve blocks.",
            "Effect on Patient": "Numbness.",
            "Adverse Reactions": "Less cardiotoxic.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Lidocaine": {
            "Mechanism of Action": "Na⁺ channel blocker (amide).",
            "Indications for Use": "Local/regional anesthesia, antiarrhythmic.",
            "Effect on Patient": "Numbness, arrhythmia suppression.",
            "Adverse Reactions": "Systemic toxicity.",
            "Situations to Avoid": "Overdose.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Antiarrhythmic effect preserved."
        },
        "Acetaminophen": {
            "Mechanism of Action": "Weak COX inhibitor, centrally acting.",
            "Indications for Use": "Fever, mild pain.",
            "Effect on Patient": "Pain relief, antipyretic.",
            "Adverse Reactions": "Hepatotoxicity.",
            "Situations to Avoid": "Liver disease.",
            "Adjuvants": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        # ...existing and additional drugs remain below...
        "Ketorolac": {
            "Mechanism of Action": "COX inhibitor → ↓ prostaglandins.",
            "Indications for Use": "Moderate-to-severe pain.",
            "Effect on Patient": "Analgesia, anti-inflammatory.",
            "Adverse Reactions": "GI bleeding, renal injury.",
            "Situations to Avoid": "Renal dysfunction.",
            "Adjuvants": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Ibuprofen": {
            "Mechanism of Action": "COX inhibitor.",
            "Indications for Use": "Mild-to-moderate pain, inflammation.",
            "Effect on Patient": "Analgesia, anti-inflammatory.",
            "Adverse Reactions": "GI bleeding, renal injury.",
            "Situations to Avoid": "Renal failure.",
            "Adjuvants": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Ketamine (sub-anesthetic)": {
            "Mechanism of Action": "NMDA antagonist.",
            "Indications for Use": "Adjunct analgesia.",
            "Effect on Patient": "Analgesia, sedation.",
            "Adverse Reactions": "Hallucinations.",
            "Situations to Avoid": "Psychiatric disorders.",
            "Adjuvants": "Benzodiazepines.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Pregabalin": {
            "Mechanism of Action": "Binds α2δ calcium channel → ↓ neurotransmitter release.",
            "Indications for Use": "Neuropathic pain.",
            "Effect on Patient": "Analgesia, anxiolysis.",
            "Adverse Reactions": "Dizziness, sedation.",
            "Situations to Avoid": "None specified.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Gabapentin": {
            "Mechanism of Action": "Same as pregabalin.",
            "Indications for Use": "Neuropathic pain.",
            "Effect on Patient": "Analgesia.",
            "Adverse Reactions": "Dizziness, sedation.",
            "Situations to Avoid": "None specified.",
            "Adjuvants": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Dexamethasone (anti-inflammatory)": {
            "Mechanism of Action": "Glucocorticoid.",
            "Indications for Use": "Anti-inflammatory, antiemetic.",
            "Effect on Patient": "↓ inflammation & nausea.",
            "Adverse Reactions": "Hyperglycemia, insomnia.",
            "Situations to Avoid": "Uncontrolled diabetes.",
            "Adjuvants": "5-HT₃ antagonists.",
            "Use": "Post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Helpful during CPB."
        },
        "Magnesium (analgesic adjunct)": {
            "Mechanism of Action": "Calcium antagonist, NMDA antagonist.",
            "Indications for Use": "Analgesic adjunct, arrhythmias.",
            "Effect on Patient": "↓ pain, arrhythmia control.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Renal failure.",
            "Adjuvants": "Electrolyte therapy.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Mitomycin C": {
            "Mechanism of Action": "Alkylating agent → DNA crosslinks.",
            "Indications for Use": "HIPEC.",
            "Effect on Patient": "Tumor cell death.",
            "Adverse Reactions": "Marrow suppression.",
            "Situations to Avoid": "Severe marrow suppression.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Cisplatin": {
            "Mechanism of Action": "Platinum alkylator → DNA crosslinks.",
            "Indications for Use": "HIPEC.",
            "Effect on Patient": "Tumor cell death.",
            "Adverse Reactions": "Nephrotoxicity, neurotoxicity.",
            "Situations to Avoid": "Renal dysfunction.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Oxaliplatin": {
            "Mechanism of Action": "Platinum alkylator → DNA crosslinks.",
            "Indications for Use": "HIPEC.",
            "Effect on Patient": "Tumor cell death.",
            "Adverse Reactions": "Neuropathy, marrow suppression.",
            "Situations to Avoid": "Neuropathy.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "General Antiemetic": {
            "Mechanism of Action": "Broad anti-nausea pathways.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "↓ nausea.",
            "Adverse Reactions": "Minimal.",
            "Situations to Avoid": "None specified.",
            "Adjuvants": "None.",
            "Use": "Pre-/post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hemodilution may reduce effect."
        },
        "Granisetron": {
            "Mechanism of Action": "5-HT₃ antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "↓ nausea.",
            "Adverse Reactions": "Headache, QT prolongation.",
            "Situations to Avoid": "QT risk.",
            "Adjuvants": "Dexamethasone.",
            "Use": "Pre-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "May require redosing."
        },
        "Palonosetron": {
            "Mechanism of Action": "Long-acting 5-HT₃ antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "Long-acting antiemetic.",
            "Adverse Reactions": "Headache, QT prolongation.",
            "Situations to Avoid": "QT risk.",
            "Adjuvants": "Dexamethasone.",
            "Use": "Pre-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Less redosing needed."
        },
        "Aprepitant": {
            "Mechanism of Action": "NK-1 antagonist.",
            "Indications for Use": "PONV.",
            "Effect on Patient": "↓ nausea.",
            "Adverse Reactions": "Fatigue, hiccups.",
            "Situations to Avoid": "Pregnancy.",
            "Adjuvants": "5-HT₃ + dexamethasone.",
            "Use": "Pre-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        # --- Drugs 64–81 ---
        "Flecainide": {
            "Mechanism of Action": "Strong Na⁺ blocker.",
            "Indications for Use": "Afib, SVT.",
            "Effect on Patient": "Slows atrial arrhythmias.",
            "Adverse Reactions": "Blurred vision, pro-arrhythmia.",
            "Situations to Avoid": "Structural heart disease, MI.",
            "Adjuvants": "Beta blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Propafenone": {
            "Mechanism of Action": "Na⁺ blocker + mild beta blockade.",
            "Indications for Use": "Atrial arrhythmias.",
            "Effect on Patient": "Rhythm control.",
            "Adverse Reactions": "Metallic taste, bronchospasm.",
            "Situations to Avoid": "Asthma, HF.",
            "Adjuvants": "AV nodal blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Metoprolol": {
            "Mechanism of Action": "Beta-1 blocker.",
            "Indications for Use": "Afib, HTN, post-MI.",
            "Effect on Patient": "↓ HR, ↓ O₂ demand.",
            "Adverse Reactions": "Bradycardia, fatigue.",
            "Situations to Avoid": "Heart block, decompensated HF.",
            "Adjuvants": "Amiodarone, digoxin.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "May be held."
        },
        "Esmolol": {
            "Mechanism of Action": "Short-acting beta-1 blocker.",
            "Indications for Use": "Acute rate control.",
            "Effect on Patient": "↓ HR.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Heart block, asthma.",
            "Adjuvants": "Anesthetics.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Requires redosing."
        },
        "Amiodarone": {
            "Mechanism of Action": "K⁺, Na⁺, Ca²⁺ blocker + beta blockade.",
            "Indications for Use": "VT, VF, Afib.",
            "Effect on Patient": "Stabilizes rhythm.",
            "Adverse Reactions": "Pulmonary fibrosis, thyroid dysfunction.",
            "Situations to Avoid": "Bradycardia, iodine allergy.",
            "Adjuvants": "Beta blockers.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "May need dose adjustment."
        },
        "Sotalol": {
            "Mechanism of Action": "K⁺ blocker + beta blockade.",
            "Indications for Use": "Afib, VT.",
            "Effect on Patient": "Slows rate, prolongs QT.",
            "Adverse Reactions": "Torsades, bradycardia.",
            "Situations to Avoid": "QT prolongation.",
            "Adjuvants": "Monitor QT & renal.",
            "Use": "Outpatient.",
            "Potency": "Moderate-high.",
            "CPB/CNS Considerations": "QT risk post-CPB."
        },
        "Dronedarone": {
            "Mechanism of Action": "K⁺, Na⁺, Ca²⁺ blocker + mild anti-adrenergic.",
            "Indications for Use": "Non-permanent Afib.",
            "Effect on Patient": "Maintains NSR.",
            "Adverse Reactions": "Liver toxicity, HF.",
            "Situations to Avoid": "HF, permanent AF.",
            "Adjuvants": "Avoid CYP3A4 inhibitors.",
            "Use": "Outpatient.",
            "Potency": "Lower than amiodarone.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Promethazine": {
            "Mechanism of Action": "H₁ & weak D₂ antagonist.",
            "Indications for Use": "PONV, motion sickness.",
            "Effect on Patient": "↓ nausea, sedation.",
            "Adverse Reactions": "Sedation, hypotension.",
            "Situations to Avoid": "Children <2, elderly.",
            "Adjuvants": "Potentiates opioids.",
            "Use": "Pre-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Verapamil": {
            "Mechanism of Action": "L-type Ca²⁺ blocker.",
            "Indications for Use": "SVT, Afib, angina.",
            "Effect on Patient": "↓ HR, vasodilation.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "HF, AV block.",
            "Adjuvants": "None.",
            "Use": "Rarely intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hypotension risk."
        },
        "Diltiazem": {
            "Mechanism of Action": "Ca²⁺ blocker.",
            "Indications for Use": "Rate control, angina, HTN.",
            "Effect on Patient": "↓ HR & SVR.",
            "Adverse Reactions": "Bradycardia, edema.",
            "Situations to Avoid": "CHF, hypotension.",
            "Adjuvants": "Anticoagulation.",
            "Use": "Pre-/post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Additive hypotension."
        },
        "Adenosine": {
            "Mechanism of Action": "A1 receptor agonist.",
            "Indications for Use": "SVT.",
            "Effect on Patient": "Transient AV block.",
            "Adverse Reactions": "Flushing, chest pain.",
            "Situations to Avoid": "Asthma.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Digoxin": {
            "Mechanism of Action": "Inhibits Na⁺/K⁺ ATPase → ↑ Ca²⁺.",
            "Indications for Use": "Rate control, HF.",
            "Effect on Patient": "↓ HR, ↑ contractility.",
            "Adverse Reactions": "Toxicity.",
            "Situations to Avoid": "Renal failure, hypokalemia.",
            "Adjuvants": "Monitor electrolytes.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "↓ clearance."
        },
        "Magnesium Sulfate": {
            "Mechanism of Action": "Stabilizes myocardium.",
            "Indications for Use": "Torsades, hypomagnesemia.",
            "Effect on Patient": "↓ ventricular irritability.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Hypermagnesemia.",
            "Adjuvants": "Electrolytes.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "In prime or intra-op."
        },
        "Insulin (Regular)": {
            "Mechanism of Action": "Facilitates glucose & K⁺ uptake.",
            "Indications for Use": "Hyperglycemia, hyperkalemia.",
            "Effect on Patient": "↓ glucose & K⁺.",
            "Adverse Reactions": "Hypoglycemia.",
            "Situations to Avoid": "Hypoglycemia.",
            "Adjuvants": "Dextrose.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ sensitivity post-CPB."
        },
        "Dextrose 50% (D50)": {
            "Mechanism of Action": "Provides glucose.",
            "Indications for Use": "Hypoglycemia.",
            "Effect on Patient": "↑ glucose.",
            "Adverse Reactions": "Phlebitis.",
            "Situations to Avoid": "Hyperglycemia.",
            "Adjuvants": "Insulin, glucagon.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Useful post-CPB."
        },
        "Glucagon": {
            "Mechanism of Action": "Glycogenolysis & gluconeogenesis.",
            "Indications for Use": "Hypoglycemia, β-blocker overdose.",
            "Effect on Patient": "↑ glucose & HR.",
            "Adverse Reactions": "Nausea, hyperglycemia.",
            "Situations to Avoid": "Pheochromocytoma.",
            "Adjuvants": "Calcium, glucose.",
            "Use": "Emergency.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Useful post-CPB."
        },
        "Vitamin K (Phytonadione)": {
            "Mechanism of Action": "Restores clotting factor activation.",
            "Indications for Use": "Warfarin reversal.",
            "Effect on Patient": "Corrects INR.",
            "Adverse Reactions": "Rare anaphylaxis.",
            "Situations to Avoid": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "4-Factor PCC (Kcentra)": {
            "Mechanism of Action": "Replaces clotting factors II, VII, IX, X.",
            "Indications for Use": "Rapid INR reversal.",
            "Effect on Patient": "Restores coagulation.",
            "Adverse Reactions": "Thrombosis.",
            "Situations to Avoid": "Active thrombosis.",
            "Use": "Emergency.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "FFP (Fresh Frozen Plasma)": {
            "Mechanism of Action": "Replaces clotting factors.",
            "Indications for Use": "Coagulopathy.",
            "Effect on Patient": "Replaces clotting.",
            "Adverse Reactions": "TRALI, TACO.",
            "Situations to Avoid": "Volume overload.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Flecainide": {
            "Mechanism of Action": "Strong Na⁺ blocker.",
            "Indications for Use": "Afib, SVT.",
            "Effect on Patient": "Slows atrial arrhythmias.",
            "Adverse Reactions": "Blurred vision, pro-arrhythmia.",
            "Situations to Avoid": "Structural heart disease, MI.",
            "Adjuvants": "Beta blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Propafenone": {
            "Mechanism of Action": "Na⁺ blocker + mild beta blockade.",
            "Indications for Use": "Atrial arrhythmias.",
            "Effect on Patient": "Rhythm control.",
            "Adverse Reactions": "Metallic taste, bronchospasm.",
            "Situations to Avoid": "Asthma, HF.",
            "Adjuvants": "AV nodal blockers.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Metoprolol": {
            "Mechanism of Action": "Beta-1 blocker.",
            "Indications for Use": "Afib, HTN, post-MI.",
            "Effect on Patient": "↓ HR, ↓ O₂ demand.",
            "Adverse Reactions": "Bradycardia, fatigue.",
            "Situations to Avoid": "Heart block, decompensated HF.",
            "Adjuvants": "Amiodarone, digoxin.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "May be held."
        },
        "Esmolol": {
            "Mechanism of Action": "Short-acting beta-1 blocker.",
            "Indications for Use": "Acute rate control.",
            "Effect on Patient": "↓ HR.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Heart block, asthma.",
            "Adjuvants": "Anesthetics.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Requires redosing."
        },
        "Amiodarone": {
            "Mechanism of Action": "K⁺, Na⁺, Ca²⁺ blocker + beta blockade.",
            "Indications for Use": "VT, VF, Afib.",
            "Effect on Patient": "Stabilizes rhythm.",
            "Adverse Reactions": "Pulmonary fibrosis, thyroid dysfunction.",
            "Situations to Avoid": "Bradycardia, iodine allergy.",
            "Adjuvants": "Beta blockers.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "May need dose adjustment."
        },
        "Sotalol": {
            "Mechanism of Action": "K⁺ blocker + beta blockade.",
            "Indications for Use": "Afib, VT.",
            "Effect on Patient": "Slows rate, prolongs QT.",
            "Adverse Reactions": "Torsades, bradycardia.",
            "Situations to Avoid": "QT prolongation.",
            "Adjuvants": "Monitor QT & renal.",
            "Use": "Outpatient.",
            "Potency": "Moderate-high.",
            "CPB/CNS Considerations": "QT risk post-CPB."
        },
        "Dronedarone": {
            "Mechanism of Action": "K⁺, Na⁺, Ca²⁺ blocker + mild anti-adrenergic.",
            "Indications for Use": "Non-permanent Afib.",
            "Effect on Patient": "Maintains NSR.",
            "Adverse Reactions": "Liver toxicity, HF.",
            "Situations to Avoid": "HF, permanent AF.",
            "Adjuvants": "Avoid CYP3A4 inhibitors.",
            "Use": "Outpatient.",
            "Potency": "Lower than amiodarone.",
            "CPB/CNS Considerations": "Not used intra-op."
        },
        "Verapamil": {
            "Mechanism of Action": "L-type Ca²⁺ blocker.",
            "Indications for Use": "SVT, Afib, angina.",
            "Effect on Patient": "↓ HR, vasodilation.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "HF, AV block.",
            "Adjuvants": "None.",
            "Use": "Rarely intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Hypotension risk."
        },
        "Diltiazem": {
            "Mechanism of Action": "Ca²⁺ blocker.",
            "Indications for Use": "Rate control, angina, HTN.",
            "Effect on Patient": "↓ HR & SVR.",
            "Adverse Reactions": "Bradycardia, edema.",
            "Situations to Avoid": "CHF, hypotension.",
            "Adjuvants": "Anticoagulation.",
            "Use": "Pre-/post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Additive hypotension."
        },
        "Adenosine": {
            "Mechanism of Action": "A1 receptor agonist.",
            "Indications for Use": "SVT.",
            "Effect on Patient": "Transient AV block.",
            "Adverse Reactions": "Flushing, chest pain.",
            "Situations to Avoid": "Asthma.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Digoxin": {
            "Mechanism of Action": "Inhibits Na⁺/K⁺ ATPase → ↑ Ca²⁺.",
            "Indications for Use": "Rate control, HF.",
            "Effect on Patient": "↓ HR, ↑ contractility.",
            "Adverse Reactions": "Toxicity.",
            "Situations to Avoid": "Renal failure, hypokalemia.",
            "Adjuvants": "Monitor electrolytes.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "↓ clearance."
        },
        "Magnesium Sulfate": {
            "Mechanism of Action": "Stabilizes myocardium.",
            "Indications for Use": "Torsades, hypomagnesemia.",
            "Effect on Patient": "↓ ventricular irritability.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Hypermagnesemia.",
            "Adjuvants": "Electrolytes.",
            "Use": "All phases.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "In prime or intra-op."
        },
        "Insulin (Regular)": {
            "Mechanism of Action": "Facilitates glucose & K⁺ uptake.",
            "Indications for Use": "Hyperglycemia, hyperkalemia.",
            "Effect on Patient": "↓ glucose & K⁺.",
            "Adverse Reactions": "Hypoglycemia.",
            "Situations to Avoid": "Hypoglycemia.",
            "Adjuvants": "Dextrose.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "↑ sensitivity post-CPB."
        },
        "Dextrose 50% (D50)": {
            "Mechanism of Action": "Provides glucose.",
            "Indications for Use": "Hypoglycemia.",
            "Effect on Patient": "↑ glucose.",
            "Adverse Reactions": "Phlebitis.",
            "Situations to Avoid": "Hyperglycemia.",
            "Adjuvants": "Insulin, glucagon.",
            "Use": "All phases.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Useful post-CPB."
        },
        "Glucagon": {
            "Mechanism of Action": "Glycogenolysis & gluconeogenesis.",
            "Indications for Use": "Hypoglycemia, β-blocker overdose.",
            "Effect on Patient": "↑ glucose & HR.",
            "Adverse Reactions": "Nausea, hyperglycemia.",
            "Situations to Avoid": "Pheochromocytoma.",
            "Adjuvants": "Calcium, glucose.",
            "Use": "Emergency.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Useful post-CPB."
        },
        "Vitamin K (Phytonadione)": {
            "Mechanism of Action": "Restores clotting factor activation.",
            "Indications for Use": "Warfarin reversal.",
            "Effect on Patient": "Corrects INR.",
            "Adverse Reactions": "Rare anaphylaxis.",
            "Situations to Avoid": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "4-Factor PCC (Kcentra)": {
            "Mechanism of Action": "Replaces clotting factors II, VII, IX, X.",
            "Indications for Use": "Rapid INR reversal.",
            "Effect on Patient": "Restores coagulation.",
            "Adverse Reactions": "Thrombosis.",
            "Situations to Avoid": "Active thrombosis.",
            "Use": "Emergency.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "FFP (Fresh Frozen Plasma)": {
            "Mechanism of Action": "Replaces clotting factors.",
            "Indications for Use": "Coagulopathy.",
            "Effect on Patient": "Replaces clotting.",
            "Adverse Reactions": "TRALI, TACO.",
            "Situations to Avoid": "Volume overload.",
            "Adjuvants": "None.",
            "Use": "Post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Edoxaban": {
            "Mechanism of Action": "Factor Xa inhibitor.",
            "Indications for Use": "VTE, AF.",
            "Effect on Patient": "Anticoagulation.",
            "Adverse Reactions": "Bleeding.",
            "Situations to Avoid": "Active bleeding, renal failure.",
            "Adjuvants": "None.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Typically withheld perioperatively."
        },
        "Betrixaban": {
            "Mechanism of Action": "Factor Xa inhibitor.",
            "Indications for Use": "VTE prophylaxis.",
            "Effect on Patient": "Anticoagulation.",
            "Adverse Reactions": "Bleeding.",
            "Situations to Avoid": "Active bleeding.",
            "Adjuvants": "None.",
            "Use": "Outpatient.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Typically withheld perioperatively."
        },
        "Tranexamic Acid (TXA)": {
            "Mechanism of Action": "Inhibits fibrinolysis by blocking plasminogen.",
            "Indications for Use": "Reduce bleeding.",
            "Effect on Patient": "↓ bleeding, ↓ transfusion.",
            "Adverse Reactions": "Seizures, thrombosis.",
            "Situations to Avoid": "Active thrombosis.",
            "Adjuvants": "Standard coagulation.",
            "Use": "Pre-, intra-, post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Often added to prime."
        },
        "Epsilon-Aminocaproic Acid (EACA)": {
            "Mechanism of Action": "Inhibits fibrinolysis.",
            "Indications for Use": "Reduce bleeding.",
            "Effect on Patient": "↓ bleeding.",
            "Adverse Reactions": "Hypotension, thrombosis.",
            "Situations to Avoid": "Active thrombosis.",
            "Adjuvants": "None.",
            "Use": "Pre-, intra-, post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Often added to prime."
        },
        "Prostacyclin (Epoprostenol)": {
            "Mechanism of Action": "PGI₂ analogue → vasodilation, platelet inhibition.",
            "Indications for Use": "Circuit thrombosis prevention.",
            "Effect on Patient": "↓ platelet aggregation, vasodilation.",
            "Adverse Reactions": "Hypotension.",
            "Situations to Avoid": "Hypotension.",
            "Adjuvants": "None.",
            "Use": "Intra-op (ECMO/CPB).",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Administered in circuit."
        },
        "Nitroglycerin": {
            "Mechanism of Action": "NO donor → venodilation.",
            "Indications for Use": "Myocardial ischemia, hypertension.",
            "Effect on Patient": "↓ preload & mild afterload.",
            "Adverse Reactions": "Hypotension, headache.",
            "Situations to Avoid": "Severe hypotension.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "None."
        },
        "Nitroprusside": {
            "Mechanism of Action": "NO donor → potent vasodilation.",
            "Indications for Use": "Hypertensive crisis.",
            "Effect on Patient": "↓ afterload.",
            "Adverse Reactions": "Cyanide toxicity.",
            "Situations to Avoid": "Prolonged use, renal failure.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "None."
        },
        "Vasopressin": {
            "Mechanism of Action": "V1 receptor agonist.",
            "Indications for Use": "Vasoplegia.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Ischemia.",
            "Situations to Avoid": "None specific.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Effective post-CPB."
        },
        "Phenylephrine": {
            "Mechanism of Action": "Alpha agonist → vasoconstriction.",
            "Indications for Use": "Hypotension.",
            "Effect on Patient": "↑ SVR, ↑ MAP.",
            "Adverse Reactions": "Reflex bradycardia.",
            "Situations to Avoid": "Severe vasoconstriction.",
            "Adjuvants": "None.",
            "Use": "Intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Common intra-op."
        },
        "Norepinephrine": {
            "Mechanism of Action": "Alpha > beta agonist.",
            "Indications for Use": "Shock, low SVR.",
            "Effect on Patient": "↑ MAP, mild ↑ CO.",
            "Adverse Reactions": "Arrhythmias.",
            "Situations to Avoid": "None specific.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Common post-CPB."
        },
        "Epinephrine": {
            "Mechanism of Action": "Beta > alpha agonist.",
            "Indications for Use": "Cardiac arrest, shock.",
            "Effect on Patient": "↑ HR, ↑ CO.",
            "Adverse Reactions": "Arrhythmias, hyperglycemia.",
            "Situations to Avoid": "None specific.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Common post-CPB."
        },
        "Milrinone": {
            "Mechanism of Action": "PDE-3 inhibitor → ↑ cAMP.",
            "Indications for Use": "Low CO, RV failure.",
            "Effect on Patient": "↑ CO, ↓ PVR.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Situations to Avoid": "Hypotension.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Common post-CPB."
        },
        "Levosimendan": {
            "Mechanism of Action": "Calcium sensitizer + PDE inhibition.",
            "Indications for Use": "Low output states.",
            "Effect on Patient": "↑ contractility.",
            "Adverse Reactions": "Hypotension, arrhythmias.",
            "Situations to Avoid": "Hypotension.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "Moderate-high.",
            "CPB/CNS Considerations": "Not widely available in US."
        },
        "Calcium Chloride": {
            "Mechanism of Action": "Replenishes ionized calcium.",
            "Indications for Use": "Hypocalcemia, myocardial depression.",
            "Effect on Patient": "↑ contractility.",
            "Adverse Reactions": "Arrhythmias if rapid.",
            "Situations to Avoid": "Hypercalcemia.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Essential post-CPB."
        },
        "Calcium Gluconate": {
            "Mechanism of Action": "Same as above.",
            "Indications for Use": "Hypocalcemia.",
            "Effect on Patient": "↑ contractility.",
            "Adverse Reactions": "Less irritating than chloride.",
            "Situations to Avoid": "Hypercalcemia.",
            "Adjuvants": "None.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Same as chloride."
        },
        "Mannitol": {
            "Mechanism of Action": "Osmotic diuretic.",
            "Indications for Use": "Renal protection, cerebral edema.",
            "Effect on Patient": "↑ urine output.",
            "Adverse Reactions": "Fluid shifts.",
            "Situations to Avoid": "Anuria.",
            "Adjuvants": "None.",
            "Use": "In prime/intra-op.",
            "Potency": "Moderate.",
            "CPB/CNS Considerations": "Often added to prime."
        },
        "Heparin": {
            "Mechanism of Action": "Potentiates antithrombin.",
            "Indications for Use": "Anticoagulation on CPB.",
            "Effect on Patient": "Prevents clotting.",
            "Adverse Reactions": "HIT, bleeding.",
            "Situations to Avoid": "HIT.",
            "Adjuvants": "None.",
            "Use": "Pre-/intra-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Essential."
        },
        "Protamine": {
            "Mechanism of Action": "Neutralizes heparin.",
            "Indications for Use": "Reverse heparin post-CPB.",
            "Effect on Patient": "Restores clotting.",
            "Adverse Reactions": "Hypotension, anaphylaxis.",
            "Situations to Avoid": "Fish allergy, prior reaction.",
            "Adjuvants": "None.",
            "Use": "Post-CPB.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Essential."
        },
        "Methylene Blue": {
            "Mechanism of Action": "Inhibits NO-cGMP pathway.",
            "Indications for Use": "Vasoplegia.",
            "Effect on Patient": "↑ SVR.",
            "Adverse Reactions": "Serotonin syndrome, blue urine.",
            "Situations to Avoid": "SSRIs.",
            "Adjuvants": "Vasopressors.",
            "Use": "Intra-/post-op.",
            "Potency": "High.",
            "CPB/CNS Considerations": "Useful post-CPB."
        }
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
    elif len(compare) == 1:
        st.info("Select a second drug to compare.")
