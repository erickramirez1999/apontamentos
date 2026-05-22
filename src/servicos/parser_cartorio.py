"""
Parser do relatório do cartório (Excel).

Formato: planilha com colunas como Devedor, Documento, Cartório, Protocolo,
Data, Número do título, Valor, Saldo, Ocorrência, Tipo autorização, etc.

Regras:
- 1 linha = 1 título protestado
- Cliente identificado por NOME (Devedor) + CNPJ/CPF (Documento) como bonus
- `Tipo autorização = CANCELAMENTO` indica que o cliente PAGOU (cartório
  só cancela com pagamento) → status = PAGO + arquivado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import BinaryIO

import pandas as pd


# Mapa de colunas esperadas
COLUNA_DEVEDOR = "Devedor"
COLUNA_DOC = "Documento"
COLUNA_CARTORIO = "Cartório"
COLUNA_PROTOCOLO = "Protocolo"
COLUNA_DATA_PROTESTO = "Data"
COLUNA_NRO_TITULO = "Número do título"
COLUNA_NOSSO_NUMERO = "Nosso número"
COLUNA_VALOR = "Valor"
COLUNA_SALDO = "Saldo"
COLUNA_OCORRENCIA = "Ocorrência"
COLUNA_TIPO_AUT = "Tipo autorização"
COLUNA_DATA_AUT = "Data autorização"
COLUNA_DATA_VENC = "Data vencimento"
COLUNA_DATA_EMISSAO = "Data emissão"
COLUNA_MUNICIPIO = "Município"
COLUNA_UF = "UF"


@dataclass
class TituloCartorio:
    """Um título protestado conforme aparece no relatório do cartório."""
    devedor_nome: str
    devedor_documento: str | None
    cod_parceiro: int | None  # vem de "Nosso número" — é o código do Sankhya
    cartorio: str
    municipio: str | None
    uf: str | None
    protocolo: str
    nro_titulo: str | None
    valor: float | None
    saldo: float | None
    data_protesto: date | None
    data_vencimento: date | None
    data_emissao: date | None
    cancelado: bool
    data_cancelamento: date | None


@dataclass
class RelatorioCartorio:
    titulos: list[TituloCartorio]
    total_linhas: int
    total_clientes_unicos: int
    total_cancelados: int


def _parse_data(v) -> date | None:
    if pd.isna(v) or v in ("", None):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    # Formato DD/MM/YYYY
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_valor(v) -> float | None:
    if pd.isna(v) or v in ("", None):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    # Formato BR: "18.685,45"
    s = str(v).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _str_ou_none(v) -> str | None:
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def ler_relatorio_cartorio(arquivo: BinaryIO | bytes | str) -> RelatorioCartorio:
    """
    Lê um relatório XLSX do cartório.

    Args:
        arquivo: BytesIO, bytes, file-like ou caminho

    Returns:
        RelatorioCartorio com lista de títulos parseados
    """
    if isinstance(arquivo, bytes):
        arquivo = BytesIO(arquivo)

    df = pd.read_excel(arquivo, header=0)

    titulos: list[TituloCartorio] = []
    cancelados = 0
    nomes_unicos: set[str] = set()

    for _, row in df.iterrows():
        devedor = _str_ou_none(row.get(COLUNA_DEVEDOR))
        if not devedor:
            continue

        tipo_aut = _str_ou_none(row.get(COLUNA_TIPO_AUT))
        cancelado = (tipo_aut or "").upper() == "CANCELAMENTO"
        if cancelado:
            cancelados += 1

        nomes_unicos.add(devedor.upper())

        # Nosso número = código do parceiro no Sankhya
        cod_raw = row.get(COLUNA_NOSSO_NUMERO)
        cod_parceiro = None
        if pd.notna(cod_raw):
            try:
                cod_parceiro = int(cod_raw)
            except (ValueError, TypeError):
                cod_parceiro = None

        titulos.append(TituloCartorio(
            devedor_nome=devedor,
            devedor_documento=_str_ou_none(row.get(COLUNA_DOC)),
            cod_parceiro=cod_parceiro,
            cartorio=_str_ou_none(row.get(COLUNA_CARTORIO)) or "",
            municipio=_str_ou_none(row.get(COLUNA_MUNICIPIO)),
            uf=_str_ou_none(row.get(COLUNA_UF)),
            protocolo=_str_ou_none(row.get(COLUNA_PROTOCOLO)) or "",
            nro_titulo=_str_ou_none(row.get(COLUNA_NRO_TITULO)),
            valor=_parse_valor(row.get(COLUNA_VALOR)),
            saldo=_parse_valor(row.get(COLUNA_SALDO)),
            data_protesto=_parse_data(row.get(COLUNA_DATA_PROTESTO)),
            data_vencimento=_parse_data(row.get(COLUNA_DATA_VENC)),
            data_emissao=_parse_data(row.get(COLUNA_DATA_EMISSAO)),
            cancelado=cancelado,
            data_cancelamento=_parse_data(row.get(COLUNA_DATA_AUT)) if cancelado else None,
        ))

    return RelatorioCartorio(
        titulos=titulos,
        total_linhas=len(titulos),
        total_clientes_unicos=len(nomes_unicos),
        total_cancelados=cancelados,
    )
