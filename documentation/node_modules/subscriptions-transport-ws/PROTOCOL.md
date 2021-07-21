# GraphQL over WebSocket Protocol

## Client-server communication

Each message has a `type` field, which defined in the protocol of this package, as well as associated fields inside `payload` field, depending on the message type, and `id` field so the client can identify each response from the server.

Each WebSocket message is represented in JSON structure, and being stringified before sending it over the network.

This is the structure of each message:

```typescript
export interface OperationMessage {
  payload?: any;
  id?: string;
  type: string;
}
```

### Client -> Server

#### GQL_CONNECTION_INIT
Client sends this message after plain websocket connection to start the communication with the server

The server will response only with `GQL_CONNECTION_ACK` + `GQL_CONNECTION_KEEP_ALIVE` (if used) or `GQL_CONNECTION_ERROR` to this message.

- `payload: Object` : optional parameters that the client specifies in `connectionParams`

#### GQL_START
Client sends this message to execute GraphQL operation
- `id: string` : The id of the GraphQL operation to start
- `payload: Object`:
    * `query: string` : GraphQL operation as string or parsed GraphQL document node
    * `variables?: Object` : Object with GraphQL variables
    * `operationName?: string` : GraphQL operation name
    
#### GQL_STOP
Client sends this message in order to stop a running GraphQL operation execution (for example: unsubscribe)
- `id: string` : operation id
    
#### GQL_CONNECTION_TERMINATE
Client sends this message to terminate the connection.    
    
### Server -> Client

#### GQL_CONNECTION_ERROR
The server may responses with this message to the `GQL_CONNECTION_INIT` from client, indicates the server rejected the connection.

It server also respond with this message in case of a parsing errors of the message (which does not disconnect the client, just ignore the message).

- `payload: Object`: the server side error

#### GQL_CONNECTION_ACK
The server may responses with this message to the `GQL_CONNECTION_INIT` from client, indicates the server accepted the connection.
May optionally include a payload.


#### GQL_DATA
The server sends this message to transfter the GraphQL execution result from the server to the client, this message is a response for `GQL_START` message.

For each GraphQL operation send with `GQL_START`, the server will respond with at least one `GQL_DATA` message.

- `id: string` : ID of the operation that was successfully set up
- `payload: Object` : 
    * `data: any`: Execution result
    * `errors?: Error[]` : Array of resolvers errors

#### GQL_ERROR
Server sends this message upon a failing operation, before the GraphQL execution, usually due to GraphQL validation errors (resolver errors are part of `GQL_DATA` message, and will be added as `errors` array)
- `payload: Error` : payload with the error attributed to the operation failing on the server
- `id: string` : operation ID of the operation that failed on the server

#### GQL_COMPLETE
Server sends this message to indicate that a GraphQL operation is done, and no more data will arrive for the specific operation.

- `id: string` : operation ID of the operation that completed

#### GQL_CONNECTION_KEEP_ALIVE
Server message that should be sent right after each `GQL_CONNECTION_ACK` processed and then periodically to keep the client connection alive.

The client starts to consider the keep alive message only upon the first received keep alive message from the server.

### Messages Flow

This is a demonstration of client-server communication, in order to get a better understanding of the protocol flow:

#### Session Init Phase

The phase initializes the connection between the client and server, and usually will also build the server-side `context` for the execution.

- Client connected immediately, or stops and wait if using lazy mode (until first operation execution)
- Client sends `GQL_CONNECTION_INIT` message to the server.
- Server calls `onConnect` callback with the init arguments, waits for init to finish and returns it's return value with `GQL_CONNECTION_ACK` + `GQL_CONNECTION_KEEP_ALIVE` (if used), or `GQL_CONNECTION_ERROR` in case of `false` or thrown exception from `onConnect` callback.
- Client gets `GQL_CONNECTION_ACK` + `GQL_CONNECTION_KEEP_ALIVE` (if used) and waits for the client's app to create subscriptions.

#### Connected Phase

This phase called per each operation the client request to execute:

- App creates a subscription using `subscribe` or `query` client's API, and the `GQL_START` message sent to the server.
- Server calls `onOperation` callback, and responds with `GQL_DATA` in case of zero errors, or `GQL_ERROR` if there is a problem with the operation (is might also return `GQL_ERROR` with `errors` array, in case of resolvers errors).
- Client get `GQL_DATA` and handles it.
- Server calls `onOperationDone` if the operation is a query or mutation (for subscriptions, this called when unsubscribing)
- Server sends `GQL_COMPLETE` if the operation is a query or mutation (for subscriptions, this sent when unsubscribing)

For subscriptions:
- App triggers `PubSub`'s publication method, and the server publishes the event, passing it through the `subscribe` executor to create GraphQL execution result
- Client receives `GQL_DATA` with the data, and handles it.
- When client unsubscribe, the server triggers `onOperationDone` and sends `GQL_COMPLETE` message to the client.

When client done with executing GraphQL, it should close the connection and terminate the session using `GQL_CONNECTION_TERMINATE` message.
