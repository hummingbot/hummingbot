from gql import gql

from hummingbot.connector.exchange.polkadex.graphql.auth.client import subscribe_query_command


async def on_balance_update(main, session, callback):
    query = gql(
        """
subscription onBalanceUpdate($main: String!) {
  onBalanceUpdate(main_account: $main) {
    asset
    free
    pending_withdrawal
    reserved
  }
}
""")
    variables = {"main": main}

    async for result in session.subscribe(query, variable_values=variables, parse_result=True):
        callback(result)


async def on_order_update(main, session, callback):
    query = gql(
        """
subscription onOrderUpdate($main: String!) {
  onOrderUpdate(main_account: $main) {
    avg_filled_price
    fee
    filled_quantity
    id
    m
    order_type
    price
    qty
    side
    status
  }
}
""")
    variables = {"main": main}

    async for result in session.subscribe(query, variable_values=variables, parse_result=True):
        callback(result)


async def on_create_trade(main, session, callback):
    query = gql(
        """
subscription onCreateTrade($main: String!) {
  onCreateTrade(main_account: $main) {
    m
    p
    q
    s
    time
  }
}
""")
    variables = {"main": main}

    async for result in session.subscribe(query, variable_values=variables, parse_result=True):
        callback(result)


async def on_transaction_update(main, callback, host, proxy_addr):
    query = gql(
        """
subscription onUpdateTransaction($main: String!) {
  onUpdateTransaction(main_account: $main) {
    amount
    asset
    fee
    status
    time
    txn_type
  }
}


""")
    variables = {"main": main}

    await subscribe_query_command(query, variables, callback, host, proxy_addr)
