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
                st.success("✅ Login successful!")
            else:
                st.error("❌ Invalid username or password")
    st.stop()

# --- FUNCTION TO EXTRACT PARTS ---
def extract_parts_from_pdf(uploaded_file):
    parts = []
    if uploaded_file is None:
        return parts

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split("\n")
                for line in lines:
                    # Match: optional part no, description, rate, qty
                    match = re.search(
                        r"(?P<part>[A-Z0-9\-]{5,})?\s+(?P<desc>.+?)\s+(?P<rate>[\d,]+\.\d{2})\s+(?P<qty>\d+\.\d{3})",
                        line
                    )
                    if match:
                        part_no = match.group("part").strip() if match.group("part") else f"NO-ID-{len(parts)+1}"
                        desc = match.group("desc").strip()
                        try:
                            rate = float(match.group("rate").replace(",", ""))
                            qty = float(match.group("qty"))
                            amt = round(rate * qty, 2)
                            parts.append({
                                "Part Number": part_no,
                                "Description": desc,
                                "Amount": amt
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

    df = pd.merge(
        df_est,
        df_bill,
        how="outer",
        on="Part Number",
        suffixes=(" Estimate", " Final")
    )

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

        if not est_parts:
            st.error("❌ Estimate PDF didn't contain usable part data.")
        elif not bill_parts:
            st.error("❌ Bill PDF didn't contain usable part data.")
        else:
            result_df = compare_parts(est_parts, bill_parts)

            st.subheader("📊 Comparison Result")
            st.dataframe(result_df, use_container_width=True)

            csv = result_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Excel", data=csv, file_name="estimate_vs_bill_comparison.csv", mime="text/csv")

else:
    st.info("📎 Please upload both Estimate and Final Bill PDFs to proceed.")
