#include "napi.h"

static napi_value Getter_Core(napi_env env, napi_callback_info info) {
  (void) info;
  napi_value result;
  napi_status status = napi_create_uint32(env, 42, &result);
  NAPI_THROW_IF_FAILED(env, status, nullptr);
  return result;
}

static napi_value Setter_Core(napi_env env, napi_callback_info info) {
  size_t argc = 1;
  napi_value argv;
  napi_status status =
      napi_get_cb_info(env, info, &argc, &argv, nullptr, nullptr);
  NAPI_THROW_IF_FAILED(env, status, nullptr);
  (void) argv;
  return nullptr;
}

static Napi::Value Getter(const Napi::CallbackInfo& info) {
  return Napi::Number::New(info.Env(), 42);
}

static void Setter(const Napi::CallbackInfo& info) {
  (void) info[0];
}

#if NAPI_VERSION > 5
class PropDescBenchmark : public Napi::Addon<PropDescBenchmark> {
 public:
  PropDescBenchmark(Napi::Env, Napi::Object exports) {
    DefineAddon(exports, {
      InstanceAccessor("addon",
                       &PropDescBenchmark::Getter,
                       &PropDescBenchmark::Setter,
                       napi_enumerable),
      InstanceAccessor<&PropDescBenchmark::Getter,
                       &PropDescBenchmark::Setter>("addon_templated",
                                                   napi_enumerable),
    });
  }

 private:
  Napi::Value Getter(const Napi::CallbackInfo& info) {
    return Napi::Number::New(info.Env(), 42);
  }

  void Setter(const Napi::CallbackInfo& info, const Napi::Value& val) {
    (void) info[0];
    (void) val;
  }
};
#endif  // NAPI_VERSION > 5

static Napi::Object Init(Napi::Env env, Napi::Object exports) {
  napi_status status;
  napi_property_descriptor core_prop = {
    "core",
    nullptr,
    nullptr,
    Getter_Core,
    Setter_Core,
    nullptr,
    napi_enumerable,
    nullptr
  };

  status = napi_define_properties(env, exports, 1, &core_prop);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  exports.DefineProperty(
      Napi::PropertyDescriptor::Accessor(env,
                                         exports,
                                         "cplusplus",
                                         Getter,
                                         Setter,
                                         napi_enumerable));

  exports.DefineProperty(
      Napi::PropertyDescriptor::Accessor<Getter, Setter>("templated",
                                                         napi_enumerable));

#if NAPI_VERSION > 5
  PropDescBenchmark::Init(env, exports);
#endif  // NAPI_VERSION > 5

  return exports;
}

NODE_API_MODULE(NODE_GYP_MODULE_NAME, Init)
