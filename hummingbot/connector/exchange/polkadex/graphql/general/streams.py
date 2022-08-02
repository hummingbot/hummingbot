from gql import gql

from hummingbot.connector.exchange.polkadex.graphql.auth.client import subscribe_query_command


async def websocket_streams_session_provided(name, session, callback, params=None):
    query = gql(
        """
subscription WebsocketStreamsMessage($name: String!) {
  websocket_streams(name: $name) {
    data
  }
}
""")
    variables = {"name": name}

    async for result in session.subscribe(query, variable_values=variables, parse_result=True):
        callback(result, params)

