# Testes internos do aplicativo

Esta pasta reúne os testes que o grupo fez antes de abrir o aplicativo à comunidade. Eles são a
base da afirmação do relatório (seção 3.9) de que os pesos "foram definidos pelo grupo e
verificados em testes internos com perfis simulados, sem validação estatística".

Todos os perfis são **simulados**; nenhum arquivo contém dados de participantes.

| Pasta / arquivo | Data | Conteúdo |
|---|---|---|
| `avaliacao_de_perfis/` | 07/11/2026 | Perfis simulados com as listas geradas pelo motor (`avaliacao_manual_perfis.csv`) e um relatório qualitativo por perfil (`relatorio_perfis_reais.txt`). |
| `comparacao_de_pesos/` | 07/11/2026 | Comparação entre o algoritmo da época e a versão com pesos experimentais: perfis testados (`perfis_testados.json`), cursos de cada lista (`comparacao_cursos.csv`) e métricas por perfil, como assuntos cobertos e diversidade de áreas (`resumo_metricas.csv`). |
| `testes_do_app_12-13nov.xlsx` | 12–13/11/2026 | Registros do aplicativo publicado durante o teste interno completo (19 participações), nas mesmas três abas da planilha da pesquisa. Foram retirados da base antes da análise da comunidade. |

Os testes de 07/11 foram feitos com versões anteriores do motor e da classificação do
catálogo. Por isso, os nomes de áreas e as listas podem ser diferentes dos da versão final.
