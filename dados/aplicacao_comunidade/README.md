# Registros da aplicação na comunidade

Esta pasta guarda a cópia dos registros que o aplicativo gravou no Google Sheets durante a etapa
extensionista. Os registros são **anônimos**: cada lista de recomendações recebe um
`id_participacao` aleatório (UUID). O aplicativo não pede nome, e-mail, login ou CPF. Foram
retiradas da cópia duas colunas que estavam sempre vazias: `nome_opcional` e `avaliacao_p08`
(pergunta retirada).

| Arquivo | Uma linha por | Colunas principais |
|---|---|---|
| `respostas.csv` | participação | respostas do questionário: `situacao_p01`, `experiencia_p02`, `formacao_p04`, `formacao_opcao_p04`, `interesses_p05`, `interesses_nao_sei_p05`, `objetivo_p06` |
| `recomendacoes.csv` | curso recomendado (5 por participação) | `posicao`, `id_curso_canonico`, `nome_curso`, `link_do_curso`, `interesse_individual` ("Me interessou" / "Não me interessou" / vazio) |
| `avaliacoes.csv` | avaliação geral enviada (opcional) | `avaliacao_p07` (compatibilidade com os interesses), `avaliacao_p09` (utilidade da lista), em escala de 1 a 5 |

Os três arquivos se ligam pelo `id_participacao`. As datas estão em UTC; no horário de Brasília,
a coleta começou na noite de 12/11.

## Coluna `grupo`

| Valor | Participações | Significado |
|---|---|---|
| `coleta` | 47 | Período de coleta analisado no relatório (13 a 17/11/2026, UTC). |
| `apos_coleta` | 3 | Acessos de 18 e 19/11, depois do fechamento da análise. |
| `teste_revisao` | 12 | Testes de revisão do aplicativo feitos em 20/11, depois da entrega. |

Os testes internos de 12 e 13/11, anteriores à coleta, foram retirados da planilha antes da
análise e estão em `documentacao/testes_internos/`.

## Reproduzir os resultados do relatório

```bash
python codigo/resumo_aplicacao_comunidade.py
```

O script recalcula as Tabelas 6, 7 e 8 da seção 4.4.1 do relatório. São 47 participações, 235
recomendações, 121 cursos distintos e 26 avaliações gerais, com médias de 3,58 para
compatibilidade e 3,77 para utilidade; das 88 opiniões individuais, 71,6% foram "Me interessou".
Com `--todos`, o cálculo inclui todos os registros.
