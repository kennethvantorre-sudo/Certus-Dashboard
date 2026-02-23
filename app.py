import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# 🎨 1. PAGINA INSTELLINGEN (ALTIJD BOVENAAN!)
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- TEST DATA (Dit vervangen we later door de echte data uit PDF's) ---
dummy_projecten = pd.DataFrame({
    'Project': ['P_STUK2601', 'P_STUK2602', 'P_STUK2603', 'P_STUK2604'],
    'Tonnen': [15000, 48000, 12000, 5000] # Je ziet dat 2602 extreem hoog is
})

dummy_rid_tijdlijn = pd.DataFrame({
    'Datum': pd.date_range(start='2026-02-01', periods=15),
    'Gewone Ritten': [2, 3, 2, 4, 3, 5, 2, 3, 4, 2, 1, 3, 4, 5, 3],
    'RID Ritten': [1, 0, 1, 2, 1, 1, 0, 1, 1, 0, 2, 1, 0, 1, 1]
})
# ------------------------------------------------------------------------

# 🎨 2. HET MENU (SIDEBAR)
with st.sidebar:
    try:
        st.image("logo.png", width=180)
    except:
        st.write("🚂 **Certus Rail Solutions**")
    
    st.markdown("---")
    st.header("📌 Hoofdmenu")
    
    # Hier maken we de navigatie knoppen
    keuze = st.radio(
        "Kies een module:",
        ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof")
    )
    
    st.markdown("---")
    st.caption("Certus Command Center v1.0")


# 🎨 3. SCHERM 1: HOME (DASHBOARD)
if keuze == "🏠 Home (Dashboard)":
    
    # Mooie header foto bovenaan
    try:
        st.image("loco.png", use_container_width=True)
    except:
        pass
        
    st.title("📊 Actueel Overzicht - 2026")
    
    # KPI BLOKKEN
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gereden Treinen", "114", "+12 deze week")
    col2.metric("Losse Ritten", "28", "-2 deze week")
    col3.metric("Totaal Vervoerd", "80.000 Ton", "+15.000 Ton")
    col4.metric("Brandstof Verbruik", "4.276 L", "+1069 L")
    
    st.markdown("---")
    
    # GRAFIEKEN
    col_grafiek1, col_grafiek2 = st.columns(2)
    
    with col_grafiek1:
        st.write("### 🏆 Top Projecten (Tonnage)")
        # De staafgrafiek voor de mappen
        fig_bar = px.bar(dummy_projecten, x='Project', y='Tonnen', 
                         color='Project', 
                         color_discrete_sequence=['#3498db', '#e74c3c', '#2ecc71', '#f1c40f'])
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_grafiek2:
        st.write("### ⏱️ Ritten Verloop (RID vs Regulier)")
        # De interactieve lijngrafiek
        fig_line = px.line(dummy_rid_tijdlijn, x='Datum', y=['Gewone Ritten', 'RID Ritten'],
                           color_discrete_map={'Gewone Ritten': '#3498db', 'RID Ritten': '#e74c3c'})
        st.plotly_chart(fig_line, use_container_width=True)


# 🎨 4. SCHERM 2: INVOER RITTEN
elif keuze == "📄 Invoer Ritten":
    st.title("📄 Ritten & Prestaties Invoeren")
    st.info("Koppel hier de Infrabel (BNX) ritten aan de RailCube wagonlijsten.")
    
    st.write("### 📂 Bestanden Uploaden")
    uploaded_files = st.file_uploader("Sleep BNX- en Wagonlijst PDF's hierin", type="pdf", accept_multiple_files=True)
    
    st.markdown("---")
    if uploaded_files:
        st.success("Bestanden ontvangen! (De 'hersenen' hiervoor bouwen we in de volgende stap in)")
    else:
        st.write("Wachtend op bestanden...")


# 🎨 5. SCHERM 3: INVOER BRANDSTOF
elif keuze == "⛽ Invoer Brandstof":
    st.title("⛽ Brandstof Registratie")
    st.write("Vul hier snel de gegevens uit de tank-emails in.")
    
    # We zetten het formulier in een mooie "kaart" in het midden
    col_space1, col_form, col_space2 = st.columns([1, 2, 1])
    
    with col_form:
        st.write("### 📝 Nieuwe Tankbeurt")
        
        # Invoer velden
        datum = st.date_input("Datum van tanken", datetime.today())
        locomotief = st.selectbox("Kies Locomotief", ["7744", "7752", "6514", "Andere..."])
        liters = st.number_input("Aantal Liters", min_value=0, step=1)
        locatie = st.text_input("Locatie (bijv. Schaarbeek-Bundel P)")
        machinist = st.text_input("Gemeld door (bijv. Draux, Lennert)")
        
        # De 'Opslaan' knop
        if st.button("💾 Sla tankbeurt op", use_container_width=True):
            if liters > 0:
                st.success(f"✅ Succes! {liters} liter voor loc {locomotief} is toegevoegd aan de database.")
            else:
                st.error("Vul een geldig aantal liters in.")