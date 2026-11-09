"""Interface de entrega do recomendador de cursos da EV.G.

Execute na raiz do projeto:
    python -m streamlit run codigo/streamlit_app.py

O aplicativo usa o motor híbrido já validado e não altera suas matrizes.
"""
from pathlib import Path
import csv
import io
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

from motor_recomendador import (
    carregar_opcoes,
    corrigir_opcoes_p01,
    montar_perfil,
    recomendar_experimental,
    validar_perfil,
)


RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "arquivos_do_modelo"

st.set_page_config(
    page_title="Encontre cursos na EV.G",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp {
        background: linear-gradient(165deg, #f0f7fc 0%, #ffffff 45%, #f3fbf8 100%);
        color: #17324d;
    }
    .block-container {max-width: 840px; padding-top: 2rem; padding-bottom: 4rem;}
    h1, h2, h3 {color: #163955; letter-spacing: -.025em;}
    h1 {font-size: clamp(1.9rem, 4vw, 2.6rem) !important;}
    .stButton > button[kind="primary"] {
        background: #087f76; border-color: #087f76; color: white;
        font-weight: 650; border-radius: 11px;
    }
    .stButton > button {border-radius: 11px; min-height: 2.75rem;}
    [data-testid="stExpander"] {
        background: #ffffff; border: 1px solid #dce7ed; border-radius: 12px;
    }
    [data-testid="stAlert"] {border-radius: 12px;}
    div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label {
        line-height: 1.4;
    }
    .evg-lead {color: #49657a; font-size: 1.08rem;}
    .evg-eyebrow {
        color: #087f76; text-transform: uppercase; letter-spacing: .12em;
        font-size: .76rem; font-weight: 750;
    }
</style>
""",
    unsafe_allow_html=True,
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

# P02 é pertinente para quem trabalha, trabalhou ou está mudando de carreira.
# Quem está apenas estudando ou procurando o primeiro emprego vai direto à P04.
SITUACOES_COM_P02 = {"trabalho", "trabalho_estudo", "oportunidade", "transicao"}

# Cada etapa tem seu próprio título. Usar uma única fonte de títulos evita
# reaproveitar visualmente o enunciado da P01 nas demais etapas.
PERGUNTAS = {
    "p01": ("P01 · Situação atual", "Qual é sua situação atualmente?"),
    "p02": ("P02 · Experiência profissional", "Em quais áreas você trabalha ou já trabalhou?"),
    "p04": ("P04 · Formação e conhecimentos", "Em quais áreas você já estudou ou possui conhecimentos?"),
    "p05": ("P05 · Interesses de aprendizagem", "Quais assuntos você gostaria de aprender?"),
    "p06": ("P06 · Objetivo", "Qual é seu principal objetivo ao fazer um curso?"),
}


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


def menus_de_opcoes(tipo, campo, limite):
    for numero, grupo in enumerate(GRUPOS):
        itens = (
            [item["nome"] for item in grupo[campo]]
            if campo == "experiencia" else grupo[campo]
        )
        with st.expander(grupo["nome"]):
            for indice, item in enumerate(itens):
                st.checkbox(item, key=f"evg_{tipo}_{numero}_{indice}")
    quantidade = len(marcadas((tipo, campo)))
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
            st.session_state["evg_tela"] = "resultado"
            st.rerun()
        except (ValueError, KeyError, FileNotFoundError) as erro:
            st.error(str(erro))
        return
    etapas = sequencia()
    st.session_state["evg_tela"] = etapas[etapas.index(etapa) + 1]
    st.rerun()


def voltar(etapa):
    guardar_respostas()
    if etapa == "resultado":
        st.session_state["evg_tela"] = "p06"
    elif etapa == "avaliacao":
        st.session_state["evg_tela"] = "resultado"
    else:
        etapas = sequencia()
        posicao = etapas.index(etapa)
        st.session_state["evg_tela"] = etapas[posicao - 1] if posicao else "inicio"
    st.rerun()


def botoes_navegacao(etapa):
    esquerda, direita = st.columns([1, 2], gap="medium")
    with esquerda:
        if st.button("← Voltar", use_container_width=True):
            voltar(etapa)
    with direita:
        texto = "Ver meus cinco cursos" if etapa == "p06" else "Avançar →"
        if st.button(texto, type="primary", use_container_width=True):
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
    nome = st.session_state.get("evg_nome", "")
    for chave in list(st.session_state):
        if chave.startswith("evg_"):
            del st.session_state[chave]
    st.session_state["evg_nome"] = nome
    st.session_state["evg_tela"] = "inicio"
    st.rerun()


def formulario_avaliacao():
    st.subheader("Sua opinião sobre as recomendações")
    st.write("As perguntas avaliam se a lista foi útil para você, e não a qualidade dos cursos.")
    st.radio(
        "1. Quanto os cursos recomendados combinam com seus interesses?",
        options=["1 — Nada", "2 — Pouco", "3 — Parcialmente", "4 — Muito", "5 — Totalmente", "Não consigo avaliar"],
        index=None, key="evg_p07",
    )
    st.radio(
        "2. Algum dos cursos despertou seu interesse?",
        options=["Sim", "Não", "Ainda não sei"],
        index=None, key="evg_p08",
    )
    st.radio(
        "3. Quanto a lista ajudou você a encontrar cursos que gostaria de fazer?",
        options=["1 — Nada", "2 — Pouco", "3 — Parcialmente", "4 — Muito", "5 — Totalmente", "Não consigo avaliar"],
        index=None, key="evg_p09",
    )
    if all(st.session_state.get(chave) for chave in ("evg_p07", "evg_p08", "evg_p09")):
        dados = st.session_state.get("evg_respostas", {})
        resultado = st.session_state.get("evg_resultado", {})
        linha = {
            "nome_opcional": st.session_state.get("evg_nome", ""),
            "situacao_p01": dados.get("situacao", ""),
            "experiencia_p02": " | ".join(dados.get("experiencia", [])),
            "formacao_p04": " | ".join(dados.get("formacao", [])),
            "interesses_p05": " | ".join(dados.get("interesses", [])) or "Ainda não sei",
            "objetivo_p06": dados.get("objetivo", ""),
            "avaliacao_p07": st.session_state["evg_p07"],
            "avaliacao_p08": st.session_state["evg_p08"],
            "avaliacao_p09": st.session_state["evg_p09"],
            "cursos_recomendados": " | ".join(
                c["nome_curso"] for c in resultado.get("cursos", [])
            ),
        }
        memoria = io.StringIO()
        escritor = csv.DictWriter(memoria, fieldnames=linha.keys(), delimiter=";")
        escritor.writeheader()
        escritor.writerow(linha)
        st.success("Obrigado! Sua avaliação está pronta para ser compartilhada.")
        st.download_button(
            "📥 Baixar minha avaliação",
            data=memoria.getvalue().encode("utf-8-sig"),
            file_name="avaliacao_evg.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
        st.caption(
            "Para esta versão de teste, envie o arquivo baixado à equipe do projeto. "
            "As respostas ainda não são armazenadas automaticamente em um banco de dados."
        )
    else:
        st.info("Responda às três perguntas para gerar seu arquivo de avaliação.")
    if st.button("← Voltar às recomendações"):
        voltar("avaliacao")
    if st.button("Responder novamente com outro perfil"):
        reiniciar()


def main():
    st.session_state.setdefault("evg_tela", "inicio")
    tela = st.session_state["evg_tela"]
    st.markdown('<div class="evg-eyebrow">Projeto Aplicado III • EV.G</div>', unsafe_allow_html=True)
    st.title("Encontre cursos para você")
    if tela == "inicio":
        st.markdown(
            '<p class="evg-lead">Conte um pouco sobre seus interesses e receba '
            'cinco sugestões de cursos da Escola Virtual de Governo.</p>',
            unsafe_allow_html=True,
        )
        st.info(
            "Você responderá algumas perguntas, uma por vez. "
            "Ao final, verá cinco cursos com links e poderá avaliar se as sugestões foram úteis."
        )
        st.text_input("Como gostaria de ser chamado(a)? (opcional)", key="evg_nome")
        if st.button("Começar questionário →", type="primary", use_container_width=True):
            st.session_state["evg_tela"] = "p01"
            st.rerun()
    elif tela in ("p01", "p02", "p04", "p05", "p06"):
        restaurar_etapa(tela)
        etapas = sequencia()
        st.progress((etapas.index(tela) + 1) / len(etapas))
        st.caption(f"Pergunta {etapas.index(tela) + 1} de {len(etapas)}")
        # O bloco é identificado pela etapa. Assim, o Streamlit não reutiliza
        # o título exibido na página anterior ao trocar as perguntas.
        etiqueta, titulo = PERGUNTAS[tela]
        with st.container(key=f"evg_pergunta_{tela}"):
            st.markdown(f'<div class="evg-eyebrow">{etiqueta}</div>', unsafe_allow_html=True)
            st.markdown(f"### {titulo}")

        if tela == "p01":
            st.radio(
                "Escolha uma opção",
                options=list(ROTULOS_P01.values()),
                index=None,
                key="evg_p01",
            )
        elif tela == "p02":
            st.caption("Escolha até três áreas. Você pode abrir mais de uma categoria.")
            menus_de_opcoes("p02", "experiencia", 3)
            st.checkbox(OPCOES["opcao_experiencia_outras"], key="evg_p02_outras")
        elif tela == "p04":
            st.caption("Considere faculdade, cursos, trabalho e estudos por conta própria.")
            menus_de_opcoes("p04", "areas_cursos", 3)
            st.checkbox(OPCOES["opcao_formacao_nenhuma"], key="evg_p04_nenhuma")
            st.checkbox(OPCOES["opcao_formacao_privacidade"], key="evg_p04_privacidade")
        elif tela == "p05":
            st.caption("Escolha até três assuntos, mesmo que não tenham relação com sua formação.")
            st.checkbox(OPCOES["opcao_interesses_nao_sei"], key="evg_p05_nao_sei")
            if not st.session_state.get("evg_p05_nao_sei", False):
                menus_de_opcoes("p05", "assuntos_p05", 3)
        elif tela == "p06":
            st.radio(
                "Escolha uma opção",
                options=list(OBJETIVOS),
                format_func=lambda codigo: OBJETIVOS[codigo],
                index=None,
                key="evg_p06",
            )
        st.divider()
        botoes_navegacao(tela)
    elif tela == "resultado":
        nome = st.session_state.get("evg_nome", "").strip()
        st.subheader(f"Seus cinco cursos recomendados{', ' + nome if nome else ''}")
        st.write("Veja os cursos e abra os links para conhecer os conteúdos.")
        resultado = st.session_state.get("evg_resultado")
        if not resultado:
            st.warning("Responda ao questionário para gerar suas recomendações.")
            if st.button("Iniciar"):
                reiniciar()
            return
        matriz, *_ = carregar_modelo()
        for posicao, curso in enumerate(resultado["cursos"][:5], start=1):
            st.markdown(f"**{posicao}. [{curso['nome_curso']}]({curso['link_do_curso']})**")
            idiomas = idiomas_alternativos(curso, matriz)
            if idiomas and st.checkbox(
                "Ver opções em outros idiomas",
                key=f"evg_idiomas_{curso['id_curso_canonico']}",
            ):
                for idioma, url in idiomas:
                    st.markdown(f"[{idioma}]({url})")
        st.divider()
        if st.button("Avaliar essas recomendações →", type="primary", use_container_width=True):
            st.session_state["evg_tela"] = "avaliacao"
            st.rerun()
        if st.button("← Alterar minhas respostas"):
            voltar("resultado")
    elif tela == "avaliacao":
        formulario_avaliacao()
    st.divider()
    st.caption(
        "Protótipo acadêmico independente. Cursos e links da EV.G. "
        "As sugestões são calculadas com um modelo híbrido e respostas ao questionário."
    )


if __name__ == "__main__":
    main()
