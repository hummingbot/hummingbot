declare module 'buffer-layout' {
  export class Blob {}
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  export class Layout<U> {}
  export class Structure {}
  export class UInt {}
  export class Union {}
}

// TODO similar to this problem, yarn build fails with a conflicting declaration of web3.js in solana and serum!!!

// TODO this not is not related to this file, but more to do not forget!!!
// It is needed to create a documention in the hummingbot-site github repository:
//   https://hummingbot.org/developers/gateway/building-gateway-connectors/#10-create-connector-documentation-page
//   https://hummingbot.org/developers/gateway/building-gateway-connectors/#11-add-documentation-page-to-index
