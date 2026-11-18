# Travel API — Etapa 1

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

Com os models criados e importados em `alembic/env.py`, gere e aplique a primeira migration:

```bash
alembic revision --autogenerate -m "create initial tables"
alembic upgrade head
```

Na etapa 1 ainda não existem models de negócio, portanto não gere uma migration vazia. A primeira migration será criada depois da etapa de modelagem.

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
- A autenticação, RBAC, rate limiting e módulos de negócio serão implementados nas próximas etapas.
