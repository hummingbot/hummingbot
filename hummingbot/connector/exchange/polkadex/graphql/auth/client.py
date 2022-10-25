from urllib.parse import urlparse

from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.appsync_auth import AppSyncJWTAuthentication

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS


# Returns a result after running graphql queries
# Doesn't take subscription commands
async def execute_query_command(query, variable_values, proxy_addr):
    # Extract host from url
    host = str(urlparse(CONSTANTS.GRAPHQL_ENDPOINT).netloc)
    url = CONSTANTS.GRAPHQL_ENDPOINT
    auth = AppSyncJWTAuthentication(host, proxy_addr)

    transport = AIOHTTPTransport(url=url, auth=auth)
    async with Client(transport=transport, fetch_schema_from_transport=False) as session:
        return await session.execute(query, variable_values=variable_values, parse_result=True)

# TODO Needs to be removed
# Calls the callback with the message from subscription endpoint
""" async def subscribe_query_command(query, variable_values, callback, host, proxy_addr):
    url, api_key = get_env_vars()
    # Extract host from url
    host = str(urlparse(url).netloc)

    auth = AppSyncJWTAuthentication(host, proxy_addr)

    transport = AppSyncWebsocketsTransport(url=url, auth=auth)

    async with Client(transport=transport, fetch_schema_from_transport=False) as session:
        async for result in session.subscribe(query, variable_values=variable_values, parse_result=True):
            callback(result) """
