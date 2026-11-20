# Sistema Híbrido de Recomendação de Cursos para Desenvolvimento Profissional

Projeto Aplicado III · Universidade Presbiteriana Mackenzie
Curso de Banco de Dados – Análise, Mineração e Engenharia de Dados · 2º semestre de 2026

**Situação:** concluído. Relatório final entregue em 19/11/2026.

| | |
|---|---|
| 📄 Relatório final (Etapa 4) | [`documentacao/Etapa_4_Versao_Entregue.pdf`](documentacao/Etapa_4_Versao_Entregue.pdf) |
| 🌐 Aplicação web | <https://encontre-cursos-evg-projeto-mackenzie.streamlit.app> |
| 🎥 Vídeo (apresentação do projeto e aplicação na comunidade) | <https://www.youtube.com/watch?v=a5bN-BiBJ_0> |

## Sobre o projeto

Com centenas de cursos gratuitos disponíveis, escolher o que estudar virou um problema. O projeto
desenvolveu um **sistema híbrido de recomendação** para o catálogo da **Escola Virtual de Governo
(EV.G/Enap)**. Ele combina:

- **Recomendação baseada em conteúdo (Content-Based):** TF-IDF sobre nome, eixos temáticos, competências,
  apresentação, público-alvo e conteúdo programático dos cursos, com similaridade do cosseno;
- **Filtragem colaborativa baseada em itens (item-based):** similaridade do cosseno entre cursos, calculada a partir de
  21,4 milhões de matrículas reais (feedback implícito binário: a matrícula indica interesse);
- **Combinação ponderada:** `S = α · conteúdo + (1 − α) · colaborativo`, com escores normalizados
  por usuário e **α = 0,55** escolhido na validação.

O sistema foi levado à comunidade em um aplicativo web. Nele, a pessoa responde a um questionário
de perfil e recebe cinco cursos da EV.G.

## Principais resultados

**Avaliação com dados históricos (offline).** A divisão foi temporal: treino até 2024, validação em 2025 e teste de
01/01 a 02/09/2026. O teste avaliou 617.448 usuários com histórico prévio:

| Modelo | Recall@10 | Hit Rate@10 | NDCG@10 | Ganho de NDCG@10 sobre a referência |
|---|---|---|---|---|
| Popularidade (referência, ou baseline) | 0,0830 | 0,1481 | 0,0515 | — |
| Baseado em conteúdo | 0,0957 | 0,1649 | 0,0655 | +27,3% |
| Filtragem colaborativa | 0,1139 | 0,1893 | 0,0761 | +47,9% |
| **Híbrido (α = 0,55)** | **0,1151** | **0,1914** | **0,0780** | **+51,6%** |

A diferença entre o híbrido e o colaborativo é pequena e não passou por teste de significância
estatística (ver seção 4.2.1 do relatório).

**Aplicação na comunidade (13 a 17/11/2026).** Foram 47 participações, 235 recomendações e
26 avaliações gerais. Na escala de 1 a 5, a utilidade da lista teve média de **3,77** (61,5% deram
nota 4 ou 5) e a compatibilidade com os interesses, média de **3,58**. Das 88 avaliações individuais
de cursos, **71,6%** foram "Me interessou". A amostra é voluntária e não probabilística. Os registros anônimos estão em
[`dados/aplicacao_comunidade/`](dados/aplicacao_comunidade/README.md), e
`python codigo/resumo_aplicacao_comunidade.py` reproduz essas tabelas.

## Estrutura do repositório

```
├── codigo/                  notebooks da pesquisa e código do aplicativo
│   ├── 01_preparacao_de_dados.ipynb      integração catálogo × matrículas (ID canônico)
│   ├── 02_analise_exploratoria.ipynb     análise exploratória
│   ├── 03_modelo_recomendacao.ipynb      modelos, divisão temporal, α e avaliação com dados históricos
│   ├── preparar_arquivos_do_modelo.py    gera as matrizes usadas pelo app
│   ├── motor_recomendador.py             regras de recomendação do app (questionário → 5 cursos)
│   ├── streamlit_app.py                  interface web
│   ├── estilo.css                        identidade visual do app
│   ├── registro_sheets.py                registro anônimo das participações (Google Sheets)
│   ├── teste_motor.py                    teste rápido do motor com perfis aleatórios
│   └── resumo_aplicacao_comunidade.py    recalcula as tabelas da aplicação na comunidade
├── arquivos_do_modelo/      matrizes pré-calculadas e opções do questionário (lidas pelo app)
├── dados/                   bases processadas (Parquet via Git LFS), classificação do catálogo
│                            e registros anônimos da aplicação na comunidade
├── documentacao/            documentos das Etapas 1 a 4, especificações, cronograma e testes internos
├── apresentacoes/           slides de acompanhamento
├── .streamlit/config.toml   tema do aplicativo
├── requirements.txt         dependências do aplicativo (usadas pelo Streamlit Cloud)
└── requirements-notebooks.txt  dependências para reproduzir os notebooks
```

Cada pasta tem um README com mais detalhes.

## Como reproduzir

**Requisitos:** Python 3.11 ou superior e [Git LFS](https://git-lfs.com). O Git LFS é
necessário para baixar os arquivos Parquet.

```bash
git lfs install
git clone https://github.com/Allana691/Projeto-aplicado-III.git
cd Projeto-aplicado-III
```

**Executar o aplicativo localmente**

```bash
pip install -r requirements.txt
streamlit run codigo/streamlit_app.py
```

As recomendações funcionam sem configuração extra. O registro na planilha só funciona com as
credenciais do Google na área de credenciais do Streamlit (*Secrets*); veja [`codigo/README.md`](codigo/README.md).
Sem elas, o app avisa que não conseguiu salvar e continua funcionando.

**Reproduzir a pesquisa**

```bash
pip install -r requirements-notebooks.txt
```

1. `01_preparacao_de_dados.ipynb`: só é necessário para refazer a integração e exige as bases
   originais de cerca de 9 GB (veja [`dados/README.md`](dados/README.md)). Os arquivos que ele gera já
   estão em `dados/processados/`.
2. `02_analise_exploratoria.ipynb` e `03_modelo_recomendacao.ipynb`: rodam a partir de
   `dados/processados/`.
3. `python codigo/preparar_arquivos_do_modelo.py`: recalcula as matrizes do app em
   `arquivos_do_modelo/`.

## Dados e privacidade

Os dados vêm de fontes públicas da EV.G: o catálogo de cursos e o portal *EV.G em Números*. Em
linha com a LGPD (Lei nº 13.709/2018), o projeto **não usa atributos pessoais** da base de
matrículas, como sexo e idade, e as matrizes publicadas descrevem apenas relações entre cursos.
O aplicativo não pede nome, e-mail, login ou CPF e não consulta o histórico do participante na EV.G.
As respostas são registradas de forma anônima, ligadas a um identificador aleatório, numa planilha
privada do projeto.

## Equipe

- Allana Rayssa Vieira de Oliveira
- Erika Cristina Alves Benesi Gomes
- Nicole Fernandes Moreira
- Tawany Nascimento Santos

O aplicativo é um protótipo acadêmico independente, sem vínculo oficial com a EV.G ou a Enap.
