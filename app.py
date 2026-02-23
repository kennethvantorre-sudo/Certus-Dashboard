import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime

# 🎨 1. PAGINA INSTELLINGEN
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# 🧠 2. HET GEHEUGEN & SCHOONMAAK
if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()

# Automatische opschoning van de foutieve miljarden-data
if not st.session_state.df_ritten.empty:
    # We behouden enkel ritten met een realistisch gewicht (onder 5000 ton)
    st.session_state.df_ritten = st.session_state.df_ritten[st.session_state.df_ritten['Gewicht (ton)'] < 5000]

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
                    
                    # Zoek treinnummers
                    nummers = re.findall(r'(\d{5})\s+\d{2}/\d{2}/\d{2}', text)
                    if not nummers: nummers = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                    
                    # Verbeterde KM scanner voor BNX-466 formaat
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
                    # We pakken enkel realistische numerieke waarden (geen wagennummers van 12 cijfers!)
                    num_data = xl.select_dtypes(include=['number'])
                    realistische_waarden = num_data[num_data < 4000] 
                    gewicht = realistische_waarden.max().max()
                    
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    if t_nr in treinen: treinen[t_nr].update({"Gewicht (ton)": gewicht})
                    else: treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": gewicht, "RID": "Nee"}
        except: pass
    return pd.DataFrame(list(treinen.values()))

# 🎨 4. MENU & DASHBOARD (WIS-KNOP IS WEG)
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))
    st.markdown("---")
    st.info("💡 De database wordt automatisch opgeschoond bij onrealistische waarden.")

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    df = st.session_state.df_ritten
    if not df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treinen", len(df))
        c2.metric("Totaal Ton", f"{df['Gewicht (ton)'].sum():,.1f}")
        c3.metric("Km Infrabel", f"{df['Afstand (km)'].sum():,.2f}")
        c4.metric("Brandstof", f"{st.session_state.brandstof_totaal:,} L")
        st.plotly_chart(px.bar(df, x='Project', y='Gewicht (ton)', color='Project', template="plotly_dark"), use_container_width=True)
    else:
        st.info("Database is nu schoon. Upload je bestanden opnieuw via 'Invoer Ritten'.")
    st.image("loco.png", use_container_width=True)

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam (bijv. P419):")
    uploaded_files = st.file_uploader("Upload PDF's & Excel", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    if uploaded_files and gekozen_project:
        if st.button("🚀 Verwerk bestanden", use_container_width=True):
            nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
            if not nieuw_df.empty:
                st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
                st.success("Nieuwe ritten succesvol toegevoegd!")
                st.rerun()
    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Database (Opgeschoond)")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Archief", data=output.getvalue(), file_name=f"Certus_Archief.xlsx")
