import streamlit as st
import pandas as pd
import pdfplumber
import io

# Set credentials
VALID_USERNAME = "Tj.cgnr"
VALID_PASSWORD = "Sarathy123"

# Session state login check
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Login screen
if not st.session_state.logged_in:
    st.title("🔐 Login to EstimateComparer")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful!")
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

# Main app starts here after login
st.set_page_config(page_title="Estimate Comparison Tool", layout="centered")
st.title("🧾 Estimate Comparison Tool")
st.markdown("Upload **Initial Estimate** and **Final Bill** PDFs to compare part costs.")

# (Rest of your existing code goes here below this line...)
