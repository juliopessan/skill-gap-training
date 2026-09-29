# Skill Gap & Training Recommender — Design

Data: 2026-09-29 · Status: rascunho para revisão

## 1. Objetivo

Aplicação em que o usuário **sobe o mini CV (PDF) de um candidato e o pipeline roda sozinho**:
extrai as skills, classifica, calcula os gaps contra a base de treinamento **FY27** e
recomenda treinamentos do catálogo próprio.

Sucesso = após o upload, o cartão do candidato mostra skills (com evidência), gaps
(com severidade) e treinamentos recomendados (priorizados), sem nenhuma etapa manual.

## 2. Decisões já acordadas

| Tema | Decisão |
|---|---|
| Fonte | Mini CVs em PDF (layout livre, PT/EN) |
| Alvo do gap | Taxonomia FY27, três trilhas: **Azure AI Foundry**, **Microsoft Fabric**, **Databricks**, todas com uso de AI |
| Catálogo | CSV próprio, editável |
| Extração/classificação | LLM (Claude API) com saída estruturada |
| Linguagem | Núcleo em **Python** |
| Interface | **Next.js** (substitui a ideia inicial de Streamlit) |
| Fluxo | Upload único dispara o pipeline completo |

## 3. Escopo

**Dentro:** upload de 1..N PDFs (com texto nativo ou escaneados, via OCR Tesseract);
extração; normalização para a taxonomia; gap por trilha; recomendação por cobertura;
cartão do candidato; export CSV/XLSX; CLI fino para lote.

**Fora (v1):** autenticação/multiusuário; integração com plataformas externas de cursos;
edição de skills pela UI; deploy em nuvem.

## 4. Arquitetura

```
Next.js (frontend/) ──HTTP/JSON──► FastAPI (backend/) ──► pipeline
                                          │
                     SQLite (resultados) · taxonomy_fy27.yaml · catalog.csv
```

### Módulos do backend (uma responsabilidade cada)

| Módulo | Faz | Depende de |
|---|---|---|
| `pdf_reader` | PDF → texto. Tenta texto nativo (pdfplumber) por página; páginas com menos de 30 caracteres úteis caem para OCR (pypdfium2 renderiza a 300 dpi, pytesseract com `por+eng`). Sem texto após o OCR → `NO_TEXT` | `tesseract` (binário do sistema) |
| `skill_extractor` | Texto → skills brutas com nível e evidência via Claude API. Único ponto que chama a API | `anthropic`, schema |
| `taxonomy` | Carrega YAML; casa skills brutas com ids da taxonomia (id, sinônimos) | YAML |
| `gap_analyzer` | Taxonomia − perfil, por trilha; calcula severidade | `taxonomy` |
| `recommender` | Catálogo × gaps → treinamentos priorizados | CSV |
| `store` | Persiste/consulta resultados (SQLite) | — |
| `api` | `POST /candidates`, `GET /candidates`, `GET /candidates/{id}`, export | módulos acima |
| `cli` | Processa pasta de PDFs sobre o mesmo núcleo | módulos acima |

### Frontend
Tela única com área de upload (arrastar PDFs), lista com progresso por CV
(`lendo PDF → extraindo → calculando gap → recomendando`, via polling) e o cartão do
candidato (skills por trilha com citação, gaps, treinamentos, botão exportar).

## 5. Configuração editável

**`taxonomy_fy27.yaml`**: trilhas → skills. Cada skill: `id`, `nome`, `sinonimos[]`,
`nivel_esperado` (1–3). Versão inicial montada por nós e revisada por você; não é
fornecida pelo cliente.

**`catalog.csv`**: `id, titulo, skills_cobertas (ids separados por ;), nivel, carga_horaria, link`.
A v1 acompanha um catálogo de exemplo no mesmo formato.

## 6. Regras de negócio

- **Níveis:** 0 não tem · 1 básico · 2 intermediário · 3 avançado. O nível é inferido
  pelo LLM e sempre acompanha um trecho de evidência do CV, para auditoria.
- **Gap:** para cada skill da taxonomia, `gap = nivel_esperado − nivel_atual` se positivo.
  Severidade (avaliada nesta ordem): `alta` se a pessoa não tem a skill (nível 0) e o
  esperado é ≥ 2, ou se a diferença é ≥ 2; `média` se não tem a skill e o esperado é 1;
  `baixa` se tem a skill e falta 1 nível (ex.: 1→2, 2→3).
  *(Corrigido no plano: a redação anterior classificava 1→3 como "baixa".)*
- **Escopo por trilha:** o gap é exibido por trilha. O candidato não é penalizado por
  trilhas em que não tem nenhuma skill (trilha sem evidência aparece como "sem dados",
  e não como lista de gaps).
- **Recomendação (determinística, sem LLM):** pontuação de cada curso = soma, sobre os
  gaps que ele cobre, de `peso_severidade` (alta 3, média 2, baixa 1). Cursos cujo nível
  é menor que o nível atual da pessoa nas skills cobertas são descartados. Ordena por
  pontuação e desempata por menor carga horária. Cada resultado indica quais gaps cobre.
- **Skill fora da taxonomia:** mantida no perfil como "outras skills", sem entrar no gap.

## 7. Contrato de dados (resultado por candidato)

```json
{
  "id": "uuid",
  "candidate": "Nome",
  "status": "done | processing | error",
  "stage": "queued | reading | extracting | analyzing | recommending | done | error",
  "error": null,
  "error_message": null,
  "no_data_tracks": ["databricks"],
  "skills": [{"id": "fabric.lakehouse", "name": "Lakehouse", "track": "fabric", "level": 2, "evidence": "trecho do CV"}],
  "other_skills": [{"name": "Kubernetes", "level": 1, "evidence": "..."}],
  "gaps": [{"skill": "foundry.agents", "name": "AI Agents", "track": "foundry", "expected": 2, "current": 0, "severity": "high"}],
  "recommendations": [{"course_id": "c12", "title": "...", "covers": ["foundry.agents"], "hours": 8, "link": "..."}]
}
```

## 8. Privacidade e erros

- Só o **texto** do CV vai à API. Antes do envio, e-mail, telefone e endereço são
  removidos por regex. O nome é mantido apenas para rotular o candidato no perfil local.
- API key via variável de ambiente `ANTHROPIC_API_KEY`; nunca em código nem no frontend.
- O OCR roda **localmente**; a imagem do CV nunca sai da máquina. Só o texto resultante
  vai à API, como no fluxo normal.
- Erros por CV, sem derrubar o lote: `NO_TEXT` (nada legível nem com OCR),
  `OCR_UNAVAILABLE` (binário Tesseract ou pacote de idioma `por` ausente), `INVALID_PDF`,
  `LLM_INVALID_OUTPUT` (validação de schema falhou após 2 retries), `LLM_UNAVAILABLE`.
  A UI exibe o motivo em português.
- Reprocessar o mesmo PDF (mesmo hash) reutiliza o resultado salvo e não chama a API.

## 9. Testes

- 3 a 5 mini CVs fictícios com skills esperadas conhecidas (`tests/fixtures/`).
- Unitários determinísticos: `taxonomy` (sinônimos), `gap_analyzer`, `recommender`.
- `pdf_reader`: uma fixture com texto nativo e outra escaneada (só imagem); a segunda
  deve passar pelo OCR e retornar as skills conhecidas. O teste de OCR é pulado (skip)
  se o Tesseract não estiver instalado.
- `skill_extractor` com resposta simulada da API, mais uma verificação manual com a
  API real antes de dar o v1 como pronto.
- Ponta a ponta: subir um PDF de fixture e conferir o cartão (skills, gaps, cursos).

## 10. Estrutura de pastas

```
backend/  src/{pdf_reader,skill_extractor,taxonomy,gap_analyzer,recommender,store,api,cli}
          config/{taxonomy_fy27.yaml,catalog.csv}   tests/
frontend/ (Next.js, TypeScript)
```

## 11. Riscos e pontos em aberto

- **Qualidade da taxonomia FY27** define a qualidade do gap; a versão inicial precisa da
  sua revisão.
- **Nível inferido por LLM** pode divergir do real; mitigado pela evidência visível e pela
  revisão humana.
- **Qualidade do OCR** cai em scans ruins ou com layout em colunas; siglas técnicas
  (ex.: "PySpark") podem sair truncadas. Mitigado pela normalização por sinônimos e pela
  evidência visível na UI.
- **Dependência do sistema:** o Tesseract e o pacote de idioma `por` precisam estar
  instalados (`brew install tesseract tesseract-lang` no macOS); o README documenta isso
  e o erro `OCR_UNAVAILABLE` orienta o usuário.
- **Custo/latência** de uma chamada por CV; o OCR acrescenta segundos por página escaneada; mitigado pelo cache por hash.
- **Duas stacks** (Python + TypeScript) aumentam a manutenção; o núcleo Python é
  independente da UI e validável pelo CLI antes da interface.
