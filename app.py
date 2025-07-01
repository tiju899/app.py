import streamlit as st
import pandas as pd
import pdfplumber
import fitz  # PyMuPDF fallback for OCR
import io
import re
import openpyxl
from io import BytesIO

# --- OCR FALLBACK ---
def ocr_text_from_pdf(uploaded_file):
    text = ""
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in doc:
            text += page.get_text()
    except Exception as e:
        st.error(f"OCR fallback failed: {e}")
    return text

# --- FUNCTION TO EXTRACT PARTS ---
def extract_parts_from_pdf(uploaded_file, is_bill=False):
    parts = []
    if uploaded_file is None:
        return parts

    raw_text = ""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    raw_text += page.extract_text() + "\n"
    except:
        pass

    if not raw_text.strip():
        uploaded_file.seek(0)
        raw_text = ocr_text_from_pdf(uploaded_file)

    if not raw_text.strip():
        return parts

    lines = raw_text.split("\n")
    for line in lines:
        # Match lines like: PARTNUM DESCRIPTION QTY RATE AMOUNT
        match = re.match(r"^(?P<part>[A-Z0-9\-/]{5,})\s+(?P<desc>.+?)\s+(?P<amount>[\d,]+\.\d{2})$", line.strip())
        if match:
            part_no = match.group("part").strip()
            desc = match.group("desc").strip()
            try:
                amt = float(match.group("amount").replace(",", ""))
                parts.append({
                    "Part Number": part_no,
                    "Description": desc,
                    "Amount": amt
                })
            except:
                continue
        else:
            # Try DMS or Estimate variant with multiple columns
            tokens = line.strip().split()
            if len(tokens) >= 4:
                try:
                    amt = float(tokens[-1].replace(",", ""))
                    rate = float(tokens[-2].replace(",", ""))
                    part_no = tokens[0]
                    desc = " ".join(tokens[1:-2])
                    parts.append({
                        "Part Number": part_no,
                        "Description": desc,
                        "Amount": amt
                    })
                except:
                    continue
    return parts

# --- COMPARISON FUNCTION ---
def compare_parts(est_parts, bill_parts):
    df_est = pd.DataFrame(est_parts)
    df_bill = pd.DataFrame(bill_parts)

    df_est = df_est[df_est["Amount"] > 0]
    df_bill = df_bill[df_bill["Amount"] > 0]

    if "Part Number" not in df_est.columns or "Part Number" not in df_bill.columns:
        st.error("❌ 'Part Number' column missing in one of the files. Check PDF formatting.")
        return pd.DataFrame()

    df_common = pd.merge(
        df_est.rename(columns={"Description": "Description Estimate", "Amount": "Amount Estimate"}),
        df_bill.rename(columns={"Description": "Description Bill", "Amount": "Amount Bill"}),
        how="outer",
        on="Part Number"
    )

    def determine_status(row):
        if pd.isna(row["Amount Estimate"]):
            return "🆕 New Part"
        elif pd.isna(row["Amount Bill"]):
            return "❌ Removed"
        elif row["Amount Bill"] > row["Amount Estimate"]:
            return "🔺 Increased"
        elif row["Amount Bill"] < row["Amount Estimate"]:
            return "🔻 Reduced"
        elif row["Amount Bill"] == row["Amount Estimate"]:
            return "✅ Same"
        return ""

    df_common["Status"] = df_common.apply(determine_status, axis=1)
    df_common["Amount Estimate"] = df_common["Amount Estimate"].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "–")
    df_common["Amount Bill"] = df_common["Amount Bill"].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "–")
    df_common["Description Estimate"] = df_common["Description Estimate"].fillna("*(not in estimate)*")
    df_common["Description Bill"] = df_common["Description Bill"].fillna("*(not in bill)*")

    return df_common[[
        "Part Number",
        "Description Estimate",
        "Amount Estimate",
        "Description Bill",
        "Amount Bill",
        "Status"
    ]]

# --- STREAMLIT APP UI ---
st.title("📄 Estimate vs Bill Comparison Tool")

col1, col2 = st.columns(2)
with col1:
    estimate_file = st.file_uploader("Upload Initial Estimate PDF", type="pdf")
with col2:
    bill_file = st.file_uploader("Upload Final Bill PDF", type="pdf")

if estimate_file and bill_file:
    with st.spinner("Extracting and comparing parts..."):
        est_parts = extract_parts_from_pdf(estimate_file, is_bill=False)
        bill_parts = extract_parts_from_pdf(bill_file, is_bill=True)

        if not est_parts:
            st.error("❌ Estimate PDF didn't contain usable part data.")
        elif not bill_parts:
            st.error("❌ Bill PDF didn't contain usable part data.")
        else:
            df_result = compare_parts(est_parts, bill_parts)
            st.subheader("📊 Full Part Comparison Table")
            st.dataframe(df_result, use_container_width=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False, sheet_name="Part Comparison")

            st.download_button(
                "⬇️ Download Excel",
                data=output.getvalue(),
                file_name="estimate_vs_bill_comparison.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("📎 Please upload both Estimate and Final Bill PDFs to proceed.")
