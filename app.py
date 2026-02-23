import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime
import base64
import docx
from docx.shared import Inches, Pt
import folium
from streamlit_folium import st_folium

# 🎨 1. PAGINA INSTELLINGEN
st.set_page_config(page_title="Certus Command Center", page_icon="🚂", layout="wide")

# --- ✨ MAGISCHE START ANIMATIE ✨ ---
def speel_certus_animatie():
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
            st.warning(f"⚠️ Animatie tip: Ik kan 'logo.png' niet vinden. Zorg dat het exact zo heet in GitHub.")

speel_certus_animatie()
# ------------------------------------

# 🧠 2. GEHEUGEN & OPSCHONING
if 'df_ritten' not in st.session_state:
    st.session_state.df_ritten = pd.DataFrame()

# 📝 3. WORD RAPPORTAGE GENERATOR
def genereer_word_rapport(df):
    doc = docx.Document()
    titel = doc.add_heading('Certus Rail Solutions - Operationeel Rapport', 0)
    titel.alignment = 1 
    doc.add_paragraph(f"Gegenereerd op: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    
    doc.add_heading('1. Samenvatting van de Prestaties', level=1)
    tot_km = df['Afstand (km)'].sum()
    tot_ton = df['Gewicht (ton)'].sum()
    tot_ritten = len(df)
    
    p = doc.add_paragraph()
    p.add_run(f"In deze periode zijn er in totaal ").bold = False
    p.add_run(f"{tot_ritten} ritten").bold = True
    p.add_run(f" uitgevoerd, met een totale afstand van ").bold = False
    p.add_run(f"{tot_km:,.1f} kilometer").bold = True
    p.add_run(f" op het Infrabel netwerk. Het totale getransporteerde gewicht bedraagt ").bold = False
    p.add_run(f"{tot_ton:,.1f} ton.").bold = True
    
    doc.add_heading('2. Rittenspecificatie per Project', level=1)
    tabel = doc.add_table(rows=1, cols=6)
    tabel.style = 'Table Grid'
    hdr_cells = tabel.rows[0].cells
    hdr_cells[0].text = 'Datum'
    hdr_cells[1].text = 'Project'
    hdr_cells[2].text = 'Trein Nr.'
    hdr_cells[3].text = 'Type Rit'
    hdr_cells[4].text = 'Afstand (km)'
    hdr_cells[5].text = 'Gewicht (ton)'
    
    for index, row in df.iterrows():
        row_cells = tabel.add_row().cells
        row_cells[0].text = str(row['Datum'])
        row_cells[1].text = str(row['Project'])
        row_cells[2].text = str(row['Trein'])
        row_cells[3].text = str(row['Type'])
        row_cells[4].text = f"{row['Afstand (km)']:.1f}"
        row_cells[5].text = f"{row['Gewicht (ton)']:.1f}"

    doc.add_paragraph("\nCertus Rail Solutions - Vertrouwelijk")
    f = BytesIO()
    doc.save(f)
    f.seek(0)
    return f

# ⚙️ 4. DE MOTOR: PDF & EXCEL ANALYSE
def analyseer_bestanden(files, gekozen_project):
    treinen = {}
    
    for file in files:
        try:
            # --- BNX ANALYSE (PDF) ---
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = "".join([page.extract_text() for page in reader.pages])
                if "Infrabel" in text:
                    datum_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                    datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                    
                    # OPLOSSING: We forceren een scheiding (spaties) tussen datums en de rest van de tekst.
                    text_clean = re.sub(r'([0-3]\d/[0-1]\d/\d{2,4})', r' \1 ', text)
                    
                    # We pakken elk 5-cijferig getal dat NIET is omringd door andere cijfers (zoals 10-cijferige dossiernummers)
                    mogelijke_nummers = re.findall(r'(?<!\d)([1-9]\d{4})(?!\d)', text_clean)
                    
                    # Filter UN codes eruit zodat die niet als treinnummer worden gezien
                    un_codes = {'1202', '1863', '1965', '3257', '1203', '1170', '3082'}
                    nummers = list(set([n for n in mogelijke_nummers if n not in un_codes]))
                    
                    km_match = re.search(r'(?:TreinKm|KmTrain|INFRABEL-net).*?(\d+(?:,\d+)?)', text, re.IGNORECASE)
                    afstand = float(km_match.group(1).replace(',', '.')) if km_match else 16.064
                    
                    for t_nr in nummers:
                        is_rid = "Ja" if re.search(r'RID:\s*Oui\s*/\s*Ja', text, re.IGNORECASE) or "1202" in text or "1863" in text else "Nee"
                        
                        if t_nr in treinen:
                            treinen[t_nr]["Afstand (km)"] = afstand
                            treinen[t_nr]["Datum"] = datum_str
                            if is_rid == "Ja": treinen[t_nr]["RID"] = "Ja"
                        else:
                            treinen[t_nr] = {
                                "Datum": datum_str, "Project": gekozen_project, "Trein": t_nr, 
                                "Type": "Losse Rit", 
                                "Afstand (km)": afstand, "Gewicht (ton)": 0.0, "RID": is_rid, "UN": ""
                            }

            # --- EXCEL WAGONLIJST ANALYSE ---
            elif file.name.lower().endswith(('.xlsx', '.xls')):
                xl = pd.read_excel(file)
                
                if 'Trein' in xl.columns and 'Project' in xl.columns:
                    st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, xl]).drop_duplicates(subset=['Trein'], keep='last')
                    continue

                t_nr_match = re.search(r'(\d{5})', file.name)
                if t_nr_match:
                    t_nr = t_nr_match.group(1)
                    
                    excel_text = xl.to_string(index=False)
                    un_match = re.search(r'\b(1202|1863|1965|3257|1203|1170|3082)\b', excel_text)
                    un_code = un_match.group(1) if un_match else ""

                    for col in xl.columns:
                        xl[col] = pd.to_numeric(xl[col].astype(str).str.replace(',', '.'), errors='coerce')
                    
                    num_data = xl.select_dtypes(include=['number'])
                    zuivere_data = num_data[~num_data.isin([1202, 1863, 1965, 3257, 1203, 1170, 3082])]
                    realistische_waarden = zuivere_data[zuivere_data < 4000]
                    gewicht = realistische_waarden.max().max()
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    
                    is_ledig = t_nr.endswith('1') or t_nr.endswith('3') or gewicht < 450
                    type_rit = "Ledige Rit" if is_ledig else "Beladen Rit"
                    
                    if t_nr in treinen: 
                        treinen[t_nr]["Gewicht (ton)"] = gewicht
                        treinen[t_nr]["Type"] = type_rit
                        if un_code: 
                            treinen[t_nr]["UN"] = un_code
                            treinen[t_nr]["RID"] = "Ja"
                    else: 
                        treinen[t_nr] = {"Datum": datetime.today().strftime('%Y-%m-%d'), "Project": gekozen_project, "Trein": t_nr, "Type": type_rit, "Afstand (km)": 0.0, "Gewicht (ton)": gewicht, "RID": "Ja" if un_code else "Nee", "UN": un_code}
        except Exception as e: 
            st.error(f"Fout bij het lezen van bestand {file.name}: {e}")
            
    return pd.DataFrame(list(treinen.values()))

# --- DASHBOARD LAYOUT ---
with st.sidebar:
    st.image("logo.png", width=180)
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "🖨️ Rapportage"))

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - Certus")
    df = st.session_state.df_ritten
    
    if not df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treinen Totaal", len(df))
        c2.metric("Km Met Last", f"{df[df['Type'] == 'Beladen Rit']['Afstand (km)'].sum():,.1f} km")
        c3.metric("Km Losse/Ledig", f"{df[df['Type'].isin(['Losse Rit', 'Ledige Rit'])]['Afstand (km)'].sum():,.1f} km")
        c4.metric("Totaal Tonnage", f"{df['Gewicht (ton)'].sum():,.1f} t")
        
        st.markdown("---")
        
        col_grafiek, col_kaart = st.columns([1.5, 1])
        with col_grafiek:
            st.write("### 🏆 Prestaties per Project")
            fig = px.bar(df, x='Project', y='Afstand (km)', color='Type', barmode='group', template="plotly_dark", title="Kilometers per Project")
            st.plotly_chart(fig, use_container_width=True)
            
        with col_kaart:
            st.write("### 🗺️ Sporenkaart")
            m = folium.Map(location=[51.05, 3.71], zoom_start=8, tiles="CartoDB dark_matter")
            folium.Marker([51.13, 3.82], popup="Gent-Zeehaven", icon=folium.Icon(color='red', icon='train', prefix='fa')).add_to(m)
            folium.Marker([51.27, 4.38], popup="Antwerpen-Noord", icon=folium.Icon(color='red', icon='train', prefix='fa')).add_to(m)
            folium.Marker([51.32, 3.20], popup="Zeebrugge", icon=folium.Icon(color='red', icon='train', prefix='fa')).add_to(m)
            st_folium(m, height=400, use_container_width=True)
    else: 
        st.info("Geen data beschikbaar. Ga in het menu links naar 'Invoer Ritten' om bestanden te uploaden.")

elif keuze == "📄 Invoer Ritten":
    st.title("📄 Data Invoeren")
    gekozen_project = st.text_input("Projectnaam (dit wordt je onzichtbare map):", value="P419")
    uploaded_files = st.file_uploader("Upload Infrabel BNX (PDF) en Wagonlijsten (Excel)", type=["pdf", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files and st.button("🚀 Verwerk bestanden"):
        nieuw_df = analyseer_bestanden(uploaded_files, gekozen_project)
        if not nieuw_df.empty:
            st.session_state.df_ritten = pd.concat([st.session_state.df_ritten, nieuw_df]).drop_duplicates(subset=['Trein'], keep='last')
        st.success("Data succesvol verwerkt en gekoppeld!")
        st.rerun()
        
    if not st.session_state.df_ritten.empty:
        st.write("### 🗄️ Database")
        st.dataframe(st.session_state.df_ritten, use_container_width=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_ritten.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Archief", data=output.getvalue(), file_name=f"Certus_Master_Data.xlsx")

elif keuze == "🖨️ Rapportage":
    st.title("🖨️ Rapportage Generator")
    st.write("Genereer hier het formele Certus projectrapport.")
    
    if not st.session_state.df_ritten.empty:
        st.dataframe(st.session_state.df_ritten.head(3), use_container_width=True)
        word_file = genereer_word_rapport(st.session_state.df_ritten)
        
        st.download_button(
            label="📄 Download Officieel Word Rapport",
            data=word_file,
            file_name=f"Certus_Rapportage_{datetime.now().strftime('%d%m%Y')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    else:
        st.warning("Er is nog geen data om een rapport van te maken.")
