# Env

The opaque data structure containing the environment in which the request is being run.

The Env object is usually created and passed by the Node.js runtime or node-addon-api infrastructure.

## Methods

### Constructor

```cpp
Napi::Env::Env(napi_env env);
```

- `[in] env`: The `napi_env` environment from which to construct the `Napi::Env` object.

### napi_env

```cpp
operator napi_env() const;
```

Returns the `napi_env` opaque data structure representing the environment.

### Global

```cpp
Napi::Object Napi::Env::Global() const;
```

Returns the `Napi::Object` representing the environment's JavaScript Global Object.

### Undefined

```cpp
Napi::Value Napi::Env::Undefined() const;
```

Returns the `Napi::Value` representing the environment's JavaScript Undefined Object.

### Null

```cpp
Napi::Value Napi::Env::Null() const;
```

Returns the `Napi::Value` representing the environment's JavaScript Null Object.

### IsExceptionPending

```cpp
bool Napi::Env::IsExceptionPending() const;
```

Returns a `bool` indicating if an exception is pending in the environment.

### GetAndClearPendingException

```cpp
Napi::Error Napi::Env::GetAndClearPendingException();
```

Returns an `Napi::Error` object representing the environment's pending exception, if any.

### RunScript

```cpp
Napi::Value Napi::Env::RunScript(____ script);
```
- `[in] script`: A string containing JavaScript code to execute.

Runs JavaScript code contained in a string and returns its result.

The `script` can be any of the following types:
- [`Napi::String`](string.md)
- `const char *`
- `const std::string &`

### GetInstanceData
```cpp
template <typename T> T* GetInstanceData();
```

Returns the instance data that was previously associated with the environment,
or `nullptr` if none was associated.

### SetInstanceData

```cpp
template <typename T> using Finalizer = void (*)(Env, T*);
template <typename T, Finalizer<T> fini = Env::DefaultFini<T>>
void SetInstanceData(T* data);
```

- `[template] fini`: A function to call when the instance data is to be deleted.
Accepts a function of the form `void CleanupData(Napi::Env env, T* data)`. If
not given, the default finalizer will be used, which simply uses the `delete`
operator to destroy `T*` when the addon instance is unloaded.
- `[in] data`: A pointer to data that will be associated with the instance of
the addon for the duration of its lifecycle.

Associates a data item stored at `T* data` with the current instance of the
addon. The item will be passed to the function `fini` which gets called when an
instance of the addon is unloaded.

### SetInstanceData

```cpp
template <typename DataType, typename HintType>
using FinalizerWithHint = void (*)(Env, DataType*, HintType*);
template <typename DataType,
          typename HintType,
          FinalizerWithHint<DataType, HintType> fini =
            Env::DefaultFiniWithHint<DataType, HintType>>
void SetInstanceData(DataType* data, HintType* hint);
```

- `[template] fini`: A function to call when the instance data is to be deleted.
Accepts a function of the form
`void CleanupData(Napi::Env env, DataType* data, HintType* hint)`. If not given,
the default finalizer will be used, which simply uses the `delete` operator to
destroy `T*` when the addon instance is unloaded.
- `[in] data`: A pointer to data that will be associated with the instance of
the addon for the duration of its lifecycle.
- `[in] hint`: A pointer to data that will be associated with the instance of
the addon for the duration of its lifecycle and will be passed as a hint to
`fini` when the addon instance is unloaded.

Associates a data item stored at `T* data` with the current instance of the
addon. The item will be passed to the function `fini` which gets called when an
instance of the addon is unloaded. This overload accepts an additional hint to
be passed to `fini`.
