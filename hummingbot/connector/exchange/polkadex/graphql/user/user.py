import json

from gql import gql
from gql.transport.exceptions import TransportQueryError

from hummingbot.connector.exchange.polkadex.graphql.auth.client import execute_query_command

async def cancel_order(params, url, api_key):
    mutation = gql(
        """
    mutation CancelOrder($input: UserActionInput!) {
        cancel_order(input: $input)
    }
        """
    )
    print("params: ", params)
    encoded_params = json.dumps({"CancelOrder": params});
    variables = {"input": {"payload": encoded_params}}
    try:
        result = await execute_query_command(mutation, variables, url, api_key)
        print("Cancel order result: ", result)
        return result["cancel_order"]
    except TransportQueryError as executionErr:
        print("Error while cancelling orders: ", executionErr.errors)
        raise Exception("TransportQueryError")


async def place_order(params, url, api_key):
    try:
        mutation = gql(
            """
        mutation PlaceOrder($input: UserActionInput!) {
            place_order(input: $input)
        }
            """
        )
        encoded_params = json.dumps({"PlaceOrder": params})

        variables = {"input": {"payload": encoded_params}}
        
        result = await execute_query_command(mutation, variables, url, api_key)
        return result["place_order"]
    except:
        raise Exception("PlaceOrder Query Failed")



#working as expected
async def get_all_balances_by_main_account(main, endpoint, api_key):
    query = gql(
        """
query getAllBalancesByMainAccount($main: String!) {
  getAllBalancesByMainAccount(main_account: $main) {
    items {
      a
      f
      r
    }
  }
}
""")
    variables = {"main": main}

    result = await execute_query_command(query, variables, endpoint, api_key)
    return result["getAllBalancesByMainAccount"]["items"]



async def find_order_by_main_account(main, order_id, market, endpoint, api_key):
    # TODO: Should We change this to client order id???
    query = gql(
        """
query findOrderByMainAccount($main: String!, $market: String!, $order_id: String!) {
  findOrderByMainAccount(main_account: $main, market: $market, order_id: $order_id) {
    afp
    cid
    fee
    fq
    id
    m
    ot
    p
    q
    s
    st
    t
    u
  }
}
""")
    variables = {"order_id": order_id, "market": market, "main": main}
    result = await execute_query_command(query, variables, endpoint, api_key)
    return result["findOrderByMainAccount"]

async def get_main_acc_from_proxy_acc(proxy, endpoint, api_key):
    query = gql(
        """
query findUserByProxyAccount($proxy_account: String!) {
  findUserByProxyAccount(proxy_account: $proxy_account) {
    items
  }
}
""")
    variables = {"proxy_account": proxy}

    result = await execute_query_command(query, variables, endpoint, api_key)
    main = result["findUserByProxyAccount"]["items"][0].split(",")[2][11:-1]
    print("FindUser by proxy result: ", main)
    # TODO: Handle error if main account not found
    return main

