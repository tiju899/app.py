import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import base64
from io import BytesIO
import tempfile

# =============================================================================
# 1. App Configuration
# =============================================================================
st.set_page_config(
    page_title="Estimate vs Bill Comparison Tool",
    page_icon="📊",
    layout="wide"
)

# =============================================================================
# 2. Custom Styling
# =============================================================================
st.markdown("""
<style>
    .header {
        color: #2e86ab;
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .metric-box {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 15px;
    }
    .highlight-increase {
        color: #e63946;
        font-weight: bold;
    }
    .highlight-decrease {
        color: #2a9d8f;
        font-weight: bold;
    }
    .tab-container {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 3. Helper Functions
# =============================================================================
def safe_float_convert(value):
    """Convert string to float with error handling."""
    try:
        # Remove commas, then convert to float
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return None

# =============================================================================
# 4. Specific PDF Extraction Functions
# =============================================================================

def extract_from_bill_pdf(doc):
    """
    Extracts parts from the BILL.pdf format.
    Uses a two-step approach for robust description parsing.
    """
    parts = []
    # Pattern to find lines that start with a serial number and a part number
    # and capture the rest of the line.
    line_pattern = re.compile(r"^\s*\d+\s+(?P<part_number>[A-Z0-9\-]+)\s+(?P<rest_of_line>.*)")

    # Pattern to find the 'Taxable Amount' (the 4th float after the part number)
    # and the preceding numbers (Rate, Qty, Tax Paid Amount)
    # This pattern is applied to 'rest_of_line'
    amount_pattern = re.compile(
        r"(?:[\d,]+\.\d{2,3})\s+" +       # Rate
        r"(?:[\d,]+\.\d{2,3})\s+" +       # Qty
        r"(?:[\d,]+\.\d{2,3})\s+" +       # Tax Paid Amount
        r"(?P<amount>[\d,]+\.\d{2,3})"    # Taxable Amount (our target)
    )

    for page in doc:
        text = page.get_text()
        for line in text.split('\n'):
            line_match = line_pattern.search(line)
            if line_match:
                part_number = line_match.group('part_number').strip()
                rest_of_line = line_match.group('rest_of_line').strip()

                amount_match = amount_pattern.search(rest_of_line)
                if amount_match:
                    amount = safe_float_convert(amount_match.group('amount'))
                    # The description is everything between the part number and the first matched number sequence
                    # Find the start of the first number sequence
                    first_num_start = re.search(r"[\d,]+\.\d{2,3}", rest_of_line)
                    if first_num_start:
                        description = rest_of_line[:first_num_start.start()].strip()
                        parts.append({
                            'Part Number': part_number,
                            'Description': description,
                            'Amount': amount
                        })
    return parts

def extract_from_estimate_pdf(doc):
    """
    Extracts parts from the ESTIMATE.pdf format.
    Uses a two-step approach for robust description parsing.
    """
    parts = []
    # Pattern to find lines that start with S.No., Part No.
    # and capture the rest of the line.
    line_pattern = re.compile(r"^\s*\d+\s+(?P<part_number>[A-Z0-9\-]+)\s+(?P<rest_of_line>.*)")

    # Pattern to find the 'Approved Amount' (the last float before 'Replace'/'Repair Allow')
    # and the preceding numbers (MRP, Depreciation %, Quantity Total, Claimed Value)
    # This pattern is applied to 'rest_of_line'
    amount_pattern = re.compile(
        r"(?:[\d,]+\.\d{2,3}|\d+)\s+" +   # MRP
        r"(?:[\d,]+\.\d{2,3}|\d+)\s+" +   # *Depreciation %
        r"(?:[\d,]+\.\d{2,3}|\d+)\s+" +   # Quantity Total
        r"(?:[\d,]+\.\d{2,3}|\d+)\s+" +   # Claimed Value
        r"(?P<amount>[\d,]+\.\d{2,3}|\d+)\s+" + # Approved Amount (our target)
        r"(?:Replace|Repair Allow)"       # Service Type
    )

    for page in doc:
        text = page.get_text()
        for line in text.split('\n'):
            line_match = line_pattern.search(line)
            if line_match:
                part_number = line_match.group('part_number').strip()
                rest_of_line = line_match.group('rest_of_line').strip()

                amount_match = amount_pattern.search(rest_of_line)
                if amount_match:
                    amount = safe_float_convert(amount_match.group('amount'))
                    # The description is everything between the part number and the first matched number sequence
                    # Find the start of the first number sequence
                    first_num_start = re.search(r"[\d,]+\.\d{2,3}|\d+", rest_of_line)
                    if first_num_start:
                        description = rest_of_line[:first_num_start.start()].strip()
                        parts.append({
                            'Part Number': part_number,
                            'Description': description,
                            'Amount': amount
                        })
    return parts

def safe_extract_parts(pdf_file, doc_type):
    """
    Dispatches to the correct PDF extraction function based on document type.
    Handles temporary file creation and cleanup.
    """
    parts = []
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_file.read())
            temp_path = tmp.name
        
        doc = fitz.open(temp_path)
        
        if doc_type == 'estimate':
            parts = extract_from_estimate_pdf(doc)
        elif doc_type == 'bill':
            parts = extract_from_bill_pdf(doc)
        else:
            st.error("Invalid document type specified for extraction.")
            return pd.DataFrame()
            
        doc.close()
        return pd.DataFrame(parts)
        
    except Exception as e:
        st.error(f"PDF Processing Error for {doc_type.capitalize()}: {str(e)}")
        return pd.DataFrame()
    finally:
        if temp_path:
            try:
                import os
                os.unlink(temp_path)
            except OSError:
                # Handle case where file might already be deleted or inaccessible
                pass

# =============================================================================
# 5. Comparison Logic
# =============================================================================
def safe_comparison(estimate_df, bill_df):
    """
    Performs a safe comparison between estimate and bill DataFrames.
    Identifies increased, reduced, new, and removed parts.
    """
    results = {
        'increased': pd.DataFrame(),
        'reduced': pd.DataFrame(),
        'new': pd.DataFrame(),
        'removed': pd.DataFrame()
    }
    
    try:
        if estimate_df.empty and bill_df.empty:
            return results
        if estimate_df.empty: # All bill items are 'new' if estimate is empty
            results['new'] = bill_df.copy().rename(columns={'Amount': 'Amount_bill'})
            return results
        if bill_df.empty: # All estimate items are 'removed' if bill is empty
            results['removed'] = estimate_df.copy().rename(columns={'Amount': 'Amount_estimate'})
            return results
            
        # Standardize column names (strip whitespace)
        estimate_df = estimate_df.rename(columns=lambda x: x.strip())
        bill_df = bill_df.rename(columns=lambda x: x.strip())
        
        # Ensure required columns exist
        required_cols = ['Part Number', 'Description', 'Amount']
        for col in required_cols:
            if col not in estimate_df.columns:
                st.error(f"Estimate DataFrame missing required column: '{col}'")
                return results
            if col not in bill_df.columns:
                st.error(f"Bill DataFrame missing required column: '{col}'")
                return results
                
        # Set 'Part Number' as index for merging
        estimate_df = estimate_df.set_index('Part Number')
        bill_df = bill_df.set_index('Part Number')
        
        # Rename 'Amount' columns to distinguish them after merge
        bill_df = bill_df.rename(columns={'Amount': 'Amount_bill', 'Description': 'Description_bill'})
        estimate_df = estimate_df.rename(columns={'Amount': 'Amount_estimate', 'Description': 'Description_estimate'})
        
        # Perform an outer merge to capture all items from both DataFrames
        merged_df = bill_df.merge(
            estimate_df,
            how='outer',
            left_index=True,
            right_index=True,
            suffixes=('_bill', '_estimate'), # This suffix is now redundant due to explicit renaming
            indicator=True # Adds a column indicating merge source
        )
        
        # Ensure 'Amount_bill' and 'Amount_estimate' columns exist after merge
        # Fill NaN values with 0 for numerical comparisons
        merged_df['Amount_bill'] = merged_df['Amount_bill'].fillna(0)
        merged_df['Amount_estimate'] = merged_df['Amount_estimate'].fillna(0)

        # Identify increased, reduced, new, and removed items
        increased_mask = (
            (merged_df['Amount_bill'] > merged_df['Amount_estimate']) &
            (merged_df['_merge'] == 'both')
        )
        reduced_mask = (
            (merged_df['Amount_bill'] < merged_df['Amount_estimate']) &
            (merged_df['_merge'] == 'both')
        )
        new_mask = (merged_df['_merge'] == 'left_only') # In bill, not in estimate
        removed_mask = (merged_df['_merge'] == 'right_only') # In estimate, not in bill

        # Populate results dictionary
        if not merged_df[increased_mask].empty:
            results['increased'] = merged_df[increased_mask].copy()
            results['increased'] = results['increased'][['Description_bill', 'Amount_bill', 'Amount_estimate']]
            results['increased'].columns = ['Description', 'Bill Amount', 'Estimate Amount']

        if not merged_df[reduced_mask].empty:
            results['reduced'] = merged_df[reduced_mask].copy()
            results['reduced'] = results['reduced'][['Description_bill', 'Amount_bill', 'Amount_estimate']]
            results['reduced'].columns = ['Description', 'Bill Amount', 'Estimate Amount']

        if not merged_df[new_mask].empty:
            results['new'] = merged_df[new_mask].copy()
            results['new'] = results['new'][['Description_bill', 'Amount_bill']]
            results['new'].columns = ['Description', 'Bill Amount']

        if not merged_df[removed_mask].empty:
            results['removed'] = merged_df[removed_mask].copy()
            results['removed'] = results['removed'][['Description_estimate', 'Amount_estimate']]
            results['removed'].columns = ['Description', 'Estimate Amount']

    except Exception as e:
        st.error(f"Comparison Logic Error: {str(e)}")
        # Return empty dataframes on error to prevent further issues
        return {k: pd.DataFrame() for k in results}
        
    return results

# =============================================================================
# 6. Display and Export Functions
# =============================================================================
def format_dataframe(df):
    """Applies consistent formatting to DataFrames for display."""
    if df.empty:
        return df
        
    # Apply comma formatting to numeric columns
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
            
    return df

def create_excel_download(comparison_result):
    """Generates an Excel file with all comparison sheets for download."""
    output = BytesIO()
    try:
        # Check if there's any data to write to Excel
        has_data = False
        for name, df in comparison_result.items():
            if not df.empty:
                has_data = True
                break
        
        if not has_data:
            # st.warning("No comparison data to export to Excel.") # Already handled by main()
            return None

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for name, df in comparison_result.items():
                if not df.empty:
                    # Reset index to include 'Part Number' as a column in Excel
                    df_to_export = df.reset_index()
                    df_to_export.to_excel(writer, sheet_name=name.capitalize(), index=False)
                    
        output.seek(0)
        b64 = base64.b64encode(output.read()).decode()
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="Estimate_vs_Bill_Comparison_Report.xlsx">📥 Download Full Report (Excel)</a>'
    except Exception as e:
        st.error(f"Excel Generation Error: {str(e)}")
        return None

# =============================================================================
# 7. Main Application Logic
# =============================================================================
def main():
    st.markdown('<div class="header">Estimate vs Bill Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown("Upload your Estimate and Bill PDFs to compare part numbers, descriptions, and amounts.")
    
    with st.expander("📁 Upload Documents", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            estimate_file = st.file_uploader("Upload Estimate PDF", type=["pdf"], key="estimate_uploader")
        with col2:
            bill_file = st.file_uploader("Upload Bill PDF", type=["pdf"], key="bill_uploader")
    
    if st.button("🔍 Compare Documents", use_container_width=True, type="primary"):
        if estimate_file is None or bill_file is None:
            st.warning("Please upload both Estimate and Bill PDF documents to proceed.")
            return
            
        with st.spinner("Processing documents and performing comparison..."):
            # Extract data from Estimate PDF
            estimate_df = safe_extract_parts(estimate_file, 'estimate')
            if estimate_df.empty:
                st.error("Failed to extract any valid part data from the Estimate PDF. Please ensure it matches the expected format.")
                return
                
            # Extract data from Bill PDF
            bill_df = safe_extract_parts(bill_file, 'bill')
            if bill_df.empty:
                st.error("Failed to extract any valid part data from the Bill PDF. Please ensure it matches the expected format.")
                return
                
            # Debug: Show extracted raw dataframes
            with st.expander("⚙️ Debug: Raw Extracted Data (for troubleshooting)", expanded=False):
                st.subheader("Extracted Estimate Data:")
                st.dataframe(estimate_df, use_container_width=True)
                st.subheader("Extracted Bill Data:")
                st.dataframe(bill_df, use_container_width=True)
                
            # Perform the comparison
            comparison_result = safe_comparison(estimate_df, bill_df)
            
            st.success("Comparison completed successfully!")
            st.markdown("---")
            
            # Display summary metrics
            metric_cols = st.columns(4)
            metrics = [
                ("🔺 Increased", len(comparison_result['increased']), "#e63946"),
                ("🔻 Reduced", len(comparison_result['reduced']), "#2a9d8f"),
                ("🆕 New", len(comparison_result['new']), "#1d3557"),
                ("❌ Removed", len(comparison_result['removed']), "#6c757d")
            ]
            
            for idx, (label, value, color) in enumerate(metrics):
                with metric_cols[idx]:
                    st.markdown(
                        f"""
                        <div class="metric-box">
                            <div style="font-size:24px;color:{color};">{label}</div>
                            <div style="font-size:28px;font-weight:bold;color:{color};">{value}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            
            # Display detailed comparison results in tabs
            st.markdown("---")
            with st.expander("📊 Detailed Comparison Results", expanded=True):
                tabs_labels = [tab[0] for tab in metrics]
                tabs_keys = ['increased', 'reduced', 'new', 'removed']
                
                tabs = st.tabs(tabs_labels)
                
                for i, tab in enumerate(tabs):
                    with tab:
                        df = comparison_result[tabs_keys[i]]
                        if not df.empty:
                            st.dataframe(
                                format_dataframe(df),
                                use_container_width=True,
                                height=400
                            )
                        else:
                            st.info(f"No {tabs_keys[i].replace('_', ' ')} parts found in this category.")
            
            # Excel download link
            st.markdown("---")
            download_link = create_excel_download(comparison_result)
            if download_link:
                st.markdown(download_link, unsafe_allow_html=True)
            else:
                st.info("No data available to generate an Excel report.")

if __name__ == "__main__":
    main()
