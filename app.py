import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import base64
from io import BytesIO
import tempfile

# ===== App Config =====
st.set_page_config(
    page_title="Estimate vs Bill Comparison",
    page_icon="📊",
    layout="wide"
)

# ===== CSS Styling =====
st.markdown("""
<style>
    .header {
        color: #2e86ab;
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .upload-section {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #ddd;
    }
    .result-section {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ddd;
    }
    .stButton>button {
        background-color: #2e86ab;
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 5px;
        font-weight: bold;
    }
    .stDownloadButton>button {
        background-color: #28a745 !important;
        color: white !important;
    }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .highlight-increase {
        color: #dc3545;
        font-weight: bold;
    }
    .highlight-decrease {
        color: #28a745;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ===== PDF Processing =====
def extract_parts_from_pdf(pdf_file):
    parts = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_file.read())
            tmp_path = tmp.name
        
        doc = fitz.open(tmp_path)
        
        for page in doc:
            text = page.get_text()
            # Enhanced regex with better pattern matching
            matches = re.finditer(
                r'(?P<part_number>[A-Z0-9\-]+)\s+(?P<description>.+?)\s+(?P<amount>[\d,]+\.\d{2})',
                text,
                re.DOTALL
            )
            for match in matches:
                parts.append({
                    'Part Number': match.group('part_number').strip(),
                    'Description': match.group('description').strip(),
                    'Amount': float(match.group('amount').replace(',', ''))
                })
        
        doc.close()
    except Exception as e:
        st.error(f"⚠️ PDF Processing Error: {str(e)}")
    finally:
        try:
            import os
            os.unlink(tmp_path)
        except:
            pass
    
    return pd.DataFrame(parts)

# ===== Data Comparison =====
def compare_dataframes(df_estimate, df_bill):
    result = {
        'increased': None,
        'reduced': None,
        'new': None,
        'removed': None
    }
    
    if df_estimate.empty or df_bill.empty:
        return result
    
    df_estimate = df_estimate.set_index('Part Number')
    df_bill = df_bill.set_index('Part Number')
    
    # Merged dataframe for comparison
    merged = df_bill.merge(
        df_estimate,
        how='outer',
        left_index=True,
        right_index=True,
        suffixes=('_bill', '_estimate')
    )
    
    # Calculate differences
    result['increased'] = merged[
        (merged['Amount_bill'] > merged['Amount_estimate']) & 
        (~merged['Amount_estimate'].isna())
    ]
    result['reduced'] = merged[
        (merged['Amount_bill'] < merged['Amount_estimate']) & 
        (~merged['Amount_estimate'].isna())
    ]
    result['new'] = merged[merged['Amount_estimate'].isna()]
    result['removed'] = merged[merged['Amount_bill'].isna()]
    
    return result

# ===== Excel Export =====
def generate_excel_report(comparison_result):
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name in ['increased', 'reduced', 'new', 'removed']:
            if comparison_result[sheet_name] is not None and not comparison_result[sheet_name].empty:
                comparison_result[sheet_name].to_excel(writer, sheet_name=sheet_name.title())
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="Estimate_vs_Bill_Comparison.xlsx">Download Excel Report</a>'
    return href

# ===== Main App =====
def main():
    st.markdown('<div class="header">📊 Estimate vs Bill Comparison Tool</div>', unsafe_allow_html=True)
    
    # Intro
    st.markdown("""
    Compare estimates and bills to identify:
    - 🔺 Increased amounts
    - 🔻 Reduced amounts
    - 🆕 New parts
    - ❌ Removed parts
    """)
    
    # File Upload
    with st.expander("Upload Documents", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            estimate_file = st.file_uploader("Upload Estimate PDF", type="pdf")
        with col2:
            bill_file = st.file_uploader("Upload Bill PDF", type="pdf")
    
    if st.button("Run Comparison", use_container_width=True, type="primary"):
        if estimate_file is None or bill_file is None:
            st.warning("Please upload both files")
            return
        
        with st.spinner("Processing documents..."):
            # Extract data
            df_estimate = extract_parts_from_pdf(estimate_file)
            df_bill = extract_parts_from_pdf(bill_file)
            
            if df_estimate.empty or df_bill.empty:
                st.error("Could not extract data. Check PDF formats and try again.")
                return
            
            # Run comparison
            comparison_result = compare_dataframes(df_estimate, df_bill)
            
            # Show summary metrics
            st.success("Comparison completed!")
            st.markdown("---")
            
            cols = st.columns(4)
            metric_data = [
                ("Increased", len(comparison_result['increased']), "#dc3545", "🔺"),
                ("Reduced", len(comparison_result['reduced']), "#28a745", "🔻"),
                ("New", len(comparison_result['new']), "#17a2b8", "🆕"),
                ("Removed", len(comparison_result['removed']), "#6c757d", "❌")
            ]
            
            for idx, (label, value, color, icon) in enumerate(metric_data):
                with cols[idx]:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div style="font-size:24px;color:{color};margin-bottom:8px;">{icon}</div>
                            <div style="font-size:14px;color:#6c757d;margin-bottom:4px;">{label}</div>
                            <div style="font-size:28px;font-weight:bold;color:{color};">{value}</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
            
            # Detailed results tabs
            with st.expander("Detailed Results", expanded=True):
                tab1, tab2, tab3, tab4 = st.tabs([
                    "🔺 Increased", 
                    "🔻 Reduced", 
                    "🆕 New", 
                    "❌ Removed"
                ])
                
                with tab1:
                    if comparison_result['increased'] is not None and not comparison_result['increased'].empty:
                        st.dataframe(comparison_result['increased'].style.applymap(
                            lambda x: 'color: #dc3545' if isinstance(x, (int, float)) and x > 0 else ''
                        ))
                    else:
                        st.info("No items with increased amounts found")
                
                with tab2:
                    if comparison_result['reduced'] is not None and not comparison_result['reduced'].empty:
                        st.dataframe(comparison_result['reduced'].style.applymap(
                            lambda x: 'color: #28a745' if isinstance(x, (int, float)) and x < 0 else ''
                        ))
                    else:
                        st.info("No items with reduced amounts found")
                
                with tab3:
                    if comparison_result['new'] is not None and not comparison_result['new'].empty:
                        st.dataframe(comparison_result['new'])
                    else:
                        st.info("No new items found")
                
                with tab4:
                    if comparison_result['removed'] is not None and not comparison_result['removed'].empty:
                        st.dataframe(comparison_result['removed'])
                    else:
                        st.info("No removed items found")
            
            # Download button
            st.markdown("---")
            st.markdown(generate_excel_report(comparison_result), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
