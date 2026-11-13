"""Interface de entrega do recomendador de cursos da EV.G.

Execute na raiz do projeto:
    python -m streamlit run codigo/streamlit_app.py

O aplicativo usa o motor híbrido já validado e não altera suas matrizes.
"""
from pathlib import Path
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd
import streamlit as st

from registro_sheets import registrar_participacao, registrar_avaliacao, registrar_interesse

from motor_recomendador import (
    carregar_opcoes,
    corrigir_opcoes_p01,
    montar_perfil,
    recomendar_experimental,
    validar_perfil,
    separar_lista,
)


RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "arquivos_do_modelo"

st.set_page_config(
    page_title="Encontre cursos na EV.G",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

    /* Tipografia geral: mesma família em textos e widgets do Streamlit,
       sem substituir a fonte usada por ícones e componentes internos. */
    body, .stApp,
    .stApp button, .stApp input, .stApp textarea,
    .stApp select, .stApp label,
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stRadio"] {
        font-family: 'Manrope', 'Segoe UI', sans-serif !important;
    }
    .stApp {font-weight: 400; line-height: 1.55;}
    .stApp h1, .stApp h2, .stApp h3,
    .stApp [data-testid="stMarkdownContainer"] h1,
    .stApp [data-testid="stMarkdownContainer"] h2,
    .stApp [data-testid="stMarkdownContainer"] h3 {
        font-family: 'Manrope', 'Segoe UI', sans-serif !important;
        font-weight: 700;
        letter-spacing: -0.025em;
        line-height: 1.25;
    }
    .stApp button, .stApp .stLinkButton > a {
        font-family: 'Manrope', 'Segoe UI', sans-serif !important;
        font-weight: 600;
    }
    .stApp [data-testid="stWidgetLabel"] label,
    .stApp [data-testid="stRadio"] label {
        font-weight: 500;
    }
    .stApp [data-testid="stMarkdownContainer"] strong {
        font-weight: 700;
    }

    /* Titulos da pagina: cor roxa no claro, lilas no escuro. */
    .stApp h1, .stApp h2,
    .stApp [data-testid="stMarkdownContainer"] h1,
    .stApp [data-testid="stMarkdownContainer"] h2 {
        color: #74258F;
    }
    html.evg-tema-escuro .stApp h1,
    html.evg-tema-escuro .stApp h2,
    html.evg-tema-escuro .stApp [data-testid="stMarkdownContainer"] h1,
    html.evg-tema-escuro .stApp [data-testid="stMarkdownContainer"] h2 {
        color: #DDB5EE;
    }
    /* Aparência padrão dos links da aplicação. */
    .stApp .stLinkButton > a {
        color: var(--st-link-color, var(--link-color, #74258F));
        border-color: var(--st-border-color,
            var(--border-color, #E7D8EF));
        background: var(--st-secondary-background-color,
            var(--secondary-background-color, transparent));
    }
    .stApp .stLinkButton > a:hover {
        border-color: var(--st-primary-color, var(--primary-color, #74258F));
        background: color-mix(in srgb,
            var(--st-primary-color, var(--primary-color, #74258F)) 7%,
            var(--st-secondary-background-color,
                var(--secondary-background-color, transparent)));
    }
    /* Links dos cinco cursos no tema claro: contorno e fundo suave em
       repouso; roxo intenso ao passar o mouse ou usar o teclado. */
    html:not(.evg-tema-escuro) .stApp
    :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
        .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
        .st-key-evg_curso_card_5) .stLinkButton > a {
        color: #74258F;
        border-color: #74258F;
        background: color-mix(in srgb, #74258F 7%, #FFFFFF);
        transition: background-color 160ms ease, color 160ms ease;
    }
    html:not(.evg-tema-escuro) .stApp
    :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
        .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
        .st-key-evg_curso_card_5) .stLinkButton > a:is(:hover, :focus-visible) {
        color: #FFFFFF;
        border-color: #74258F;
        background: #74258F;
    }
    @media (prefers-reduced-motion: reduce) {
        html:not(.evg-tema-escuro) .stApp
        :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
            .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
            .st-key-evg_curso_card_5) .stLinkButton > a {
            transition: none;
        }
    }

    /* Largura da página: uma coluna centralizada, confortável de ler */
    /* O espaço no topo (5rem) evita que a primeira linha fique escondida
       atrás da barra fixa do Streamlit, onde aparece o botão Deploy */
    .block-container {max-width: 760px; padding-top: 5rem; padding-bottom: 4rem;}

    /* Cabecalhos do questionario e dos resultados. */
    .evg-titulo {
        color: #74258F;
        font-size: clamp(1.6rem, 4vw, 2.1rem);
        font-weight: 700; letter-spacing: -.025em;
        line-height: 1.25; margin: .4rem 0 1rem 0;
    }
    .evg-subtitulo {
        color: #74258F;
        font-size: 1.25rem; font-weight: 700;
        letter-spacing: -.015em; margin: 1.2rem 0 .6rem 0;
    }
    html.evg-tema-escuro .stApp .evg-titulo,
    html.evg-tema-escuro .stApp .evg-subtitulo {
        color: #DDB5EE;
    }

    /* Etapa 1: atalho visível para a avaliação, sem modificar os cursos. */
    .evg-cabecalho-resultado {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1rem;
        margin: .4rem 0 1rem;
    }
    .evg-cabecalho-resultado .evg-titulo {margin: 0;}
    .evg-atalho-avaliacao {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: .55rem;
        min-height: 2.75rem;
        padding: .65rem 1rem;
        background: #74258F;
        border: 1px solid #74258F;
        border-radius: 10px;
        color: #FFFFFF !important;
        font-family: 'Manrope', 'Segoe UI', sans-serif;
        font-size: .9rem;
        font-weight: 700;
        line-height: 1.3;
        text-decoration: none !important;
        white-space: nowrap;
        transition: background 160ms ease, border-color 160ms ease;
    }
    .evg-atalho-avaliacao:hover,
    .evg-atalho-avaliacao:focus-visible {
        background: var(--evg-hover, #5F1E74);
        border-color: var(--evg-hover, #5F1E74);
        color: #FFFFFF !important;
        text-decoration: none !important;
    }
    .evg-atalho-avaliacao:focus-visible {
        outline: 3px solid #C7A6D8;
        outline-offset: 3px;
    }
    #evg-avaliacao-geral {scroll-margin-top: 5rem;}
    @media (max-width: 640px) {
        .evg-cabecalho-resultado {align-items: stretch;}
        .evg-atalho-avaliacao {width: 100%;}
    }
    @media (prefers-reduced-motion: reduce) {
        .evg-atalho-avaliacao {transition: none;}
    }

    /* Orientação: lilás translúcido sobre o fundo REAL da tela. Não misturar
       com variáveis de tema que podem permanecer no modo claro após a troca
       para escuro pelo menu do Streamlit. A letra acompanha a cor corrente. */
    .evg-orientacao {
        background: rgba(116, 37, 143, 0.11);
        color: inherit;
        border: 1px solid rgba(116, 37, 143, 0.30);
        border-radius: 10px;
        padding: .85rem 1.1rem; margin-bottom: 1.2rem; line-height: 1.55;
    }
    .evg-orientacao strong {color: inherit; font-weight: 700;}

    /* Os elementos nativos usam primaryColor do tema; mantemos hover definido. */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    .stDownloadButton > button[kind="primary"],
    .stDownloadButton > button[data-testid="stBaseButton-primary"] {
        background: var(--st-primary-color, var(--primary-color, #74258F));
        border-color: var(--st-primary-color, var(--primary-color, #74258F));
        color: #FFFFFF;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    .stDownloadButton > button[kind="primary"]:hover,
    .stDownloadButton > button[data-testid="stBaseButton-primary"]:hover {
        background: var(--evg-hover, #5F1E74);
        border-color: var(--evg-hover, #5F1E74);
        color: #FFFFFF;
    }
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 10px; min-height: 2.75rem;
    }

    /* Bordas e superfícies acompanhando o tema ativo. */
    [data-testid="stExpander"] {
        background: var(--st-secondary-background-color,
            var(--secondary-background-color, transparent));
        border: 1px solid var(--st-border-color,
            var(--border-color, color-mix(in srgb, currentColor 20%, transparent)));
        border-radius: 10px;
    }
    [data-testid="stAlert"] {border-radius: 10px;}

    /* Avisos informativos independentes do st.info: este componente nativo
       impõe sua paleta azul mesmo com as cores roxas do tema. */
    .evg-aviso-academico, .evg-aviso-secundario {
        display: flex;
        align-items: flex-start;
        gap: 0.85rem;
        padding: 1rem 1.15rem;
        border: 1px solid var(--st-border-color,
            var(--border-color, #E7D8EF));
        border-radius: 12px;
        background: var(--st-secondary-background-color,
            var(--secondary-background-color, #FFFFFF));
        color: var(--st-text-color, var(--text-color, #2F2336));
        line-height: 1.6;
    }
    /* Fundo exclusivo do aviso academico. A sincronizacao com o tema ativo
       do Streamlit e feita pelo script do proprio aviso, nao pelo tema do SO. */
    .evg-aviso-academico {
        background: #EEE2F2;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.10),
                    0 1px 4px rgba(0, 0, 0, 0.05);
    }
    .evg-aviso-academico .evg-aviso-icone {
        color: var(--evg-aviso-icon, #74258F);
        border-color: var(--evg-aviso-icon, #74258F);
    }
    .evg-aviso-secundario {
        margin-top: 0.6rem;
        background: color-mix(in srgb,
            var(--st-primary-color, var(--primary-color, #74258F)) 8%,
            var(--st-secondary-background-color,
                var(--secondary-background-color, #FFFFFF)));
    }
    .evg-aviso-icone {
        flex: 0 0 23px;
        width: 23px;
        height: 23px;
        display: inline-flex;
        justify-content: center;
        align-items: center;
        margin-top: 0.1rem;
        border: 1.7px solid var(--st-link-color,
            var(--link-color, #74258F));
        border-radius: 50%;
        color: var(--st-link-color, var(--link-color, #74258F));
        background: color-mix(in srgb,
            var(--st-primary-color, var(--primary-color, #74258F)) 9%, transparent);
        font-family: 'Manrope', 'Segoe UI', sans-serif;
        font-size: 0.85rem;
        font-weight: 800;
        font-style: normal;
        line-height: 1;
    }
    .evg-aviso-conteudo {flex: 1; min-width: 0; font-size: 0.96rem;}
    .evg-aviso-conteudo p {margin: 0;}
    .evg-aviso-conteudo strong {font-weight: 700;}
    @media (max-width: 400px) {
        .evg-aviso-academico, .evg-aviso-secundario {padding: 0.8rem; gap: 0.65rem;}
        .evg-aviso-conteudo {font-size: 0.9rem;}
    }
    div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label {
        line-height: 1.5;
    }
    /* P01/P06: o botão é um bloco, não grid nem flex. O texto nativo
       ocupa toda a largura disponível e o ícone fica posicionado à esquerda.
       Isso evita colunas implícitas do Streamlit que espremem o título. */
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button {
        display: block !important;
        position: relative;
        width: 100%;
        min-height: 100px;
        height: auto;
        padding: 1rem 1.1rem 1rem 4.9rem !important;
        box-sizing: border-box;
        border: 1.5px solid #E7D8EF;
        border-radius: 16px;
        background: #FFFFFF;
        color: #2F2336;
        text-align: left !important;
        white-space: normal;
        box-shadow: 0 2px 9px rgba(48, 34, 53, 0.06);
        transition: transform 150ms ease, border-color 150ms ease,
                    box-shadow 150ms ease, background-color 150ms ease;
    }
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button > :not([data-testid="stIconMaterial"]) {
        display: block;
        width: 100%;
        max-width: 100%;
        text-align: left !important;
        margin: 0;
    }
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stMarkdownContainer"] {
        display: block;
        width: 100%;
        min-width: 0;
        text-align: left !important;
        margin: 0;
    }
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stMarkdownContainer"] p {
        font-size: 1.02rem;
        font-weight: 700;
        line-height: 1.4;
        color: #2F2336;
        text-align: left !important;
        white-space: normal;
        margin: 0;
    }
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stIconMaterial"] {
        position: absolute;
        left: 1.1rem;
        top: 50%;
        transform: translateY(-50%);
        width: 2.8rem;
        height: 2.8rem;
        background: #F1E8F6;
        color: #74258F;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.45rem;
        flex-shrink: 0;
    }
    /* Descrição no mesmo parágrafo do título: início horizontal idêntico. */
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stMarkdownContainer"] p::after {
        content: var(--evg-card-descricao, "");
        display: block;
        margin-top: 0.25rem;
        text-align: left;
        color: #5E4C68;
        font-family: 'Manrope', 'Segoe UI', sans-serif;
        font-size: 0.9rem;
        font-weight: 400;
        line-height: 1.5;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button:focus-visible {
        outline: 3px solid #C7A6D8;
        outline-offset: 2px;
    }
    @media (hover: hover) and (pointer: fine) {
        :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
        button:hover {
            transform: translateY(-2px);
            border-color: #C7A6D8;
            box-shadow: 0 8px 18px rgba(48, 34, 53, 0.10);
        }
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button {
        background: #2B2233;
        border-color: #584365;
        color: #F4ECF7;
        box-shadow: 0 2px 9px rgba(0, 0, 0, 0.16);
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stMarkdownContainer"] p {
        color: #F4ECF7;
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stIconMaterial"] {
        background: #3A2944;
        color: #DDB5EE;
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
    button [data-testid="stMarkdownContainer"] p::after {
        color: #D7C6DE;
    }
    @media (hover: hover) and (pointer: fine) {
        html.evg-tema-escuro .stApp
        :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
        button:hover {
            border-color: #DDB5EE;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.28);
        }
    }
    @media (max-width: 560px) {
        :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
        button {
            min-height: 94px;
            padding: 0.9rem 0.9rem 0.9rem 4.25rem !important;
        }
        :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
        button [data-testid="stIconMaterial"] {
            left: 0.9rem;
            width: 2.5rem;
            height: 2.5rem;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        :is([class*="st-key-evg_card_p01_"], [class*="st-key-evg_card_p06_"])
        button {transition: none; transform: none !important;}
    }
    /* Hover usa a variante mais profunda; o tema escuro ajusta o tom. */
    :root {--evg-hover: #5F1E74;}
    @media (prefers-color-scheme: dark) {
        :root {--evg-hover: #6D2584;}
    }
    .evg-lead {opacity: .9; font-size: 1.08rem; font-weight: 500; line-height: 1.65;}

    /* Cards de apresentação: ilustrações em ameixa/lilás (SVG como CSS)
       para evitar o filtro de SVG inline do Streamlit. */
    .evg-como-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        align-items: stretch;
        gap: 1rem;
        margin: 0.75rem 0 1.45rem;
    }
    .evg-como-card {
        min-width: 0;
        min-height: 205px;
        border: 1px solid var(--st-border-color,
            var(--border-color, color-mix(in srgb, currentColor 15%, transparent)));
        border-radius: 14px;
        background: var(--st-secondary-background-color,
            var(--secondary-background-color, color-mix(in srgb, currentColor 2%, transparent)));
        padding: 1.1rem;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.11);
        transition: transform 180ms ease, box-shadow 180ms ease;
    }
    .evg-como-topo {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        min-height: 60px;
        margin-bottom: 0.6rem;
    }
    .evg-como-icone {
        flex: 0 0 56px;
        width: 56px;
        height: 56px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 11px;
        background: linear-gradient(140deg, #E9D8F0, #F1E8F6);
    }
    .evg-como-icone::before {
        content: "";
        display: block;
        width: 47px;
        height: 47px;
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }
    .evg-icone-responde::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%20fill%3D%22none%22%20stroke%3D%22%2374258F%22%20stroke-width%3D%222.8%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%2211%22%20y%3D%227%22%20width%3D%2239%22%20height%3D%2249%22%20rx%3D%225%22%20fill%3D%22%23F1E8F6%22%2F%3E%3Cpath%20d%3D%22M20%2019h21M20%2026h18M20%2033h11M20%2041h12%22%2F%3E%3Cpath%20d%3D%22m36%2044%2016-17a4%204%200%200%201%205%205L41%2049l-9%203%204-8Z%22%20fill%3D%22%23C7A6D8%22%20stroke%3D%22%235F1E74%22%2F%3E%3Cpath%20d%3D%22m49%2030%205%205%22%2F%3E%3C%2Fsvg%3E");
    }
    .evg-icone-compara::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%20fill%3D%22none%22%20stroke%3D%22%2374258F%22%20stroke-width%3D%222.6%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%2218%22%20y%3D%2217%22%20width%3D%2228%22%20height%3D%2230%22%20rx%3D%225%22%20fill%3D%22%23F1E8F6%22%2F%3E%3Cpath%20d%3D%22M11%2010l8%208M52%2010l-7%208M10%2054l9-9M53%2054l-8-9M32%208v9M32%2047v9M8%2032h10M46%2032h10%22%2F%3E%3Ccircle%20cx%3D%229%22%20cy%3D%229%22%20r%3D%224%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%2255%22%20cy%3D%229%22%20r%3D%224%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%229%22%20cy%3D%2255%22%20r%3D%224%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%2255%22%20cy%3D%2255%22%20r%3D%224%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%226%22%20r%3D%223%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2258%22%20r%3D%223%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%226%22%20cy%3D%2232%22%20r%3D%223%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Ccircle%20cx%3D%2258%22%20cy%3D%2232%22%20r%3D%223%22%20fill%3D%22%23C7A6D8%22%2F%3E%3Cpath%20d%3D%22M25%2025h14M25%2031h14M25%2037h14%22%20stroke%3D%22%23A76ABF%22%2F%3E%3C%2Fsvg%3E");
    }
    .evg-icone-lista::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%20fill%3D%22none%22%20stroke%3D%22%2374258F%22%20stroke-width%3D%222.8%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%229%22%20y%3D%226%22%20width%3D%2246%22%20height%3D%2252%22%20rx%3D%225%22%20fill%3D%22%23F1E8F6%22%2F%3E%3Cpath%20d%3D%22m17%2019%204%204%207-8M33%2020h14M17%2034l4%204%207-8M33%2035h14M17%2049l4%204%207-8M33%2050h14%22%20stroke%3D%22%2374258F%22%2F%3E%3C%2Fsvg%3E");
    }
    .evg-como-card h3 {
        font-family: 'Manrope', 'Segoe UI', sans-serif !important;
        font-size: 1.04rem;
        font-weight: 700;
        line-height: 1.35;
        letter-spacing: -.02em;
        margin: 0;
        color: inherit;
    }
    .evg-como-card p {
        font-family: 'Manrope', 'Segoe UI', sans-serif;
        font-size: 0.93rem;
        line-height: 1.6;
        opacity: 0.94;
        margin: 0;
    }
    @media (hover: hover) and (pointer: fine) {
        .evg-como-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 9px 22px rgba(0, 0, 0, 0.16),
                0 0 0 1px color-mix(in srgb, currentColor 10%, transparent);
        }
    }
    @media (max-width: 720px) {
        .evg-como-grid {grid-template-columns: 1fr;}
        .evg-como-card {min-height: 0;}
    }
    @media (prefers-reduced-motion: reduce) {
        .evg-como-card {transition: none; transform: none !important;}
    }

    /* Legibilidade das legendas em todo o aplicativo: no tema claro e
       no escuro, partem da cor do texto corrente em vez do cinza claro
       usado por padrao no st.caption. Mantem hierarquia com leve opacidade. */
    .stApp [data-testid="stCaptionContainer"] {
        color: var(--st-text-color, var(--text-color, inherit)) !important;
        opacity: 0.9;
        font-size: 0.9rem !important;
        font-weight: 400;
        line-height: 1.55;
    }
    .stApp [data-testid="stCaptionContainer"] * {
        color: inherit !important;
    }

    /* A nota antes da avaliacao precisa ser secundaria, mas nao desbotada. */
    .evg-nota-avaliacao {
        color: inherit;
        opacity: 0.9;
        font-size: 0.93rem;
        font-weight: 500;
        line-height: 1.6;
        margin: 0.25rem 0 1.05rem;
    }

    /* Etapa 3: convite de avaliação no sexto espaço da grade.
       Visual diferente dos cursos e legível nos temas claro e escuro. */
    .evg-convite-avaliacao {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        gap: 0.85rem;
        box-sizing: border-box;
        width: 100%;
        padding: 1.5rem;
        border: 1px solid rgba(116, 37, 143, 0.42);
        border-radius: 12px;
        background: rgba(116, 37, 143, 0.09);
        color: inherit;
    }
    .evg-convite-icone {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 3.3rem;
        height: 3.3rem;
        border-radius: 12px;
        background: rgba(116, 37, 143, 0.15);
        color: #74258F;
    }
    /* O Streamlit pode filtrar SVG inline em st.html: usamos imagens SVG
       como fundos CSS, padrão já aplicado aos ícones da página inicial. */
    .evg-convite-icone::before {
        content: "";
        display: block;
        width: 2rem;
        height: 2rem;
        background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2374258F%22%20stroke-width%3D%221.8%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%225%22%20y%3D%224%22%20width%3D%2214%22%20height%3D%2217%22%20rx%3D%222%22%2F%3E%3Crect%20x%3D%229%22%20y%3D%222%22%20width%3D%226%22%20height%3D%224%22%20rx%3D%221%22%2F%3E%3Cpath%20d%3D%22m8%2012%202%202%204-4M8%2018h8%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
    }
    html.evg-tema-escuro .evg-convite-icone::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23DDB5EE%22%20stroke-width%3D%221.8%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%225%22%20y%3D%224%22%20width%3D%2214%22%20height%3D%2217%22%20rx%3D%222%22%2F%3E%3Crect%20x%3D%229%22%20y%3D%222%22%20width%3D%226%22%20height%3D%224%22%20rx%3D%221%22%2F%3E%3Cpath%20d%3D%22m8%2012%202%202%204-4M8%2018h8%22%2F%3E%3C%2Fsvg%3E");
    }
    .evg-convite-avaliacao h3 {
        margin: 0;
        font-size: 1.22rem;
        font-weight: 800;
        line-height: 1.3;
        color: #74258F;
    }
    html.evg-tema-escuro .evg-convite-avaliacao h3 {color: #DDB5EE;}
    .evg-convite-avaliacao p {
        margin: 0;
        font-size: 0.97rem;
        line-height: 1.6;
        color: inherit;
    }
    .evg-convite-botao {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: .45rem;
        width: 100%;
        min-height: 2.8rem;
        margin-top: .45rem;
        padding: .65rem .75rem;
        box-sizing: border-box;
        border: 1px solid #74258F;
        border-radius: 10px;
        background: #74258F;
        color: #FFFFFF !important;
        text-align: center;
        text-decoration: none !important;
        font-weight: 700;
        font-size: 0.9rem;
        line-height: 1.35;
        transition: background 160ms ease, border-color 160ms ease;
    }
    .evg-convite-botao::before,
    .evg-convite-botao::after {
        content: "";
        display: block;
        flex: 0 0 1.05rem;
        width: 1.05rem;
        height: 1.05rem;
        background-position: center;
        background-repeat: no-repeat;
        background-size: contain;
    }
    .evg-convite-botao::before {background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23FFFFFF%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m12%2019%207-7%203%203-7%207-4%201%201-4Z%22%2F%3E%3Cpath%20d%3D%22m17%2014%203%203%22%2F%3E%3C%2Fsvg%3E");}
    .evg-convite-botao::after {background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23FFFFFF%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M5%2012h14m-6-6%206%206-6%206%22%2F%3E%3C%2Fsvg%3E");}
    .evg-convite-botao:hover, .evg-convite-botao:focus-visible {
        background: var(--evg-hover, #5F1E74);
        border-color: var(--evg-hover, #5F1E74);
        color: #FFFFFF !important;
    }
    .evg-convite-botao:focus-visible {
        outline: 3px solid #C7A6D8;
        outline-offset: 3px;
    }
    @media (prefers-reduced-motion: reduce) {
        .evg-convite-botao {transition: none;}
    }

    /* Avaliação geral: caixa branca somente no tema claro, para contrastar
       com o novo fundo lavanda. No tema escuro, preservar o estilo original. */
    html:not(.evg-tema-escuro) .stApp .st-key-evg_avaliacao_card {
        background-color: #FFFFFF;
        border-color: #D8B9E3;
    }

    /* Avaliação individual: botões de interesse destacados nos cinco cursos.
       A chave do botão indica apenas a apresentação (ativo ou neutro);
       a resposta registrada permanece controlada pelo estado da sessão. */
    .stApp :is([class*="st-key-evg_interesse_sim_"],
               [class*="st-key-evg_interesse_nao_"]) button {
        width: 100%;
        min-height: 3rem;
        padding: .55rem .5rem;
        border: 1px solid #D8B9E3;
        border-radius: 10px;
        background: #FFF9FC;
        color: #74258F;
        white-space: normal;
        font-size: .86rem;
        font-weight: 700;
        line-height: 1.3;
    }
    .stApp :is([class*="st-key-evg_interesse_sim_"],
               [class*="st-key-evg_interesse_nao_"]) button:hover {
        border-color: #74258F;
        background: #F1E8F6;
        color: #74258F;
    }
    .stApp :is([class*="st-key-evg_interesse_sim_"][class*="_ativo"],
               [class*="st-key-evg_interesse_nao_"][class*="_ativo"]) button,
    .stApp :is([class*="st-key-evg_interesse_sim_"][class*="_ativo"],
               [class*="st-key-evg_interesse_nao_"][class*="_ativo"]) button:hover {
        background: #74258F;
        border-color: #74258F;
        color: #FFFFFF;
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_interesse_sim_"],
        [class*="st-key-evg_interesse_nao_"]) button {
        background: #2B2233;
        border-color: #584365;
        color: #DDB5EE;
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_interesse_sim_"],
        [class*="st-key-evg_interesse_nao_"]) button:hover {
        background: #3A2944;
        border-color: #DDB5EE;
        color: #F4ECF7;
    }
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_interesse_sim_"][class*="_ativo"],
        [class*="st-key-evg_interesse_nao_"][class*="_ativo"]) button,
    html.evg-tema-escuro .stApp
    :is([class*="st-key-evg_interesse_sim_"][class*="_ativo"],
        [class*="st-key-evg_interesse_nao_"][class*="_ativo"]) button:hover {
        background: #803199;
        border-color: #DDB5EE;
        color: #FFFFFF;
    }

    /* Cinco cards dos cursos: no tema claro, o mesmo fundo lavanda do
       convite "Antes de finalizar". Manter o tom anterior no tema escuro. */
    :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
        .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
        .st-key-evg_curso_card_5) {
        background: rgba(116, 37, 143, 0.09);
        border-radius: 12px;
        /* Altura sincronizada com o maior dos cinco cards pelo script abaixo.
           min-height permite crescimento sem cortar conteúdo. */
        box-sizing: border-box;
    }
    html.evg-tema-escuro .stApp
    :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
        .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
        .st-key-evg_curso_card_5) {
        background: var(--st-secondary-background-color,
            var(--secondary-background-color, color-mix(in srgb, currentColor 2%, transparent)));
    }

    /* Elevação discreta somente nos cinco cards dos cursos.
       Os seletores st-key são gerados pelo key= do st.container. */
    @media (hover: hover) and (pointer: fine) {
        :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
            .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
            .st-key-evg_curso_card_5) {
            transition: transform 180ms ease, box-shadow 180ms ease;
        }
        :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
            .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
            .st-key-evg_curso_card_5):hover {
            transform: translateY(-5px);
            /* A sombra escura dá profundidade; o contorno e brilho usam
               a cor do texto do tema atual, ficando visíveis também no escuro. */
            box-shadow:
                0 10px 24px rgba(0, 0, 0, 0.22),
                0 0 0 1px color-mix(in srgb, currentColor 24%, transparent),
                0 0 18px color-mix(in srgb, currentColor 12%, transparent);
        }
    }
    @media (prefers-reduced-motion: reduce) {
        :is(.st-key-evg_curso_card_1, .st-key-evg_curso_card_2,
            .st-key-evg_curso_card_3, .st-key-evg_curso_card_4,
            .st-key-evg_curso_card_5) {
            transition: none !important;
            transform: none !important;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)

# Sincroniza a cor dos titulos com o tema realmente exibido pelo Streamlit.
# Isso inclui trocas de tema pelo menu, sem recarregar a pagina.
st.html(
    """
    <script>
    (() => {
        if (window.__evgTemaCabecalhosTimer) {
            clearInterval(window.__evgTemaCabecalhosTimer);
        }
        const brilho = (cor) => {
            const rgb = String(cor).match(/rgba?\\(([^)]+)\\)/i);
            if (!rgb) return null;
            const valores = rgb[1].split(',').map(v => Number.parseFloat(v));
            if (valores.length < 3 || valores.slice(0, 3).some(v => !Number.isFinite(v))) {
                return null;
            }
            if (valores.length > 3 && valores[3] === 0) return null;
            return .2126 * valores[0] + .7152 * valores[1] + .0722 * valores[2];
        };
        const sincronizar = () => {
            const app = document.querySelector('[data-testid="stAppViewContainer"]')
                || document.querySelector('.stApp') || document.body;
            const estilo = getComputedStyle(app);
            const fundo = brilho(estilo.backgroundColor);
            const texto = brilho(estilo.color);
            const escuro = fundo !== null ? fundo < 125 : texto !== null && texto > 150;
            document.documentElement.classList.toggle('evg-tema-escuro', escuro);
        };
        sincronizar();
        window.__evgTemaCabecalhosTimer = setInterval(sincronizar, 350);
    })();
    </script>
    """,
    unsafe_allow_javascript=True,
)


@st.cache_resource(show_spinner="Carregando os cursos da EV.G...")
def carregar_modelo():
    nomes = [
        "matriz_cursos_resumida.csv",
        "ids_dos_cursos.npy",
        "semelhanca_por_conteudo.npy",
        "semelhanca_por_matriculas.npy",
        "popularidade_dos_cursos.npy",
    ]
    faltam = [nome for nome in nomes if not (MODELO / nome).is_file()]
    if faltam:
        raise FileNotFoundError("Arquivos do modelo ausentes: " + ", ".join(faltam))
    matriz = pd.read_csv(MODELO / nomes[0]).fillna("")
    arrays = [np.load(MODELO / nome, allow_pickle=False) for nome in nomes[1:]]
    ids, conteudo, matriculas, popularidade = arrays
    n = len(ids)
    if (
        n != len(matriz)
        or not np.array_equal(matriz["id_curso_canonico"].to_numpy(), ids)
        or conteudo.shape != (n, n)
        or matriculas.shape != (n, n)
        or popularidade.shape != (n,)
    ):
        raise ValueError("Os arquivos do modelo não estão alinhados. Confira a pasta arquivos_do_modelo.")
    return matriz, ids, conteudo, matriculas, popularidade


OPCOES = corrigir_opcoes_p01(carregar_opcoes(MODELO / "opcoes_questionario.json"))
GRUPOS = OPCOES["grupos"]
OBJETIVOS = {item["codigo"]: item["texto"] for item in OPCOES["objetivos_p06"]}

# Textos exibidos diretamente pela interface. Os códigos continuam iguais aos
# exigidos pelo motor, mas as frases não dependem de versões antigas dele.
ROTULOS_P01 = {
    "trabalho": "Estou trabalhando",
    "trabalho_estudo": "Trabalho e estudo",
    "estudo": "Estou estudando",
    "primeiro": "Estou procurando meu primeiro emprego",
    "oportunidade": "Estou procurando uma nova oportunidade",
    "transicao": "Quero mudar de área profissional",
    "outra": "Outra situação / Prefiro não informar",
}

# P01 e P06 permanecem perguntas de escolha unica. Os códigos, títulos e
# pesos do modelo continuam inalterados; apenas a interface usa st.button.
# Cada metadado contém o nome de um ícone Material e uma descrição curta.
CARDS_P01 = {
    "trabalho": ("work", "Atualmente exerço uma atividade profissional."),
    "trabalho_estudo": ("menu_book", "Divido meu tempo entre trabalho e estudos."),
    "estudo": ("school", "Atualmente me dedico aos estudos."),
    "primeiro": ("search", "Estou buscando minha primeira oportunidade profissional."),
    "oportunidade": ("trending_up", "Busco novas oportunidades de trabalho."),
    "transicao": ("sync_alt", "Quero começar uma trajetória em outra área."),
    "outra": ("help_outline", "Minha situação não está listada ou prefiro não responder."),
}
CARDS_P06 = {
    "melhorar": ("track_changes", "Aprimorar conhecimentos que já utilizo no trabalho."),
    "crescer": ("trending_up", "Desenvolver competências para avançar na carreira."),
    "emprego": ("work", "Preparar-me para conquistar uma oportunidade."),
    "mudar": ("sync_alt", "Adquirir conhecimentos para atuar em outra área."),
    "novo": ("explore", "Conhecer temas e possibilidades que ainda não explorei."),
    "pessoal": ("favorite_border", "Estudar por curiosidade e desenvolvimento pessoal."),
    "indefinido": ("help_outline", "Explorar possibilidades antes de decidir."),
    "privacidade": ("shield", "Continuar sem informar um objetivo específico."),
}


def selecionar_card(etapa, resposta):
    """Guarda a mesma resposta que o radio anterior, sem criar um widget radio."""
    chave = f"evg_{etapa}"
    st.session_state[chave] = resposta
    st.session_state.setdefault("evg_valores", {})[chave] = resposta


def mostrar_cards_escolha_unica(etapa):
    """Cards inteiros clicáveis; mantêm o valor original de P01 e P06."""
    if etapa == "p01":
        opcoes = ROTULOS_P01
        metadados = CARDS_P01
        selecionado = situacao_atual()
    else:
        opcoes = OBJETIVOS
        metadados = CARDS_P06
        selecionado = valor("evg_p06")

    estilos = []
    for codigo, (icone, descricao) in metadados.items():
        seletor = f".st-key-evg_card_{etapa}_{codigo} button"
        # Uma string CSS, não HTML: cada descrição aparece dentro do botão.
        texto_css = descricao.replace("\\\\", "\\\\\\\\").replace('"', '\\"')
        estilos.append(f'{seletor}{{--evg-card-descricao:"{texto_css}";}}')
        if codigo == selecionado:
            estilos.append(
                f'{seletor}{{background:#F1E8F6!important;'
                f'border:2px solid #74258F!important;'
                f'box-shadow:0 5px 15px rgba(116,37,143,.12)!important;}}'
                f'html.evg-tema-escuro {seletor}{{background:#3A2944!important;'
                f'border:2px solid #DDB5EE!important;}}'
            )
    st.markdown("<style>" + "".join(estilos) + "</style>", unsafe_allow_html=True)

    # Duas opções por linha no desktop; no celular o Streamlit
    # empilha as colunas, exibindo um card por linha.
    itens = list(opcoes.items())
    for inicio in range(0, len(itens), 2):
        colunas = st.columns(2, gap="medium")
        for coluna, (codigo, titulo) in zip(colunas, itens[inicio:inicio + 2]):
            icone, _descricao = metadados[codigo]
            # Mantém as mesmas chaves e valores consumidos pelo recomendador.
            with coluna:
                st.button(
                    titulo,
                    key=f"evg_card_{etapa}_{codigo}",
                    icon=f":material/{icone}:",
                    use_container_width=True,
                    on_click=selecionar_card,
                    args=(etapa, titulo if etapa == "p01" else codigo),
                )

    # P01 e P06: igualar a altura de TODOS os cards à maior altura natural
    # da pergunta, inclusive após mudança de seleção ou largura da tela.
    # Usar min-height, sem valores fixos nem cortes em títulos/descrições.
    st.html(
        """
        <script>
        (() => {
            const etapa = "__ETAPA__";
            const quantidade = __TOTAL__;
            const raiz = document.querySelector('.st-key-evg_pergunta_' + etapa);
            if (!raiz) return;

            if (window.__evgCardsEscolhaAltura?.encerrar) {
                window.__evgCardsEscolhaAltura.encerrar();
            }
            const seletor = '[class*="st-key-evg_card_' + etapa + '_"] button';
            let frame = null;
            let botoesAtuais = [];
            let observador = null;

            const encerrar = () => {
                if (observador) observador.disconnect();
                window.removeEventListener('resize', agendar);
                if (frame !== null) cancelAnimationFrame(frame);
                botoesAtuais.forEach(botao => { botao.style.minHeight = ''; });
                if (window.__evgCardsEscolhaAltura?.encerrar === encerrar) {
                    window.__evgCardsEscolhaAltura = null;
                }
            };
            const medir = () => {
                frame = null;
                if (!raiz.isConnected) {
                    encerrar();
                    return;
                }
                const botoes = [...raiz.querySelectorAll(seletor)];
                if (botoes.length !== quantidade) return;

                // Remover alturas aplicadas anteriormente antes de medir.
                botoes.forEach(botao => { botao.style.minHeight = ''; });
                const maior = Math.ceil(Math.max(...botoes.map(
                    botao => botao.getBoundingClientRect().height
                )));
                botoes.forEach(botao => {
                    botao.style.minHeight = maior + 'px';
                });
                botoesAtuais = botoes;
            };
            const agendar = () => {
                if (frame !== null) cancelAnimationFrame(frame);
                frame = requestAnimationFrame(medir);
            };
            observador = new MutationObserver(agendar);
            observador.observe(raiz, {
                subtree: true, childList: true, characterData: true
            });
            window.__evgCardsEscolhaAltura = { encerrar };
            window.addEventListener('resize', agendar, { passive: true });
            agendar();
            if (document.fonts?.ready) document.fonts.ready.then(agendar);
        })();
        </script>
        """.replace("__ETAPA__", etapa).replace("__TOTAL__", str(len(itens))),
        unsafe_allow_javascript=True,
    )


# P02 é pertinente para quem trabalha, trabalhou ou está mudando de carreira.
# Quem está apenas estudando ou procurando o primeiro emprego vai direto à P04.
SITUACOES_COM_P02 = {"trabalho", "trabalho_estudo", "oportunidade", "transicao"}

# Textos de cada etapa: (pergunta exibida, orientação complementar).
# Para mudar qualquer frase da tela, é só editar aqui.
# Centralizar os enunciados evita duplicar a pergunta em cada tela.
PERGUNTAS = {
    "p01": (
        "Qual é sua situação atualmente?",
        "Primeiro, queremos conhecer sua situação atual. Considere o que "
        "melhor representa seu momento neste período.",
    ),
    "p02": (
        "Em quais áreas você trabalha ou já trabalhou?",
        "Escolha até três áreas. Você pode abrir mais de uma categoria.",
    ),
    "p04": (
        "Em quais áreas você já estudou ou possui conhecimentos?",
        "Considere faculdade, cursos, trabalho e estudos por conta própria. "
        "Escolha até três áreas.",
    ),
    "p05": (
        "Quais assuntos você gostaria de aprender?",
        "Escolha até três assuntos, mesmo que não tenham relação com sua "
        "formação.",
    ),
    "p06": (
        "Qual é seu principal objetivo ao fazer um curso?",
        "Por fim, considerando sua vida profissional, seus estudos e seus "
        "interesses, queremos entender o que você busca ao fazer cursos "
        "neste momento.",
    ),
}


# Estes títulos organizam o questionário sem expor os códigos P01/P02/etc.
TITULOS_DAS_ETAPAS = {
    "p01": "Situação Atual",
    "p02": "Experiência Profissional",
    "p04": "Formação e Conhecimentos",
    "p05": "Interesses de Aprendizagem",
    "p06": "Objetivo de Aprendizagem",
}


def cabecalho_da_pergunta(etapa):
    """Mostra a seção, a orientação e o enunciado, sem código de pergunta."""
    pergunta, orientacao = PERGUNTAS[etapa]
    titulo = TITULOS_DAS_ETAPAS[etapa]
    st.markdown(f'<h2 class="evg-titulo">{titulo}</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="evg-orientacao"><strong>Orientação:</strong> {orientacao}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="evg-subtitulo">{pergunta}</div>',
        unsafe_allow_html=True,
    )


# Textos da tela inicial. Para mudar qualquer frase, é só editar aqui.
APRESENTACAO_ABERTURA = (
    "Responda a algumas perguntas e receba cinco sugestões de cursos da "
    "Escola Virtual de Governo (EV.G), a plataforma de cursos online gratuitos "
    "do governo federal."
)
APRESENTACAO_AVISO = (
    "<strong>Este é um trabalho acadêmico.</strong> O recomendador foi desenvolvido por "
    "estudantes do Mackenzie no <strong>Projeto Aplicado III</strong> e está em fase de "
    "testes. Ele <strong>não é um serviço oficial da EV.G</strong>. As sugestões são só um "
    "ponto de partida: para se inscrever em qualquer curso, use o site da EV.G."
)
APRESENTACAO_COMO_FUNCIONA = """
<div class="evg-como-grid">
    <article class="evg-como-card">
        <div class="evg-como-topo">
            <span class="evg-como-icone evg-icone-responde" aria-hidden="true"></span>
            <h3>Você responde</h3>
        </div>
        <p>A algumas perguntas, uma por vez, sobre sua situação, experiências,
        estudos, interesses e objetivo. É só selecionar as opções.</p>
    </article>
    <article class="evg-como-card">
        <div class="evg-como-topo">
            <span class="evg-como-icone evg-icone-compara" aria-hidden="true"></span>
            <h3>O modelo compara</h3>
        </div>
        <p>Seu perfil com os mais de mil cursos do catálogo da EV.G e
        seleciona cinco recomendações.</p>
    </article>
    <article class="evg-como-card">
        <div class="evg-como-topo">
            <span class="evg-como-icone evg-icone-lista" aria-hidden="true"></span>
            <h3>Você recebe a lista</h3>
        </div>
        <p>Com os links dos cinco cursos e pode avaliar se as sugestões
        foram úteis. A avaliação ajuda o nosso trabalho.</p>
    </article>
</div>
"""
APRESENTACAO_MODELO = """
O modelo é **híbrido**: junta duas pistas.

- **O conteúdo dos cursos:** assuntos e áreas de cada curso, comparados com as
  suas respostas.
- **O que costuma andar junto:** associações do passado entre cursos, somadas a
  partir de muitas matrículas na EV.G, sem identificar nenhuma pessoa.

Juntando as duas pistas, ele monta a lista de cinco cursos. O seu objetivo
também ajuda a decidir quanto cada parte do seu perfil (trabalho,
estudos e interesses) pesa na escolha.
"""
APRESENTACAO_DADOS = """
- Não pedimos nome, login, e-mail ou CPF para responder ao questionário.
- O app **não consulta o seu histórico** na EV.G. O seu perfil vem apenas das
  respostas que você dá aqui.
- Suas respostas servem só para montar a sua lista: elas **não alteram o
  modelo**, e cada pessoa começa do zero.
- Ao gerar sua lista, as respostas e os cinco cursos recomendados são
  registrados numa planilha privada do projeto para análise acadêmica.
  As avaliações, quando enviadas, também são registradas.
- Suas respostas não são enviadas à EV.G e não alteram o modelo.
- Alguns cursos têm requisitos de acesso. Quem decide se você pode se matricular
  é a EV.G.
"""

APRESENTACAO_NOSSO_PROJETO = """
**Sobre o projeto**

Somos estudantes do curso de **Banco de Dados – Análise, Mineração e Engenharia
de Dados**, da **Universidade Presbiteriana Mackenzie**, e desenvolvemos este
recomendador na disciplina **Projeto Aplicado III**, em 2026.

Nosso objetivo é facilitar a descoberta de oportunidades gratuitas de
capacitação profissional. Para isso, combinamos informações sobre os cursos da
**Escola Virtual de Governo (EV.G)** com técnicas de recomendação baseadas em
conteúdo e em padrões de matrículas, apresentando cinco sugestões de acordo
com as respostas de cada participante.

**Nossa equipe**

- Allana Rayssa Vieira de Oliveira
- Erika Cristina Alves Benesi Gomes
- Nicole Fernandes Moreira
- Tawany Nascimento Santos

O aplicativo é um **protótipo acadêmico independente**, desenvolvido para
fins de pesquisa e aprendizagem. Não é um serviço oficial da EV.G.
"""


def valor(chave, padrao=None):
    """Lê a resposta guardada mesmo após o Streamlit ocultar o widget."""
    return st.session_state.get(
        chave, st.session_state.get("evg_valores", {}).get(chave, padrao)
    )


def guardar_respostas():
    """Os widgets ocultos são limpos pelo Streamlit: guardar cópia separada."""
    guardadas = st.session_state.setdefault("evg_valores", {})
    for chave in list(st.session_state):
        if chave.startswith("evg_p"):
            guardadas[chave] = st.session_state[chave]


def restaurar_etapa(etapa):
    """Preenche os widgets quando a pessoa volta para corrigir uma pergunta."""
    guardadas = st.session_state.get("evg_valores", {})
    for chave, resposta in guardadas.items():
        if chave.startswith("evg_" + etapa) and chave not in st.session_state:
            st.session_state[chave] = resposta


def situacao_atual():
    """Traduz o texto visível da P01 para o código usado pelo modelo."""
    escolha = valor("evg_p01")
    for codigo, rotulo in ROTULOS_P01.items():
        if escolha == rotulo:
            return codigo
    return escolha  # compatibilidade com uma sessão criada antes desta versão


def sequencia():
    etapas = ["p01"]
    if situacao_atual() in SITUACOES_COM_P02:
        etapas.append("p02")
    return etapas + ["p04", "p05", "p06"]


def marcadas(grupo_campo):
    tipo, campo = grupo_campo
    selecionadas = []
    for numero, grupo in enumerate(GRUPOS):
        opcoes_do_grupo = (
            [item["nome"] for item in grupo[campo]]
            if campo == "experiencia" else grupo[campo]
        )
        for indice, item in enumerate(opcoes_do_grupo):
            if valor(f"evg_{tipo}_{numero}_{indice}", False):
                selecionadas.append(item)
    return list(dict.fromkeys(selecionadas))


def ao_alterar_opcao_exclusiva_p04(chave):
    """Torna 'Nenhuma' e 'Prefiro não informar' escolhas exclusivas na P04."""
    marcacao = bool(st.session_state.get(chave, False))
    guardadas = st.session_state.setdefault("evg_valores", {})
    guardadas[chave] = marcacao
    if not marcacao:
        return  # Ao desmarcar, todas as áreas voltam a ficar disponíveis.

    outra = (
        "evg_p04_privacidade" if chave == "evg_p04_nenhuma"
        else "evg_p04_nenhuma"
    )
    st.session_state[outra] = False
    guardadas[outra] = False

    # Limpa tanto os widgets atuais quanto cópias de respostas já guardadas.
    # Os callbacks executam antes da nova renderização do Streamlit.
    chaves = set(st.session_state) | set(guardadas)
    for campo in chaves:
        if campo.startswith("evg_p04_") and campo not in (
            "evg_p04_nenhuma", "evg_p04_privacidade"
        ):
            if campo in st.session_state:
                st.session_state[campo] = False
            guardadas[campo] = False


def menus_de_opcoes(tipo, campo, limite):
    quantidade = len(marcadas((tipo, campo)))
    # Só a P04 tem escolhas exclusivas; P02 e P05 não são alteradas.
    exclusivo_ativo = (
        bool(valor("evg_p04_nenhuma", False))
        or bool(valor("evg_p04_privacidade", False))
    ) if tipo == "p04" else False

    for numero, grupo in enumerate(GRUPOS):
        itens = (
            [item["nome"] for item in grupo[campo]]
            if campo == "experiencia" else grupo[campo]
        )
        with st.expander(grupo["nome"]):
            for indice, item in enumerate(itens):
                chave = f"evg_{tipo}_{numero}_{indice}"
                # Com escolha exclusiva, não se marcam áreas. Ao atingir três
                # áreas, só as desmarcadas ficam temporariamente indisponíveis.
                bloqueada = (
                    exclusivo_ativo
                    or (quantidade >= limite and not bool(valor(chave, False)))
                ) if tipo == "p04" else False
                st.checkbox(item, key=chave, disabled=bloqueada)
    st.caption(f"{quantidade} de até {limite} opções selecionadas.")


def coletar_respostas():
    situacao = situacao_atual()
    formacao_opcao = (
        "privacidade" if valor("evg_p04_privacidade", False)
        else "nenhuma" if valor("evg_p04_nenhuma", False)
        else "areas"
    )
    nao_sei = bool(valor("evg_p05_nao_sei", False))
    experiencia = (
        marcadas(("p02", "experiencia"))
        if situacao in SITUACOES_COM_P02 else []
    )
    if situacao in SITUACOES_COM_P02 and valor("evg_p02_outras", False):
        experiencia.append(OPCOES["opcao_experiencia_outras"])
    return {
        "situacao": situacao,
        "experiencia": experiencia,
        "formacao": (
            marcadas(("p04", "areas_cursos"))
            if formacao_opcao == "areas" else []
        ),
        "formacao_opcao": formacao_opcao,
        "interesses": [] if nao_sei else marcadas(("p05", "assuntos_p05")),
        "nao_sei": nao_sei,
        "objetivo": valor("evg_p06"),
    }


def validar_etapa(etapa):
    if etapa == "p01" and not valor("evg_p01"):
        return "Selecione sua situação atual para continuar."
    if etapa == "p02" and len(coletar_respostas()["experiencia"]) > 3:
        return "Selecione no máximo três áreas profissionais."
    if etapa == "p04":
        quantidade = len(marcadas(("p04", "areas_cursos")))
        nenhuma = valor("evg_p04_nenhuma", False)
        privacidade = valor("evg_p04_privacidade", False)
        if nenhuma and privacidade:
            return "Marque apenas uma: Nenhuma das opções ou Prefiro não informar."
        if (nenhuma or privacidade) and quantidade:
            return "Desmarque as áreas escolhidas para selecionar Nenhuma ou Prefiro não informar."
        if not (quantidade or nenhuma or privacidade):
            return "Selecione uma área ou marque Nenhuma das opções ou Prefiro não informar."
        if quantidade > 3:
            return "Selecione no máximo três áreas de formação."
    if etapa == "p05":
        interesses = marcadas(("p05", "assuntos_p05"))
        nao_sei = valor("evg_p05_nao_sei", False)
        if not nao_sei and not interesses:
            return "Escolha ao menos um assunto ou marque Ainda não sei."
        if not nao_sei and len(interesses) > 3:
            return "Selecione no máximo três assuntos de interesse."
    if etapa == "p06" and not valor("evg_p06"):
        return "Selecione seu principal objetivo."
    return None


def solicitar_rolagem_topo():
    """Marca uma mudança real de etapa, não uma simples interação com widgets."""
    st.session_state["evg_rolagem_pendente"] = True
    st.session_state["evg_rolagem_versao"] = (
        st.session_state.get("evg_rolagem_versao", 0) + 1
    )


def aplicar_rolagem_topo():
    """Volta ao topo após mudança de tela, sem rolar nos reruns dos widgets.

    O script confiável usa as superfícies de rolagem do Streamlit e repete
    o ajuste brevemente para contornar a restauração tardia da posição.
    """
    if not st.session_state.pop("evg_rolagem_pendente", False):
        return
    versao = st.session_state["evg_rolagem_versao"]
    st.html(
        f"""
        <span style="display:none" data-evg-scroll="{versao}"></span>
        <script>
        (() => {{
            const toTop = () => {{
                // O Streamlit pode preservar a rolagem ao trocar as etapas.
                // Rolar também o contêiner correto, não só o window.
                const scrollers = [
                    document.scrollingElement,
                    document.documentElement,
                    document.body,
                    ...document.querySelectorAll(
                        'section[data-testid="stMain"],' +
                        '[data-testid="stAppViewContainer"],' +
                        '[data-testid="stMainBlockContainer"]'
                    ),
                ];
                scrollers.forEach((el) => {{
                    if (el) el.scrollTop = 0;
                }});
                window.scrollTo({{top: 0, left: 0, behavior: 'instant'}});
                const topContent = document.querySelector(
                    'section[data-testid="stMain"] .block-container'
                ) || document.querySelector('.block-container');
                if (topContent) {{
                    topContent.scrollIntoView({{block: 'start', behavior: 'instant'}});
                }}
            }};
            requestAnimationFrame(() => requestAnimationFrame(toTop));
            [80, 220, 500, 850].forEach((ms) => setTimeout(toTop, ms));
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def avancar(etapa):
    guardar_respostas()
    problema = validar_etapa(etapa)
    if problema:
        st.error(problema)
        return
    if etapa == "p06":
        try:
            respostas = coletar_respostas()
            perfil, objetivo, explorar = montar_perfil(respostas, OPCOES)
            validar_perfil(perfil, OPCOES)
            matriz, ids, conteudo, matriculas, popularidade = carregar_modelo()
            with st.spinner("Buscando cinco cursos para você..."):
                resultado = recomendar_experimental(
                    perfil, objetivo, matriz, ids, conteudo, matriculas,
                    popularidade, explorar_novos_temas=explorar,
                )
            if resultado["quantidade"] != 5:
                st.error("Não foi possível encontrar cinco cursos elegíveis para este perfil.")
                return
            st.session_state["evg_resultado"] = resultado
            st.session_state["evg_respostas"] = respostas
            st.session_state["evg_participacao_id"] = str(uuid4())
            st.session_state["evg_participacao_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            st.session_state["evg_registro_status"] = "pendente"
            st.session_state["evg_avaliacao_enviada"] = False
            for chave in list(st.session_state):
                if chave in ("evg_p07", "evg_p08", "evg_p09") or chave.startswith("evg_interesse_curso_"):
                    st.session_state.pop(chave, None)
            st.session_state["evg_interesses_salvos"] = {}
            st.session_state["evg_tela"] = "resultado"
            solicitar_rolagem_topo()
            st.rerun()
        except (ValueError, KeyError, FileNotFoundError) as erro:
            st.error(str(erro))
        return
    etapas = sequencia()
    st.session_state["evg_tela"] = etapas[etapas.index(etapa) + 1]
    solicitar_rolagem_topo()
    st.rerun()


def voltar(etapa):
    guardar_respostas()
    if etapa == "resultado":
        st.session_state["evg_tela"] = "p06"
    else:
        etapas = sequencia()
        posicao = etapas.index(etapa)
        st.session_state["evg_tela"] = etapas[posicao - 1] if posicao else "inicio"
    solicitar_rolagem_topo()
    st.rerun()


def botoes_navegacao(etapa):
    esquerda, direita = st.columns([1, 3], gap="medium")
    with esquerda:
        if st.button("Voltar"):
            voltar(etapa)
    with direita:
        texto = (
            "Gerar Recomendações Personalizadas"
            if etapa == "p06" else "Avançar"
        )
        if st.button(texto, type="primary"):
            avancar(etapa)


def normalizar(texto):
    return " ".join(
        "".join(
            letra for letra in unicodedata.normalize("NFKD", str(texto).casefold())
            if not unicodedata.combining(letra)
        ).split()
    )


# Pares de versões do mesmo curso conferidos no catálogo EV.G.
# Não confiar apenas no nome: títulos traduzidos são diferentes.
# Chaves e valores são os IDs públicos dos cursos na EV.G.
IDIOMAS_EQUIVALENTES = {
    629: [338],                 # Aprendendo com Python
    317: [547, 560],            # Ágil no Contexto do Serviço Público
    416: [1460, 1461],          # Gestão da Inovação no Setor Público
    107: [1408, 1409],          # Planejamento Estratégico para Organizações Públicas
    468: [1182, 1402],          # Gestão do Tempo e Produtividade
    259: [551, 597],            # Administração de Serviços na Nuvem de Governo
    318: [626, 627],            # Inteligência Emocional
    628: [335],                 # Metodologias Ativas
    444: [1380, 1397],          # Estratégias de produtividade
    507: [676, 677],            # Rotulagem Ambiental Tipo I
    773: [1295, 1326],          # E-liderança
    475: [1140, 1187],          # Planejamento e Organização Pessoal
    909: [1462, 1463],          # Valores Culturais da Natureza
    163: [552, 707],            # Gestão Pessoal - Base da Liderança
    175: [277],                 # Gestão por Competências
    415: [1421, 1450],          # Gestão de Projetos Educacionais
}


def idiomas_alternativos(curso, matriz):
    atual = matriz.loc[
        matriz["id_curso_canonico"].eq(curso["id_curso_canonico"])
    ]
    if atual.empty:
        return []
    id_evg = int(atual.iloc[0]["id_curso_evg"])
    ids_idiomas = IDIOMAS_EQUIVALENTES.get(id_evg, [])
    correspondentes = matriz[matriz["id_curso_evg"].isin(ids_idiomas)]
    opcoes = []
    for _, linha in correspondentes.iterrows():
        idioma = str(linha.get("idioma", ""))
        url = str(linha.get("link_do_curso", ""))
        restrito = normalizar(linha.get("acesso_restrito", "")) in ("true", "1", "sim")
        if normalizar(idioma) != "portugues" and url.startswith("https://") and not restrito:
            item = idioma, url
            if item not in opcoes:
                opcoes.append(item)
    return opcoes


def reiniciar():
    for chave in list(st.session_state):
        if chave.startswith("evg_"):
            del st.session_state[chave]
    st.session_state["evg_tela"] = "inicio"
    solicitar_rolagem_topo()
    st.rerun()


def linha_do_curso(curso, matriz):
    """Acha, no catálogo, a linha com os detalhes do curso recomendado."""
    achadas = matriz.loc[matriz["id_curso_canonico"].eq(curso["id_curso_canonico"])]
    return None if achadas.empty else achadas.iloc[0]


def explicar_recomendacao(curso, linha, respostas):
    """Explicação factual, sem transformar a nota interna em porcentagem.

    O motor usa P05 por correspondência em assuntos/termos de busca;
    na ausência de coincidência explícita, não inventamos um vínculo.
    """
    if linha is not None:
        termos = [
            normalizar(item)
            for campo in ("assuntos", "termos_busca")
            for item in separar_lista(linha.get(campo, ""))
        ]
        for interesse in respostas.get("interesses", []):
            if any(normalizar(interesse) in termo for termo in termos):
                return f"Relacionado ao interesse que você marcou: **{interesse}**."

        area = str(linha.get("area_principal", ""))
        if area in respostas.get("formacao", []):
            return "É da mesma área de formação ou conhecimentos que você informou."

    motivos = curso.get("motivos", [])
    if "popularidade histórica da EV.G" in motivos:
        return "Sugestão baseada na popularidade histórica dos cursos no catálogo analisado."
    if "conhecimento e experiência informados" in motivos:
        return "Considera sua experiência e seus conhecimentos, junto das relações entre cursos."
    return "Selecionado a partir dos seus interesses e das relações entre os conteúdos dos cursos."


def selecionar_interesse_curso(posicao, interesse):
    """Registra a opinião do curso em sua linha existente e mantém a escolha visível.

    Repetir a mesma opção não faz nova gravação. Trocar a opção substitui
    a opinião anterior na mesma célula da planilha Recomendacoes.
    """
    salvos = st.session_state.setdefault("evg_interesses_salvos", {})
    erros = st.session_state.setdefault("evg_interesses_erros", {})
    erros.pop(posicao, None)

    if salvos.get(posicao) == interesse:
        return
    if st.session_state.get("evg_registro_status") != "salvo":
        erros[posicao] = (
            "O registro do questionário precisa ser concluído "
            "antes de salvar esta opinião. Tente novamente."
        )
        return
    try:
        registrar_interesse(
            st.session_state["evg_participacao_id"],
            posicao,
            interesse,
        )
    except Exception:
        erros[posicao] = "Não conseguimos salvar sua opinião. Você pode tentar novamente."
    else:
        salvos[posicao] = interesse


def mostrar_curso(posicao, curso, matriz, respostas):
    """Card compacto, com link e avaliação individual em linhas consecutivas."""
    linha = linha_do_curso(curso, matriz)
    with st.container(border=True, key=f"evg_curso_card_{posicao}"):
        st.markdown(f"**{posicao}. {curso['nome_curso']}**")
        area = str(curso.get("area_principal", "")).strip()
        if area:
            st.caption(f"Área: {area}")

        st.markdown("**Por que apareceu para você?**")
        st.caption(explicar_recomendacao(curso, linha, respostas))

        # Mostrar o aviso antes do link: a pessoa deve saber sobre a
        # restrição antes de tentar fazer a matrícula.
        if linha is not None:
            restrito = normalizar(linha.get("acesso_restrito", "")) in ("true", "1", "sim")
        else:
            restrito = bool(curso.get("acesso_restrito", False))
        if restrito:
            st.warning(
                "Atenção: curso com acesso restrito. "
                "Verifique as condições de matrícula na EV.G."
            )
            requisito = (
                str(linha.get("vinculo_exigido", "")).strip()
                if linha is not None else str(curso.get("vinculo_exigido", "")).strip()
            )
            if requisito and normalizar(requisito) not in ("nan", "none"):
                st.caption(f"Requisito de acesso informado no catálogo: {requisito}")

        st.link_button("Abrir curso na EV.G", curso["link_do_curso"], use_container_width=True)

        st.markdown("**Esta recomendação despertou seu interesse?**")
        selecionado = st.session_state.get("evg_interesses_salvos", {}).get(posicao)
        coluna_sim, coluna_nao = st.columns(2, gap="small")
        with coluna_sim:
            st.button(
                "Me interessou",
                key=f"evg_interesse_sim_{posicao}_{'ativo' if selecionado == 'Me interessou' else 'neutro'}",
                icon=":material/thumb_up:",
                use_container_width=True,
                on_click=selecionar_interesse_curso,
                args=(posicao, "Me interessou"),
            )
        with coluna_nao:
            st.button(
                "Não me interessou",
                key=f"evg_interesse_nao_{posicao}_{'ativo' if selecionado == 'Não me interessou' else 'neutro'}",
                icon=":material/thumb_down:",
                use_container_width=True,
                on_click=selecionar_interesse_curso,
                args=(posicao, "Não me interessou"),
            )
        erro = st.session_state.get("evg_interesses_erros", {}).get(posicao)
        if erro:
            st.error(erro)
        elif selecionado:
            st.caption("Opinião registrada.")

        # Preservar as versões em outros idiomas, quando existirem,
        # sem mostrar um menu de detalhes em todos os cards.
        idiomas = idiomas_alternativos(curso, matriz)
        if idiomas:
            links = " · ".join(f"[{idioma}]({url})" for idioma, url in idiomas)
            st.caption("Este curso também existe em outros idiomas:")
            st.markdown(links)



def mostrar_avaliacao():
    """Avaliação geral opcional; gravada somente com envio explícito."""
    st.markdown(
        '<div id="evg-avaliacao-geral" class="evg-subtitulo">Avaliação da Experiência (Opcional)</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="evg-nota-avaliacao">As perguntas avaliam se a lista foi útil para você, '
        'não a qualidade dos cursos.</p>',
        unsafe_allow_html=True,
    )
    escala = [
        "1 — Nada", "2 — Pouco", "3 — Parcialmente",
        "4 — Muito", "5 — Totalmente", "Não consigo avaliar",
    ]
    with st.container(border=True, key="evg_avaliacao_card"):
        st.radio(
            "Quanto os cursos recomendados combinam com seus interesses?",
            options=escala, index=None, horizontal=True, key="evg_p07",
        )
        st.radio(
            "Quanto a lista ajudou você a encontrar cursos que gostaria de fazer?",
            options=escala, index=None, horizontal=True, key="evg_p09",
        )
    if st.session_state.get("evg_avaliacao_enviada"):
        st.success("Obrigado! Sua avaliação foi registrada.")
        return
    if all(st.session_state.get(chave) for chave in ("evg_p07", "evg_p09")):
        if st.button("Enviar minha avaliação", type="primary"):
            try:
                registrar_avaliacao(
                    st.session_state["evg_participacao_id"],
                    {
                        "p07": st.session_state["evg_p07"],
                        "p09": st.session_state["evg_p09"],
                    },
                )
            except Exception:
                st.error("Não foi possível salvar a avaliação. Tente enviar novamente.")
            else:
                st.session_state["evg_avaliacao_enviada"] = True
                st.rerun()
    else:
        st.html(
            '<div class="evg-aviso-secundario" role="note">'
            '<span class="evg-aviso-icone" aria-hidden="true">i</span>'
            '<div class="evg-aviso-conteudo"><p>Se quiser contribuir, '
            'responda às duas perguntas e clique em Enviar.</p></div>'
            '</div>'
        )


def tentar_registrar_participacao():
    """Uma gravação por resultado; permite retomar em caso de falha."""
    if st.session_state.get("evg_registro_status") == "pendente":
        try:
            registrar_participacao(
                st.session_state["evg_participacao_id"],
                st.session_state["evg_participacao_utc"],
                "",  # Coluna histórica de nome mantida vazia por compatibilidade.
                st.session_state["evg_respostas"],
                st.session_state["evg_resultado"]["cursos"][:5],
            )
        except Exception:
            st.session_state["evg_registro_status"] = "erro"
        else:
            st.session_state["evg_registro_status"] = "salvo"
    if st.session_state.get("evg_registro_status") == "erro":
        st.warning("As recomendações foram geradas, mas não foi possível registrar os dados na planilha.")
        if st.button("Tentar salvar os dados novamente"):
            st.session_state["evg_registro_status"] = "pendente"
            st.rerun()



def main():
    st.session_state.setdefault("evg_tela", "inicio")
    tela = st.session_state["evg_tela"]
    if tela == "inicio":
        # Abertura um pouco mais larga para três cards com ícone ao lado do título.
        st.markdown("<style>.block-container {max-width: 960px;}</style>", unsafe_allow_html=True)
        st.title("Encontre cursos para você")
        st.markdown(
            f'<p class="evg-lead">{APRESENTACAO_ABERTURA}</p>',
            unsafe_allow_html=True,
        )
        with st.container(key="evg_aviso_academico"):
            st.html(
                '<aside class="evg-aviso-academico" role="note" aria-label="Aviso acadêmico">'
                '<span class="evg-aviso-icone" aria-hidden="true">i</span>'
                f'<div class="evg-aviso-conteudo"><p>{APRESENTACAO_AVISO}</p></div>'
                '</aside>'
                """
                <script>
                (() => {
                    // O menu de temas do Streamlit pode divergir do tema do SO.
                    // Leia a aparência ativa do app, inclusive após a troca no menu.
                    if (window.__evgAvisoTemaTimer) {
                        clearInterval(window.__evgAvisoTemaTimer);
                    }
                    const card = document.querySelector('.evg-aviso-academico');
                    if (!card) return;

                    const intensidade = (cor) => {
                        const rgb = cor.match(/rgba?\(([^)]+)\)/i);
                        if (!rgb) return null;
                        const valores = rgb[1].split(',').map(v => Number.parseFloat(v));
                        if (valores.length < 3 ||
                            valores.slice(0, 3).some(v => !Number.isFinite(v))) return null;
                        if (valores.length > 3 && valores[3] === 0) return null;
                        return .2126 * valores[0] + .7152 * valores[1] + .0722 * valores[2];
                    };
                    const atualizar = () => {
                        if (!card.isConnected) {
                            clearInterval(window.__evgAvisoTemaTimer);
                            window.__evgAvisoTemaTimer = null;
                            return;
                        }
                        const app = document.querySelector('[data-testid="stAppViewContainer"]')
                            || document.querySelector('.stApp') || document.body;
                        const estilo = getComputedStyle(app);
                        const brilhoFundo = intensidade(estilo.backgroundColor);
                        // Se a superfície for transparente, usar o texto do app:
                        // letra clara indica tema escuro.
                        const brilhoTexto = intensidade(estilo.color);
                        const escuro = brilhoFundo !== null
                            ? brilhoFundo < 125
                            : (brilhoTexto !== null && brilhoTexto > 150);
                        const modo = escuro ? 'dark' : 'light';
                        if (card.dataset.evgTema === modo) return;
                        card.dataset.evgTema = modo;
                        card.style.backgroundColor = escuro ? '#22162B' : '#EEE2F2';
                        card.style.color = escuro ? '#F4ECF7' : '#2F2336';
                        card.style.setProperty('--evg-aviso-icon',
                            escuro ? '#DDB5EE' : '#74258F');
                    };
                    atualizar();
                    window.__evgAvisoTemaTimer = setInterval(atualizar, 350);
                })();
                </script>
                """,
                unsafe_allow_javascript=True,
            )
        st.caption(
            "Ao gerar sua lista, suas respostas e os cursos recomendados serão "
            "registrados para análise acadêmica. "
            "Veja os detalhes em 'Sobre os seus dados'."
        )
        # Ação imediata para quem já conhece a proposta do projeto.
        if st.button(
            "Começar questionário", type="primary",
            key="evg_comecar_topo", use_container_width=True,
        ):
            st.session_state["evg_tela"] = "p01"
            solicitar_rolagem_topo()
            st.rerun()
        st.markdown('<div class="evg-subtitulo">Como funciona</div>', unsafe_allow_html=True)
        st.html(APRESENTACAO_COMO_FUNCIONA)
        with st.expander("Como o modelo escolhe os cursos"):
            st.markdown(APRESENTACAO_MODELO)
        with st.expander("Sobre os seus dados"):
            st.markdown(APRESENTACAO_DADOS)
        with st.expander("Conheça nosso projeto"):
            st.markdown(APRESENTACAO_NOSSO_PROJETO)
        # Segunda ação para quem preferiu ler as informações antes de começar.
        if st.button(
            "Começar questionário", type="primary",
            key="evg_comecar_final", use_container_width=True,
        ):
            st.session_state["evg_tela"] = "p01"
            solicitar_rolagem_topo()
            st.rerun()
    elif tela in ("p01", "p02", "p04", "p05", "p06"):
        restaurar_etapa(tela)
        etapas = sequencia()
        st.progress((etapas.index(tela) + 1) / len(etapas))
        # O bloco inteiro da pergunta é identificado pela etapa. Assim, o
        # Streamlit não reutiliza elementos da tela anterior ao trocar de pergunta.
        with st.container(key=f"evg_pergunta_{tela}"):
            cabecalho_da_pergunta(tela)
            if tela == "p01":
                mostrar_cards_escolha_unica("p01")
            elif tela == "p02":
                menus_de_opcoes("p02", "experiencia", 3)
                st.checkbox(OPCOES["opcao_experiencia_outras"], key="evg_p02_outras")
            elif tela == "p04":
                menus_de_opcoes("p04", "areas_cursos", 3)
                st.checkbox(
                    OPCOES["opcao_formacao_nenhuma"],
                    key="evg_p04_nenhuma",
                    disabled=bool(valor("evg_p04_privacidade", False)),
                    on_change=ao_alterar_opcao_exclusiva_p04,
                    args=("evg_p04_nenhuma",),
                )
                st.checkbox(
                    OPCOES["opcao_formacao_privacidade"],
                    key="evg_p04_privacidade",
                    disabled=bool(valor("evg_p04_nenhuma", False)),
                    on_change=ao_alterar_opcao_exclusiva_p04,
                    args=("evg_p04_privacidade",),
                )
                st.caption(
                    "Nenhuma das opções e Prefiro não informar são escolhas "
                    "exclusivas e não contam entre as três áreas."
                )
            elif tela == "p05":
                st.checkbox(OPCOES["opcao_interesses_nao_sei"], key="evg_p05_nao_sei")
                if not st.session_state.get("evg_p05_nao_sei", False):
                    menus_de_opcoes("p05", "assuntos_p05", 3)
            elif tela == "p06":
                mostrar_cards_escolha_unica("p06")
            st.divider()
            botoes_navegacao(tela)
    elif tela == "resultado":
        resultado = st.session_state.get("evg_resultado")
        if not resultado:
            st.warning("Responda ao questionário para gerar suas recomendações.")
            if st.button("Iniciar", type="primary"):
                reiniciar()
            return
        st.markdown(
            '<div class="evg-cabecalho-resultado">'
            '<h2 class="evg-titulo">Cursos Recomendados para Você</h2>'
            '<a class="evg-atalho-avaliacao" href="#evg-avaliacao-geral" '
            'aria-label="Ir para a avaliação da experiência">'
            'Avaliar experiência <span aria-hidden="true">↓</span></a>'
            '</div>',
            unsafe_allow_html=True,
        )
        tentar_registrar_participacao()
        st.write("Compare os cursos e marque, se quiser, quais sugestões despertaram seu interesse. As escolhas são salvas automaticamente.")
        matriz, *_ = carregar_modelo()
        # A página de resultados é mais larga para acomodar os cards.
        st.markdown(
            "<style>.block-container {max-width: 1180px;}"
            "@media (max-width: 900px) {.block-container {padding-left: 1rem; padding-right: 1rem;}}</style>",
            unsafe_allow_html=True,
        )
        cursos = resultado["cursos"][:5]
        respostas = st.session_state.get("evg_respostas", {})
        # Etapa 2: tres colunas de mesma largura em cada linha.
        # Cursos 4 e 5 ocupam as duas primeiras colunas; a terceira fica
        # disponivel para o convite de avaliacao da proxima etapa.
        primeira_linha = st.columns(3, gap="medium")
        for posicao, curso in enumerate(cursos[:3], start=1):
            with primeira_linha[posicao - 1]:
                mostrar_curso(posicao, curso, matriz, respostas)

        segunda_linha = st.columns(3, gap="medium")
        for posicao, curso in enumerate(cursos[3:], start=4):
            with segunda_linha[posicao - 4]:
                mostrar_curso(posicao, curso, matriz, respostas)

        # Convite destacado no terceiro espaço da segunda linha.
        # Ele não é um curso e não participa dos registros de interesse.
        with segunda_linha[2]:
            st.html(
                """
                <section class="evg-convite-avaliacao"
                         aria-labelledby="evg-convite-titulo">
                    <span class="evg-convite-icone" aria-hidden="true"></span>
                    <h3 id="evg-convite-titulo">Antes de finalizar</h3>
                    <p>Responda 2 perguntas rápidas sobre sua experiência.</p>
                    <a class="evg-convite-botao" href="#evg-avaliacao-geral"
                       aria-label="Responder avaliação da experiência">
                        <span>Responder avaliação</span>
                    </a>
                </section>
                """
            )

        # A primeira e a segunda linha sao blocos Streamlit independentes.
        # Sincronizar os cinco cards de cursos e o convite com a maior
        # altura natural evita cortes e mantém as duas linhas alinhadas.
        st.html(
            """
            <script>
            (() => {
                if (window.__evgCardsAltura) {
                    window.__evgCardsAltura.encerrar();
                }
                const cards = [1, 2, 3, 4, 5]
                    .map(n => document.querySelector('.st-key-evg_curso_card_' + n));
                if (cards.some(card => !card)) return;
                const convite = document.querySelector('.evg-convite-avaliacao');
                if (convite) cards.push(convite);

                let frame = null;
                const observers = [];
                const medir = () => {
                    frame = null;
                    if (cards.some(card => !card.isConnected)) {
                        encerrar();
                        return;
                    }
                    // Retirar a altura anterior ANTES de medir o conteúdo natural.
                    cards.forEach(card => { card.style.minHeight = ''; });
                    const maior = Math.ceil(Math.max(...cards.map(
                        card => card.getBoundingClientRect().height
                    )));
                    cards.forEach(card => {
                        card.style.minHeight = maior + 'px';
                    });
                };
                const agendar = () => {
                    if (frame !== null) cancelAnimationFrame(frame);
                    frame = requestAnimationFrame(medir);
                };
                const escutar = () => {
                    const observer = new MutationObserver(agendar);
                    cards.forEach(card => observer.observe(card, {
                        subtree: true, childList: true, characterData: true
                    }));
                    observers.push(observer);
                };
                const encerrar = () => {
                    observers.forEach(obs => obs.disconnect());
                    window.removeEventListener('resize', agendar);
                    if (frame !== null) cancelAnimationFrame(frame);
                    cards.forEach(card => { card.style.minHeight = ''; });
                    if (window.__evgCardsAltura?.encerrar === encerrar) {
                        window.__evgCardsAltura = null;
                    }
                };
                window.__evgCardsAltura = { encerrar };
                escutar();
                window.addEventListener('resize', agendar, { passive: true });
                agendar();
                if (document.fonts?.ready) document.fonts.ready.then(agendar);
            })();
            </script>
            """,
            unsafe_allow_javascript=True,
        )
        st.divider()
        mostrar_avaliacao()
        st.divider()
        esquerda, direita = st.columns(2, gap="medium")
        with esquerda:
            if st.button("Alterar minhas respostas"):
                voltar("resultado")
        with direita:
            if st.button("Reiniciar e fazer novo teste"):
                reiniciar()
    st.divider()
    st.caption(
        "Protótipo acadêmico independente. Cursos e links da EV.G. "
        "As sugestões são calculadas com um modelo híbrido e respostas ao questionário."
    )
    aplicar_rolagem_topo()


if __name__ == "__main__":
    main()
