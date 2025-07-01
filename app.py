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

def is_number(s):
    """Checks if a string can be converted to a number (int or float)."""
    try:
        float(s.replace(',', ''))
        return True
    except ValueError:
        return False

# =============================================================================
# 4. Advanced PDF Extraction Functions
# =============================================================================

def extract_data_from_words(doc, doc_type):
    """
    Extracts structured data (Part Number, Description, Amount) from PDF
    using word coordinates, suitable for both Bill and Estimate formats.
    """
    all_parts = []
    
    # Define expected headers and their approximate X-coordinates for column identification
    if doc_type == 'bill':
        # Approximate X-coordinates for columns (left edge)
        col_x_ranges = {
            'srl': (20, 60), # Srl.
            'part_number': (60, 150), # Part Number
            'description': (150, 400), # Description (wide range)
            'rate': (400, 460), # Rate
            'qty': (460, 510), # Qty.
            'taxable_amount': (510, 580), # Taxable Amount (our target)
            'tax_paid_amount': (580, 650) # Tax Paid Amount
        }
        amount_col_key = 'taxable_amount'

    elif doc_type == 'estimate':
        # Approximate X-coordinates for columns (left edge)
        col_x_ranges = {
            'srl': (20, 60), # S.No.
            'part_number': (60, 150), # Part No.
            'description': (150, 350), # Part Desc. (wide range)
            'mrp': (350, 400), # MRP
            'depreciation': (400, 480), # *Depreciation %
            'quantity_total': (480, 530), # Quantity Total
            'claimed_value': (530, 600), # Claimed Value
            'approved_amount': (600, 680) # Approved Amount (our target)
        }
        amount_col_key = 'approved_amount'
    else:
        st.error(f"Unknown document type: {doc_type}")
        return []

    # Tolerance for Y-coordinates to group words into the same line
    LINE_Y_TOLERANCE = 3 # pixels

    for page_num, page in enumerate(doc):
        words = page.get_text("words") # (x0, y0, x1, y1, word, block_no, line_no, word_no)

        # Group words by line (using y0 coordinate)
        lines = {}
        for word_info in words:
            x0, y0, x1, y1, word_text, _, line_no, _ = word_info
            
            # Find the line this word belongs to
            found_line = False
            for existing_y in lines:
                if abs(y0 - existing_y) <= LINE_Y_TOLERANCE:
                    lines[existing_y].append(word_info)
                    found_line = True
                    break
            if not found_line:
                lines[y0] = [word_info]
        
        # Sort lines by Y-coordinate
        sorted_y_coords = sorted(lines.keys())

        # Process each line
        for y_coord in sorted_y_coords:
            line_words = sorted(lines[y_coord], key=lambda w: w[0]) # Sort words in line by X-coordinate

            current_part_number = None
            current_description_words = []
            current_amount = None

            # Heuristic to identify data rows:
            is_data_row = False
            potential_srl = ""
            potential_part_num = ""

            for i, word_info in enumerate(line_words):
                x0, y0, x1, y1, word_text, _, _, _ = word_info
                
                # Check for serial number in the first column
                if col_x_ranges['srl'][0] <= x0 < col_x_ranges['srl'][1]:
                    if word_text.isdigit():
                        potential_srl = word_text
                
                # Check for part number in the second column
                if col_x_ranges['part_number'][0] <= x0 < col_x_ranges['part_number'][1]:
                    if re.match(r"^[A-Z0-9\-]+$", word_text): # Typical part number format
                        potential_part_num = word_text
                        if potential_srl: # If we also found a serial number, this is likely a data row
                            is_data_row = True
                            current_part_number = potential_part_num
                            break # Found the start of a data row, process it below

            if not is_data_row or not current_part_number:
                continue # Not a data row, skip

            # Now, re-process the line to extract description and amount based on identified columns
            current_description_words = []
            current_amount_str = None

            for word_info in line_words:
                x0, y0, x1, y1, word_text, _, _, _ = word_info

                # Part Number (already identified, but ensure it's within its range)
                if col_x_ranges['part_number'][0] <= x0 < col_x_ranges['part_number'][1] and word_text == current_part_number:
                    pass # Already handled

                # Description
                elif col_x_ranges['description'][0] <= x0 < col_x_ranges['description'][1]:
                    current_description_words.append(word_text)
                
                # Amount (Taxable Amount for Bill, Approved Amount for Estimate)
                elif col_x_ranges[amount_col_key][0] <= x0 < col_x_ranges[amount_col_key][1]:
                    if is_number(word_text):
                        current_amount_str = word_text
                        
            if current_part_number and current_amount_str:
                all_parts.append({
                    'Part Number': current_part_number,
                    'Description': " ".join(current_description_words).strip(),
                    'Amount': safe_float_convert(current_amount_str)
                })
    return all_parts

def safe_extract_parts(pdf_file, doc_type):
    """
    Dispatches to the advanced PDF extraction function.
    Handles temporary file creation and cleanup.
    Also extracts raw text for debugging.
    """
    parts = []
    raw_text = ""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_file.read())
            temp_path = tmp.name
        
        doc = fitz.open(temp_path)
        
        # Extract raw text for debugging
        for page in doc:
            raw_text += page.get_text() + "\n"

        parts = extract_data_from_words(doc, doc_type)
            
        doc.close()
        return pd.DataFrame(parts), raw_text
        
    except Exception as e:
        st.error(f"PDF Processing Error for {doc_type.capitalize()}: {str(e)}")
        return pd.DataFrame(), raw_text # Return empty DF and raw text on error
    finally:
        if temp_path:
            try:
                import os
                os.unlink(temp_path)
            except OSError:
                pass

# =============================================================================
# 5. Comparison Logic (remains the same as it operates on DataFrames)
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
# 6. Display and Export Functions (remain the same)
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
    
    # Initialize raw_text variables in session state to persist across reruns
    if 'estimate_raw_text' not in st.session_state:
        st.session_state.estimate_raw_text = ""
    if 'bill_raw_text' not in st.session_state:
        st.session_state.bill_raw_text = ""

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
            estimate_df, st.session_state.estimate_raw_text = safe_extract_parts(estimate_file, 'estimate')
            if estimate_df.empty:
                st.error("Failed to extract any valid part data from the Estimate PDF. This might be due to an unexpected format or layout.")
                
            # Extract data from Bill PDF
            bill_df, st.session_state.bill_raw_text = safe_extract_parts(bill_file, 'bill')
            if bill_df.empty:
                st.error("Failed to extract any valid part data from the Bill PDF. This might be due to an unexpected format or layout.")
                
            # Debug: Show extracted raw dataframes
            with st.expander("⚙️ Debug: Raw Extracted Data (for troubleshooting)", expanded=False):
                st.subheader("Extracted Estimate Data:")
                st.dataframe(estimate_df, use_container_width=True)
                st.subheader("Extracted Bill Data:")
                st.dataframe(bill_df, use_container_width=True)

            # Only proceed with comparison if both DFs are not empty
            if not estimate_df.empty and not bill_df.empty:
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
