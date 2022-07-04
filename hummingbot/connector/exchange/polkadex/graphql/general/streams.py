from gql import gql

from auth.client import subscribe_query_command


async def websocket_streams_session_provided(name, session, callback):
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
        callback(result)

async def websocket_streams(name, callback):
    query = gql(
        """
subscription WebsocketStreamsMessage($name: String!) {
  websocket_streams(name: $name) {
    data
  }
}
""")
    variables = {"name": name}

    await subscribe_query_command(query, variables, callback)
