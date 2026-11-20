# Dados

Esta pasta reúne informações e arquivos relacionados às bases de dados utilizadas no desenvolvimento do sistema de recomendação.

## Fontes de dados

O projeto utiliza dados públicos da Escola Virtual de Governo (EV.G), mantida pela Escola Nacional de Administração Pública (Enap).

### 1. Catálogo de cursos da EV.G

O catálogo contém informações sobre os cursos disponibilizados pela plataforma, incluindo características que são utilizadas na abordagem baseada em conteúdo do sistema de recomendação.

- Arquivo utilizado: `catalogo.csv`
- Fonte: Escola Virtual de Governo (EV.G)
- https://www.escolavirtual.gov.br/catalogo

### 2. Base de matrículas da EV.G

A base contém dados relativos às matrículas realizadas na Escola Virtual de Governo (EV.G), incluindo informações sobre usuários, cursos e situação das matrículas. Esses dados são utilizados para analisar o comportamento dos usuários e apoiar o desenvolvimento do sistema de recomendação.

- Arquivo utilizado: `20260902_escolavirtual_dadosabertos_matriculas_utf8.csv`
- Fonte: EV.G em Números – Dados Abertos
- https://emnumeros.escolavirtual.gov.br/dados-abertos/

## Armazenamento dos dados

Devido ao grande volume dos dados originais, especialmente da base histórica de matrículas (cerca de 9 GB), os arquivos originais **não** são armazenados neste repositório. Para executar o notebook de preparação, eles devem ser baixados pelos links acima.

Os arquivos derivados, gerados pelo notebook `codigo/01_preparacao_de_dados.ipynb`, ficam na pasta `processados`.

Os arquivos Parquet são armazenados com o **Git LFS**. Para baixá-los corretamente, instale o Git LFS (`git lfs install`) antes de clonar o repositório ou de executar `git pull`.

## Arquivos processados (`processados/`)

### `interacoes_cursos_atuais.parquet`

Contém as matrículas do histórico que puderam ser associadas a cursos do catálogo atual: **21.363.002 interações**, de **6.444.712 usuários**, em **1.030 cursos**. Todas as situações de matrícula são preservadas, e as interações repetidas entre um mesmo usuário e um mesmo curso não são consolidadas nesta etapa.

| Coluna | Descrição |
|---|---|
| `cod_matricula` | Identificador original da matrícula (não é uma chave única global) |
| `dt_matricula` | Data da matrícula |
| `cod_curso` | Código histórico do curso |
| `nome_curso` | Nome histórico do curso |
| `carga_horaria` | Carga horária |
| `dt_fim` | Data de término |
| `tematica` | Temática do curso |
| `sit_matricula` | Situação da matrícula |
| `codigo_pessoa` | Identificador do usuário |
| `id_curso_canonico` | Identificador interno do curso conceitual (1 a 1.030) |

Atributos pessoais (como sexo e idade) e atributos institucionais não foram incluídos nesta base.

### `catalogo_canonico.parquet`

Contém uma linha para cada curso canônico (**1.030 linhas**), com as características do catálogo usadas pelo componente baseado em conteúdo.

Colunas: `id_curso_canonico`, `id_curso`, `nome_curso`, `eixos_tematicos`, `competencias`, `certificador`, `conteudista`, `carga_horaria`, `disponibilidade_dias`, `tipo_oferta`, `apresentacao`, `publico_alvo`, `conteudo_programatico` e `data_lancamento`.

### O identificador canônico de curso

Alguns cursos aparecem no catálogo com mais de um `id_curso`, com títulos que diferem apenas na escrita (por exemplo, pontuação). Para que o sistema de recomendação não os trate como itens diferentes, esses registros foram agrupados em um único curso, identificado por `id_curso_canonico`. Foram 11 grupos, e os 1.041 registros do catálogo resultaram em 1.030 cursos.

Os identificadores originais são preservados. Nos cursos que reúnem mais de um registro, os valores diferentes de um mesmo campo são combinados em um único texto, separados por ` | `.

A versão em espanhol do curso "Inteligência Emocional" (`id_curso` 627) é mantida como um curso distinto da versão em português (`id_curso` 318).

## Matriz preliminar de classificação do catálogo (`processados/matriz_classificacao_catalogo_EVG.xlsx`)

É a primeira versão da classificação temática dos 1.030 cursos canônicos. Ela foi gerada por regras
de palavras-chave sobre o nome, o eixo temático, a apresentação e o conteúdo programático, e
serviu de ponto de partida para organizar o catálogo e montar as perguntas do questionário.

A planilha tem cinco abas: `Matriz de cursos`, `Resumo por área`, `Áreas`, `Assuntos por área` e
`Leia-me`. A aba `Leia-me` explica cada campo. Entre as colunas estão o ID canônico e o ID EV.G,
o eixo original, as grandes áreas e assuntos candidatos, o público-alvo, o tipo de oferta, um
sinal de elegibilidade e a evidência textual que justifica a classificação.

Esta matriz tem caráter **preliminar**. Depois, a classificação foi revisada curso a curso por duas
integrantes do grupo (relatório, seção 3.9) e passou a ter 5 grandes áreas, 17 áreas e 37 assuntos.
A **versão final** está em `processados/classificacao_final_catalogo_EVG.xlsx` (abaixo), e a tabela
usada pelo aplicativo, em
[`arquivos_do_modelo/matriz_cursos_resumida.csv`](../arquivos_do_modelo/matriz_cursos_resumida.csv).
A matriz não substitui o `catalogo_canonico.parquet`, que continua sendo a referência do catálogo
para as análises e os modelos.

## Classificação final do catálogo (`processados/classificacao_final_catalogo_EVG.xlsx`)

Classificação usada pelo aplicativo, elaborada por Tawany. A área principal de cada curso é igual
à do `matriz_cursos_resumida.csv`.

- `Catálogo simplificado`: uma linha por curso (1.030), com área principal, até 3 áreas
  complementares, até 3 assuntos, idioma, link e indicação de acesso restrito.
- `Áreas do questionário`: as 17 áreas de curso, organizadas nas 5 grandes áreas.
- `Experiência profissional`: o nome exibido na P02 e as áreas do catálogo correspondentes.

## Assuntos da P05 (`processados/assuntos_P05_verificados.xlsx`)

- `Opções P05`: os 37 assuntos mostrados na P05, com o número de cursos em português e um exemplo
  de curso de cada um.
- `Vínculos com cursos`: os assuntos da P05 associados a cada um dos 1.030 cursos.

## Registros da aplicação na comunidade (`aplicacao_comunidade/`)

Cópia anônima das respostas, recomendações e avaliações registradas pelo aplicativo. O
[README da pasta](aplicacao_comunidade/README.md) descreve os arquivos e como reproduzir as
tabelas do relatório.
