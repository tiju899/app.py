import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
from io import BytesIO

# ------------------- Extract Parts Function -------------------
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
                # Normalize whitespace
                line = re.sub(r"\s{2,}", " ", line.strip())

                # Debug: Print parsed lines (optional)
                # st.write(line)

                # Match lines like: PARTNO DESC 1234.00 2.000
                match = re.match(
                    r"(?P<part>[A-Z0-9\-]{5,})\s+(?P<desc>.+?)\s+(?P<rate>\d[\d,]*\.\d{2})\s+(?P<qty>\d+\.\d{3})",
                    line
                )

                if match:
                    try:
                        part_no = match.group("part").strip()
                        desc = match.group("desc").strip()
                        rate = float(match.group("rate").replace(",", ""))
                        qty = float(match.group("qty"))
                        amount = round(rate * qty, 2)

                        parts.append({
                            "Part Number": part_no,
                            "Part Description": desc,
                            f"Amount in {source.capitalize()}": amount
                        })
                    except Exception as e:
                        continue  # Skip bad lines
    except Exception as e:
        st.error(f"❌ Failed to parse {source.upper()} PDF: {e}")

    return parts

# ------------------- Comparison Logic -------------------
def compare_bill_vs_estimate(bill_file, estimate_file):
    bill_parts = extract_parts_from_pdf(bill_file, source="bill")
    estimate_parts = extract_parts_from_pdf(estimate_file, source="estimate")

    df_bill = pd.DataFrame(bill_parts)
    df_estimate = pd.DataFrame(estimate_parts)

    # Protect against empty cases
    if df_estimate.empty:
        df_estimate = pd.DataFrame(columns=["Part Number", "Part Description", "Amount in Estimate"])
    if df_bill.empty:
        df_bill = pd.DataFrame(columns=["Part Number", "Part Description", "Amount in Bill"])

    # Merge
    df = pd.merge(
        df_estimate,
        df_bill,
        on="Part Number",
        how="outer",
        suffixes=("_Estimate", "_Bill")
    )

    # Merge descriptions
    df["Part Description"] = df["Part Description_Estimate"].combine_first(df["Part Description_Bill"])
    df.drop(columns=["Part Description_Estimate", "Part Description_Bill"], inplace=True, errors='ignore')

    # Add fixed identifiers
    df["Estimate No"] = "ES25000088"
    df["Bill No"] = "4/BI/25000304"

    # Rearranged columns
    df_final = df[[
        "Estimate No", "Bill No", "Part Number", "Part Description",
        "Amount in Estimate", "Amount in Bill"
    ]]

    # Add comparison status
    df_final["Status"] = df_final.apply(lambda row: (
        "Only in Estimate" if pd.isna(row["Amount in Bill"]) else
        "Only in Bill" if pd.isna(row["Amount in Estimate"]) else
        "Match" if abs(row["Amount in Bill"] - row["Amount in Estimate"]) < 0.01 else
        "Mismatch"
    ), axis=1)

    return df_final

# ------------------- Streamlit UI -------------------
st.set_page_config(page_title="Bill vs Estimate Comparator", layout="wide")
st.title("📄 Bill vs Estimate Comparator")

col1, col2 = st.columns(2)
with col1:
    bill_file = st.file_uploader("📥 Upload BILL PDF", type=["pdf"])
with col2:
    estimate_file = st.file_uploader("📥 Upload ESTIMATE PDF", type=["pdf"])

if bill_file and estimate_file:
    df_result = compare_bill_vs_estimate(bill_file, estimate_file)

    if not df_result.empty:
        st.success("✅ Comparison Complete")
        st.dataframe(df_result, use_container_width=True)

        # Downloadable Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_result.to_excel(writer, index=False, sheet_name="Comparison")
        output.seek(0)

        st.download_button(
            label="📥 Download Excel Report",
            data=output,
            file_name="Estimate_vs_Bill_Comparison.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ No matching part data found in the PDFs.")
else:
    st.info("📝 Please upload both BILL and ESTIMATE PDFs to continue.")
