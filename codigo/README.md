# Código

A pasta tem duas partes:

1. **Pesquisa (notebooks Jupyter)**: preparação dos dados, análise exploratória e avaliação com dados históricos
   dos modelos. As tabelas do relatório saem daqui.
2. **Aplicação (programas `.py`)**: o aplicativo web da etapa extensionista.

## 1. Notebooks

Os notebooks seguem uma ordem, e cada um usa os arquivos gerados pela etapa anterior. O relatório
cita as seções do notebook 03 (por exemplo, "seções 7.7 e 7.8"), por isso a numeração das seções
foi mantida.

| Ordem | Notebook | O que faz |
|---|---|---|
| 1 | `01_preparacao_de_dados.ipynb` | Lê a base original de matrículas e o catálogo, integra os dois pelos títulos normalizados, cria o `id_curso_canonico` e gera `dados/processados/*.parquet`. |
| 2 | `02_analise_exploratoria.ipynb` | Análise exploratória das interações e do catálogo. |
| 3 | `03_modelo_recomendacao.ipynb` | Feedback implícito (matrícula como sinal de interesse), divisão temporal (treino ≤ 2024, validação 2025, teste 2026), modelo baseado em conteúdo, filtragem colaborativa baseada em itens, escolha de α (seção 6) e avaliação final com a popularidade como referência (seção 7). |

**Como executar**

- Instale as dependências com `pip install -r requirements-notebooks.txt`, a partir da raiz.
- Os notebooks 02 e 03 precisam apenas de `dados/processados/`, baixados com o Git LFS.
- O notebook 01 precisa das bases originais, que não estão no repositório porque têm cerca de 9 GB:
  1. baixe `catalogo.csv` e `20260902_escolavirtual_dadosabertos_matriculas_utf8.csv` pelos links
     de [`dados/README.md`](../dados/README.md);
  2. coloque os dois numa pasta chamada `data set`, **uma pasta acima** do repositório, ou ajuste
     `pasta_dados_originais` na seção 2 do notebook;
  3. execute com `codigo/` como pasta de trabalho.

## 2. Aplicação

```
questionário (streamlit_app.py)
      │  respostas P01–P06
      ▼
motor_recomendador.py ──lê──► arquivos_do_modelo/  ◄──gera── preparar_arquivos_do_modelo.py
      │  5 cursos                                              (a partir de dados/processados/)
      ▼
tela de resultados ──registra──► registro_sheets.py ──► Google Sheets (privado)
```

| Arquivo | Responsabilidade |
|---|---|
| `streamlit_app.py` | Interface: tela inicial, questionário em etapas, lista de cinco cursos e avaliação opcional. |
| `estilo.css` | Fonte, cores, cartões e tema escuro, carregados pelo `streamlit_app.py`. |
| `motor_recomendador.py` | Valida as respostas, converte-as em perfil e escolhe os cinco cursos (notas de interesses, trajetória e similaridade; regras de diversidade). |
| `preparar_arquivos_do_modelo.py` | Refaz os cálculos do notebook 03 com todo o histórico e salva as matrizes em `arquivos_do_modelo/`. |
| `registro_sheets.py` | Grava respostas, recomendações e avaliações, anônimas, em três abas do Google Sheets. |
| `teste_motor.py` | Teste rápido: gera perfis aleatórios válidos e confere se o motor sempre devolve cinco cursos distintos, em português e com link (`python codigo/teste_motor.py 1000`). |
| `resumo_aplicacao_comunidade.py` | Recalcula as Tabelas 6, 7 e 8 do relatório a partir dos registros em `dados/aplicacao_comunidade/`. |

### Como o motor escolhe os cinco cursos

Esta seção resume a seção 3.9 do relatório. Os parâmetros ficam no início de
`motor_recomendador.py`.

- **Interesses (P05).** Nota 1,00 se o curso ensina o assunto e 0,85 se o assunto aparece só como
  termo de apoio. Há um pequeno acréscimo quando o curso atende a mais de um assunto.
- **Trajetória (P02 e P04).** Nota 1,00 para a área principal e 0,40 para uma área complementar.
  A experiência vale 60% e a formação 40%.
- **Similaridade entre cursos.** É o modelo híbrido do experimento com dados históricos, com α = 0,55.
- **Pesos por objetivo (P06).** Seguem a Tabela 2 do relatório e estão em `PESOS_POR_OBJETIVO`.
  O questionário tem oito opções de objetivo; o relatório agrupa as que têm os mesmos pesos
  ("interesse pessoal" com "explorar assuntos" e "ainda não sei" com "prefiro não informar").
- **Sem assuntos ("Ainda não sei").** A lista usa 50% de trajetória e 50% de similaridade. Se a
  pessoa também não informou trajetória, a lista usa a popularidade histórica.
- **Seleção.** Entram só cursos em português e com link HTTPS. A lista garante pelo menos um curso
  por assunto e no máximo 2 módulos da mesma série. Cursos de acesso aberto são preferidos quando
  as notas são próximas.

Os códigos das perguntas seguem a especificação funcional (em `documentacao/`). A P03
("confirmação da situação profissional") não entrou na versão final, por isso não há P03 no app
nem na planilha de registros.

### Executar localmente

Na raiz do repositório:

```bash
pip install -r requirements.txt
streamlit run codigo/streamlit_app.py
```

### Registro no Google Sheets

O registro usa uma conta de serviço do Google. As credenciais ficam na área de credenciais do Streamlit
Cloud (*Secrets*) ou em `.streamlit/secrets.toml` para uso local. Esse arquivo **não deve** ir para o GitHub.

```toml
google_service_account_json = '''{ ... JSON da conta de serviço ... }'''
google_sheets_id = "ID da planilha"
```

A planilha precisa das abas `Respostas`, `Recomendacoes` e `Avaliacoes`; os cabeçalhos são
criados automaticamente. Sem as credenciais, as recomendações continuam funcionando e o app
apenas avisa que não conseguiu salvar.
