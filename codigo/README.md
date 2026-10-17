# Código

Esta pasta reúne os notebooks desenvolvidos na implementação do sistema híbrido de recomendação de cursos da Escola Virtual de Governo (EV.G).

Os notebooks seguem uma ordem: cada um usa os arquivos gerados pela etapa anterior.

## Notebooks

| Ordem | Notebook | O que faz |
|---|---|---|
| 1 | `01_preparacao_de_dados.ipynb` | Prepara os dados. Lê a base original de matrículas e o catálogo de cursos, integra os dois por títulos normalizados, cria o identificador canônico de curso (`id_curso_canonico`) e gera os arquivos processados em `dados/processados`. |
| 2 | `02_analise_exploratoria.ipynb` | Análise exploratória das interações e do catálogo, a partir dos arquivos processados. |
| 3 | `03_modelo_recomendacao.ipynb` | Modelagem e avaliação do sistema de recomendação, a partir dos arquivos processados. |

## Arquivos gerados pelo notebook 01

O notebook 01 salva dois arquivos em `dados/processados`:

- `interacoes_cursos_atuais.parquet`
- `catalogo_canonico.parquet`

A descrição de cada um está no README da pasta `dados`.

## Como executar

**Notebooks 02 e 03.** Precisam apenas dos arquivos que já estão em `dados/processados`. Não é necessário ter a base original.

**Notebook 01.** Precisa da base original, que não está no repositório por causa do tamanho (cerca de 9 GB). Para executá-lo:

1. Baixe os dois arquivos originais (links no README da pasta `dados`): `catalogo.csv` e `20260902_escolavirtual_dadosabertos_matriculas_utf8.csv`.
2. Coloque os dois em uma pasta chamada `data set`, localizada **uma pasta acima** do repositório.
3. Se a sua organização for diferente, ajuste a variável `pasta_dados_originais` na seção 2 do notebook.
4. Execute o notebook com a pasta `codigo` como pasta de trabalho, pois os caminhos são relativos a ela. O processamento pode demorar, porque o notebook lê toda a base de matrículas.

O notebook 01 utiliza as bibliotecas `pandas` e `duckdb`. As bibliotecas dos demais notebooks são importadas nas primeiras células de cada um.

## Arquivos grandes (Git LFS)

Os arquivos Parquet de `dados/processados` são armazenados com o **Git LFS**. Para baixá-los corretamente ao clonar o repositório, instale o Git LFS (`git lfs install`) antes de clonar ou de executar `git pull`. Sem ele, os arquivos aparecem como pequenos arquivos de texto, e os notebooks não conseguem lê-los.
