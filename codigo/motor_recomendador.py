"""Motor único do recomendador de cursos EV.G.

O questionário fornece o perfil. O modelo usa matrizes construídas
com o catálogo e as matrículas reais da EV.G.
Os pesos abaixo foram revisados em 07/11/2026 e são provisórios
até avaliação qualitativa com perfis.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict
import re
from collections import Counter


# --------------------------------------------------------------------
# 1. Afinidade entre perfil e catálogo
# --------------------------------------------------------------------

SEPARADOR = " | "


AJUSTES_PADRAO = {
    "peso_experiencia": 0.60,
    "peso_formacao": 0.40,
    "nota_area_principal": 1.00,
    "nota_area_complementar": 0.40,
    "bonus_assunto": 0.30,
    "afinidade_maxima": 1.00,
}


def carregar_ajustes(arquivo=None):
    """Lê o ajustes_da_recomendacao.json (se existir) por cima dos valores padrão."""
    ajustes = dict(AJUSTES_PADRAO)
    if arquivo is not None and Path(arquivo).exists():
        with open(arquivo, "r", encoding="utf-8") as f:
            ajustes.update(json.load(f))
    return ajustes


def normalizar_texto(texto):
    """Tira acentos, deixa em minúsculas e arruma os espaços: 'Gestão ' vira 'gestao'."""
    sem_acentos = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acentos.lower().split())


def separar_lista(texto):
    """Transforma 'A | B | C' em ['A', 'B', 'C']. Célula vazia vira lista vazia."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return []
    return [parte.strip() for parte in str(texto).split(SEPARADOR) if parte.strip()]


def carregar_matriz(arquivo_csv):
    """Lê o matriz_cursos_resumida.csv (gerado pelo preparar_matriz_resumida.py)."""
    matriz = pd.read_csv(arquivo_csv, encoding="utf-8")
    for coluna in ["area_principal", "areas_complementares", "assuntos"]:
        matriz[coluna] = matriz[coluna].fillna("").astype(str)
    if "termos_busca" not in matriz.columns:
        matriz["termos_busca"] = ""  # compatibilidade com o CSV anterior
    matriz["termos_busca"] = matriz["termos_busca"].fillna("").astype(str)
    return matriz


def preparar_cursos(matriz):
    """
    Organiza a matriz para consulta rápida (faz isso uma vez só).
    Cada lista abaixo tem um item por curso, na mesma ordem da matriz.
    """
    return {
        "ids": matriz["id_curso_canonico"].to_numpy(),
        "area_principal": [a.strip() for a in matriz["area_principal"]],
        "areas_complementares": [set(separar_lista(t)) for t in matriz["areas_complementares"]],
        "assuntos": [set(normalizar_texto(a) for a in separar_lista(t)) for t in matriz["assuntos"]],
        "termos_busca": [
            set(normalizar_texto(a) for a in separar_lista(t))
            for t in matriz["termos_busca"]
        ] if "termos_busca" in matriz.columns else [set() for _ in range(len(matriz))],
        "quantidade": len(matriz),
    }


def afinidade_por_areas(areas_escolhidas, cursos, ajustes):
    """
    Para cada curso: 1,00 se a área principal foi marcada; senão 0,40 se uma área
    complementar foi marcada; senão 0. Várias áreas marcadas: vale a maior nota.
    """
    escolhidas = set(areas_escolhidas)
    notas = np.zeros(cursos["quantidade"])
    if not escolhidas:
        return notas

    for posicao in range(cursos["quantidade"]):
        if cursos["area_principal"][posicao] in escolhidas:
            notas[posicao] = ajustes["nota_area_principal"]
        elif cursos["areas_complementares"][posicao] & escolhidas:
            notas[posicao] = ajustes["nota_area_complementar"]
    return notas


def bonus_por_assuntos(assuntos_escolhidos, cursos, ajustes):
    """+0,30 para cada curso que tem algum dos assuntos marcados (reforço, não filtro)."""
    correspondencias = correspondencia_por_assuntos(assuntos_escolhidos, cursos)
    return correspondencias.astype(float) * ajustes["bonus_assunto"]


def correspondencia_por_assuntos(assuntos_escolhidos, cursos):
    """Máscara booleana: curso contém assunto declarado (ou sinônimo revisado).

    É apenas um indicador de correspondência; não é nota, filtro nem prova de domínio.
    """
    escolhidos = set(normalizar_texto(a) for a in assuntos_escolhidos)
    resultado = np.zeros(cursos["quantidade"], dtype=bool)
    if not escolhidos:
        return resultado
    termos_adicionais = cursos.get("termos_busca")
    for posicao in range(cursos["quantidade"]):
        termos = cursos["assuntos"][posicao]
        if termos_adicionais is not None:
            termos = termos | termos_adicionais[posicao]
        resultado[posicao] = bool(termos & escolhidos)
    return resultado


def calcular_afinidade_dimensao(areas, cursos, ajustes, assuntos=()):
    """Nota por área + bônus de assunto, limitada a 1,00."""
    notas = afinidade_por_areas(areas, cursos, ajustes) + bonus_por_assuntos(assuntos, cursos, ajustes)
    return np.minimum(notas, ajustes["afinidade_maxima"])


def calcular_afinidades(perfil, cursos, ajustes):
    """
    Recebe o perfil da sessão, por exemplo:
        {
          "experiencia": {"areas": ["Tributário e Fiscal"]},
          "formacao":    {"areas": ["Planejamento e Gestão Pública"], "assuntos": ["Python"]},
          "interesses":  {"areas": ["Dados e Inteligência Artificial"], "assuntos": []},
        }
    e devolve as notas de afinidade (uma lista de 1.030 números para cada item):
        afinidade_experiencia, afinidade_formacao, afinidade_interesses, afinidade_base
    e também quais dimensões foram informadas (para saber o que NÃO foi respondido).
    """
    areas_experiencia = perfil.get("experiencia", {}).get("areas", [])
    areas_formacao = perfil.get("formacao", {}).get("areas", [])
    areas_interesses = perfil.get("interesses", {}).get("areas", [])
    assuntos_interesses = perfil.get("interesses", {}).get("assuntos", [])
    assuntos_formacao = perfil.get("formacao", {}).get("assuntos", [])

    informou_experiencia = len(areas_experiencia) > 0
    informou_formacao = len(areas_formacao) > 0 or len(assuntos_formacao) > 0
    informou_interesses = len(areas_interesses) > 0 or len(assuntos_interesses) > 0

    zeros = np.zeros(cursos["quantidade"])

    afinidade_experiencia = (
        calcular_afinidade_dimensao(areas_experiencia, cursos, ajustes)
        if informou_experiencia else zeros.copy()
    )
    afinidade_formacao = (
        calcular_afinidade_dimensao(areas_formacao, cursos, ajustes)
        if informou_formacao else zeros.copy()
    )
    afinidade_interesses = (
        calcular_afinidade_dimensao(areas_interesses, cursos, ajustes, assuntos_interesses)
        if informou_interesses else zeros.copy()
    )

    # Base = atuação (60%) + formação (40%). Se só uma foi informada, ela vale 100%.
    if informou_experiencia and informou_formacao:
        peso_experiencia = ajustes["peso_experiencia"]
        peso_formacao = ajustes["peso_formacao"]
        afinidade_base = (
            peso_experiencia * afinidade_experiencia + peso_formacao * afinidade_formacao
        ) / (peso_experiencia + peso_formacao)
    elif informou_experiencia:
        afinidade_base = afinidade_experiencia.copy()
    elif informou_formacao:
        afinidade_base = afinidade_formacao.copy()
    else:
        afinidade_base = zeros.copy()

    return {
        "afinidade_experiencia": afinidade_experiencia,
        "afinidade_formacao": afinidade_formacao,
        "afinidade_interesses": afinidade_interesses,
        "afinidade_base": afinidade_base,
        # Informação de contexto para a seleção final; não altera os pesos 60/40.
        "conhecimentos_previos": {
            "areas": list(areas_formacao),
            "assuntos": list(assuntos_formacao),
            "correspondencia_assuntos": correspondencia_por_assuntos(assuntos_formacao, cursos),
        },
        "informadas": {
            "experiencia": informou_experiencia,
            "formacao": informou_formacao,
            "base": informou_experiencia or informou_formacao,
            "interesses": informou_interesses,
        },
    }


# --------------------------------------------------------------------
# 2. Validação das respostas do questionário
# --------------------------------------------------------------------

def carregar_opcoes(caminho):
    with open(caminho, encoding='utf-8') as arquivo:
        return json.load(arquivo)


def chave(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(texto).casefold())
                            if not unicodedata.combining(c)).split())


def _unicos(valores, campo, erros):
    if not isinstance(valores, list):
        erros.append(f'{campo}: as escolhas devem estar em uma lista')
        return []
    if len(valores) != len(set(valores)):
        erros.append(f'{campo}: existem escolhas repetidas')
    return valores


def _catalogo_opcoes(opcoes):
    grupos = opcoes['grupos']
    profissionais = {item['nome']: item['areas_cursos']
                     for g in grupos for item in g['experiencia']}
    areas = {a for g in grupos for a in g['areas_cursos']}
    assuntos = {a for g in grupos for a in g['assuntos_p05']}
    return profissionais, areas, assuntos


def validar_respostas(respostas, opcoes):
    """Valida o que a pessoa marcou *na interface*, antes da tradução para áreas.

    formato: situacao, experiencia (nomes visíveis), formacao (áreas),
    formacao_opcao ('areas'|'nenhuma'|'privacidade'), interesses (assuntos),
    nao_sei (bool), objetivo.
    """
    profissionais, areas, assuntos = _catalogo_opcoes(opcoes)
    erros = []
    situacoes = {x['codigo'] for x in opcoes['situacoes_p01']}
    objetivos = {x['codigo'] for x in opcoes['objetivos_p06']}
    situacao = respostas.get('situacao')
    if situacao not in situacoes:
        erros.append('P01: selecione sua situação atual')
    objetivo = respostas.get('objetivo')
    if objetivo not in objetivos:
        erros.append('P06: selecione seu objetivo principal')
    exp = _unicos(respostas.get('experiencia', []), 'P02', erros)
    if len(exp) > opcoes['max_experiencia']:
        erros.append('P02: selecione no máximo 3 áreas profissionais')
    if situacao == 'primeiro' and exp:
        erros.append('P02: não deve ser respondida ao procurar o primeiro emprego')
    nomes_profissionais = set(profissionais) | {opcoes['opcao_experiencia_outras']}
    for item in exp:
        if item not in nomes_profissionais:
            erros.append(f'P02: opção desconhecida: {item}')
    formacao = _unicos(respostas.get('formacao', []), 'P04', erros)
    if len(formacao) > opcoes['max_formacao']:
        erros.append('P04: selecione no máximo 3 áreas de conhecimento')
    for item in formacao:
        if item not in areas:
            erros.append(f'P04: área desconhecida: {item}')
    modo_p04 = respostas.get('formacao_opcao', 'areas')
    if modo_p04 not in ('areas', 'nenhuma', 'privacidade'):
        erros.append('P04: opção geral inválida')
    if modo_p04 != 'areas' and formacao:
        erros.append('P04: opção geral não pode ser combinada com áreas')
    temas = _unicos(respostas.get('interesses', []), 'P05', erros)
    if len(temas) > opcoes['max_interesses']:
        erros.append('P05: selecione no máximo 3 assuntos')
    for t in temas:
        if t not in assuntos:
            erros.append(f'P05: assunto não disponível: {t}')
    nao_sei = respostas.get('nao_sei', False)
    if not isinstance(nao_sei, bool):
        erros.append('P05: Ainda não sei deve ser verdadeiro ou falso')
    elif nao_sei and temas:
        erros.append('P05: Ainda não sei não pode ser combinado com assuntos')
    elif not nao_sei and not temas:
        erros.append('P05: selecione um assunto ou marque Ainda não sei')
    if erros:
        raise ValueError('\n'.join(erros))
    return True


def montar_interesses_p05(assuntos=None, nao_sei=False):
    """Mantém o formato de interesses esperado pelo algoritmo existente."""
    return {'areas': [], 'assuntos': list(assuntos or []), 'nao_sei': bool(nao_sei)}


def montar_perfil(respostas, opcoes):
    """Converte labels simples para áreas técnicas, sem alterar a pontuação.

    Retorna (perfil, codigo_objetivo_antigo, explorar_novos_temas).
    """
    validar_respostas(respostas, opcoes)
    profissionais, _, _ = _catalogo_opcoes(opcoes)
    areas_exp = []
    if respostas['situacao'] != 'primeiro':
        for item in respostas['experiencia']:
            for area in profissionais.get(item, []):  # 'Outras áreas' não inventa uma área
                if area not in areas_exp:
                    areas_exp.append(area)
    perfil = {
        'experiencia': {'areas': areas_exp},
        'formacao': {'areas': list(respostas['formacao']) if respostas['formacao_opcao']=='areas' else [], 'assuntos': []},
        'interesses': montar_interesses_p05(respostas['interesses'], respostas['nao_sei']),
    }
    mapa = {x['codigo']: x['codigo_modelo'] for x in opcoes['objetivos_p06']}
    objetivo = mapa[respostas['objetivo']]
    if respostas['situacao'] == 'primeiro' and respostas['objetivo'] == 'emprego':
        objetivo = 'A'  # primeira oportunidade; compatibilidade com o modelo antigo
    return perfil, objetivo, respostas['nao_sei']


def validar_perfil(perfil, opcoes):
    """Valida também o perfil convertido, útil para testes sem interface."""
    _, areas, assuntos = _catalogo_opcoes(opcoes)
    erros = []
    for nome in ('experiencia','formacao','interesses'):
        resp = perfil.get(nome, {})
        if not isinstance(resp.get('areas',[]),list) or not isinstance(resp.get('assuntos',[]),list):
            erros.append(f'{nome}: áreas e assuntos devem ser listas')
            continue
        for area in resp.get('areas',[]):
            if area not in areas:
                erros.append(f'{nome}: área desconhecida: {area}')
    formacao = perfil.get('formacao',{})
    if len(formacao.get('areas',[]))>3 or formacao.get('assuntos',[]):
        erros.append('P04: no máximo 3 áreas, sem assuntos adicionais')
    inter = perfil.get('interesses',{})
    if inter.get('areas',[]) or len(inter.get('assuntos',[]))>3:
        erros.append('P05: selecione até 3 assuntos, sem marcar áreas')
    for assunto in inter.get('assuntos',[]):
        if assunto not in assuntos:
            erros.append(f'P05: assunto desconhecido: {assunto}')
    if inter.get('nao_sei', False) and inter.get('assuntos',[]):
        erros.append('P05: Ainda não sei não pode coexistir com assuntos')
    if not inter.get('nao_sei', False) and not inter.get('assuntos',[]):
        erros.append('P05: escolha assunto ou Ainda não sei')
    if erros:
        raise ValueError('\n'.join(erros))
    return True


# --------------------------------------------------------------------
# 3. Regras de navegação da primeira pergunta
# --------------------------------------------------------------------

SITUACOES_P01 = {
    'trabalho': 'Estou trabalhando',
    'trabalho_estudo': 'Trabalho e estudo',
    'estudo': 'Estou estudando',
    'primeiro': 'Estou procurando meu primeiro emprego',
    'oportunidade': 'Estou procurando uma nova oportunidade',
    'transicao': 'Quero mudar de área profissional',
    'outra': 'Outra situação / Prefiro não informar',
}


def corrigir_opcoes_p01(opcoes):
    """Atualiza apenas P01; preserva todo o restante do questionário."""
    atualizadas = dict(opcoes)
    atualizadas['situacoes_p01'] = [
        {'codigo': codigo, 'texto': texto}
        for codigo, texto in SITUACOES_P01.items()
    ]
    return atualizadas


def deve_exibir_p02(situacao):
    """Primeiro emprego pula P02; sem P01 selecionada, não a apresenta."""
    return situacao in SITUACOES_P01 and situacao != 'primeiro'


# --------------------------------------------------------------------
# 4. Relações reais entre cursos e matrículas
# --------------------------------------------------------------------

def _normalizar_vetor(vetor):
    vetor = np.nan_to_num(np.asarray(vetor, dtype=float), nan=0., posinf=0., neginf=0.)
    vetor = np.maximum(vetor, 0.)
    maior = float(vetor.max()) if vetor.size else 0.
    return vetor / maior if maior else np.zeros_like(vetor)


def _modelo(referencias, conteudo, matriculas, popularidade, peso_conteudo):
    """Referências ponderadas -> duas similaridades normalizadas -> híbrida.

    Não utiliza a diagonal do conteúdo, que representa o próprio curso.
    Sem histórico de matrículas, usa apenas conteúdo.
    """
    pesos = np.maximum(np.asarray(referencias, dtype=float), 0.)
    if not np.any(pesos):
        return np.zeros(len(pesos))
    sc = np.asarray(conteudo, dtype=float).copy()
    np.fill_diagonal(sc, 0.)
    c = _normalizar_vetor(pesos @ sc)
    m = _normalizar_vetor(pesos @ matriculas)
    h = peso_conteudo * c + (1 - peso_conteudo) * m
    h[np.asarray(popularidade) == 0] = c[np.asarray(popularidade) == 0]
    return np.clip(h, 0., 1.)


def _somente_profissao_antiga(perfil, cursos, matriz):
    """Regra P06=D: exclusão conservadora.

    Exclusivo significa: curso ligado a área P02, sem QUALQUER área fora de P02.
    Curso com áreas mistas é mantido. P05 explícita sobre a área/assunto do curso
    suspende a exclusão. P04 nunca é interpretada como profissão abandonada.
    """
    antigas = set(perfil.get('experiencia', {}).get('areas', []))
    interesses = perfil.get('interesses', {})
    novas = set(interesses.get('areas', []))
    assuntos = interesses.get('assuntos', [])
    assunto_explicito = correspondencia_por_assuntos(assuntos, cursos)
    excluidos = np.zeros(cursos['quantidade'], dtype=bool)
    if not antigas:
        return excluidos
    for i in range(cursos['quantidade']):
        todas = {cursos['area_principal'][i]} | cursos['areas_complementares'][i]
        todas.discard('')
        exclusivo = bool(todas) and bool(todas & antigas) and todas <= antigas
        excecao = bool(todas & novas) or bool(assunto_explicito[i])
        excluidos[i] = exclusivo and not excecao
    return excluidos


# --------------------------------------------------------------------
# 5. Pesos e seleção das recomendações
# --------------------------------------------------------------------

PESOS_POR_OBJETIVO = {
    'A': (.65, .20, .15), 'B': (.65, .20, .15),
    'C': (.60, .25, .15), 'D': (.80, .05, .15),
    'E': (.55, .30, .15), 'F': (.70, .15, .15),
    'G': (.70, .15, .15), 'H': (.60, .25, .15),
    'I': (.60, .25, .15),
}


def _sem_acentos(valor):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(valor).casefold())
                   if not unicodedata.combining(c))


def _titulo_limpo(valor):
    """Remove somente termos genéricos para evitar duplicatas quase idênticas."""
    palavras = re.findall(r'[a-z0-9]+', _sem_acentos(valor))
    irrelevantes = {'o','a','os','as','ao','aos','da','de','do','dos','das','para','em',
                    'introducao','basico','basica','fundamentos','conceitos','curso',
                    'usuario','municipal','estadual','federal'}
    return frozenset(x for x in palavras if x not in irrelevantes)


def _mesma_familia(nome1, nome2):
    a, b = _titulo_limpo(nome1), _titulo_limpo(nome2)
    if not a or not b:
        return False
    if a == b:
        return True
    # Variações de uma mesma série: "Transferências Discricionárias da União: ...".
    p1, p2 = str(nome1).split(':')[0], str(nome2).split(':')[0]
    prefixo = _titulo_limpo(p1)
    if ':' in str(nome1) and ':' in str(nome2) and len(prefixo)>=3 and prefixo == _titulo_limpo(p2):
        return True
    return False


def _familia_serie(titulo):
    """Identifica séries que não devem ocupar as cinco sugestões sozinhas."""
    t = _sem_acentos(titulo)
    if t.startswith('s2id -'):
        return 's2id'
    if 'programa - ' in t and t.lstrip().startswith('eixo '):
        return 'programa:'+t.rsplit('programa - ',1)[-1].strip()
    if t.startswith('introducao a ciencia de dados - modelos de '):
        return 'modelos_ciencia_dados'
    if t.startswith('transferencias discricionarias da uniao:'):
        return 'transferencias_discricionarias'
    return ''


def _dados_elegiveis(matriz):
    idioma = matriz['idioma'].astype(str).map(normalizar_texto)
    restrito = matriz['acesso_restrito'].astype(str).str.strip().str.lower().isin(('true','1','sim'))
    link = matriz['link_do_curso'].astype(str).str.startswith('https://')
    return (idioma.isin(('portugues','pt','pt-br','')) & ~restrito & link).to_numpy()


def recomendar_experimental(perfil, objetivo, matriz, ids_modelo, semelhanca_conteudo,
                              semelhanca_matriculas, popularidade,
                              incluir_outros_idiomas=False, explorar_novos_temas=False):
    """Retorna um resultado compatível com as cinco recomendações do Streamlit.

    Conserva filtros e popularidade como alternativa sem P05. Não grava histórico.
    """
    ids = np.asarray(ids_modelo)
    n = len(matriz)
    if (not np.array_equal(matriz['id_curso_canonico'].to_numpy(), ids)
            or np.shape(semelhanca_conteudo) != (n,n)
            or np.shape(semelhanca_matriculas) != (n,n)
            or len(popularidade) != n):
        raise ValueError('IDs/matrizes incompatíveis; não é seguro recomendar cursos.')
    obj = str(objetivo).upper()
    if obj not in PESOS_POR_OBJETIVO:
        raise ValueError('Objetivo P06 inválido')
    cursos = preparar_cursos(matriz)
    afin = calcular_afinidades(perfil, cursos, carregar_ajustes())
    base = np.asarray(afin['afinidade_base'], dtype=float)
    pop = np.asarray(popularidade, dtype=float)
    permitido = _dados_elegiveis(matriz)
    if incluir_outros_idiomas:
        # A opção é para ver versões de cursos ofertados; a lista principal
        # continua em português, conforme decisão do questionário.
        pass
    indices_elegiveis = np.flatnonzero(permitido)
    assuntos = list(dict.fromkeys(perfil.get('interesses',{}).get('assuntos', [])))
    if not assuntos:
        # Sem assuntos na P05, a P06 não define pesos.
        # Apenas sem P05 E sem trajetória usamos o baseline de popularidade.
        if not np.any(base):
            ordem = sorted(indices_elegiveis, key=lambda i: (-pop[i],int(ids[i])))
            motivo = 'popularidade histórica da EV.G'
            notas = pop
        else:
            sim = _modelo(base, semelhanca_conteudo, semelhanca_matriculas,pop,.55)
            notas = .50*base + .50*sim
            ordem = sorted(indices_elegiveis, key=lambda i: (-notas[i],-pop[i],int(ids[i])))
            motivo = 'conhecimento e experiência informados'
        selecionados = []
        for i in ordem:
            if not any(_mesma_familia(matriz.iloc[i]['nome_curso'],matriz.iloc[j]['nome_curso']) for j in selecionados):
                selecionados.append(i)
            if len(selecionados)==5:
                break
        return _resposta(obj, matriz, ids, selecionados, notas, motivo)

    # Mudança de carreira: não recomendar curso exclusivamente ligado à
    # profissão anterior, salvo interesse explicitamente declarado na P05.
    # Com P05 vazia, a regra acima de 50/50 não depende da P06.
    if obj == 'D':
        permitido = permitido & ~_somente_profissao_antiga(perfil, cursos, matriz)
        indices_elegiveis = np.flatnonzero(permitido)

    # Tópicos marcados na P05: separar assunto ensinado (forte) de termo auxiliar.
    topicos = []
    contagem = np.zeros(n)
    for assunto in assuntos:
        texto = normalizar_texto(assunto)
        forte = np.array([texto in c for c in cursos['assuntos']], dtype=bool)
        tag = np.array([texto in c for c in cursos['termos_busca']], dtype=bool)
        mask = forte | tag
        valores = np.where(forte, 1., np.where(tag, .85, 0.))
        # A área principal dominante do próprio assunto reforça a confiança,
        # mas não inventa correspondência para cursos sem assunto/tag.
        achados = np.flatnonzero(mask & permitido)
        if len(achados):
            areas = Counter(cursos['area_principal'][i] for i in achados)
            for i in achados:
                share = areas[cursos['area_principal'][i]]/len(achados)
                valores[i] = min(1., valores[i] + .10*share)
        topicos.append({'nome':assunto,'mask':mask,'valores':valores})
        contagem += mask.astype(int)
    afin_interesse = np.maximum.reduce([x['valores'] for x in topicos])
    afin_interesse = np.minimum(1., afin_interesse + .04*np.maximum(0.,contagem-1))
    referencias = np.maximum(afin_interesse, 0.)
    sim = _modelo(referencias, semelhanca_conteudo, semelhanca_matriculas, pop,.55)
    wi,wb,ws = PESOS_POR_OBJETIVO[obj]
    if not np.any(base):
        wi += wb  # Ausência de P02/P04 não é tratada como zero na nota.
        wb = 0.
    notas = wi*afin_interesse + wb*base + ws*sim
    # Área de apoio: inferida apenas dos cursos elegíveis vinculados à P05.
    # Evita deixar a formação anterior dominar o preenchimento das vagas.
    areas_contexto = Counter()
    for item in topicos:
        for i in np.flatnonzero(item['mask'] & permitido):
            areas_contexto[cursos['area_principal'][i]] += 1
    areas_alvo = {a for a, _ in areas_contexto.most_common(3)}
    # Quando um assunto aponta majoritariamente para uma área, preferir cursos
    # de área principal correspondente aos com apenas termo auxiliar.
    areas_dominantes = set()
    for item in topicos:
        achados = np.flatnonzero(item['mask'] & permitido)
        if len(achados) >= 5:
            distribuicao = Counter(cursos['area_principal'][i] for i in achados)
            dominante, qt = distribuicao.most_common(1)[0]
            if qt / len(achados) >= .65:
                areas_dominantes.add(dominante)
    candidatos_diretos = set(np.flatnonzero((afin_interesse>0) & permitido))

    # Nas vagas sem vínculo explícito, preferir conteúdo vizinho ao assunto,
    # e não qualquer curso da mesma área (ex.: Python não implica Excel).
    parar = {'gesta','publi','curso','dados','tecno','funda','forma','metod','digit',
             'servi','proje','aplic','feder','estud','anali','conhe','apren'}
    def palavras_conteudo(i):
        textos = list(cursos['assuntos'][i]) + list(cursos['termos_busca'][i])
        termos = set()
        for termo in textos:
            for palavra in re.findall(r'[a-z0-9]+', normalizar_texto(termo)):
                if len(palavra)>=5 and palavra[:5] not in parar:
                    termos.add(palavra[:5])
        return termos
    sementes = [i for i in candidatos_diretos]
    frequencias=Counter()
    for i in sementes:
        for palavra in palavras_conteudo(i):
            frequencias[palavra] += 1
    # Palavras recorrentes no conteúdo dos cursos relacionados à P05.
    palavras_referencia = {w for w,nf in frequencias.items() if nf>=max(1, len(sementes)//4)}

    def classificar(i):
        area = cursos['area_principal'][i]
        e_da_area = area in areas_alvo
        vizinhanca = len(palavras_conteudo(i) & palavras_referencia)
        # Um vínculo por conteúdo vale mais do que popularidade ou área sozinha.
        nota_rel = .42*min(vizinhanca/2,1.) + .24*float(e_da_area) + .24*sim[i]+.10*base[i]
        return (-nota_rel, not e_da_area, -pop[i],int(ids[i]))

    # Seleção com cobertura: pelo menos 1 candidato por assunto se disponível.
    ordem_geral = sorted(indices_elegiveis, key=lambda i:(
        cursos['area_principal'][i] not in areas_dominantes if afin_interesse[i] > 0 else True,
        -notas[i],-afin_interesse[i],-pop[i],int(ids[i])))
    selecionados=[]
    def adicionar(i):
        if len(selecionados) >= 5 or i in selecionados or not permitido[i]:
            return False
        if any(_mesma_familia(matriz.iloc[i]['nome_curso'],matriz.iloc[j]['nome_curso']) for j in selecionados):
            return False
        serie = _familia_serie(matriz.iloc[i]['nome_curso'])
        if serie:
            contagem_serie = sum(_familia_serie(matriz.iloc[j]['nome_curso']) == serie for j in selecionados)
            # Limite 2 módulos da mesma série. Para S2ID, limite 1, pois as
            # variantes municipais/federais/estaduais frequentemente se repetem.
            limite_serie = 1 if serie == 's2id' else 2
            if contagem_serie >= limite_serie:
                return False
        selecionados.append(i)
        return True
    for item in topicos:
        candidatos = sorted(np.flatnonzero(item['mask'] & permitido),
                            key=lambda i:(cursos['area_principal'][i] not in areas_dominantes,
                                          # Preferência apenas no desempate pedagógico
                                          # pelo título, sem alterar os pesos.
                                          (not any(p in normalizar_texto(matriz.iloc[i]['nome_curso'])
                                                   for p in ('aprendendo','basico','fundamentos')))
                                           if obj == 'A' else False,
                                          -item['valores'][i], -notas[i], -pop[i], int(ids[i])))
        for i in candidatos:
            if adicionar(int(i)):
                break
    # Prioridade absoluta da P05 quando existem candidatos com vínculo explícito.
    for i in ordem_geral:
        if i in candidatos_diretos:
            adicionar(int(i))
        if len(selecionados)>=5:
            break
    # Apenas quando os assuntos não têm 5 cursos distintos, preencher por
    # áreas relacionadas + similaridade; cursos não relacionados ficam por último.
    if len(selecionados) < 5:
        relacionados=[i for i in indices_elegiveis if i not in candidatos_diretos]
        for i in sorted(relacionados, key=classificar):
            adicionar(int(i))
            if len(selecionados)>=5:
                break
    return _resposta(obj, matriz, ids, selecionados, notas,
                    'prioridade aos assuntos escolhidos')


def _resposta(obj, matriz, ids, selecionados, notas, motivo):
    itens=[]
    for i in selecionados:
        linha=matriz.iloc[i]
        itens.append({
            'id_curso_canonico':int(ids[i]), 'nome_curso':str(linha['nome_curso']),
            'area_principal':str(linha['area_principal']),
            'nota':float(notas[i]), # somente para testes internos, não exibir ao usuário
            'motivos':[motivo], 'acesso_restrito':False,
            'idioma':str(linha['idioma']), 'link_do_curso':str(linha['link_do_curso']),
        })
    return {'objetivo':obj,'estrategia':'experimental','cursos':itens,
            'quantidade':len(itens),'secoes':[]}
