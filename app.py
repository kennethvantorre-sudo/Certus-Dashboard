import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
from datetime import datetime
import google.generativeai as genai

# --- PAGINA CONFIG ---
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- AI CONFIGURATIE (DE DEFINITIEVE FIX) ---
API_KEY = "AIzaSyDGvPTbF1_s_PmUMqOhBr2BjVYVk6aS1Zg"
genai.configure(api_key=API_KEY)

# We gebruiken de 'latest' versie om de v1beta fout te voorkomen
model = genai.GenerativeModel('gemini-1.5-flash-latest') 

# --- DATABASE LOCATIES ---
LOCATIES_DB = {
    "GENT-ZEEH": [51.134, 3.823],
    "GENT-ZEEHAVEN": [51.134, 3.823],
    "FGZH": [51.134, 3.823],
    "VERB.GTS": [51.145, 3.815],
    "ANTWERPEN-NOORD": [51.275, 4.433],
    "EVERGEM-BUNDEL ZANDEKEN": [51.121, 3.738],
    "FZNKN": [51.121, 3.738]
}

if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()
if "messages" not in st.session_state:
    st.session_state.messages = []

def analyseer_bestanden(files, proj):
    treinen = {}
    bekende_nrs = set()

    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_m = re.search(r'(\d{5})', file.name)
            if t_nr_m:
                t_nr = t_nr_m.group(1)
                bekende_nrs.add(t_nr)
                xl = pd.read_excel(file)
                txt = xl.to_string().upper()
                
                # Gewicht & Locatie
                for c in xl.columns: xl[c] = pd.to_numeric(xl[c].astype(str).str.replace(',', '.'), errors='coerce')
                gew = xl.select_dtypes(include=['number']).max().max()
                gew = float(gew) if pd.notnull(gew) and gew < 4000 else 0.0
                
                locs = [l for l in LOCATIES_DB.keys() if l in txt]
                v, a = (locs[0], locs[-1]) if locs else ("Onbekend", "Onbekend")
                
                treinen[t_nr] = {
                    "Datum": datetime.today().strftime('%Y-%m-%d'), "Project": proj, "Trein": t_nr,
                    "Type": "Ledig" if gew < 450 else "Beladen", "Afstand (km)": 0.0, 
                    "Gewicht (ton)": gew, "RID": "Ja" if "1863" in txt else "Nee", "Vertrek": v, "Aankomst": a
                }

    for file in files:
        if file.name.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file)
            full_txt = "".join([p.extract_text() for p in reader.pages])
            clean_txt = full_txt.replace(' ', '').replace('\n', '')
            
            km_m = re.search(r'(?:KmTrain|TreinKm|INFRABEL-net)[^\d]*(\d+(?:[.,]\d+)?)', full_txt, re.IGNORECASE)
            km = float(km_m.group(1).replace(',', '.')) if km_m else 0.0
            
            for t_nr in bekende_nrs:
                if t_nr in clean_txt and t_nr in treinen:
                    treinen[t_nr]["Afstand (km)"] = km

    return pd.DataFrame(list(treinen.values()))

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚂 Certus Rail")
    if st.button("🗑️ Reset Systeem"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
    menu = st.radio("Ga naar:", ["📊 Dashboard", "📄 Invoer", "💬 AI Assistent"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Actueel Overzicht")
    if not st.session_state.df_ritten.empty:
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
    else: st.info("Geen data beschikbaar.")

# --- INVOER ---
elif menu == "📄 Invoer":
    st.title("📄 Data Invoer")
    files = st.file_uploader("Upload wagonlijsten en BNX", accept_multiple_files=True)
    if files and st.button("🚀 Start Verwerking"):
        st.session_state.df_ritten = analyseer_bestanden(files, "P420")
        st.rerun()

# --- AI CHAT ---
elif menu == "💬 AI Assistent":
    st.title("🤖 Certus AI")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if p := st.chat_input("Vraag iets aan de AI..."):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        
        with st.chat_message("assistant"):
            try:
                data_ctx = st.session_state.df_ritten.to_csv(index=False) if not st.session_state.df_ritten.empty else "Geen data."
                # Direct aanroepen zonder extra config om v1beta te omzeilen
                res = model.generate_content(f"Data: {data_ctx}\n\nGebruiker: {p}")
                st.markdown(res.text)
                st.session_state.messages.append({"role": "assistant", "content": res.text})
            except Exception as e:
                st.error(f"AI Connectie fout: {str(e)}")
