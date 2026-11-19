# Publicação futura da demonstração

O projeto ainda não foi publicado. Para preservar a arquitetura, a opção gratuita mais simples é **um Web Service Docker no Render**, servindo FastAPI e o frontend compilado no mesmo domínio, ligado a **um PostgreSQL gratuito no Neon**. Isso dispensa CORS e evita a perda do SQLite quando o serviço reinicia. O banco deve conter somente os dados sintéticos do projeto.

## Preparação local

1. Execute os testes, lint, typecheck e build descritos no README. Confira também `npm audit --omit=dev` e a auditoria das versões Python. Não envie `.env`, credenciais ou o banco local ao repositório.
2. Crie um projeto PostgreSQL vazio no Neon, em uma região próxima à do serviço. Guarde a URL de conexão como segredo; no Python, use o prefixo `postgresql+psycopg://` e `sslmode=require`. Configure essa URL temporariamente em `DATABASE_URL` no ambiente local e execute `.\.venv\Scripts\python.exe -m backend.app.cli init` **uma vez** para migrar, inserir as 50.000 transações sintéticas e persistir o pipeline. Confirme que uma segunda execução é idempotente. Se quiser mostrar histórico na página **Automações**, mantenha `NOTIFICATION_MODE=simulated`, inicie a API somente em `127.0.0.1` com a chave administrativa local e execute a automação uma vez pela interface; ela registrará entregas simuladas e deduplicadas no Neon. Pare a API e remova a URL do ambiente local antes de publicar.
3. Verifique no banco a contagem de 50.000 transações, 602 candidatos da união e as métricas do README. O modo público seleciona **regras** por padrão; os candidatos de Isolation Forest e da união permanecem consultáveis.

## Configuração proposta no Render

Crie um **Web Service** no plano Free apontando para o Dockerfile da raiz. O container respeita `PORT` e, com `PUBLIC_DEMO=true`, aplica somente migrations na partida. Configure como variáveis de ambiente do serviço:

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | URL secreta do Neon, com driver `psycopg` e TLS |
| `PUBLIC_DEMO` | `true` |
| `NOTIFICATION_MODE` | `simulated` |
| `GEMINI_API_KEY` | ausente |
| `FINOPS_ADMIN_KEY` | ausente |
| `SMTP_*` | ausentes |

Com `PUBLIC_DEMO=true`, a aplicação rejeita configuração de Gemini ou SMTP real, não registra rotas de escrita nem `/api/automations/pending`, e remove controles administrativos da interface. A investigação por regras fica disponível como **prévia de leitura**, sem criar histórico; Gemini e notificações reais não são acionados. Antes de divulgar a URL, confira `GET /api/health` (`public_demo: true`), o OpenAPI (sem rotas administrativas), o estado do banco e os fluxos no navegador. Não exponha o editor n8n nem a URL do PostgreSQL.

## Custos e limites a conferir antes de ativar

Em 18/11/2026, a [documentação do Render Free](https://render.com/docs/free) informa suspensão após 15 minutos sem tráfego, retomada que pode levar cerca de um minuto, 750 horas de instância por workspace/mês, filesystem efêmero e limite de 512 MB de RAM. O banco PostgreSQL gratuito do próprio Render expira após 30 dias; por isso a proposta usa Neon. O [plano Free do Neon](https://neon.com/docs/introduction/plans) informa 1 GB por projeto, 100 CU-horas por projeto/mês, 5 GB de transferência pública e suspensão do compute após inatividade. Limites e políticas podem mudar; confira as páginas antes de criar contas ou adicionar método de pagamento.

O serviço gratuito não oferece latência previsível, alta disponibilidade nem capacidade para tráfego intenso. O consumo de memória do pipeline de ML, a migração no Neon e o build Docker **não foram medidos no Render**. Se o plano não suportar a carga ou os custos não forem aceitáveis, não publique até medir e ajustar a implantação. A aplicação foi desenhada para dados sintéticos e leitura pública; não é um serviço financeiro de produção.
