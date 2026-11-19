# Perfil e administração de clientes

## Perfil do usuário autenticado

### `GET /api/v1/users/me`

Retorna os dados do usuário associado ao Access Token atual. A rota atende CLIENT e ADMIN.

### `PATCH /api/v1/users/me`

Atualiza somente os campos enviados entre `name`, `email` e `cpf`. É um PATCH parcial; envie ao menos um campo.

Exemplo:

```json
{
  "name": "Maria da Silva",
  "email": "maria@example.com",
  "cpf": "529.982.247-25"
}
```

O CPF é normalizado para 11 dígitos e validado pelos dígitos verificadores. O email é normalizado para minúsculas. `role`, `is_active`, `password_hash` e demais campos não fazem parte do schema e são rejeitados (`extra=forbid`).

A atualização sempre usa o `user_id` obtido do usuário autenticado. O cliente não consegue informar o ID de outro usuário para alterar seu perfil.

## Administração de clientes

Todas as rotas seguintes exigem `role=ADMIN` verificada a partir do PostgreSQL.

### `GET /api/v1/admin/users`

Parâmetros:

- `page` (padrão 1) e `limit` (padrão 20, máximo 100);
- `q`: busca parcial por nome, email ou CPF;
- `is_active`: filtra clientes ativos/inativos;
- `created_from` e `created_to`: período de cadastro (`YYYY-MM-DD`);
- `sort_by`: `created_at`, `name` ou `email`;
- `sort_order`: `asc` ou `desc`.

A consulta sempre filtra `role=CLIENT`; administradores não aparecem na listagem de clientes.

### `GET /api/v1/admin/users/{user_id}`

Retorna os dados pessoais do cliente e `purchases_count`. Não retorna hash de senha. IDs que não correspondem a clientes retornam `404`.

### `GET /api/v1/admin/users/{user_id}/purchases`

Retorna compras do cliente com paginação e filtros opcionais `status`, `departure_from` e `departure_to`. A rota é somente leitura.

Não existe rota `PATCH` ou `DELETE` administrativa para alterar dados de clientes nesta etapa. O cliente altera os próprios dados através de `/users/me`.

## Integridade

A atualização verifica email e CPF existentes excluindo o próprio usuário da consulta. Em caso de corrida entre requisições, as constraints/índices únicos no PostgreSQL continuam sendo a proteção final; violações são convertidas em `409 Conflict`.

Nenhuma migration é necessária para esta etapa.
