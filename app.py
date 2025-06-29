import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

# ========== Streamlit Config ==========
st.set_page_config(page_title="Sarathy Estimate Tool", layout="centered")

# ========== PDF Extractor: Auto Detect Format ==========
def extract_parts_from_pdf(uploaded_file):
    parts = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # 🧾 Try TABLE FORMAT (bill-style)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 5:
                        continue
                    part_number = str(row[1]).strip() if row[1] else ''
                    description = str(row[2]).strip() if row[2] else ''
                    rate = str(row[3]).strip()
                    qty = str(row[4]).strip()

                    if not re.match(r'^[A-Z0-9\-]{6,}$', part_number):
                        continue
                    try:
                        rate = float(rate)
                        qty = float(qty)
                        amount = round(rate * qty, 2)
                        parts.append({
                            'Part Number': part_number,
                            'Description': description,
                            'Amount': amount
                        })
                    except:
                        continue

            # ✏️ If nothing found, try TEXT FORMAT (estimate-style)
            if not parts:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split('\n'):
                    tokens = line.strip().split()
                    if len(tokens) >= 3:
                        try:
                            part_number = tokens[0]
                            amount = float(tokens[-1].replace(',', '').replace('₹', ''))
                            description = ' '.join(tokens[1:-1])
                            if re.match(r'^[A-Z0-9\-]{6,}$', part_number):
                                parts.append({
                                    'Part Number': part_number,
                                    'Description': description,
                                    'Amount': amount
                                })
                        except:
                            continue

    df = pd.DataFrame(parts)
    return df.drop_duplicates(subset="Part Number")

# ========== Status Logic ==========
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

# ========== Stylish Login ==========
VALID_USERNAME = "Tj.cgnr"
VALID_PASSWORD = "Sarathy123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("""
        <style>
        .login-box {
            background-color: #f9f9f9;
            padding: 30px 40px;
            border-radius: 15px;
            box-shadow: 0px 0px 15px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
            margin: auto;
            margin-top: 60px;
        }
        </style>
        <div class="login-box">
            <h2 style='text-align: center;'>🔐 Sarathy Estimate Login</h2>
            <p style='text-align: center;'>Please enter your credentials to continue</p>
        """, unsafe_allow_html=True)

    with st.form("login_form"):
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
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ========== Main App UI ==========
st.title("📄 Estimate vs Bill Comparison Tool")
st.markdown("Upload your **Initial Estimate** and **Final Bill** PDFs to compare part-wise differences.")

uploaded_est = st.file_uploader("📤 Upload Initial Estimate PDF", type="pdf")
uploaded_bill = st.file_uploader("📤 Upload Final Bill PDF", type="pdf")

if uploaded_est and uploaded_bill:
    est_df = extract_parts_from_pdf(uploaded_est)
    bill_df = extract_parts_from_pdf(uploaded_bill)

    if est_df.empty or bill_df.empty:
        st.warning("⚠️ One of the PDFs didn't contain usable part data.")
    else:
        # Merge by part number
        merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))

        # Use available description
        merged['Description'] = merged.apply(
            lambda row: row.get('Description_Bill') if pd.notna(row.get('Description_Bill')) else row.get('Description_Estimate'),
            axis=1
        )

        merged['Status'] = merged.apply(get_status, axis=1)

        # Format ₹ values
        merged['Amount_Estimate'] = merged['Amount_Estimate'].apply(
            lambda x: f"₹{x:,.2f}" if pd.notna(x) else ""
        )
        merged['Amount_Bill'] = merged['Amount_Bill'].apply(
            lambda x: f"₹{x:,.2f}" if pd.notna(x) else ""
        )

        final_df = merged[['Part Number', 'Description', 'Amount_Estimate', 'Amount_Bill', 'Status']]
        final_df.columns = ['Part Number', 'Description', 'Amount Estimate', 'Amount Final', 'Status']

        st.subheader("📊 Comparison Result")
        st.dataframe(final_df, use_container_width=True)

        # Excel download
        output = io.BytesIO()
        final_df.to_excel(output, index=False)
        st.download_button("⬇️ Download Excel", data=output.getvalue(), file_name="comparison_result.xlsx")
