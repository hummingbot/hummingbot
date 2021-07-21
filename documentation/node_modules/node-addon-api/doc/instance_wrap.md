# InstanceWrap<T>

This class serves as the base class for [`Napi::ObjectWrap<T>`][] and
[`Napi::Addon<T>`][].

In the case of [`Napi::Addon<T>`][] it provides the
methods for exposing functions to JavaScript on instances of an add-on.

As a base class for [`Napi::ObjectWrap<T>`][] it provides the methods for
exposing instance methods of JavaScript objects instantiated from the JavaScript
class corresponding to the subclass of [`Napi::ObjectWrap<T>`][].

## Methods

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(const char* utf8name,
                             InstanceVoidMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
void MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(const char* utf8name,
                             InstanceMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
Napi::Value MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(Napi::Symbol name,
                             InstanceVoidMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] name`: JavaScript symbol that represents the name of the method provided
by instances of the class.
- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
void MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(Napi::Symbol name,
                             InstanceMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] name`: JavaScript symbol that represents the name of the method provided
by instances of the class.
- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
Napi::Value MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
<template typename T>
template <typename InstanceWrap<T>::InstanceVoidMethodCallback method>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap::InstanceMethod(const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
void MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
template <typename InstanceWrap<T>::InstanceMethodCallback method>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
Napi::Value MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
template <typename InstanceWrap<T>::InstanceVoidMethodCallback method>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(Napi::Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
instance method for the class.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
void MethodName(const Napi::CallbackInfo& info);
```

### InstanceMethod

Creates a property descriptor that represents a method exposed on JavaScript
instances of this class.

```cpp
template <typename T>
template <InstanceWrap<T>::InstanceMethodCallback method>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceMethod(Napi::Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a method provided by the
add-on.
- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
instance method for the class.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the method when it is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents a method
provided by instances of the class. The method must be of the form

```cpp
Napi::Value MethodName(const Napi::CallbackInfo& info);
```

### InstanceAccessor

Creates a property descriptor that represents a property exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceAccessor(const char* utf8name,
                             InstanceGetterCallback getter,
                             InstanceSetterCallback setter,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] getter`: The native function to call when a get access to the property
is performed.
- `[in] setter`: The native function to call when a set access to the property
is performed.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the getter or the setter when it
is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
accessor property provided by instances of the class.

### InstanceAccessor

Creates a property descriptor that represents a property exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceAccessor(Symbol name,
                             InstanceGetterCallback getter,
                             InstanceSetterCallback setter,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
instance accessor.
- `[in] getter`: The native function to call when a get access to the property of
a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property of
a JavaScript class is performed.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the getter or the setter when it
is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
accessor property provided instances of the class.

### InstanceAccessor

Creates a property descriptor that represents a property exposed on JavaScript
instances of this class.

```cpp
template <typename T>
template <typename InstanceWrap<T>::InstanceGetterCallback getter,
          typename InstanceWrap<T>::InstanceSetterCallback setter=nullptr>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceAccessor(const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] getter`: The native function to call when a get access to the property of
a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property of
a JavaScript class is performed.
- `[in] utf8name`: Null-terminated string that represents the name of the method
provided by instances of the class.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the getter or the setter when it
is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
accessor property provided by instances of the class.

### InstanceAccessor

Creates a property descriptor that represents a property exposed on JavaScript
instances of this class.

```cpp
template <typename T>
template <typename InstanceWrap<T>::InstanceGetterCallback getter,
          typename InstanceWrap<T>::InstanceSetterCallback setter=nullptr>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceAccessor(Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] getter`: The native function to call when a get access to the property of
a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property of
a JavaScript class is performed.
- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
instance accessor.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.
- `[in] data`: User-provided data passed into the getter or the setter when it
is invoked.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
accessor property provided by instances of the class.

### InstanceValue

Creates property descriptor that represents a value exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceValue(const char* utf8name,
                            Napi::Value value,
                            napi_property_attributes attributes = napi_default);
```

- `[in] utf8name`: Null-terminated string that represents the name of the
property.
- `[in] value`: The value that's retrieved by a get access of the property.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
value property of an add-on.

### InstanceValue

Creates property descriptor that represents a value exposed on JavaScript
instances of this class.

```cpp
template <typename T>
static Napi::ClassPropertyDescriptor<T>
Napi::InstanceWrap<T>::InstanceValue(Symbol name,
                            Napi::Value value,
                            napi_property_attributes attributes = napi_default);
```

- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
name of the property.
- `[in] value`: The value that's retrieved by a get access of the property.
- `[in] attributes`: The attributes associated with the property. One or more of
`napi_property_attributes`.

Returns a `Napi::ClassPropertyDescriptor<T>` object that represents an instance
value property of an add-on.

[`Napi::Addon<T>`]: ./addon.md
[`Napi::ObjectWrap<T>`]: ./object_wrap.md
