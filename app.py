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
if 'brandstof_lijst' not in st.session_state:
    st.session_state.brandstof_lijst = []

# ⚙️ 3. DE MOTOR: PDF & EXCEL ANALYSE
def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    for file in files:
        try:
            # --- A. ALS HET EEN PDF IS ---
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                # INFRABEL CHECK
                if "Infrabel" in text and "Book In" in text:
                    datum_match = re.search(r'Geldig van (\d{2})/(\d{2})/(\d{4})', text)
                    datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                    delen = re.split(r'Parcours à vide\s*/\s*Losse ritten', text, flags=re.IGNORECASE)
                    tekst_los = delen[1] if len(delen) > 1 else ""
                    alle_treinen = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                    for t_nr in alle_treinen:
                        km_match = re.search(r'TreinKm INFRABEL-net:\s*(\d+(?:,\d+)?)\s*km', text)
                        afstand = float(km_match.group(1).replace(',', '.')) if km_match else 0.0
                        if t_nr not in treinen:
                            treinen[t_nr] = {"Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, "Type": "Losse Rit" if t_nr in tekst_los else "Beladen Rit", "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": "Nee", "UN Nummer": ""}

                # RAILCUBE PDF CHECK
                elif "Trein Nummer:" in text:
                    t_match = re.search(r'Trein Nummer:\s*(\d{5})', text)
                    if t_match:
                        t_nr = t_match.group(1)
                        rid_match = re.search(r'\b(UN\s*\d{4}|\b1170\b|\b1202\b|\b1863\b|\b1203\b|\b3257\b|\b1965\b)\b', text)
                        totalen_match = re.search(r'Totalen(.*?)\n', text, re.IGNORECASE)
                        totaal_gewicht = 0.0
                        if totalen_match:
                            getallen = re.findall(r'\d+(?:,\d+)?', totalen_match.group(1))
                            if getallen: totaal_gewicht = max([float(g.replace(',', '.')) for g in getallen])
                        if t_nr in treinen:
                            treinen[t_nr].update({"Gewicht (ton)": totaal_gewicht, "RID": "Ja" if rid_match else "Nee", "UN Nummer": rid_match.group(1).replace('UN', '').strip() if rid_match else ""})

            # --- B. ALS HET EEN EXCEL IS ---
            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file)
                # We zoeken naar het treinnummer in de bestandsnaam of in de cellen
                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    # We proberen het gewicht te vinden (vaak de laatste rij bij 'Totaal')
                    totaal_gewicht = 0.0
                    if not xl.empty:
                        # Zoek in alle kolommen naar het hoogste getal (meestal het totaalgewicht)
                        totaal_gewicht = xl.select_dtypes(include=['number']).max().max()
                    
                    if t_nr in treinen:
                        treinen[t_nr].update({"Gewicht (ton)": totaal_gewicht})
                    else:
                        treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": totaal_gewicht, "RID": "Nee", "UN Nummer": ""}
        except: pass 
    return pd.DataFrame(list(treinen.values()))

# --- MENU & PAGINA LAYOUT (Gelijk gebleven) ---
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    df = st.session_state.df_ritten
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Treinen", f"{len(df)}")
        col2.metric("Losse Ritten", f"{len(df[df['Type'] == 'Losse Rit'])}")
        col3.metric("Totaal Ton", f"{df['Gewicht (ton)'].sum():,.0f}")
        col4.metric("Brandstof", f"{st.session_state.brandstof_totaal:,} L")
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(df.groupby('Project')['Gewicht (ton)'].sum().reset_index(), x='Project', y='Gewicht (ton)', color='Project')
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.line(df.groupby(['Datum', 'RID']).size().reset_index(name='Aantal'), x='Datum', y='Aantal', color='RID', markers=True)
            st.plotly_chart(fig2, use_container_width=True)
    st.markdown("---")
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_m:
        try: st.image("loco.png", use_container_width=True)
        except: pass

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam (bijv. P_STUK2602, P419):")
    # AANGEPAST: accepteert nu ook Excel!
    uploaded_files = st.file_uploader("Upload PDF's of Excel wagonlijsten", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files and gekozen_project:
        if st.button("🚀 Verwerk bestanden", use_container_width=True):
            nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
            st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
            st.success("Data toegevoegd!")
                
    if not st.session_state.df_ritten.empty:
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Archief", data=output.getvalue(), file_name=f"Certus_Data.xlsx")

elif keuze == "⛽ Invoer Brandstof":
    st.title("⛽ Brandstof")
    with st.form("tank_form"):
        loc = st.selectbox("Locomotief", ["7744", "7752", "6514"])
        liters = st.number_input("Liters", min_value=0)
        if st.form_submit_button("Opslaan"):
            st.session_state.brandstof_totaal += liters
            st.session_state.brandstof_lijst.append({"Datum": datetime.today(), "Loc": loc, "Liters": liters})
            st.success("Opgeslagen!")
