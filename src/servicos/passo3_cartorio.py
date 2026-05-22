"""
Serviço do PASSO 3: seleção final de títulos e geração do arquivo TXT.

A partir da planilha completa (vida total dos clientes):

1. Aplica filtros (mesmos do passo 1: PROT, ACORDO, etc + atraso 60-364)
2. Calcula o MONTANTE TOTAL da dívida de cada cliente (soma TODOS títulos válidos)
3. Define quantidade máxima de títulos POR CLIENTE com base no montante:
   - até 10k → 2 títulos
   - 10k até 30k → 4 títulos
   - 30k em diante → 5 títulos
4. Seleciona os títulos: MAIOR VALOR primeiro, desempate por MAIOR ATRASO
5. Agrupa selecionados por (Empresa 1 ou 2) x Banco (Santander/Bradesco)
6. Gera arquivo .txt:
   Empresa 1 Santander: nro1, nro2, ...
   Empresa 1 Bradesco: ...
   Empresa 2 Santander: ...
   Empresa 2 Bradesco: ...
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from src.servicos.filtragem_sankhya import normalizar_banco


def limite_por_montante(montante: float) -> int:
    """Retorna a quantidade máxima de títulos com base no montante total."""
    if montante <= 10000:
        return 2
    if montante <= 30000:
        return 4
    return 5


@dataclass
class ResultadoPasso3:
    df_selecionados: pd.DataFrame
    total_clientes: int
    total_titulos: int
    valor_total: float
    grupos: dict[str, list[str]]  # 'Empresa 1 Santander' -> [nros]


def selecionar_titulos_passo3(df_validos: pd.DataFrame) -> ResultadoPasso3:
    """
    A partir do DF de títulos válidos (já passados pelo filtro de histórico/atraso),
    seleciona os títulos pra protesto seguindo as regras de montante.
    """
    if df_validos.empty:
        return ResultadoPasso3(
            df_selecionados=df_validos.copy(),
            total_clientes=0,
            total_titulos=0,
            valor_total=0.0,
            grupos={},
        )

    df = df_validos.copy()

    # Calcular montante total por cliente
    montantes = df.groupby("Parceiro")["Vlr do Desdobramento"].sum().to_dict()

    selecionados_idx = []

    for cod_parceiro, sub in df.groupby("Parceiro"):
        montante = montantes[cod_parceiro]
        limite = limite_por_montante(montante)

        # Ordenar por: VALOR desc, depois ATRASO desc
        sub_ordenado = sub.sort_values(
            ["Vlr do Desdobramento", "Atraso (dias)"],
            ascending=[False, False]
        )

        # Pegar os N maiores
        top_n = sub_ordenado.head(limite)
        selecionados_idx.extend(top_n.index.tolist())

    df_sel = df.loc[selecionados_idx].copy()

    # Agrupar por Empresa + Banco
    grupos: dict[str, list[str]] = defaultdict(list)
    for _, row in df_sel.iterrows():
        empresa_cod = int(row["Empresa"]) if pd.notna(row["Empresa"]) else 0
        banco = normalizar_banco(row.get("Descrição (Banco)", ""))
        chave = f"Empresa {empresa_cod} {banco}"

        nro_unico = row["Nro Único"]
        if pd.notna(nro_unico):
            grupos[chave].append(str(int(nro_unico)))

    valor_total = float(df_sel["Vlr do Desdobramento"].sum())
    total_clientes = df_sel["Parceiro"].nunique()

    return ResultadoPasso3(
        df_selecionados=df_sel,
        total_clientes=total_clientes,
        total_titulos=len(df_sel),
        valor_total=valor_total,
        grupos=dict(grupos),
    )


def gerar_txt_passo3(grupos: dict[str, list[str]]) -> str:
    """
    Gera o arquivo TXT no formato:
    Empresa 1 Santander: 1234567, 4564789
    Empresa 2 Bradesco: 4567897, 456789
    """
    if not grupos:
        return ""

    # Ordenar chaves: Empresa 1 antes de 2, Santander antes de Bradesco
    def ordenar_chave(k: str) -> tuple:
        partes = k.split()
        empresa = int(partes[1]) if len(partes) >= 2 and partes[1].isdigit() else 9
        banco = " ".join(partes[2:]) if len(partes) >= 3 else ""
        # Santander primeiro
        ordem_banco = 0 if "Santander" in banco else (1 if "Bradesco" in banco else 9)
        return (empresa, ordem_banco, banco)

    linhas = []
    for chave in sorted(grupos.keys(), key=ordenar_chave):
        nros = grupos[chave]
        linhas.append(f"{chave}: {', '.join(nros)}")

    return "\n".join(linhas) + "\n"
