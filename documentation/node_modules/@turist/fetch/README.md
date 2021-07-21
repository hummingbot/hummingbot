# @turist/fetch

Opinionated `fetch` optimized for use inside microservices.

It automatically configures an `agent` via
[agentkeepalive](https://github.com/node-modules/agentkeepalive),
if not provided, with the following settings:

| Name                         | Value |
|------------------------------|-------|
| `maxSockets`                 | 50    |
| `maxFreeSockets`             | 20    |
| `timeout`                    | 60000 |
| `freeSocketKeepAliveTimeout` | 30000 |

## How to use

```js
const fetch = require('@turist/fetch').default(require('some-fetch-implementation'))
```

```ts
import createFetch from '@turist/fetch';

const fetch = createFetch();
```

If no fetch implementation is supplied, it will attempt to use peerDep
`node-fetch`.
