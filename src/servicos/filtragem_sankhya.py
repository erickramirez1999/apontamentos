"""
Serviço de filtragem do Sankhya.

Aplica as regras do LLE Protestos:
- Atraso entre 60 e 364 dias (inclusivo)
- Histórico:
    - PROT (#PROT, -PROT, _PROT, etc) em qualquer título → cliente inteiro EXCLUÍDO
    - ACORDO isolado (sem QUEBRA antes) → bloqueia título
    - DV TOTAL → bloqueia título
    - #Ticket, CHAMADO, TMK (com número) → bloqueia título
    - Terceirizadas (RENNOVARE, KNOWHOW, SOLUTE) SEM 'DV' → bloqueia título
    - Terceirizadas COM 'DV' no mesmo histórico → libera título
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, BinaryIO

import pandas as pd


# Faixas de atraso
ATRASO_MIN = 60
ATRASO_MAX = 364

# Padrões de histórico
# Captura "PROT" como palavra independente — aceita prefixos:
#   #PROT, # PROT, -PROT, - PROT, _PROT, –PROT, ou PROT solto entre espaços
# NÃO pega: PROTOCOLO, PROTESTADO, REPROTOCOLAR (palavras que CONTÊM PROT)
PROT_PATTERN = re.compile(r"(?:^|[#\-_–\s])PROT\b", re.IGNORECASE)
# ACORDO isolado: palavra ACORDO NÃO precedida por QUEBRA
ACORDO_ISOLADO = re.compile(r"(?<!QUEBRA[\s\-])(?<!QUEBRA)\bACORDO\b", re.IGNORECASE)
# QUEBRA presente (qualquer variante: QUEBRA, QUEBRA DE ACORDO, QUEBRA ACORDO)
QUEBRA_PATTERN = re.compile(r"\bQUEBRA\b", re.IGNORECASE)
DV_TOTAL_PATTERN = re.compile(r"\bDV\s*TOTAL\b", re.IGNORECASE)
TICKET_PATTERN = re.compile(r"\bTICKET\b", re.IGNORECASE)
CHAMADO_PATTERN = re.compile(r"\bCHAMADO\b", re.IGNORECASE)
TMK_PATTERN = re.compile(r"\bTMK\b", re.IGNORECASE)

TERCEIRIZADAS = ("RENNOVARE", "KNOWHOW", "SOLUTE")
# Lookarounds em vez de \b porque \b não funciona com underscore
# (queremos achar RENNOVARE em "1ºLT_022026_RENNOVARE-DV" também).
TERCEIRIZADA_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(TERCEIRIZADAS) + r")(?![A-Za-z])",
    re.IGNORECASE,
)
DV_PATTERN = re.compile(r"(?<![A-Za-z])DV(?![A-Za-z])", re.IGNORECASE)

# Tipos de título que SÃO boletos (alinhado com LLE Acordos - 13/05/2026).
# Tipos fora dessa lista (crédito automático, depósito, NF de serviço, etc)
# não viram protesto.
TIPOS_TITULO_PERMITIDOS = {4, 28, 29, 39, 40, 41, 47, 48, 64, 70}


@dataclass
class ResultadoFiltragem:
    df_validos: pd.DataFrame
    total_brutos: int
    total_validos: int
    clientes_excluidos_prot: int
    titulos_excluidos_atraso: int
    titulos_excluidos_historico: int
    titulos_excluidos_tipo: int = 0
    tipos_ignorados: set = None
    motivos_exclusao: dict[str, int] = None

    def __post_init__(self):
        if self.tipos_ignorados is None:
            self.tipos_ignorados = set()
        if self.motivos_exclusao is None:
            self.motivos_exclusao = {}


def _achar_coluna(df: pd.DataFrame, *nomes_possiveis: str) -> str | None:
    """
    Busca uma coluna no df ignorando maiúsculas/minúsculas e espaços.
    Resolve o bug do Sankhya que exporta 'Atraso (dias)' ou 'Atraso (Dias)'
    dependendo da configuração.
    """
    cols_norm = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes_possiveis:
        chave = nome.strip().lower()
        if chave in cols_norm:
            return cols_norm[chave]
    return None


def ler_planilha_sankhya(arquivo: BinaryIO | bytes | str) -> pd.DataFrame:
    """
    Lê a planilha Sankhya (xls/xlsx) e retorna DataFrame válido.
    O cabeçalho real fica na linha 2 (linhas 0 e 1 são metadados).
    """
    # Suporta tanto BytesIO quanto path
    if isinstance(arquivo, bytes):
        arquivo = BytesIO(arquivo)

    try:
        df = pd.read_excel(arquivo, engine="xlrd", header=2)
    except Exception:
        # Fallback pra xlsx
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)
        df = pd.read_excel(arquivo, header=2)

    # Remove a linha de rodapé (Parceiro vazio)
    df = df[df["Parceiro"].notna()].copy()
    return df


def aplicar_filtros(df: pd.DataFrame) -> ResultadoFiltragem:
    """
    Aplica TODOS os filtros do projeto LLE Protestos.

    Retorna ResultadoFiltragem com o DataFrame dos títulos válidos.
    """
    total_brutos = len(df)
    motivos: dict[str, int] = {}

    # 0a) FILTRO DE NATUREZA: só "Vendas notas fiscais" (Erick - 09/06/2026):
    # Sankhya exporta adiantamentos, comissões, benefícios etc — descarta tudo,
    # só vendas viram protesto.
    col_natureza = _achar_coluna(df, "Descrição (Natureza)", "Descricao (Natureza)",
                                  "Descrição Natureza", "Natureza Descrição")
    titulos_excluidos_natureza = 0
    if col_natureza is not None:
        mask_natureza_ok = (
            df[col_natureza].astype(str).str.strip().str.lower()
            == "vendas notas fiscais"
        )
        titulos_excluidos_natureza = int((~mask_natureza_ok).sum())
        df = df[mask_natureza_ok].copy()
        motivos["natureza_nao_vendas"] = titulos_excluidos_natureza

    # 0b) FILTRO DE TIPO DE TÍTULO (Erick - 25/05/2026):
    # Só boletos viram protesto. Outros tipos (depósito, NF de serviço,
    # crédito automático, etc) são descartados silenciosamente.
    titulos_excluidos_tipo = 0
    tipos_ignorados: set[int] = set()

    if "Tipo de Título" in df.columns:
        tipos = pd.to_numeric(df["Tipo de Título"], errors="coerce")
        mask_tipo_ok = tipos.isin(TIPOS_TITULO_PERMITIDOS)
        # NaN também é fora (não é boleto)
        mask_tipo_ok = mask_tipo_ok.fillna(False)

        # Registra tipos que foram filtrados
        tipos_fora = tipos[~mask_tipo_ok & tipos.notna()]
        tipos_ignorados = set(int(t) for t in tipos_fora.unique())
        titulos_excluidos_tipo = int((~mask_tipo_ok).sum())

        df = df[mask_tipo_ok].copy()
        motivos["tipo_titulo_nao_boleto"] = titulos_excluidos_tipo

    # 0c) FILTRO COBCLOUD (Erick - 09/06/2026):
    # Cliente com QUALQUER título tendo código de acordo CobCloud preenchido
    # tem TODOS os títulos removidos (mesma lógica do PROT).
    col_cobcloud = _achar_coluna(df, "Código do acordo CobCloud", "Cod. do acordo CobCloud",
                                  "Acordo CobCloud", "CobCloud")
    titulos_excluidos_cobcloud = 0
    if col_cobcloud is not None:
        # Acha clientes que têm QUALQUER título com código CobCloud preenchido
        clientes_cobcloud = set()
        for cod, sub in df.groupby("Parceiro"):
            for valor in sub[col_cobcloud]:
                # Aceita string não vazia OU número (não NaN)
                if pd.notna(valor) and str(valor).strip() not in ("", "nan", "0"):
                    clientes_cobcloud.add(cod)
                    break

        df_sem_cobcloud = df[~df["Parceiro"].isin(clientes_cobcloud)].copy()
        titulos_excluidos_cobcloud = len(df) - len(df_sem_cobcloud)
        df = df_sem_cobcloud
        motivos["cliente_com_CobCloud"] = titulos_excluidos_cobcloud

    # 1) Identificar clientes com #PROT em QUALQUER título → excluir todos os títulos
    clientes_prot = set()
    for cod, sub in df.groupby("Parceiro"):
        for hist in sub["Histórico"].fillna(""):
            if PROT_PATTERN.search(str(hist)):
                clientes_prot.add(cod)
                break

    df_sem_prot = df[~df["Parceiro"].isin(clientes_prot)].copy()
    titulos_excluidos_prot = len(df) - len(df_sem_prot)
    motivos["cliente_com_PROT"] = titulos_excluidos_prot

    # 2) Filtrar por atraso (60 <= Atraso <= 364) — case-insensitive (bug fix)
    col_atraso = _achar_coluna(df_sem_prot, "Atraso (dias)", "Atraso (Dias)",
                                "Atraso em dias", "Atraso")
    if col_atraso is None:
        raise KeyError(
            f"Coluna de atraso não encontrada. Colunas disponíveis: {list(df_sem_prot.columns)}"
        )
    atraso = pd.to_numeric(df_sem_prot[col_atraso], errors="coerce")
    mask_atraso = (atraso >= ATRASO_MIN) & (atraso <= ATRASO_MAX)
    titulos_excluidos_atraso = (~mask_atraso).sum()
    motivos["atraso_fora_60_364"] = int(titulos_excluidos_atraso)
    df_atraso_ok = df_sem_prot[mask_atraso].copy()

    # 3) Filtrar por histórico (linha a linha)
    bloqueados_idx = []
    motivos_titulo = {
        "ACORDO_isolado": 0,
        "DV_TOTAL": 0,
        "TICKET": 0,
        "CHAMADO": 0,
        "TMK": 0,
        "terceirizada_sem_DV": 0,
    }

    for idx, row in df_atraso_ok.iterrows():
        hist = str(row["Histórico"]) if pd.notna(row["Histórico"]) else ""

        bloqueia, motivo = _avaliar_historico(hist)
        if bloqueia:
            bloqueados_idx.append(idx)
            if motivo in motivos_titulo:
                motivos_titulo[motivo] += 1

    df_validos = df_atraso_ok.drop(bloqueados_idx).copy()
    titulos_excluidos_hist = len(bloqueados_idx)
    motivos.update(motivos_titulo)

    return ResultadoFiltragem(
        df_validos=df_validos,
        total_brutos=total_brutos,
        total_validos=len(df_validos),
        clientes_excluidos_prot=len(clientes_prot),
        titulos_excluidos_atraso=int(titulos_excluidos_atraso),
        titulos_excluidos_historico=titulos_excluidos_hist,
        titulos_excluidos_tipo=titulos_excluidos_tipo,
        tipos_ignorados=tipos_ignorados,
        motivos_exclusao=motivos,
    )


def _avaliar_historico(hist: str) -> tuple[bool, str]:
    """
    Avalia o histórico e retorna (bloqueia, motivo).
    Se bloqueia=False, o título é válido.
    """
    if not hist or hist.strip() == "" or hist.lower() == "nan":
        return False, ""

    # DV TOTAL — bloqueia
    if DV_TOTAL_PATTERN.search(hist):
        return True, "DV_TOTAL"

    # #Ticket / CHAMADO / TMK com número
    if TICKET_PATTERN.search(hist):
        return True, "TICKET"
    if CHAMADO_PATTERN.search(hist):
        return True, "CHAMADO"
    if TMK_PATTERN.search(hist):
        return True, "TMK"

    # ACORDO isolado (sem QUEBRA antes)
    if ACORDO_ISOLADO.search(hist) and not QUEBRA_PATTERN.search(hist):
        return True, "ACORDO_isolado"

    # Terceirizada: precisa de DV no mesmo histórico
    if TERCEIRIZADA_PATTERN.search(hist):
        if not DV_PATTERN.search(hist):
            return True, "terceirizada_sem_DV"

    return False, ""


def classificar_empresa(empresa_cod: int | float | None,
                        vendedor_cod: int | float | None) -> str:
    """
    Classifica empresa em PISA / KING / TRIO.

    - Empresa=1 → PISA
    - Empresa=2 e Vendedor<5000 → KING
    - Empresa=2 e Vendedor>=5000 → TRIO
    """
    try:
        emp = int(empresa_cod) if pd.notna(empresa_cod) else None
        vend = int(vendedor_cod) if pd.notna(vendedor_cod) else 0
    except (ValueError, TypeError):
        return "PISA"  # fallback seguro

    if emp == 1:
        return "PISA"
    if emp == 2:
        if vend >= 5000:
            return "TRIO"
        return "KING"
    return "PISA"


def normalizar_banco(descricao: Any) -> str:
    """
    Normaliza nome do banco a partir de 'Descrição (Banco)'.

    'Banco Santander S.A.' → 'Santander'
    'Banco Bradesco S.A.' → 'Bradesco'
    """
    if pd.isna(descricao):
        return "Desconhecido"
    s = str(descricao).strip().lower()
    if "santander" in s:
        return "Santander"
    if "bradesco" in s:
        return "Bradesco"
    if "itau" in s or "itaú" in s:
        return "Itau"
    if "caixa" in s:
        return "Caixa"
    if "banco do brasil" in s or "bb" in s:
        return "BancoDoBrasil"
    return str(descricao).strip()
