"""Tradutor central de códigos internos pra nomes amigáveis."""
from __future__ import annotations


PERFIS = {
    "ADMIN": "Gestão",
    "OPERADOR": "Operador",
    "DIRETORIA": "Diretoria",
    "FINANCEIRO": "Setor Financeiro",
}

STATUS_PROTESTO = {
    "NAO_PROTESTADO": "Não protestado",
    "PROTESTADO": "Protestado",
    "ACORDO": "Em acordo",
    "PAGO": "Pago",
}

STATUS_SERASA = {
    "NAO_ENVIADO": "Não enviado ao Serasa",
    "ENVIADO": "Enviado ao Serasa",
    "EXCLUIDO": "Excluído do Serasa",
}

INDICADOR_CONSOLIDADO = {
    "BAIXADO_TOTAL": "Baixado total",
    "PENDENTE_SERASA": "Pendente Serasa",
    "PENDENTE_PROTESTO": "Pendente Protesto",
    "PENDENTE_PROTESTO_E_SERASA": "Pendente Protesto e Serasa",
}

EMPRESAS = {
    "PISA": "PISA",
    "KING": "KING",
    "TRIO": "TRIO",
}

ACOES = {
    "LOGIN": "Fez login",
    "CRIAR_USUARIO": "Cadastrou usuário",
    "APROVAR_USUARIO": "Aprovou usuário",
    "RECUSAR_USUARIO": "Recusou usuário",
    "INATIVAR_USUARIO": "Inativou usuário",
    "REATIVAR_USUARIO": "Reativou usuário",
    "ALTERAR_PERFIL_USUARIO": "Alterou cargo do usuário",
    "REDEFINIR_SENHA_USUARIO": "Redefiniu senha de usuário",
    "TROCAR_PROPRIA_SENHA": "Alterou a própria senha",
    "EDITAR_PARAMETROS": "Editou parâmetros do sistema",
    "UPLOAD_SANKHYA": "Subiu planilha do Sankhya",
    "UPLOAD_SERASA": "Subiu arquivo do Serasa",
    "GERAR_PASSO1": "Gerou planilha do Passo 1",
    "GERAR_PASSO2": "Gerou planilha do Passo 2",
    "GERAR_PASSO3": "Gerou arquivo do Passo 3 (cartório)",
    "ALTERAR_STATUS_PROTESTO": "Alterou status de protesto",
    "ALTERAR_STATUS_SERASA": "Alterou status do Serasa",
    "ARQUIVAR_CLIENTE": "Arquivou cliente",
    "DESARQUIVAR_CLIENTE": "Desarquivou cliente",
}


def traduzir_perfil(codigo: str) -> str:
    return PERFIS.get(codigo, _humanizar(codigo))


def traduzir_status_protesto(codigo: str) -> str:
    return STATUS_PROTESTO.get(codigo, _humanizar(codigo))


def traduzir_status_serasa(codigo: str) -> str:
    return STATUS_SERASA.get(codigo, _humanizar(codigo))


def traduzir_indicador(codigo: str) -> str:
    return INDICADOR_CONSOLIDADO.get(codigo, _humanizar(codigo))


def traduzir_empresa(codigo: str) -> str:
    return EMPRESAS.get(codigo, codigo)


def traduzir_acao(codigo: str) -> str:
    return ACOES.get(codigo, _humanizar(codigo))


def _humanizar(codigo: str) -> str:
    if not codigo:
        return ""
    palavras = str(codigo).replace("_", " ").lower().split()
    return " ".join(p.capitalize() for p in palavras)
