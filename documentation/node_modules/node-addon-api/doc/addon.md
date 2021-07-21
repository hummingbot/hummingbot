# Add-on Structure

Class `Napi::Addon<T>` inherits from class [`Napi::InstanceWrap<T>`][].

Creating add-ons that work correctly when loaded multiple times from the same
source package into multiple Node.js threads and/or multiple times into the same
Node.js thread requires that all global data they hold be associated with the
environment in which they run. It is not safe to store global data in static
variables because doing so does not take into account the fact that an add-on
may be loaded into multiple threads nor that an add-on may be loaded multiple
times into a single thread.

The `Napi::Addon<T>` class can be used to define an entire add-on. Instances of
`Napi::Addon<T>` subclasses become instances of the add-on, stored safely by
Node.js on its various threads and into its various contexts. Thus, any data
stored in the instance variables of a `Napi::Addon<T>` subclass instance are
stored safely by Node.js. Functions exposed to JavaScript using
`Napi::Addon<T>::InstanceMethod` and/or `Napi::Addon<T>::DefineAddon` are
instance methods of the `Napi::Addon` subclass and thus have access to data
stored inside the instance.

`Napi::Addon<T>::DefineProperties` may be used to attach `Napi::Addon<T>`
subclass instance methods to objects other than the one that will be returned to
Node.js as the add-on instance.

The `Napi::Addon<T>` class can be used together with the `NODE_API_ADDON()` and
`NODE_API_NAMED_ADDON()` macros to define add-ons.

## Example

```cpp
#include <napi.h>

class ExampleAddon : public Napi::Addon<ExampleAddon> {
 public:
  ExampleAddon(Napi::Env env, Napi::Object exports) {
    // In the constructor we declare the functions the add-on makes avaialable
    // to JavaScript.
    DefineAddon(exports, {
      InstanceMethod("increment", &ExampleAddon::Increment),

      // We can also attach plain objects to `exports`, and instance methods as
      // properties of those sub-objects.
      InstanceValue("subObject", DefineProperties(Napi::Object::New(), {
        InstanceMethod("decrement", &ExampleAddon::Decrement
      })), napi_enumerable)
    });
  }
 private:

  // This method has access to the data stored in the environment because it is
  // an instance method of `ExampleAddon` and because it was listed among the
  // property descriptors passed to `DefineAddon()` in the constructor.
  Napi::Value Increment(const Napi::CallbackInfo& info) {
    return Napi::Number::New(info.Env(), ++value);
  }

  // This method has access to the data stored in the environment because it is
  // an instance method of `ExampleAddon` and because it was exposed to
  // JavaScript by calling `DefineProperties()` with the object onto which it is
  // attached.
  Napi::Value Decrement(const Napi::CallbackInfo& info) {
    return Napi::Number::New(info.Env(), --value);
  }

  // Data stored in these variables is unique to each instance of the add-on.
  uint32_t value = 42;
};

// The macro announces that instances of the class `ExampleAddon` will be
// created for each instance of the add-on that must be loaded into Node.js.
NODE_API_ADDON(ExampleAddon)
```

The above code can be used from JavaScript as follows:

```js
'use strict'

const exampleAddon = require('bindings')('example_addon');
console.log(exampleAddon.increment()); // prints 43
console.log(exampleAddon.increment()); // prints 44
consnole.log(exampleAddon.subObject.decrement()); // prints 43
```

When Node.js loads an instance of the add-on, a new instance of the class is
created. Its constructor receives the environment `Napi::Env env` and the
exports object `Napi::Object exports`. It can then use the method `DefineAddon`
to either attach methods, accessors, and/or values to the `exports` object or to
create its own `exports` object and attach methods, accessors, and/or values to
it.

Functions created with `Napi::Function::New()`, accessors created with
`PropertyDescriptor::Accessor()`, and values can also be attached. If their
implementation requires the `ExampleAddon` instance, it can be retrieved from
the `Napi::Env env` with `GetInstanceData()`:

```cpp
void ExampleBinding(const Napi::CallbackInfo& info) {
  ExampleAddon* addon = info.Env().GetInstanceData<ExampleAddon>();
}
```

## Methods

### Constructor

Creates a new instance of the add-on.

```cpp
Napi::Addon(Napi::Env env, Napi::Object exports);
```

- `[in] env`: The environment into which the add-on is being loaded.
- `[in] exports`: The exports object received from JavaScript.

Typically, the constructor calls `DefineAddon()` to attach methods, accessors,
and/or values to `exports`. The constructor may also create a new object and
pass it to `DefineAddon()` as its first parameter if it wishes to replace the
`exports` object as provided by Node.js.

### DefineAddon

Defines an add-on instance with functions, accessors, and/or values.

```cpp
template <typename T>
void Napi::Addon<T>::DefineAddon(Napi::Object exports,
                   const std::initializer_list<PropertyDescriptor>& properties);
```

* `[in] exports`: The object to return to Node.js as an instance of the add-on.
* `[in] properties`: Initializer list of add-on property descriptors of the
methods, property accessors, and values that define the add-on. They will be
set on `exports`.
See: [`Class property and descriptor`](class_property_descriptor.md).

### DefineProperties

Defines function, accessor, and/or value properties on an object using add-on
instance methods.

```cpp
template <typename T>
Napi::Object
Napi::Addon<T>::DefineProperties(Napi::Object object,
                   const std::initializer_list<PropertyDescriptor>& properties);
```

* `[in] object`: The object that will receive the new properties.
* `[in] properties`: Initializer list of property descriptors of the methods,
property accessors, and values to attach to `object`.
See: [`Class property and descriptor`](class_property_descriptor.md).

Returns `object`.

[`Napi::InstanceWrap<T>`]: ./instance_wrap.md
