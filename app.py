import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime

# 🎨 1. PAGINA INSTELLINGEN
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# 🧠 2. HET GEHEUGEN
if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()
if 'brandstof_totaal' not in st.session_state:
    st.session_state.brandstof_totaal = 0

# ⚙️ 3. DE MOTOR: PDF & EXCEL ANALYSE
def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    for file in files:
        try:
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = "".join([page.extract_text() for page in reader.pages])
                if "Infrabel" in text:
                    datum_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                    datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                    
                    # Zoek treinnummers (65901, 65902, etc.)
                    nummers = re.findall(r'(\d{5})\s+\d{2}/\d{2}/\d{2}', text)
                    if not nummers: nummers = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                    
                    # Zoek de kilometers (Infrabel BNX formaat)
                    km_match = re.search(r'(?:TreinKm|KmTrain|INFRABEL-net).*?(\d+(?:,\d+)?)', text, re.IGNORECASE)
                    afstand = float(km_match.group(1).replace(',', '.')) if km_match else 16.064
                    
                    for t_nr in set(nummers):
                        if t_nr not in treinen:
                            treinen[t_nr] = {"Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": "Nee"}

            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file, engine='openpyxl')
                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    # We zoeken enkel in kolommen die op gewicht lijken en filteren wagennummers (max 4000 ton)
                    num_data = xl.select_dtypes(include=['number'])
                    realistische_waarden = num_data[num_data < 4000]
                    gewicht = realistische_waarden.max().max()
                    
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    if t_nr in treinen: treinen[t_nr].update({"Gewicht (ton)": gewicht})
                    else: treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": gewicht, "RID": "Nee"}
        except: pass
    return pd.DataFrame(list(treinen.values()))

# 🎨 4. MENU
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))
    st.markdown("---")
    st.info("💡 Tip: Download je archief regelmatig via de Invoer-pagina.")

# 🎨 5. HOME DASHBOARD
if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    df = st.session_state.df_ritten
    
    if not df.empty:
        # We filteren de miljarden-fout er handmatig uit mocht die nog in het geheugen zitten
        df = df[df['Gewicht (ton)'] < 1000000] 
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treinen", len(df))
        c2.metric("Totaal Ton", f"{df['Gewicht (ton)'].sum():,.1f}")
        c3.metric("Km Infrabel", f"{df['Afstand (km)'].sum():,.2f}")
        c4.metric("Brandstof", f"{st.session_state.brandstof_totaal:,} L")
        
        st.plotly_chart(px.bar(df, x='Project', y='Gewicht (ton)', color='Project', template="plotly_dark"), use_container_width=True)
    else:
        st.info("Dashboard is leeg. Ga naar 'Invoer Ritten' om bestanden te verwerken.")
    
    st.markdown("---")
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_m:
        try: st.image("loco.png", use_container_width=True)
        except: pass

# 🎨 6. INVOER RITTEN
elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam (bijv. P419):")
    uploaded_files = st.file_uploader("Upload PDF's & Excel", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files and gekozen_project:
        if st.button("🚀 Verwerk bestanden", use_container_width=True):
            nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
            if not nieuw_df.empty:
                st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
                st.success("Data succesvol verwerkt!")
                st.rerun()

    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Database")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Archief", data=output.getvalue(), file_name=f"Certus_Archief_{datetime.now().strftime('%Y%m%d')}.xlsx")
