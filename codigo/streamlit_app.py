"""Interface de entrega do recomendador de cursos da EV.G.

Execute na raiz do projeto:
    python -m streamlit run codigo/streamlit_app.py

O aplicativo usa o motor híbrido já validado e não altera suas matrizes.
"""
from pathlib import Path
import html
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
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    /* Largura da página: uma coluna centralizada, confortável de ler */
    /* O espaço no topo (5rem) evita que a primeira linha fique escondida
       atrás da barra fixa do Streamlit, onde aparece o botão Deploy */
    .block-container {max-width: 760px; padding-top: 5rem; padding-bottom: 4rem;}

    /* Título de cada pergunta (azul, como nos prints de referência) */
    .evg-titulo {
        color: #3d82e0; font-size: clamp(1.6rem, 4vw, 2.1rem);
        font-weight: 700; line-height: 1.2; margin: .4rem 0 1rem 0;
    }
    .evg-subtitulo {
        color: #3d82e0; font-size: 1.25rem; font-weight: 650;
        margin: 1.2rem 0 .6rem 0;
    }

    /* Caixa cinza de "Orientação". Fundo claro + letra escura = legível
       tanto no tema claro quanto no escuro. */
    .evg-orientacao {
        background: #e3e7ec; color: #1f2937; border-radius: 10px;
        padding: .85rem 1.1rem; margin-bottom: 1.2rem; line-height: 1.45;
    }

    /* Botão principal azul (os dois seletores cobrem versões diferentes do Streamlit) */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    .stDownloadButton > button[kind="primary"],
    .stDownloadButton > button[data-testid="stBaseButton-primary"] {
        background: #2563eb; border-color: #2563eb; color: #ffffff;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    .stDownloadButton > button[kind="primary"]:hover,
    .stDownloadButton > button[data-testid="stBaseButton-primary"]:hover {
        background: #1d4ed8; border-color: #1d4ed8; color: #ffffff;
    }
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 10px; min-height: 2.75rem;
    }

    /* Caixas que abrem (grupos de áreas e cursos): sem fundo fixo, para
       combinar com o tema claro ou escuro de quem estiver usando */
    [data-testid="stExpander"] {
        background: transparent; border: 1px solid rgba(128, 128, 128, .35);
        border-radius: 10px;
    }
    [data-testid="stAlert"] {border-radius: 10px;}
    div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label {
        line-height: 1.4;
    }
    .evg-lead {opacity: .8; font-size: 1.08rem;}
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

# Textos de cada etapa: (título azul, pergunta, texto da caixa "Orientação").
# Para mudar qualquer frase da tela, é só editar aqui.
# Usar uma única fonte de textos evita reaproveitar visualmente o enunciado da
# P01 nas demais etapas.
PERGUNTAS = {
    "p01": (
        "P01 — Situação Atual",
        "Qual é sua situação atualmente?",
        "Primeiro, queremos conhecer sua situação atual. Considere o que "
        "melhor representa seu momento neste período.",
    ),
    "p02": (
        "P02 — Experiência Profissional",
        "Em quais áreas você trabalha ou já trabalhou?",
        "Escolha até três áreas. Você pode abrir mais de uma categoria.",
    ),
    "p04": (
        "P04 — Formação e Conhecimentos",
        "Em quais áreas você já estudou ou possui conhecimentos?",
        "Considere faculdade, cursos, trabalho e estudos por conta própria. "
        "Escolha até três áreas.",
    ),
    "p05": (
        "P05 — Interesses de Aprendizagem",
        "Quais assuntos você gostaria de aprender?",
        "Escolha até três assuntos, mesmo que não tenham relação com sua "
        "formação.",
    ),
    "p06": (
        "P06 — Objetivo de Aprendizagem",
        "Qual é seu principal objetivo ao fazer um curso?",
        "Por fim, considerando sua vida profissional, seus estudos e seus "
        "interesses, queremos entender o que você busca ao fazer cursos "
        "neste momento.",
    ),
}


def cabecalho_da_pergunta(etapa):
    """Título azul + caixa cinza de orientação, como nos prints de referência."""
    titulo, _, orientacao = PERGUNTAS[etapa]
    st.markdown(f'<h2 class="evg-titulo">{titulo}</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="evg-orientacao">👉 <strong>Orientação:</strong> {orientacao}</div>',
        unsafe_allow_html=True,
    )


def pergunta_em_azul(etapa):
    """Pergunta em azul (usada nas telas com caixas de marcar)."""
    st.markdown(
        f'<div class="evg-subtitulo">{PERGUNTAS[etapa][1]}</div>',
        unsafe_allow_html=True,
    )


# Textos da tela inicial. Para mudar qualquer frase, é só editar aqui.
APRESENTACAO_ABERTURA = (
    "Responda a algumas perguntas e receba cinco sugestões de cursos da "
    "Escola Virtual de Governo (EV.G), a plataforma de cursos online do "
    "governo federal."
)
APRESENTACAO_AVISO = (
    "**Este é um trabalho acadêmico.** O recomendador foi desenvolvido por "
    "estudantes do Mackenzie no **Projeto Aplicado III** e está em fase de "
    "testes. Ele **não é um serviço oficial da EV.G**. As sugestões são só um "
    "ponto de partida: para se inscrever em qualquer curso, use o site da EV.G."
)
APRESENTACAO_COMO_FUNCIONA = """
1. **Você responde** a poucas perguntas, uma por vez, sobre sua situação, o que
   já fez e estudou, o que quer aprender e qual é o seu objetivo. É só clicar
   nas opções.
2. **O modelo compara** o seu perfil com os mais de mil cursos do catálogo da
   EV.G e escolhe cinco.
3. **Você recebe a lista**, com os links dos cursos, e avalia 
   se ela foi útil. Essa avaliação ajuda o nosso trabalho.
"""
APRESENTACAO_MODELO = """
O modelo é **híbrido**: junta duas pistas.

- **O conteúdo dos cursos:** assuntos e áreas de cada curso, comparados com as
  suas respostas.
- **O que costuma andar junto:** associações do passado entre cursos, somadas a
  partir de muitas matrículas na EV.G, sem identificar nenhuma pessoa.

Juntando as duas pistas, ele monta a lista de cinco cursos. O seu objetivo
(pergunta P06) ajuda a decidir quanto cada parte do seu perfil (trabalho,
estudos e interesses) pesa na escolha.
"""
APRESENTACAO_DADOS = """
- Não pedimos login, e-mail, CPF nem outros dados pessoais. Só o nome, que é
  opcional.
- O app **não consulta o seu histórico** na EV.G. O seu perfil vem apenas das
  respostas que você dá aqui.
- Suas respostas servem só para montar a sua lista: elas **não alteram o
  modelo**, e cada pessoa começa do zero.
- Ao gerar sua lista, as respostas (e o nome, se informado) e os cinco cursos
  recomendados são registrados numa planilha privada do projeto para análise
  acadêmica. As avaliações, quando enviadas, também são registradas.
- Suas respostas não são enviadas à EV.G e não alteram o modelo.
- Alguns cursos têm requisitos de acesso. Quem decide se você pode se matricular
  é a EV.G.
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


def menus_de_opcoes(tipo, campo, limite):
    for numero, grupo in enumerate(GRUPOS):
        itens = (
            [item["nome"] for item in grupo[campo]]
            if campo == "experiencia" else grupo[campo]
        )
        with st.expander(f"📁 {grupo['nome']}"):
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
            st.session_state["evg_participacao_id"] = str(uuid4())
            st.session_state["evg_participacao_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            st.session_state["evg_registro_status"] = "pendente"
            st.session_state["evg_avaliacao_enviada"] = False
            for chave in list(st.session_state):
                if chave in ("evg_p07", "evg_p08", "evg_p09") or chave.startswith("evg_interesse_curso_"):
                    st.session_state.pop(chave, None)
            st.session_state["evg_interesses_salvos"] = {}
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
    else:
        etapas = sequencia()
        posicao = etapas.index(etapa)
        st.session_state["evg_tela"] = etapas[posicao - 1] if posicao else "inicio"
    st.rerun()


def botoes_navegacao(etapa):
    esquerda, direita = st.columns([1, 3], gap="medium")
    with esquerda:
        if st.button("← Voltar"):
            voltar(etapa)
    with direita:
        texto = (
            "🎯 Gerar Recomendações Personalizadas"
            if etapa == "p06" else "Avançar ➡️"
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
    nome = st.session_state.get("evg_nome", "")
    for chave in list(st.session_state):
        if chave.startswith("evg_"):
            del st.session_state[chave]
    st.session_state["evg_nome"] = nome
    st.session_state["evg_tela"] = "inicio"
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


def mostrar_curso(posicao, curso, matriz, respostas):
    """Card compacto, com link e avaliação individual em linhas consecutivas."""
    linha = linha_do_curso(curso, matriz)
    with st.container(border=True):
        st.markdown(f"**{posicao}. {curso['nome_curso']}**")
        area = str(curso.get("area_principal", "")).strip()
        if area:
            st.caption(f"Área: {area}")

        st.markdown("**Por que apareceu para você?**")
        st.caption(explicar_recomendacao(curso, linha, respostas))
        st.link_button("Abrir curso na EV.G ↗", curso["link_do_curso"], use_container_width=True)

        st.caption("Esta recomendação despertou seu interesse? (opcional)")
        interesse = st.radio(
            f"Interesse no curso {posicao}",
            options=["Me interessou", "Não me interessou"],
            index=None,
            horizontal=True,
            label_visibility="collapsed",
            key=f"evg_interesse_curso_{posicao}",
        )
        if interesse:
            salvos = st.session_state.setdefault("evg_interesses_salvos", {})
            if st.session_state.get("evg_registro_status") != "salvo":
                st.warning("O registro do questionário precisa ser concluído para salvar esta opinião.")
            elif salvos.get(posicao) != interesse:
                try:
                    registrar_interesse(
                        st.session_state["evg_participacao_id"],
                        posicao,
                        interesse,
                    )
                except Exception:
                    st.error("Não conseguimos salvar sua opinião. Você pode tentar novamente.")
                else:
                    salvos[posicao] = interesse
            if salvos.get(posicao) == interesse:
                st.caption("✓ Opinião registrada.")

        with st.expander("Mais informações"):
            if linha is not None:
                instituicao = str(linha.get("instituicao", "")).strip()
                if instituicao:
                    st.markdown(f"**Instituição:** {instituicao}")
                restrito = normalizar(linha.get("acesso_restrito", "")) in ("true", "1", "sim")
                if restrito:
                    st.warning(
                        "Este curso pode ter requisitos de acesso. Consulte a EV.G."
                    )
                    requisito = str(linha.get("vinculo_exigido", "")).strip()
                    if requisito:
                        st.caption(f"Requisito informado pela EV.G: {requisito}")
            idiomas = idiomas_alternativos(curso, matriz)
            if idiomas:
                links = " · ".join(f"[{idioma}]({url})" for idioma, url in idiomas)
                st.markdown(f"Outros idiomas disponíveis: {links}")



def mostrar_avaliacao():
    """Avaliação geral opcional; gravada somente com envio explícito."""
    st.markdown(
        '<div class="evg-subtitulo">📝 Avaliação da Experiência (Opcional)</div>',
        unsafe_allow_html=True,
    )
    st.caption("As perguntas avaliam se a lista foi útil para você, não a qualidade dos cursos.")
    escala = [
        "1 — Nada", "2 — Pouco", "3 — Parcialmente",
        "4 — Muito", "5 — Totalmente", "Não consigo avaliar",
    ]
    with st.container(border=True):
        st.radio(
            "P07 — Quanto os cursos recomendados combinam com seus interesses?",
            options=escala, index=None, horizontal=True, key="evg_p07",
        )
        st.radio(
            "P09 — Quanto a lista ajudou você a encontrar cursos que gostaria de fazer?",
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
        st.info("Se quiser contribuir, responda às duas perguntas e clique em Enviar.")


def tentar_registrar_participacao():
    """Uma gravação por resultado; permite retomar em caso de falha."""
    if st.session_state.get("evg_registro_status") == "pendente":
        try:
            registrar_participacao(
                st.session_state["evg_participacao_id"],
                st.session_state["evg_participacao_utc"],
                st.session_state.get("evg_nome", ""),
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
        st.title("Encontre cursos para você")
        st.markdown(
            f'<p class="evg-lead">{APRESENTACAO_ABERTURA}</p>',
            unsafe_allow_html=True,
        )
        st.info(APRESENTACAO_AVISO)
        st.markdown('<div class="evg-subtitulo">Como funciona</div>', unsafe_allow_html=True)
        st.markdown(APRESENTACAO_COMO_FUNCIONA)
        with st.expander("🔎 Como o modelo escolhe os cursos"):
            st.markdown(APRESENTACAO_MODELO)
        with st.expander("🔒 Sobre os seus dados"):
            st.markdown(APRESENTACAO_DADOS)
        st.text_input("Como gostaria de ser chamado(a)? (opcional)", key="evg_nome")
        st.checkbox(
            "Estou ciente de que minhas respostas e os cursos apresentados serão "
            "registrados para a análise acadêmica descrita acima.",
            key="evg_ciente_registro",
        )
        if st.button(
            "Começar questionário ➡️", type="primary",
            disabled=not st.session_state.get("evg_ciente_registro", False),
        ):
            st.session_state["evg_tela"] = "p01"
            st.rerun()
    elif tela in ("p01", "p02", "p04", "p05", "p06"):
        restaurar_etapa(tela)
        etapas = sequencia()
        st.progress((etapas.index(tela) + 1) / len(etapas))
        st.caption(f"Pergunta {etapas.index(tela) + 1} de {len(etapas)}")
        # O bloco inteiro da pergunta é identificado pela etapa. Assim, o
        # Streamlit não reutiliza elementos da tela anterior ao trocar de pergunta.
        with st.container(key=f"evg_pergunta_{tela}"):
            cabecalho_da_pergunta(tela)
            if tela == "p01":
                st.radio(
                    PERGUNTAS["p01"][1],
                    options=list(ROTULOS_P01.values()),
                    index=None,
                    key="evg_p01",
                )
            elif tela == "p02":
                pergunta_em_azul("p02")
                menus_de_opcoes("p02", "experiencia", 3)
                st.checkbox(OPCOES["opcao_experiencia_outras"], key="evg_p02_outras")
            elif tela == "p04":
                pergunta_em_azul("p04")
                menus_de_opcoes("p04", "areas_cursos", 3)
                st.checkbox(OPCOES["opcao_formacao_nenhuma"], key="evg_p04_nenhuma")
                st.checkbox(OPCOES["opcao_formacao_privacidade"], key="evg_p04_privacidade")
            elif tela == "p05":
                pergunta_em_azul("p05")
                st.checkbox(OPCOES["opcao_interesses_nao_sei"], key="evg_p05_nao_sei")
                if not st.session_state.get("evg_p05_nao_sei", False):
                    menus_de_opcoes("p05", "assuntos_p05", 3)
            elif tela == "p06":
                st.radio(
                    PERGUNTAS["p06"][1],
                    options=list(OBJETIVOS),
                    format_func=lambda codigo: OBJETIVOS[codigo],
                    index=None,
                    key="evg_p06",
                )
            st.divider()
            botoes_navegacao(tela)
    elif tela == "resultado":
        resultado = st.session_state.get("evg_resultado")
        if not resultado:
            st.warning("Responda ao questionário para gerar suas recomendações.")
            if st.button("Iniciar", type="primary"):
                reiniciar()
            return
        nome = html.escape(st.session_state.get("evg_nome", "").strip())
        saudacao = f", {nome}" if nome else ""
        st.markdown(
            f'<h2 class="evg-titulo">🎯 Cursos Recomendados para Você{saudacao}</h2>',
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
        # Distribuição 3 + 2: a segunda linha usa duas colunas mais largas,
        # sem deixar um terceiro espaço vazio à direita.
        primeira_linha = st.columns(3, gap="medium")
        for posicao, curso in enumerate(cursos[:3], start=1):
            with primeira_linha[posicao - 1]:
                mostrar_curso(posicao, curso, matriz, respostas)

        segunda_linha = st.columns(2, gap="medium")
        for posicao, curso in enumerate(cursos[3:], start=4):
            with segunda_linha[posicao - 4]:
                mostrar_curso(posicao, curso, matriz, respostas)
        st.divider()
        mostrar_avaliacao()
        st.divider()
        esquerda, direita = st.columns(2, gap="medium")
        with esquerda:
            if st.button("← Alterar minhas respostas"):
                voltar("resultado")
        with direita:
            if st.button("🔄 Reiniciar e Fazer Novo Teste"):
                reiniciar()
    st.divider()
    st.caption(
        "Protótipo acadêmico independente. Cursos e links da EV.G. "
        "As sugestões são calculadas com um modelo híbrido e respostas ao questionário."
    )


if __name__ == "__main__":
    main()
