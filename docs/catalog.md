# Catálogo: destinos e pacotes

## Destinos

### Endpoints públicos

- `GET /api/v1/destinations`: lista somente destinos ativos; aceita `q`, `country`, `state`, `page`, `limit` e `sort_order`.
- `GET /api/v1/destinations/{destination_id}`: consulta um destino ativo.

### Endpoints administrativos

- `GET /api/v1/admin/destinations`: lista destinos ativos e inativos; aceita `is_active`.
- `GET /api/v1/admin/destinations/{destination_id}`: consulta um destino independentemente do status.
- `POST /api/v1/admin/destinations`: cadastra destino.
- `PATCH /api/v1/admin/destinations/{destination_id}`: atualiza parcialmente um destino.
- `DELETE /api/v1/admin/destinations/{destination_id}`: desativa logicamente o destino.

Um destino com pacotes ativos associados não pode ser desativado. Desative os pacotes primeiro. O registro nunca é apagado fisicamente, preservando as referências históricas.

## Pacotes de viagem

### Endpoints públicos

- `GET /api/v1/packages`: pesquisa somente pacotes ativos ligados a destinos ativos.
- `GET /api/v1/packages/{package_id}`: consulta um pacote ativo.

Filtros combináveis:

| Parâmetro | Significado |
|---|---|
| `q` | Busca textual em título, descrição, origem e destino |
| `origin_id` | UUID do destino de partida |
| `destination_id` | UUID do destino de chegada |
| `departure_from` / `departure_to` | Intervalo da data de partida |
| `min_price` / `max_price` | Faixa de preço |
| `min_days` / `max_days` | Duração em dias de calendário, incluindo partida e retorno; a resposta também informa `duration_nights` |
| `page` / `limit` | Paginação; limite máximo de 100 |
| `sort_by` | `departure_date`, `return_date`, `price`, `created_at` ou `title` |
| `sort_order` | `asc` ou `desc` |

Exemplo:

```http
GET /api/v1/packages?origin_id=UUID&destination_id=UUID&departure_from=2026-12-01&min_price=500&max_price=3000&min_days=3&page=1&limit=20&sort_by=price&sort_order=asc
```

### Endpoints administrativos

- `GET /api/v1/admin/packages`: lista pacotes ativos e inativos; aceita os filtros públicos e o filtro administrativo `is_active`.
- `GET /api/v1/admin/packages/{package_id}`: consulta pacote, incluindo custo interno.
- `POST /api/v1/admin/packages`: cria pacote; vagas disponíveis começam iguais ao total de vagas.
- `PATCH /api/v1/admin/packages/{package_id}`: atualiza parcialmente um pacote.
- `DELETE /api/v1/admin/packages/{package_id}`: desativa logicamente o pacote.

A role ADMIN é exigida em todos os endpoints administrativos. O custo (`cost_price`) e o usuário criador nunca são expostos nos endpoints públicos.

Quando o total de vagas é alterado, a quantidade já vendida/reservada é preservada. O novo total não pode ficar abaixo da quantidade já comprometida. Origem, destino e datas não podem ser alterados após existir compra vinculada; crie um novo pacote para um novo itinerário. A compra mantém snapshots independentes para preservar o histórico.

A migration `20261118_0002_destination_location_ci.py` adiciona um índice único funcional para impedir duplicidade de localização mesmo com diferenças entre maiúsculas/minúsculas e com `state` nulo. Aplique-a após atualizar o código com `alembic upgrade head`. Se já houver destinos cadastrados com a mesma localização em variações de caixa, consolide esses registros antes da migration.

## Cache

As consultas públicas de destinos e pacotes utilizam Redis como cache best-effort. Chaves usam prefixos `cache:destinations:*` e `cache:packages:*` e TTLs configuráveis por `DESTINATIONS_CACHE_TTL_SECONDS` e `PACKAGES_CACHE_TTL_SECONDS`.

Após criação, atualização ou desativação administrativa, o serviço invalida o prefixo correspondente. Alterações de destino também invalidam o cache de pacotes. A invalidação utiliza `SCAN` + `UNLINK`, nunca `KEYS`. Se Redis estiver indisponível, consultas seguem ao PostgreSQL e o cache expirará pelo TTL; PostgreSQL permanece como fonte da verdade.

## Respostas paginadas

Listagens retornam `items`, `total`, `page`, `limit` e `pages`. Quando não há resultados, `pages` é `0` e `items` é uma lista vazia.
