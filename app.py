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

# --- AI CONFIGURATIE ---
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

if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()
if "messages" not in st.session_state:
    st.session_state.messages = []

def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    bekende_nrs = set()

    # 1. EXCEL SCAN (Tonnages & Basis)
    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_match = re.search(r'(\d{5})', file.name)
            if t_nr_match:
                t_nr = t_nr_match.group(1)
                bekende_nrs.add(t_nr)
                xl = pd.read_excel(file)
                excel_text = xl.to_string(index=False).upper()
                
                for col in xl.columns: xl[col] = pd.to_numeric(xl[col].astype(str).str.replace(',', '.'), errors='coerce')
                gewicht = xl.select_dtypes(include=['number']).max().max()
                gewicht = float(gewicht) if pd.notnull(gewicht) and gewicht < 4000 else 0.0
                
                gevonden_locs = [loc for loc in LOCATIES_DB.keys() if loc in excel_text]
                v_loc = gevonden_locs[0] if gevonden_locs else "Onbekend"
                a_loc = gevonden_locs[-1] if len(gevonden_locs) > 1 else v_loc
                
                treinen[t_nr] = {
                    "Datum": datetime.today().strftime('%Y-%m-%d'),
                    "Project": gekozen_project, "Trein": t_nr,
                    "Type": "Ledige Rit" if gewicht < 450 else "Beladen Rit",
                    "Afstand (km)": 0.0, "Gewicht (ton)": gewicht,
                    "RID": "Ja" if "1863" in excel_text else "Nee",
                    "Vertrek": v_loc, "Aankomst": a_loc
                }

    # 2. PDF SCAN (Kilometers koppelen)
    for file in files:
        if file.name.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            full_text = "".join([p.extract_text() for p in reader.pages])
            clean_text = full_text.replace(' ', '').replace('\n', '')
            
            km_m = re.search(r'(?:KmTrain|TreinKm|INFRABEL-net)[^\d]*(\d+(?:[.,]\d+)?)', full_text, re.IGNORECASE)
            afstand = float(km_m.group(1).replace(',', '.')) if km_m else 0.0
            
            for t_nr in bekende_nrs:
                if t_nr in clean_text:
                    if t_nr in treinen:
                        treinen[t_nr]["Afstand (km)"] = afstand
                        d_m = re.search(r'(\d{2})/(\d{2})/(\d{4})', full_text)
                        if d_m: treinen[t_nr]["Datum"] = f"{d_m.group(3)}-{d_m.group(2)}-{d_m.group(1)}"

    return pd.DataFrame(list(treinen.values()))

with st.sidebar:
    st.title("🚂 Certus Rail")
    if st.button("🗑️ Reset Alles"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
    keuze = st.radio("Menu", ["🏠 Dashboard", "📄 Invoer", "💬 AI Assistent"])

if keuze == "🏠 Dashboard":
    st.title("📊 Dashboard")
    df = st.session_state.df_ritten
    if not df.empty:
        st.metric("Totaal km", f"{df['Afstand (km)'].sum():,.1f}")
        st.dataframe(df, use_container_width=True)
    else: st.info("Geen data.")

elif keuze == "📄 Invoer":
    st.title("📄 Invoer")
    files = st.file_uploader("Upload bestanden", accept_multiple_files=True)
    if files and st.button("🚀 Start Analyse"):
        st.session_state.df_ritten = analyseer_bestanden(files, "P420")
        st.rerun()

elif keuze == "💬 AI Assistent":
    st.title("🤖 Certus AI")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if prompt := st.chat_input("Vraag iets..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            try:
                ctx = st.session_state.df_ritten.to_csv(index=False) if not st.session_state.df_ritten.empty else "Geen ritten geladen."
                response = model.generate_content(f"Context: {ctx}\n\nGebruiker zegt: {prompt}")
                msg = response.text
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception as e:
                st.error(f"Fout: {str(e)}")
