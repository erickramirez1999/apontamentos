"""Tipos centrais do sistema."""
from __future__ import annotations
from enum import Enum


class PerfilUsuario(str, Enum):
    """
    Perfis de acesso.

    - ADMIN: pode tudo (mostrado como 'Gestão' na UI).
    - OPERADOR: operacional (uploads, geração de planilhas, altera status).
    - DIRETORIA: só visualiza.
    - FINANCEIRO: só visualiza (acesso compartilhado pelo Setor Financeiro).
    """
    ADMIN = "ADMIN"
    OPERADOR = "OPERADOR"
    DIRETORIA = "DIRETORIA"
    FINANCEIRO = "FINANCEIRO"


class StatusProtesto(str, Enum):
    NAO_PROTESTADO = "NAO_PROTESTADO"
    PROTESTADO = "PROTESTADO"
    ACORDO = "ACORDO"
    PAGO = "PAGO"


class StatusSerasa(str, Enum):
    NAO_ENVIADO = "NAO_ENVIADO"
    ENVIADO = "ENVIADO"
    EXCLUIDO = "EXCLUIDO"


class IndicadorConsolidado(str, Enum):
    BAIXADO_TOTAL = "BAIXADO_TOTAL"
    PENDENTE_SERASA = "PENDENTE_SERASA"
    PENDENTE_PROTESTO = "PENDENTE_PROTESTO"
    PENDENTE_PROTESTO_E_SERASA = "PENDENTE_PROTESTO_E_SERASA"


class EmpresaLLE(str, Enum):
    PISA = "PISA"
    KING = "KING"
    TRIO = "TRIO"


class TipoEventoSerasa(str, Enum):
    INCLUSAO = "INCLUSAO"
    EXCLUSAO = "EXCLUSAO"
