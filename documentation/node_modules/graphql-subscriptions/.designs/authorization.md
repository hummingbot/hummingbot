## Authorize on connect

When client side creates the WebSocket instance and connects to the subscriptions server, it must provide the authorization token, but there are some issues with that:

1. It’s not possible to provide custom headers when creating WebSocket connection in browser. 

> related to https://github.com/apollostack/subscriptions-transport-ws/issues/50 ,
https://github.com/apollostack/subscriptions-transport-ws/pull/45
 
A possible workaround is to send the auth token in the url as query parameter and parse in on sever side while doing the connection handshake 

> (Note: graphql-subscription does not expose onConnection callback, only onSubscribe, which occur after the connection) 

2. You have to create the actual connection and then reject it in the server side if there is an error with the user’s authorization token.
At the moment, graphql-subscription does not expose `unsubscribe` or `disconnect` feature for a connection (should be part of `onConnection`) 

> related to https://github.com/apollostack/subscriptions-transport-ws/issues/51 , https://github.com/apollostack/subscriptions-transport-ws/pull/17

3. At the moment, the client side can provide the “context” object for the subscription (and not for the connection), which can contain his auth token.


Another option is to send the auth token from the client side on a separate message (like, `ON_INIT`) before creating the subscriptions. 


## Authorization Lifecycle

Another issue is the lifecycle of the authorization token, there are some cases that needs a solution:

1. How to handle invalidation of the auth token? 
If the client side logout from the application, it’s the client side’s responsibility to disconnect the WebSocket. 

2. How to handle expiration of token?
At the moment, If the client side’s token no longer valid, it should logout the user and disconnect the token.


## Authorization Validation

What is the server side’s responsibility when dealing with authorized WebSocket and subscriptions?
 
If the client side does not disconnects the WebSocket when needed (for example, on logout or on expiration), and the WebSocket remains open, the client side will receive the publications of it’s existing subscriptions.
It’s not an option to validate the auth token on the server before each publication, for each user that subscribed. 


## Existing WebSocket Authorization Solutions

* Socket.io-auth (https://github.com/facundoolano/socketio-auth )
    * Provides a similar flow to onConnection and onAuthorize with a token, the server can validate and authorize the connection only when the connection created.
    * The auth token send via a custom WebSocket message.
    * Features callbacks for `onAuthorize`, `onAuthorized`, `onReject`, `postAuthenticate`.
* Sockjs-node (https://github.com/sockjs/sockjs-node#authorisation )
    * Does not provide a built-in solution and suggest a self-implemented authorization.
* https://gist.github.com/subudeepak/9897212 
* https://auth0.com/blog/auth-with-socket-io/ 
* https://auth0.com/blog/auth-with-socket-io/ 
    * Suggests using authorization on connection using url parameter with the auth token.
* Meteor/DDP
    * The DDP protocol itself has no concept of authentication. Authentication is done via normal method calls.
    * The Meteor DDP server implementation allows method calls to store state on the connection object representing the current user ID, which is accessible from other methods and publications. If the user ID ever changes, all publications are basically re-evaluated from scratch (inside the server). Nothing special is done on the server side to allow methods to notice if the user ID changes while they are running; however, methods run in series unless they explicitly ask to unblock the connection (and the client tries to not send login methods in parallel with other methods).
    * The Meteor Accounts package tracks DDP connections associated with resume tokens and disconnects them if the resume token associated with that connection is deleted from the database.
    * Personal opinion from @glasser: having auth just be "another method" wasn't the best idea. It works better if it's an established-at-beginning-of-connection, disconnect-to-change thing. However, the general idea of having a way for changes to authn/authz to "rerun publishers" or "disconnect connections" is nice.
  


## Implementation possibility:

* Client creates a networkInterface with WebSocket client, and provides the auth token using one of the following:
    * URL parameter with the auth token.
    * Custom object that will be translated into INIT_MESSAGE and will be sent after initial connection handshake.
* Server side “onConnection” fires and validate the token, if the token is invalid, it rejects the connection / disconnects the socket.

#### Pros:

* Simple to implement.
        * Server side - need to add “onConnection” callback with ability to reject the connection.
        * Client side - need to add ability to send custom object with the auth token (or take if from the requested URL).
* Custom auth for each application. 

#### Cons:

* Forces the client side to handle logout/expiration of the token
* Server publications not validated.
