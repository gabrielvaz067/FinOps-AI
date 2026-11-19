# n8n local com FinOps AI

O workflow `automation/critical-alerts.n8n.json` é opcional. Para uso pessoal, o n8n Community auto-hospedado não exige licença paga; a infraestrutura é responsabilidade de quem executa a instância. Este guia usa apenas Docker Desktop local e notificações simuladas.

1. Configure `.env` na raiz com `FINOPS_ADMIN_KEY`, `POSTGRES_PASSWORD` e `N8N_ENCRYPTION_KEY` fortes. O arquivo já é ignorado pelo Git e excluído do build Docker. Mantenha `NOTIFICATION_MODE=simulated` e `PUBLIC_DEMO=false` (ou ausente). Não copie credenciais para o frontend nem para o JSON do workflow.
2. Confira a configuração sem imprimir os segredos: `docker info` e `docker compose --profile automation config --quiet`. Inicie apenas os serviços necessários: `docker compose --profile automation up -d --build postgres app n8n`. Os volumes `postgres_data` e `n8n_data` persistem; não use `down -v` para este teste. Aguarde `docker compose --profile automation ps` mostrar PostgreSQL saudável e confirme `http://127.0.0.1:8000/api/health` e `http://localhost:5678`.
3. Na primeira abertura do n8n, crie o usuário proprietário local e guarde a senha fora do repositório. Nesta instância de validação, a conta local foi criada com endereço `finops-local@example.invalid`; a senha aleatória está somente no `.env` local em `N8N_LOCAL_OWNER_PASSWORD`. Faça login no editor para inspecionar o fluxo.
4. Importe `automation/critical-alerts.n8n.json` pelo editor ou pelo [CLI do n8n](https://docs.n8n.io/deploy/host-n8n/configure-n8n/use-the-command-line.md). O workflow permanece inativo após a importação. Crie uma credencial **Header Auth** no n8n com nome de cabeçalho `X-Admin-Key` e valor de `FINOPS_ADMIN_KEY` do `.env`, e vincule-a ao nó **Notificar e registrar no FinOps**. A chave fica criptografada no armazenamento de credenciais do n8n; o JSON exportado não a contém.
5. Execute o gatilho manual no editor. A consulta usa `http://app:8000` na rede interna do Compose e traz até 100 alertas críticos sintéticos detectados por regras. O backend exclui entregas concluídas, impõe unicidade por alerta e modo e registra cada tentativa. Consulte a página **Automações** no FinOps AI ou `GET /api/automations`. Repetir o workflow com a fila vazia não cria nova notificação. Ative o agendamento de cinco minutos apenas se quiser operação contínua local.

Na validação de 18/11/2026, Docker Engine 29.9.3, Compose 5.7.0 e n8n 2.48.5 funcionaram. PostgreSQL ficou saudável, n8n respondeu HTTP 200 em `http://localhost:5678` e a API respondeu com `synthetic=true`, `notification_mode=simulated`, `public_demo=false`. A credencial foi importada para o armazenamento do n8n por CLI; o arquivo temporário em texto claro foi removido. O workflow de seis nós foi importado e vinculado à credencial sem incluir a chave no JSON.

| Tentativa no n8n | Duração | Alertas processados | Falhas | Resultado |
| --- | ---: | ---: | ---: | --- |
| CLI inicial | 14,684 s | 0 | 1 falha de execução | Porta interna 5679 do task broker já estava em uso; não houve chamada ao backend. |
| Execução 1 | 29,860 s | 100 | 0 | Concluída. |
| Execução 2 | 56,800 s | 41 | 0 | Concluída. |
| Execução 3, fila vazia | 23,186 s | 0 | 0 | Concluída sem nova chamada de gravação ao backend. |

Para executar pelo CLI com esta versão enquanto o editor está aberto, use um ID de workflow obtido no próprio n8n e portas internas diferentes das do servidor:

```powershell
docker exec --env N8N_RUNNERS_BROKER_PORT=5681 --env N8N_PORT=5682 -u node finops-ai-n8n-1 n8n execute --id=<ID_DO_WORKFLOW>
```

Após as três execuções bem-sucedidas, o PostgreSQL continha **141 notificações simuladas para 141 alertas distintos, com 141 tentativas e nenhuma entrega SMTP**. A página Automações exibiu os dois registros de execução do backend; o painel inicial exibiu a execução #2, com 41 processadas e 0 falhas. A verificação no Chrome não encontrou erros no console. Pytest (52 testes), Vitest (7 testes), Ruff, ESLint, typecheck e build passaram. O workflow segue inativo, sem agendamento publicado.

Uma varredura de 114 arquivos do projeto e artefatos locais não encontrou valores das credenciais do `.env`. Esta cópia não contém metadados `.git`, então não foi possível verificar o índice de arquivos rastreados. Antes de publicar em um repositório, confirme que `.env` continua ignorado.

Use este perfil apenas localmente. Com `PUBLIC_DEMO=true`, os endpoints de consulta de pendências e execução não são registrados. Não publique o editor n8n nem exponha as portas 5678, 8000 ou 5432 para a internet.
