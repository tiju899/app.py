import streamlit as st
import pandas as pd
import pdfplumber
import io

# 🔧 1. Define functions at the top
def extract_parts_from_pdf(uploaded_file):
    parts = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                tokens = line.split()
                if len(tokens) >= 3:
                    try:
                        part_number = tokens[0]
                        amount = float(tokens[-1].replace(',', '').replace('₹', ''))
                        description = ' '.join(tokens[1:-1])
                        parts.append({
                            'Part Number': part_number,
                            'Description': description,
                            'Amount': amount
                        })
                    except:
                        continue
    return pd.DataFrame(parts)

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

# 🔐 2. Login logic
VALID_USERNAME = "Tj.cgnr"
VALID_PASSWORD = "Sarathy123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login to EstimateComparer")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful!")
        else:
            st.error("Invalid username or password.")
    st.stop()

# 🧾 3. Main app starts after login
st.set_page_config(page_title="Estimate Comparison Tool", layout="centered")
st.title("🧾 Estimate Comparison Tool")
st.markdown("Upload **Initial Estimate** and **Final Bill** PDFs to compare part costs.")

uploaded_est = st.file_uploader("📄 Upload Initial Estimate PDF", type="pdf")
uploaded_bill = st.file_uploader("📄 Upload Final Bill PDF", type="pdf")

if uploaded_est and uploaded_bill:
    est_df = extract_parts_from_pdf(uploaded_est)
    bill_df = extract_parts_from_pdf(uploaded_bill)

    merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))
    merged['Status'] = merged.apply(get_status, axis=1)

    st.subheader("📊 Comparison Result")
    st.dataframe(merged)

    output = io.BytesIO()
    merged.to_excel(output, index=False)
    st.download_button("⬇️ Download Excel", data=output.getvalue(), file_name="comparison_result.xlsx")
