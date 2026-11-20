"""Aplicativo da etapa extensionista: "Encontre cursos na EV.G".

O participante responde a um questionário (P01 a P06), recebe cinco cursos
da EV.G e pode avaliar a lista. As recomendações vêm de motor_recomendador.py;
os registros anônimos vão para o Google Sheets (registro_sheets.py).

Execute na raiz do repositório:
    streamlit run codigo/streamlit_app.py

Organização deste arquivo:
    1. Configuração da página, estilo e carregamento do modelo
    2. Textos e opções do questionário
    3. Estado da sessão e navegação entre as perguntas
    4. Tela de resultados e avaliação
    5. main()
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import streamlit as st

from motor_recomendador import (
    carregar_opcoes,
    eh_verdadeiro,
    montar_perfil,
    normalizar_texto,
    recomendar_cursos,
    separar_lista,
    validar_perfil,
)
from registro_sheets import registrar_avaliacao, registrar_interesse, registrar_participacao


# ====================================================================
# 1. Configuração da página, estilo e carregamento do modelo
# ====================================================================

PASTA_CODIGO = Path(__file__).resolve().parent
MODELO = PASTA_CODIGO.parent / "arquivos_do_modelo"

st.set_page_config(
    page_title="Encontre cursos na EV.G",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Identidade visual (fonte, cores, cartões, tema escuro) fica em estilo.css.
st.markdown("\n<style>" + (PASTA_CODIGO / "estilo.css").read_text(encoding="utf-8") + "</style>\n",
            unsafe_allow_html=True)

# Marca <html> com a classe "evg-tema-escuro" quando o tema escuro está ativo
# (inclusive após trocar o tema pelo menu), para o CSS ajustar as cores.
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


# ====================================================================
# 2. Textos e opções do questionário
# ====================================================================

# Áreas, assuntos, situações (P01) e objetivos (P06) vêm do JSON do modelo.
OPCOES = carregar_opcoes(MODELO / "opcoes_questionario.json")
GRUPOS = OPCOES["grupos"]
ROTULOS_P01 = {item["codigo"]: item["texto"] for item in OPCOES["situacoes_p01"]}
OBJETIVOS = {item["codigo"]: item["texto"] for item in OPCOES["objetivos_p06"]}

# P01 e P06 são de escolha única e aparecem como cartões clicáveis.
# Cada cartão: (ícone do Material Symbols, descrição curta).
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


def selecionar_card(etapa, codigo):
    """Guarda o código da opção escolhida (ex.: 'trabalho', 'crescer')."""
    chave = f"evg_{etapa}"
    st.session_state[chave] = codigo
    st.session_state.setdefault("evg_valores", {})[chave] = codigo


def mostrar_cards_escolha_unica(etapa):
    """Mostra P01 ou P06 como cartões clicáveis, dois por linha."""
    if etapa == "p01":
        opcoes, metadados = ROTULOS_P01, CARDS_P01
    else:
        opcoes, metadados = OBJETIVOS, CARDS_P06
    selecionado = valor(f"evg_{etapa}")

    # A descrição de cada cartão entra como variável CSS (o st.button só aceita o título).
    estilos = []
    for codigo, (_, descricao) in metadados.items():
        seletor = f".st-key-evg_card_{etapa}_{codigo} button"
        # Uma string CSS, não HTML: cada descrição aparece dentro do botão.
        texto_css = descricao.replace("\\", "\\\\").replace('"', '\\"')
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
    # empilha as colunas, exibindo um cartão por linha.
    itens = list(opcoes.items())
    for inicio in range(0, len(itens), 2):
        colunas = st.columns(2, gap="medium")
        for coluna, (codigo, titulo) in zip(colunas, itens[inicio:inicio + 2]):
            icone, _ = metadados[codigo]
            with coluna:
                st.button(
                    titulo,
                    key=f"evg_card_{etapa}_{codigo}",
                    icon=f":material/{icone}:",
                    width="stretch",
                    on_click=selecionar_card,
                    args=(etapa, codigo),
                )

    # P01 e P06: igualar a altura de TODOS os cartões à maior altura natural
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
# Não existe P03: a "confirmação da situação profissional" prevista na especificação
# funcional não entrou na versão final. Os códigos seguem os da especificação.
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


# ====================================================================
# 3. Estado da sessão e navegação entre as perguntas
# ====================================================================

def valor(chave, padrao=None):
    """Lê a resposta guardada mesmo após o Streamlit ocultar o campo."""
    return st.session_state.get(
        chave, st.session_state.get("evg_valores", {}).get(chave, padrao)
    )


def guardar_respostas():
    """Os campos ocultos são limpos pelo Streamlit: guardar cópia separada."""
    guardadas = st.session_state.setdefault("evg_valores", {})
    for chave in list(st.session_state):
        if chave.startswith("evg_p"):
            guardadas[chave] = st.session_state[chave]


def restaurar_etapa(etapa):
    """Preenche os campos quando a pessoa volta para corrigir uma pergunta."""
    guardadas = st.session_state.get("evg_valores", {})
    for chave, resposta in guardadas.items():
        if chave.startswith("evg_" + etapa) and chave not in st.session_state:
            st.session_state[chave] = resposta


def situacao_atual():
    """Código da situação escolhida na P01 (ex.: 'trabalho')."""
    return valor("evg_p01")


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

    # Limpa tanto os campos atuais quanto cópias de respostas já guardadas.
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
    """Marca uma mudança real de etapa, não uma simples interação com campos."""
    st.session_state["evg_rolagem_pendente"] = True
    st.session_state["evg_rolagem_versao"] = (
        st.session_state.get("evg_rolagem_versao", 0) + 1
    )


def aplicar_rolagem_topo():
    """Volta ao topo após mudança de tela, sem rolar nos recarregamentos dos campos.

    O código JavaScript confiável usa as superfícies de rolagem do Streamlit e repete
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
                        '[data-testid="stMain"],' +
                        '[data-testid="stAppViewContainer"],' +
                        '[data-testid="stMainBlockContainer"]'
                    ),
                ];
                scrollers.forEach((el) => {{
                    if (el) el.scrollTop = 0;
                }});
                window.scrollTo({{top: 0, left: 0, behavior: 'instant'}});
                const topContent = document.querySelector(
                    '[data-testid="stMain"] .block-container'
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
            perfil, objetivo = montar_perfil(respostas, OPCOES)
            validar_perfil(perfil, OPCOES)
            matriz, ids, conteudo, matriculas, popularidade = carregar_modelo()
            with st.spinner("Buscando cinco cursos para você..."):
                resultado = recomendar_cursos(
                    perfil, objetivo, matriz, ids, conteudo, matriculas, popularidade,
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
                if chave in ("evg_p07", "evg_p09") or chave.startswith("evg_interesse_curso_"):
                    st.session_state.pop(chave, None)
            st.session_state["evg_interesses_salvos"] = {}
            # Mensagens de erro da lista anterior não devem aparecer na nova.
            st.session_state["evg_interesses_erros"] = {}
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


# ====================================================================
# 4. Tela de resultados e avaliação
# ====================================================================

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
        restrito = eh_verdadeiro(linha.get("acesso_restrito", ""))
        if normalizar_texto(idioma) != "portugues" and url.startswith("https://") and not restrito:
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
            normalizar_texto(item)
            for campo in ("assuntos", "termos_busca")
            for item in separar_lista(linha.get(campo, ""))
        ]
        for interesse in respostas.get("interesses", []):
            if any(normalizar_texto(interesse) in termo for termo in termos):
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
            restrito = eh_verdadeiro(linha.get("acesso_restrito", ""))
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
            if requisito and normalizar_texto(requisito) not in ("nan", "none"):
                st.caption(f"Requisito de acesso informado no catálogo: {requisito}")

        st.link_button("Abrir curso na EV.G", curso["link_do_curso"], width="stretch")

        st.markdown("**Esta recomendação despertou seu interesse?**")
        selecionado = st.session_state.get("evg_interesses_salvos", {}).get(posicao)
        coluna_sim, coluna_nao = st.columns(2, gap="small")
        with coluna_sim:
            st.button(
                "Me interessou",
                key=f"evg_interesse_sim_{posicao}_{'ativo' if selecionado == 'Me interessou' else 'neutro'}",
                icon=":material/thumb_up:",
                width="stretch",
                on_click=selecionar_interesse_curso,
                args=(posicao, "Me interessou"),
            )
        with coluna_nao:
            st.button(
                "Não me interessou",
                key=f"evg_interesse_nao_{posicao}_{'ativo' if selecionado == 'Não me interessou' else 'neutro'}",
                icon=":material/thumb_down:",
                width="stretch",
                on_click=selecionar_interesse_curso,
                args=(posicao, "Não me interessou"),
            )
        erro = st.session_state.get("evg_interesses_erros", {}).get(posicao)
        if erro:
            st.error(erro)
        elif selecionado:
            st.caption("Opinião registrada.")

        # Preservar as versões em outros idiomas, quando existirem,
        # sem mostrar um menu de detalhes em todos os cartões.
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
                "",  # coluna "nome_opcional" da planilha: o app não pede nome, fica vazia
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



# ====================================================================
# 5. Fluxo principal
# ====================================================================

def main():
    st.session_state.setdefault("evg_tela", "inicio")
    tela = st.session_state["evg_tela"]
    if tela == "inicio":
        # Abertura um pouco mais larga para três cartões com ícone ao lado do título.
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
                        const rgb = cor.match(/rgba?\\(([^)]+)\\)/i);
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
            key="evg_comecar_topo", width="stretch",
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
            key="evg_comecar_final", width="stretch",
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
        # A página de resultados é mais larga para acomodar os cartões.
        st.markdown(
            "<style>.block-container {max-width: 1180px;}"
            "@media (max-width: 900px) {.block-container {padding-left: 1rem; padding-right: 1rem;}}</style>",
            unsafe_allow_html=True,
        )
        cursos = resultado["cursos"][:5]
        respostas = st.session_state.get("evg_respostas", {})
        # Grade de três colunas: cursos 1 a 3 na primeira linha; cursos 4 e 5
        # na segunda, com o convite para a avaliação na terceira coluna.
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

        # A primeira e a segunda linha são blocos Streamlit independentes.
        # Sincronizar os cinco cartões de cursos e o convite com a maior
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
