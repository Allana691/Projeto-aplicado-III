"""
Gera as matrizes pré-calculadas que o aplicativo usa (pasta arquivos_do_modelo/).

O que este script faz:
  1. Lê os arquivos processados pelo notebook 01 (dados/processados/).
  2. Refaz os cálculos do notebook 03 com TODO o histórico disponível:
     TF-IDF + cosseno (conteúdo) e cosseno item-item (matrículas).
  3. Salva só os resultados, em arquivos pequenos, na pasta arquivos_do_modelo/.

O aplicativo nunca abre a base de matrículas: ele usa apenas esses arquivos.
Rode de novo só se a base de matrículas ou o catálogo mudarem.

Bibliotecas: duckdb, scipy e scikit-learn (requirements-notebooks.txt).

Como executar (de qualquer pasta, com o Git LFS instalado):
    python codigo/preparar_arquivos_do_modelo.py

Arquivos criados:
  ids_dos_cursos.npy             -> o ID de cada curso, na ordem das tabelas
  semelhanca_por_conteudo.npy    -> quanto cada curso se parece com os outros pelo CONTEÚDO
  semelhanca_por_matriculas.npy  -> quanto cada curso se liga aos outros pelas MATRÍCULAS
  popularidade_dos_cursos.npy    -> quantas pessoas diferentes se matricularam em cada curso
  informacoes_do_modelo.json     -> peso do conteúdo, data de corte e contagens
"""

import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------
# 1. CONFIGURAÇÕES (caminhos relativos à raiz do repositório)
# ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados" / "processados"
ARQUIVO_MATRICULAS = PASTA_DADOS / "interacoes_cursos_atuais.parquet"
ARQUIVO_CATALOGO = PASTA_DADOS / "catalogo_canonico.parquet"

PASTA_SAIDA = RAIZ / "arquivos_do_modelo"

# Só entram matrículas ANTES desta data.
# A base vai até 2 de setembro de 2026, então esta data usa tudo o que existe.
DATA_CORTE = "2026-09-03"

# α escolhido na validação de 2025 (notebook 03, seção 6.4). O app usa o
# mesmo valor em motor_recomendador.PESO_CONTEUDO; aqui ele só é registrado.
PESO_CONTEUDO = 0.55


def executar():
    PASTA_SAIDA.mkdir(exist_ok=True)
    conexao = duckdb.connect()

    # -----------------------------------------------------------
    # 2. CATÁLOGO: mesma ordem do notebook (ordenado pelo ID)
    # -----------------------------------------------------------
    print("Lendo o catálogo...")
    catalogo = conexao.execute(f"""
        SELECT
            id_curso_canonico,
            nome_curso,
            eixos_tematicos,
            competencias,
            apresentacao,
            publico_alvo,
            conteudo_programatico
        FROM read_parquet('{ARQUIVO_CATALOGO.as_posix()}')
        ORDER BY id_curso_canonico
    """).df()

    colunas_de_texto = [
        "nome_curso", "eixos_tematicos", "competencias",
        "apresentacao", "publico_alvo", "conteudo_programatico",
    ]
    catalogo[colunas_de_texto] = catalogo[colunas_de_texto].fillna("").astype(str)

    # Mesmos pesos do notebook: nome 3 vezes, eixos 2 vezes, o resto 1 vez
    catalogo["texto_combinado"] = (
        catalogo["nome_curso"] + " "
        + catalogo["nome_curso"] + " "
        + catalogo["nome_curso"] + " "
        + catalogo["eixos_tematicos"] + " "
        + catalogo["eixos_tematicos"] + " "
        + catalogo["competencias"] + " "
        + catalogo["apresentacao"] + " "
        + catalogo["publico_alvo"] + " "
        + catalogo["conteudo_programatico"]
    )

    ids_dos_cursos = catalogo["id_curso_canonico"].to_numpy()
    posicao_do_curso = {int(id_curso): posicao for posicao, id_curso in enumerate(ids_dos_cursos)}
    quantidade_de_cursos = len(catalogo)
    print(f"  {quantidade_de_cursos} cursos no catálogo.")

    # -----------------------------------------------------------
    # 3. SEMELHANÇA POR CONTEÚDO (Content-Based)
    #    Transforma o texto de cada curso em números (TF-IDF) e
    #    mede o quanto os cursos se parecem.
    # -----------------------------------------------------------
    print("Calculando a semelhança por conteúdo...")
    tfidf = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )
    matriz_de_textos = tfidf.fit_transform(catalogo["texto_combinado"])
    semelhanca_por_conteudo = cosine_similarity(matriz_de_textos).astype(np.float32)

    # -----------------------------------------------------------
    # 4. SEMELHANÇA POR MATRÍCULAS (Collaborative Filtering)
    #    Aqui é onde a base grande é lida.
    # -----------------------------------------------------------
    print("Lendo as matrículas (esta parte demora)...")
    inicio = time.time()
    pares = conexao.execute(f"""
        SELECT DISTINCT
            codigo_pessoa,
            id_curso_canonico
        FROM read_parquet('{ARQUIVO_MATRICULAS.as_posix()}')
        WHERE dt_matricula < DATE '{DATA_CORTE}'
    """).df()
    print(f"  {len(pares):,} pares pessoa-curso em {time.time() - inicio:.0f}s.")

    # Só usa cursos que existem no catálogo
    pares = pares[pares["id_curso_canonico"].isin(posicao_do_curso)]

    numero_da_pessoa, pessoas = pd.factorize(pares["codigo_pessoa"], sort=False)
    numero_do_curso = pares["id_curso_canonico"].map(posicao_do_curso).to_numpy()

    # Tabela pessoas x cursos: 1 onde a pessoa se matriculou no curso
    matriz_pessoa_curso = csr_matrix(
        (np.ones(len(pares), dtype=np.float32), (numero_da_pessoa, numero_do_curso)),
        shape=(len(pessoas), quantidade_de_cursos),
    )

    print("Calculando a semelhança por matrículas...")
    semelhanca_por_matriculas = cosine_similarity(
        matriz_pessoa_curso.T, dense_output=True
    ).astype(np.float32)
    np.fill_diagonal(semelhanca_por_matriculas, 0)

    # Popularidade: quantas pessoas diferentes se matricularam em cada curso
    popularidade_dos_cursos = np.asarray(matriz_pessoa_curso.sum(axis=0)).ravel().astype(np.int32)

    # -----------------------------------------------------------
    # 5. SALVAR (só arquivos pequenos)
    # -----------------------------------------------------------
    print("Salvando...")
    np.save(PASTA_SAIDA / "ids_dos_cursos.npy", ids_dos_cursos)
    np.save(PASTA_SAIDA / "semelhanca_por_conteudo.npy", semelhanca_por_conteudo)
    np.save(PASTA_SAIDA / "semelhanca_por_matriculas.npy", semelhanca_por_matriculas)
    np.save(PASTA_SAIDA / "popularidade_dos_cursos.npy", popularidade_dos_cursos)

    with open(PASTA_SAIDA / "informacoes_do_modelo.json", "w", encoding="utf-8") as arquivo:
        json.dump(
            {
                "peso_conteudo": PESO_CONTEUDO,
                "data_de_corte": DATA_CORTE,
                "quantidade_de_cursos": int(quantidade_de_cursos),
                "quantidade_de_pessoas_no_treino": int(len(pessoas)),
                "quantidade_de_pares_pessoa_curso": int(len(pares)),
            },
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    for arquivo in sorted(PASTA_SAIDA.iterdir()):
        print(f"  {arquivo.name}: {arquivo.stat().st_size / 1_000_000:.2f} MB")
    print("Pronto!")


if __name__ == "__main__":
    executar()
