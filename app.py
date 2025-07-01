import streamlit as st
import pandas as pd
import pdfplumber
import fitz  # PyMuPDF
import io
import re
from io import BytesIO

st.set_page_config(page_title="Estimate vs Bill Comparison Tool", layout="centered")

# --- OCR fallback ---
def ocr_text_from_pdf(uploaded_file):
    text = ""
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in doc:
            text += page.get_text()
    except Exception as e:
        st.error(f"OCR fallback failed: {e}")
    return text

# --- Extract parts from PDF ---
def extract_parts_from_pdf(uploaded_file):
    parts = []
    if not uploaded_file:
        return parts

    text = ""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except:
        uploaded_file.seek(0)
        text = ocr_text_from_pdf(uploaded_file)

    if not text.strip():
        return parts

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        tokens = re.split(r'\s{2,}', line)
        if len(tokens) >= 2:
            try:
                amount = float(tokens[-1].replace(",", "").replace("₹", ""))
                desc = " ".join(tokens[1:-1])
                part = tokens[0]
                # Filter out invalid part numbers (like JC25000962, Sub, SGST etc)
                if re.match(r"^[A-Z0-9\-]{6,}$", part):
                    parts.append({
                        "Part Number": part,
                        "Description": desc,
                        "Amount": amount
                    })
            except:
                continue
    return parts

# --- Compare Estimates vs Bill ---
def compare_parts(est_parts, bill_parts, est_no, bill_no):
    df_est = pd.DataFrame(est_parts)
    df_bill = pd.DataFrame(bill_parts)

    if df_est.empty or df_bill.empty:
        return pd.DataFrame()

    df_est = df_est[df_est["Amount"] > 0]
    df_bill = df_bill[df_bill["Amount"] > 0]

    df_est.rename(columns={"Description": "Description Estimate", "Amount": "Amount Estimate"}, inplace=True)
    df_bill.rename(columns={"Description": "Description Bill", "Amount": "Amount Bill"}, inplace=True)

    df_merged = pd.merge(df_est, df_bill, on="Part Number", how="outer")

    def get_status(row):
        if pd.isna(row["Amount Estimate"]):
            return "🆕 New Part"
        elif pd.isna(row["Amount Bill"]):
            return "❌ Removed"
        elif row["Amount Bill"] > row["Amount Estimate"]:
            return "🔺 Increased"
        elif row["Amount Bill"] < row["Amount Estimate"]:
            return "🔻 Reduced"
        else:
            return "✅ Same"

    df_merged["Status"] = df_merged.apply(get_status, axis=1)
    df_merged["Estimate No"] = est_no
    df_merged["Bill No"] = bill_no

    # Format money
    df_merged["Amount Estimate"] = df_merged["Amount Estimate"].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "–")
    df_merged["Amount Bill"] = df_merged["Amount Bill"].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "–")
    df_merged["Description Estimate"] = df_merged["Description Estimate"].fillna("*(not in estimate)*")
    df_merged["Description Bill"] = df_merged["Description Bill"].fillna("*(not in bill)*")

    return df_merged[[
        "Estimate No",
        "Bill No",
        "Part Number",
        "Description Estimate",
        "Amount Estimate",
        "Description Bill",
        "Amount Bill",
        "Status"
    ]]

# --- UI ---
st.title("📊 Estimate vs Final Bill – Part Comparison")

col1, col2 = st.columns(2)
with col1:
    est_file = st.file_uploader("📎 Upload Estimate PDF", type="pdf", key="est")
with col2:
    bill_file = st.file_uploader("📎 Upload Final Bill PDF", type="pdf", key="bill")

if est_file and bill_file:
    with st.spinner("🔍 Extracting parts and comparing..."):
        est_parts = extract_parts_from_pdf(est_file)
        bill_parts = extract_parts_from_pdf(bill_file)

        if not est_parts:
            st.error("❌ Estimate PDF didn't contain usable part data.")
        elif not bill_parts:
            st.error("❌ Bill PDF didn't contain usable part data.")
        else:
            est_no = est_file.name
            bill_no = bill_file.name
            result_df = compare_parts(est_parts, bill_parts, est_no, bill_no)

            st.success("✅ Comparison completed!")
            st.dataframe(result_df, use_container_width=True)

            # Download Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False, sheet_name="Comparison")

            st.download_button(
                "⬇️ Download Excel",
                data=output.getvalue(),
                file_name="Estimate_vs_Bill.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("📁 Please upload both Estimate and Bill PDFs to begin.")
