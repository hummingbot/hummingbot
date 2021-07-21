[![npm version](https://badge.fury.io/js/subscriptions-transport-ws.svg)](https://badge.fury.io/js/subscriptions-transport-ws) [![GitHub license](https://img.shields.io/github/license/apollostack/subscriptions-transport-ws.svg)](https://github.com/apollostack/subscriptions-transport-ws/blob/license/LICENSE)

# subscriptions-transport-ws

**(Work in progress!)**

A GraphQL WebSocket server and client to facilitate GraphQL queries, mutations and subscriptions over WebSocket.

> `subscriptions-transport-ws` is an extension for GraphQL, and you can use it with any GraphQL client and server (not only Apollo).

See [GitHunt-API](https://github.com/apollostack/GitHunt-API) and [GitHunt-React](https://github.com/apollostack/GitHunt-React) for an example server and client integration.

# Getting Started

Start by installing the package, using Yarn or NPM.

    Using Yarn:
    $ yarn add subscriptions-transport-ws

    Or, using NPM:
    $ npm install --save subscriptions-transport-ws

> Note that you need to use this package on both GraphQL client and server.

> This command also installs this package's dependencies, including `graphql-subscriptions`.

## Server

Starting with the server, create a new simple `PubSub` instance. We will later use this `PubSub` to publish and subscribe to data changes.

```js
import { PubSub } from 'graphql-subscriptions';

export const pubsub = new PubSub();
```

Now, create `SubscriptionServer` instance, with your GraphQL `schema`, `execute` and `subscribe` (from `graphql-js` package):

```js
import { createServer } from 'http';
import { SubscriptionServer } from 'subscriptions-transport-ws';
import { execute, subscribe } from 'graphql';
import { schema } from './my-schema';

const WS_PORT = 5000;

// Create WebSocket listener server
const websocketServer = createServer((request, response) => {
  response.writeHead(404);
  response.end();
});

// Bind it to port and start listening
websocketServer.listen(WS_PORT, () => console.log(
  `Websocket Server is now running on http://localhost:${WS_PORT}`
));

const subscriptionServer = SubscriptionServer.create(
  {
    schema,
    execute,
    subscribe,
  },
  {
    server: websocketServer,
    path: '/graphql',
  },
);
```

### Creating Your Subscriptions

Please refer to [`graphql-subscriptions`](https://github.com/apollographql/graphql-subscriptions) documentation for how to create your GraphQL subscriptions, and how to publish data.



## Client (browser)

When using this package for client side, you can choose either use HTTP request for Queries and Mutation and use the WebSocket for subscriptions only, or create a full transport that handles all type of GraphQL operations over the socket.

### Full WebSocket Transport

To start with a full WebSocket transport, that handles all types of GraphQL operations, import and create an instance of `SubscriptionClient`.

Then, create your `ApolloClient` instance and use the `SubscriptionsClient` instance as network interface:

```js
import { SubscriptionClient } from 'subscriptions-transport-ws';
import ApolloClient from 'apollo-client';

const GRAPHQL_ENDPOINT = 'ws://localhost:3000/graphql';

const client = new SubscriptionClient(GRAPHQL_ENDPOINT, {
  reconnect: true,
});

const apolloClient = new ApolloClient({
    networkInterface: client,
});

```

### Hybrid WebSocket Transport

To start with a hybrid WebSocket transport, that handles only `subscription`s over WebSocket, create your `SubscriptionClient` and a regular HTTP network interface, then extend your network interface to use the WebSocket client for GraphQL subscriptions:

```js
import {SubscriptionClient, addGraphQLSubscriptions} from 'subscriptions-transport-ws';
import ApolloClient, {createNetworkInterface} from 'apollo-client';

// Create regular NetworkInterface by using apollo-client's API:
const networkInterface = createNetworkInterface({
 uri: 'http://localhost:3000' // Your GraphQL endpoint
});

// Create WebSocket client
const wsClient = new SubscriptionClient(`ws://localhost:5000/`, {
    reconnect: true,
    connectionParams: {
        // Pass any arguments you want for initialization
    }
});

// Extend the network interface with the WebSocket
const networkInterfaceWithSubscriptions = addGraphQLSubscriptions(
    networkInterface,
    wsClient
);

// Finally, create your ApolloClient instance with the modified network interface
const apolloClient = new ApolloClient({
    networkInterface: networkInterfaceWithSubscriptions
});
```

Now, when you want to use subscriptions in client side, use your `ApolloClient` instance, with [`subscribe`](https://www.apollographql.com/docs/react/api/apollo-client#ApolloClient.subscribe) or `query` [`subscribeToMore`](https://www.apollographql.com/docs/react/api/apollo-client#ObservableQuery.subscribeToMore):

```js
apolloClient.subscribe({
  query: gql`
    subscription onNewItem {
        newItemCreated {
            id
        }
    }`,
  variables: {}
}).subscribe({
  next (data) {
    // Notify your application with the new arrived data
  }
});
```

```js
apolloClient.query({
  query: ITEM_LIST_QUERY,
  variables: {}
}).subscribeToMore({
  document: gql`
    subscription onNewItem {
        newItemCreated {
            id
        }
    }`,
  variables: {},
  updateQuery: (prev, { subscriptionData, variables }) => {
    // Perform updates on previousResult with subscriptionData
    return updatedResult;
  }
});
```

If you don't use any package/modules loader, you can still use this package, by using `unpkg` service, and get the client side package from:

```
https://unpkg.com/subscriptions-transport-ws@VERSION/browser/client.js
```

> Replace VERSION with the latest version of the package.


## Use it with GraphiQL

You can use this package's power with GraphiQL, and subscribe to live-data stream inside GraphiQL.

If you are using the latest version of `graphql-server` flavors (`graphql-server-express`, `graphql-server-koa`, etc...), you already can use it! Make sure to specify `subscriptionsEndpoint` in GraphiQL configuration, and that's it!

For example, `graphql-server-express` users need to add the following:

```js
app.use('/graphiql', graphiqlExpress({
  endpointURL: '/graphql',
  subscriptionsEndpoint: `YOUR_SUBSCRIPTION_ENDPOINT_HERE`,
}));
```

If you are using older version, or another GraphQL server, start by modifying GraphiQL static HTML, and add this package and it's fetcher from CDN:

```html
    <script src="//unpkg.com/subscriptions-transport-ws@0.5.4/browser/client.js"></script>
    <script src="//unpkg.com/graphiql-subscriptions-fetcher@0.0.2/browser/client.js"></script>
```

Then, create `SubscriptionClient` and define the fetcher:

```js
let subscriptionsClient = new window.SubscriptionsTransportWs.SubscriptionClient('SUBSCRIPTION_WS_URL_HERE', {
  reconnect: true
});
let myCustomFetcher = window.GraphiQLSubscriptionsFetcher.graphQLFetcher(subscriptionsClient, graphQLFetcher);
```

> `graphQLFetcher` is the default fetcher, and we use it as fallback for non-subscription GraphQL operations.

And replace your GraphiQL creation logic to use the new fetcher:

```js
ReactDOM.render(
  React.createElement(GraphiQL, {
    fetcher: myCustomFetcher, // <-- here
    onEditQuery: onEditQuery,
    onEditVariables: onEditVariables,
    onEditOperationName: onEditOperationName,
    query: ${safeSerialize(queryString)},
    response: ${safeSerialize(resultString)},
    variables: ${safeSerialize(variablesString)},
    operationName: ${safeSerialize(operationName)},
  }),
  document.body
);
```

# API Docs

## SubscriptionClient
### `Constructor(url, options, webSocketImpl)`
- `url: string` : url that the client will connect to, starts with `ws://` or `wss://`
- `options?: Object` : optional, object to modify default client behavior
  * `timeout?: number` : how long the client should wait in ms for a keep-alive message from the server (default 30000 ms), this parameter is ignored if the server does not send keep-alive messages. This will also be used to calculate the max connection time per connect/reconnect
  * `minTimeout?: number`: the minimum amount of time the client should wait for a connection to be made (default 1000 ms)
  * `lazy?: boolean` : use to set lazy mode - connects only when first subscription created, and delay the socket initialization
  * `connectionParams?: Object | Function | Promise<Object>` : object that will be available as first argument of `onConnect` (in server side), if passed a function - it will call it and send the return value, if function returns as promise - it will wait until it resolves and send the resolved value.
  * `reconnect?: boolean` : automatic reconnect in case of connection error
  * `reconnectionAttempts?: number` : how much reconnect attempts
  * `connectionCallback?: (error) => {}` : optional, callback that called after the first init message, with the error (if there is one)
  * `inactivityTimeout?: number` : how long the client should wait in ms, when there are no active subscriptions, before disconnecting from the server. Set to 0 to disable this behavior. (default 0)
- `webSocketImpl?: Object` - optional, constructor for W3C compliant WebSocket implementation. Use this when your environment does not have a built-in native WebSocket (for example, with NodeJS client)

### Methods
#### `request(options) => Observable<ExecutionResult>`: returns observable to execute the operation.
- `options: {OperationOptions}`
  * `query: string` : GraphQL subscription
  * `variables: Object` : GraphQL subscription variables
  * `operationName: string` : operation name of the subscription
  * `context: Object` : use to override context for a specific call

#### `unsubscribeAll() => void` - unsubscribes from all active subscriptions.

#### `on(eventName, callback, thisContext) => Function`
- `eventName: string`: the name of the event, available events are: `connecting`, `connected`, `reconnecting`, `reconnected`, `disconnected` and `error`
- `callback: Function`: function to be called when websocket connects and initialized.
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onConnected(callback, thisContext) => Function` - shorthand for `.on('connected', ...)`
- `callback: Function(payload)`: function to be called when websocket connects and initialized, after ACK message returned from the server. Includes payload from server, if any.
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onReconnected(callback, thisContext) => Function` - shorthand for `.on('reconnected', ...)`
- `callback: Function(payload)`: function to be called when websocket reconnects and initialized, after ACK message returned from the server. Includes payload from server, if any.
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onConnecting(callback, thisContext) => Function` - shorthand for `.on('connecting', ...)`
- `callback: Function`: function to be called when websocket starts it's connection
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onReconnecting(callback, thisContext) => Function` - shorthand for `.on('reconnecting', ...)`
- `callback: Function`: function to be called when websocket starts it's reconnection
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onDisconnected(callback, thisContext) => Function` - shorthand for `.on('disconnected', ...)`
- `callback: Function`: function to be called when websocket disconnected.
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

#### `onError(callback, thisContext) => Function` - shorthand for `.on('error', ...)`
- `callback: Function`: function to be called when an error occurs.
- `thisContext: any`: `this` context to use when calling the callback function.
- => Returns an `off` method to cancel the event subscription.

### `close() => void` - closes the WebSocket connection manually, and ignores `reconnect` logic if it was set to `true`.

### `use(middlewares: MiddlewareInterface[]) => SubscriptionClient` - adds middleware to modify `OperationOptions` per each request
- `middlewares: MiddlewareInterface[]` - Array contains list of middlewares (implemented `applyMiddleware` method) implementation, the `SubscriptionClient` will use the middlewares to modify `OperationOptions` for every operation

### `status: number` : returns the current socket's `readyState`


## SubscriptionServer
### `Constructor(options, socketOptions | socketServer)`
- `options: {ServerOptions}`
  * `rootValue?: any` : Root value to use when executing GraphQL root operations
  * `schema?: GraphQLSchema` : GraphQL schema object. If not provided, you have to return the schema as a property on the object returned from `onOperation`.
  * `execute?: (schema, document, rootValue, contextValue, variableValues, operationName) => Promise<ExecutionResult> | AsyncIterator<ExecutionResult>` : GraphQL `execute` function, provide the default one from `graphql` package. Return value of `AsyncItrator` is also valid since this package also support reactive `execute` methods.
  * `subscribe?: (schema, document, rootValue, contextValue, variableValues, operationName) => Promise<ExecutionResult | AsyncIterator<ExecutionResult>>` : GraphQL `subscribe` function, provide the default one from `graphql` package.
  * `onOperation?: (message: SubscribeMessage, params: ExecutionParams, webSocket: WebSocket)` : optional method to create custom params that will be used when resolving this operation. It can also be used to dynamically resolve the schema that will be used for the particular operation.
  * `onOperationComplete?: (webSocket: WebSocket, opId: string)` : optional method that called when a GraphQL operation is done (for query and mutation it's immediately, and for subscriptions when unsubscribing)
  * `onConnect?: (connectionParams: Object, webSocket: WebSocket, context: ConnectionContext)` : optional method that called when a client connects to the socket, called with the `connectionParams` from the client, if the return value is an object, its elements will be added to the context. return `false` or throw an exception to reject the connection. May return a Promise.
  * `onDisconnect?: (webSocket: WebSocket, context: ConnectionContext)` : optional method that called when a client disconnects
  * `keepAlive?: number` : optional interval in ms to send `KEEPALIVE` messages to all clients

- `socketOptions: {WebSocket.IServerOptions}` : options to pass to the WebSocket object (full docs [here](https://github.com/websockets/ws/blob/master/doc/ws.md))
  * `server?: HttpServer` - existing HTTP server to use (use without `host`/`port`)
  * `host?: string` - server host
  * `port?: number` - server port
  * `path?: string` - endpoint path

- `socketServer: {WebSocket.Server}` : a configured server if you need more control. Can be used for integration testing with in-memory WebSocket implementation.

## How it works?

* For GraphQL WebSocket protocol docs, [click here](https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md)
* This package also uses `AsyncIterator` internally using [iterall](https://github.com/leebyron/iterall), for more information [click here](https://github.com/ReactiveX/IxJS), or [the proposal](https://github.com/tc39/proposal-async-iteration)

The current version of this transport, also support a previous version of the protocol.

[You can find the old protocol docs here](https://github.com/apollographql/subscriptions-transport-ws/blob/cacb8692f3601344a4101d802443d046d73f8b23/README.md#client-server-communication)
