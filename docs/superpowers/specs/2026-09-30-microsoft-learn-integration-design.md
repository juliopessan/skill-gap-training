# Integração Microsoft Learn (catálogo + MCP) — Design

Data: 2026-09-30 · Estende: `2026-09-29-skill-gap-training-design.md`

## Objetivo

Recomendar cursos **e certificações reais** da Microsoft Learn, agrupados por nível (Básico, Intermediário,
Avançado), no lugar da lista manual de 26 cursos "não verificados". Nível, link e duração vêm da Microsoft;
o vínculo com as skills da taxonomia FY27 é regra nossa e aparece como tal.

## Decisões tomadas com o usuário

- **Abordagem:** catálogo oficial sincronizado no SQLite + MCP como busca complementar.
- **Mapeamento item → skill:** regras versionadas em YAML, aplicadas por código, com relatório para revisão.

## Fatos verificados em 2026-09-30

- `https://learn.microsoft.com/api/mcp` responde sem autenticação (protocolo 2025-03-26). Ferramentas de
  **documentação**: `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`. Os
  resultados são trechos de páginas, sem nível, tipo ou duração.
- `https://learn.microsoft.com/api/catalog/?type=courses,learningPaths,certifications,exams&locale=en-us`
  devolve: learningPaths 820, courses 143, certifications 152, exams 145. Campos úteis: `uid`, `title`,
  `levels` (beginner|intermediate|advanced), `products`, `roles`, `duration_in_minutes` (learning paths) ou
  `duration_in_hours` (cursos), `url`, `last_modified`; certificações têm `exams` e não têm `products`;
  exames têm `products` e `study_guide`.
- Produtos relevantes vistos: `microsoft-foundry`, `foundry-agent-service`, `foundry-tools`, `azure-openai`,
  `fabric`, `azure-databricks`, `ai-builder`. 65 learning paths casam com Foundry/Fabric/Databricks.
- A listagem `tools/list` do MCP exige sessão; o cliente deve executar `initialize` e enviar
  `notifications/initialized` antes (a verificar na implementação com teste ao vivo opcional).

## Componentes

### 1. `learn_catalog.py` — sincronização (código)

- Busca os quatro tipos no Catalog API (`locale` configurável, padrão `en-us`; timeout e limite de tamanho).
- Normaliza para `Course` com `kind` em `curso | trilha | certificação | exame`.
- **Nível:** beginner→1, intermediate→2, advanced→3. Vários níveis: vale o menor; a lista completa fica em
  `raw_levels`.
- **Duração:** minutos→horas (arredondadas para cima) só quando informada; senão `None`. Nunca estimada.
- **Certificação:** herda produtos dos exames ligados (`exams[].uid` → exame → `products`); os códigos dos
  exames ficam em `exam_codes`.
- Filtro por produtos permitidos (lista em `learn_mapping.yaml`).
- Link sem `WT.mc_id` e demais parâmetros de rastreio.
- Ids `learn:<uid>`; `verified=1`; `source="Microsoft Learn Catalog API"`; `synced_at`.
- Upsert apenas das linhas `learn:*`. Linhas manuais e edições nunca são tocadas. Item que sumiu do catálogo
  é marcado `retired`, não apagado, e deixa de ser recomendado.
- Sincronização atômica (transação): falha de rede não altera nada.
- CLI: `python -m skillgap.cli catalog sync-learn [--locale en-us]`.

### 2. `config/learn_mapping.yaml` — regras item → skill (código)

- Por skill da taxonomia: `products` (qualquer) e `keywords` (título/resumo, sem acento e sem caixa, com
  fronteira de palavra).
- Um item recebe todas as skills cujas regras casam (produto **e** palavra-chave, ou só palavra-chave forte
  quando marcada `strong`).
- Relatório em saída padrão e `--report arquivo.md`: casados por skill, itens descartados, **skills sem
  nenhum item**.
- Vínculo gravado em `course_skills` com `origin="rule"`.

### 3. Recomendador

- Pontuação inalterada (cobertura de gaps ponderada por severidade, `course.level >= atual`).
- Desempate: verificado primeiro, depois duração conhecida, depois menor duração, depois id.
- Certificações e exames entram na etapa do seu nível, com selo e códigos de exame.
- Cronograma por cadência inalterado; certificações/exames ficam ao fim da etapa, sem data derivada de horas.

### 4. `learn_mcp.py` — complemento via MCP

- Cliente mínimo JSON-RPC sobre HTTP (initialize → initialized → `tools/call`), respostas SSE ou JSON.
- Acionado só para skills em gap **sem nenhum item do catálogo** após a recomendação.
- A consulta é o nome da skill da taxonomia mais o nome do produto. **Nunca texto do CV.**
- Devolve `supplementary`: lista de `{title, url, excerpt, skill}` (máx. 3 por skill).
- Cache em SQLite (tabela `mcp_cache`, TTL 7 dias). Timeout curto; qualquer falha resulta em lista vazia e um
  aviso de estado (`mcp: unavailable`), nunca em erro para o usuário.
- Só aceita URLs `https://learn.microsoft.com/...`; qualquer outra é descartada.
- Desligável por configuração (`SKILLGAP_LEARN_MCP=0`).

### 5. API e modelos

- `Recommendation` ganha `kind` (já existe), `exam_codes`, `source`, `synced_at`, `match_origin`
  (`rule|manual`). `ProcessedCandidate` ganha `supplementary` e `learn_status`.
- Registros antigos continuam válidos: campos novos opcionais (`null`, nunca `false`).
- `GET /catalog/status`: contagem por tipo, última sincronização, itens `retired`.

### 6. Interface (Ledger)

- Cartão do item: tipo, nível, duração ("duração não informada" quando `null`), exames, link, origem
  "Microsoft Learn · sincronizado em <data>".
- Vínculo mostrado como "casado por regra" em tinta. Verde/terracota inalterados (verde só para citação
  localizada).
- Bloco "Leitura complementar" separado, com a nota "encontrado pela busca da Microsoft Learn; não é curso e
  não tem nível".
- Rodapé e README passam a dizer que o catálogo agora é oficial para os itens `learn:*`.

## Erros e privacidade

- Catálogo indisponível na sincronização: nada muda, código de saída ≠ 0, mensagem clara.
- Sem catálogo Learn sincronizado: o app funciona com os 26 itens manuais, como hoje.
- Só o nome de skills da taxonomia sai para a Microsoft; nenhum dado do candidato.

## Testes (sem rede)

- Fixture reduzida do catálogo (cursos, paths, certificação com exames, item fora dos produtos, item sem
  duração, vários níveis).
- Normalização de nível/duração; certificação herdando produto; remoção de parâmetros de rastreio.
- Sync idempotente; não toca linhas manuais; item removido vira `retired`; falha no meio não deixa estado
  parcial.
- Regras: casamento por produto+palavra, fronteira de palavra, sem acento, relatório de skills sem item.
- Recomendador: desempate, certificação na etapa certa, `retired` excluído, registros antigos.
- MCP com transporte falso: SSE e JSON, timeout, resposta malformada, URL fora do domínio, cache com TTL,
  consulta sem texto do CV (teste de contrato).
- Front: `check` de tipos/selos/"duração não informada"; verificação no navegador do cartão e do bloco.
- Script opcional `scripts/learn_smoke.py` para teste ao vivo (fora do CI).

## Fora de escopo

- Botão de sincronização na interface; agendamento automático; tradução dos títulos; matrículas ou progresso
  no Learn; uso do MCP para inferir nível.

## Limites a documentar

- O catálogo em pt-br tem menos itens que o em inglês; padrão `en-us`.
- A qualidade do mapeamento depende das regras; o relatório existe para corrigi-las.
- Nível e duração são da Microsoft; o casamento com as skills é regra nossa, sem medição.
- O MCP é busca de documentação: os links dele são leitura, não treinamento.
