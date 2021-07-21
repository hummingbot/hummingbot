# string-env-interpolation

Use string interpolation to provide Environment Variables.

## Installation

    yarn add string-env-interpolation
    npm install string-env-interpolation

## Usage

Let's say we have a config file: `config.yaml`.

```yaml
debug: ${DEBUG:false}
name: ${NAME:"Development"}
user: ${USER}
```

Our library wants to be able to consume environment variables in `index.js`.

```typescript
import { env } from "string-env-interpolation";
import { readFileSync } from "fs";

const content = env(readFileSync("./config.yaml", "utf-8"));

console.log(content);
```

Outputs:

```bash
DEBUG=true USER=kamil node index.js

# Output
debug: true
name: Development
user: kamil



NAME=Production USER=kamil node index.js

# Output
debug: false
name: Production
user: kamil
```

