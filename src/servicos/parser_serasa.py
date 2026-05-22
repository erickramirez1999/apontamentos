"""
Parser dos arquivos CNAB do Serasa.

Formato: linhas de 600 chars, encoding latin-1.
Nome: Inclusão_DD_MM_YYYY_NNNN.txt ou Exclusão_DD_MM_YYYY_NNNN.txt
  - NNNN é sequencial único compartilhado entre Inclusão e Exclusão.

Posições da linha de detalhe (inicia com '1I' ou '1E'):
  0:2    tipo registro
  2:8    código convênio
  8:16   data YYYYMMDD
  33:47  CPF/CNPJ (14 dígitos com zeros à esquerda)
  105:175 razão social
  411:419 CEP / parte de endereço
  419:432 região do valor (parsing pendente refinamento)
  593:600 sequencial linha
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import BinaryIO


@dataclass
class TituloSerasa:
    cnpj_cpf: str
    nome: str
    cep: str
    nro_unico_serasa: str
    valor: float | None
    data: date


@dataclass
class ArquivoSerasa:
    tipo: str            # 'INCLUSAO' ou 'EXCLUSAO'
    data_arquivo: date
    sequencial: int
    titulos: list[TituloSerasa]


def _extrair_metadados_nome(nome: str) -> tuple[str, date, int]:
    """
    Extrai tipo, data e sequencial do nome do arquivo:
    Inclusão_21_05_2026_4547.txt
    Exclusão_19_05_2026_4542.txt
    """
    nome_base = Path(nome).name
    nome_base = re.sub(r'\.[a-zA-Z]+$', '', nome_base)  # tira extensão

    # Normalizar acento
    nome_norm = nome_base.replace("Inclusão", "Inclusao").replace("Exclusão", "Exclusao")

    # Aceita separadores: _ . - ou espaço
    match = re.match(
        r'(Inclusao|Exclusao)[ _.\-]+(\d{2})[ _.\-]+(\d{2})[ _.\-]+(\d{4})[ _.\-]+(\d+)',
        nome_norm,
        re.IGNORECASE
    )
    if not match:
        raise ValueError(f"Nome de arquivo Serasa inválido: {nome}")

    tipo_str, dia, mes, ano, seq = match.groups()
    tipo = "INCLUSAO" if tipo_str.lower() == "inclusao" else "EXCLUSAO"
    data = date(int(ano), int(mes), int(dia))
    sequencial = int(seq)
    return tipo, data, sequencial


def _parsear_data_yyyymmdd(s: str) -> date | None:
    s = s.strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def parsear_arquivo_serasa(nome_arquivo: str,
                            conteudo: bytes | str | BinaryIO) -> ArquivoSerasa:
    """
    Lê um arquivo CNAB Serasa.

    Args:
        nome_arquivo: nome original com data + sequencial
        conteudo: bytes, string ou file-like

    Returns:
        ArquivoSerasa parseado
    """
    if hasattr(conteudo, "read"):
        conteudo = conteudo.read()
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("latin-1")

    tipo, data_arq, sequencial = _extrair_metadados_nome(nome_arquivo)

    linhas = conteudo.splitlines()
    titulos: list[TituloSerasa] = []

    for linha in linhas:
        if len(linha) < 175:
            continue
        # Pula header e trailer (não começam com '1I' ou '1E')
        prefixo = linha[:2]
        if prefixo not in ("1I", "1E"):
            continue

        cnpj_cpf = linha[33:47].strip()
        nome = linha[105:175].rstrip()
        cep = linha[411:419].strip() if len(linha) >= 419 else ""

        # nro único do Serasa repete em 432-450 (geralmente 9 dígitos × 2)
        nro_unico_serasa = ""
        if len(linha) >= 450:
            campo = linha[432:450].strip()
            if campo:
                nro_unico_serasa = campo[:9]

        # Data do título no registro (8 chars no início pós convenio)
        data_str = linha[8:16] if len(linha) >= 16 else ""
        data_titulo = _parsear_data_yyyymmdd(data_str) or data_arq

        if not nome:
            continue

        titulos.append(TituloSerasa(
            cnpj_cpf=cnpj_cpf,
            nome=nome,
            cep=cep,
            nro_unico_serasa=nro_unico_serasa,
            valor=None,  # parsing de valor pode ser refinado depois
            data=data_titulo,
        ))

    return ArquivoSerasa(
        tipo=tipo,
        data_arquivo=data_arq,
        sequencial=sequencial,
        titulos=titulos,
    )
