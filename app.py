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
            # --- A. PDF SCAN (Infrabel) ---
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = "".join([page.extract_text() for page in reader.pages])
                
                if "Infrabel" in text:
                    # Datum zoeken 
                    datum_match = re.search(r'Geldig van (\d{2})/(\d{2})/(\d{4})', text)
                    datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                    
                    # Nieuwe regex die nummers zoals 65901 vinnig uit de tabel vist 
                    nummers = re.findall(r'(\d{5})\s+\d{2}/\d{2}/\d{2}', text)
                    
                    for t_nr in set(nummers):
                        # Afstand zoeken [cite: 21]
                        km_match = re.search(r'TreinKm INFRABEL-net:\s*(\d+(?:,\d+)?)\s*km', text)
                        afstand = float(km_match.group(1).replace(',', '.')) if km_match else 16.064
                        
                        if t_nr not in treinen:
                            treinen[t_nr] = {"Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": "Nee"}

            # --- B. EXCEL SCAN (Wagonlijst) ---
            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file)
                # Nummer uit bestandsnaam halen, bijv. 65902 
                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    # Hoogste getal zoeken voor gewicht
                    totaal_gewicht = xl.select_dtypes(include=['number']).max().max() if not xl.empty else 0.0
                    
                    if t_nr in treinen:
                        treinen[t_nr].update({"Gewicht (ton)": totaal_gewicht})
                    else:
                        treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": totaal_gewicht, "RID": "Nee"}
        except Exception as e:
            st.error(f"Fout bij {file.name}: {e}")
                
    return pd.DataFrame(list(treinen.values()))

# 🎨 4. MENU & LAYOUT
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    df = st.session_state.df_ritten
    
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Treinen", len(df))
        col2.metric("Totaal Ton", f"{df['Gewicht (ton)'].sum():,.0f}")
        col3.metric("Km Infrabel", f"{df['Afstand (km)'].sum():,.2f}")
        col4.metric("Brandstof", f"{st.session_state.brandstof_totaal:,} L")
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 🏆 Projecten")
            fig = px.bar(df.groupby('Project')['Gewicht (ton)'].sum().reset_index(), x='Project', y='Gewicht (ton)', color='Project', template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("### ⏱️ Tonnage verloop")
            fig2 = px.scatter(df, x='Datum', y='Gewicht (ton)', color='Project', size='Gewicht (ton)', template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("⚠️ Dashboard is leeg. Upload PDF/Excel via 'Invoer Ritten'.")
    
    st.markdown("---")
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_m:
        try: st.image("loco.png", use_container_width=True)
        except: pass

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam (bijv. P419):")
    uploaded_files = st.file_uploader("Upload PDF's & Excel", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files and gekozen_project:
        if st.button("🚀 Verwerk bestanden", use_container_width=True):
            nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
            if not nieuw_df.empty:
                st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
                st.success(f"✅ Succes! {len(nieuw_df)} treinen verwerkt.")
                st.rerun()
            else:
                st.error("❌ Kon geen treinnummers vinden in de PDF's. Check het formaat.")
