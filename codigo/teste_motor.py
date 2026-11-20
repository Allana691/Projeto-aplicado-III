"""Teste rápido do motor de recomendação (não precisa do Streamlit).

Gera perfis aleatórios de questionário, válidos segundo as regras da
interface, e confere que o motor sempre devolve cinco cursos diferentes,
em português e com link da EV.G.

Execute na raiz do projeto:
    python codigo/teste_motor.py            # 300 perfis
    python codigo/teste_motor.py 1000       # outra quantidade
"""
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from motor_recomendador import (
    carregar_opcoes,
    corrigir_opcoes_p01,
    montar_perfil,
    recomendar_experimental,
    validar_perfil,
)

MODELO = Path(__file__).resolve().parent.parent / "arquivos_do_modelo"
SEM_P02 = {"primeiro", "estudo", "outra"}  # mesma regra da interface


def carregar():
    opcoes = corrigir_opcoes_p01(carregar_opcoes(MODELO / "opcoes_questionario.json"))
    matriz = pd.read_csv(MODELO / "matriz_cursos_resumida.csv").fillna("")
    arrays = [
        np.load(MODELO / nome, allow_pickle=False)
        for nome in (
            "ids_dos_cursos.npy",
            "semelhanca_por_conteudo.npy",
            "semelhanca_por_matriculas.npy",
            "popularidade_dos_cursos.npy",
        )
    ]
    return opcoes, matriz, arrays


def perfil_aleatorio(opcoes, sorteio):
    grupos = opcoes["grupos"]
    profissoes = [item["nome"] for g in grupos for item in g["experiencia"]]
    areas = sorted({a for g in grupos for a in g["areas_cursos"]})
    assuntos = sorted({a for g in grupos for a in g["assuntos_p05"]})

    situacao = sorteio.choice([x["codigo"] for x in opcoes["situacoes_p01"]])
    experiencia = [] if situacao in SEM_P02 else sorteio.sample(
        profissoes + [opcoes["opcao_experiencia_outras"]], sorteio.randint(0, 3)
    )
    formacao_opcao = sorteio.choice(["areas", "areas", "nenhuma", "privacidade"])
    formacao = sorteio.sample(areas, sorteio.randint(1, 3)) if formacao_opcao == "areas" else []
    nao_sei = sorteio.random() < 0.2
    interesses = [] if nao_sei else sorteio.sample(assuntos, sorteio.randint(1, 3))
    return {
        "situacao": situacao,
        "experiencia": experiencia,
        "formacao": formacao,
        "formacao_opcao": formacao_opcao,
        "interesses": interesses,
        "nao_sei": nao_sei,
        "objetivo": sorteio.choice([x["codigo"] for x in opcoes["objetivos_p06"]]),
    }


def main(quantidade=300):
    opcoes, matriz, arrays = carregar()
    sorteio = random.Random(42)
    problemas = []
    inicio = time.perf_counter()
    for _ in range(quantidade):
        respostas = perfil_aleatorio(opcoes, sorteio)
        try:
            perfil, objetivo, explorar = montar_perfil(respostas, opcoes)
            validar_perfil(perfil, opcoes)
            resultado = recomendar_experimental(
                perfil, objetivo, matriz, *arrays, explorar_novos_temas=explorar
            )
        except Exception as erro:  # registrar e seguir para o próximo perfil
            problemas.append((respostas, repr(erro)))
            continue
        cursos = resultado["cursos"]
        ids = [c["id_curso_canonico"] for c in cursos]
        if len(cursos) != 5 or len(set(ids)) != 5:
            problemas.append((respostas, f"{len(set(ids))} cursos distintos"))
        elif any(not c["link_do_curso"].startswith("https://") for c in cursos):
            problemas.append((respostas, "curso sem link válido"))
        elif any(c["idioma"] not in ("Português", "") for c in cursos):
            problemas.append((respostas, "curso fora do português"))
    tempo = (time.perf_counter() - inicio) / quantidade * 1000

    print(f"{quantidade} perfis testados, {tempo:.1f} ms por recomendação.")
    if problemas:
        print(f"{len(problemas)} problema(s) encontrado(s). Primeiros casos:")
        for respostas, motivo in problemas[:5]:
            print(" -", motivo, respostas)
        sys.exit(1)
    print("OK: todos os perfis receberam cinco cursos distintos, em português e com link.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
