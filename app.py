import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import openpyxl
from io import BytesIO

# --- LOGIN SETTINGS ---
VALID_USERNAME = "Tj.cgnr"
VALID_PASSWORD = "Sarathy123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login to Sarathy Estimate Tool")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

        if login_btn:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.success("✅ Login successful!")
            else:
                st.error("❌ Invalid username or password")
    st.stop()

# --- DEBUGGING FUNCTION TO EXTRACT PARTS ---
def extract_parts_from_pdf(uploaded_file, is_bill=False):
    parts = []
    if uploaded_file is None:
        return parts

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    st.warning(f"⚠️ Page {page_num+1}: No text extracted.")
                    continue
                lines = text.split("\n")
                for line in lines:
                    pattern = r"(?P<part>[A-Z0-9\-]{5,})?\s+(?P<desc>.+?)\s+(?P<rate>[\d,]+\.\d{2})\s+(?P<qty>\d+\.\d{3})(?:\s+(?P<tax>\d{1,2})%)?"
                    match = re.search(pattern, line)

                    if match:
                        part_no = match.group("part") or f"NO-ID-{len(parts)+1}"
                        desc = match.group("desc").strip()
                        try:
                            rate = float(match.group("rate").replace(",", ""))
                            qty = float(match.group("qty"))
                            tax = float(match.group("tax")) / 100 if is_bill and match.group("tax") else 0
                            amt = round(rate * qty * (1 + tax), 2) if is_bill else round(rate * qty, 2)

                            parts.append({
                                "Part Number": part_no.strip(),
                                "Description": desc,
                                "Amount": amt,
                                "Line Number": len(parts) + 1
                            })
                        except:
                            continue
    except Exception as e:
        st.error(f"❌ PDF parse failed: {e}")

    return parts

# --- COMPARISON FUNCTION ---
def compare_parts(est_parts, bill_parts):
    df_est = pd.DataFrame(est_parts)
    df_bill = pd.DataFrame(bill_parts)

    df_est = df_est[df_est["Amount"] > 0]
    df_bill = df_bill[df_bill["Amount"] > 0]

    df_common = pd.merge(
        df_est,
        df_bill,
        how="inner",
        on="Part Number",
        suffixes=(" Estimate", " Bill")
    )

    df_common["Amount Estimate"] = df_common["Amount Estimate"].fillna(0)
    df_common["Amount Bill"] = df_common["Amount Bill"].fillna(0)

    def determine_status(row):
        if row["Amount Bill"] > row["Amount Estimate"]:
            return "🔺 Increased"
        elif row["Amount Bill"] < row["Amount Estimate"]:
            return "🔻 Reduced"
        elif row["Amount Bill"] == row["Amount Estimate"]:
            return "✅ Same"
        else:
            return ""

    df_common["Status"] = df_common.apply(determine_status, axis=1)

    for col in ["Amount Estimate", "Amount Bill"]:
        df_common[col] = df_common[col].apply(lambda x: f"₹{float(x):,.2f}" if pd.notna(x) and isinstance(x, (int, float)) else "")

    df_common = df_common.rename(columns={
        "Line Number Estimate": "Estimate No",
        "Line Number Bill": "Bill No",
        "Part Number": "Part Number",
        "Description Estimate": "Part Description",
        "Amount Estimate": "Amount in Estimate",
        "Amount Bill": "Amount in Bill"
    })

    output_columns = [
        "Estimate No",
        "Bill No",
        "Part Number",
        "Part Description",
        "Amount in Estimate",
        "Amount in Bill",
        "Status"
    ]

    for col in output_columns:
        if col not in df_common.columns:
            df_common[col] = ""

    # New Parts
    df_new = df_bill[~df_bill["Part Number"].isin(df_est["Part Number"])]
    df_new["Estimate No"] = ""
    df_new["Bill No"] = df_new["Line Number"]
    df_new["Part Description"] = df_new["Description"]
    df_new["Amount in Estimate"] = ""
    df_new["Amount in Bill"] = df_new["Amount"].apply(lambda x: f"₹{float(x):,.2f}")
    df_new["Status"] = "🆕 New Part"
    df_new = df_new[output_columns]

    # Removed Parts
    df_removed = df_est[~df_est["Part Number"].isin(df_bill["Part Number"])]
    df_removed["Estimate No"] = df_removed["Line Number"]
    df_removed["Bill No"] = ""
    df_removed["Part Description"] = df_removed["Description"]
    df_removed["Amount in Estimate"] = df_removed["Amount"].apply(lambda x: f"₹{float(x):,.2f}")
    df_removed["Amount in Bill"] = ""
    df_removed["Status"] = "❌ Removed"
    df_removed = df_removed[output_columns]

    return df_common[output_columns], df_new, df_removed

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
            df_main, df_new, df_removed = compare_parts(est_parts, bill_parts)

            st.subheader("📊 Matched Parts Comparison")
            st.dataframe(df_main, use_container_width=True)

            if not df_new.empty:
                st.subheader("🆕 New Parts (only in Bill)")
                st.dataframe(df_new, use_container_width=True)

            if not df_removed.empty:
                st.subheader("❌ Removed Parts (only in Estimate)")
                st.dataframe(df_removed, use_container_width=True)

            all_rows = pd.concat([df_main, df_new, df_removed])

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_main.to_excel(writer, index=False, sheet_name="Matched")
                df_new.to_excel(writer, index=False, sheet_name="New Parts")
                df_removed.to_excel(writer, index=False, sheet_name="Removed Parts")

            st.download_button(
                "⬇️ Download Excel",
                data=output.getvalue(),
                file_name="estimate_vs_bill_comparison.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("📎 Please upload both Estimate and Final Bill PDFs to proceed.")
