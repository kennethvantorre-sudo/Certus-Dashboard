import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime

# 🎨 1. PAGINA INSTELLINGEN
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# 🧠 2. HET GEHEUGEN VAN DE SITE (Session State)
if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()
if 'brandstof_totaal' not in st.session_state:
    st.session_state.brandstof_totaal = 0
if 'brandstof_lijst' not in st.session_state:
    st.session_state.brandstof_lijst = []

# ⚙️ 3. DE MOTOR: PDF ANALYSE & KOPPELING
# Let op: We geven nu de 'gekozen_project' naam mee aan de motor!
def analyseer_pdfs(files, gekozen_project):
    treinen = {}
    for file in files:
        try:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            # --- INFRABEL CHECK ---
            if "Infrabel" in text and "Book In" in text:
                
                # Haal de datum eruit
                datum_match = re.search(r'Geldig van (\d{2})/(\d{2})/(\d{4})', text)
                if datum_match:
                    dag, maand, jaar = datum_match.groups()
                    datum_str = f"{jaar}-{maand}-{dag}"
                else:
                    datum_str = datetime.today().strftime('%Y-%m-%d')

                delen = re.split(r'Parcours à vide\s*/\s*Losse ritten', text, flags=re.IGNORECASE)
                tekst_beladen = delen[0]
                tekst_los = delen[1] if len(delen) > 1 else ""
                alle_treinen = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                
                for t_nr in alle_treinen:
                    is_los = t_nr in tekst_los
                    km_match = re.search(r'TreinKm INFRABEL-net:\s*(\d+(?:,\d+)?)\s*km', text)
                    afstand = float(km_match.group(1).replace(',', '.')) if km_match else 0.0
                    
                    if t_nr not in treinen:
                        treinen[t_nr] = {
                            "Datum": datum_str, "Project": gekozen_project, "Trein": t_nr,
                            "Type": "Losse Rit" if is_los else "Beladen Rit",
                            "Afstand (km)": afstand, "Gewicht (ton)": 0.0,
                            "RID": "Nee", "UN Nummer": ""
                        }

            # --- RAILCUBE CHECK ---
            elif "Trein Nummer:" in text or "rail solutions" in text:
                t_match = re.search(r'Trein Nummer:\s*(\d{5})', text)
                if t_match:
                    t_nr = t_match.group(1)
                    
                    # RID Scanner
                    rid_match = re.search(r'\b(UN\s*\d{4}|\b1170\b|\b1202\b|\b1863\b|\b1203\b|\b3257\b|\b1965\b)\b', text)
                    is_rid = "Ja" if rid_match else "Nee"
                    un_code = rid_match.group(1) if rid_match else ""

                    totaal_gewicht = 0.0
                    totalen_match = re.search(r'Totalen(.*?)\n', text, re.IGNORECASE)
                    if totalen_match:
                        getallen = re.findall(r'\d+(?:,\d+)?', totalen_match.group(1))
                        getallen_floats = [float(g.replace(',', '.')) for g in getallen]
                        if getallen_floats:
                            totaal_gewicht = max(getallen_floats)
                    
                    if t_nr in treinen:
                        treinen[t_nr]["Gewicht (ton)"] = totaal_gewicht
                        treinen[t_nr]["RID"] = is_rid
                        treinen[t_nr]["UN Nummer"] = un_code.replace('UN', '').strip()
                        # Zorg dat Railcube ook het gekozen project krijgt als Infrabel ontbrak
                        treinen[t_nr]["Project"] = gekozen_project
                    else:
                        treinen[t_nr] = {
                            "Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr,
                            "Type": "Beladen Rit", "Afstand (km)": 0.0,
                            "Gewicht (ton)": totaal_gewicht, "RID": is_rid, "UN Nummer": un_code.replace('UN', '').strip()
                        }
        except Exception as e:
            pass 
    return pd.DataFrame(list(treinen.values()))

# 🎨 4. HET MENU (SIDEBAR)
with st.sidebar:
    try:
        st.image("logo.png", width=180)
    except:
        st.write("🚂 **Certus Rail Solutions**")
    
    st.markdown("---")
    st.header("📌 Hoofdmenu")
    keuze = st.radio("Kies een module:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))
    
    if st.button("🗑️ Wis alle data"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.brandstof_totaal = 0
        st.session_state.brandstof_lijst = []
        st.rerun()

    st.markdown("---")
    st.caption("Certus Command Center v2.1")

# 🎨 5. SCHERM 1: HOME (DASHBOARD)
if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    
    df = st.session_state.df_ritten
    tot_brandstof = st.session_state.brandstof_totaal
    
    if not df.empty:
        tot_treinen = len(df)
        tot_los = len(df[df["Type"] == "Losse Rit"])
        tot_ton = df["Gewicht (ton)"].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gereden Treinen", f"{tot_treinen}")
        col2.metric("Losse Ritten", f"{tot_los}")
        col3.metric("Totaal Vervoerd", f"{tot_ton:,.0f} Ton")
        col4.metric("Brandstof Verbruik", f"{tot_brandstof:,} L")
        
        st.markdown("---")
        
        col_grafiek1, col_grafiek2 = st.columns(2)
        
        with col_grafiek1:
            st.write("### 🏆 Top Projecten (Tonnage)")
            df_project = df.groupby('Project')['Gewicht (ton)'].sum().reset_index()
            if not df_project.empty and df_project['Gewicht (ton)'].sum() > 0:
                fig_bar = px.bar(df_project, x='Project', y='Gewicht (ton)', color='Project', color_discrete_sequence=px.colors.qualitative.Set1)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Nog geen gewichten geladen om projecten te vergelijken.")
            
        with col_grafiek2:
            st.write("### ⏱️ Ritten Verloop (RID vs Regulier)")
            df_tijd = df.groupby(['Datum', 'RID']).size().reset_index(name='Aantal')
            if not df_tijd.empty:
                fig_line = px.line(df_tijd, x='Datum', y='Aantal', color='RID', markers=True, color_discrete_map={'Ja': '#e74c3c', 'Nee': '#3498db'})
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Onvoldoende data voor de tijdlijn.")
    else:
        st.info("👆 Het dashboard is nog leeg. Ga in het menu naar 'Invoer Ritten' om je eerste PDF's in te laden!")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gereden Treinen", "0")
        col2.metric("Losse Ritten", "0")
        col3.metric("Totaal Vervoerd", "0 Ton")
        col4.metric("Brandstof Verbruik", f"{tot_brandstof} L")

    st.markdown("---")
    col_img_links, col_img_midden, col_img_rechts = st.columns([2, 3, 2])
    with col_img_midden:
        try:
            st.image("loco.png", caption="Certus Rail Solutions", use_container_width=True)
        except:
            pass

# 🎨 6. SCHERM 2: INVOER RITTEN
elif keuze == "📄 Invoer Ritten":
    st.title("📄 Ritten & Prestaties Invoeren")
    st.info("Koppel hier de Infrabel (BNX) ritten aan de RailCube wagonlijsten.")
    
    # HIER IS HET NIEUWE INVULVAK!
    st.write("### 🏷️ Stap 1: Kies het Project")
    gekozen_project = st.text_input("Typ hier de projectnaam (bijv. P_STUK2602, P419, P406):")
    
    st.write("### 📂 Stap 2: Bestanden Uploaden")
    uploaded_files = st.file_uploader("Sleep de bijbehorende BNX- en Wagonlijst PDF's hierin", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        if not gekozen_project:
            # Waarschuwing als ze het project vergeten zijn!
            st.warning("⚠️ Wacht even! Vul eerst de projectnaam in bovenaan voordat je op verwerken klikt.")
        else:
            if st.button("🚀 Verwerk deze bestanden", use_container_width=True):
                # Stuur de bestanden én de projectnaam naar de motor
                nieuw_df = analyseer_pdfs(uploaded_files, gekozen_project)
                
                if not nieuw_df.empty:
                    gecombineerd_df = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
                    st.session_state.df_ritten = gecombineerd_df
                    st.success(f"✅ Succes! {len(nieuw_df)} treinen zijn opgeslagen onder project **{gekozen_project}**.")
                else:
                    st.error("Er is geen treindata gevonden in deze PDF's.")
                
    st.markdown("---")
    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Huidige Database")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False, sheet_name='Certus_Rapport')
            
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            st.download_button("📥 Download Database als Excel", data=output.getvalue(), file_name="Certus_Rapportage.xlsx", use_container_width=True)

# 🎨 7. SCHERM 3: INVOER BRANDSTOF
elif keuze == "⛽ Invoer Brandstof":
    st.title("⛽ Brandstof Registratie")
    st.write("Vul hier de tankbeurten in. Deze worden direct opgeteld op het dashboard.")
    
    col_space1, col_form, col_space2 = st.columns([1, 2, 1])
    with col_form:
        st.write("### 📝 Nieuwe Tankbeurt")
        datum = st.date_input("Datum van tanken", datetime.today())
        locomotief = st.selectbox("Kies Locomotief", ["7744", "7752", "6514", "Andere..."])
        liters = st.number_input("Aantal Liters", min_value=0, step=1)
        
        if st.button("💾 Sla tankbeurt op", use_container_width=True):
            if liters > 0:
                st.session_state.brandstof_totaal += liters
                st.session_state.brandstof_lijst.append({"Datum": datum, "Loc": locomotief, "Liters": liters})
                st.success(f"✅ {liters}L voor {locomotief} opgeslagen! Check het Dashboard.")
            else:
                st.error("Vul een geldig aantal liters in.")
                
    if st.session_state.brandstof_lijst:
        st.markdown("---")
        st.write("#### 📋 Recente Tankbeurten")
        st.table(pd.DataFrame(st.session_state.brandstof_lijst).tail(5))
