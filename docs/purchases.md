# Etapa 5 — Compras e pagamentos simulados

## Endpoints

Todas as rotas abaixo ficam sob `/api/v1` e exigem usuário autenticado com role `CLIENT`.

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/purchases/checkout` | Executar checkout simulado |
| GET | `/purchases/me` | Listar compras do cliente |
| GET | `/purchases/me/{purchase_id}` | Consultar uma compra própria |
| POST | `/purchases/me/{purchase_id}/cancel` | Cancelar compra confirmada e simular estorno |

## Checkout

O endpoint `POST /api/v1/purchases/checkout` exige o header `Idempotency-Key` (16 a 128 caracteres). Recomenda-se UUID aleatório por intenção de compra.

Exemplo:

```http
POST /api/v1/purchases/checkout
Authorization: Bearer <access_token>
Idempotency-Key: 08f777aa-7c2b-4637-a20d-9e52f87d1e49
Content-Type: application/json
```

```json
{
  "package_id": "2e2cded0-bb50-4fa6-bab0-c39511f927f9",
  "quantity": 2,
  "card": {
    "cardholder_name": "Cliente de Teste",
    "card_number": "SIMULATED-CARD-NUMBER",
    "expiry_month": "MM",
    "expiry_year": "YYYY",
    "cvv": "SIMULATED-CVV"
  }
}
```

A simulação não valida a autenticidade dos dados de cartão: ao receber os campos, o pagamento é aprovado automaticamente. O número, vencimento e CVV são recebidos somente para representar o formulário e **não são persistidos, retornados nem incluídos no fingerprint de idempotência**. Não utilize dados reais de cartão neste projeto.

O fingerprint considera `package_id`, `quantity` e método de pagamento. Repetir a mesma chave com a mesma intenção retorna a compra já criada; reutilizá-la com outra intenção retorna `409 Conflict`.

## Integridade e concorrência

O checkout realiza uma transação PostgreSQL:

1. Busca uma compra anterior com a mesma chave de idempotência.
2. Bloqueia a linha do pacote com `SELECT ... FOR UPDATE`.
3. Confere se o pacote está ativo, se a viagem ainda não começou e se há vagas.
4. Confere viagens confirmadas/concluídas do cliente que cruzem o período.
5. Cria `PurchaseModel` e `PaymentModel` como `CONFIRMED` e `APPROVED`.
6. Decrementa `available_seats`.
7. Confirma tudo em um único commit.

A constraint GiST `excl_purchases_user_travel_period` continua sendo a proteção definitiva contra duas viagens sobrepostas do mesmo usuário, inclusive quando checkouts de pacotes diferentes ocorrem em paralelo. A verificação no service fornece uma mensagem amigável; a constraint trata a corrida.

O administrador também bloqueia a linha do pacote ao editar ou desativar o registro, evitando sobrescrever uma alteração de vagas feita por checkout concorrente.

## Cancelamento

O cancelamento é permitido somente quando:

- a compra pertence ao usuário autenticado;
- a compra está `CONFIRMED`;
- a data de partida ainda não chegou;
- o pagamento está `APPROVED`.

O processo bloqueia o pacote e a compra, muda a compra para `CANCELLED`, o pagamento para `REFUNDED` e devolve a quantidade de vagas. Tudo ocorre na mesma transação. O estorno também é apenas simulado; não há integração com adquirente.

## Respostas

O retorno da compra contém os valores e período contratados, os dados resumidos do pacote e os metadados do pagamento (`transaction_reference`, status e data). Não retorna `cost_amount`, dados de cartão ou CVV.

## Migration

A revisão `20261118_0003` adiciona `idempotency_key` e `idempotency_fingerprint` a `purchases` e cria a restrição única `(user_id, idempotency_key)`. As colunas são nullable para preservar registros antigos; o endpoint de checkout exige a chave em novas compras.

Aplicar com:

```bash
alembic upgrade head
```
