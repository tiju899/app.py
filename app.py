import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

# ========== CONFIG ==========
st.set_page_config(page_title="Estimate Comparison Tool", layout="centered")

# ========== FUNCTION: Extract parts from PDF ==========
def extract_parts_from_pdf(uploaded_file):
    parts = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line or len(line.split()) < 3:
                    continue

                if any(keyword in line.lower() for keyword in [
                    "gst", "cgst", "sgst", "total", "net", "round", "tax",
                    "estimation", "print", "amount", "liability", "mileage", 
                    "insurer", "signatory", "recommendation", "engine", "chassis"
                ]):
                    continue

                match = re.match(r'^([A-Z0-9\-]{6,})\s+(.*\s)?(\d{2,6}\.\d{2})$', line)
                if match:
                    part_number = match.group(1)
                    description = match.group(2).strip() if match.group(2) else ""
                    amount = float(match.group(3))
                    parts.append({
                        'Part Number': part_number,
                        'Description': description,
                        'Amount': amount
                    })
    return pd.DataFrame(parts)

# ========== FUNCTION: Status Logic ==========
def get_status(row):
    if pd.isna(row['Amount_Estimate']):
        return '🆕 New Part'
    elif pd.isna(row['Amount_Bill']):
        return '❌ Removed'
    elif row['Amount_Bill'] > row['Amount_Estimate']:
        return '🔺 Increased'
    elif row['Amount_Bill'] < row['Amount_Estimate']:
        return '🔻 Reduced'
    else:
        return '✅ Same'

# ========== LOGIN ==========
VALID_USERNAME = "Tj.cgnr"
VALID_PASSWORD = "Sarathy123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown(
        """
        <div style="text-align: center;">
            <h2>🔐 Welcome to Sarathy Estimate Tool</h2>
            <p style="font-size:16px;">Please login to access the system</p>
        </div>
        """, unsafe_allow_html=True
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

        if login_btn:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.success("✅ Login successful!")
                st.experimental_rerun()
            else:
                st.error("❌ Invalid username or password")
    st.stop()

# ========== MAIN APP ==========
st.title("📄 Estimate vs Bill Comparison")
st.markdown("Upload both PDFs to compare the estimated and final billed parts.")

uploaded_est = st.file_uploader("📤 Upload Initial Estimate PDF", type="pdf")
uploaded_bill = st.file_uploader("📤 Upload Final Bill PDF", type="pdf")

if uploaded_est and uploaded_bill:
    est_df = extract_parts_from_pdf(uploaded_est)
    bill_df = extract_parts_from_pdf(uploaded_bill)

    if est_df.empty or bill_df.empty:
        st.warning("One of the PDFs didn't contain usable data.")
    else:
        # Add serial columns
        est_df.insert(0, "Estimate No.", range(1, len(est_df) + 1))
        bill_df.insert(0, "Bill No.", range(1, len(bill_df) + 1))

        # Merge on part number
        merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))
        merged['Status'] = merged.apply(get_status, axis=1)

        # Reorder columns
        final_df = merged[
            ['Part Number', 'Estimate No.', 'Description_Estimate', 'Amount_Estimate',
             'Bill No.', 'Description_Bill', 'Amount_Bill', 'Status']
        ]

        st.subheader("📊 Comparison Result")
        st.dataframe(final_df, use_container_width=True)

        # Download button
        output = io.BytesIO()
        final_df.to_excel(output, index=False)
        st.download_button("⬇️ Download as Excel", data=output.getvalue(), file_name="comparison_result.xlsx")
