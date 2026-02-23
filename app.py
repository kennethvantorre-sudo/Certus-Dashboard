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
    # We zorgen dat de animatie alleen de allereerste keer afspeelt
    if 'animatie_gespeeld' not in st.session_state:
        try:
            with open("logo.png", "rb") as f:
                data = f.read()
                b64_logo = base64.b64encode(data).decode("utf-8")
                
            css_animatie = f"""
            <style>
            #splash-screen {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background-color: #0e1117;
                z-index: 99999;
                display: flex;
                justify-content: center;
                align-items: center;
                animation: fadeOut 1.5s forwards;
                animation-delay: 2s;
                pointer-events: none;
            }}
            #splash-logo {{
                width: 350px;
                animation: moveAndShrink 1.5s forwards;
                animation-delay: 1.5s;
            }}
            
            @keyframes fadeOut {{
                0% {{ opacity: 1; }}
                100% {{ opacity: 0; visibility: hidden; }}
            }}
            
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
            st.session_state.animatie_gespeeld = True 
            
        except Exception as e:
            # Als hij hem niet vindt, geeft hij een melding bovenaan
            st.error(f"⚠️ Animatie tip: Ik kan het bestand 'logo.png' niet vinden in GitHub. Zorg dat het plaatje exact 'logo.png' heet (zonder hoofdletters). Foutmelding: {e}")

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
                    if not nummers: nummers = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                    
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
                
                # Check of dit een oud Certus Archief is (om data te herstellen)
                if 'Trein' in xl.columns and 'Project' in xl.columns:
                    st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, xl]).drop_duplicates(subset=['Trein'], keep='last')
                    continue

                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    # We negeren het getal 1202 bij de gewichtsmeting!
                    num_data = xl.select_dtypes(include=['number'])
                    zuivere_data = num_data[num_data != 1202]
                    gewicht = zuivere_data.max().max()
                    
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    if t_nr in treinen: treinen[t_nr].update({"Gewicht (ton)": gewicht})
                    else: treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": "Beladen Rit", "Afstand (km)": 0.0, "Gewicht (ton)": gewicht, "RID": "Nee", "UN": ""}
        except: pass
    return pd.DataFrame(list(treinen.values()))

# --- DASHBOARD LAYOUT ---
with st.sidebar:
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten"))

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
    else: st.info("Geen data. Upload bestanden of herstel je archief bij 'Invoer Ritten'.")
    
    # Extra logo op de homepagina voor de afwerking
    try:
        col_l, col_m, col_r = st.columns([2, 3, 2])
        with col_m:
            st.image("logo.png", use_container_width=True)
    except: pass

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam:", value="P419")
    uploaded_files = st.file_uploader("Upload PDF's & Excel", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    if uploaded_files and st.button("🚀 Verwerk bestanden"):
        nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
        if not nieuw_df.empty:
            st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
        st.success("Data succesvol verwerkt!")
        st.rerun()
    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Database")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Archief", data=output.getvalue(), file_name=f"Certus_Master_Data.xlsx")
