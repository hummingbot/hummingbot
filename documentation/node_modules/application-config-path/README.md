# node-application-config-path

Store your application config in the right location.

## Installation

```bash
npm install --save application-config-path
```

## Usage

```javascript
var applicationConfigPath = require('application-config-path')

// cfgPath is a string with the path to a directory
// where you can store your config.
var cfgPath = applicationConfigPath('My App')
```

## API

### `applicationConfigPath(name)`

Return a string with the path to a directory where you can store your
application specific config.

## License

MIT
