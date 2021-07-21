# Array

_Array_ instance

## `array/is`

Confirms if given object is a native array

```javascript
const isArray = require("type/array/is");

isArray([]); // true
isArray({}); // false
isArray("foo"); // false
```

## `array/ensure`

If given argument is an array, it is returned back. Otherwise `TypeError` is thrown.

```javascript
const ensureArray = require("type/array/ensure");

ensureArray(["foo"]); // ["foo"]
ensureArray("foo"); // Thrown TypeError: foo is not an array
```
