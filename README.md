# FinOps AI

Aplicação de monitoramento financeiro com dados **inteiramente sintéticos**. Gera 50.000 transações de 2025, detecta grupos atípicos por conta, canal e dia, apresenta evidências e registra investigações e notificações simuladas. Pode rodar localmente com ações administrativas ou em modo público somente de leitura. Anomalia é um sinal para investigar; o sistema não classifica fraude nem movimenta dinheiro.

## Executar no Windows (PowerShell)

Requisitos: Python 3.14, Node.js 24 e npm 11. O comando de preparação instala dependências no projeto, cria `.env` local com chaves aleatórias, aplica a migration, carrega a base uma vez, executa o pipeline e compila o frontend. A primeira preparação processa 50.000 transações e leva alguns minutos.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Abra <http://127.0.0.1:8000>. A API tem documentação OpenAPI em <http://127.0.0.1:8000/docs>. Para gerar análises, reexecutar o pipeline ou simular notificações, abra **Acesso administrativo** na interface e copie o valor de `FINOPS_ADMIN_KEY` do seu `.env` local. A interface mantém a chave apenas na memória da aba. Não compartilhe nem versione esse arquivo.

Se o lançador `py -3.14` não estiver disponível, use `-PythonPath 'C:\caminho\para\python.exe'` no primeiro comando. Para desenvolvimento separado, inicie `uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000` pelo ambiente virtual na raiz e `npm.cmd run dev` em `frontend/`; o Vite encaminha `/api` para a porta 8000. A versão compilada é servida pelo FastAPI sem dois servidores.

## O que há no sistema

- **Dashboard:** volume e saldo de transações aprovadas, taxa de aprovação, contagem de alertas, série temporal e distribuição por canal. Compara as métricas reais das três abordagens no teste sintético e mostra a última execução de automação registrada pela API. A seleção padrão é **regras**, por ter o maior F1 observado; a seleção também altera a lista de alertas e a contagem no período. As métricas são globais e não são recalculadas pelos filtros financeiros.
- **Transações:** busca por referência, filtros de período, conta, canal e status, paginação e horários em UTC.
- **Central de anomalias:** prioridade, score do Isolation Forest, motivos e valores observados; filtros por abordagem, prioridade e paginação. Regras, Isolation Forest e união permanecem disponíveis.
- **Investigação:** evidências do grupo, maiores transações, histórico e geração sob demanda. Análises do Gemini e baseadas em regras têm identificação visual distinta. Sem chave Gemini, a análise local funciona por regras; respostas inválidas ou indisponibilidade geram fallback registrado. No modo público, uma prévia por regras não grava histórico.
- **Automações:** seleção de alertas críticos detectados por regras, deduplicação por alerta e modo, registro de execução e tentativas. O modo padrão simula notificações e **não envia e-mails**. O modo público só permite consultar o fluxo e o histórico.

## Arquitetura e decisões

`frontend/` usa React 19, TypeScript, Vite e Tailwind CSS 4. A API em `backend/` usa FastAPI, SQLAlchemy e Pydantic. `database/` contém a migration Alembic e o SQLite local ignorado pelo Git. `automation/` contém o workflow n8n exportável. No modo local, as operações de gravação exigem `X-Admin-Key`. Com `PUBLIC_DEMO=true`, essas rotas e a consulta de pendências do n8n deixam de ser registradas; o navegador recebe somente dados sintéticos. A API aplica filtros tipados, paginação e cabeçalhos de segurança. Execute um worker no modo local. Esse modo público é uma vitrine de leitura, não substitui autenticação por usuário para um produto operacional.

A geração usa seed 42 e período fixo de janeiro a dezembro de 2025. O volume varia por dia da semana e estação, com perfis de conta e canal. São inseridas amostras rotuladas de valor extremo, horário incomum, referência duplicada, pico de volume e queda na aprovação. Os rótulos ficam em `synthetic_labels`, fora da tabela usada para features. `datasets.id` identifica versão, seed e contagem; repetir a carga/pipeline com os mesmos parâmetros retorna o resultado existente. Uma base incompatível ou incompleta é recusada, sem apagar registros.

O detector agrega transações por conta, canal e dia, após o fechamento do dia. Medianas por conta/canal são ajustadas somente com janeiro a agosto. Isolation Forest e regras estatísticas são calculados separadamente; a união persiste todos os candidatos, sem descartar nenhum detector. **Regras é o filtro padrão de consulta e notificação** por ter o maior F1 nesta avaliação. Setembro a dezembro é o teste cronológico. Os rótulos entram **após** `fit`/`predict`, para calcular matriz de confusão, precisão, recall e F1. O score do modelo não é probabilidade de fraude. O pipeline persiste versão, features, corte temporal, métricas e evidências dos grupos sinalizados.

### Resultado medido no dataset padrão

Pipeline executado localmente com 50.000 transações, 7.197 grupos de treino e 3.543 de teste (554 positivos no teste). A unidade de avaliação é **conta/canal/dia**, e os positivos incluem eventos injetados; estes números não representam desempenho em dados reais.

| Detector | Precisão | Recall | F1 |
| --- | ---: | ---: | ---: |
| Isolation Forest | 0,7842 | 0,4134 | 0,5414 |
| Regras | 0,8574 | 0,8574 | 0,8574 |
| União | 0,8023 | 0,8718 | 0,8356 |

Nesta seed, a união recupera mais positivos que cada detector isolado, mas as regras têm maior F1. A seleção padrão não é um ajuste de hiperparâmetros pelo conjunto de teste: o pipeline e as três abordagens permanecem fixos, e o dashboard informa a escolha baseada **apenas neste resultado sintético**. Não extrapole essa ordenação para dados reais. Métricas por tipo de evento e contagens da matriz de confusão estão em `GET /api/pipeline/runs`.

## Integrações opcionais

**Gemini:** somente no modo local, coloque `GEMINI_API_KEY` em `.env` e reinicie o servidor. `GEMINI_MODEL` é configurável (padrão `gemini-3.5-flash-lite`, com entrada e saída gratuitas no [plano Free](https://aistudio.google.com/docs/pricing#gemini-3-5-flash-lite)). Para atualizar um banco já criado, rode `.\.venv\Scripts\python.exe -m backend.app.cli migrate`. A ação explícita na página de investigação envia apenas dia, severidade, motivos e evidências agregadas. O retorno JSON é validado e guardado com provedor e modelo; chave ausente, erro HTTP, timeout, falha de conexão ou resposta inválida resultam em análise por regras. Cada chamada real gera um registro interno em `gemini_attempts` com modelo solicitado, horário UTC, status HTTP, código e categoria do erro, sem mensagem ou payload do provedor. Esses diagnósticos não são servidos pela API pública. O modo público recusa a chave e oferece somente a prévia local por regras. Confirme no AI Studio que o projeto está na camada gratuita antes de testar; não envie a chave pelo chat.

Em 18/11/2026, uma tentativa com `gemini-2.5-flash` terminou no fallback por regras; a versão anterior descartou o erro externo, então sua causa exata não pode ser recuperada. A [documentação dos modelos](https://aistudio.google.com/docs/models) limita o acesso à família 2.5 a usuários anteriores; o HTTP 200 da consulta de metadados não comprovava acesso à geração. Após a mudança para `gemini-3.5-flash-lite`, **uma** geração real da anomalia sintética 1 foi concluída (HTTP 200) e salva no histórico como `gemini` / `gemini-3.5-flash-lite`. A resposta continha resumo, evidências numéricas conferidas com o banco, hipóteses, recomendações e limitações. Esse único sucesso não demonstra disponibilidade contínua nem desempenho em dados reais.

**PostgreSQL:** configure `DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/banco` em `.env`, crie um banco vazio e rode `.\.venv\Scripts\python.exe -m backend.app.cli init`. A migration é a mesma para PostgreSQL local ou gerenciado; serviços externos podem exigir TLS (`sslmode=require`). Conexão externa e políticas do provedor dependem do ambiente e ainda não foram testadas aqui. Não exponha essa URL no frontend.

**Docker Compose e n8n Community:** o ambiente local foi validado com Docker Engine 29.9.3, Compose 5.7.0 e n8n 2.48.5. Depois de configurar `.env`, confirme `NOTIFICATION_MODE=simulated` e execute:

```powershell
docker compose --profile automation config --quiet
docker compose --profile automation up -d --build postgres app n8n
```

O app integrado fica em <http://127.0.0.1:8000> e n8n em <http://localhost:5678>. O workflow existente foi importado no n8n local pelo CLI e associado a uma credencial **Header Auth** para `X-Admin-Key`, armazenada no n8n; a chave não está no JSON exportado. O fluxo busca até 100 críticos detectados por regras e ainda pendentes, deduplica o lote e chama o backend, que confirma idempotência no banco e registra resultado e tentativa. Três execuções reais no n8n processaram 100, 41 e 0 alertas, respectivamente: **141 notificações simuladas, 141 alertas distintos e nenhuma duplicata**. O agendamento segue inativo. Veja o [guia de instalação e resultados verificados](docs/n8n-local.md).

**SMTP:** altere `NOTIFICATION_MODE=smtp` e configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_TO` e, se necessário, `SMTP_USER`/`SMTP_PASSWORD`. O envio usa STARTTLS. Falhas antes do envio podem ser tentadas até três vezes; falha durante SMTP vira `unknown` e exige revisão manual antes de qualquer reenvio, pois a entrega pode ter ocorrido. A idempotência é por alerta e modo. O modo padrão é `simulated`.

## Demonstração pública

O modo `PUBLIC_DEMO=true` mantém somente consultas e uma prévia de investigação por regras. Os dados devem continuar sintéticos; não coloque chaves, credenciais ou dados reais nesse ambiente. A estratégia gratuita proposta é um serviço Docker no Render com frontend e API no mesmo domínio e PostgreSQL Free no Neon. **Nenhum deploy foi realizado.** O [guia de publicação futura](docs/public-demo.md) descreve a preparação do banco, a configuração segura e os limites dos planos gratuitos.

## Capturas das cinco telas

Capturas integrais feitas com Playwright em viewport desktop de 1440 × 900, após o carregamento da API. O servidor de teste usa uma cópia isolada do SQLite, dados sintéticos e `PUBLIC_DEMO=true`. Por isso, a investigação mostra a prévia baseada em regras e o histórico de automações dessa cópia está vazio; as execuções n8n descritas acima foram registradas no PostgreSQL local.

### Visão geral

![Dashboard com indicadores, comparação dos detectores e fluxo financeiro](docs/images/01-dashboard.png)

### Transações

![Livro de movimentações com transações sintéticas carregadas](docs/images/02-transacoes.png)

### Central de anomalias

![Fila de anomalias com prioridades e evidências dos detectores](docs/images/03-anomalias.png)

### Investigação com IA

![Evidências de um alerta sintético e prévia de análise baseada em regras](docs/images/04-investigacao-ia.png)

### Automações

![Fluxo de notificações simuladas e histórico da cópia isolada](docs/images/05-automacoes.png)

## Qualidade e comandos úteis

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

O teste de navegador usa uma cópia descartável do SQLite, servidor local na porta 8001 e uma chave exclusivamente de teste. Capturas integrais ficam em `artifacts/` e são ignoradas pelo Git. Para repetir as duas verificações públicas, execute `$env:PUBLIC_DEMO='true'; .\.venv\Scripts\python.exe scripts\verify_browser.py public-demo.spec.ts` em um novo PowerShell. O navegador testa as cinco telas em desktop e mobile, filtros, paginação, investigação por regras, estado vazio, recuperação de falha de API e ausência de ações administrativas no modo público. A validação em aparelho físico, SMTP real e PostgreSQL gerenciado permanece pendente. `npm audit` aponta uma vulnerabilidade alta de ReDoS em `picomatch`, presente apenas nas ferramentas de desenvolvimento; ainda não havia correção na [advisory consultada](https://github.com/advisories/GHSA-fc5q-39xc-vjpf). O build estático gerado não inclui essa dependência. Verifique um patch antes de atualizar ou expor ferramentas de build a padrões glob de origem não confiável.

Validação local em 18/11/2026: **52 testes pytest** e **7 testes Vitest** passaram; typecheck, ESLint, Ruff e a compilação do frontend também passaram. A validação anterior incluiu seis fluxos Playwright (quatro locais e dois públicos). Nesta rodada, Docker Compose iniciou PostgreSQL, FastAPI e n8n; o workflow foi importado e executado três vezes no n8n, com **141 notificações simuladas, 141 alertas distintos, 141 tentativas e zero falhas de entrega**. Uma quarta tentativa inicial do CLI falhou por conflito na porta interna do task broker, antes de chamar o backend; a execução com portas internas exclusivas funcionou. Chrome confirmou os registros na página Automações e o resumo na página inicial sem erro no console. O agendamento não foi ativado. Na auditoria anterior, `npm audit --omit=dev` e `pip-audit` sobre `backend/requirements.lock.txt` retornaram zero vulnerabilidades; o audit completo do npm apontou entradas altas encadeadas a `picomatch` nas dependências de desenvolvimento. Não houve validação em dispositivo móvel físico nem PostgreSQL gerenciado.

O dataset é demonstrativo, não contém dados financeiros reais e não oferece decisão automática ou aconselhamento financeiro. O corte temporal e as regras foram escolhidos para a simulação; métricas podem mudar com seed, versão do algoritmo ou dependências.

