#define NAPI_VERSION 1
#include <assert.h>
#include <node_api.h>

napi_value IsValidUTF8(napi_env env, napi_callback_info info) {
  napi_status status;
  size_t argc = 1;
  napi_value argv[1];

  status = napi_get_cb_info(env, info, &argc, argv, NULL, NULL);
  assert(status == napi_ok);

  uint8_t *s;
  size_t length;

  status = napi_get_buffer_info(env, argv[0], (void **)&s, &length);
  assert(status == napi_ok);

  uint8_t *end = s + length;

  //
  // This code has been taken from utf8_check.c which was developed by
  // Markus Kuhn <http://www.cl.cam.ac.uk/~mgk25/>.
  //
  // For original code / licensing please refer to
  // https://www.cl.cam.ac.uk/%7Emgk25/ucs/utf8_check.c
  //
  while (s < end) {
    if (*s < 0x80) {  // 0xxxxxxx
      s++;
    } else if ((s[0] & 0xe0) == 0xc0) {  // 110xxxxx 10xxxxxx
      if (
        s + 1 == end ||
        (s[1] & 0xc0) != 0x80 ||
        (s[0] & 0xfe) == 0xc0  // overlong
      ) {
        break;
      } else {
        s += 2;
      }
    } else if ((s[0] & 0xf0) == 0xe0) {  // 1110xxxx 10xxxxxx 10xxxxxx
      if (
        s + 2 >= end ||
        (s[1] & 0xc0) != 0x80 ||
        (s[2] & 0xc0) != 0x80 ||
        (s[0] == 0xe0 && (s[1] & 0xe0) == 0x80) ||
        (s[0] == 0xed && (s[1] & 0xe0) == 0xa0)
      ) {
        break;
      } else {
        s += 3;
      }
    } else if ((s[0] & 0xf8) == 0xf0) {  // 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
      if (
        s + 3 >= end ||
        (s[1] & 0xc0) != 0x80 ||
        (s[2] & 0xc0) != 0x80 ||
        (s[3] & 0xc0) != 0x80 ||
        (s[0] == 0xf0 && (s[1] & 0xf0) == 0x80) ||  // overlong
        (s[0] == 0xf4 && s[1] > 0x8f) || s[0] > 0xf4  // > U+10FFFF
      ) {
        break;
      } else {
        s += 4;
      }
    } else {
      break;
    }
  }

  napi_value result;
  status = napi_get_boolean(env, s == end, &result);
  assert(status == napi_ok);

  return result;
}

napi_value Init(napi_env env, napi_value exports) {
  napi_status status;
  napi_value isValidUTF8;

  status = napi_create_function(env, NULL, 0, IsValidUTF8, NULL, &isValidUTF8);
  assert(status == napi_ok);

  return isValidUTF8;
}

NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
