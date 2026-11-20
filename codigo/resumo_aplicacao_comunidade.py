"""Reproduz as Tabelas 6, 7 e 8 do relatório (seção 4.4.1) a partir dos registros da aplicação.

Os registros estão em dados/aplicacao_comunidade/. Por padrão, só entram as
participações do período de coleta (grupo = "coleta", 13 a 17/11/2026, em UTC).

Execute na raiz do repositório:
    python codigo/resumo_aplicacao_comunidade.py
    python codigo/resumo_aplicacao_comunidade.py --todos     # inclui todos os registros
"""
import sys
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).resolve().parent.parent / "dados" / "aplicacao_comunidade"
ESCALA = ["1 — Nada", "2 — Pouco", "3 — Parcialmente", "4 — Muito", "5 — Totalmente"]


def carregar(todos=False):
    tabelas = {nome: pd.read_csv(PASTA / f"{nome}.csv", dtype=str)
               for nome in ("respostas", "recomendacoes", "avaliacoes")}
    if not todos:
        tabelas = {nome: df[df["grupo"] == "coleta"] for nome, df in tabelas.items()}
    return tabelas["respostas"], tabelas["recomendacoes"], tabelas["avaliacoes"]


def main(todos=False):
    respostas, recomendacoes, avaliacoes = carregar(todos)
    n = len(respostas)
    interesse = recomendacoes["interesse_individual"].fillna("")
    manifestacoes = (interesse != "").sum()
    positivas = (interesse == "Me interessou").sum()

    print("Tabela 6 – Resumo da avaliação com participantes")
    print(f"  Participações registradas ............ {n}")
    print(f"  Recomendações apresentadas ........... {len(recomendacoes)}")
    print(f"  Cursos distintos recomendados ........ {recomendacoes['id_curso_canonico'].nunique()}")
    print(f"  Avaliações gerais preenchidas ........ {len(avaliacoes)} ({len(avaliacoes) / n:.1%})")
    print(f"  Avaliações individuais de cursos ..... {manifestacoes} ({manifestacoes / len(recomendacoes):.1%})")
    print(f"     'Me interessou' ................... {positivas} ({positivas / manifestacoes:.1%})")

    perguntas = {"avaliacao_p07": "Compatibilidade", "avaliacao_p09": "Utilidade"}
    print("\nTabela 7 – Distribuição das notas")
    print(f"  {'Nota':18s}" + "".join(f"{t:>17s}" for t in perguntas.values()))
    for nota in ESCALA:
        print(f"  {nota:18s}" + "".join(f"{(avaliacoes[c] == nota).sum():>17d}" for c in perguntas))

    print("\nTabela 8 – Estatísticas descritivas (respostas 'Não consigo avaliar' excluídas)")
    for coluna, titulo in perguntas.items():
        notas = pd.to_numeric(avaliacoes[coluna].str[0], errors="coerce").dropna()
        modas = " e ".join(str(int(m)) for m in notas.mode())
        print(f"  {titulo:16s} média {notas.mean():.2f} | mediana {notas.median():g} | moda {modas} | "
              f"desvio-padrão {notas.std():.2f} | variância {notas.var():.2f} | "
              f"mín. {notas.min():g} | máx. {notas.max():g} | 4 ou 5: {(notas >= 4).mean():.1%}")


if __name__ == "__main__":
    main(todos="--todos" in sys.argv)
