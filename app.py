import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import RequestOptions

st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- AI CONFIGURATIE (STRICTE VERSIE) ---
API_KEY = "AIzaSyDGvPTbF1_s_PmUMqOhBr2BjVYVk6aS1Zg"
genai.configure(api_key=API_KEY)

# We gebruiken de stabiele 'gemini-1.5-flash' met een geforceerde stabiele API-versie
model = genai.GenerativeModel('gemini-1.5-flash')

# --- LOCATIES DATABASE (Nu met de codes uit jouw ritten) ---
LOCATIES_DB = {
    "GENT-ZEEH": [51.134, 3.823],
    "GENT-ZEEHAVEN": [51.134, 3.823],
    "FGZH": [51.134, 3.823],
    "VERB.GTS": [51.145, 3.815],
    "EVERGEM-BUNDEL ZANDEKEN": [51.121, 3.738],
    "FZNKN": [51.121, 3.738]
}

if 'df_ritten' not in st.session_state: st.session_state.df_ritten = pd.DataFrame()
if "messages" not in st.session_state: st.session_state.messages = []

def analyseer_bestanden(files, proj):
    treinen = {}
    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_m = re.search(r'(\d{5})', file.name)
            if t_nr_m:
                t_nr = t_nr_m.group(1)
                xl = pd.read_excel(file)
                txt = xl.to_string().upper()
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
    return pd.DataFrame(list(treinen.values()))

# --- INTERFACE ---
with st.sidebar:
    st.title("🚂 Certus Rail")
    if st.button("🗑️ Reset Alles"):
        st.session_state.df_ritten = pd.DataFrame()
        st.session_state.messages = []
        st.rerun()
    menu = st.radio("Menu:", ["📊 Dashboard", "📄 Invoer", "💬 AI Assistent"])

if menu == "📊 Dashboard":
    st.title("📊 Actueel Overzicht")
    st.dataframe(st.session_state.df_ritten, use_container_width=True)

elif menu == "📄 Invoer":
    st.title("📄 Data Invoer")
    files = st.file_uploader("Upload bestanden", accept_multiple_files=True)
    if files and st.button("🚀 Verwerk"):
        st.session_state.df_ritten = analyseer_bestanden(files, "P420")
        st.rerun()

elif menu == "💬 AI Assistent":
    st.title("🤖 Certus AI")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if p := st.chat_input("Vraag iets..."):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            try:
                ctx = st.session_state.df_ritten.to_csv(index=False)
                # We forceren hier de v1 versie ipv v1beta
                response = model.generate_content(
                    f"Data: {ctx}\n\nVraag: {p}",
                    request_options=RequestOptions(api_version='v1')
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Connectie-check: {str(e)}")
