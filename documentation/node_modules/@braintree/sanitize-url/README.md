# sanitize-url

## Installation

```sh
npm install -S @braintree/sanitize-url
```

## Usage

```js
var sanitizeUrl = require('@braintree/sanitize-url').sanitizeUrl;

sanitizeUrl('https://example.com'); // 'https://example.com'
sanitizeUrl('http://example.com'); // 'http://example.com'
sanitizeUrl('mailto:hello@example.com'); // 'mailto:hello@example.com'

sanitizeUrl('javascript:alert(document.domain)'); // 'about:blank'
sanitizeUrl('jAvasCrIPT:alert(document.domain)'); // 'about:blank'
sanitizeUrl(decodeURIComponent('JaVaScRiP%0at:alert(document.domain)')); // 'about:blank'
```
