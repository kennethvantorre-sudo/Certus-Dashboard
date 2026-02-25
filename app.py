import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
from datetime import datetime
import google.generativeai as genai
import docx

st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- AI CONFIGURATIE ---
API_KEY = "AIzaSyDGvPTbF1_s_PmUMqOhBr2BjVYVk6aS1Zg"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- LOCATIE DATABASE ---
LOCATIES_DB = {
    "GENT-ZEEH": [51.134, 3.823], "GENT-ZEEHAVEN": [51.134, 3.823], "FGZH": [51.134, 3.823],
    "VERB.GTS": [51.145, 3.815], "ANTWERPEN-NOORD": [51.275, 4.433],
    "EVERGEM-BUNDEL ZANDEKEN": [51.121, 3.738], "FZNKN": [51.121, 3.738]
}

if 'df_ritten' not in st.session_state: st.session_state.df_ritten = pd.DataFrame()
if "messages" not in st.session_state: st.session_state.messages = []

def genereer_word_rapport(df):
    doc = docx.Document()
    doc.add_heading('Certus Rail Solutions - Operationeel Rapport', 0)
    doc.add_paragraph(f"Gegenereerd op: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    tabel = doc.add_table(rows=1, cols=6)
    tabel.style = 'Table Grid'
    hdr = tabel.rows[0].cells
    for i, t in enumerate(['Datum', 'Trein', 'Type', 'Afstand (km)', 'Gewicht (ton)', 'RID']): hdr[i].text = t
    for _, row in df.iterrows():
        rc = tabel.add_row().cells
        rc[0].text, rc[1].text, rc[2].text = str(row['Datum']), str(row['Trein']), str(row['Type'])
        rc[3].text, rc[4].text, rc[5].text = f"{row['Afstand (km)']:.1f}", f"{row['Gewicht (ton)']:.1f}", str(row['RID'])
    f = BytesIO(); doc.save(f); f.seek(0)
    return f

def analyseer_bestanden(files, proj):
    treinen = {}
    bekende_nrs = set()
    for file in files:
        if file.name.lower().endswith(('.xlsx', '.xls')):
            t_nr_m = re.search(r'(\d{5})', file.name)
            if t_nr_m:
                t_nr = t_nr_m.group(1); bekende_nrs.add(t_nr)
                xl = pd.read_excel(file); txt = xl.to_string().upper()
                for c in xl.columns: xl[c] = pd.to_numeric(xl[c].astype(str).str.replace(',', '.'), errors='coerce')
                gew = xl.select_dtypes(include=['number']).max().max()
                gew = float(gew) if pd.notnull(gew) and gew < 4000 else 0.0
                locs = [l for l in LOCATIES_DB.keys() if l in txt]
                v, a = (locs[0], locs[-1]) if locs else ("Onbekend", "Onbekend")
                treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": proj, "Trein": t_nr, "Type": "Ledig" if gew < 450 else "Beladen", "Afstand (km)": 0.0, "Gewicht (ton)": gew, "RID": "Ja" if "1863" in txt else "Nee", "Vertrek": v, "Aankomst": a}
    for file in files:
        if file.name.lower().endswith('.pdf'):
            reader = PyPDF2.PdfReader(file); full_txt = "".join([p.extract_text() for p in reader.pages])
            km_m = re.search(r'(?:KmTrain|TreinKm|INFRABEL-net)[^\d]*(\d+(?:[.,]\d+)?)', full_txt, re.IGNORECASE)
            km = float(km_m.group(1).replace(',', '.')) if km_m else 0.0
            for t_nr in bekende_nrs:
                if t_nr in full_txt.replace(' ', '') and t_nr in treinen: treinen[t_nr]["Afstand (km)"] = km
    return pd.DataFrame(list(treinen.values()))

with st.sidebar:
    st.title("Certus Rail")
    if st.button("Wis Data & Chat"):
        st.session_state.df_ritten = pd.DataFrame(); st.session_state.messages = []; st.rerun()
    menu = st.radio("Menu:", ["Dashboard", "Invoer Ritten", "Rapportage", "AI Assistent"])

if menu == "Dashboard":
    st.title("Actueel Overzicht")
    if not st.session_state.df_ritten.empty: st.dataframe(st.session_state.df_ritten, use_container_width=True)
    else: st.info("Geen data.")

elif menu == "Invoer Ritten":
    st.title("Data Invoeren")
    files = st.file_uploader("Upload wagonlijsten/BNX", accept_multiple_files=True)
    if files and st.button("Verwerk ritten"):
        st.session_state.df_ritten = analyseer_bestanden(files, "P420"); st.rerun()
    st.dataframe(st.session_state.df_ritten)

elif menu == "Rapportage":
    st.title("Word Rapportage")
    if not st.session_state.df_ritten.empty:
        st.download_button("Download Rapport", data=genereer_word_rapport(st.session_state.df_ritten), file_name="Certus_Rapport.docx")
    else: st.warning("Eerst ritten invoeren.")

elif menu == "AI Assistent":
    st.title("AI Assistent")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if p := st.chat_input("Vraag iets..."):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            try:
                ctx = st.session_state.df_ritten.to_csv(index=False)
                res = model.generate_content(f"Data: {ctx}\n\nVraag: {p}")
                st.markdown(res.text); st.session_state.messages.append({"role": "assistant", "content": res.text})
            except Exception as e: st.error(f"AI tijdelijk onbereikbaar: {str(e)}")
