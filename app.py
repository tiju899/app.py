import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import base64
from io import BytesIO
import tempfile

# ========================================================
# 1. PDF PROCESSING ENGINE
# ========================================================

class PDFProcessor:
    """Advanced PDF parser with industrial part number support"""
    
    @staticmethod
    def extract_tabular_data(doc) -> pd.DataFrame:
        """
        Extract parts data from PDF with strict validation
        Returns DataFrame with: ['Part Number', 'Description', 'Quantity', 'Amount']
        """
        def clean_text(text: str) -> str:
            """Normalize text for parsing"""
            return re.sub(r'\s+', ' ', text).strip()
            
        # Enhanced industrial part number pattern
        PART_PATTERN = re.compile(r'''
            ^[A-Z0-9]            # Must start with alphanumeric
            [A-Z0-9\-/]{3,}      # Main body (min 3 chars)
            (?<![-/])$           # Cannot end with separator
        ''', re.VERBOSE)
        
        # Robust amount detection (handles ₹, Rs, USD formats)
        AMOUNT_PATTERN = re.compile(r'''
            (?:₹|Rs?\.?|USD)?\s*  # Currency symbols
            (\d{1,3}             # Main digits
            (?:,\d{3})*          # Thousands separators
            (?:\.\d{2})?)        # Decimal part
        ''', re.VERBOSE)

        parts = []
        for page in doc:
            text = page.get_text("blocks")
            for block in text:
                lines = [clean_text(l) for l in block[4].split('\n') if l.strip()]
                for line in lines:
                    # Skip irrelevant lines (headings, totals etc.)
                    if any(x in line.lower() for x in ['total', 'subtotal', 'tax']):
                        continue
                        
                    tokens = line.split()
                    if len(tokens) < 3:
                        continue
                        
                    # Find part number (prioritize early in line)
                    part_num = next((t for t in tokens[:3] if PART_PATTERN.match(t)), None)
                    if not part_num:
                        continue
                        
                    # Extract all monetary values
                    amounts = [float(m.group(1).replace(',','')) 
                             for m in AMOUNT_PATTERN.finditer(line)]
                    if not amounts:
                        continue
                        
                    # Description is between part# and first amount
                    desc_start = line.index(part_num) + len(part_num)
                    desc_end = line.find(str(amounts[0]))
                    description = line[desc_start:desc_end].strip(' -•,')
                    
                    # Standard quantity = 1 unless specified
                    qty_match = re.search(r'(\d+)\s*(?:pcs?|nos?|units?|qty)', line, re.I)
                    quantity = float(qty_match.group(1)) if qty_match else 1.0
                    
                    parts.append({
                        'Part Number': part_num,
                        'Description': description,
                        'Quantity': quantity,
                        'Amount': amounts[-1]  # Last amount is typically total
                    })
        
        return pd.DataFrame(parts)

# ========================================================
# 2. COMPARISON ENGINE
# ========================================================

class BillComparator:
    """Performs intelligent comparison between Estimate and Bill"""
    
    def __init__(self):
        self.tax_rate = 0.18  # Default 18% GST
        
    def compare(self, 
                estimate: pd.DataFrame, 
                bill: pd.DataFrame) -> pd.DataFrame:
        """
        Compare parts data between estimate and bill
        Returns enriched DataFrame with comparison metrics
        """
        comparison = []
        all_parts = set(estimate['Part Number']).union(bill['Part Number'])
        
        for part in all_parts:
            est = estimate[estimate['Part Number'] == part].iloc[0] if part in estimate['Part Number'].values else None
            bill_rec = bill[bill['Part Number'] == part].iloc[0] if part in bill['Part Number'].values else None
            
            # Determine comparison status
            if est and not bill_rec:
                status = "❌ Missing"
            elif not est and bill_rec:
                status = "🆕 New"
            else:
                if est['Quantity'] != bill_rec['Quantity']:
                    status = f"🔄 Qty Changed ({est['Quantity']}→{bill_rec['Quantity']})"
                elif est['Amount'] > bill_rec['Amount']:
                    status = "🔽 Reduced"
                elif est['Amount'] < bill_rec['Amount']:
                    status = "🔺 Increased"
                else:
                    status = "✅ Same"
                    
            # Calculate tax-adjusted amounts
            est_amount = est['Amount'] if est else 0
            bill_pre_tax = bill_rec['Amount'] if bill_rec else 0
            bill_with_tax = bill_pre_tax * (1 + self.tax_rate)
            
            comparison.append({
                'Part Number': part,
                'Description': est['Description'] if est else bill_rec['Description'],
                'Estimate (Inc Tax)': est_amount,
                'Bill (Excl Tax)': bill_pre_tax,
                'Bill (Inc Tax)': bill_with_tax,
                'Tax Amount': bill_with_tax - bill_pre_tax if bill_rec else 0,
                'Status': status,
                'Delta': bill_with_tax - est_amount if (est and bill_rec) else None
            })
            
        return pd.DataFrame(comparison).sort_values('Status')

# ========================================================
# 3. STREAMLIT APPLICATION
# ========================================================

class PDFComparisonApp:
    """Main application interface"""
    
    def __init__(self):
        self.processor = PDFProcessor()
        self.comparator = BillComparator()
        self._setup_ui()
        
    def _setup_ui(self):
        """Configure Streamlit UI elements"""
        st.set_page_config(
            page_title="Estimate vs Bill Analyzer", 
            page_icon="📊",
            layout="wide"
        )
        
        st.markdown("""
        <style>
            .highlight-reduced { color: #2a9d8f; font-weight: bold; }
            .highlight-increased { color: #e63946; font-weight: bold; }
            .stDataFrame { font-size: 14px; }
        </style>
        """, unsafe_allow_html=True)
        
        st.title("Industrial Parts Comparison Tool")
        st.markdown("Upload Estimate and Bill PDFs to analyze variances")
        
    def _process_file(self, file) -> Tuple[pd.DataFrame, str]:
        """Handle PDF file upload and processing"""
        ext = file.name.split('.')[-1].lower()
        if ext != 'pdf':
            st.error("Only PDF files are supported")
            return pd.DataFrame(), ""
            
        with st.spinner(f"Processing {file.name}..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                doc = fitz.open(tmp.name)
                try:
                    df = self.processor.extract_tabular_data(doc)
                    raw_text = "\n".join(page.get_text() for page in doc)
                    return df, raw_text
                finally:
                    doc.close()
                    
    def show_debug_info(self, estimate_text, bill_text):
        """Debug panel for raw PDF content"""
        with st.expander("🛠 Raw PDF Contents (Debug)"):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Estimate PDF")
                st.text_area("Content", estimate_text, height=300)
            with col2:
                st.subheader("Bill PDF")  
                st.text_area("Content", bill_text, height=300)
                
    def show_results(self, results_df):
        """Display comparison results"""
        st.success(f"Analysis completed for {len(results_df)} parts")
        st.markdown("---")
        
        # Summary statistics
        st.subheader("Comparison Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Parts", len(results_df))
        col2.metric("Reduced Parts", len(results_df[results_df['Status'].str.startswith('🔽')]))
        col3.metric("New Parts", len(results_df[results_df['Status'] == "🆕 New"]))
        
        # Main comparison table
        st.subheader("Detailed Comparison")
        styled_df = results_df.style.format({
            'Estimate (Inc Tax)': "₹{:.2f}",
            'Bill (Excl Tax)': "₹{:.2f}",
            'Bill (Inc Tax)': "₹{:.2f}",
            'Tax Amount': "₹{:.2f}",
            'Delta': lambda x: "₹{:+,.2f}".format(x) if pd.notna(x) else ""
        }).apply(self._color_status_column, axis=1)
        
        st.dataframe(styled_df, use_container_width=True, height=700)
        
        # Download option
        st.markdown("---")
        self._generate_excel_download(results_df)
        
    def _color_status_column(self, row):
        """Helper for DataFrame styling"""
        colors = {
            "🔽 Reduced": 'lightgreen',
            "🔺 Increased": 'lightcoral', 
            "🆕 New": 'lightblue',
            "❌ Missing": 'lightgray'
        }
        return ['background-color: {}'.format(colors.get(row['Status'], ''))]*len(row)
        
    def _generate_excel_download(self, df):
        """Create Excel download link"""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        excel_data = output.getvalue()
        b64 = base64.b64encode(excel_data).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="parts_comparison.xlsx">📥 Download Full Report</a>'
        st.markdown(href, unsafe_allow_html=True)
        
    def run(self):
        """Main application flow"""
        with st.form("upload_form"):
            col1, col2 = st.columns(2)
            with col1:
                est_file = st.file_uploader("Upload Estimate PDF", type=["pdf"])
            with col2:
                bill_file = st.file_uploader("Upload Bill PDF", type=["pdf"])
                
            submitted = st.form_submit_button("Analyze Documents", type="primary")
            
        if submitted:
            if not est_file or not bill_file:
                st.warning("Please upload both Estimate and Bill PDFs")
                return
                
            # Process both documents
            est_df, est_text = self._process_file(est_file)
            bill_df, bill_text = self._process_file(bill_file)
            
            # Debug view if needed
            show_debug = st.checkbox("Show raw PDF contents")
            if show_debug:
                self.show_debug_info(est_text, bill_text)
                
            # Run comparison if data was extracted
            if not est_df.empty and not bill_df.empty:
                results = self.comparator.compare(est_df, bill_df)
                self.show_results(results)
            else:
                st.error("Failed to extract parts data - check PDF format")

# ========================================================
# MAIN EXECUTION
# ========================================================

if __name__ == "__main__":
    app = PDFComparisonApp()
    app.run()
