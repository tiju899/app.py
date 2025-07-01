import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import pdfplumber
import os

# Credentials
USERNAME = "Tj.cgnr"
PASSWORD = "Sarathy123"

# ==============================
# PDF Extractor and Comparator
# ==============================

def extract_parts_from_pdf(pdf_path):
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                tokens = line.strip().split()
                if len(tokens) >= 3 and any(char.isdigit() for char in tokens[0]):
                    try:
                        part_number = tokens[0]
                        amount = float(tokens[-1].replace(',', '').replace('₹', ''))
                        description = ' '.join(tokens[1:-1])
                        parts.append({
                            "Part Number": part_number,
                            "Description": description,
                            "Amount": amount
                        })
                    except:
                        continue
    return pd.DataFrame(parts)

def compare_and_export(est_df, bill_df, save_path):
    merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))

    def get_status(row):
        if pd.isna(row['Amount_Estimate']):
            return 'New Part'
        elif pd.isna(row['Amount_Bill']):
            return 'Removed Part'
        elif row['Amount_Bill'] > row['Amount_Estimate']:
            return 'Increased'
        elif row['Amount_Bill'] < row['Amount_Estimate']:
            return 'Reduced'
        else:
            return 'Same'

    merged["Status"] = merged.apply(get_status, axis=1)
    merged.to_excel(save_path, index=False)
    return save_path

# ============================
# File Selection and Compare
# ============================

def select_files():
    estimate_path = filedialog.askopenfilename(title="Select Initial Estimate PDF")
    if not estimate_path:
        return
    bill_path = filedialog.askopenfilename(title="Select Final Bill PDF")
    if not bill_path:
        return

    est_df = extract_parts_from_pdf(estimate_path)
    bill_df = extract_parts_from_pdf(bill_path)

    if est_df.empty or bill_df.empty:
        messagebox.showerror("Error", "Failed to extract parts from one or both PDFs.")
        return

    save_path = os.path.join(os.path.dirname(estimate_path), "comparison_result.xlsx")
    compare_and_export(est_df, bill_df, save_path)
    messagebox.showinfo("Success", f"Comparison complete!\nSaved to:\n{save_path}")

# ======================
# Login Screen Function
# ======================

def login():
    user = username_entry.get()
    pwd = password_entry.get()
    if user == USERNAME and pwd == PASSWORD:
        login_window.destroy()
        launch_main_app()
    else:
        messagebox.showerror("Login Failed", "Incorrect username or password.")

# ======================
# Main App Window
# ======================

def launch_main_app():
    main_app = tk.Tk()
    main_app.title("EstimateComparer - Offline")
    main_app.geometry("400x200")

    tk.Label(main_app, text="EstimateComparer Tool", font=("Helvetica", 14, "bold")).pack(pady=20)
    tk.Button(main_app, text="Start Comparison", command=select_files, width=25, height=2, bg="#4CAF50", fg="white").pack(pady=10)
    tk.Label(main_app, text="Made for Sarathy | Offline Version").pack(side="bottom", pady=10)

    main_app.mainloop()

# ==================
# Login GUI Setup
# ==================

login_window = tk.Tk()
login_window.title("Login - EstimateComparer")
login_window.geometry("300x200")

tk.Label(login_window, text="Username").pack(pady=5)
username_entry = tk.Entry(login_window)
username_entry.pack()

tk.Label(login_window, text="Password").pack(pady=5)
password_entry = tk.Entry(login_window, show="*")
password_entry.pack()

tk.Button(login_window, text="Login", command=login, bg="#2E86C1", fg="white", width=15).pack(pady=20)
login_window.mainloop()
