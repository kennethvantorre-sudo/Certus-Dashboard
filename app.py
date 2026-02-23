import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime
import base64

# 🎨 1. PAGINA INSTELLINGEN
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- ✨ MAGISCHE START ANIMATIE ✨ ---
def speel_certus_animatie():
    try:
        # We laden het logo in als een ruwe code zodat we het kunnen animeren
        with open("logo.png", "rb") as f:
            data = f.read()
            b64_logo = base64.b64encode(data).decode("utf-8")
            
        # Hier is de verborgen CSS code die de animatie aanstuurt
        css_animatie = f"""
        <style>
        #splash-screen {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-color: #0e1117; /* Streamlit donkere achtergrond */
            z-index: 99999;
            display: flex;
            justify-content: center;
            align-items: center;
            animation: fadeOut 1.5s forwards;
            animation-delay: 2s; /* Blijft eerst 2 seconden mooi in het midden staan */
            pointer-events: none;
        }}
        #splash-logo {{
            width: 350px; /* Lekker groot in het midden */
            animation: moveAndShrink 1.5s forwards;
            animation-delay: 1.5s; /* Begint te krimpen na 1.5s */
        }}
        
        /* Het scherm verdwijnt */
        @keyframes fadeOut {{
            0% {{ opacity: 1; }}
            100% {{ opacity: 0; visibility: hidden; }}
        }}
        
        /* Het logo krimpt en vliegt naar linksboven (de zijbalk) */
        @keyframes moveAndShrink {{
            0% {{ transform: scale(1) translate(0, 0); opacity: 1; }}
            100% {{ transform: scale(0.3) translate(-100vw, -100vh); opacity: 0; }}
        }}
        </style>
        <div id="splash-screen">
            <img id="splash-logo" src="data:image/png;base64,{b64_logo}">
        </div>
        """
        st.markdown(css_animatie, unsafe_allow_html=True)
    except Exception as e:
        pass # Als het logo even niet gevonden wordt, crasht de app niet

# Roep de animatie aan!
speel_certus_animatie()
# ------------------------------------

# 🧠 2. GEHEUGEN & OPSCHONING
if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()

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
                    
                    # Nummers vissen
                    nummers = re.findall(r'(\d{5})\s+\d{2}/\d{2}/\d{2}', text)
                    
                    # KM scanner
                    km_match = re.search(r'(?:TreinKm|KmTrain|INFRABEL-net).*?(\d+(?:,\d+)?)', text, re.IGNORECASE)
                    afstand = float(km_match.group(1).replace(',', '.')) if km_match else 16.064
                    
                    for t_nr in set(nummers):
                        is_rid = "Ja" if "RID: Oui / Ja" in text or "1202" in text else "Nee"
                        treinen[t_nr] = {
                            "Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, 
                            "Type": "Ledige Rit" if t_nr.endswith('1') else "Beladen Rit",
                            "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": is_rid, "UN": "1202" if is_rid == "Ja" else ""
                        }

            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file, engine='openpyxl')
                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    # We negeren het getal 1202 bij de gewichtsmeting!
                    num_data = xl.select_dtypes(include=['number'])
                    zuivere_data = num_data[num_data != 1202]
                    gewicht = zuivere_data.max().max()
                    
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    if t_nr in treinen: treinen[t_nr].update({"Gewicht (ton)": gewicht})
        except: pass
    return pd.DataFrame(list(treinen.values()))

# --- DASHBOARD LAYOUT ---
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "⛽ Invoer Brandstof"))

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - 2026")
    df = st.session_state.df_ritten
    if not df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treinen", len(df))
        c2.metric("Totaal Ton", f"{df['Gewicht (ton)'].sum():,.1f}")
        c3.metric("Km Infrabel", f"{df['Afstand (km)'].sum():,.2f}")
        c4.metric("RID Ritten", len(df[df['RID'] == 'Ja']))
        st.plotly_chart(px.bar(df, x='Trein', y='Gewicht (ton)', color='Type', barmode='group', template="plotly_dark"), use_container_width=True)
    else: st.info("Geen data. Upload bestanden bij 'Invoer Ritten'.")

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam:", value="P419")
    uploaded_files = st.file_uploader("Upload PDF's & Excel", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    if uploaded_files and st.button("🚀 Verwerk bestanden"):
        nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
        st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
        st.success("Data bijgewerkt met RID-check!")
        st.rerun()
    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Database")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
