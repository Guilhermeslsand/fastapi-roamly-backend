# Etapa 7 — Dashboard administrativo e calendário do cliente

## Dashboard administrativo

Todas as rotas abaixo exigem Access Token válido e role `ADMIN`.

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/v1/admin/dashboard/overview` | Indicadores resumidos |
| GET | `/api/v1/admin/dashboard/revenue` | Série de receita e lucro bruto |
| GET | `/api/v1/admin/dashboard/sales` | Série de vendas e unidades vendidas |
| GET | `/api/v1/admin/dashboard/destinations` | Destinos mais vendidos |
| GET | `/api/v1/admin/dashboard/packages` | Pacotes com mais vendas e ocupação atual |

### Filtros por período

Os endpoints aceitam `start_date` e `end_date` no formato `YYYY-MM-DD`. Informe ambos ou omita ambos. Quando omitidos, o serviço utiliza o mês civil atual no fuso `APP_TIMEZONE` (padrão `America/Sao_Paulo`). O período agregado máximo é de cinco anos.

Nas séries de receita e vendas, `group_by=month` é o padrão. `group_by=day` aceita períodos de até 93 dias. A resposta inclui buckets sem vendas com valor zero, facilitando a renderização de gráficos no frontend.

Exemplos:

```http
GET /api/v1/admin/dashboard/overview?start_date=2026-01-01&end_date=2026-11-30
GET /api/v1/admin/dashboard/revenue?start_date=2026-01-01&end_date=2026-11-30&group_by=month
GET /api/v1/admin/dashboard/sales?start_date=2026-11-01&end_date=2026-11-30&group_by=day
GET /api/v1/admin/dashboard/destinations?start_date=2026-01-01&end_date=2026-11-30&limit=5
GET /api/v1/admin/dashboard/packages?start_date=2026-01-01&end_date=2026-11-30&limit=10
```

### Definições dos indicadores

- `revenue`: soma de `purchases.total_amount` para compras `CONFIRMED` ou `COMPLETED` com pagamento `APPROVED`, no período de `purchased_at`.
- `sales_count`: quantidade de transações/compra, não quantidade de passageiros.
- `units_sold`: soma de `purchases.quantity`.
- `average_ticket`: `revenue / sales_count`, calculado por compra.
- `active_clients`: clientes (`role=CLIENT`) ativos no momento da consulta, independentemente do período.
- `new_clients`: clientes cadastrados durante o período, usando `created_at`.
- `gross_profit`: receita menos `cost_amount` registrado nas compras. Se ao menos uma compra do período não tiver custo registrado (`cost_amount IS NULL`), o indicador é `null`, `profit_data_complete=false` e `purchases_without_cost` informa quantos registros estão incompletos. Isso evita apresentar lucro parcial como se fosse lucro real.
- `occupancy_rate` dos pacotes: ocupação atual, calculada por `(total_seats - available_seats) / total_seats * 100`. Ela representa a ocupação vigente do pacote, não apenas as vendas do período filtrado.
- `top_destinations` e `top_packages`: ordenados principalmente por unidades vendidas no período e, em caso de empate, por receita.

Receita e lucro são valores brutos da simulação acadêmica; não consideram impostos, taxas de gateway ou custos operacionais. O projeto não deve chamar esse indicador de lucro líquido.

## Calendário do cliente

| Método | Endpoint | Acesso |
|---|---|---|
| GET | `/api/v1/purchases/me/calendar` | CLIENT autenticado |

Exemplo:

```http
GET /api/v1/purchases/me/calendar?start_date=2026-12-01&end_date=2026-12-31
```

Sem parâmetros, retorna o mês civil atual. Informe as duas datas ou nenhuma; a janela máxima é de 366 dias.

A consulta considera somente compras do próprio usuário com status `CONFIRMED` ou `COMPLETED`. Compras canceladas e pendentes não ocupam o calendário. Uma viagem aparece se o intervalo dela intersectar a janela consultada, mesmo que a partida ou o retorno ocorram fora da janela.

A resposta contém:

- `trips`: detalhes das viagens (pacote, origem, destino, período, quantidade, valor e status).
- `travel_status`: `UPCOMING`, `ONGOING` ou `COMPLETED`, calculado usando `APP_TIMEZONE`.
- `days`: cada dia civil ocupado, incluindo a data de partida e a data de retorno, junto dos IDs das compras que ocupam aquele dia. Datas são limitadas à janela consultada para facilitar a exibição mensal.

## Persistência e migrations

A etapa 7 utiliza somente `purchases`, `payments`, `travel_packages`, `destinations` e `users`, já existentes. Nenhuma migration é necessária.

O dashboard executa agregações no PostgreSQL. O calendário consulta as compras do cliente com eager loading de pacote, origem e destino para evitar N+1 queries. O Redis não é utilizado para esses dados agregados: os resultados são dinâmicos e o PostgreSQL continua como fonte da verdade.

## Testes

```bash
pytest -q tests/unit/test_dashboard_service.py \
  tests/unit/test_calendar_service.py \
  tests/unit/test_dashboard_repository_sql.py \
  tests/unit/test_calendar_repository_sql.py
```

A suíte de repositórios compila as consultas com o dialeto PostgreSQL; testes com banco real devem ser executados também no ambiente Docker de desenvolvimento.
