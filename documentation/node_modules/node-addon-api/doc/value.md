# Value

`Napi::Value` is the C++ manifestation of a JavaScript value. It is the base
class upon which other JavaScript values such as `Napi::Number`,
`Napi::Boolean`, `Napi::String`, and `Napi::Object` are based. It represents a
JavaScript value of an unknown type. It is a thin wrapper around the N-API
datatype `napi_value`. Methods on this class can be used to check the JavaScript
type of the underlying N-API `napi_value` and also to convert to C++ types.

## Constructors

### Empty Constructor

```cpp
Napi::Value::Value();
```

Creates a new *empty* `Napi::Value` instance.

### Constructor

```cpp
Napi::Value::Value(napi_env env, napi_value value);
```

- `[in] env`: The `napi_env` environment in which to construct the `Napi::Value`
object.
- `[in] value`: The C++ primitive from which to instantiate the `Napi::Value`.
value` may be any of:
  - `bool`
  - Any integer type
  - Any floating point type
  - `const char*` (encoded using UTF-8, null-terminated)
  - `const char16_t*` (encoded using UTF-16-LE, null-terminated)
  - `std::string` (encoded using UTF-8)
  - `std::u16string`
  - `Napi::Value`
  - `napi_value`

## Operators

### operator napi_value

```cpp
Napi::Value::operator napi_value() const;
```

Returns the underlying N-API `napi_value`. If the instance is _empty_, this
returns `nullptr`.

### operator ==

```cpp
bool Napi::Value::operator ==(const Napi::Value& other) const;
```

Returns `true` if this value strictly equals another value, or `false`
otherwise.

### operator !=

```cpp
bool Napi::Value::operator !=(const Napi::Value& other) const;
```

Returns `false` if this value strictly equals another value, or `true`
otherwise.

## Methods

### As

```cpp
template <typename T> T Napi::Value::As() const;
```

Casts to another type of `Napi::Value`, when the actual type is known or
assumed.

This conversion does not coerce the type. Calling any methods inappropriate for
the actual value type will throw `Napi::Error`.

### Env

```cpp
Napi::Env Napi::Value::Env() const;
```

Returns the `Napi::Env` environment this value is associated with. See
[`Napi::Env`](env.md) for more details about environments.

### From

```cpp
template <typename T>
static Napi::Value Napi::Value::From(napi_env env, const T& value);
```

- `[in] env`: The `napi_env` environment in which to create the `Napi::Value`
object.
- `[in] value`: The N-API primitive value from which to create the `Napi::Value`
object.

Returns a `Napi::Value` object from an N-API primitive value.

This method is used to convert from a C++ type to a JavaScript value.
Here, `value` may be any of:
- `bool` - returns a `Napi::Boolean`.
- Any integer type - returns a `Napi::Number`.
- Any floating point type - returns a `Napi::Number`.
- `const char*` (encoded using UTF-8, null-terminated) - returns a
`Napi::String`.
- `const char16_t*` (encoded using UTF-16-LE, null-terminated) - returns a
`Napi::String`.
- `std::string` (encoded using UTF-8) - returns a `Napi::String`.
- `std::u16string` - returns a `Napi::String`.
- `Napi::Value` - returns a `Napi::Value`.
- `Napi_value` - returns a `Napi::Value`.

### IsArray

```cpp
bool Napi::Value::IsArray() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Array` or `false`
otherwise.

### IsArrayBuffer

```cpp
bool Napi::Value::IsArrayBuffer() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::ArrayBuffer` or
`false` otherwise.

### IsBoolean

```cpp
bool Napi::Value::IsBoolean() const;
```

Returns `true` if the underlying value is a JavaScript `true` or JavaScript
`false`, or `false` if the value is not a `Napi::Boolean` value in JavaScript.

### IsBuffer

```cpp
bool Napi::Value::IsBuffer() const;
```

Returns `true` if the underlying value is a Node.js `Napi::Buffer` or `false`
otherwise.

### IsDataView
```cpp
bool Napi::Value::IsDataView() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::DataView` or
`false` otherwise.

### IsDate

```cpp
bool Napi::Value::IsDate() const;
```

Returns `true` if the underlying value is a JavaScript `Date` or `false`
otherwise.

### IsEmpty

```cpp
bool Napi::Value::IsEmpty() const;
```

Returns `true` if the value is uninitialized.

An empty `Napi::Value` is invalid, and most attempts to perform an operation on
an empty `Napi::Value` will result in an exception. An empty `Napi::Value` is
distinct from JavaScript `null` or `undefined`, which are valid values.

When C++ exceptions are disabled at compile time, a method with a `Napi::Value`
return type may return an empty `Napi::Value` to indicate a pending exception.
Thus, when C++ exceptions are not being used, callers should check the result of
`Env::IsExceptionPending` before attempting to use the value.

### IsExternal
```cpp
bool Napi::Value::IsExternal() const;
```

Returns `true` if the underlying value is a N-API external object or `false`
otherwise.

### IsFunction

```cpp
bool Napi::Value::IsFunction() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Function` or
`false` otherwise.

### IsNull

```cpp
bool Napi::Value::IsNull() const;
```

Returns `true` if the underlying value is a JavaScript `null` or `false`
otherwise.

### IsNumber

```cpp
bool Napi::Value::IsNumber() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Number` or `false`
otherwise.

### IsObject

```cpp
bool Napi::Value::IsObject() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Object` or `false`
otherwise.

### IsPromise

```cpp
bool Napi::Value::IsPromise() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Promise` or
`false` otherwise.

### IsString

```cpp
bool Napi::Value::IsString() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::String` or `false`
otherwise.

### IsSymbol

```cpp
bool Napi::Value::IsSymbol() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::Symbol` or `false`
otherwise.

### IsTypedArray

```cpp
bool Napi::Value::IsTypedArray() const;
```

Returns `true` if the underlying value is a JavaScript `Napi::TypedArray` or
`false` otherwise.

### IsUndefined

```cpp
bool Napi::Value::IsUndefined() const;
```

Returns `true` if the underlying value is a JavaScript `undefined` or `false`
otherwise.

### StrictEquals

```cpp
bool Napi::Value::StrictEquals(const Napi::Value& other) const;
```
- `[in] other`: The `Napi::Value` object to be compared.

Returns a `bool` indicating if this `Napi::Value` strictly equals another
`Napi::Value`.

### ToBoolean

```cpp
Napi::Boolean Napi::Value::ToBoolean() const;
```

Returns a `Napi::Boolean` representing the `Napi::Value`.

This is a wrapper around `napi_coerce_to_boolean`. This will throw a JavaScript
exception if the coercion fails. If C++ exceptions are not being used, callers
should check the result of `Env::IsExceptionPending` before attempting to use
the returned value.

### ToNumber

```cpp
Napi::Number Napi::Value::ToNumber() const;
```

Returns the `Napi::Value` coerced to a JavaScript number.

### ToObject

```cpp
Napi::Object Napi::Value::ToObject() const;
```

Returns the `Napi::Value` coerced to a JavaScript object.

### ToString

```cpp
Napi::String Napi::Value::ToString() const;
```

Returns the `Napi::Value` coerced to a JavaScript string.

### Type

```cpp
napi_valuetype Napi::Value::Type() const;
```

Returns the `napi_valuetype` type of the `Napi::Value`.

[`Napi::Boolean`]: ./boolean.md
[`Napi::BigInt`]: ./bigint.md
[`Napi::Date`]: ./date.md
[`Napi::External`]: ./external.md
[`Napi::Name`]: ./name.md
[`Napi::Number`]: ./number.md
[`Napi::Object`]: ./object.md
