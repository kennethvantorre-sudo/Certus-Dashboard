import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime
import base64
import docx
import folium
from streamlit_folium import st_folium
import google.generativeai as genai

st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- AI CONFIGURATIE (Stabiele Versie) ---
API_KEY = "AIzaSyDGvPTbF1_s_PmUMqOhBr2BjVYVk6aS1Zg"
genai.configure(api_key=API_KEY)
# We gebruiken 'gemini-pro' omdat deze de minste 404-fouten geeft op Streamlit Cloud
model = genai.GenerativeModel('gemini-pro') 

# --- DATABASE LOCATIES (Inclusief Infrabel-codes uit jouw wagonlijsten) ---
LOCATIES_DB = {
    "GENT-ZEEH": [51.134, 3.823],
    "GENT-ZEEHAVEN": [51.134, 3.823],
    "FGZH": [51.134, 3.823],           # Gent-Zeehaven afkorting
    "VERB.GTS": [51.145, 3.815],
    "ANTWERPEN-NOORD": [51.275, 4.433],
    "ROOSENDAAL": [51.540, 4.458],
    "ZEEBRUGGE": [51.328, 3.197],
    "KALLO": [51.254, 4.275],
    "BRUSSEL-ZUID": [50.836, 4.335],
    "EVERGEM-BUNDEL ZANDEKEN": [51.121, 3.738],
    "EVERGEM": [51.108, 3.708],
    "FZNKN": [51.121, 3.738]           # Evergem-Zandeken afkorting
}

def speel_certus_animatie():
    if 'animatie_gespeeld' not in st.session_state:
        try:
            with open("logo.png", "rb") as f:
                b64_logo = base64.b64encode(f.read()).decode("utf-8")
            st.markdown(f"""
            <div id="splash-screen" style="position:fixed;top:0;left:0;width:100vw;height:100vh;background:#0e1117;z-index:9999;display:flex;justify-content:center;align-items:center;animation:fadeOut 1s forwards;animation-delay:1.5s;pointer-events:none;">
                <img src="data:image/png;base64,{b64_logo}" style="width:300px;">
            </div>
            <style>@keyframes fadeOut {{ 0% {{opacity:1;}} 100% {{opacity:0;visibility:hidden;}} }}</style>
            """, unsafe_allow_html=True)
            st.session_state.animatie_gespeeld = True
        except: pass

speel_certus_animatie()

if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()

if "messages" not in st.session_state:
    st.session_state.messages = []

def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    bekende_treinen_uit_excel = set()

    # STAP 1: Scan Excels voor treinnummers en locaties (De basis)
    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_match = re.search(r'(\d{5})', file.name)
            if t_nr_match:
                t_nr = t_nr_match.group(1)
                bekende_treinen_uit_excel.add(t_nr)
                xl = pd.read_excel(file)
                excel_text = xl.to_string(index=False).upper()
                
                # Gewicht bepalen
                for col in xl.columns: xl[col] = pd.to_numeric(xl[col].astype(str).str.replace(',', '.'), errors='coerce')
                gewicht = xl.select_dtypes(include=['number']).max().max()
                gewicht = float(gewicht) if pd.notnull(gewicht) and gewicht < 4000 else 0.0
                
                # Locaties bepalen via afkortingen FGZH/FZNKN
                gevonden_locs = [loc for loc in LOCATIES_DB.keys() if loc in excel_text]
                v_loc = gevonden_locs[0] if gevonden_locs else "Onbekend"
                a_loc = gevonden_locs[-1] if len(gevonden_locs) > 1 else v_loc
                
                treinen[t_nr] = {
                    "Datum": datetime.today().strftime('%Y-%m-%d'),
                    "Project": gekozen_project,
                    "Trein": t_nr,
                    "Type": "Ledige Rit" if gewicht < 450 else "Beladen Rit",
                    "Afstand (km)": 0.0,
                    "Gewicht (ton)": gewicht,
                    "RID": "Ja" if "1863" in excel_text else "Nee",
                    "Vertrek": v_loc,
                    "Aankomst": a_loc
                }

    # STAP 2: Vul aan met PDF data (De afstanden)
    for file in files:
        if file.name.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
            clean_text = text.replace(' ', '').replace('\n', '')
            
            # Kilometer scanner
            km_match = re.search(r'(?:KmTrain|TreinKm|INFRABEL-net)[^\d]*(\d+(?:[.,]\d+)?)', text, re.IGNORECASE)
            afstand = float(km_match.group(1).replace(',', '.')) if km_match else 0.0
            
            # Koppel afstand aan de juiste trein uit de Excel
            for t_nr in bekende_treinen_uit_excel:
                if t_nr in clean_text:
                    treinen[t_nr]["Afstand (km)"] = afstand
                    # Update datum uit PDF indien gevonden
                    datum_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                    if datum_match: treinen[t_nr]["Datum"] = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}"

    return pd.DataFrame(list(treinen.values()))

with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    if st.button("🗑️ Wis Data & Chat"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
    keuze = st.radio("Menu:", ("🏠 Dashboard", "📄 Invoer", "💬 AI Assistent"))

if keuze == "🏠 Dashboard":
    st.title("📊 Overzicht")
    df = st.session_state.df_ritten
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Treinen", len(df))
        c2.metric("Totaal km", f"{df['Afstand (km)'].sum():,.1f}")
        c3.metric("Totaal ton", f"{df['Gewicht (ton)'].sum():,.0f}")
        
        m = folium.Map(location=[51.05, 3.71], zoom_start=8, tiles="CartoDB dark_matter")
        for i, r in df.iterrows():
            if r['Vertrek'] in LOCATIES_DB: folium.Marker(LOCATIES_DB[r['Vertrek']], icon=folium.Icon(color='green')).add_to(m)
            if r['Aankomst'] in LOCATIES_DB: folium.Marker(LOCATIES_DB[r['Aankomst']], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, height=450, use_container_width=True)
    else: st.info("Geen data.")

elif keuze == "📄 Invoer":
    st.title("📄 Invoer")
    proj = st.text_input("Project:", value="P420")
    files = st.file_uploader("Upload bestanden", accept_multiple_files=True)
    if files and st.button("🚀 Verwerk"):
        st.session_state.df_ritten = analyseer_bestanden(files, proj)
        st.rerun()
    st.dataframe(st.session_state.df_ritten)

elif keuze == "💬 AI Assistent":
    st.title("🤖 Certus AI")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if prompt := st.chat_input("Vraag iets over de ritten..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            try:
                ctx = st.session_state.df_ritten.to_csv(index=False) if not st.session_state.df_ritten.empty else "Geen data."
                resp = model.generate_content(f"Data: {ctx}\n\nAntwoord kort in het Nederlands op: {prompt}")
                st.markdown(resp.text)
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
            except Exception as e:
                st.error("AI is nog aan het opstarten in de cloud. Probeer het over een minuutje nog eens.")
