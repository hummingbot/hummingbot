# graphql-playground-middleware-express

> Express middleware to expose an endpoint for the GraphQL Playground IDE
> **SECURITY NOTE**: All versions of `graphql-playground-express` until `1.7.16` or later have a security vulnerability when unsanitized user input is used while invoking `expressPlayground()`. [Read more below](#security-notes)

## Installation

Using yarn:

```console
yarn add graphql-playground-middleware-express
```

Or npm:

```console
npm install graphql-playground-middleware-express --save
```

## Usage

See full example in [examples/basic](https://github.com/prisma/graphql-playground/tree/master/packages/graphql-playground-middleware-express/examples/basic).

```js
const express = require('express')
const expressPlayground = require('graphql-playground-middleware-express')
  .default

const app = express()

app.get('/playground', expressPlayground({ endpoint: '/graphql' }))
```

## Security Notes

All versions before `1.7.16` were vulnerable to user-defined input to `expressPlayground()`. Read more in [the security notes](https://github.com/prisma/graphql-playground/tree/master/SECURITY.md)

### Security Upgrade Steps

To fix the issue, you can upgrade to `1.6.12` or later. If you aren't able to upgrade, see the security notes for a workaround.

**yarn:**
`yarn add graphql-playground-express@^1.7.16`

**npm:**
`npm install --save graphql-playground-express@^1.7.16`
