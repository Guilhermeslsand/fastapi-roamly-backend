# Autenticação e sessões

## Contratos HTTP

### `POST /api/v1/auth/register`

Cadastro público de cliente. A role é sempre definida no backend como `CLIENT`.

```json
{
  "name": "Maria Silva",
  "email": "maria@example.com",
  "cpf": "123.456.789-01",
  "password": "uma-senha-forte"
}
```

Retorna `201 Created` com `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in` e dados públicos do usuário. O cadastro já inicia uma sessão.

### `POST /api/v1/auth/login`

```json
{
  "email": "maria@example.com",
  "password": "uma-senha-forte"
}
```

Retorna `200 OK` com o mesmo formato de resposta do cadastro.

### `POST /api/v1/auth/refresh`

```json
{
  "refresh_token": "<refresh-jwt>"
}
```

Retorna um novo par de tokens. O refresh token anterior é invalidado por compare-and-swap atômico no Redis. Se duas requisições tentarem renovar simultaneamente, somente uma será aceita; uma tentativa de reutilização revoga a sessão inteira. O frontend deve implementar *single-flight refresh* para evitar chamadas concorrentes.

### `POST /api/v1/auth/logout`

Requer `Authorization: Bearer <access-token>`. Revoga a sessão associada ao `sid`, invalidando imediatamente todos os access tokens daquela sessão e impedindo o refresh correspondente.

### `POST /api/v1/auth/logout-all`

Requer access token. Revoga todas as sessões Redis do usuário autenticado.

### `POST /api/v1/admin/admins`

Requer access token de um usuário com role `ADMIN`. Cria outra conta `ADMIN`; o endpoint não cria uma sessão automaticamente. A nova conta deverá autenticar-se em `/auth/login`. O endpoint não aceita role no payload: o próprio endpoint determina `ADMIN`.

### `GET /api/v1/auth/me`

Requer access token. Retorna os dados públicos do usuário autenticado.

## Decisões de segurança

- Senhas são armazenadas com Argon2 por meio de `pwdlib`; nunca armazenar senha em texto puro.
- JWT usa HS256, `iss`, `aud`, `iat`, `nbf`, `exp`, `sub`, `sid`, `jti` e `type`.
- Access token dura 15 minutos por padrão; refresh token dura 7 dias por padrão.
- O Redis armazena sessões, não os JWTs. A chave `auth:session:{sid}` guarda `user_id`, `access_jti`, `refresh_jti` e timestamps. O conjunto `auth:user:{user_id}:sessions` indexa as sessões do usuário.
- A dependência de autenticação compara o `jti` do access token com o `access_jti` da sessão. Após o refresh, o access token anterior também deixa de funcionar imediatamente.
- Toda rota autenticada verifica a existência da sessão no Redis e consulta o usuário no PostgreSQL. Portanto, logout e desativação de usuário têm efeito imediato.
- A role usada no RBAC vem do PostgreSQL, não do claim `role` do JWT.
- O refresh token é de uso único. A rotação usa script Lua para comparar o `refresh_jti` atual e atualizar os `jti` de access e refresh atomicamente.
- O endpoint público de cadastro não aceita o campo `role` e sempre cria `CLIENT`.
- O primeiro administrador é criado via CLI: `python -m app.scripts.create_admin`. O comando CLI permite apenas o bootstrap do primeiro ADMIN. Depois, um ADMIN autenticado pode criar outros administradores em `POST /api/v1/admin/admins`.
- Rate limit usa janela fixa de 60 segundos no Redis, por IP e grupo de rota. O middleware não confia em `X-Forwarded-For`; configure proxy confiável explicitamente antes de expor a API atrás de load balancer.

## Armazenamento no frontend

A resposta retorna os dois tokens em JSON para simplificar a integração do projeto. Em uma aplicação web real, prefira manter o refresh token em cookie `HttpOnly; Secure; SameSite` e o access token apenas em memória. Não persista refresh token em `localStorage`. Se usar cookie, implemente também proteção CSRF conforme a política de domínio e `SameSite` escolhida.

## Geração de chave JWT

```bash
openssl rand -hex 32
```

Coloque o resultado em `JWT_SECRET_KEY` no `.env`. Não reutilize a chave entre ambientes e nunca versione o `.env`.
