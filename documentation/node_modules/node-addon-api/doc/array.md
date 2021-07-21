# Array

Class [`Napi::Array`][] inherits from class [`Napi::Object`][].

Arrays are native representations of JavaScript Arrays. `Napi::Array` is a wrapper
around `napi_value` representing a JavaScript Array.

[`Napi::TypedArray`][] and [`Napi::ArrayBuffer`][] correspond to JavaScript data
types such as [`Napi::Int32Array`][] and [`Napi::ArrayBuffer`][], respectively,
that can be used for transferring large amounts of data from JavaScript to the
native side. An example illustrating the use of a JavaScript-provided
`ArrayBuffer` in native code is available [here](https://github.com/nodejs/node-addon-examples/tree/master/array_buffer_to_native/node-addon-api).

## Constructor
```cpp
Napi::Array::Array();
```

Returns an empty array.

If an error occurs, a `Napi::Error` will be thrown. If C++ exceptions are not
being used, callers should check the result of `Env::IsExceptionPending` before
attempting to use the returned value.

```cpp
Napi::Array::Array(napi_env env, napi_value value);
```
- `[in] env` - The environment in which to create the array.
- `[in] value` - The primitive to wrap.

Returns a `Napi::Array` wrapping a `napi_value`.

If an error occurs, a `Napi::Error` will get thrown. If C++ exceptions are not
being used, callers should check the result of `Env::IsExceptionPending` before
attempting to use the returned value.

## Methods

### New
```cpp
static Napi::Array Napi::Array::New(napi_env env);
```
- `[in] env` - The environment in which to create the array.

Returns a new `Napi::Array`.

If an error occurs, a `Napi::Error` will get thrown. If C++ exceptions are not
being used, callers should check the result of `Env::IsExceptionPending` before
attempting to use the returned value.

### New

```cpp
static Napi::Array Napi::Array::New(napi_env env, size_t length);
```
- `[in] env` - The environment in which to create the array.
- `[in] length` - The length of the array.

Returns a new `Napi::Array` with the given length.

If an error occurs, a `Napi::Error` will get thrown. If C++ exceptions are not
being used, callers should check the result of `Env::IsExceptionPending` before
attempting to use the returned value.

### Length
```cpp
uint32_t Napi::Array::Length() const;
```

Returns the length of the array.

Note:
This can execute JavaScript code implicitly according to JavaScript semantics.
If an error occurs, a `Napi::Error` will get thrown. If C++ exceptions are not
being used, callers should check the result of `Env::IsExceptionPending` before
attempting to use the returned value.

[`Napi::ArrayBuffer`]: ./array_buffer.md
[`Napi::Int32Array`]: ./typed_array_of.md
[`Napi::Object`]: ./object.md
[`Napi::TypedArray`]: ./typed_array.md
