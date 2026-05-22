"""
Serviço de agrupamento e geração da planilha resumida.

Regras:
- Cada LINHA da saída = combinação única de (CLIENTE + EMPRESA classificada PISA/KING/TRIO)
- VENDEDOR e APELIDO = lista de todos separados por vírgula
- VALOR = soma dos títulos elegíveis dessa combinação
- ATRASO = maior atraso da combinação

Colunas de saída (modelo Pasta_de_Trabalho1.xlsx):
EMPRESA | PARCEIRO | NOME DO PARCEIRO | VENDEDOR | APELIDO | VALOR | ATRASO
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

import pandas as pd

from src.servicos.filtragem_sankhya import classificar_empresa


def agrupar_para_planilha_resumo(df_validos: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa títulos válidos em: 1 linha por (Cliente + Empresa).

    Retorna DataFrame com colunas:
    EMPRESA | PARCEIRO | NOME DO PARCEIRO | VENDEDOR | APELIDO | VALOR | ATRASO
    """
    if df_validos.empty:
        return pd.DataFrame(columns=[
            "EMPRESA", "PARCEIRO", "NOME DO PARCEIRO",
            "VENDEDOR", "APELIDO", "VALOR ", "ATRASO "
        ])

    # Adicionar coluna de empresa classificada
    df = df_validos.copy()
    df["empresa_lle"] = df.apply(
        lambda r: classificar_empresa(r["Empresa"], r["Vendedor"]),
        axis=1
    )

    # Agrupar
    linhas = []
    for (cod_parceiro, empresa), sub in df.groupby(["Parceiro", "empresa_lle"]):
        nome = sub["Nome Parceiro (Parceiro)"].iloc[0]

        # Vendedores únicos (preservando ordem de aparição)
        vendedores_unicos = []
        vendedores_set = set()
        for v in sub["Vendedor"]:
            if pd.notna(v):
                vi = int(v)
                if vi not in vendedores_set:
                    vendedores_unicos.append(vi)
                    vendedores_set.add(vi)

        apelidos_unicos = []
        apelidos_set = set()
        for a in sub["Apelido"]:
            if pd.notna(a):
                ai = str(a).strip()
                if ai and ai not in apelidos_set:
                    apelidos_unicos.append(ai)
                    apelidos_set.add(ai)

        valor_total = float(sub["Vlr do Desdobramento"].sum())
        atraso_max = int(sub["Atraso (dias)"].max())

        linhas.append({
            "EMPRESA": empresa,
            "PARCEIRO": int(cod_parceiro),
            "NOME DO PARCEIRO": nome,
            "VENDEDOR": ", ".join(str(v) for v in vendedores_unicos),
            "APELIDO": ", ".join(apelidos_unicos),
            "VALOR ": round(valor_total, 2),
            "ATRASO ": atraso_max,
        })

    df_out = pd.DataFrame(linhas)
    # Ordenar por VALOR desc (maiores primeiro)
    df_out = df_out.sort_values("VALOR ", ascending=False).reset_index(drop=True)
    return df_out


def gerar_excel_resumo(df_resumo: pd.DataFrame) -> bytes:
    """
    Gera Excel (.xlsx) a partir do DataFrame resumido.
    Retorna bytes prontos pra download.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_resumo.to_excel(writer, sheet_name="Planilha1", index=False)

        # Ajustar largura das colunas
        ws = writer.sheets["Planilha1"]
        larguras = {
            "A": 10,   # EMPRESA
            "B": 12,   # PARCEIRO
            "C": 50,   # NOME
            "D": 25,   # VENDEDOR
            "E": 35,   # APELIDO
            "F": 14,   # VALOR
            "G": 10,   # ATRASO
        }
        for col, larg in larguras.items():
            ws.column_dimensions[col].width = larg

    return output.getvalue()
