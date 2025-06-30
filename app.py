import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd

def extract_parts_from_pdf(uploaded_file, source="bill"):
    parts = []

    if uploaded_file is None:
        return parts

    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in doc:
            text = page.get_text("text")
            lines = text.split("\n")

            for line in lines:
                match = re.search(
                    r"(?P<part>[A-Z0-9\-]{5,})\s+(?P<desc>.+?)\s+(?P<rate>[\d,]+\.\d{2})\s+(?P<qty>\d+\.\d{3})",
                    line
                )
                if match:
                    part_no = match.group("part").strip()
                    desc = match.group("desc").strip()
                    try:
                        rate = float(match.group("rate").replace(",", ""))
                        qty = float(match.group("qty"))
                        amt = round(rate * qty, 2)
                        parts.append({
                            "Part Number": part_no,
                            "Part Description": desc,
                            f"Amount in {source.capitalize()}": amt
                        })
                    except:
                        continue
    except Exception as e:
        st.error(f"❌ Failed to parse {source} PDF: {e}")

    return parts

def compare_bill_vs_estimate(bill_file, estimate_file):
    bill_parts = extract_parts_from_pdf(bill_file, source="bill")
    estimate_parts = extract_parts_from_pdf(estimate_file, source="estimate")

    df_bill = pd.DataFrame(bill_parts)
    df_estimate = pd.DataFrame(estimate_parts)

    df_merged = pd.merge(
        df_estimate,
        df_bill,
        on="Part Number",
        how="outer",
        suffixes=("_Estimate", "_Bill")
    )

    df_merged["Part Description"] = df_merged["Part Description_Estimate"].combine_first(df_merged["Part Description_Bill"])
    df_merged.drop(columns=["Part Description_Estimate", "Part Description_Bill"], inplace=True)

    df_merged["Estimate No"] = "ES25000088"
    df_merged["Bill No"] = "4/BI/25000304"

    df_final = df_merged[[
        "Estimate No", "Bill No", "Part Number", "Part Description",
        "Amount in Estimate", "Amount in Bill"
    ]]

    df_final["Status"] = df_final.apply(lambda row: (
        "Only in Estimate" if pd.isna(row["Amount in Bill"]) else
        "Only in Bill" if pd.isna(row["Amount in Estimate"]) else
        "Match" if abs(row["Amount in Bill"] - row["Amount in Estimate"]) < 1e-2 else
        "Mismatch"
    ), axis=1)

    return df_final

# --- STREAMLIT UI ---
st.title("🔍 Bill vs Estimate PDF Comparator")

bill_file = st.file_uploader("Upload BILL PDF", type=["pdf"])
estimate_file = st.file_uploader("Upload ESTIMATE PDF", type=["pdf"])

if bill_file and estimate_file:
    df_result = compare_bill_vs_estimate(bill_file, estimate_file)
    st.success("✅ Comparison Complete")
    st.dataframe(df_result)

    # Export option
    excel = df_result.to_excel(index=False)
    st.download_button("📥 Download Excel", data=excel, file_name="Estimate_vs_Bill_Comparison.xlsx")
