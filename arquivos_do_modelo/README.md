# Arquivos do modelo

Arquivos pré-calculados que o aplicativo carrega ao iniciar. Com eles, o app não precisa
processar as 21 milhões de matrículas a cada acesso. **Nenhum deles contém dados de pessoas:**
são tabelas e matrizes sobre os 1.030 cursos canônicos.

| Arquivo | Conteúdo | Gerado por |
|---|---|---|
| `ids_dos_cursos.npy` | `id_curso_canonico` de cada curso, na ordem das linhas e colunas das matrizes. | `codigo/preparar_arquivos_do_modelo.py` |
| `semelhanca_por_conteudo.npy` | Matriz curso × curso (1.030 × 1.030) de similaridade do cosseno entre os vetores TF-IDF. | idem |
| `semelhanca_por_matriculas.npy` | Matriz curso × curso de similaridade do cosseno entre as colunas da matriz binária usuário × curso (diagonal zerada). | idem |
| `popularidade_dos_cursos.npy` | Número de pessoas distintas matriculadas em cada curso. | idem |
| `informacoes_do_modelo.json` | Metadados da geração: α (`peso_conteudo` = 0,55), data de corte (2026-09-03, ou seja, todo o histórico), 1.030 cursos, 6.444.712 pessoas e 19.309.669 pares pessoa–curso distintos. | idem |
| `matriz_cursos_resumida.csv` | Uma linha por curso: nome, link, idioma, área principal, áreas complementares, assuntos, termos de apoio, acesso restrito e vínculo exigido. É a classificação do catálogo em 5 grandes áreas, 17 áreas e 37 assuntos (relatório, seção 3.9). | Elaborada por Tawany a partir da classificação do catálogo |
| `opcoes_questionario.json` | Opções do questionário: grupos, áreas, assuntos da P05, situações da P01 e objetivos da P06, com o código usado pelo motor (`codigo_modelo`). | _a confirmar_ |

## Atenção

- **Não renomeie** os arquivos: o aplicativo procura cada um pelo nome.
- **A ordem importa:** a linha *i* de cada matriz e do vetor de popularidade corresponde ao curso
  na posição *i* de `ids_dos_cursos.npy` e à linha *i* de `matriz_cursos_resumida.csv`. Se um
  deles for regenerado, todos devem ser regenerados juntos. O app confere esse alinhamento ao
  iniciar e para com um erro se algo não bater.
- As matrizes do app usam **todo o histórico** (até 02/09/2026). Já a avaliação offline do
  relatório usou cortes temporais, para evitar vazamento de dados.
