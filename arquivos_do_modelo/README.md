# Arquivos do modelo

Arquivos pré-calculados que o Recomendador carrega ao iniciar. Eles evitam
reprocessar a base de matrículas a cada acesso. Nenhum deles contém dados
de pessoas: são tabelas e matrizes sobre os cursos.

## Arquivos

| Arquivo | O que contém |
|---|---|
| `matriz_cursos_resumida.csv` | Tabela com os cursos do catálogo: nome, link, área principal, assuntos, idioma, indicação de acesso restrito etc. |
| `ids_dos_cursos.npy` | Lista com o identificador de cada curso, na ordem das linhas e colunas das matrizes. |
| `semelhanca_por_conteudo.npy` | Matriz curso × curso: quanto dois cursos se parecem pelo conteúdo. |
| `semelhanca_por_matriculas.npy` | Matriz curso × curso: quanto dois cursos costumam aparecer juntos nas matrículas da EV.G (calculada de forma agregada). |
| `popularidade_dos_cursos.npy` | Popularidade de cada curso, na mesma ordem de `ids_dos_cursos.npy`. Usada quando a pessoa não informa interesses nem trajetória. |
| `opcoes_questionario.json` | Opções do questionário: áreas, assuntos da P05, situações da P01 e objetivos da P06 (com o código usado pelo modelo). |
| `informacoes_do_modelo.json` | **[confirmar]** Metadados do modelo (versão, parâmetros, data de geração). |

## Atenção

- **Não renomeie** os arquivos: o aplicativo os procura pelo nome.
- **A ordem importa:** a linha *i* de cada matriz e do vetor de popularidade
  corresponde ao curso na posição *i* de `ids_dos_cursos.npy`. Se um desses
  arquivos for regenerado, todos devem ser regenerados juntos.
