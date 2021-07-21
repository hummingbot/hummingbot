# Name

Class `Napi::Name` inherits from class [`Napi::Value`][].

Names are JavaScript values that can be used as a property name. There are two
specialized types of names supported in Node.js Addon API [`Napi::String`](string.md)
and [`Napi::Symbol`](symbol.md).

## Methods

### Constructor
```cpp
Napi::Name::Name();
```

Returns an empty `Napi::Name`.

```cpp
Napi::Name::Name(napi_env env, napi_value value);
```
- `[in] env` - The environment in which to create the array.
- `[in] value` - The primitive to wrap.

Returns a `Napi::Name` created from the JavaScript primitive.

Note:
The value is not coerced to a string.

[`Napi::Value`]: ./value.md
