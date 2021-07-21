var _Object$defineProperties = require("@babel/runtime-corejs3/core-js/object/define-properties");

var _Object$freeze = require("@babel/runtime-corejs3/core-js/object/freeze");

var _sliceInstanceProperty = require("@babel/runtime-corejs3/core-js/instance/slice");

function _taggedTemplateLiteral(strings, raw) {
  if (!raw) {
    raw = _sliceInstanceProperty(strings).call(strings, 0);
  }

  return _Object$freeze(_Object$defineProperties(strings, {
    raw: {
      value: _Object$freeze(raw)
    }
  }));
}

module.exports = _taggedTemplateLiteral;