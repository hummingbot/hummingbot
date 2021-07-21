# Object Wrap

Class `Napi::ObjectWrap<T>` inherits from class [`Napi::InstanceWrap<T>`][].

The `Napi::ObjectWrap<T>` class is used to bind the lifetime of C++ code to a
JavaScript object. Once bound, each time an instance of the JavaScript object
is created, an instance of the C++ class will also be created. When a method
is called on the JavaScript object which is defined as an InstanceMethod, the
corresponding C++ method on the wrapped C++ class will be invoked.

In order to create a wrapper it's necessary to extend the
`Napi::ObjectWrap<T>` class which contains all the plumbing to connect
JavaScript code with a C++ object. Classes extending `Napi::ObjectWrap` can be
instantiated from JavaScript using the **new** operator, and their methods can
be directly invoked from JavaScript. The **wrap** word refers to a way of
grouping methods and state of the class because it will be necessary write
custom code to bridge each of your C++ class methods.

## Example

```cpp
#include <napi.h>

class Example : public Napi::ObjectWrap<Example> {
  public:
    static Napi::Object Init(Napi::Env env, Napi::Object exports);
    Example(const Napi::CallbackInfo& info);
    static Napi::Value CreateNewItem(const Napi::CallbackInfo& info);

  private:
    double _value;
    Napi::Value GetValue(const Napi::CallbackInfo& info);
    Napi::Value SetValue(const Napi::CallbackInfo& info);
};

Napi::Object Example::Init(Napi::Env env, Napi::Object exports) {
    // This method is used to hook the accessor and method callbacks
    Napi::Function func = DefineClass(env, "Example", {
        InstanceMethod<&Example::GetValue>("GetValue"),
        InstanceMethod<&Example::SetValue>("SetValue"),
        StaticMethod<&Example::CreateNewItem>("CreateNewItem"),
    });

    Napi::FunctionReference* constructor = new Napi::FunctionReference();

    // Create a peristent reference to the class constructor. This will allow
    // a function called on a class prototype and a function
    // called on instance of a class to be distinguished from each other.
    *constructor = Napi::Persistent(func);
    exports.Set("Example", func);

    // Store the constructor as the add-on instance data. This will allow this
    // add-on to support multiple instances of itself running on multiple worker
    // threads, as well as multiple instances of itself running in different
    // contexts on the same thread.
    //
    // By default, the value set on the environment here will be destroyed when
    // the add-on is unloaded using the `delete` operator, but it is also
    // possible to supply a custom deleter.
    env.SetInstanceData<Napi::FunctionReference>(constructor);

    return exports;
}

Example::Example(const Napi::CallbackInfo& info) :
    Napi::ObjectWrap<Example>(info) {
  Napi::Env env = info.Env();
  // ...
  Napi::Number value = info[0].As<Napi::Number>();
  this->_value = value.DoubleValue();
}

Napi::Value Example::GetValue(const Napi::CallbackInfo& info){
    Napi::Env env = info.Env();
    return Napi::Number::New(env, this->_value);
}

Napi::Value Example::SetValue(const Napi::CallbackInfo& info){
    Napi::Env env = info.Env();
    // ...
    Napi::Number value = info[0].As<Napi::Number>();
    this->_value = value.DoubleValue();
    return this->GetValue(info);
}

// Initialize native add-on
Napi::Object Init (Napi::Env env, Napi::Object exports) {
    Example::Init(env, exports);
    return exports;
}

// Create a new item using the constructor stored during Init.
Napi::Value Example::CreateNewItem(const Napi::CallbackInfo& info) {
  // Retrieve the instance data we stored during `Init()`. We only stored the
  // constructor there, so we retrieve it here to create a new instance of the
  // JS class the constructor represents.
  Napi::FunctionReference* constructor =
      info.Env().GetInstanceData<Napi::FunctionReference>();
  return constructor->New({ Napi::Number::New(info.Env(), 42) });
}

// Register and initialize native add-on
NODE_API_MODULE(NODE_GYP_MODULE_NAME, Init)
```

The above code can be used from JavaScript as follows:

```js
'use strict'

const { Example } = require('bindings')('addon')

const example = new Example(11)
console.log(example.GetValue())
// It prints 11
example.SetValue(19)
console.log(example.GetValue());
// It prints 19
```

At initialization time, the `Napi::ObjectWrap::DefineClass()` method must be
used to hook up the accessor and method callbacks. It takes a list of property
descriptors, which can be constructed via the various static methods on the base
class.

When JavaScript code invokes the constructor, the constructor callback will
create a new C++ instance and "wrap" it into the newly created JavaScript
object.

When JavaScript code invokes a method or a property accessor on the class the
corresponding C++ callback function will be executed.

For a wrapped object it could be difficult to distinguish between a function
called on a class prototype and a function called on instance of a class.
Therefore it is good practice to save a persistent reference to the class
constructor. This allows the two cases to be distinguished from each other by
checking the this object against the class constructor.

## Methods

### Constructor

Creates a new instance of a JavaScript object that wraps native instance.

```cpp
Napi::ObjectWrap(const Napi::CallbackInfo& callbackInfo);
```

- `[in] callbackInfo`: The object representing the components of the JavaScript
request being made.

### Unwrap

Retrieves a native instance wrapped in a JavaScript object.

```cpp
static T* Napi::ObjectWrap::Unwrap(Napi::Object wrapper);
```

* `[in] wrapper`: The JavaScript object that wraps the native instance.

Returns a native instance wrapped in a JavaScript object. Given the
Napi:Object, this allows a method to get a pointer to the wrapped
C++ object and then reference fields, call methods, etc. within that class.
In many cases calling Unwrap is not required, as methods can
use the `this` field for ObjectWrap when running in a method on a
class that extends ObjectWrap.

### DefineClass

Defnines a JavaScript class with constructor, static and instance properties and
methods.

```cpp
static Napi::Function Napi::ObjectWrap::DefineClass(Napi::Env env,
                    const char* utf8name,
                    const std::initializer_list<PropertyDescriptor>& properties,
                    void* data = nullptr);
```

* `[in] env`: The environment in which to construct a JavaScript class.
* `[in] utf8name`: Null-terminated string that represents the name of the
JavaScript constructor function.
* `[in] properties`: Initializer list of class property descriptor describing
static and instance properties and methods of the class.
See: [`Class property and descriptor`](class_property_descriptor.md).
* `[in] data`: User-provided data passed to the constructor callback as `data`
property of the `Napi::CallbackInfo`.

Returns a `Napi::Function` representing the constructor function for the class.

### DefineClass

Defnines a JavaScript class with constructor, static and instance properties and
methods.

```cpp
static Napi::Function Napi::ObjectWrap::DefineClass(Napi::Env env,
                            const char* utf8name,
                            const std::vector<PropertyDescriptor>& properties,
                            void* data = nullptr);
```

* `[in] env`: The environment in which to construct a JavaScript class.
* `[in] utf8name`: Null-terminated string that represents the name of the
JavaScript constructor function.
* `[in] properties`: Vector of class property descriptor describing static and
instance properties and methods of the class.
See: [`Class property and descriptor`](class_property_descriptor.md).
* `[in] data`: User-provided data passed to the constructor callback as `data`
property of the `Napi::CallbackInfo`.

Returns a `Napi::Function` representing the constructor function for the class.

### Finalize

Provides an opportunity to run cleanup code that requires access to the
`Napi::Env` before the wrapped native object instance is freed.  Override to
implement.

```cpp
virtual void Finalize(Napi::Env env);
```

- `[in] env`: `Napi::Env`.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(
                             const char* utf8name,
                             StaticVoidMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of a static
method for the class.
- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents the static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(
                             const char* utf8name,
                             StaticMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of a static
method for the class.
- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(Symbol name,
                             StaticVoidMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] name`: Napi:Symbol that represents the name of a static
method for the class.
- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents the static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(Symbol name,
                             StaticMethodCallback method,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

method for the class.
- `[in] name`: Napi:Symbol that represents the name of a static.
- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
template <StaticVoidMethodCallback method>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(
                             const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a static method of a
JavaScript class. This function returns nothing.
- `[in] utf8name`: Null-terminated string that represents the name of a static
method for the class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents the static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
template <StaticMethodCallback method>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(
                             const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] utf8name`: Null-terminated string that represents the name of a static
method for the class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
template <StaticVoidMethodCallback method>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] name`: Napi:Symbol that represents the name of a static
method for the class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents the static method of a
JavaScript class.

### StaticMethod

Creates property descriptor that represents a static method of a JavaScript
class.

```cpp
template <StaticMethodCallback method>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticMethod(Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] method`: The native function that represents a static method of a
JavaScript class.
- `[in] name`: Napi:Symbol that represents the name of a static.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into method when it is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static method of a
JavaScript class.

### StaticAccessor

Creates property descriptor that represents a static accessor property of a
JavaScript class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticAccessor(
                             const char* utf8name,
                             StaticGetterCallback getter,
                             StaticSetterCallback setter,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] utf8name`: Null-terminated string that represents the name of a static
accessor property for the class.
- `[in] getter`: The native function to call when a get access to the property
of a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property
of a JavaScript class is performed.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into getter or setter when
is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static accessor
property of a JavaScript class.

### StaticAccessor

Creates property descriptor that represents a static accessor property of a
JavaScript class.

```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticAccessor(Symbol name,
                             StaticGetterCallback getter,
                             StaticSetterCallback setter,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] name`: Napi:Symbol that represents the name of a static accessor.
- `[in] getter`: The native function to call when a get access to the property
of a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property
of a JavaScript class is performed.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into getter or setter when
is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static accessor
property of a JavaScript class.

### StaticAccessor

Creates property descriptor that represents a static accessor property of a
JavaScript class.

```cpp
template <StaticGetterCallback getter, StaticSetterCallback setter=nullptr>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticAccessor(
                             const char* utf8name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] getter`: The native function to call when a get access to the property
of a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property
of a JavaScript class is performed.
- `[in] utf8name`: Null-terminated string that represents the name of a static
accessor property for the class.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into getter or setter when
is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static accessor
property of a JavaScript class.

### StaticAccessor

Creates property descriptor that represents a static accessor property of a
JavaScript class.

```cpp
template <StaticGetterCallback getter, StaticSetterCallback setter=nullptr>
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticAccessor(Symbol name,
                             napi_property_attributes attributes = napi_default,
                             void* data = nullptr);
```

- `[in] getter`: The native function to call when a get access to the property
of a JavaScript class is performed.
- `[in] setter`: The native function to call when a set access to the property
of a JavaScript class is performed.
- `[in] name`: Napi:Symbol that represents the name of a static accessor.
- `[in] attributes`: The attributes associated with a particular property.
One or more of `napi_property_attributes`.
- `[in] data`: User-provided data passed into getter or setter when
is invoked.

Returns `Napi::PropertyDescriptor` object that represents a static accessor
property of a JavaScript class.

### StaticValue

Creates property descriptor that represents an static value property of a
JavaScript class.
```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticValue(
                            const char* utf8name,
                            Napi::Value value,
                            napi_property_attributes attributes = napi_default);
```

- `[in] utf8name`: Null-terminated string that represents the name of the static
property.
- `[in] value`: The value that's retrieved by a get access of the property.
- `[in] attributes`: The attributes to be associated with the property in
addition to the napi_static attribute.  One or more of
`napi_property_attributes`.

Returns `Napi::PropertyDescriptor` object that represents an static value
property of a JavaScript class

### StaticValue

Creates property descriptor that represents an static value property of a
JavaScript class.
```cpp
static Napi::PropertyDescriptor Napi::ObjectWrap::StaticValue(Symbol name,
                            Napi::Value value,
                            napi_property_attributes attributes = napi_default);
```

- `[in] name`: The `Napi::Symbol` object whose value is used to identify the
name of the static property.
- `[in] value`: The value that's retrieved by a get access of the property.
- `[in] attributes`: The attributes to be associated with the property in
addition to the napi_static attribute.  One or more of
`napi_property_attributes`.

Returns `Napi::PropertyDescriptor` object that represents an static value
property of a JavaScript class

[`Napi::InstanceWrap<T>`]: ./instance_wrap.md
