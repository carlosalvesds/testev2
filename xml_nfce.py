
import streamlit as st
import pandas as pd
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
import time
from tempfile import NamedTemporaryFile

def app():
    st.title("📁 XML NFC-e | Conferência")
    st.markdown("""
Essa ferramenta extrai informações de arquivos XML de NFC-e, facilitando a conferência e auditoria de dados fiscais. A ferramenta organiza os dados em uma planilha Excel, permitindo uma análise rápida e eficiente. Com suporte para o processamento de grandes volumes de arquivos, garante agilidade e precisão, mesmo em operações que envolvem milhares de documentos.

""")
    # Apenas uma chamada para o file_uploader

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    def formatar_cpf_cnpj(valor):
        if not valor or not valor.isdigit():
            return valor
        if len(valor) == 11:
            return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
        elif len(valor) == 14:
            return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
        return valor

    def extrair_xml_completo(tree):
        root = tree.getroot()
        resultado = []
        infNFe = root.find(".//nfe:infNFe", ns)
        if infNFe is None:
            return resultado
        ide = infNFe.find("nfe:ide", ns)
        emit = infNFe.find("nfe:emit", ns)
        dest = infNFe.find("nfe:dest", ns)
        pagamentos = root.findall(".//nfe:pag/nfe:detPag", ns)

        nNF = ide.findtext("nfe:nNF", default="", namespaces=ns)
        serie = ide.findtext("nfe:serie", default="", namespaces=ns)
        dhEmi = ide.findtext("nfe:dhEmi", default="", namespaces=ns)
        cNF = infNFe.findtext("nfe:cNF", default="", namespaces=ns)
        if not cNF and ide is not None:
            cNF = ide.findtext("nfe:cNF", default="", namespaces=ns)
        emit_cnpj = emit.findtext("nfe:CNPJ", default="", namespaces=ns)
        emit_xfant = emit.findtext("nfe:xFant", default="", namespaces=ns)
        dest_cpf_cnpj = dest.findtext("nfe:CPF", namespaces=ns) or dest.findtext("nfe:CNPJ", namespaces=ns) if dest is not None else ""
        dest_xnome = dest.findtext("nfe:xNome", default="", namespaces=ns) if dest is not None else ""

        tPag = pagamentos[0].findtext("nfe:tPag", default="", namespaces=ns) if pagamentos else ""

        for det in infNFe.findall("nfe:det", ns):
            prod = det.find("nfe:prod", ns)
            imposto = det.find("nfe:imposto", ns)
            icms = imposto.find(".//nfe:ICMS", ns) if imposto is not None else None
            pis = imposto.find(".//nfe:PIS", ns) if imposto is not None else None
            cofins = imposto.find(".//nfe:COFINS", ns) if imposto is not None else None

            # Extrai pRedBC (redução da base de cálculo do ICMS), se existir, especificamente de ICMS20
            pRedBC = ""
            if icms is not None:
                icms20 = icms.find("nfe:ICMS20", ns)
                if icms20 is not None:
                    pRedBC = icms20.findtext("nfe:pRedBC", default="", namespaces=ns)
                else:
                    # fallback: busca em qualquer lugar dentro de ICMS
                    pRedBC = icms.findtext(".//nfe:pRedBC", default="", namespaces=ns)
            linha = {
                "nNF": nNF, "serie": serie, "dhEmi": dhEmi, "cNF": cNF,
                "emit_CNPJ": emit_cnpj, "emit_xFant": emit_xfant,
                "dest_CPF_CNPJ": dest_cpf_cnpj, "dest_xNome": dest_xnome,
                "cProd": prod.findtext("nfe:cProd", default="", namespaces=ns),
                "cEAN": prod.findtext("nfe:cEAN", default="", namespaces=ns),
                "xProd": prod.findtext("nfe:xProd", default="", namespaces=ns),
                "NCM": prod.findtext("nfe:NCM", default="", namespaces=ns),
                "CFOP": prod.findtext("nfe:CFOP", default="", namespaces=ns),
                "uCom": prod.findtext("nfe:uCom", default="", namespaces=ns),
                "qCom": prod.findtext("nfe:qCom", default="", namespaces=ns),
                "vUnCom": prod.findtext("nfe:vUnCom", default="", namespaces=ns),
                "vDesc": prod.findtext("nfe:vDesc", default="", namespaces=ns),
                "vProd": prod.findtext("nfe:vProd", default="", namespaces=ns),
                "uTrib": prod.findtext("nfe:uTrib", default="", namespaces=ns),
                "qTrib": prod.findtext("nfe:qTrib", default="", namespaces=ns),
                "vUnTrib": prod.findtext("nfe:vUnTrib", default="", namespaces=ns),
                "ICMS_orig": icms.findtext(".//nfe:orig", default="", namespaces=ns) if icms is not None else "",
                "ICMS_CST": icms.findtext(".//nfe:CST", default="", namespaces=ns) if icms is not None else "",
                "ICMS_vBC": icms.findtext(".//nfe:vBC", default="", namespaces=ns) if icms is not None else "",
                "ICMS_pICMS": icms.findtext(".//nfe:pICMS", default="", namespaces=ns) if icms is not None else "",
                "ICMS_vICMS": icms.findtext(".//nfe:vICMS", default="", namespaces=ns) if icms is not None else "",
                "PIS_CST": pis.findtext(".//nfe:CST", default="", namespaces=ns) if pis is not None else "",
                "PIS_vBC": pis.findtext(".//nfe:vBC", default="", namespaces=ns) if pis is not None else "",
                "PIS_pPIS": pis.findtext(".//nfe:pPIS", default="", namespaces=ns) if pis is not None else "",
                "PIS_vPIS": pis.findtext(".//nfe:vPIS", default="", namespaces=ns) if pis is not None else "",
                "COFINS_CST": cofins.findtext(".//nfe:CST", default="", namespaces=ns) if cofins is not None else "",
                "COFINS_vBC": cofins.findtext(".//nfe:vBC", default="", namespaces=ns) if cofins is not None else "",
                "COFINS_pCOFINS": cofins.findtext(".//nfe:pCOFINS", default="", namespaces=ns) if cofins is not None else "",
                "COFINS_vCOFINS": cofins.findtext(".//nfe:vCOFINS", default="", namespaces=ns) if cofins is not None else "",
                "pag_tPag": tPag,
                "pRedBC": pRedBC
            }
            resultado.append(linha)
        return resultado

    uploaded_file = st.file_uploader("Envie um arquivo .zip com XMLs de NFC-e", type="zip")
    dados, resumo, status, xml_completo = [], [], [], []
    chaves_canceladas = set()

    if uploaded_file:
        with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
            xml_files = [zip_ref.open(name) for name in zip_ref.namelist() if ".xml" in name.lower()]
            for file in xml_files:
                try:
                    tree = ET.parse(file)
                    root = tree.getroot()
                    xml_completo.extend(extrair_xml_completo(tree))

                    if root.tag.endswith("procEventoNFe"):
                        chave = root.findtext(".//nfe:chNFe", namespaces=ns)
                        cnpj_emit = root.findtext(".//nfe:CNPJ", namespaces=ns)
                        dh_evento = root.findtext(".//nfe:dhEvento", namespaces=ns)
                        numero_doc = chave[25:34] if chave else None
                        serie = chave[22:25] if chave and len(chave) >= 25 else ""
                        chaves_canceladas.add(chave)

                        dados.append({
                            "Número_Doc": int(numero_doc),
                            "Chave_Acesso": str(chave).zfill(44),
                            "Situação_do_Documento": "Cancelamento de NF-e homologado",
                            "Modelo": "65",
                            "CNPJ_Emissor": formatar_cpf_cnpj(str(cnpj_emit)),
                            "CPF_CNPJ_Destinatário": "",
                            "UF_Destinatário": "",
                            "Valor_Total": 0.00,
                            "Data_de_Emissão": pd.to_datetime(dh_evento).strftime("%d-%m-%Y") if dh_evento else None,
                            "Serie": serie
                        })
                        status.append({"Arquivo_XML": file.name, "Progresso": "OK"})
                        continue

                    ide = root.find(".//nfe:ide", ns)
                    emit = root.find(".//nfe:emit", ns)
                    dest = root.find(".//nfe:dest", ns) or None
                    total = root.find(".//nfe:total", ns)
                    infNFe = root.find(".//nfe:infNFe", ns)

                    numero_doc = ide.findtext("nfe:nNF", default="", namespaces=ns)
                    serie = ide.findtext("nfe:serie", default="", namespaces=ns)
                    chave_acesso = infNFe.attrib.get("Id", "").replace("NFe", "")
                    modelo = ide.findtext("nfe:mod", default="", namespaces=ns)
                    cnpj_emit = emit.findtext("nfe:CNPJ", default="", namespaces=ns)
                    cnpj_dest = dest.findtext("nfe:CNPJ", namespaces=ns) if dest is not None else ""
                    cnpj_dest = cnpj_dest or (dest.findtext("nfe:CPF", default="", namespaces=ns) if dest is not None else "")
                    uf_dest = dest.findtext("nfe:enderDest/nfe:UF", default="", namespaces=ns) if dest is not None else ""
                    valor_total = total.findtext("nfe:ICMSTot/nfe:vNF", default="0", namespaces=ns)
                    data_emissao = ide.findtext("nfe:dhEmi", default="", namespaces=ns)[:10]

                    dados.append({
                        "Número_Doc": int(numero_doc),
                        "Chave_Acesso": str(chave_acesso).zfill(44),
                        "Situação_do_Documento": "Autorizado",
                        "Modelo": modelo,
                        "CNPJ_Emissor": formatar_cpf_cnpj(str(cnpj_emit)),
                        "CPF_CNPJ_Destinatário": formatar_cpf_cnpj(str(cnpj_dest)),
                        "UF_Destinatário": uf_dest,
                        "Valor_Total": float(valor_total),
                        "Data_de_Emissão": pd.to_datetime(data_emissao).strftime("%d-%m-%Y") if data_emissao else None,
                        "Serie": serie
                    })


                    for det in root.findall(".//nfe:det", ns):
                        cfop = det.findtext(".//nfe:CFOP", namespaces=ns)
                        cst = det.findtext(".//nfe:ICMS/*/nfe:CST", namespaces=ns)
                        vprod = det.findtext(".//nfe:prod/nfe:vProd", namespaces=ns)
                        vdesc = det.findtext(".//nfe:prod/nfe:vDesc", namespaces=ns) or "0"
                        vbc = det.findtext(".//nfe:ICMS/*/nfe:vBC", namespaces=ns)
                        picms = det.findtext(".//nfe:ICMS/*/nfe:pICMS", namespaces=ns)
                        vicms = det.findtext(".//nfe:ICMS/*/nfe:vICMS", namespaces=ns)

                        resumo.append({
                            "CST": cst,
                            "CFOP": cfop,
                            "Valor Total": float(vprod or 0) - float(vdesc or 0),
                            "Base de Cálculo": float(vbc or 0),
                            "Alíquota": f"{float(picms):.2f}" if picms else "0.00",
                            "ICMS": float(vicms or 0),
                            "Chave_Acesso": str(chave_acesso).zfill(44)
                        })

                    status.append({"Arquivo_XML": file.name, "Progresso": "OK"})
                except Exception as e:
                    status.append({"Arquivo_XML": file.name, "Progresso": "ERRO"})

    if chaves_canceladas:
        dados = [
            d for d in dados
            if not (d["Situação_do_Documento"] == "Autorizado" and d["Chave_Acesso"] in chaves_canceladas)
        ]

    df_dados = pd.DataFrame(dados)
    # Corrige erro caso a coluna 'Serie' não exista
    if "Serie" not in df_dados.columns:
        df_dados["Serie"] = ""
    df_dados["Serie"] = df_dados["Serie"].fillna("").astype(str).str.zfill(3).str.strip()
    # Corrige erro caso a coluna 'Número_Doc' não exista
    if "Número_Doc" not in df_dados.columns:
        df_dados["Número_Doc"] = None
    df_dados["Número_Doc"] = pd.to_numeric(df_dados["Número_Doc"], errors="coerce")
    df_dados = df_dados.sort_values(by=["Serie", "Número_Doc"]).reset_index(drop=True)

    # Filtrar apenas notas autorizadas que NÃO estão canceladas para as abas de resumo, produtos e XML completo
    chaves_canceladas = set(chaves_canceladas)
    if "Situação_do_Documento" in df_dados.columns and "Chave_Acesso" in df_dados.columns:
        chaves_autorizadas_validas = set(
            df_dados.loc[
                (df_dados["Situação_do_Documento"] == "Autorizado") &
                (~df_dados["Chave_Acesso"].astype(str).isin(chaves_canceladas)),
                "Chave_Acesso"
            ].astype(str)
        )
    else:
        chaves_autorizadas_validas = set()

    # Função auxiliar para filtrar listas de dicts por chaves autorizadas válidas
    def filtrar_por_chave(lista, chave_nome="Chave_Acesso"):
        return [item for item in lista if str(item.get(chave_nome, "")) in chaves_autorizadas_validas]

    # Filtrar resumo e xml_completo se possível
    if resumo and chaves_autorizadas_validas:
        # Se cada item do resumo tiver Chave_Acesso, filtra
        if "Chave_Acesso" in resumo[0]:
            resumo = filtrar_por_chave(resumo, "Chave_Acesso")
    if xml_completo and chaves_autorizadas_validas:
        # Se cada item do xml_completo tiver cNF, tenta filtrar por Chave_Acesso se existir
        if "Chave_Acesso" in xml_completo[0]:
            xml_completo = filtrar_por_chave(xml_completo, "Chave_Acesso")

    df_status = pd.DataFrame(status)
    df_resumo = pd.DataFrame(resumo)
    # Garante que as colunas existem antes do groupby
    for col in ["CST", "CFOP", "Alíquota", "Valor Total", "Base de Cálculo", "ICMS"]:
        if col not in df_resumo.columns:
            df_resumo[col] = None
    # Filtra resumo apenas para notas autorizadas válidas
    if (
        "Chave_Acesso" in df_dados.columns and
        "Chave_Acesso" in df_resumo.columns and
        not df_resumo.empty
    ):
        df_resumo = df_resumo[df_resumo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
    # Filtrar df_resumo para considerar apenas notas autorizadas e não canceladas antes do groupby
    if (
        "Chave_Acesso" in df_resumo.columns and
        chaves_autorizadas_validas
    ):
        df_resumo = df_resumo[df_resumo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
    df_resumo_grouped = df_resumo.groupby(["CST", "CFOP", "Alíquota"], dropna=False).agg({
        "Valor Total": "sum",
        "Base de Cálculo": "sum",
        "ICMS": "sum"
    }).reset_index()

    df_seq = []
    for serie, grupo in df_dados.groupby("Serie"):
        numeros = sorted(grupo["Número_Doc"].dropna().astype(int).unique())
        for i in range(1, len(numeros)):
            anterior, atual = numeros[i - 1], numeros[i]
            if atual != anterior + 1:
                df_seq.append({
                    "Série": serie,
                    "Número_Anterior": anterior,
                    "Número_Atual": atual,
                    "Quebra_Detectada": "SIM"
                })
    df_seq = pd.DataFrame(df_seq)

    df_xml_completo = pd.DataFrame(xml_completo)
    # Filtrar XML_Completo apenas para notas autorizadas válidas
    if "Chave_Acesso" in df_dados.columns and not df_xml_completo.empty:
        if "Chave_Acesso" in df_xml_completo.columns:
            df_xml_completo = df_xml_completo[df_xml_completo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
    # Renomear colunas para nomes mais legíveis
    colunas_legiveis = {
        "nNF": "Número NF",
        "serie": "Série",
        "dhEmi": "Data de Emissão",
        "cNF": "CNF",
        "emit_CNPJ": "CNPJ Emitente",
        "emit_xFant": "Nome Fantasia Emitente",
        "dest_CPF_CNPJ": "CPF/CNPJ Destinatário",
        "dest_xNome": "Nome Destinatário",
        "cProd": "Código Produto",
        "cEAN": "EAN",
        "xProd": "Descrição Produto",
        "NCM": "NCM",
        "CFOP": "CFOP",
        "uCom": "Unidade Comercial",
        "qCom": "Quantidade Comercial",
        "vUnCom": "Valor Unitário Comercial",
        "vDesc": "Valor Desconto",
        "vProd": "Valor Produto",
        "uTrib": "Unidade Tributável",
        "qTrib": "Quantidade Tributável",
        "vUnTrib": "Valor Unitário Tributável",
        "ICMS_orig": "Origem ICMS",
        "ICMS_CST": "CST ICMS",
        "ICMS_vBC": "Base de Cálculo ICMS",
        "ICMS_pICMS": "Alíquota ICMS (%)",
        "ICMS_vICMS": "Valor ICMS",
        "PIS_CST": "CST PIS",
        "PIS_vBC": "Base de Cálculo PIS",
        "PIS_pPIS": "Alíquota PIS (%)",
        "PIS_vPIS": "Valor PIS",
        "COFINS_CST": "CST COFINS",
        "COFINS_vBC": "Base de Cálculo COFINS",
        "COFINS_pCOFINS": "Alíquota COFINS (%)",
        "COFINS_vCOFINS": "Valor COFINS",
    "pag_tPag": "Tipo de Pagamento",
    "pRedBC": "Redução_BC_%"
    }
    df_xml_completo = df_xml_completo.rename(columns=colunas_legiveis)
    # Ajustar coluna de data para formato dd/mm/yyyy
    if "Data de Emissão" in df_xml_completo.columns:
        df_xml_completo["Data de Emissão"] = pd.to_datetime(df_xml_completo["Data de Emissão"], errors="coerce").dt.strftime("%d/%m/%Y")

    # Formatar CNPJ/CPF nas colunas legíveis
    if "CNPJ Emitente" in df_xml_completo.columns:
        df_xml_completo["CNPJ Emitente"] = df_xml_completo["CNPJ Emitente"].astype(str).apply(formatar_cpf_cnpj)
    if "CPF/CNPJ Destinatário" in df_xml_completo.columns:
        df_xml_completo["CPF/CNPJ Destinatário"] = df_xml_completo["CPF/CNPJ Destinatário"].astype(str).apply(formatar_cpf_cnpj)
    # Converter colunas de valores e alíquotas para float para garantir soma/média no Excel (usando nomes legíveis)
    colunas_valores_legiveis = [
        "Valor Produto", "Valor Desconto", "Valor Unitário Comercial", "Valor Unitário Tributável",
        "Base de Cálculo ICMS", "Valor ICMS",
        "Base de Cálculo PIS", "Valor PIS",
        "Base de Cálculo COFINS", "Valor COFINS"
    ]
    colunas_aliquotas = [
        "Alíquota ICMS (%)", "Alíquota PIS (%)", "Alíquota COFINS (%)"
    ]
    import numpy as np
    for col in colunas_valores_legiveis + colunas_aliquotas:
        if col in df_xml_completo.columns:
            df_xml_completo[col] = pd.to_numeric(df_xml_completo[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            df_xml_completo[col] = df_xml_completo[col].replace([np.nan, np.inf, -np.inf], 0)

    # Só gera a planilha e exibe mensagem se houver arquivo enviado
    if uploaded_file:
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            with pd.ExcelWriter(tmp.name, engine="xlsxwriter") as writer:
                wb = writer.book
                header_format = wb.add_format({'bold': True, 'bg_color': '#333333', 'font_color': 'white', 'align': 'center'})
                moeda = wb.add_format({'num_format': 'R$ #,##0.00', 'align': 'center'})
                texto = wb.add_format({'align': 'center'})
                vermelho = wb.add_format({'font_color': 'red', 'align': 'center'})
                vermelho_moeda = wb.add_format({'font_color': 'red', 'bold': True, 'num_format': 'R$ #,##0.00', 'align': 'center'})

                def escrever_aba(df, nome, colorir_cancelada=False):
                    df.to_excel(writer, sheet_name=nome, index=False, startrow=1, header=False)
                    ws = writer.sheets[nome]
                    ws.hide_gridlines(2)
                    for i, col in enumerate(df.columns):
                        # Centraliza o título da coluna Descrição_Produto
                        if nome == "Resumo_Produtos" and col == "Descrição_Produto":
                            ws.write(0, i, col, header_format)
                        else:
                            ws.write(0, i, col, header_format)
                        largura = max(len(str(col)), max((len(str(val)) for val in df[col]), default=0)) + 2
                        ws.set_column(i, i, largura)
                    for r, row in df.iterrows():
                        for c, val in enumerate(row):
                            col = df.columns[c]
                            # Alinha à esquerda a coluna Descrição_Produto na aba Resumo_Produtos
                            if nome == "Resumo_Produtos" and col == "Descrição_Produto":
                                fmt = wb.add_format({'align': 'left'})
                            # Formatação monetária para XML_Completo
                            elif nome == "XML_Completo" and col in [
                                "Valor Produto", "Valor Desconto", "Valor Unitário Comercial", "Valor Unitário Tributável",
                                "Base de Cálculo ICMS", "Valor ICMS",
                                "Base de Cálculo PIS", "Valor PIS",
                                "Base de Cálculo COFINS", "Valor COFINS"
                            ]:
                                fmt = moeda
                            # Formatação monetária para Resumo_NFC-e (mantém igual ao Resumo_NF)
                            elif nome == "Resumo_NFC-e" and col in [
                                "Valor Produto", "Valor Desconto", "Valor Líquido",
                                "Valor ICMS", "Base de Cálculo ICMS",
                                "Valor PIS", "Base de Cálculo PIS",
                                "Valor COFINS", "Base de Cálculo COFINS"
                            ]:
                                fmt = moeda
                            elif colorir_cancelada and row.get("Situação_do_Documento") == "Cancelamento de NF-e homologado":
                                fmt = vermelho_moeda if col == "Valor_Total" else vermelho
                            else:
                                fmt = moeda if col in ["Valor_Total", "Valor Total", "Base de Cálculo", "ICMS"] else texto
                            ws.write(r+1, c, val, fmt)

                # Nova aba de resumo por nota fiscal (apenas notas autorizadas e não canceladas)
                if not df_xml_completo.empty:
                    # Garante que a coluna Chave_Acesso exista em df_xml_completo
                    if "Chave_Acesso" not in df_xml_completo.columns:
                        # Tenta preencher Chave_Acesso a partir de df_dados usando Número NF e Série
                        if "Número NF" in df_xml_completo.columns and "Série" in df_xml_completo.columns and "Chave_Acesso" in df_dados.columns:
                            # Garante que ambas as colunas estejam como string para o merge
                            df_xml_completo["Número NF"] = df_xml_completo["Número NF"].astype(str)
                            df_xml_completo["Série"] = df_xml_completo["Série"].astype(str)
                            dados_merge = df_dados[["Número_Doc", "Serie", "Chave_Acesso"]].copy()
                            dados_merge["Número_Doc"] = dados_merge["Número_Doc"].astype(str)
                            dados_merge["Serie"] = dados_merge["Serie"].astype(str)
                            dados_merge = dados_merge.rename(columns={"Número_Doc": "Número NF", "Serie": "Série"})
                            df_xml_completo = pd.merge(
                                df_xml_completo,
                                dados_merge,
                                on=["Número NF", "Série"],
                                how="left"
                            )
                    # Filtra pelas chaves válidas
                    if "Chave_Acesso" in df_xml_completo.columns and chaves_autorizadas_validas:
                        df_xml_filtrado = df_xml_completo[df_xml_completo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
                    else:
                        df_xml_filtrado = df_xml_completo.copy()
                    resumo_nf = df_xml_filtrado.groupby(["Número NF", "Série"], dropna=False).agg({
                        "Valor Produto": "sum",
                        "Valor Desconto": "sum",
                        "Valor ICMS": "sum",
                        "Valor PIS": "sum",
                        "Valor COFINS": "sum",
                        "Base de Cálculo ICMS": "sum",
                        "Base de Cálculo PIS": "sum",
                        "Base de Cálculo COFINS": "sum"
                    }).reset_index()
                    resumo_nf["Valor Líquido"] = resumo_nf["Valor Produto"] - resumo_nf["Valor Desconto"]
                    resumo_nf = resumo_nf[[
                        "Número NF", "Série", "Valor Produto", "Valor Desconto", "Valor Líquido",
                        "Base de Cálculo ICMS", "Valor ICMS",
                        "Valor PIS", "Base de Cálculo PIS",
                        "Valor COFINS", "Base de Cálculo COFINS"
                    ]]
                    # Ordenar por Série crescente e Número NF crescente
                    resumo_nf = resumo_nf.sort_values(by=["Série", "Número NF"]).reset_index(drop=True)
                else:
                    resumo_nf = pd.DataFrame(columns=[
                        "Número NF", "Série", "Valor Produto", "Valor Desconto", "Valor Líquido",
                        "Base de Cálculo ICMS", "Valor ICMS",
                        "Valor PIS", "Base de Cálculo PIS",
                        "Valor COFINS", "Base de Cálculo COFINS"
                    ])

                escrever_aba(df_dados, "Dados_NFC-e", colorir_cancelada=True)
                escrever_aba(df_resumo_grouped, "Resumo CFOP")
                escrever_aba(resumo_nf, "Resumo_NFC-e")
                # Nova aba Resumo_Produtos preenchida apenas com notas autorizadas e não canceladas
                if not df_xml_completo.empty:
                    # Garante que a coluna Chave_Acesso exista em df_xml_completo
                    if "Chave_Acesso" not in df_xml_completo.columns:
                        # Tenta preencher Chave_Acesso a partir de df_dados usando Número NF e Série
                        if "Número NF" in df_xml_completo.columns and "Série" in df_xml_completo.columns and "Chave_Acesso" in df_dados.columns:
                            df_xml_completo["Número NF"] = df_xml_completo["Número NF"].astype(str)
                            df_xml_completo["Série"] = df_xml_completo["Série"].astype(str)
                            dados_merge = df_dados[["Número_Doc", "Serie", "Chave_Acesso"]].copy()
                            dados_merge["Número_Doc"] = dados_merge["Número_Doc"].astype(str)
                            dados_merge["Serie"] = dados_merge["Serie"].astype(str)
                            dados_merge = dados_merge.rename(columns={"Número_Doc": "Número NF", "Serie": "Série"})
                            df_xml_completo = pd.merge(
                                df_xml_completo,
                                dados_merge,
                                on=["Número NF", "Série"],
                                how="left"
                            )
                    # Filtra pelas chaves válidas
                    if "Chave_Acesso" in df_xml_completo.columns and chaves_autorizadas_validas:
                        df_xml_filtrado = df_xml_completo[df_xml_completo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
                    else:
                        df_xml_filtrado = df_xml_completo.copy()
                    group_cols = ["Código Produto", "Descrição Produto", "NCM"]
                    agg_dict = {
                        "Valor Produto": "sum",
                        "Valor ICMS": "sum",
                        "Base de Cálculo ICMS": "sum",
                        "Quantidade Comercial": lambda x: pd.to_numeric(x, errors="coerce").sum(),
                        "Valor Unitário Comercial": lambda x: pd.to_numeric(x, errors="coerce").iloc[0] if len(x) > 0 else 0,
                        "CST ICMS": lambda x: x.mode().iloc[0] if not x.mode().empty else '',
                        "Alíquota ICMS (%)": lambda x: x.mode().iloc[0] if not x.mode().empty else ''
                    }
                    resumo_produtos = df_xml_filtrado.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()
                    rename_dict = {
                        "Código Produto": "Cod_Produto",
                        "Descrição Produto": "Descrição_Produto",
                        "NCM": "NCM",
                        "Quantidade Comercial": "Quantidade",
                        "Valor Unitário Comercial": "Valor_Unitario",
                        "Valor Produto": "Valor_Total",
                        "Valor ICMS": "Valor_ICMS",
                        "Base de Cálculo ICMS": "Base_Calculo",
                        "CST ICMS": "CST_ICMS",
                        "Alíquota ICMS (%)": "Aliquota_ICMS_(%)"
                    }
                    if "pRedBC" in resumo_produtos.columns:
                        rename_dict["pRedBC"] = "Redução_BC_%"
                    resumo_produtos = resumo_produtos.rename(columns=rename_dict)
                    resumo_produtos = resumo_produtos[[
                        "Cod_Produto", "Descrição_Produto", "NCM", "Quantidade", "Valor_Unitario", "Valor_Total", "CST_ICMS", "Base_Calculo", "Aliquota_ICMS_(%)", "Valor_ICMS"
                    ]]
                    try:
                        resumo_produtos = resumo_produtos.sort_values(by="Cod_Produto", key=lambda x: pd.to_numeric(x, errors="coerce")).reset_index(drop=True)
                    except Exception:
                        resumo_produtos = resumo_produtos.sort_values(by="Cod_Produto").reset_index(drop=True)
                else:
                    resumo_produtos = pd.DataFrame(columns=["Cod_Produto", "Descrição_Produto", "NCM", "Quantidade", "Valor_Unitario", "Valor_Produto", "CST_ICMS", "Base_Calculo", "Aliquota_ICMS_(%)", "Valor_ICMS"])
                # Formatar colunas de valores como moeda brasileira com duas casas decimais
                for col in ["Valor_Total", "Base_Calculo", "Valor_ICMS", "Valor_Unitario"]:
                    if col in resumo_produtos.columns:
                        resumo_produtos[col] = resumo_produtos[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "")
                    # Não formatar Redução_BC_%
                
                escrever_aba(resumo_produtos, "Resumo_Produtos")
                # Filtra df_xml_completo para considerar apenas notas autorizadas e não canceladas
                if "Chave_Acesso" not in df_xml_completo.columns:
                    # Tenta preencher Chave_Acesso a partir de df_dados usando Número NF e Série
                    if "Número NF" in df_xml_completo.columns and "Série" in df_xml_completo.columns and "Chave_Acesso" in df_dados.columns:
                        df_xml_completo["Número NF"] = df_xml_completo["Número NF"].astype(str)
                        df_xml_completo["Série"] = df_xml_completo["Série"].astype(str)
                        dados_merge = df_dados[["Número_Doc", "Serie", "Chave_Acesso"]].copy()
                        dados_merge["Número_Doc"] = dados_merge["Número_Doc"].astype(str)
                        dados_merge["Serie"] = dados_merge["Serie"].astype(str)
                        dados_merge = dados_merge.rename(columns={"Número_Doc": "Número NF", "Serie": "Série"})
                        df_xml_completo = pd.merge(
                            df_xml_completo,
                            dados_merge,
                            on=["Número NF", "Série"],
                            how="left"
                        )
                if "Chave_Acesso" in df_xml_completo.columns and chaves_autorizadas_validas:
                    df_xml_filtrado = df_xml_completo[df_xml_completo["Chave_Acesso"].astype(str).isin(chaves_autorizadas_validas)]
                else:
                    df_xml_filtrado = df_xml_completo.copy()
                escrever_aba(df_xml_filtrado, "XML_Completo")
                escrever_aba(df_seq, "Sequência")
                escrever_aba(df_status, "Status")

            tmp.seek(0)
            st.success("✅ Planilha gerada com sucesso!")
            st.download_button("📥 Baixar Planilha", tmp.read(), file_name="Dados NFC-e.xlsx")

# Garante execução da função app() ao rodar com streamlit
if __name__ == "__main__":
    app()
