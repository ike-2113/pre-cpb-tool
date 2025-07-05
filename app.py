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
    pass

# ---- Drug Library Section ----
if tool == "Drug Library":
    st.title("Drug Library")
    st.markdown("Search for a drug below or select two to compare.")

    # Use the global drug_data dictionary (should be defined once, above this section, with all info included)
    drug_names = list(drug_data.keys())

    # --- Searchable Drug List ---
    search = st.text_input("Search or filter drugs:")
    filtered = [d for d in drug_names if search.lower() in d.lower()] if search else drug_names

    selected_drug = st.selectbox("Select a drug to view details:", filtered)
    if selected_drug:
        st.subheader(selected_drug)
        for k, v in drug_data[selected_drug].items():
            st.write(f"**{k}:** {v}")

    st.markdown("---")
    st.markdown("### Compare Drugs")
    compare_search = st.text_input("Search drugs to compare:", key="compare_search")
    compare_filtered = [d for d in drug_names if compare_search.lower() in d.lower()] if compare_search else drug_names
    compare = st.multiselect("Select up to 2 drugs to compare:", compare_filtered, max_selections=2)
    if len(compare) == 2:
        st.write(f"#### {compare[0]} vs {compare[1]}")
        col1, col2 = st.columns(2)
        for key in sorted(set(drug_data[compare[0]].keys()).union(drug_data[compare[1]].keys())):
            with col1:
                st.write(f"**{key}:** {drug_data[compare[0]].get(key, '-')}")
            with col2:
                st.write(f"**{key}:** {drug_data[compare[1]].get(key, '-')}")
    st.stop()
