#include "napi.h"

static napi_value NoArgFunction_Core(napi_env env, napi_callback_info info) {
  (void) env;
  (void) info;
  return nullptr;
}

static napi_value OneArgFunction_Core(napi_env env, napi_callback_info info) {
  size_t argc = 1;
  napi_value argv;
  if (napi_get_cb_info(env, info, &argc, &argv, nullptr, nullptr) != napi_ok) {
    return nullptr;
  }
  (void) argv;
  return nullptr;
}

static napi_value TwoArgFunction_Core(napi_env env, napi_callback_info info) {
  size_t argc = 2;
  napi_value argv[2];
  if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok) {
    return nullptr;
  }
  (void) argv[0];
  (void) argv[1];
  return nullptr;
}

static napi_value ThreeArgFunction_Core(napi_env env, napi_callback_info info) {
  size_t argc = 3;
  napi_value argv[3];
  if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok) {
    return nullptr;
  }
  (void) argv[0];
  (void) argv[1];
  (void) argv[2];
  return nullptr;
}

static napi_value FourArgFunction_Core(napi_env env, napi_callback_info info) {
  size_t argc = 4;
  napi_value argv[4];
  if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok) {
    return nullptr;
  }
  (void) argv[0];
  (void) argv[1];
  (void) argv[2];
  (void) argv[3];
  return nullptr;
}

static void NoArgFunction(const Napi::CallbackInfo& info) {
  (void) info;
}

static void OneArgFunction(const Napi::CallbackInfo& info) {
  Napi::Value argv0 = info[0]; (void) argv0;
}

static void TwoArgFunction(const Napi::CallbackInfo& info) {
  Napi::Value argv0 = info[0]; (void) argv0;
  Napi::Value argv1 = info[1]; (void) argv1;
}

static void ThreeArgFunction(const Napi::CallbackInfo& info) {
  Napi::Value argv0 = info[0]; (void) argv0;
  Napi::Value argv1 = info[1]; (void) argv1;
  Napi::Value argv2 = info[2]; (void) argv2;
}

static void FourArgFunction(const Napi::CallbackInfo& info) {
  Napi::Value argv0 = info[0]; (void) argv0;
  Napi::Value argv1 = info[1]; (void) argv1;
  Napi::Value argv2 = info[2]; (void) argv2;
  Napi::Value argv3 = info[3]; (void) argv3;
}

#if NAPI_VERSION > 5
class FunctionArgsBenchmark : public Napi::Addon<FunctionArgsBenchmark> {
 public:
  FunctionArgsBenchmark(Napi::Env env, Napi::Object exports) {
    DefineAddon(exports, {
      InstanceValue("addon", DefineProperties(Napi::Object::New(env), {
        InstanceMethod("noArgFunction", &FunctionArgsBenchmark::NoArgFunction),
        InstanceMethod("oneArgFunction",
                       &FunctionArgsBenchmark::OneArgFunction),
        InstanceMethod("twoArgFunction",
                       &FunctionArgsBenchmark::TwoArgFunction),
        InstanceMethod("threeArgFunction",
                       &FunctionArgsBenchmark::ThreeArgFunction),
        InstanceMethod("fourArgFunction",
                       &FunctionArgsBenchmark::FourArgFunction),
      }), napi_enumerable),
      InstanceValue("addon_templated",
        DefineProperties(Napi::Object::New(env), {
          InstanceMethod<&FunctionArgsBenchmark::NoArgFunction>(
                                                            "noArgFunction"),
          InstanceMethod<&FunctionArgsBenchmark::OneArgFunction>(
                                                            "oneArgFunction"),
          InstanceMethod<&FunctionArgsBenchmark::TwoArgFunction>(
                                                            "twoArgFunction"),
          InstanceMethod<&FunctionArgsBenchmark::ThreeArgFunction>(
                                                            "threeArgFunction"),
          InstanceMethod<&FunctionArgsBenchmark::FourArgFunction>(
                                                            "fourArgFunction"),
        }), napi_enumerable),
    });
  }
 private:
  void NoArgFunction(const Napi::CallbackInfo& info) {
    (void) info;
  }

  void OneArgFunction(const Napi::CallbackInfo& info) {
    Napi::Value argv0 = info[0]; (void) argv0;
  }

  void TwoArgFunction(const Napi::CallbackInfo& info) {
    Napi::Value argv0 = info[0]; (void) argv0;
    Napi::Value argv1 = info[1]; (void) argv1;
  }

  void ThreeArgFunction(const Napi::CallbackInfo& info) {
    Napi::Value argv0 = info[0]; (void) argv0;
    Napi::Value argv1 = info[1]; (void) argv1;
    Napi::Value argv2 = info[2]; (void) argv2;
  }

  void FourArgFunction(const Napi::CallbackInfo& info) {
    Napi::Value argv0 = info[0]; (void) argv0;
    Napi::Value argv1 = info[1]; (void) argv1;
    Napi::Value argv2 = info[2]; (void) argv2;
    Napi::Value argv3 = info[3]; (void) argv3;
  }
};
#endif  // NAPI_VERSION > 5

static Napi::Object Init(Napi::Env env, Napi::Object exports) {
  napi_value no_arg_function, one_arg_function, two_arg_function,
      three_arg_function, four_arg_function;
  napi_status status;

  status = napi_create_function(env,
                                "noArgFunction",
                                NAPI_AUTO_LENGTH,
                                NoArgFunction_Core,
                                nullptr,
                                &no_arg_function);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  status = napi_create_function(env,
                                "oneArgFunction",
                                NAPI_AUTO_LENGTH,
                                OneArgFunction_Core,
                                nullptr,
                                &one_arg_function);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  status = napi_create_function(env,
                                "twoArgFunction",
                                NAPI_AUTO_LENGTH,
                                TwoArgFunction_Core,
                                nullptr,
                                &two_arg_function);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  status = napi_create_function(env,
                                "threeArgFunction",
                                NAPI_AUTO_LENGTH,
                                ThreeArgFunction_Core,
                                nullptr,
                                &three_arg_function);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  status = napi_create_function(env,
                                "fourArgFunction",
                                NAPI_AUTO_LENGTH,
                                FourArgFunction_Core,
                                nullptr,
                                &four_arg_function);
  NAPI_THROW_IF_FAILED(env, status, Napi::Object());

  Napi::Object core = Napi::Object::New(env);
  core["noArgFunction"] = Napi::Value(env, no_arg_function);
  core["oneArgFunction"] = Napi::Value(env, one_arg_function);
  core["twoArgFunction"] = Napi::Value(env, two_arg_function);
  core["threeArgFunction"] = Napi::Value(env, three_arg_function);
  core["fourArgFunction"] = Napi::Value(env, four_arg_function);
  exports["core"] = core;

  Napi::Object cplusplus = Napi::Object::New(env);
  cplusplus["noArgFunction"] = Napi::Function::New(env, NoArgFunction);
  cplusplus["oneArgFunction"] = Napi::Function::New(env, OneArgFunction);
  cplusplus["twoArgFunction"] = Napi::Function::New(env, TwoArgFunction);
  cplusplus["threeArgFunction"] = Napi::Function::New(env, ThreeArgFunction);
  cplusplus["fourArgFunction"] = Napi::Function::New(env, FourArgFunction);
  exports["cplusplus"] = cplusplus;

  Napi::Object templated = Napi::Object::New(env);
  templated["noArgFunction"] = Napi::Function::New<NoArgFunction>(env);
  templated["oneArgFunction"] = Napi::Function::New<OneArgFunction>(env);
  templated["twoArgFunction"] = Napi::Function::New<TwoArgFunction>(env);
  templated["threeArgFunction"] = Napi::Function::New<ThreeArgFunction>(env);
  templated["fourArgFunction"] = Napi::Function::New<FourArgFunction>(env);
  exports["templated"] = templated;

#if NAPI_VERSION > 5
  FunctionArgsBenchmark::Init(env, exports);
#endif  // NAPI_VERSION > 5

  return exports;
}

NODE_API_MODULE(NODE_GYP_MODULE_NAME, Init)
