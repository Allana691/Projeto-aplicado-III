"""Registro de respostas e recomendações no Google Sheets.

A planilha deve conter as abas Respostas, Recomendacoes e Avaliacoes.
Os cabeçalhos são inicializados apenas quando a primeira linha está vazia.
"""
import json
from datetime import datetime, timezone

import gspread
import streamlit as st


COLUNAS = {
    "Respostas": [
        "id_participacao", "data_hora_utc", "nome_opcional",
        "situacao_p01", "experiencia_p02", "formacao_p04",
        "formacao_opcao_p04", "interesses_p05", "interesses_nao_sei_p05",
        "objetivo_p06",
    ],
    "Recomendacoes": [
        "id_participacao", "posicao", "id_curso_canonico",
        "nome_curso", "link_do_curso",
    ],
    "Avaliacoes": [
        "id_participacao", "data_hora_utc",
        "avaliacao_p07", "avaliacao_p08", "avaliacao_p09",
    ],
}


def _abrir_planilha():
    """Usa credenciais privadas dos Secrets (não pertencem ao GitHub)."""
    credenciais = json.loads(st.secrets["google_service_account_json"])
    cliente = gspread.service_account_from_dict(credenciais)
    return cliente.open_by_key(st.secrets["google_sheets_id"])


def _aba(planilha, nome):
    aba = planilha.worksheet(nome)
    atual = aba.row_values(1)
    if not atual:
        aba.update([COLUNAS[nome]], "A1", value_input_option="RAW")
    elif atual != COLUNAS[nome]:
        raise ValueError(f"Cabeçalhos inesperados na aba {nome}; nenhuma linha foi sobrescrita.")
    return aba


def _juntar(itens):
    return " | ".join(str(item) for item in itens)


def registrar_participacao(identificador, instante, nome, respostas, cursos):
    """Registra questionário e 5 recomendações, retomando envios parciais."""
    planilha = _abrir_planilha()
    aba_respostas = _aba(planilha, "Respostas")
    if identificador not in aba_respostas.col_values(1)[1:]:
        aba_respostas.append_row(
            [
                identificador, instante, nome.strip(),
                respostas.get("situacao", ""),
                _juntar(respostas.get("experiencia", [])),
                _juntar(respostas.get("formacao", [])),
                respostas.get("formacao_opcao", ""),
                _juntar(respostas.get("interesses", [])),
                "Sim" if respostas.get("nao_sei", False) else "Não",
                respostas.get("objetivo", ""),
            ],
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
        )

    aba_cursos = _aba(planilha, "Recomendacoes")
    existentes = {
        (linha[0], linha[1])
        for linha in aba_cursos.get("A2:B")
        if len(linha) >= 2
    }
    faltantes = []
    for posicao, curso in enumerate(cursos, start=1):
        if (identificador, str(posicao)) not in existentes:
            faltantes.append([
                identificador,
                posicao,
                str(curso["id_curso_canonico"]),
                curso["nome_curso"],
                curso["link_do_curso"],
            ])
    if faltantes:
        aba_cursos.append_rows(
            faltantes,
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
        )


def registrar_avaliacao(identificador, respostas):
    """Salva avaliação geral opcional sem duplicar o mesmo ID."""
    planilha = _abrir_planilha()
    aba = _aba(planilha, "Avaliacoes")
    if identificador not in aba.col_values(1)[1:]:
        aba.append_row(
            [
                identificador,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                respostas.get("p07", ""),
                respostas.get("p08", ""),
                respostas.get("p09", ""),
            ],
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
        )
