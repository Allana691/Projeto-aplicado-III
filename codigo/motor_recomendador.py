"""Motor de recomendação usado pelo aplicativo Streamlit (etapa extensionista).

O participante não tem histórico de matrículas na EV.G, então o perfil vem
das respostas ao questionário. A lista de cinco cursos combina três notas
(seção 3.9 do relatório):

1. **Interesses** - o curso ensina os assuntos escolhidos na P05?
2. **Trajetória** - o curso é da área de experiência (P02) ou de
   formação (P04) informada? Experiência vale 60% e formação 40%.
3. **Similaridade entre cursos** - modelo híbrido do experimento offline,
   com α = 0,55 (55% conteúdo / 45% matrículas).

Os pesos de cada nota dependem do objetivo escolhido na P06
(``PESOS_POR_OBJETIVO``, Tabela 2 do relatório). Eles foram definidos pelo
grupo e conferidos com perfis simulados, sem validação estatística.

As matrizes de similaridade são pré-calculadas por
``preparar_arquivos_do_modelo.py``; este módulo não lê a base de matrículas.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

import numpy as np


# ====================================================================
# Parâmetros do modelo
# ====================================================================

SEPARADOR = " | "  # separador de listas nas células do CSV
QUANTIDADE_RECOMENDACOES = 5

# α escolhido na validação de 2025 (relatório, seção 3.8.1; notebook 03, seção 6.4).
PESO_CONTEUDO = 0.55

# Nota de trajetória (P02 e P04).
PESO_EXPERIENCIA = 0.60
PESO_FORMACAO = 0.40
NOTA_AREA_PRINCIPAL = 1.00
NOTA_AREA_COMPLEMENTAR = 0.40

# Nota de interesses (P05).
NOTA_ASSUNTO_ENSINADO = 1.00     # o curso ensina o assunto
NOTA_TERMO_DE_APOIO = 0.85       # o assunto aparece só como termo de busca/sinônimo
REFORCO_AREA_DO_ASSUNTO = 0.10   # reforço pela área predominante do assunto
BONUS_VARIOS_ASSUNTOS = 0.04     # por assunto adicional atendido pelo mesmo curso

# Sem assuntos na P05: metade trajetória, metade similaridade entre cursos.
PESO_TRAJETORIA_SEM_ASSUNTOS = 0.50

# Pesos (interesses, trajetória, similaridade) por objetivo da P06.
# Os códigos são os "codigo_modelo" de opcoes_questionario.json:
#   A primeiro emprego | B conseguir emprego | C crescer | D mudar de área
#   E melhorar no trabalho | F interesse pessoal | G explorar assuntos
#   H ainda não sei | I prefiro não informar
PESOS_POR_OBJETIVO = {
    "A": (0.65, 0.20, 0.15), "B": (0.65, 0.20, 0.15),
    "C": (0.60, 0.25, 0.15), "D": (0.80, 0.05, 0.15),
    "E": (0.55, 0.30, 0.15), "F": (0.70, 0.15, 0.15),
    "G": (0.70, 0.15, 0.15), "H": (0.60, 0.25, 0.15),
    "I": (0.60, 0.25, 0.15),
}

# Desempate a favor de cursos de acesso aberto. Diferenças de nota maiores
# que 0,02 (escala 0 a 1) continuam favorecendo o curso mais pertinente.
PREFERENCIA_CURSO_ABERTO = 0.02

VALORES_VERDADEIROS = ("true", "1", "sim")


# ====================================================================
# Utilidades de texto
# ====================================================================

def normalizar_texto(texto):
    """Remove acentos, passa para minúsculas e junta espaços: ' Gestão ' -> 'gestao'."""
    sem_acentos = "".join(
        letra for letra in unicodedata.normalize("NFKD", str(texto).casefold())
        if not unicodedata.combining(letra)
    )
    return " ".join(sem_acentos.split())


def separar_lista(texto):
    """Transforma 'A | B | C' em ['A', 'B', 'C']. Célula vazia vira lista vazia."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return []
    return [parte.strip() for parte in str(texto).split(SEPARADOR) if parte.strip()]


def eh_verdadeiro(valor):
    """Interpreta as marcações 'True', '1' ou 'sim' do CSV."""
    return normalizar_texto(valor) in VALORES_VERDADEIROS


# ====================================================================
# 1. Questionário: validação e conversão em perfil
# ====================================================================

def carregar_opcoes(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _sem_repeticao(valores, campo, erros):
    if not isinstance(valores, list):
        erros.append(f"{campo}: as escolhas devem estar em uma lista")
        return []
    if len(valores) != len(set(valores)):
        erros.append(f"{campo}: existem escolhas repetidas")
    return valores


def _opcoes_validas(opcoes):
    """Devolve (experiências -> áreas, áreas de curso, assuntos) do questionário."""
    grupos = opcoes["grupos"]
    profissionais = {item["nome"]: item["areas_cursos"]
                     for grupo in grupos for item in grupo["experiencia"]}
    areas = {area for grupo in grupos for area in grupo["areas_cursos"]}
    assuntos = {assunto for grupo in grupos for assunto in grupo["assuntos_p05"]}
    return profissionais, areas, assuntos


def validar_respostas(respostas, opcoes):
    """Valida o que a pessoa marcou na interface, antes da conversão em áreas.

    Campos esperados: situacao, experiencia (nomes visíveis), formacao (áreas),
    formacao_opcao ('areas' | 'nenhuma' | 'privacidade'), interesses (assuntos),
    nao_sei (bool) e objetivo. Levanta ValueError com todos os problemas.
    """
    profissionais, areas, assuntos = _opcoes_validas(opcoes)
    erros = []

    situacao = respostas.get("situacao")
    if situacao not in {x["codigo"] for x in opcoes["situacoes_p01"]}:
        erros.append("P01: selecione sua situação atual")
    if respostas.get("objetivo") not in {x["codigo"] for x in opcoes["objetivos_p06"]}:
        erros.append("P06: selecione seu objetivo principal")

    experiencia = _sem_repeticao(respostas.get("experiencia", []), "P02", erros)
    if len(experiencia) > opcoes["max_experiencia"]:
        erros.append(f"P02: selecione no máximo {opcoes['max_experiencia']} áreas profissionais")
    if situacao == "primeiro" and experiencia:
        erros.append("P02: não deve ser respondida ao procurar o primeiro emprego")
    nomes_validos = set(profissionais) | {opcoes["opcao_experiencia_outras"]}
    erros += [f"P02: opção desconhecida: {item}" for item in experiencia if item not in nomes_validos]

    formacao = _sem_repeticao(respostas.get("formacao", []), "P04", erros)
    if len(formacao) > opcoes["max_formacao"]:
        erros.append(f"P04: selecione no máximo {opcoes['max_formacao']} áreas de conhecimento")
    erros += [f"P04: área desconhecida: {item}" for item in formacao if item not in areas]
    modo_p04 = respostas.get("formacao_opcao", "areas")
    if modo_p04 not in ("areas", "nenhuma", "privacidade"):
        erros.append("P04: opção geral inválida")
    if modo_p04 != "areas" and formacao:
        erros.append("P04: opção geral não pode ser combinada com áreas")

    temas = _sem_repeticao(respostas.get("interesses", []), "P05", erros)
    if len(temas) > opcoes["max_interesses"]:
        erros.append(f"P05: selecione no máximo {opcoes['max_interesses']} assuntos")
    erros += [f"P05: assunto não disponível: {tema}" for tema in temas if tema not in assuntos]
    nao_sei = respostas.get("nao_sei", False)
    if not isinstance(nao_sei, bool):
        erros.append("P05: Ainda não sei deve ser verdadeiro ou falso")
    elif nao_sei and temas:
        erros.append("P05: Ainda não sei não pode ser combinado com assuntos")
    elif not nao_sei and not temas:
        erros.append("P05: selecione um assunto ou marque Ainda não sei")

    if erros:
        raise ValueError("\n".join(erros))
    return True


def montar_perfil(respostas, opcoes):
    """Converte as respostas em áreas de curso e no código de objetivo do modelo.

    Retorna (perfil, codigo_objetivo). A experiência marcada como "Outras áreas"
    não é convertida em nenhuma área.
    """
    validar_respostas(respostas, opcoes)
    profissionais, _, _ = _opcoes_validas(opcoes)

    areas_experiencia = []
    if respostas["situacao"] != "primeiro":
        for item in respostas["experiencia"]:
            for area in profissionais.get(item, []):
                if area not in areas_experiencia:
                    areas_experiencia.append(area)

    formacao = list(respostas["formacao"]) if respostas["formacao_opcao"] == "areas" else []
    perfil = {
        "experiencia": {"areas": areas_experiencia},
        "formacao": {"areas": formacao, "assuntos": []},
        "interesses": {
            "areas": [],
            "assuntos": list(respostas["interesses"] or []),
            "nao_sei": bool(respostas["nao_sei"]),
        },
    }

    codigos = {x["codigo"]: x["codigo_modelo"] for x in opcoes["objetivos_p06"]}
    objetivo = codigos[respostas["objetivo"]]
    if respostas["situacao"] == "primeiro" and respostas["objetivo"] == "emprego":
        objetivo = "A"  # primeiro emprego
    return perfil, objetivo


def validar_perfil(perfil, opcoes):
    """Confere o perfil já convertido (também útil em testes sem interface)."""
    _, areas, assuntos = _opcoes_validas(opcoes)
    erros = []
    for nome in ("experiencia", "formacao", "interesses"):
        resposta = perfil.get(nome, {})
        if not isinstance(resposta.get("areas", []), list) or not isinstance(resposta.get("assuntos", []), list):
            erros.append(f"{nome}: áreas e assuntos devem ser listas")
            continue
        erros += [f"{nome}: área desconhecida: {area}"
                  for area in resposta.get("areas", []) if area not in areas]

    formacao = perfil.get("formacao", {})
    if len(formacao.get("areas", [])) > 3 or formacao.get("assuntos", []):
        erros.append("P04: no máximo 3 áreas, sem assuntos adicionais")

    interesses = perfil.get("interesses", {})
    escolhidos = interesses.get("assuntos", [])
    nao_sei = interesses.get("nao_sei", False)
    if interesses.get("areas", []) or len(escolhidos) > 3:
        erros.append("P05: selecione até 3 assuntos, sem marcar áreas")
    erros += [f"P05: assunto desconhecido: {a}" for a in escolhidos if a not in assuntos]
    if nao_sei and escolhidos:
        erros.append("P05: Ainda não sei não pode coexistir com assuntos")
    if not nao_sei and not escolhidos:
        erros.append("P05: escolha assunto ou Ainda não sei")

    if erros:
        raise ValueError("\n".join(erros))
    return True


# ====================================================================
# 2. Catálogo: estrutura de consulta e elegibilidade
# ====================================================================

def preparar_cursos(matriz):
    """Organiza a matriz_cursos_resumida.csv em listas alinhadas (um item por curso)."""
    def conjunto_normalizado(texto):
        return {normalizar_texto(item) for item in separar_lista(texto)}

    return {
        "ids": matriz["id_curso_canonico"].to_numpy(),
        "area_principal": [area.strip() for area in matriz["area_principal"]],
        "areas_complementares": [set(separar_lista(t)) for t in matriz["areas_complementares"]],
        "assuntos": [conjunto_normalizado(t) for t in matriz["assuntos"]],
        "termos_busca": [conjunto_normalizado(t) for t in matriz["termos_busca"]],
        "quantidade": len(matriz),
    }


def _cursos_elegiveis(matriz):
    """Cursos em português e com link HTTPS. Acesso restrito NÃO elimina o curso."""
    idioma = matriz["idioma"].astype(str).map(normalizar_texto)
    link_valido = matriz["link_do_curso"].astype(str).str.startswith("https://")
    return (idioma.isin(("portugues", "pt", "pt-br", "")) & link_valido).to_numpy()


def _cursos_restritos(matriz):
    return matriz["acesso_restrito"].map(eh_verdadeiro).to_numpy()


def _nota_com_preferencia(nota, restrito):
    """Aplica o desempate a favor de cursos abertos (não altera a nota exibida)."""
    return nota - (PREFERENCIA_CURSO_ABERTO if restrito else 0.0)


# ====================================================================
# 3. Notas de trajetória e de interesses
# ====================================================================

def _afinidade_por_areas(areas_escolhidas, cursos):
    """1,00 se a área principal foi marcada; 0,40 se só uma complementar; senão 0."""
    escolhidas = set(areas_escolhidas)
    notas = np.zeros(cursos["quantidade"])
    if not escolhidas:
        return notas
    for i in range(cursos["quantidade"]):
        if cursos["area_principal"][i] in escolhidas:
            notas[i] = NOTA_AREA_PRINCIPAL
        elif cursos["areas_complementares"][i] & escolhidas:
            notas[i] = NOTA_AREA_COMPLEMENTAR
    return notas


def calcular_nota_trajetoria(perfil, cursos):
    """Combina experiência (60%) e formação (40%); se só uma foi informada, ela vale 100%."""
    areas_experiencia = perfil.get("experiencia", {}).get("areas", [])
    formacao = perfil.get("formacao", {})
    informou_experiencia = len(areas_experiencia) > 0
    informou_formacao = len(formacao.get("areas", [])) > 0 or len(formacao.get("assuntos", [])) > 0

    nota_experiencia = _afinidade_por_areas(areas_experiencia, cursos)
    nota_formacao = _afinidade_por_areas(formacao.get("areas", []), cursos)
    if informou_experiencia and informou_formacao:
        return (
            PESO_EXPERIENCIA * nota_experiencia + PESO_FORMACAO * nota_formacao
        ) / (PESO_EXPERIENCIA + PESO_FORMACAO)
    if informou_experiencia:
        return nota_experiencia
    if informou_formacao:
        return nota_formacao
    return np.zeros(cursos["quantidade"])


def correspondencia_por_assuntos(assuntos_escolhidos, cursos):
    """Máscara: o curso tem algum dos assuntos (ou termo de apoio) escolhidos."""
    escolhidos = {normalizar_texto(a) for a in assuntos_escolhidos}
    resultado = np.zeros(cursos["quantidade"], dtype=bool)
    if not escolhidos:
        return resultado
    for i in range(cursos["quantidade"]):
        resultado[i] = bool((cursos["assuntos"][i] | cursos["termos_busca"][i]) & escolhidos)
    return resultado


def _notas_por_assunto(assuntos, cursos, permitido):
    """Para cada assunto da P05: máscara de cursos ligados e nota de 0 a 1."""
    topicos = []
    for assunto in assuntos:
        texto = normalizar_texto(assunto)
        ensina = np.array([texto in c for c in cursos["assuntos"]], dtype=bool)
        termo = np.array([texto in c for c in cursos["termos_busca"]], dtype=bool)
        ligado = ensina | termo
        valores = np.where(ensina, NOTA_ASSUNTO_ENSINADO, np.where(termo, NOTA_TERMO_DE_APOIO, 0.0))
        # A área que mais aparece entre os cursos do assunto reforça a nota,
        # sem criar vínculo para cursos que não têm o assunto.
        achados = np.flatnonzero(ligado & permitido)
        if len(achados):
            areas = Counter(cursos["area_principal"][i] for i in achados)
            for i in achados:
                participacao = areas[cursos["area_principal"][i]] / len(achados)
                valores[i] = min(1.0, valores[i] + REFORCO_AREA_DO_ASSUNTO * participacao)
        topicos.append({"nome": assunto, "mask": ligado, "valores": valores})
    return topicos


def _excluir_profissao_anterior(perfil, cursos):
    """Objetivo 'mudar de área' (D): exclusão conservadora.

    Exclui só cursos cujas áreas estão TODAS dentro das áreas de experiência
    (P02). Cursos com áreas mistas ficam, e um assunto escolhido na P05
    suspende a exclusão. A formação (P04) nunca é tratada como profissão anterior.
    """
    antigas = set(perfil.get("experiencia", {}).get("areas", []))
    interesses = perfil.get("interesses", {})
    novas = set(interesses.get("areas", []))
    assunto_escolhido = correspondencia_por_assuntos(interesses.get("assuntos", []), cursos)
    excluidos = np.zeros(cursos["quantidade"], dtype=bool)
    if not antigas:
        return excluidos
    for i in range(cursos["quantidade"]):
        todas = {cursos["area_principal"][i]} | cursos["areas_complementares"][i]
        todas.discard("")
        exclusivo = bool(todas) and bool(todas & antigas) and todas <= antigas
        excecao = bool(todas & novas) or bool(assunto_escolhido[i])
        excluidos[i] = exclusivo and not excecao
    return excluidos


# ====================================================================
# 4. Similaridade entre cursos (modelo híbrido do experimento offline)
# ====================================================================

def _normalizar_pelo_maximo(vetor):
    vetor = np.nan_to_num(np.asarray(vetor, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    vetor = np.maximum(vetor, 0.0)
    maior = float(vetor.max()) if vetor.size else 0.0
    return vetor / maior if maior else np.zeros_like(vetor)


def similaridade_hibrida(referencias, conteudo, matriculas, popularidade, peso_conteudo=PESO_CONTEUDO):
    """Similaridade dos cursos com os cursos de referência do perfil.

    referencias: peso de cada curso como ponto de partida (ex.: nota de interesses).
    Cada componente é normalizado pelo maior valor antes da combinação, como no
    notebook 03. Cursos sem matrículas usam apenas a similaridade de conteúdo.
    """
    pesos = np.maximum(np.asarray(referencias, dtype=float), 0.0)
    if not np.any(pesos):
        return np.zeros(len(pesos))
    conteudo_sem_diagonal = np.asarray(conteudo, dtype=float).copy()
    np.fill_diagonal(conteudo_sem_diagonal, 0.0)  # o curso não é semelhante a si mesmo
    nota_conteudo = _normalizar_pelo_maximo(pesos @ conteudo_sem_diagonal)
    nota_matriculas = _normalizar_pelo_maximo(pesos @ matriculas)
    hibrida = peso_conteudo * nota_conteudo + (1 - peso_conteudo) * nota_matriculas
    sem_matriculas = np.asarray(popularidade) == 0
    hibrida[sem_matriculas] = nota_conteudo[sem_matriculas]
    return np.clip(hibrida, 0.0, 1.0)


# ====================================================================
# 5. Diversidade da lista (evitar cursos repetidos ou da mesma série)
# ====================================================================

PALAVRAS_GENERICAS_TITULO = {
    "o", "a", "os", "as", "ao", "aos", "da", "de", "do", "dos", "das", "para", "em",
    "introducao", "basico", "basica", "fundamentos", "conceitos", "curso",
    "usuario", "municipal", "estadual", "federal",
}


def _palavras_do_titulo(titulo):
    palavras = re.findall(r"[a-z0-9]+", normalizar_texto(titulo))
    return frozenset(p for p in palavras if p not in PALAVRAS_GENERICAS_TITULO)


def _mesma_familia(titulo1, titulo2):
    """Títulos praticamente iguais ou do mesmo prefixo 'Série: módulo'."""
    a, b = _palavras_do_titulo(titulo1), _palavras_do_titulo(titulo2)
    if not a or not b:
        return False
    if a == b:
        return True
    titulo1, titulo2 = str(titulo1), str(titulo2)
    if ":" in titulo1 and ":" in titulo2:
        prefixo = _palavras_do_titulo(titulo1.split(":")[0])
        return len(prefixo) >= 3 and prefixo == _palavras_do_titulo(titulo2.split(":")[0])
    return False


def _serie_do_curso(titulo):
    """Séries conhecidas do catálogo que não devem ocupar a lista sozinhas."""
    t = normalizar_texto(titulo)
    if t.startswith("s2id -"):
        return "s2id"
    if "programa - " in t and t.startswith("eixo "):
        return "programa:" + t.rsplit("programa - ", 1)[-1].strip()
    if t.startswith("introducao a ciencia de dados - modelos de "):
        return "modelos_ciencia_dados"
    if t.startswith("transferencias discricionarias da uniao:"):
        return "transferencias_discricionarias"
    return ""


class _Lista:
    """Lista de até cinco cursos que respeita as regras de diversidade."""

    def __init__(self, matriz, permitido):
        self.titulos = matriz["nome_curso"].tolist()
        self.permitido = permitido
        self.indices = []

    def cheia(self):
        return len(self.indices) >= QUANTIDADE_RECOMENDACOES

    def adicionar(self, i):
        if self.cheia() or i in self.indices or not self.permitido[i]:
            return False
        if any(_mesma_familia(self.titulos[i], self.titulos[j]) for j in self.indices):
            return False
        serie = _serie_do_curso(self.titulos[i])
        if serie:
            # No máximo 2 módulos de uma série; para S2ID, 1, pois as
            # versões municipal/estadual/federal são muito parecidas.
            limite = 1 if serie == "s2id" else 2
            if sum(_serie_do_curso(self.titulos[j]) == serie for j in self.indices) >= limite:
                return False
        self.indices.append(i)
        return True


# ====================================================================
# 6. Recomendação
# ====================================================================

# Prefixos de palavras comuns demais para indicar vizinhança de conteúdo.
PREFIXOS_GENERICOS = {
    "gesta", "publi", "curso", "dados", "tecno", "funda", "forma", "metod", "digit",
    "servi", "proje", "aplic", "feder", "estud", "anali", "conhe", "apren",
}


def _prefixos_de_conteudo(cursos, i):
    """Prefixos (5 letras) das palavras dos assuntos e termos de busca do curso."""
    prefixos = set()
    for termo in list(cursos["assuntos"][i]) + list(cursos["termos_busca"][i]):
        for palavra in re.findall(r"[a-z0-9]+", normalizar_texto(termo)):
            if len(palavra) >= 5 and palavra[:5] not in PREFIXOS_GENERICOS:
                prefixos.add(palavra[:5])
    return prefixos


def recomendar_cursos(perfil, objetivo, matriz, ids_modelo, semelhanca_conteudo,
                      semelhanca_matriculas, popularidade):
    """Gera as cinco recomendações para um perfil do questionário.

    Mantém só cursos em português e com link válido, inclui cursos de acesso
    restrito (com preferência por abertos quando a nota é próxima) e não grava
    nenhum histórico.
    """
    ids = np.asarray(ids_modelo)
    n = len(matriz)
    if (not np.array_equal(matriz["id_curso_canonico"].to_numpy(), ids)
            or np.shape(semelhanca_conteudo) != (n, n)
            or np.shape(semelhanca_matriculas) != (n, n)
            or len(popularidade) != n):
        raise ValueError("IDs/matrizes incompatíveis; não é seguro recomendar cursos.")
    objetivo = str(objetivo).upper()
    if objetivo not in PESOS_POR_OBJETIVO:
        raise ValueError("Objetivo P06 inválido")

    cursos = preparar_cursos(matriz)
    trajetoria = np.asarray(calcular_nota_trajetoria(perfil, cursos), dtype=float)
    pop = np.asarray(popularidade, dtype=float)
    permitido = _cursos_elegiveis(matriz)
    restritos = _cursos_restritos(matriz)
    assuntos = list(dict.fromkeys(perfil.get("interesses", {}).get("assuntos", [])))

    if not assuntos:
        return _recomendar_sem_assuntos(objetivo, matriz, ids, permitido, restritos, pop,
                                        trajetoria, semelhanca_conteudo, semelhanca_matriculas)

    # Mudança de área: tirar cursos ligados só à profissão anterior.
    if objetivo == "D":
        permitido = permitido & ~_excluir_profissao_anterior(perfil, cursos)
    elegiveis = np.flatnonzero(permitido)

    # --- Notas -------------------------------------------------------
    topicos = _notas_por_assunto(assuntos, cursos, permitido)
    assuntos_atendidos = np.sum([t["mask"] for t in topicos], axis=0)
    nota_interesses = np.maximum.reduce([t["valores"] for t in topicos])
    nota_interesses = np.minimum(
        1.0, nota_interesses + BONUS_VARIOS_ASSUNTOS * np.maximum(0.0, assuntos_atendidos - 1)
    )
    similaridade = similaridade_hibrida(np.maximum(nota_interesses, 0.0), semelhanca_conteudo,
                                        semelhanca_matriculas, pop)
    peso_interesses, peso_trajetoria, peso_similaridade = PESOS_POR_OBJETIVO[objetivo]
    if not np.any(trajetoria):
        # Sem experiência nem formação, o peso da trajetória passa para os interesses.
        peso_interesses += peso_trajetoria
        peso_trajetoria = 0.0
    notas = (peso_interesses * nota_interesses + peso_trajetoria * trajetoria
             + peso_similaridade * similaridade)

    # --- Contexto para a ordenação -------------------------------------
    # Áreas mais frequentes entre os cursos ligados aos assuntos escolhidos.
    contagem_areas = Counter()
    for topico in topicos:
        for i in np.flatnonzero(topico["mask"] & permitido):
            contagem_areas[cursos["area_principal"][i]] += 1
    areas_alvo = {area for area, _ in contagem_areas.most_common(3)}

    # Área dominante de um assunto (>= 65% dos seus cursos, com pelo menos 5).
    areas_dominantes = set()
    for topico in topicos:
        achados = np.flatnonzero(topico["mask"] & permitido)
        if len(achados) >= 5:
            area, quantidade = Counter(cursos["area_principal"][i] for i in achados).most_common(1)[0]
            if quantidade / len(achados) >= 0.65:
                areas_dominantes.add(area)

    ligados_aos_assuntos = set(np.flatnonzero((nota_interesses > 0) & permitido))

    def fora_da_area_dominante(i):
        return cursos["area_principal"][i] not in areas_dominantes

    # --- Seleção -----------------------------------------------------
    lista = _Lista(matriz, permitido)

    # (a) Pelo menos um curso para cada assunto escolhido.
    for topico in topicos:
        def ordem_do_assunto(i, valores=topico["valores"]):
            # Para quem busca o primeiro emprego (A), títulos introdutórios desempatam.
            nao_introdutorio = (
                not any(p in normalizar_texto(lista.titulos[i])
                        for p in ("aprendendo", "basico", "fundamentos"))
                if objetivo == "A" else False
            )
            return (fora_da_area_dominante(i), nao_introdutorio,
                    -_nota_com_preferencia(valores[i], restritos[i]),
                    -_nota_com_preferencia(notas[i], restritos[i]),
                    -pop[i], int(ids[i]))

        for i in sorted(np.flatnonzero(topico["mask"] & permitido), key=ordem_do_assunto):
            if lista.adicionar(int(i)):
                break

    # (b) Demais vagas: cursos ligados aos assuntos, pela nota final.
    ordem_geral = sorted(elegiveis, key=lambda i: (
        fora_da_area_dominante(i) if nota_interesses[i] > 0 else True,
        -_nota_com_preferencia(notas[i], restritos[i]),
        -nota_interesses[i], -pop[i], int(ids[i]),
    ))
    for i in ordem_geral:
        if i in ligados_aos_assuntos:
            lista.adicionar(int(i))
        if lista.cheia():
            break

    # (c) Se ainda faltar curso: vizinhos de conteúdo dos assuntos (e não
    # qualquer curso da mesma área - ex.: Python não implica Excel).
    if not lista.cheia():
        frequencia = Counter()
        for i in ligados_aos_assuntos:
            frequencia.update(_prefixos_de_conteudo(cursos, i))
        minimo = max(1, len(ligados_aos_assuntos) // 4)
        prefixos_referencia = {p for p, f in frequencia.items() if f >= minimo}

        def ordem_complementar(i):
            da_area = cursos["area_principal"][i] in areas_alvo
            vizinhanca = len(_prefixos_de_conteudo(cursos, i) & prefixos_referencia)
            nota = (0.42 * min(vizinhanca / 2, 1.0) + 0.24 * float(da_area)
                    + 0.24 * similaridade[i] + 0.10 * trajetoria[i])
            return (-_nota_com_preferencia(nota, restritos[i]), not da_area, -pop[i], int(ids[i]))

        restantes = [i for i in elegiveis if i not in ligados_aos_assuntos]
        for i in sorted(restantes, key=ordem_complementar):
            lista.adicionar(int(i))
            if lista.cheia():
                break

    return _resposta(objetivo, matriz, ids, lista.indices, notas, "prioridade aos assuntos escolhidos")


def _recomendar_sem_assuntos(objetivo, matriz, ids, permitido, restritos, pop, trajetoria,
                             semelhanca_conteudo, semelhanca_matriculas):
    """P05 = 'Ainda não sei': o objetivo não altera os pesos.

    Com trajetória: 50% trajetória + 50% similaridade entre cursos.
    Sem trajetória: popularidade histórica (baseline).
    """
    elegiveis = np.flatnonzero(permitido)
    if not np.any(trajetoria):
        popularidade_normalizada = _normalizar_pelo_maximo(pop)
        ordem = sorted(elegiveis, key=lambda i: (
            -_nota_com_preferencia(popularidade_normalizada[i], restritos[i]), -pop[i], int(ids[i])
        ))
        motivo, notas = "popularidade histórica da EV.G", pop
    else:
        similaridade = similaridade_hibrida(trajetoria, semelhanca_conteudo, semelhanca_matriculas, pop)
        notas = (PESO_TRAJETORIA_SEM_ASSUNTOS * trajetoria
                 + (1 - PESO_TRAJETORIA_SEM_ASSUNTOS) * similaridade)
        ordem = sorted(elegiveis, key=lambda i: (
            -_nota_com_preferencia(notas[i], restritos[i]), -pop[i], int(ids[i])
        ))
        motivo = "conhecimento e experiência informados"

    # Aqui só se evita repetir a mesma família de títulos.
    titulos = matriz["nome_curso"].tolist()
    selecionados = []
    for i in ordem:
        if not any(_mesma_familia(titulos[i], titulos[j]) for j in selecionados):
            selecionados.append(i)
        if len(selecionados) == QUANTIDADE_RECOMENDACOES:
            break
    return _resposta(objetivo, matriz, ids, selecionados, notas, motivo)


def _resposta(objetivo, matriz, ids, selecionados, notas, motivo):
    cursos = []
    for i in selecionados:
        linha = matriz.iloc[i]
        cursos.append({
            "id_curso_canonico": int(ids[i]),
            "nome_curso": str(linha["nome_curso"]),
            "area_principal": str(linha["area_principal"]),
            "nota": float(notas[i]),  # uso interno/testes; não é exibida ao participante
            "motivos": [motivo],
            "acesso_restrito": eh_verdadeiro(linha["acesso_restrito"]),
            "vinculo_exigido": str(linha["vinculo_exigido"]).strip(),
            "idioma": str(linha["idioma"]),
            "link_do_curso": str(linha["link_do_curso"]),
        })
    return {"objetivo": objetivo, "cursos": cursos, "quantidade": len(cursos)}
