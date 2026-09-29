# Skill Gap Training

Suba o mini CV de um candidato e o pipeline faz o resto: extrai as skills (com OCR quando o PDF é
escaneado), mapeia para a taxonomia FY27 (**Azure AI Foundry**, **Microsoft Fabric** e **Databricks**,
todas com uso de AI), calcula os gaps e recomenda treinamentos do seu catálogo.

Ferramenta local, de uso individual: backend em Python (FastAPI) e interface em Next.js.

**Stack:** Python 3.11+ · FastAPI · pdfplumber + pypdfium2 + Tesseract (OCR) · Anthropic SDK
(`claude-sonnet-5-5`, saída estruturada via `messages.parse` com um modelo Pydantic) · SQLite ·
Next.js 15 (TypeScript).

> **Status:** os testes automáticos passam, mas a extração com o Claude real ainda **não foi
> exercitada** (ver [O que está e o que não está verificado](#o-que-está-e-o-que-não-está-verificado)).
> Trate a v1 como pronta para validação com CVs reais, não como validada.

## Estrutura do projeto

```
backend/   pipeline e API em Python
  src/skillgap/  pdf_reader · privacy · skill_extractor · classifier · gap_analyzer ·
                 recommender · pipeline · store · service · exports · api · cli · demo
  config/        taxonomy_fy27.yaml · catalog.csv   (editáveis)
  tests/
frontend/  interface Next.js (upload, progresso por CV, cartão do candidato)
docs/superpowers/  spec e plano de implementação
```

## Como funciona

```
PDF → texto (nativo/OCR) → remoção de contatos → Claude (skills + nível + evidência)
    → normalização p/ taxonomia → gap por trilha → recomendação por cobertura
```

- **Nível:** 0 não tem · 1 básico · 2 intermediário · 3 avançado, sempre com a citação do CV.
- **Gap:** `esperado − atual`; severidade alta/média/baixa. Trilha sem nenhuma evidência aparece
  como "sem dados", e não como lista de gaps.
- **Recomendação:** determinística (sem LLM), por cobertura ponderada pela severidade.
- **Cache:** o mesmo PDF (SHA-256) não é processado duas vezes.
- **Limites:** 10 MB por PDF e até 20 arquivos por envio.

### Medido × afirmado (design Ledger)

A interface segue o design system **Ledger**: o que foi *calculado* nunca se parece com o que foi
*afirmado pelo modelo*.

| | Origem | Na interface |
|---|---|---|
| Nível de cada skill, citação, nome do candidato | **Afirmado** pelo modelo | Nunca fica verde |
| A citação existe no texto do CV (`evidence_verified`) | **Calculado** (busca de texto, sem LLM) | Selo verde `✓ citação no CV`; se não existe, selo terracota e faixa "Citação não encontrada" |
| Casamento de nomes com a taxonomia | **Calculado** | Entra no bloco "Calculado, não estimado" |
| Gaps e ranking dos treinamentos | Contas calculadas, **mas a partir dos níveis inferidos** | Não recebem selo de "medido" |
| Trilha sem dados | Fato conhecido | Faixa "Sem dados", sem lista de gaps |

- O **ledger** no topo do cartão mostra as barras pareadas "citações do modelo" × "citações
  localizadas no CV" e os números do candidato. Registros processados antes da verificação não
  mostram selo nenhum (o campo é `null`, nunca `false`).
- O verde e o terracota são **reservados** a esses sinais; severidade dos gaps é só rótulo em tinta.
- **O selo verde prova que a citação existe no texto do CV, não que ela sustenta aquela skill ou
  aquele nível.** Um modelo pode citar uma linha verdadeira e irrelevante: revise as citações.
- A busca (`backend/src/skillgap/evidence.py`) normaliza caixa, espaços, hífens e aspas, exige
  fronteira de palavra/número (`"of 5"` não casa com `"of 50"`) e ignora trechos com menos de 8
  caracteres; reticências (`…`/`...`) separam trechos que precisam aparecer em ordem.
- Suporta tema claro e escuro (`prefers-color-scheme`); as cores de texto pequeno passam de 4,5:1.

## Requisitos

- Python 3.11+, Node 20+
- Tesseract com o idioma português (necessário para páginas escaneadas; PDFs em que todas as páginas têm texto nativo não precisam dele): `brew install tesseract tesseract-lang`. Sem o Tesseract, um PDF majoritariamente nativo ainda funciona e um PDF totalmente escaneado falha com `OCR_UNAVAILABLE`.
- Uma `ANTHROPIC_API_KEY` (só para a extração real; o modo demo e os testes não precisam)

## Rodando

**Importante:** todos os comandos do backend (`uvicorn`, `python -m skillgap.cli`,
`python -m skillgap.demo`, `pytest`) devem ser executados a partir de `backend/`, porque os caminhos
de configuração são relativos (`config/...`, `data/...`).

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...
uvicorn skillgap.api:create_app --factory --port 8000

# Frontend (outro terminal)
cd frontend && cp .env.example .env.local && npm install && npm run dev
# http://localhost:3000
```

- Não existe `app` no nível do módulo: use sempre `--factory`.
- Use **um único worker** do uvicorn (nada de `--workers` maior que 1): a aplicação assume que um
  só processo é dono do arquivo SQLite (ao iniciar, ela marca como falhos os registros que ficaram
  em `processing`).
- O frontend lê a API de `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`). A API só aceita
  CORS de `http://localhost:3000` e `http://127.0.0.1:3000`.

Sem API key, para ver a interface: `python -m skillgap.demo` (a partir de `backend/`). Ele sobe a API
em `127.0.0.1:8000` com um extrator **simulado**, que devolve sempre o mesmo perfil fictício
independentemente do PDF enviado. As citações das três primeiras skills vêm de trechos reais do texto
do PDF (é preciso um PDF com pelo menos 3 linhas de 8+ caracteres), e a última (Kubernetes) é inventada de
propósito, para você ver o selo e a faixa de "citação não encontrada".

Em lote, sem interface (a partir de `backend/`):

```bash
python -m skillgap.cli process ./cvs --out ./out
```

Processa todos os `.pdf` da pasta e grava um JSON por arquivo em `--out` (padrão `out`). O código de
saída é 1 se algum CV falhar.

## Erros por CV

Quando um CV falha, o erro aparece só nele; os demais seguem.

| Código | Significado |
|---|---|
| `INVALID_PDF` | O arquivo não é um PDF válido. |
| `NO_TEXT` | Não foi possível ler texto neste PDF, nem com OCR. |
| `OCR_UNAVAILABLE` | OCR indisponível: falta instalar o Tesseract e o idioma português. |
| `LLM_INVALID_OUTPUT` | O modelo devolveu uma resposta inválida após novas tentativas. |
| `LLM_UNAVAILABLE` | Serviço de IA indisponível ou `ANTHROPIC_API_KEY` ausente. |
| `INTERNAL` | Erro interno ao processar este CV. |

## Configuração editável

| Arquivo | O que define |
|---|---|
| `backend/config/taxonomy_fy27.yaml` | Trilhas, skills, sinônimos e nível esperado (1–3) |
| `backend/config/catalog.csv` | Treinamentos: `id,titulo,skills_cobertas,nivel,carga_horaria,link` |

Variáveis de ambiente: `SKILLGAP_DB` (padrão `data/skillgap.db`), `SKILLGAP_TAXONOMY`,
`SKILLGAP_CATALOG` e `SKILLGAP_MODEL` (padrão `claude-sonnet-5-5`).

O catálogo que acompanha o repositório é **de exemplo** (títulos e links fictícios): substitua pelo
real. A taxonomia é uma versão inicial, que deve ser revisada.

## Privacidade

Só o **texto** do CV vai para a API do Claude, depois de remover:

- e-mails e URLs de LinkedIn/GitHub;
- telefones brasileiros e internacionais (com `+`, com `55` sem `+`, com DDD) e links `wa.me/<número>`;
- números locais sem DDD (`91234-5678`) **somente quando vêm depois de um rótulo** como `Cel:`, `Tel:`,
  `Fone:`, `WhatsApp` ou `Contato:` (o rótulo é mantido); sem rótulo eles ficam, para não apagar
  períodos como `2019-2021`;
- CEPs com hífen (`01234-567`) ou de 8 dígitos depois do rótulo `CEP` (o rótulo é mantido);
- trechos de endereço em português e inglês e códigos postais do Reino Unido.

O OCR roda localmente.

Essa remoção é baseada em expressões regulares, faz o melhor esforço e **não é uma garantia**: o nome
e outros dados pessoais no texto podem permanecer. Não envie CVs que você não tem permissão para
processar com um serviço externo de LLM.

## Testes

```bash
(cd backend && pytest -q)                 # 215 testes; também passa com `pytest -W error -q`
(cd frontend && npx tsc --noEmit && npm run check:http && npm run check:ledger && npm run build)
```

> Não rode `npm run build` com o `npm run dev` ativo: os dois usam a pasta `.next` e o servidor de
> desenvolvimento quebra (`Cannot find module './851.js'`). Pare o servidor, faça o build e suba de novo.

`npm run check:ledger` confere a lógica pura dos números do ledger (`frontend/lib/ledger.ts`): contagens,
horas, citações sem verificação e o percentual das barras.

`npm run check:http` roda, com `fetch` simulado, os helpers HTTP da interface (`frontend/lib/http.ts`):
confirma que a chamada de rede é de fato feita, que uma falha de rede vira mensagem em português e que
erros `detail` da API são tratados.

### O que está e o que não está verificado

**Verificado**
- Backend: 215 testes automáticos, incluindo o fluxo completo (upload → pipeline → cartão), cache por
  hash, concorrência no envio, exportações com proteção contra injeção de fórmula e o OCR real do
  Tesseract (quando instalado).
- Formato do pedido ao Claude: um teste de contrato garante que a requisição usa saída estruturada
  (`output_format`) e **não** força `tool_choice`, que o `claude-sonnet-5-5` rejeita com HTTP 400. O
  caminho de parsing foi conferido contra o SDK real com um transporte HTTP simulado.
- Interface: `tsc`, `next build`, `check:http`, `check:ledger` e uma verificação manual no navegador
  contra a API de demonstração, em tema claro, tema escuro e largura de celular (375 px: a página
  não rola para o lado; a tabela de gaps rola dentro do próprio contêiner).

**Não verificado**
- A extração com o **Claude real**: nenhum teste chama a API. Não se sabe ainda a qualidade das skills,
  níveis e evidências extraídos, nem a latência e o custo por CV, nem se o modelo aceita o esquema de
  saída sem ajustes. Antes de confiar nos resultados, rode 2 ou 3 CVs seus (incluindo um escaneado)
  com uma `ANTHROPIC_API_KEY` e ajuste os sinônimos em `taxonomy_fy27.yaml` se necessário.
- `python -m skillgap.demo` usa um extrator simulado: serve para ver a interface, não para avaliar a
  extração.
- A interface não tem testes de componente; o comportamento de negócio é coberto pelos testes do backend.

## Limitações conhecidas

- Taxonomia e catálogo são exemplos iniciais, a revisar.
- `npm audit` reporta 2 achados no `postcss` embutido no Next 15 (a correção exige Next 16).
- Sem autenticação: não exponha a API fora da sua máquina.
- Ferramenta local para um único usuário (um processo, um arquivo SQLite).
- Requer o SDK `anthropic>=1.9` (é a menor versão verificada com `messages.parse`).
- A remoção de dados pessoais é por regex e pode deixar passar formatos incomuns de telefone, CPF/RG,
  datas de nascimento e endereços abreviados.
- Uma recusa do modelo (`refusal`) aparece como `LLM_INVALID_OUTPUT`.

Documentação de projeto: `docs/superpowers/specs/` e `docs/superpowers/plans/`.
