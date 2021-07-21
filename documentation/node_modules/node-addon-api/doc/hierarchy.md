# Full Class Hierarchy

| Class | Parent Class(es) |
|---|---|
| [`Napi::Addon`][] | [`Napi::InstanceWrap`][] |
| [`Napi::Array`][] | [`Napi::Object`][] |
| [`Napi::ArrayBuffer`][] | [`Napi::Object`][] |
| [`Napi::AsyncContext`][] |  |
| [`Napi::AsyncProgressQueueWorker`][] | `Napi::AsyncProgressWorkerBase` |
| [`Napi::AsyncProgressWorker`][] | `Napi::AsyncProgressWorkerBase` |
| [`Napi::AsyncWorker`][] |  |
| [`Napi::BigInt`][] | [`Napi::Value`][] |
| [`Napi::Boolean`][] | [`Napi::Value`][] |
| [`Napi::Buffer`][] | [`Napi::Uint8Array`][] |
| [`Napi::CallbackInfo`][] |  |
| [`Napi::CallbackScope`][] |  |
| [`Napi::ClassPropertyDescriptor`][] |  |
| [`Napi::DataView`][] | [`Napi::Object`][] |
| [`Napi::Date`][] | [`Napi::Value`][] |
| [`Napi::Env`][] |  |
| [`Napi::Error`][] | [`Napi::ObjectReference`][], [`std::exception`][] |
| [`Napi::EscapableHandleScope`][] |  |
| [`Napi::External`][] | [`Napi::Value`][] |
| [`Napi::Function`][] | [`Napi::Object`][] |
| [`Napi::FunctionReference`][] | [`Napi::Reference<Napi::Function>`][] |
| [`Napi::HandleScope`][] |  |
| [`Napi::InstanceWrap`][] |  |
| [`Napi::MemoryManagement`][] |  |
| [`Napi::Name`][] | [`Napi::Value`][] |
| [`Napi::Number`][] | [`Napi::Value`][] |
| [`Napi::Object`][] | [`Napi::Value`][] |
| [`Napi::ObjectReference`][] | [`Napi::Reference<Napi::Object>`][] |
| [`Napi::ObjectWrap`][] | [`Napi::InstanceWrap`][], [`Napi::Reference<Napi::Object>`][] |
| [`Napi::Promise`][] | [`Napi::Object`][] |
| [`Napi::PropertyDescriptor`][] |  |
| [`Napi::RangeError`][] | [`Napi::Error`][] |
| [`Napi::Reference`] |  |
| [`Napi::String`][] | [`Napi::Name`][] |
| [`Napi::Symbol`][] | [`Napi::Name`][] |
| [`Napi::ThreadSafeFunction`][] |  |
| [`Napi::TypeError`][] | [`Napi::Error`][] |
| [`Napi::TypedArray`][] | [`Napi::Object`][] |
| [`Napi::TypedArrayOf`][] | [`Napi::TypedArray`][] |
| [`Napi::Value`][] |  |
| [`Napi::VersionManagement`][] |  |

[`Napi::Addon`]: ./addon.md
[`Napi::Array`]: ./array.md
[`Napi::ArrayBuffer`]: ./array_buffer.md
[`Napi::AsyncContext`]: ./async_context.md
[`Napi::AsyncProgressQueueWorker`]: ./async_worker_variants.md#asyncprogressqueueworker
[`Napi::AsyncProgressWorker`]: ./async_worker_variants.md#asyncprogressworker
[`Napi::AsyncWorker`]: ./async_worker.md
[`Napi::BigInt`]: ./bigint.md
[`Napi::Boolean`]: ./boolean.md
[`Napi::Buffer`]: ./buffer.md
[`Napi::CallbackInfo`]: ./callbackinfo.md
[`Napi::CallbackScope`]: ./callback_scope.md
[`Napi::ClassPropertyDescriptor`]: ./class_property_descriptor.md
[`Napi::DataView`]: ./dataview.md
[`Napi::Date`]: ./date.md
[`Napi::Env`]: ./env.md
[`Napi::Error`]: ./error.md
[`Napi::EscapableHandleScope`]: ./escapable_handle_scope.md
[`Napi::External`]: ./external.md
[`Napi::Function`]: ./function.md
[`Napi::FunctionReference`]: ./function_reference.md
[`Napi::HandleScope`]: ./handle_scope.md
[`Napi::InstanceWrap`]: ./instance_wrap.md
[`Napi::MemoryManagement`]: ./memory_management.md
[`Napi::Name`]: ./name.md
[`Napi::Number`]: ./number.md
[`Napi::Object`]: ./object.md
[`Napi::ObjectReference`]: ./object_reference.md
[`Napi::ObjectWrap`]: ./object_wrap.md
[`Napi::Promise`]: ./promise.md
[`Napi::PropertyDescriptor`]: ./property_descriptor.md
[`Napi::RangeError`]: ./range_error.md
[`Napi::Reference`]: ./reference.md
[`Napi::Reference<Napi::Function>`]: ./reference.md
[`Napi::Reference<Napi::Object>`]: ./reference.md
[`Napi::String`]: ./string.md
[`Napi::Symbol`]: ./symbol.md
[`Napi::ThreadSafeFunction`]: ./thread_safe_function.md
[`Napi::TypeError`]: ./type_error.md
[`Napi::TypedArray`]: ./typed_array.md
[`Napi::TypedArrayOf`]: ./typed_array_of.md
[`Napi::Uint8Array`]: ./typed_array_of.md
[`Napi::Value`]: ./value.md
[`Napi::VersionManagement`]: ./version_management.md
[`std::exception`]: http://cplusplus.com/reference/exception/exception/
