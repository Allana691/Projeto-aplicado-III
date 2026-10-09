
# Sistema Híbrido de Recomendação de Cursos para Desenvolvimento Profissional

## Identificação

**Instituição:** Universidade Presbiteriana Mackenzie  
**Curso:** Banco de Dados – Análise, Mineração e Engenharia de Dados  
**Disciplina:** Projeto Aplicado III  
**Semestre:** 2º semestre de 2026

## Sobre o projeto

Este projeto tem como objetivo desenvolver e avaliar um sistema híbrido de recomendação de cursos gratuitos voltados ao desenvolvimento profissional, utilizando dados públicos da Escola Virtual de Governo (EV.G).

A proposta combina técnicas de recomendação baseada em conteúdo (*Content-Based Filtering*) e filtragem colaborativa (*Collaborative Filtering*) para identificar cursos potencialmente relevantes aos usuários.

O sistema busca facilitar a descoberta de oportunidades de capacitação, considerando características dos cursos e padrões de interação presentes no histórico de matrículas.

## Base de dados

Foram utilizadas duas fontes de dados disponibilizadas pela Escola Virtual de Governo (EV.G):

- **Catálogo de cursos:** informações e características dos cursos ofertados.
- **Histórico de matrículas:** registros de interações dos usuários com os cursos, incluindo informações sobre a situação das matrículas.

As bases passaram por procedimentos de preparação, padronização e integração para permitir a análise exploratória e o desenvolvimento dos modelos de recomendação.

## Abordagem metodológica

O desenvolvimento técnico contempla três abordagens:

1. **Recomendação baseada em conteúdo (Content-Based):** utiliza características dos cursos para identificar similaridades e gerar recomendações.

2. **Filtragem colaborativa (Collaborative Filtering):** explora padrões de interação dos usuários com os cursos para identificar relações e preferências.

3. **Sistema híbrido:** combina as duas abordagens para produzir recomendações personalizadas.

A avaliação utiliza uma divisão temporal dos dados em conjuntos de treinamento, validação e teste, buscando simular recomendações para interações futuras.

Entre as métricas utilizadas estão:

- **Recall@10:** proporção de itens relevantes recuperados entre as recomendações.
- **Hit Rate@10:** proporção de usuários para os quais pelo menos um item relevante aparece entre as recomendações.
- **NDCG@10:** avalia a qualidade da ordenação das recomendações, considerando a posição dos itens relevantes.

Também está prevista a comparação com um modelo de referência baseado na popularidade dos cursos (*baseline de popularidade*).

## Objetivo extensionista

O projeto prevê a aplicação do sistema junto à comunidade, permitindo que participantes recebam recomendações de cursos gratuitos de acordo com seus interesses, conhecimentos prévios e objetivos profissionais.

Para essa etapa, está sendo planejada uma aplicação web com:

- Questionário para identificação do perfil e dos interesses dos participantes;
- Geração de recomendações personalizadas de cursos;
- Apresentação de informações e links para os cursos recomendados;
- Coleta de avaliações sobre a relevância e a utilidade das recomendações.

A proposta está relacionada aos Objetivos de Desenvolvimento Sustentável (ODS) da Organização das Nações Unidas (ONU):

- **ODS 4 – Educação de Qualidade**
- **ODS 8 – Trabalho Decente e Crescimento Econômico**

A aplicação busca contribuir para a democratização do acesso à capacitação gratuita e para o desenvolvimento de competências profissionais.

## Organização do repositório

O repositório reúne os arquivos acadêmicos e técnicos produzidos durante o desenvolvimento do projeto.

- **`documentacao/`** – Documentos das etapas acadêmicas, cronograma e registros do projeto.
- **`codigo/`** – Notebooks e códigos utilizados na preparação dos dados, análise exploratória e desenvolvimento dos modelos.
- **`dados/`** – Arquivos e informações relacionados às bases utilizadas.
- **`apresentacoes/`** – Materiais utilizados nas apresentações de acompanhamento.

Os diretórios poderão ser atualizados conforme o avanço das etapas.

## Integrantes

- Allana Rayssa Vieira de Oliveira
- Erika Cristina Alves Benesi Gomes
- Nicole Fernandes Moreira
- Tawany Nascimento Santos

## Status do projeto

🚧 **Projeto em desenvolvimento – 2º semestre de 2026.**

### Etapas acadêmicas

- **Etapa 1 – Concepção do projeto:** concluída.
- **Etapa 2 – Fundamentação teórica:** concluída e avaliada com nota máxima, sem necessidade de correções.
- **Etapa 3 – Metodologia:** em desenvolvimento.
- **Etapa 4 – Aplicação extensionista e finalização:** planejada.

### Desenvolvimento técnico

- [x] Identificação e integração das bases da EV.G.
- [x] Preparação e análise exploratória dos dados.
- [x] Implementação da recomendação baseada em conteúdo.
- [x] Implementação da filtragem colaborativa.
- [x] Implementação do sistema híbrido.
- [x] Divisão temporal em treinamento, validação e teste.
- [x] Avaliação inicial com Recall@10, Hit Rate@10 e NDCG@10.
- [ ] Comparação com baseline de popularidade.
- [ ] Consolidação da metodologia acadêmica.
- [ ] Desenvolvimento da aplicação web extensionista.
- [ ] Aplicação junto à comunidade e análise do feedback.
- [ ] Finalização e entrega do projeto.
