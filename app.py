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

# --- AI CONFIGURATIE VOOR DE CHATBOT ---
API_KEY = "AIzaSyDGvPTbF1_s_PmUMqOhBr2BjVYVk6aS1Zg"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') 

# --- DATABASE LOCATIES ---
LOCATIES_DB = {
    "GENT-ZEEH": [51.134, 3.823],
    "GENT-ZEEHAVEN": [51.134, 3.823],
    "FGZH": [51.134, 3.823],
    "VERB.GTS": [51.145, 3.815],
    "ANTWERPEN-NOORD": [51.275, 4.433],
    "ROOSENDAAL": [51.540, 4.458],
    "ZEEBRUGGE": [51.328, 3.197],
    "KALLO": [51.254, 4.275],
    "BRUSSEL-ZUID": [50.836, 4.335],
    "EVERGEM-BUNDEL ZANDEKEN": [51.121, 3.738],
    "EVERGEM": [51.108, 3.708],
    "FZNKN": [51.121, 3.738]
}

def speel_certus_animatie():
    if 'animatie_gespeeld' not in st.session_state:
        try:
            with open("logo.png", "rb") as f:
                b64_logo = base64.b64encode(f.read()).decode("utf-8")
            css_animatie = f"""
            <style>
            #splash-screen {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: #0e1117; z-index: 99999; display: flex; justify-content: center; align-items: center; animation: fadeOut 1.5s forwards; animation-delay: 2s; pointer-events: none; }}
            #splash-logo {{ width: 350px; animation: moveAndShrink 1.5s forwards; animation-delay: 1.5s; }}
            @keyframes fadeOut {{ 0% {{ opacity: 1; }} 100% {{ opacity: 0; visibility: hidden; }} }}
            @keyframes moveAndShrink {{ 0% {{ transform: scale(1) translate(0, 0); opacity: 1; }} 100% {{ transform: scale(0.3) translate(-100vw, -100vh); opacity: 0; }} }}
            </style>
            <div id="splash-screen"><img id="splash-logo" src="data:image/png;base64,{b64_logo}"></div>
            """
            st.markdown(css_animatie, unsafe_allow_html=True)
            st.session_state.animatie_gespeeld = True
        except: pass

speel_certus_animatie()

if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()

if "messages" not in st.session_state:
    st.session_state.messages = []

def genereer_word_rapport(df):
    doc = docx.Document()
    doc.add_heading('Certus Rail Solutions - Operationeel Rapport', 0)
    doc.add_paragraph(f"Gegenereerd op: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    doc.add_heading('1. Samenvatting', level=1)
    doc.add_paragraph(f"Totaal: {len(df)} ritten, {df['Afstand (km)'].sum():,.1f} km, {df['Gewicht (ton)'].sum():,.1f} ton.")
    f = BytesIO()
    doc.save(f)
    f.seek(0)
    return f

def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    bekende_treinen = set()
    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_match = re.search(r'(\d{5})', file.name)
            if t_nr_match: bekende_treinen.add(t_nr_match.group(1))

    for file in files:
        try:
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
                datum_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                
                clean_text = text.replace(' ', '').replace('\n', '')
                ruwe_nummers = re.findall(r'([1-9]\d{4})(?=\d{2}/\d{2}/\d{2,4})', clean_text)
                for bt in bekende_treinen:
                    if bt in clean_text and bt not in ruwe_nummers: ruwe_nummers.append(bt)
                
                nummers = list(set([n for n in ruwe_nummers if n not in {'1202', '1863', '1965', '3257'}]))
                km_match = re.search(r'(?:TreinKm|KmTrain|INFRABEL-net)[^\d]*(\d+(?:[.,]\d+)?)', text, re.IGNORECASE)
                afstand = float(km_match.group(1).replace(',', '.')) if km_match else 0.0
                
                route_match = re.search(r'([A-Z0-9.-]+)\s*->\s*([A-Z0-9.-]+)', text.upper())
                v_loc, a_loc = (route_match.group(1), route_match.group(2)) if route_match else ("Onbekend", "Onbekend")

                for t_nr in nummers:
                    treinen[t_nr] = {"Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, "Type": "Losse Rit", "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": "Nee", "Vertrek": v_loc, "Aankomst": a_loc}

            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file)
                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    excel_text = xl.to_string(index=False).upper()
                    un_match = re.search(r'\b(1202|1863|1965|3257)\b', excel_text)
                    for col in xl.columns: xl[col] = pd.to_numeric(xl[col].astype(str).str.replace(',', '.'), errors='coerce')
                    gewicht = xl.select_dtypes(include=['number']).max().max()
                    gewicht = float(gewicht) if pd.notnull(gewicht) and gewicht < 4000 else 0.0
                    
                    gevonden_locs = [loc for loc in LOCATIES_DB.keys() if loc in excel_text]
                    v_back, a_back = (gevonden_locs[0], gevonden_locs[-1]) if gevonden_locs else ("Onbekend", "Onbekend")

                    if t_nr in treinen:
                        treinen[t_nr].update({"Gewicht (ton)": gewicht, "Type": "Ledige Rit" if gewicht < 450 else "Beladen Rit", "RID": "Ja" if un_match else "Nee"})
                        if treinen[t_nr]["Vertrek"] == "Onbekend":
                            treinen[t_nr]["Vertrek"], treinen[t_nr]["Aankomst"] = v_back, a_back
                    else:
                        treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": gewicht, "RID": "Ja" if un_match else "Nee", "Vertrek": v_back, "Aankomst": a_back}
        except Exception as e: st.error(f"Fout bij {file.name}: {e}")
    return pd.DataFrame(list(treinen.values()))

with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    if st.button("🗑️ Wis Data"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
    keuze = st.radio("Menu:", ("🏠 Dashboard", "📄 Invoer", "🖨️ Rapport", "💬 AI Assistent"))

if keuze == "🏠 Dashboard":
    st.title("📊 Overzicht")
    df = st.session_state.df_ritten
    if not df.empty:
        st.metric("Totaal km", f"{df['Afstand (km)'].sum():,.1f} km")
        m = folium.Map(location=[51.05, 3.71], zoom_start=8, tiles="CartoDB dark_matter")
        for i, r in df.iterrows():
            if r['Vertrek'] in LOCATIES_DB: folium.Marker(LOCATIES_DB[r['Vertrek']], icon=folium.Icon(color='green')).add_to(m)
            if r['Aankomst'] in LOCATIES_DB: folium.Marker(LOCATIES_DB[r['Aankomst']], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, height=400, use_container_width=True)
    else: st.info("Geen data.")

elif keuze == "📄 Invoer":
    st.title("📄 Data")
    gekozen_project = st.text_input("Project:", value="P420")
    files = st.file_uploader("Upload", accept_multiple_files=True)
    if files and st.button("🚀 Verwerk"):
        st.session_state.df_ritten = analyseer_bestanden(files, gekozen_project)
        st.rerun()
    st.dataframe(st.session_state.df_ritten)

elif keuze == "💬 AI Assistent":
    st.title("🤖 Certus AI")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if prompt := st.chat_input("Vraag iets..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            ctx = st.session_state.df_ritten.to_csv(index=False) if not st.session_state.df_ritten.empty else "Geen data."
            resp = model.generate_content(f"Data: {ctx}\n\nVraag: {prompt}")
            st.markdown(resp.text)
            st.session_state.messages.append({"role": "assistant", "content": resp.text})
