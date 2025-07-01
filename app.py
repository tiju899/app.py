# 🧾 Extract parts
est_df = extract_parts_from_pdf(uploaded_est)
bill_df = extract_parts_from_pdf(uploaded_bill)

if est_df.empty or bill_df.empty:
    st.warning("One of the PDFs didn't contain usable data.")
else:
    # Merge using part number
    merged = pd.merge(est_df, bill_df, on="Part Number", how="outer", suffixes=('_Estimate', '_Bill'))

    # Merge descriptions smartly
    def pick_description(row):
        if pd.notna(row['Description_Bill']):
            return row['Description_Bill']
        elif pd.notna(row['Description_Estimate']):
            return row['Description_Estimate']
        return ""

    merged['Description'] = merged.apply(pick_description, axis=1)

    # Determine status
    def get_status(row):
        if pd.isna(row['Amount_Estimate']):
            return '🆕 New Part'
        elif pd.isna(row['Amount_Bill']):
            return '❌ Removed'
        elif row['Amount_Bill'] > row['Amount_Estimate']:
            return '🔺 Increased'
        elif row['Amount_Bill'] < row['Amount_Estimate']:
            return '🔻 Reduced'
        else:
            return '✅ Same'

    merged['Status'] = merged.apply(get_status, axis=1)

    # Format output table
    merged['Amount_Estimate'] = merged['Amount_Estimate'].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "")
    merged['Amount_Bill'] = merged['Amount_Bill'].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "")

    final_df = merged[['Part Number', 'Description', 'Amount_Estimate', 'Amount_Bill', 'Status']]
    final_df.columns = ['Part Number', 'Description', 'Amount Estimate', 'Amount Final', 'Status']

    # Show results
    st.subheader("📊 Comparison Result")
    st.dataframe(final_df, use_container_width=True)

    # Excel export
    output = io.BytesIO()
    final_df.to_excel(output, index=False)
    st.download_button("⬇️ Download as Excel", data=output.getvalue(), file_name="comparison_result.xlsx")
