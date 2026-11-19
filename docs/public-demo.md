# Demonstração online: Netlify, Render e Neon

A demonstração online foi publicada e conferida em 19/11/2026, com dados exclusivamente sintéticos. **Aplicação:** https://finops-ai-monitor.netlify.app/ · **API:** https://finops-ai-api.onrender.com · **OpenAPI:** https://finops-ai-api.onrender.com/docs. O frontend está no Netlify; a API FastAPI roda no Render Free; o PostgreSQL 17 está no Neon Free. O Docker Compose e o n8n continuam restritos ao ambiente local. Este guia também documenta como reproduzir o deploy.

## 1. Preparar o banco no Neon

Crie um projeto **Free** em região próxima à escolhida no Render. Use a string de conexão **direta** fornecida pelo Neon, sem publicar seu valor. Em `DATABASE_URL`, troque apenas o esquema `postgresql://` por `postgresql+psycopg://` e preserve host, usuário, senha, banco e parâmetros da URL. A conexão deve incluir `sslmode=require`; mantenha também outros parâmetros de segurança fornecidos pelo Neon. A URL é um segredo do backend, nunca uma variável `VITE_`.

Antes do deploy, configure temporariamente essa `DATABASE_URL` no `.env` local, que é ignorado pelo Git, e execute na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m backend.app.cli init
```

Esse comando aplica as migrations, insere as 50.000 transações sintéticas e executa o pipeline. Execute-o **uma vez** para a carga inicial. A função de carga verifica a versão, seed e contagem; uma segunda execução com a mesma base retorna `created: false` e reutiliza o pipeline. Se encontrar uma base diferente ou incompleta, ela falha sem apagar dados. Confirme no banco 50.000 transações, 602 candidatos da abordagem combinada e as métricas descritas no README. Restaure o `DATABASE_URL` local depois da verificação. O serviço Render executará apenas `migrate` nas partidas, sem geração de dados ou treino de ML.

## 2. Criar a API no Render

Crie um **Web Service Free** a partir deste repositório, com estas opções:

| Campo | Configuração |
| --- | --- |
| Branch | `main` |
| Language | `Docker` |
| Root Directory / Docker Context | raiz do repositório (`.`) |
| Dockerfile Path | `./Dockerfile.render` |
| Docker Command | vazio; usa o `CMD` do Dockerfile |
| Health Check Path | `/api/health` |
| Instance | `Free`, um worker |

`Dockerfile.render` instala somente a API e as migrations; o frontend não entra nessa imagem. Ele exige `PUBLIC_DEMO=true` e `DATABASE_URL`, aplica migrations idempotentes e inicia o Uvicorn em `0.0.0.0` na porta `${PORT}` definida pelo Render (padrão local `10000`). O health check retorna 200 somente se a consulta ao banco funcionar.

Configure as variáveis no painel do serviço, sem gravar valores reais no repositório:

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | URL secreta do Neon com `postgresql+psycopg://` e `sslmode=require` |
| `PUBLIC_DEMO` | `true` |
| `NOTIFICATION_MODE` | `simulated` |
| `CORS_ORIGIN` | origem HTTPS **exata** do site Netlify, por exemplo `https://seu-site.netlify.app` |
| `GEMINI_API_KEY`, `FINOPS_ADMIN_KEY`, `SMTP_*` | não configurar |

Não defina `PORT` manualmente. O CORS permite somente `GET` da origem configurada; `https://seu-site.netlify.app.evil.example` e outras origens não recebem autorização. Use o subdomínio final do Netlify; se ele só for conhecido depois de criar o site, atualize `CORS_ORIGIN` no Render antes de divulgar os links. Previews de deploy e domínios personalizados precisam ser avaliados separadamente, sem usar `*`. CORS limita acesso pelo navegador, mas a proteção principal é `PUBLIC_DEMO=true`: as rotas de escrita e `/api/automations/pending` não são registradas. A prévia de investigação usa regras, sem chamada ao Gemini nem gravação. O modo de notificação permanece simulado e nenhum e-mail é enviado.

## 3. Criar o frontend no Netlify

Conecte o mesmo repositório ao Netlify. O `netlify.toml` da raiz define a configuração; confira no painel:

| Campo | Configuração |
| --- | --- |
| Branch | `main` |
| Base directory | `frontend` |
| Build command | `npm run build` |
| Publish directory | `dist` (relativo a `frontend`) |
| Node.js | `24` |
| SPA routing | `/*` → `/index.html` com status `200` |

Defina **somente** `VITE_API_BASE_URL=https://seu-servico.onrender.com` nas variáveis de build do Netlify, sem `/api` no final e sem barra final. Essa URL é pública por natureza e é incorporada ao JavaScript compilado. Nunca use o prefixo `VITE_` para chaves, senhas ou `DATABASE_URL`. O mesmo valor direciona as consultas `/api/...` e o link da documentação `/docs` para o Render. Localmente, sem essa variável, o frontend continua usando `/api` e o proxy do Vite. Alterar `VITE_API_BASE_URL` requer novo build do frontend.

## 4. Verificação antes de divulgar os links

1. Confirme `GET https://seu-servico.onrender.com/api/health`: `status=ok`, `synthetic=true`, `public_demo=true`, `gemini_available=false`, `notification_mode=simulated`.
2. Confira o OpenAPI: não deve listar `POST /api/pipeline/run`, `POST /api/automations/run`, `POST /api/anomalies/{id}/investigate` nem `GET /api/automations/pending`.
3. Abra as cinco páginas do Netlify, teste filtros, gráficos, paginação, prévia por regras e o link da documentação. Confira no navegador se as requisições vão apenas ao domínio Render configurado e se não há erros de CORS.
4. Verifique que não aparecem credenciais, dados reais ou controles administrativos. O histórico de n8n do PostgreSQL local não estará no Neon, salvo se for gerado ali deliberadamente em ambiente privado.

## Limites conhecidos dos planos gratuitos

O [Render Free](https://render.com/docs/free) suspende o serviço após 15 minutos sem tráfego; a retomada pode levar cerca de um minuto. Há 750 horas de instância por workspace/mês, filesystem efêmero e restrições de tráfego de saída. A [tabela de preços](https://render.com/pricing) informa 512 MB de RAM no serviço Free. Em contêiner local, a API em repouso usou cerca de **177 MiB**; partida a frio, pico de memória, build Docker e consulta ao Neon **não foram medidos no Render**. A geração e o treino das 50.000 transações devem ocorrer fora do Render; caso a memória ou a inicialização excedam os limites, não faça upgrade automático.

O [Neon Free](https://neon.com/docs/introduction/plans) informa 1 GB de armazenamento por projeto, 100 CU-horas por projeto/mês, 5 GB de transferência pública e suspensão do compute após inatividade. O [Netlify Free](https://www.netlify.com/pricing/) informa 300 créditos por mês; ao atingir o limite, projetos podem pausar até o próximo ciclo. Confira os limites e as configurações de cobrança de cada conta antes de criar os serviços. Disponibilidade, latência e custos futuros dependem dos provedores; esta configuração é para portfólio, não para operação financeira.
