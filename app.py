import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import pdfplumber
import os

def extract_parts_from_pdf(pdf_path):
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')
            for line in lines:
                if any(char.isdigit() for char in line) and len(line.split()) >= 3:
                    tokens = line.split()
                    try:
                        part_number = tokens[0]
                        amount = float(tokens[-1].replace(',', ''))
                        desc = ' '.join(tokens[1:-1])
                        parts.append({'Part Number': part_number, 'Description': desc, 'Amount': amount})
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

    merged['Status'] = merged.apply(get_status, axis=1)
    merged.to_excel(save_path, index=False)
    return save_path

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
    messagebox.showinfo("Done", f"Comparison complete.\nFile saved to:\n{save_path}")

# GUI
root = tk.Tk()
root.title("EstimateComparer - Offline")
root.geometry("400x200")

tk.Label(root, text="EstimateComparer Tool", font=("Helvetica", 14, "bold")).pack(pady=20)
tk.Button(root, text="Start Comparison", command=select_files, width=25, height=2, bg="#4CAF50", fg="white").pack(pady=10)
tk.Label(root, text="Made for Sarathy | Offline Version").pack(side="bottom", pady=10)

root.mainloop()
