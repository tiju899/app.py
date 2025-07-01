import pandas as pd
import fitz  # PyMuPDF
import io
import re
from io import BytesIO

# NOTE: This version does not use streamlit, for environments where streamlit is not available

# --- OCR text extraction ---
def extract_text_from_pdf(uploaded_file):
    text = ""
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in doc:
            text += page.get_text()
    except Exception as e:
        print(f"OCR failed: {e}")
    return text

# --- Extract parts from Estimate PDF (inclusive of tax) ---
def extract_estimate_parts(text):
    parts = []
    lines = text.splitlines()
    for line in lines:
        match = re.search(r"\b([A-Z0-9]{6,})\b\s+(.*?)\s+(\d+[.]?\d*)\s+\d\s+\d\s+(\d+[.]?\d*)", line)
        if match:
            part_no = match.group(1)
            desc = match.group(2).strip()
            amt = float(match.group(4))
            parts.append({
                "Part Number": part_no,
                "Description": desc,
                "Amount": amt
            })
    return parts

# --- Extract parts from Bill PDF (exclusive of tax) ---
def extract_bill_parts(text):
    parts = []
    lines = text.splitlines()
    for line in lines:
        match = re.search(r"\b([A-Z0-9]{6,})\b\s+(.*?)\s+(\d+[.]\d{2})\s+[\d.]+\s+[\d.]+\s+(\d+[.]\d{2})", line)
        if match:
            part_no = match.group(1)
            desc = match.group(2).strip()
            amt = float(match.group(4))
            parts.append({
                "Part Number": part_no,
                "Description": desc,
                "Amount": amt
            })
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

# --- Console CLI Runner ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python compare_parts.py <estimate.pdf> <bill.pdf>")
        sys.exit(1)

    estimate_path = sys.argv[1]
    bill_path = sys.argv[2]

    with open(estimate_path, "rb") as f:
        est_text = extract_text_from_pdf(f)

    with open(bill_path, "rb") as f:
        bill_text = extract_text_from_pdf(f)

    est_parts = extract_estimate_parts(est_text)
    bill_parts = extract_bill_parts(bill_text)

    if not est_parts:
        print("❌ Estimate PDF didn't contain usable part data.")
    elif not bill_parts:
        print("❌ Bill PDF didn't contain usable part data.")
    else:
        est_no = estimate_path
        bill_no = bill_path
        result_df = compare_parts(est_parts, bill_parts, est_no, bill_no)

        print("✅ Comparison completed!")
        print(result_df.to_string(index=False))

        output_file = "Estimate_vs_Bill.xlsx"
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            result_df.to_excel(writer, index=False, sheet_name="Comparison")

        print(f"Excel file saved: {output_file}")
