import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

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
                st.success("✅ Login successful! Please click below to continue.")
                st.button("Continue")
            else:
                st.error("❌ Invalid username or password")
    st.stop()

# --- FUNCTION TO EXTRACT PARTS ---
def extract_parts_from_pdf(uploaded_file):
    parts = []
    if uploaded_file is None:
        return parts

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    row = [cell.strip() if cell else "" for cell in row]
                    if len(row) >= 5:
                        part_no = row[0]
                        desc = row[1]
                        rate = row[2].replace(",", "")
                        qty = row[3].replace(",", "")
                        try:
                            rate_val = float(rate)
                            qty_val = float(qty)
                            amt = round(rate_val * qty_val, 2)
                        except:
                            continue

                        if re.match(r"^[A-Z0-9]{5,}$", part_no):
                            parts.append({
                                "Part Number": part_no,
                                "Description": desc,
                                "Amount": amt
                            })
            else:
                # Fallback to line-based matching
                words = page.extract_words(x_tolerance=1, y_tolerance=1)
                line_texts = {}
                for word in words:
                    y0 = round(word["top"], 1)
                    if y0 not in line_texts:
                        line_texts[y0] = []
                    line_texts[y0].append(word["text"])

                for y0 in sorted(line_texts):
                    line = " ".join(line_texts[y0])
                    match = re.match(r"^([A-Z]{3,5}[0-9]{5,}|[0-9]{5,}[A-Z]{2,})\s+(.*?)(?:\s+\u20b9|\s+Rs|\s+INR)?\s*([0-9,]+\.\d{2})?", line)
                    if match:
                        number = match.group(1).strip()
                        desc = match.group(2).strip()
                        amt = match.group(3)
                        try:
                            amt = float(amt.replace(",", "")) if amt else 0.0
                        except:
                            amt = 0.0
                        parts.append({"Part Number": number, "Description": desc, "Amount": amt})

    return parts

# --- COMPARISON FUNCTION ---
def compare_parts(est_parts, bill_parts):
    df_est = pd.DataFrame(est_parts)
    df_bill = pd.DataFrame(bill_parts)

    df = pd.merge(df_est, df_bill, on="Part Number", how="outer", suffixes=(" Estimate", " Final"))
    df["Amount Estimate"] = df["Amount Estimate"].fillna(0)
    df["Amount Final"] = df["Amount Final"].fillna(0)

    def determine_status(row):
        if row["Amount Estimate"] == 0 and row["Amount Final"] > 0:
            return "🆕 New Part"
        elif row["Amount Estimate"] > 0 and row["Amount Final"] == 0:
            return "❌ Removed"
        elif row["Amount Final"] > row["Amount Estimate"]:
            return "🔺 Increased"
        elif row["Amount Final"] < row["Amount Estimate"]:
            return "🔻 Reduced"
        elif row["Amount Final"] == row["Amount Estimate"] and row["Amount Final"] != 0:
            return "✅ Same"
        else:
            return ""

    df["Status"] = df.apply(determine_status, axis=1)

    # Format Amount columns
    for col in ["Amount Estimate", "Amount Final"]:
        df[col] = df[col].apply(lambda x: f"₹{float(x):,.2f}" if pd.notna(x) and isinstance(x, (int, float)) else "")

    return df

# --- STREAMLIT APP UI ---
st.title("📄 Estimate vs Bill Comparison Tool")

col1, col2 = st.columns(2)
with col1:
    estimate_file = st.file_uploader("Upload Initial Estimate PDF", type="pdf")
with col2:
    bill_file = st.file_uploader("Upload Final Bill PDF", type="pdf")

if estimate_file and bill_file:
    with st.spinner("Extracting and comparing parts..."):
        est_parts = extract_parts_from_pdf(estimate_file)
        bill_parts = extract_parts_from_pdf(bill_file)

        if not est_parts and not bill_parts:
            st.warning("⚠️ One of the PDFs didn't contain usable part data.")
        else:
            result_df = compare_parts(est_parts, bill_parts)

            st.subheader("📊 Comparison Result")
            st.dataframe(result_df, use_container_width=True)

            # Download
            csv = result_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Excel", data=csv, file_name="estimate_vs_bill_comparison.csv", mime="text/csv")

else:
    st.info("📎 Please upload both Estimate and Final Bill PDFs to proceed.")
