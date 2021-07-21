# password-prompt

Node cross-platform password prompt.

Supported Environments:

* Unix
* TTY or non-TTY
* cygwin
* Git Bash
* cmd.exe
* PowerShell
* cmder
* Console2

# API Reference
prompt -- Prompt for a password

**Returns**: <code>Promise.&lt;string&gt;</code> - input from user  

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| [ask] | <code>string</code> |  | prompt output |
| [options] | <code>Object</code> |  |  |
| [options.method] | <code>string</code> | <code>&quot;mask&quot;</code> | mask or hide |

**Example**  
```js
let prompt = require('password-prompt')
let password = prompt('password: ')
// password: ******
```
