# app.py
import streamlit as st
import pandas as pd
import pdfplumber
import io

st.set_page_config(page_title="Estimate Comparison Tool", layout="centered")
st.title("🧾 Estimate Comparison Tool")

st.markdown("Upload **Initial Estimate** and **Final Bill** PDFs to compare part costs.")

# Function to extract parts
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

# File uploads
uploaded_est = st.file_uploader("📄 Upload Initial Estimate PDF", type="pdf")
uploaded_bill = st.file_uploader("📄 Upload Final Bill PDF", type="pdf")

if uploaded_est and uploaded_bill:
    est_df = extract_parts_from_pdf(uploaded_est)
    bill_df = extract_parts_from_pdf(uploaded_bill)

    merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))

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

    merged['Status'] = merged.apply(get_status, axis=1)
    st.subheader("📊 Comparison Result")
    st.dataframe(merged)

    output = io.BytesIO()
    merged.to_excel(output, index=False)
    st.download_button("⬇️ Download Excel", data=output.getvalue(), file_name="comparison_result.xlsx")
streamlit
pandas
pdfplumber
openpyxl
