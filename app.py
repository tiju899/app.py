import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import base64
from io import BytesIO
import tempfile

# App Configuration
st.set_page_config(
    page_title="Estimate vs Bill Comparison Tool",
    page_icon="📊",
    layout="wide"
)

# ===== Custom Styling =====
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

# ===== PDF Processing Functions =====
def safe_extract_parts(pdf_file):
    """Safely extract parts from PDF with enhanced error handling"""
    parts = []
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_file.read())
            temp_path = tmp.name
        
        doc = fitz.open(temp_path)
        
        for page in doc:
            text = page.get_text()
            # Improved regex pattern for robustness
            matches = re.finditer(
                r'(?P<part_number>[A-Z0-9\-]+)\s+(?P<description>.+?)\s+(?P<amount>[\d,]+\.\d{2})',
                text,
                re.DOTALL
            )
            for match in matches:
                part = {
                    'Part Number': match.group('part_number').strip(),
                    'Description': match.group('description').strip(),
                    'Amount': safe_float_convert(match.group('amount'))
                }
                if part['Amount'] is not None:
                    parts.append(part)
        
        doc.close()
        return pd.DataFrame(parts)
        
    except Exception as e:
        st.error(f"PDF Processing Error: {str(e)}")
        return pd.DataFrame()
    finally:
        if temp_path:
            try:
                import os
                os.unlink(temp_path)
            except:
                pass

def safe_float_convert(value):
    """Convert string to float with error handling"""
    try:
        return float(str(value).replace(',', ''))
    except:
        return None

# ===== Comparison Functions =====
def safe_comparison(estimate_df, bill_df):
    """Perform comparison with comprehensive error checking"""
    results = {
        'increased': pd.DataFrame(),
        'reduced': pd.DataFrame(),
        'new': pd.DataFrame(),
        'removed': pd.DataFrame()
    }
    
    try:
        if estimate_df.empty or bill_df.empty:
            return results
            
        # Standardize column names
        estimate_df = estimate_df.rename(columns=str.strip)
        bill_df = bill_df.rename(columns=str.strip)
        
        # Ensure required columns exist
        required_cols = ['Part Number', 'Description', 'Amount']
        for col in required_cols:
            if col not in estimate_df.columns or col not in bill_df.columns:
                st.error(f"Missing required column: {col}")
                return results
                
        # Set index and prepare for comparison
        estimate_df = estimate_df.set_index('Part Number')
        bill_df = bill_df.set_index('Part Number')
        
        # Perform a safe merge
        try:
            merged_df = bill_df.merge(
                estimate_df,
                how='outer',
                suffixes=('_bill', '_estimate'),
                indicator=True
            )
        except Exception as e:
            st.error(f"Merge Error: {str(e)}")
            return results
            
        # Calculate comparisons more safely
        increased_mask = (
            (merged_df['Amount_bill'] > merged_df['Amount_estimate']) & 
            (merged_df['_merge'] == 'both')
        )
        
        reduced_mask = (
            (merged_df['Amount_bill'] < merged_df['Amount_estimate']) & 
            (merged_df['_merge'] == 'both')
        )
        
        new_mask = (merged_df['_merge'] == 'left_only')
        removed_mask = (merged_df['_merge'] == 'right_only')
        
        # Create comparison results with proper columns
        for key, mask in [
            ('increased', increased_mask),
            ('reduced', reduced_mask),
            ('new', new_mask),
            ('removed', removed_mask)
        ]:
            if sum(mask) > 0:
                results[key] = merged_df[mask].copy()
                # Rename columns for display
                results[key].columns = [c.replace('_bill', '').replace('_estimate', ' (Estimate)') 
                                      for c in results[key].columns]
                results[key] = results[key][[c for c in results[key].columns if c != '_merge']]
                
    except Exception as e:
        st.error(f"Comparison Error: {str(e)}")
        
    return results

# ===== Display Functions =====
def format_dataframe(df):
    """Apply consistent formatting to DataFrames"""
    if df.empty:
        return df
        
    # Format numeric columns
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
            
    return df

def create_excel_download(comparison_result):
    """Generate Excel download with all comparison sheets"""
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for name, df in comparison_result.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=name.capitalize(), index=True)
                    
        output.seek(0)
        b64 = base64.b64encode(output.read()).decode()
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="Estimate_vs_Bill.xlsx">📥 Download Full Report</a>'
    except Exception as e:
        st.error(f"Excel Generation Error: {str(e)}")
        return None

# ===== Main Application =====
def main():
    st.markdown('<div class="header">Estimate vs Bill Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown("Compare your estimate and bill documents to identify changes in pricing and parts.")
    
    with st.expander("📁 Upload Documents", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            estimate_file = st.file_uploader("Upload Estimate PDF", type=["pdf"])
        with col2:
            bill_file = st.file_uploader("Upload Bill PDF", type=["pdf"])
    
    if st.button("🔍 Compare Documents", use_container_width=True, type="primary"):
        if estimate_file is None or bill_file is None:
            st.warning("Please upload both estimate and bill documents")
            return
            
        with st.spinner("Processing documents..."):
            # Processing estimate
            estimate_df = safe_extract_parts(estimate_file)
            if estimate_df.empty:
                st.error("Failed to extract data from Estimate PDF")
                return
                
            # Processing bill
            bill_df = safe_extract_parts(bill_file)
            if bill_df.empty:
                st.error("Failed to extract data from Bill PDF")
                return
                
            # Run comparison
            comparison_result = safe_comparison(estimate_df, bill_df)
            
            # Display results
            st.success("Comparison completed successfully!")
            st.markdown("---")
            
            # Show summary metrics
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
            
            # Show detailed comparison tabs
            st.markdown("---")
            with st.expander("📊 Detailed Comparison Results", expanded=True):
                tabs = st.tabs([tab[0] for tab in metrics])
                
                for i, (tab, key) in enumerate(zip(tabs, ['increased', 'reduced', 'new', 'removed'])):
                    with tab:
                        df = comparison_result[key]
                        if not df.empty:
                            st.dataframe(
                                format_dataframe(df),
                                use_container_width=True,
                                height=400
                            )
                        else:
                            st.info(f"No {key.replace('_', ' ')} parts found")
            
            # Excel download
            st.markdown("---")
            download_link = create_excel_download(comparison_result)
            if download_link:
                st.markdown(download_link, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
