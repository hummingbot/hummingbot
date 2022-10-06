from gql import gql

from hummingbot.connector.exchange.polkadex.graphql.auth.client import subscribe_query_command


async def websocket_streams_session_provided(name, session, callback, params=None):
    # print("in websocket_streams_session_provided")
    query = gql(
        """
subscription WebsocketStreamsMessage($name: String!) {
  websocket_streams(name: $name) {
    data
  }
}
""")
    # print("web socket message receive")
    variables = {"name": name}
    counter = 0
    # print("Going into for loop with counter", counter)
    async for result in session.subscribe(query, variable_values=variables, parse_result=True):
        # print("iteration no:", counter)
        # counter += 1
        # raise Exception("web socket message recv something:",result,params)
        # print("web socket message recv something:",result,params)
        callback(result, params)

    # raise Exception("Coming out of for loop")

