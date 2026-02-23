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
            # --- BNX ANALYSE ---
            if file.name.lower().endswith('.pdf'):
                reader = PyPDF2.PdfReader(file)
                text = "".join([page.extract_text() for page in reader.pages])
                if "Infrabel" in text:
                    datum_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                    datum_str = f"{datum_match.group(3)}-{datum_match.group(2)}-{datum_match.group(1)}" if datum_match else datetime.today().strftime('%Y-%m-%d')
                    
                    # OPLOSSING 1: Flexibele scanner voor nummers (vangt nu ook enters en spaties op)
                    nummers = re.findall(r'(\d{5})\s*[\n\r]+\s*\d{2}/\d{2}/\d{2}', text)
                    if not nummers: nummers = re.findall(r'(\d{5})\s+\d{2}/\d{2}/\d{2}', text)
                    if not nummers: nummers = re.findall(r'^\s*(\d{5})\s*$', text, re.MULTILINE)
                    
                    km_match = re.search(r'(?:TreinKm|KmTrain|INFRABEL-net).*?(\d+(?:,\d+)?)', text, re.IGNORECASE)
                    afstand = float(km_match.group(1).replace(',', '.')) if km_match else 16.064
                    
                    for t_nr in set(nummers):
                        is_rid = "Ja" if re.search(r'RID:\s*Oui\s*/\s*Ja', text, re.IGNORECASE) or "1202" in text or "1863" in text else "Nee"
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
                    
                    # OPLOSSING 2: Zoek blind in heel de Excel naar UN nummers (ongeacht de rij!)
                    excel_text = xl.to_string(index=False)
                    un_match = re.search(r'\b(1202|1863|1965|3257|1203|1170|3082)\b', excel_text)
                    un_code = un_match.group(1) if un_match else ""

                    # OPLOSSING 3: Zorg dat hij Belgische komma's als decimalen snapt en naar getallen omzet
                    for col in xl.columns:
                        xl[col] = pd.to_numeric(xl[col].astype(str).str.replace(',', '.'), errors='coerce')
                    
                    num_data = xl.select_dtypes(include=['number'])
                    zuivere_data = num_data[~num_data.isin([1202, 1863, 1965, 3257, 1203, 1170, 3082])]
                    realistische_waarden = zuivere_data[zuivere_data < 4000]
                    gewicht = realistische_waarden.max().max()
                    gewicht = float(gewicht) if pd.notnull(gewicht) else 0.0
                    
                    # Als de trein eindigt op een 1 of 3 (of onder 500 ton), is het vaak een ledige wagonrit
                    is_ledig = t_nr.endswith('1') or t_nr.endswith('3') or gewicht < 450
                    type_rit = "Ledige Rit" if is_ledig else "Beladen Rit"
                    
                    if t_nr in treinen: 
                        treinen[t_nr].update({"Gewicht (ton)": gewicht, "Type": type_rit})
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
    st.write("🚂 **Certus Rail Solutions**")
    keuze = st.radio("Menu:", ("🏠 Home (Dashboard)", "📄 Invoer Ritten", "🖨️ Rapportage"))

if keuze == "🏠 Home (Dashboard)":
    st.title("📊 Actueel Overzicht - Certus")
    df = st.session_state.df_ritten
    
    if not df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Treinen Totaal", len(df))
        c2.metric("Km Met Last", f"{df[df['Type'] == 'Beladen Rit']['Afstand (km)'].sum():,.1f} km")
        c3.metric("Km Losse Ritten", f"{df[df['Type'] == 'Losse Rit']['Afstand (km)'].sum():,.1f} km")
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
        st.info("Geen data beschikbaar. Upload je bestanden of herstel je archief bij 'Invoer Ritten'.")

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
