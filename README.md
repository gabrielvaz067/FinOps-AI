# FinOps AI

FinOps AI é uma aplicação de monitoramento financeiro construída sobre **50.000 transações inteiramente sintéticas** de 2025. O projeto reúne exploração de movimentações, detecção de grupos atípicos por conta, canal e dia, investigação sob demanda e notificações simuladas. A versão local permite ações administrativas; a demonstração pública é somente de leitura. Um alerta é um sinal para investigar, não uma classificação de fraude nem uma movimentação financeira.

## Demonstração online

**[Acessar o FinOps AI](https://finops-ai-monitor.netlify.app/)** · [Documentação interativa da API](https://finops-ai-api.onrender.com/docs) · [Health check da API](https://finops-ai-api.onrender.com/api/health)

A aplicação está publicada em uma arquitetura separada: **Netlify** hospeda o frontend React/Vite, **Render Free** executa a API FastAPI em um contêiner Docker e **Neon Free** armazena os dados sintéticos em PostgreSQL 17. A base hospedada foi verificada com **50.000 transações**, **602 candidatos da abordagem combinada**, oito contas, quatro canais e uma execução do pipeline. A API respondeu com `status=ok`, `synthetic=true`, `public_demo=true`, `gemini_available=false` e `notification_mode=simulated`; a navegação pelas cinco páginas foi conferida após a publicação.

O ambiente online é uma **demonstração somente de leitura**. Não executa investigações por Gemini nem envia notificações reais; a integração Gemini e o workflow n8n foram validados separadamente no ambiente local. Como o Render utiliza o plano gratuito, a primeira requisição após um período de inatividade pode demorar enquanto o serviço é reativado.

## Prévia do dashboard

![Dashboard do FinOps AI com indicadores, comparação dos detectores e fluxo financeiro](docs/images/01-dashboard.png)

A interface usa azul-marinho no fundo, na navegação lateral e nas superfícies, com azul claro para ações e séries principais. Verde, âmbar e vermelho distinguem estados operacionais e prioridades. O layout mantém filtros globais, indicadores, gráficos e tabelas em grades que se adaptam ao espaço disponível.

## Tecnologias utilizadas

- **Frontend:** React 19, TypeScript, Vite 7 e Tailwind CSS 4; gráficos em SVG e testes com Vitest e Playwright.
- **API:** Python 3.14, FastAPI, Pydantic e SQLAlchemy; testes com pytest e Ruff.
- **Dados:** SQLite no início rápido local, PostgreSQL no Docker e PostgreSQL 17 gerenciado no Neon para a demonstração pública; migrations Alembic.
- **Detecção:** Isolation Forest e regras estatísticas, avaliados separadamente e em união.
- **Integrações opcionais:** Gemini API para investigação sob demanda e n8n Community para automação local. O modo padrão de notificação é `simulated`.

## Arquitetura da aplicação

O frontend em `frontend/` consulta a API FastAPI em `backend/`. Na execução local integrada, a aplicação compilada é servida pelo próprio FastAPI; no desenvolvimento, o Vite encaminha `/api` para a porta 8000. Na versão online, o frontend estático é hospedado no Netlify, a API FastAPI é executada no Render Free com Docker e o banco PostgreSQL 17 fica no Neon Free. O Netlify chama a API pela variável pública `VITE_API_BASE_URL`; o Render mantém `DATABASE_URL` como segredo no backend e restringe `CORS_ORIGIN` ao domínio HTTPS `https://finops-ai-monitor.netlify.app`. `database/` guarda as migrations e o SQLite local ignorado pelo Git. `automation/` contém o workflow n8n exportável. A API usa filtros tipados, paginação e cabeçalhos de segurança.

No modo local, gravações exigem `X-Admin-Key`. Com `PUBLIC_DEMO=true`, as rotas administrativas e a consulta de alertas pendentes do n8n não são registradas. O navegador recebe somente dados sintéticos e pode solicitar uma prévia de investigação por regras, sem gravação nem chamada externa. Esse modo é uma vitrine de leitura; não substitui autenticação por usuário em um produto operacional. Use um worker no modo local.

O PostgreSQL usa a mesma migration Alembic do SQLite. Para configurá-lo fora do Compose, defina `DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/banco` no `.env`, crie um banco vazio e execute `.\.venv\Scripts\python.exe -m backend.app.cli init`. Na implantação no Neon, a conexão externa com TLS (`sslmode=require`) foi utilizada e a carga sintética foi conferida diretamente no banco. A URL do banco não vai para o frontend.

## Pipeline e dados sintéticos

A geração usa seed 42 e o período fixo de janeiro a dezembro de 2025. O volume varia por dia da semana e estação, com perfis de conta e canal. São injetados eventos rotulados de valor extremo, horário incomum, referência duplicada, pico de volume e queda na aprovação. Os rótulos ficam em `synthetic_labels`, fora da tabela usada para as features.

`datasets.id` identifica versão, seed e contagem. Repetir a carga ou o pipeline com os mesmos parâmetros retorna o resultado existente; uma base incompatível ou incompleta é recusada sem apagar registros. O detector agrega transações por **conta/canal/dia**, após o fechamento do dia. As medianas por conta e canal são ajustadas somente com janeiro a agosto de 2025. Setembro a dezembro é o teste cronológico. Os rótulos entram após `fit` e `predict`, para calcular matriz de confusão, precisão, recall e F1. O pipeline persiste versão, features, corte temporal, métricas e evidências dos grupos sinalizados.

## Detecção de anomalias e resultados de Machine Learning

Isolation Forest e regras estatísticas são calculados separadamente; a abordagem combinada reúne os candidatos dos dois detectores. As três abordagens permanecem disponíveis no dashboard e na central de anomalias. **Regras é a seleção padrão de consulta e notificação**, pois teve o maior F1 nesta avaliação sintética. A seleção do dashboard altera a contagem no período e os alertas exibidos, mas os filtros financeiros não recalculam as métricas globais de teste. O score do Isolation Forest não é probabilidade de fraude.

Resultado medido no dataset padrão: 50.000 transações, 7.197 grupos de treino e 3.543 de teste, dos quais 554 são positivos. A unidade de avaliação é conta/canal/dia, e os positivos incluem eventos injetados. Estes números **não representam desempenho em dados reais**.

| Detector | Precisão | Recall | F1 |
| --- | ---: | ---: | ---: |
| Isolation Forest | 0,7842 | 0,4134 | 0,5414 |
| Regras | 0,8574 | 0,8574 | **0,8574** |
| Abordagem combinada (união) | 0,8023 | 0,8718 | 0,8356 |

Nesta seed, a união recuperou mais positivos, enquanto as regras tiveram maior F1. A escolha padrão é uma decisão de apresentação baseada apenas nesse resultado sintético; o pipeline e as três abordagens permanecem fixos, sem ajuste de hiperparâmetros no conjunto de teste. Não extrapole a ordenação para dados reais. Métricas por tipo de evento e contagens da matriz de confusão estão em `GET /api/pipeline/runs`.

## Integração com Gemini

No modo local, defina `GEMINI_API_KEY` no `.env` e reinicie o servidor. `GEMINI_MODEL` permite selecionar o modelo; o padrão verificado é `gemini-3.5-flash-lite`. Confira no AI Studio a disponibilidade da camada gratuita para seu projeto antes de fazer uma chamada. Para migrar um banco já criado, execute `.\.venv\Scripts\python.exe -m backend.app.cli migrate`. A chave permanece no backend e nunca deve ser enviada pelo chat, colocada no frontend ou versionada.

A ação explícita na página de investigação envia ao Gemini somente dia, severidade, motivos e evidências agregadas. O JSON retornado é validado e salvo com provedor e modelo. Chave ausente, erro HTTP, timeout, falha de conexão ou resposta inválida produzem análise por regras, identificada visualmente como **sem IA generativa**. Cada tentativa real gera um diagnóstico interno em `gemini_attempts` com modelo solicitado, horário UTC, status HTTP, código e categoria do erro, sem mensagem ou payload do provedor. Esses diagnósticos não são servidos pela API pública; o modo público recusa chamadas ao Gemini.

Em 18/11/2026, uma tentativa com `gemini-2.5-flash` terminou em fallback. A implementação anterior descartava o erro externo, portanto a causa exata daquela tentativa não pode ser recuperada; HTTP 200 na consulta de metadados não comprovava acesso à geração. Após a mudança para `gemini-3.5-flash-lite`, **uma geração real** da anomalia sintética 1 foi concluída com HTTP 200 e salva no histórico como `gemini` / `gemini-3.5-flash-lite`. A resposta continha resumo, evidências numéricas conferidas com o banco, hipóteses, recomendações e limitações. Esse único sucesso não demonstra disponibilidade contínua nem desempenho em dados reais. Consulte a [documentação dos modelos](https://aistudio.google.com/docs/models) e a [tabela de preços do AI Studio](https://aistudio.google.com/docs/pricing#gemini-3-5-flash-lite) antes de repetir o teste.

## Automações com n8n e Docker

O workflow em `automation/critical-alerts.n8n.json` consulta até 100 alertas críticos detectados por regras e ainda pendentes, deduplica o lote e chama o backend. A API confirma a idempotência no banco e registra execução, resultado e tentativa. A chave administrativa fica em uma credencial **Header Auth** do n8n para `X-Admin-Key`, não no JSON exportado.

O ambiente local foi verificado com Docker Engine 29.9.3, Docker Compose 5.7.0 e n8n Community 2.48.5. Com `.env` configurado e `NOTIFICATION_MODE=simulated`, valide e inicie somente os serviços necessários:

```powershell
docker compose --profile automation config --quiet
docker compose --profile automation up -d --build postgres app n8n
```

O app fica em <http://127.0.0.1:8000> e o n8n em <http://localhost:5678>. O workflow foi importado no n8n local pelo CLI e executado três vezes: 100, 41 e 0 alertas processados. O backend registrou **141 notificações simuladas, 141 alertas distintos e nenhuma duplicata**. Não houve envio de e-mail; o agendamento segue inativo. O [guia de instalação e resultados verificados](docs/n8n-local.md) registra a configuração e a execução.

O envio SMTP é opcional. Ele exige `NOTIFICATION_MODE=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_TO` e, se necessário, `SMTP_USER`/`SMTP_PASSWORD`; usa STARTTLS. Falhas anteriores ao envio podem ser tentadas até três vezes. Uma falha durante SMTP vira `unknown` e exige revisão manual antes de reenviar, pois a entrega pode ter ocorrido. A idempotência é por alerta e modo. **Nenhum e-mail real foi enviado nesta validação.**

## Cinco páginas da aplicação

As capturas integrais abaixo foram feitas com Playwright em viewport desktop de 1440 × 900, após carregar a API. O servidor de teste usa uma cópia isolada do SQLite, dados sintéticos e `PUBLIC_DEMO=true`. Por isso, a investigação mostra uma prévia por regras e o histórico de automações nessa cópia está vazio; as execuções n8n descritas acima foram registradas no PostgreSQL local.

### Dashboard

Indicadores de volume aprovado, saldo, aprovação e anomalias; comparação dos três detectores, série temporal, canais, alertas prioritários e a última execução de automação registrada pela API.

![Dashboard com indicadores, comparação dos detectores, gráfico e alertas](docs/images/01-dashboard.png)

### Transações

Livro de movimentações com busca por referência, filtros de período, conta, canal e status, paginação e horários sintéticos em UTC. A tabela mantém rolagem própria em telas estreitas.

![Tabela de transações sintéticas com busca e filtros](docs/images/02-transacoes.png)

### Central de anomalias

Fila com prioridade, score do Isolation Forest, motivos e valores observados. Permite filtrar por detector e prioridade e abrir cada alerta para investigação.

![Fila de anomalias com prioridades e detectores](docs/images/03-anomalias.png)

### Investigação com IA

Evidências e análise aparecem lado a lado no desktop e empilhadas no celular. A página mostra maiores transações, histórico e geração sob demanda; análises do Gemini e baseadas em regras têm identificações distintas.

![Evidências de alerta sintético e prévia de análise por regras](docs/images/04-investigacao-ia.png)

### Automações

Mostra o fluxo de consulta, deduplicação, notificação e registro, além do histórico de execuções e tentativas. No modo público, as operações de escrita não ficam disponíveis.

![Fluxo de notificações simuladas e histórico da cópia isolada](docs/images/05-automacoes.png)

## Estrutura do repositório

```text
backend/              API, geração sintética, detecção, investigação e testes
frontend/             React, estilos, testes unitários e Playwright
database/migrations/  versões Alembic
automation/           workflow n8n exportável
docs/                 guias e capturas reais das cinco telas
scripts/              preparação, inicialização e verificação de navegador
docker-compose.yml    serviços locais PostgreSQL, app e n8n
Dockerfile            imagem da aplicação integrada local
Dockerfile.render     imagem somente da API para Render
netlify.toml          build e roteamento SPA do Netlify
```

O SQLite local, `.env`, logs, capturas temporárias e artefatos de build são ignorados pelo Git.

## Como executar localmente

No Windows, use Python 3.14, Node.js 24 e npm 11. A preparação instala dependências no projeto, cria `.env` local com chaves aleatórias, aplica a migration, carrega a base uma vez, executa o pipeline e compila o frontend. A primeira execução processa 50.000 transações e pode levar alguns minutos.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Abra <http://127.0.0.1:8000>; a documentação OpenAPI está em <http://127.0.0.1:8000/docs>. Para gerar análises, reexecutar o pipeline ou simular notificações no ambiente local, abra **Acesso administrativo** e use `FINOPS_ADMIN_KEY` do `.env` local. A interface mantém a chave apenas na memória da aba. Não compartilhe nem versione esse arquivo.

Se `py -3.14` não estiver disponível, passe `-PythonPath 'C:\caminho\para\python.exe'` ao primeiro comando. Para executar frontend e backend separadamente, inicie `uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000` pelo ambiente virtual da raiz e `npm.cmd run dev` em `frontend/`. O Vite encaminha `/api` à porta 8000.

A [demonstração online](https://finops-ai-monitor.netlify.app/) está publicada. O [guia de publicação e reprodução](docs/public-demo.md) documenta frontend no Netlify, API no Render Free e PostgreSQL no Neon Free. `VITE_API_BASE_URL` aponta o navegador para a API e `CORS_ORIGIN` autoriza somente o domínio HTTPS configurado. `PUBLIC_DEMO=true` mantém somente leitura e prévia por regras. Não coloque chaves, credenciais ou dados reais no ambiente público.

## Testes, limitações e próximos passos

Comandos de validação:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend database scripts
.\.venv\Scripts\python.exe -m ruff format --check backend database scripts
Push-Location frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
Pop-Location
.\.venv\Scripts\python.exe scripts\verify_browser.py
```

O teste de navegador usa cópia descartável do SQLite, servidor local na porta 8001 e chave exclusivamente de teste. Capturas temporárias ficam em `artifacts/`, ignorado pelo Git. Para verificar o modo público, execute `$env:PUBLIC_DEMO='true'; .\.venv\Scripts\python.exe scripts\verify_browser.py public-demo.spec.ts` em um novo PowerShell. O navegador cobre as cinco páginas, filtros, paginação, investigação por regras, estado vazio, recuperação de falha de API e ausência de ações administrativas públicas.

Na validação de 18/11/2026, passaram **52 testes pytest**, **7 testes Vitest**, typecheck, ESLint, Ruff, build e seis fluxos Playwright (quatro locais e dois públicos). Docker Compose iniciou PostgreSQL, FastAPI e n8n. O workflow foi importado e executado três vezes no n8n, com 141 notificações simuladas, 141 alertas distintos, 141 tentativas e zero falhas de entrega. Uma tentativa inicial do CLI falhou por conflito na porta interna do task broker antes de chamar o backend; a execução com portas internas exclusivas funcionou. O Chrome confirmou registros na página de Automações e resumo no dashboard sem erro de console. O agendamento não foi ativado.

Depois do redesign, o frontend passou novamente por typecheck, ESLint, 7 testes Vitest e build. O Playwright gerou as cinco capturas públicas reais e verificou as páginas em larguras de 1440, 1366, 768 e 390 px, sem erro de console ou overflow horizontal da página. Essa rodada não incluiu aparelho móvel físico, SMTP real ou PostgreSQL gerenciado; a conexão gerenciada foi validada posteriormente durante a implantação no Neon.

Na preparação para hospedagem separada em 19/11/2026, passaram **57 testes pytest**, **8 testes Vitest**, Ruff, typecheck, ESLint, build e dois fluxos Playwright do modo público (desktop e mobile). O build de exemplo incorporou `VITE_API_BASE_URL` sem credenciais; a imagem `Dockerfile.render` compilou e, em teste local com banco descartável, respondeu ao health check com `PUBLIC_DEMO=true`, CORS restrito e sem rota administrativa. A conexão real ao Neon e a partida no Render eram pendências dessa etapa e foram verificadas posteriormente durante a publicação.

Na auditoria anterior, `npm audit --omit=dev` e `pip-audit` sobre `backend/requirements.lock.txt` retornaram zero vulnerabilidades. O audit completo do npm apontou uma vulnerabilidade alta de ReDoS em `picomatch` nas ferramentas de desenvolvimento; ainda não havia correção na [advisory consultada](https://github.com/advisories/GHSA-fc5q-39xc-vjpf). O build estático não inclui essa dependência. Verifique um patch antes de atualizar ou expor ferramentas de build a padrões glob de origem não confiável.

Em 19/11/2026, a implantação no Neon foi verificada com 13 tabelas, 50.000 transações, 602 candidatos da abordagem combinada e uma execução do pipeline; o Render iniciou a API com sucesso e o endpoint `/api/health` retornou a configuração pública esperada. O frontend foi publicado no Netlify e as cinco páginas foram conferidas na demonstração online. Esses resultados são verificações de implantação, não uma nova bateria de testes automatizados em produção.

O dataset é demonstrativo: não contém dados financeiros reais e não oferece decisão automática ou aconselhamento financeiro. O corte temporal e as regras foram escolhidos para a simulação; métricas podem mudar com seed, algoritmo ou dependências. Permanecem como próximos passos a verificação em aparelho físico e o acompanhamento da disponibilidade e dos limites dos planos gratuitos.
