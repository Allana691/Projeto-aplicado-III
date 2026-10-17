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

Contém as matrículas do histórico que puderam ser associadas a cursos do catálogo atual: **21.363.002 interações**, de **6.444.712 usuários**, em **1.030 cursos**. Todos os status de matrícula são preservados, e as interações repetidas entre um mesmo usuário e um mesmo curso não são consolidadas nesta etapa.

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
