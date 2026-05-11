
import streamlit as st
import pandas as pd
import io

def app():
    st.title("🔄 Conversor XLSX para CSV")
    st.write("Esta ferramenta foi desenvolvida para converter automaticamente uma base de dados" \
    " em formato Excel (.xlsx) para um arquivo CSV, com estrutura e formatação específicas" \
    " para atender às exigências de automações voltadas ao preenchimento de Lançamentos no IRPF.")

    uploaded_file = st.file_uploader("Selecione a base de dados em EXCEL.", type=["xlsx"])

    st.markdown(
        """
        <div style='background-color:#1a222d;color:#fff;padding:12px 18px;border-radius:8px;margin-bottom:18px;'>
        <b>Como preparar seu arquivo Excel para conversão ideal:</b><br>
        <ul style='margin-top: 8px;'>
        <li>Certifique-se de que a primeira linha do arquivo contenha os <b>nomes das colunas</b> (cabeçalhos).</li>
        <li>Inclua uma coluna chamada <b>subconta</b> e outra coluna chamada <b>rendimento<b>.</li>
        <li>Evite células mescladas, fórmulas ou linhas em branco extras no arquivo.</li>
        <li>Salve o arquivo em formato <b>.xlsx</b> (Excel moderno).</li>
        <li>Se possível, revise os dados para garantir que não há caracteres especiais indesejados e verifique se todos os valores tem duas casas decimais.</li>
        </ul>
        <span style='color:#00e0ff;'>Dica:</span> Quanto mais limpa e padronizada estiver sua base, melhor será o resultado da automação!
        </div>
        """,
        unsafe_allow_html=True
    )

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            return

        # Formata a coluna 'rendimento' para garantir sempre duas casas decimais
        col_rendimento = None
        for col in df.columns:
            if col.strip().lower() == 'rendimento':
                col_rendimento = col
                break
        if col_rendimento:
            def format_rendimento(x):
                if pd.isnull(x) or x == "":
                    return ""
                try:
                    x_str = str(x).replace(',', '.').strip()
                    num = float(x_str)
                    return f"{num:,.2f}".replace('.', ',')
                except Exception:
                    return str(x)
            df[col_rendimento] = df[col_rendimento].apply(format_rendimento)

        # Salva CSV em buffer
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, sep=',', encoding='utf-8')
        csv_data = csv_buffer.getvalue()

        st.success("Conversão realizada com sucesso!")
        st.download_button(
            label="Baixar CSV",
            data=csv_data,
            file_name="convertido.csv",
            mime="text/csv"
        )
