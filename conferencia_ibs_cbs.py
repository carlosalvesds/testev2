import html
import json
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def apenas_digitos(valor):
    return "".join(filter(str.isdigit, valor or ""))


def formatar_cpf_cnpj(valor):
    doc = apenas_digitos(valor)
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    return valor or ""


def para_float(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def formatar_data_br(valor):
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return valor or ""
    return data.strftime("%d/%m/%Y")


def formatar_periodo(datas):
    datas_convertidas = pd.to_datetime(datas, errors="coerce").dropna()
    if datas_convertidas.empty:
        return ""

    data_inicial = datas_convertidas.min()
    data_final = datas_convertidas.max()
    if data_inicial.date() == data_final.date():
        return data_inicial.strftime("%d/%m/%Y")
    return f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"


def formatar_moeda_br(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        numero = 0.0
    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def local_name(elemento):
    return elemento.tag.rsplit("}", 1)[-1]


def filho(elemento, nome):
    if elemento is None:
        return None
    for item in list(elemento):
        if local_name(item) == nome:
            return item
    return None


def descendente(elemento, nome):
    if elemento is None:
        return None
    for item in elemento.iter():
        if local_name(item) == nome:
            return item
    return None


def texto(elemento, caminho, padrao=""):
    atual = elemento
    for parte in caminho.split("/"):
        atual = filho(atual, parte)
        if atual is None:
            return padrao
    return atual.text or padrao


def texto_desc(elemento, nome, padrao=""):
    encontrado = descendente(elemento, nome)
    if encontrado is None:
        return padrao
    return encontrado.text or padrao


def chave_da_nota(root):
    inf_nfe = descendente(root, "infNFe")
    if inf_nfe is not None:
        chave = inf_nfe.attrib.get("Id", "").replace("NFe", "")
        if chave:
            return chave
    return texto_desc(root, "chNFe")


def eh_evento_cancelamento(root):
    if not local_name(root).endswith("procEventoNFe"):
        return False
    tp_evento = texto_desc(root, "tpEvento")
    desc_evento = texto_desc(root, "descEvento").lower()
    cstat = texto_desc(root, "cStat")
    return tp_evento == "110111" or "cancel" in desc_evento or cstat in {"101", "135", "155"}


def listar_xmls_zip(arquivo_zip):
    xmls = []
    with zipfile.ZipFile(arquivo_zip, "r") as zip_ref:
        for nome in zip_ref.namelist():
            if nome.endswith("/"):
                continue
            conteudo = zip_ref.read(nome)
            if nome.lower().endswith(".xml"):
                xmls.append((nome, conteudo))
            elif nome.lower().endswith(".zip"):
                xmls.extend(listar_xmls_zip(BytesIO(conteudo)))
    return xmls


def extrair_dados_nota(root):
    inf_nfe = descendente(root, "infNFe")
    ide = filho(inf_nfe, "ide")
    emit = filho(inf_nfe, "emit")
    dest = filho(inf_nfe, "dest")
    total = filho(inf_nfe, "total")
    icms_tot = filho(total, "ICMSTot")
    ibs_cbs_tot = filho(total, "IBSCBSTot")

    doc_dest = texto(dest, "CNPJ") or texto(dest, "CPF")
    status = texto(root.find(".//nfe:infProt", NFE_NS), "xMotivo") or texto_desc(root, "xMotivo")

    return {
        "Chave_Acesso": chave_da_nota(root),
        "Modelo": texto(ide, "mod"),
        "Série": texto(ide, "serie"),
        "Número": texto(ide, "nNF"),
        "Data_Emissão": texto(ide, "dhEmi")[:10],
        "CNPJ_Emitente": formatar_cpf_cnpj(texto(emit, "CNPJ")),
        "Nome_Emitente": texto(emit, "xNome"),
        "CPF_CNPJ_Destinatário": formatar_cpf_cnpj(doc_dest),
        "Nome_Destinatário": texto(dest, "xNome"),
        "Valor_NF": para_float(texto(icms_tot, "vNF")),
        "Status_SEFAZ": status,
        "Total_vBC_IBS_CBS": para_float(texto(ibs_cbs_tot, "vBCIBSCBS")),
        "Total_vIBS": para_float(texto_desc(ibs_cbs_tot, "vIBS")),
        "Total_vCBS": para_float(texto_desc(filho(ibs_cbs_tot, "gCBS"), "vCBS")),
    }


def extrair_itens_ibs_cbs(root, dados_nota):
    inf_nfe = descendente(root, "infNFe")
    itens = []
    tem_item_sem_destaque = False

    for det in inf_nfe.findall("nfe:det", NFE_NS):
        prod = filho(det, "prod")
        imposto = filho(det, "imposto")
        ibs_cbs = filho(imposto, "IBSCBS")
        g_ibs_cbs = filho(ibs_cbs, "gIBSCBS")
        g_ibs_uf = filho(g_ibs_cbs, "gIBSUF")
        g_ibs_mun = filho(g_ibs_cbs, "gIBSMun")
        g_cbs = filho(g_ibs_cbs, "gCBS")
        tem_destaque = ibs_cbs is not None

        if not tem_destaque:
            tem_item_sem_destaque = True

        valor_produto = para_float(texto(prod, "vProd"))
        valor_desconto = para_float(texto(prod, "vDesc"))

        itens.append({
            "Chave_Acesso": dados_nota["Chave_Acesso"],
            "Nome_Emitente": dados_nota["Nome_Emitente"],
            "Data_Emissão": dados_nota["Data_Emissão"],
            "Modelo": dados_nota["Modelo"],
            "Série": dados_nota["Série"],
            "Número": dados_nota["Número"],
            "Item": det.attrib.get("nItem", ""),
            "Código_Produto": texto(prod, "cProd"),
            "Produto": texto(prod, "xProd"),
            "NCM": texto(prod, "NCM"),
            "CFOP": texto(prod, "CFOP"),
            "Valor_Produto": valor_produto,
            "Valor_Desconto": valor_desconto,
            "Valor_Líquido": valor_produto - valor_desconto,
            "Tem_Destaque_IBS_CBS": "Sim" if tem_destaque else "Não",
            "CST_IBS_CBS": texto(ibs_cbs, "CST"),
            "cClassTrib": texto(ibs_cbs, "cClassTrib"),
            "vBC_IBS_CBS": para_float(texto(g_ibs_cbs, "vBC")),
            "pIBSUF": para_float(texto(g_ibs_uf, "pIBSUF")),
            "vIBSUF": para_float(texto(g_ibs_uf, "vIBSUF")),
            "pIBSMun": para_float(texto(g_ibs_mun, "pIBSMun")),
            "vIBSMun": para_float(texto(g_ibs_mun, "vIBSMun")),
            "vIBS": para_float(texto(g_ibs_cbs, "vIBS")),
            "pCBS": para_float(texto(g_cbs, "pCBS")),
            "vCBS": para_float(texto(g_cbs, "vCBS")),
        })

    return itens, tem_item_sem_destaque


def gerar_resumo(df_itens):
    colunas_resumo = [
        "Nome_Emitente",
        "Período",
        "Modelo",
        "CST_IBS_CBS",
        "cClassTrib",
        "Valor_Líquido",
        "vBC_IBS_CBS",
        "vIBS",
        "vCBS",
    ]

    if df_itens.empty:
        return pd.DataFrame(columns=colunas_resumo)

    df_resumo = df_itens.groupby(
        ["Nome_Emitente", "Modelo", "CST_IBS_CBS", "cClassTrib"],
        dropna=False,
        as_index=False
    ).agg({
        "Data_Emissão": formatar_periodo,
        "Valor_Líquido": "sum",
        "vBC_IBS_CBS": "sum",
        "vIBS": "sum",
        "vCBS": "sum",
    })
    df_resumo = df_resumo.rename(columns={"Data_Emissão": "Período"})

    return df_resumo[colunas_resumo]


def exibir_resumo_por_emitente(df_resumo):
    if df_resumo.empty:
        st.warning("Nenhum resumo de IBS/CBS foi gerado.")
        return

    colunas_tabela = [
        "Modelo",
        "CST_IBS_CBS",
        "cClassTrib",
        "Valor_Líquido",
        "vBC_IBS_CBS",
        "vIBS",
        "vCBS",
    ]

    st.subheader("Resumo IBS e CBS")
    exibir_botao_imprimir_resumo(df_resumo, colunas_tabela)

    for emitente, grupo in df_resumo.groupby("Nome_Emitente", dropna=False):
        periodos = " / ".join(grupo["Período"].dropna().astype(str).unique())
        st.markdown(f"**{emitente or 'Emitente não identificado'}**  \nPeríodo: {periodos}")
        st.dataframe(
            grupo[colunas_tabela].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor_Líquido": st.column_config.NumberColumn("Valor Líquido", format="R$ %.2f"),
                "vBC_IBS_CBS": st.column_config.NumberColumn("BC IBS/CBS", format="R$ %.2f"),
                "vIBS": st.column_config.NumberColumn("Valor IBS", format="R$ %.2f"),
                "vCBS": st.column_config.NumberColumn("Valor CBS", format="R$ %.2f"),
            }
        )


def montar_html_impressao_resumo(df_resumo, colunas_tabela):
    blocos = []
    for emitente, grupo in df_resumo.groupby("Nome_Emitente", dropna=False):
        periodos = " / ".join(grupo["Período"].dropna().astype(str).unique())
        linhas = []

        for _, linha in grupo[colunas_tabela].iterrows():
            linhas.append(
                "<tr>"
                f"<td>{html.escape(str(linha['Modelo']))}</td>"
                f"<td>{html.escape(str(linha['CST_IBS_CBS']))}</td>"
                f"<td>{html.escape(str(linha['cClassTrib']))}</td>"
                f"<td class='num'>{formatar_moeda_br(linha['Valor_Líquido'])}</td>"
                f"<td class='num'>{formatar_moeda_br(linha['vBC_IBS_CBS'])}</td>"
                f"<td class='num'>{formatar_moeda_br(linha['vIBS'])}</td>"
                f"<td class='num'>{formatar_moeda_br(linha['vCBS'])}</td>"
                "</tr>"
            )

        blocos.append(f"""
            <section>
                <h2>{html.escape(str(emitente or "Emitente não identificado"))}</h2>
                <p class="periodo">Período: {html.escape(periodos)}</p>
                <table>
                    <thead>
                        <tr>
                            <th>Modelo</th>
                            <th>CST IBS/CBS</th>
                            <th>cClassTrib</th>
                            <th>Valor Líquido</th>
                            <th>BC IBS/CBS</th>
                            <th>Valor IBS</th>
                            <th>Valor CBS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(linhas)}
                    </tbody>
                </table>
            </section>
        """)

    return f"""
    <!doctype html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <title>Resumo IBS e CBS</title>
        <style>
            body {{
                color: #111;
                font-family: Arial, Helvetica, sans-serif;
                margin: 32px;
            }}
            h1 {{
                font-size: 22px;
                margin: 0 0 24px;
                text-align: center;
            }}
            h2 {{
                font-size: 16px;
                margin: 24px 0 4px;
            }}
            .periodo {{
                margin: 0 0 12px;
                font-size: 13px;
            }}
            table {{
                border-collapse: collapse;
                margin-bottom: 20px;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #333;
                font-size: 11px;
                padding: 7px 8px;
            }}
            th {{
                background: #000;
                color: #fff;
                text-align: center;
            }}
            td {{
                text-align: center;
            }}
            .num {{
                text-align: right;
                white-space: nowrap;
            }}
            @page {{
                margin: 16mm;
            }}
        </style>
    </head>
    <body>
        <h1>Resumo IBS e CBS</h1>
        {''.join(blocos)}
    </body>
    </html>
    """


def exibir_botao_imprimir_resumo(df_resumo, colunas_tabela):
    html_relatorio = json.dumps(montar_html_impressao_resumo(df_resumo, colunas_tabela))
    components.html(
        f"""
        <button id="print-resumo" type="button">🖨️ Imprimir resumo</button>
        <script>
            const button = document.getElementById("print-resumo");
            const reportHtml = {html_relatorio};

            button.addEventListener("click", () => {{
                const printWindow = window.open("", "_blank");
                printWindow.document.open();
                printWindow.document.write(reportHtml);
                printWindow.document.close();
                printWindow.focus();
                setTimeout(() => printWindow.print(), 250);
            }});
        </script>
        <style>
            #print-resumo {{
                background: #111827;
                border: 1px solid #111827;
                border-radius: 6px;
                color: white;
                cursor: pointer;
                font-family: Arial, Helvetica, sans-serif;
                font-size: 14px;
                font-weight: 600;
                padding: 9px 14px;
            }}
            #print-resumo:hover {{
                background: #000;
            }}
        </style>
        """,
        height=52,
    )


def gerar_excel(df_notas, df_itens, df_resumo, df_canceladas):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_notas.to_excel(writer, index=False, sheet_name="Notas")
        df_resumo.to_excel(writer, index=False, sheet_name="Resumo")
        df_itens.to_excel(writer, index=False, sheet_name="Itens_IBS_CBS")
        df_canceladas.to_excel(writer, index=False, sheet_name="Canceladas")

        workbook = writer.book
        header_format = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": "black",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        cell_format = workbook.add_format({
            "align": "center",
            "valign": "vcenter",
        })

        for sheet_name, df in {
            "Notas": df_notas,
            "Resumo": df_resumo,
            "Itens_IBS_CBS": df_itens,
            "Canceladas": df_canceladas,
        }.items():
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            worksheet.set_row(0, 22)
            for idx, coluna in enumerate(df.columns):
                largura = max(len(str(coluna)), df[coluna].astype(str).str.len().max() if not df.empty else 0)
                worksheet.write(0, idx, coluna, header_format)
                worksheet.set_column(idx, idx, min(largura + 2, 45), cell_format)

    output.seek(0)
    return output.getvalue()


def app():
    st.title("📁 Conferência IBS e CBS")
    st.markdown("""
Esta ferramenta confere XMLs de NF-e/NFC-e, ignora documentos cancelados e extrai as informações da nota fiscal junto com o destaque de IBS e CBS por item.
""")

    arquivos = st.file_uploader(
        "Envie um ou mais arquivos .zip contendo os XMLs",
        type=["zip"],
        accept_multiple_files=True,
        help="Você pode selecionar vários arquivos .zip de uma vez."
    )

    if not arquivos:
        return

    st.info(f"📦 Arquivos ZIP selecionados: {len(arquivos)}")

    xmls = []
    for arquivo in arquivos:
        try:
            xmls.extend(listar_xmls_zip(arquivo))
        except zipfile.BadZipFile:
            st.error(f"O arquivo {arquivo.name} não é um ZIP válido.")

    if not xmls:
        st.warning("Nenhum XML foi encontrado nos arquivos enviados.")
        return

    chaves_canceladas = set()
    canceladas = []
    documentos = []
    erros = []

    for nome, conteudo in xmls:
        try:
            root = ET.fromstring(conteudo)
            if eh_evento_cancelamento(root):
                chave = texto_desc(root, "chNFe")
                chaves_canceladas.add(chave)
                canceladas.append({
                    "Chave_Acesso": chave,
                    "Evento": texto_desc(root, "descEvento"),
                    "Data_Evento": texto_desc(root, "dhEvento"),
                    "Status_Evento": texto_desc(root, "xMotivo"),
                })
            elif descendente(root, "infNFe") is not None:
                documentos.append((nome, root))
        except ET.ParseError as erro:
            erros.append(f"{nome}: XML inválido ({erro})")
        except Exception as erro:
            erros.append(f"{nome}: {erro}")

    notas = []
    itens = []
    notas_sem_destaque = []

    for nome, root in documentos:
        dados_nota = extrair_dados_nota(root)
        if dados_nota["Chave_Acesso"] in chaves_canceladas:
            continue

        itens_nota, tem_item_sem_destaque = extrair_itens_ibs_cbs(root, dados_nota)
        tem_destaque_nota = bool(itens_nota) and not tem_item_sem_destaque
        dados_nota["Itens_Conferidos"] = len(itens_nota)
        dados_nota["Destaque_IBS_CBS"] = "Sim" if tem_destaque_nota else "Não"

        if not tem_destaque_nota:
            notas_sem_destaque.append(dados_nota["Chave_Acesso"])

        notas.append(dados_nota)
        itens.extend(itens_nota)

    df_notas = pd.DataFrame(notas)
    df_itens = pd.DataFrame(itens)
    df_resumo = gerar_resumo(df_itens)
    df_canceladas = pd.DataFrame(canceladas)

    st.info(f"📄 XMLs lidos: {len(xmls)}")
    st.info(f"🚫 Notas canceladas ignoradas: {len(chaves_canceladas)}")
    st.info(f"✅ Notas válidas conferidas: {len(df_notas)}")
    if erros:
        st.warning(f"⚠️ {len(erros)} XML(s) não puderam ser processados.")

    if df_notas.empty:
        st.warning("Nenhuma nota autorizada foi encontrada após ignorar as canceladas.")
        return

    if not notas_sem_destaque:
        st.success("✅ Todas as notas foram emitidas com o destaque de IBS e CBS.")
    else:
        st.warning(f"⚠️ {len(notas_sem_destaque)} nota(s) válida(s) possuem item sem destaque de IBS/CBS.")

    exibir_resumo_por_emitente(df_resumo)

    excel = gerar_excel(df_notas, df_itens, df_resumo, df_canceladas)
    st.download_button(
        label="📥 Baixar conferência em Excel",
        data=excel,
        file_name="conferencia_ibs_cbs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
