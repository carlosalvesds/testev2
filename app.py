# importar as bibliotecas
import streamlit as st
import pandas as pd
from PIL import Image
import base64
import io

# Configurações da página
st.set_page_config(
    page_title="FiscAI",
    layout="wide",
    page_icon="💻",
    initial_sidebar_state="collapsed"
)

# Cache da imagem convertida
@st.cache_data
def carregar_banner_base64():
    image = Image.open("fiscai_banner.png")
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# CSS da sidebar
st.markdown("""
    <style>
        section[data-testid="stSidebar"] {
            background-color: rgba(0, 0, 0, 0.0);
        }
        section[data-testid="stSidebar"] > div:first-child {
            box-shadow: none;
        }
    </style>
""", unsafe_allow_html=True)

# Sidebar - Navegação unificada
st.sidebar.markdown("##  Menu")

menu = st.sidebar.radio("Escolha uma opção:", [
    "🏠 Início",
    "📁 XML NF-e | Regime Tributário",
    "📁 XML NF-e | Pendências",
    "📁 XML NFC-e | Conferência",
    "📁 Conferência IBS e CBS",
    "📄 Leitor PDF | Energia Elétrica",
    "📊 Leitor TXT | Natureza da Receita",
    "🔄 EXCEL - CSV | Lançamentos IRPF",
])

# Linha separadora visual
st.sidebar.markdown(
    "<hr style='margin: 10px 5px; border: none; height: 1px; background-color: #00e0ff;'>",
    unsafe_allow_html=True
)

# Exibir conteúdo com base na opção escolhida
if menu == "🏠 Início":
    img_base64 = carregar_banner_base64()
    st.markdown(
        f"""
        <div style='text-align: center; margin-bottom: 1rem;'>
            <img src="data:image/png;base64,{img_base64}" width="900">
        </div>
        """,
        unsafe_allow_html=True
    )

elif menu == "📁 XML NF-e | Regime Tributário":
    from ferramentas.leitor_rt import app as leitor_rt_app
    leitor_rt_app()

elif menu == "📁 XML NF-e | Pendências":
    from ferramentas.xml_nfe_pendentes import app as pendentes_app
    pendentes_app()

elif menu == "📁 XML NFC-e | Conferência":
    from ferramentas.xml_nfce import app as xml_nfce_app
    xml_nfce_app()

elif menu == "📁 Conferência IBS e CBS":
    from ferramentas.conferencia_ibs_cbs import app as conferencia_ibs_cbs_app
    conferencia_ibs_cbs_app()

elif menu == "📄 Leitor PDF | Energia Elétrica":
    from ferramentas.leitor_pdf_nf3e import app as leitor_pdf_nf3e_app
    leitor_pdf_nf3e_app()

elif menu == "📊 Leitor TXT | Natureza da Receita":
    from ferramentas.resumo_nat_receita import app as resumo_app
    resumo_app()
elif menu == "🔄 EXCEL - CSV | Lançamentos IRPF":
    from ferramentas.converter_xlsx_csv import app as converter_xlsx_csv_app
    converter_xlsx_csv_app()

