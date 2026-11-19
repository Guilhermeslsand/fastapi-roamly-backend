# Travel API — Etapas 1, 2, 3 e 4

Base inicial de uma API de viagens com FastAPI, PostgreSQL, SQLAlchemy síncrono, Alembic e Redis.

## Requisitos

- Python 3.12+
- Docker Engine e Docker Compose plugin
- Git (recomendado)

## 1. Preparar ambiente

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Edite `.env` e altere `POSTGRES_PASSWORD` e a senha presente em `DATABASE_URL` para o mesmo valor.

## 2. Subir PostgreSQL e Redis

Com toda a stack (API, PostgreSQL e Redis) no Docker:

```bash
docker compose up --build -d
```

Logs da API:

```bash
docker compose logs -f api
```

Alternativamente, suba somente a infraestrutura e execute a API localmente:

```bash
docker compose up -d db redis
uvicorn app.main:app --reload
```

## 3. Verificar a aplicação

- Swagger: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness (PostgreSQL + Redis): http://localhost:8000/api/v1/health/ready

A rota `health/ready` deve responder com `status=ready`, `database=connected` e `redis=connected`.

## 4. Alembic

O `alembic/env.py` já lê `DATABASE_URL` do `.env` e usa `Base.metadata`.

A migration inicial da etapa 2 já está versionada. Aplique-a com:

```bash
alembic upgrade head
```

Para revisar o SQL que será executado sem alterar o banco:

```bash
alembic upgrade head --sql
```

Se estiver executando Alembic dentro do container da API:

```bash
docker compose exec api alembic upgrade head
```

## 5. Comandos úteis

```bash
docker compose ps
docker compose logs -f db redis
docker compose down
```

Para apagar também os dados persistidos dos volumes (ação destrutiva):

```bash
docker compose down -v
```

## Decisões desta base

- SQLAlchemy 2.x em modo síncrono, com uma sessão por requisição.
- Driver PostgreSQL `psycopg` 3.
- Redis síncrono (`redis-py`), compatível com a estratégia síncrona da aplicação.
- Redis e PostgreSQL são dependências separadas; PostgreSQL permanece como fonte da verdade.
- A autenticação, RBAC, rate limiting e catálogo de destinos/pacotes estão implementados nas etapas seguintes.

## Etapa 2 — Domains, Models e migration inicial

A modelagem de domínio e persistência está em `app/domains` e `app/modules`:

- `app/domains`: entidades e enums independentes do SQLAlchemy.
- `app/modules/*/models.py`: models ORM do SQLAlchemy.
- `app/modules/models.py`: importa todos os models para registrar as tabelas no `Base.metadata` do Alembic.
- `docs/data-model.md`: decisões e relacionamentos do banco.
- `alembic/versions/20261118_0001_initial_domain.py`: migration inicial das cinco tabelas.

Com PostgreSQL e Redis iniciados, execute a migration:

```bash
alembic upgrade head
```

Confira a revisão aplicada:

```bash
alembic current
```

Execute os testes de domínio e metadata:

```bash
pytest
```

Para voltar a migration anterior (em ambiente de desenvolvimento, pois isso remove as tabelas):

```bash
alembic downgrade base
```

A migration habilita a extensão PostgreSQL `btree_gist`, necessária à constraint de exclusão que impede compras confirmadas/concluídas com períodos sobrepostos para o mesmo usuário. A extensão não é removida no downgrade por poder ser compartilhada por outras tabelas.

## Etapa 3 — Autenticação e segurança

### Configuração

Gere uma chave JWT e configure o `.env`:

```bash
openssl rand -hex 32
```

Defina o resultado em `JWT_SECRET_KEY`. Os demais parâmetros (`JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_MINUTES` e `REFRESH_TOKEN_DAYS`) possuem valores de desenvolvimento no `.env.example`.

Instale as novas dependências:

```bash
pip install -r requirements.txt
```

### Endpoints implementados

| Método | Endpoint | Acesso |
|---|---|---|
| POST | `/api/v1/auth/register` | Público — cria CLIENT |
| POST | `/api/v1/auth/login` | Público |
| POST | `/api/v1/auth/refresh` | Refresh token no body |
| POST | `/api/v1/auth/logout` | Access token |
| POST | `/api/v1/auth/logout-all` | Access token |
| GET | `/api/v1/auth/me` | Access token |
| POST | `/api/v1/admin/admins` | ADMIN autenticado cria outro ADMIN |

O cadastro e o login retornam access token, refresh token e dados públicos do usuário. O refresh token é de uso único e deve ser substituído em cada renovação. A rotação atualiza os identificadores dos dois tokens na sessão; assim, o access token anterior também deixa de funcionar imediatamente. Uma tentativa de reutilizar um refresh token revoga a sessão inteira. Evite chamadas concorrentes no frontend (implemente single-flight refresh).

### Testar autenticação

Depois de iniciar PostgreSQL e Redis, e aplicar a migration da etapa 2:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Abra `http://localhost:8000/docs` para testar cadastro, login, refresh e logout.

Para criar o primeiro administrador (bootstrap):

```bash
python -m app.scripts.create_admin
```

O comando solicita nome, email, CPF e senha no terminal, sem expor senha nos argumentos do processo. Ele só funciona enquanto ainda não existir um ADMIN. Depois do bootstrap, um administrador autenticado cria outros pela rota `POST /api/v1/admin/admins`. O cadastro público não permite escolher `role`.

### Dependências protegidas e RBAC

- `get_current_user`: valida JWT, verifica `sid` no Redis e busca usuário ativo no PostgreSQL.
- `require_roles(UserRole.ADMIN)`: autoriza apenas administradores.
- `require_roles(UserRole.CLIENT)`: autoriza apenas clientes.
- A role vigente é consultada no banco em cada requisição protegida; o claim de role do JWT não é usado como fonte de autorização.

Exemplo para as próximas rotas administrativas:

```python
@router.get("/admin/example")
def admin_example(
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN)),
):
    ...
```

### Rate limiting

O `RateLimitMiddleware` utiliza Redis e aplica limites por IP: login 5/min, cadastro 5/min, refresh 10/min e demais rotas da API 120/min. Health checks e requisições CORS preflight não entram na contagem. Se Redis estiver indisponível, o rate limiting falha aberto para não derrubar endpoints públicos; autenticação, por sua vez, falha fechada porque exige validar a sessão no Redis.

Detalhes dos contratos e decisões: `docs/authentication.md`.

### Testes

```bash
pytest
```


## Etapa 4 — Destinos e pacotes de viagens

A etapa 4 implementa o catálogo público e a administração de destinos e pacotes. Consulte `docs/catalog.md` para os contratos completos, filtros, regras de atualização e estratégia de cache.

### Principais endpoints

| Método | Endpoint | Acesso |
|---|---|---|
| GET | `/api/v1/destinations` | Público — destinos ativos |
| GET | `/api/v1/destinations/{id}` | Público — destino ativo |
| GET | `/api/v1/admin/destinations` | ADMIN |
| POST | `/api/v1/admin/destinations` | ADMIN |
| PATCH | `/api/v1/admin/destinations/{id}` | ADMIN |
| DELETE | `/api/v1/admin/destinations/{id}` | ADMIN — desativação lógica |
| GET | `/api/v1/packages` | Público — pesquisa de pacotes ativos |
| GET | `/api/v1/packages/{id}` | Público — pacote ativo |
| GET | `/api/v1/admin/packages` | ADMIN |
| POST | `/api/v1/admin/packages` | ADMIN |
| PATCH | `/api/v1/admin/packages/{id}` | ADMIN |
| DELETE | `/api/v1/admin/packages/{id}` | ADMIN — desativação lógica |

A pesquisa aceita `q`, `origin_id`, `destination_id`, `departure_from`, `departure_to`, `min_price`, `max_price`, `min_days`, `max_days`, `page`, `limit`, `sort_by` e `sort_order`. `min_days`/`max_days` contam dias de calendário, incluindo partida e retorno; a resposta também informa `duration_nights`. O máximo de itens por página é 100.

O custo interno (`cost_price`) só aparece nas respostas administrativas. Os endpoints públicos retornam preço de venda e informações dos destinos.

### Cache do catálogo

O Redis armazena respostas públicas por TTL configurável (`DESTINATIONS_CACHE_TTL_SECONDS` e `PACKAGES_CACHE_TTL_SECONDS`). Após alteração administrativa, os serviços invalidam as chaves correspondentes com `SCAN` + `UNLINK`. Se Redis estiver indisponível, as consultas seguem ao PostgreSQL; falha de cache não substitui nem compromete a fonte da verdade.

### Regras de negócio aplicadas

- Destinos e pacotes são desativados logicamente; não há exclusão física.
- Destino com pacotes ativos associados não pode ser desativado.
- Pacote só pode ser criado com origem e destino existentes e ativos.
- Ao alterar capacidade, vagas já vendidas/reservadas são preservadas.
- Capacidade não pode ser reduzida abaixo da quantidade vendida/reservada.
- Itinerário (origem, destino e período) não pode ser alterado após haver compra vinculada.
- A migration `20261118_0002_destination_location_ci.py` adiciona unicidade case-insensitive para nome/país/estado, inclusive quando estado é nulo.

Testes da etapa 4:

```bash
pytest -q tests/test_domain_entities.py tests/test_database_metadata.py tests/unit/test_auth_schemas.py tests/unit/test_catalog_schemas.py tests/unit/test_catalog_repositories.py
```
