'use strict';

/**
 * Takes an array of [keyValue1, keyValue2] pairs and creates an object of {keyValue1: keyValue2, keyValue2: keyValue1}
 * @param {Array} array the array of pairs
 * @return {Object} the {key, value} pair object
 */
function arrayToObject(array) {
  return array.reduce(function (obj, _ref) {
    var prop1 = _ref[0],
        prop2 = _ref[1];
    obj[prop1] = prop2;
    obj[prop2] = prop1;
    return obj;
  }, {});
}

function isBoolean(val) {
  return typeof val === 'boolean';
}

function isFunction(val) {
  return typeof val === 'function';
}

function isNumber(val) {
  return typeof val === 'number';
}

function isNullOrUndefined(val) {
  return val === null || typeof val === 'undefined';
}

function isObject(val) {
  return val && typeof val === 'object';
}

function isString(val) {
  return typeof val === 'string';
}

function includes(inclusive, inclusee) {
  return inclusive.indexOf(inclusee) !== -1;
}
/**
 * Flip the sign of a CSS value, possibly with a unit.
 *
 * We can't just negate the value with unary minus due to the units.
 *
 * @private
 * @param {String} value - the original value (for example 77%)
 * @return {String} the result (for example -77%)
 */


function flipSign(value) {
  if (parseFloat(value) === 0) {
    // Don't mangle zeroes
    return value;
  }

  if (value[0] === '-') {
    return value.slice(1);
  }

  return "-" + value;
}

function flipTransformSign(match, prefix, offset, suffix) {
  return prefix + flipSign(offset) + suffix;
}
/**
 * Takes a percentage for background position and inverts it.
 * This was copied and modified from CSSJanus:
 * https://github.com/cssjanus/cssjanus/blob/4245f834365f6cfb0239191a151432fb85abab23/src/cssjanus.js#L152-L175
 * @param {String} value - the original value (for example 77%)
 * @return {String} the result (for example 23%)
 */


function calculateNewBackgroundPosition(value) {
  var idx = value.indexOf('.');

  if (idx === -1) {
    value = 100 - parseFloat(value) + "%";
  } else {
    // Two off, one for the "%" at the end, one for the dot itself
    var len = value.length - idx - 2;
    value = 100 - parseFloat(value);
    value = value.toFixed(len) + "%";
  }

  return value;
}
/**
 * This takes a list of CSS values and converts it to an array
 * @param {String} value - something like `1px`, `1px 2em`, or `3pt rgb(150, 230, 550) 40px calc(100% - 5px)`
 * @return {Array} the split values (for example: `['3pt', 'rgb(150, 230, 550)', '40px', 'calc(100% - 5px)']`)
 */


function getValuesAsList(value) {
  return value.replace(/ +/g, ' ') // remove all extraneous spaces
  .split(' ').map(function (i) {
    return i.trim();
  }) // get rid of extra space before/after each item
  .filter(Boolean) // get rid of empty strings
  // join items which are within parenthese
  // luckily `calc (100% - 5px)` is invalid syntax and it must be `calc(100% - 5px)`, otherwise this would be even more complex
  .reduce(function (_ref2, item) {
    var list = _ref2.list,
        state = _ref2.state;
    var openParansCount = (item.match(/\(/g) || []).length;
    var closedParansCount = (item.match(/\)/g) || []).length;

    if (state.parensDepth > 0) {
      list[list.length - 1] = list[list.length - 1] + " " + item;
    } else {
      list.push(item);
    }

    state.parensDepth += openParansCount - closedParansCount;
    return {
      list: list,
      state: state
    };
  }, {
    list: [],
    state: {
      parensDepth: 0
    }
  }).list;
}
/**
 * This is intended for properties that are `top right bottom left` and will switch them to `top left bottom right`
 * @param {String} value - `1px 2px 3px 4px` for example, but also handles cases where there are too few/too many and
 * simply returns the value in those cases (which is the correct behavior)
 * @return {String} the result - `1px 4px 3px 2px` for example.
 */


function handleQuartetValues(value) {
  var splitValues = getValuesAsList(value);

  if (splitValues.length <= 3 || splitValues.length > 4) {
    return value;
  }

  var top = splitValues[0],
      right = splitValues[1],
      bottom = splitValues[2],
      left = splitValues[3];
  return [top, left, bottom, right].join(' ');
}

var propertyValueConverters = {
  padding: function padding(_ref) {
    var value = _ref.value;

    if (isNumber(value)) {
      return value;
    }

    return handleQuartetValues(value);
  },
  textShadow: function textShadow(_ref2) {
    var value = _ref2.value;
    // intentionally leaving off the `g` flag here because we only want to change the first number (which is the offset-x)
    return value.replace(/(-*)([.|\d]+)/, function (match, negative, number) {
      if (number === '0') {
        return match;
      }

      var doubleNegative = negative === '' ? '-' : '';
      return "" + doubleNegative + number;
    });
  },
  borderColor: function borderColor(_ref3) {
    var value = _ref3.value;
    return handleQuartetValues(value);
  },
  borderRadius: function borderRadius(_ref4) {
    var value = _ref4.value;

    if (isNumber(value)) {
      return value;
    }

    if (includes(value, '/')) {
      var _value$split = value.split('/'),
          radius1 = _value$split[0],
          radius2 = _value$split[1];

      var convertedRadius1 = propertyValueConverters.borderRadius({
        value: radius1.trim()
      });
      var convertedRadius2 = propertyValueConverters.borderRadius({
        value: radius2.trim()
      });
      return convertedRadius1 + " / " + convertedRadius2;
    }

    var splitValues = getValuesAsList(value);

    switch (splitValues.length) {
      case 2:
        {
          return splitValues.reverse().join(' ');
        }

      case 4:
        {
          var topLeft = splitValues[0],
              topRight = splitValues[1],
              bottomRight = splitValues[2],
              bottomLeft = splitValues[3];
          return [topRight, topLeft, bottomLeft, bottomRight].join(' ');
        }

      default:
        {
          return value;
        }
    }
  },
  background: function background(_ref5) {
    var value = _ref5.value,
        valuesToConvert = _ref5.valuesToConvert,
        isRtl = _ref5.isRtl,
        bgImgDirectionRegex = _ref5.bgImgDirectionRegex,
        bgPosDirectionRegex = _ref5.bgPosDirectionRegex;
    // Yeah, this is in need of a refactor 🙃...
    // but this property is a tough cookie 🍪
    // get the backgroundPosition out of the string by removing everything that couldn't be the backgroundPosition value
    var backgroundPositionValue = value.replace(/(url\(.*?\))|(rgba?\(.*?\))|(hsl\(.*?\))|(#[a-fA-F0-9]+)|((^| )(\D)+( |$))/g, '').trim(); // replace that backgroundPosition value with the converted version

    value = value.replace(backgroundPositionValue, propertyValueConverters.backgroundPosition({
      value: backgroundPositionValue,
      valuesToConvert: valuesToConvert,
      isRtl: isRtl,
      bgPosDirectionRegex: bgPosDirectionRegex
    })); // do the backgroundImage value replacing on the whole value (because why not?)

    return propertyValueConverters.backgroundImage({
      value: value,
      valuesToConvert: valuesToConvert,
      bgImgDirectionRegex: bgImgDirectionRegex
    });
  },
  backgroundImage: function backgroundImage(_ref6) {
    var value = _ref6.value,
        valuesToConvert = _ref6.valuesToConvert,
        bgImgDirectionRegex = _ref6.bgImgDirectionRegex;

    if (!includes(value, 'url(') && !includes(value, 'linear-gradient(')) {
      return value;
    }

    return value.replace(bgImgDirectionRegex, function (match, g1, group2) {
      return match.replace(group2, valuesToConvert[group2]);
    });
  },
  backgroundPosition: function backgroundPosition(_ref7) {
    var value = _ref7.value,
        valuesToConvert = _ref7.valuesToConvert,
        isRtl = _ref7.isRtl,
        bgPosDirectionRegex = _ref7.bgPosDirectionRegex;
    return value // intentionally only grabbing the first instance of this because that represents `left`
    .replace(isRtl ? /^((-|\d|\.)+%)/ : null, function (match, group) {
      return calculateNewBackgroundPosition(group);
    }).replace(bgPosDirectionRegex, function (match) {
      return valuesToConvert[match];
    });
  },
  backgroundPositionX: function backgroundPositionX(_ref8) {
    var value = _ref8.value,
        valuesToConvert = _ref8.valuesToConvert,
        isRtl = _ref8.isRtl,
        bgPosDirectionRegex = _ref8.bgPosDirectionRegex;

    if (isNumber(value)) {
      return value;
    }

    return propertyValueConverters.backgroundPosition({
      value: value,
      valuesToConvert: valuesToConvert,
      isRtl: isRtl,
      bgPosDirectionRegex: bgPosDirectionRegex
    });
  },
  transition: function transition(_ref9) {
    var value = _ref9.value,
        propertiesToConvert = _ref9.propertiesToConvert;
    return value.split(/,\s*/g).map(function (transition) {
      var values = transition.split(' '); // Property is always defined first

      values[0] = propertiesToConvert[values[0]] || values[0];
      return values.join(' ');
    }).join(', ');
  },
  transitionProperty: function transitionProperty(_ref10) {
    var value = _ref10.value,
        propertiesToConvert = _ref10.propertiesToConvert;
    return value.split(/,\s*/g).map(function (prop) {
      return propertiesToConvert[prop] || prop;
    }).join(', ');
  },
  transform: function transform(_ref11) {
    var value = _ref11.value;
    // This was copied and modified from CSSJanus:
    // https://github.com/cssjanus/cssjanus/blob/4a40f001b1ba35567112d8b8e1d9d95eda4234c3/src/cssjanus.js#L152-L153
    var nonAsciiPattern = "[^\\u0020-\\u007e]";
    var escapePattern = "(?:" + '(?:(?:\\[0-9a-f]{1,6})(?:\\r\\n|\\s)?)' + "|\\\\[^\\r\\n\\f0-9a-f])";
    var signedQuantPattern = "((?:-?" + ('(?:[0-9]*\\.[0-9]+|[0-9]+)' + "(?:\\s*" + '(?:em|ex|px|cm|mm|in|pt|pc|deg|rad|grad|ms|s|hz|khz|%)' + "|" + ("-?" + ("(?:[_a-z]|" + nonAsciiPattern + "|" + escapePattern + ")") + ("(?:[_a-z0-9-]|" + nonAsciiPattern + "|" + escapePattern + ")") + "*") + ")?") + ")|(?:inherit|auto))";
    var translateXRegExp = new RegExp("(translateX\\s*\\(\\s*)" + signedQuantPattern + "(\\s*\\))", 'gi');
    var translateRegExp = new RegExp("(translate\\s*\\(\\s*)" + signedQuantPattern + "((?:\\s*,\\s*" + signedQuantPattern + "){0,1}\\s*\\))", 'gi');
    var translate3dRegExp = new RegExp("(translate3d\\s*\\(\\s*)" + signedQuantPattern + "((?:\\s*,\\s*" + signedQuantPattern + "){0,2}\\s*\\))", 'gi');
    var rotateRegExp = new RegExp("(rotate[ZY]?\\s*\\(\\s*)" + signedQuantPattern + "(\\s*\\))", 'gi');
    return value.replace(translateXRegExp, flipTransformSign).replace(translateRegExp, flipTransformSign).replace(translate3dRegExp, flipTransformSign).replace(rotateRegExp, flipTransformSign);
  }
};
propertyValueConverters.objectPosition = propertyValueConverters.backgroundPosition;
propertyValueConverters.margin = propertyValueConverters.padding;
propertyValueConverters.borderWidth = propertyValueConverters.padding;
propertyValueConverters.boxShadow = propertyValueConverters.textShadow;
propertyValueConverters.webkitBoxShadow = propertyValueConverters.boxShadow;
propertyValueConverters.mozBoxShadow = propertyValueConverters.boxShadow;
propertyValueConverters.WebkitBoxShadow = propertyValueConverters.boxShadow;
propertyValueConverters.MozBoxShadow = propertyValueConverters.boxShadow;
propertyValueConverters.borderStyle = propertyValueConverters.borderColor;
propertyValueConverters.webkitTransform = propertyValueConverters.transform;
propertyValueConverters.mozTransform = propertyValueConverters.transform;
propertyValueConverters.WebkitTransform = propertyValueConverters.transform;
propertyValueConverters.MozTransform = propertyValueConverters.transform;
propertyValueConverters.transformOrigin = propertyValueConverters.backgroundPosition;
propertyValueConverters.webkitTransformOrigin = propertyValueConverters.transformOrigin;
propertyValueConverters.mozTransformOrigin = propertyValueConverters.transformOrigin;
propertyValueConverters.WebkitTransformOrigin = propertyValueConverters.transformOrigin;
propertyValueConverters.MozTransformOrigin = propertyValueConverters.transformOrigin;
propertyValueConverters.webkitTransition = propertyValueConverters.transition;
propertyValueConverters.mozTransition = propertyValueConverters.transition;
propertyValueConverters.WebkitTransition = propertyValueConverters.transition;
propertyValueConverters.MozTransition = propertyValueConverters.transition;
propertyValueConverters.webkitTransitionProperty = propertyValueConverters.transitionProperty;
propertyValueConverters.mozTransitionProperty = propertyValueConverters.transitionProperty;
propertyValueConverters.WebkitTransitionProperty = propertyValueConverters.transitionProperty;
propertyValueConverters.MozTransitionProperty = propertyValueConverters.transitionProperty; // kebab-case versions

propertyValueConverters['text-shadow'] = propertyValueConverters.textShadow;
propertyValueConverters['border-color'] = propertyValueConverters.borderColor;
propertyValueConverters['border-radius'] = propertyValueConverters.borderRadius;
propertyValueConverters['background-image'] = propertyValueConverters.backgroundImage;
propertyValueConverters['background-position'] = propertyValueConverters.backgroundPosition;
propertyValueConverters['background-position-x'] = propertyValueConverters.backgroundPositionX;
propertyValueConverters['object-position'] = propertyValueConverters.objectPosition;
propertyValueConverters['border-width'] = propertyValueConverters.padding;
propertyValueConverters['box-shadow'] = propertyValueConverters.textShadow;
propertyValueConverters['-webkit-box-shadow'] = propertyValueConverters.textShadow;
propertyValueConverters['-moz-box-shadow'] = propertyValueConverters.textShadow;
propertyValueConverters['border-style'] = propertyValueConverters.borderColor;
propertyValueConverters['-webkit-transform'] = propertyValueConverters.transform;
propertyValueConverters['-moz-transform'] = propertyValueConverters.transform;
propertyValueConverters['transform-origin'] = propertyValueConverters.transformOrigin;
propertyValueConverters['-webkit-transform-origin'] = propertyValueConverters.transformOrigin;
propertyValueConverters['-moz-transform-origin'] = propertyValueConverters.transformOrigin;
propertyValueConverters['-webkit-transition'] = propertyValueConverters.transition;
propertyValueConverters['-moz-transition'] = propertyValueConverters.transition;
propertyValueConverters['transition-property'] = propertyValueConverters.transitionProperty;
propertyValueConverters['-webkit-transition-property'] = propertyValueConverters.transitionProperty;
propertyValueConverters['-moz-transition-property'] = propertyValueConverters.transitionProperty;

var propertiesToConvert = arrayToObject([['paddingLeft', 'paddingRight'], ['marginLeft', 'marginRight'], ['left', 'right'], ['borderLeft', 'borderRight'], ['borderLeftColor', 'borderRightColor'], ['borderLeftStyle', 'borderRightStyle'], ['borderLeftWidth', 'borderRightWidth'], ['borderTopLeftRadius', 'borderTopRightRadius'], ['borderBottomLeftRadius', 'borderBottomRightRadius'], // kebab-case versions
['padding-left', 'padding-right'], ['margin-left', 'margin-right'], ['border-left', 'border-right'], ['border-left-color', 'border-right-color'], ['border-left-style', 'border-right-style'], ['border-left-width', 'border-right-width'], ['border-top-left-radius', 'border-top-right-radius'], ['border-bottom-left-radius', 'border-bottom-right-radius']]);
var propsToIgnore = ['content']; // this is the same as the propertiesToConvert except for values

var valuesToConvert = arrayToObject([['ltr', 'rtl'], ['left', 'right'], ['w-resize', 'e-resize'], ['sw-resize', 'se-resize'], ['nw-resize', 'ne-resize']]); // Sorry for the regex 😞, but basically thisis used to replace _every_ instance of
// `ltr`, `rtl`, `right`, and `left` in `backgroundimage` with the corresponding opposite.
// A situation we're accepting here:
// url('/left/right/rtl/ltr.png') will be changed to url('/right/left/ltr/rtl.png')
// Definite trade-offs here, but I think it's a good call.

var bgImgDirectionRegex = new RegExp('(^|\\W|_)((ltr)|(rtl)|(left)|(right))(\\W|_|$)', 'g');
var bgPosDirectionRegex = new RegExp('(left)|(right)');
/**
 * converts properties and values in the CSS in JS object to their corresponding RTL values
 * @param {Object} object the CSS in JS object
 * @return {Object} the RTL converted object
 */

function convert(object) {
  return Object.keys(object).reduce(function (newObj, originalKey) {
    var originalValue = object[originalKey];

    if (isString(originalValue)) {
      // you're welcome to later code 😺
      originalValue = originalValue.trim();
    } // Some properties should never be transformed


    if (includes(propsToIgnore, originalKey)) {
      newObj[originalKey] = originalValue;
      return newObj;
    }

    var _convertProperty = convertProperty(originalKey, originalValue),
        key = _convertProperty.key,
        value = _convertProperty.value;

    newObj[key] = value;
    return newObj;
  }, Array.isArray(object) ? [] : {});
}
/**
 * Converts a property and its value to the corresponding RTL key and value
 * @param {String} originalKey the original property key
 * @param {Number|String|Object} originalValue the original css property value
 * @return {Object} the new {key, value} pair
 */

function convertProperty(originalKey, originalValue) {
  var isNoFlip = /\/\*\s?@noflip\s?\*\//.test(originalValue);
  var key = isNoFlip ? originalKey : getPropertyDoppelganger(originalKey);
  var value = isNoFlip ? originalValue : getValueDoppelganger(key, originalValue);
  return {
    key: key,
    value: value
  };
}
/**
 * This gets the RTL version of the given property if it has a corresponding RTL property
 * @param {String} property the name of the property
 * @return {String} the name of the RTL property
 */

function getPropertyDoppelganger(property) {
  return propertiesToConvert[property] || property;
}
/**
 * This converts the given value to the RTL version of that value based on the key
 * @param {String} key this is the key (note: this should be the RTL version of the originalKey)
 * @param {String|Number|Object} originalValue the original css property value. If it's an object, then we'll convert that as well
 * @return {String|Number|Object} the converted value
 */

function getValueDoppelganger(key, originalValue) {
  /* eslint complexity:[2, 10] */
  // let's try to keep the complexity down... If we have to do this much more, let's break this up
  if (isNullOrUndefined(originalValue) || isBoolean(originalValue)) {
    return originalValue;
  }

  if (isObject(originalValue)) {
    return convert(originalValue); // recurssion 🌀
  }

  var isNum = isNumber(originalValue);
  var isFunc = isFunction(originalValue);
  var importantlessValue = isNum || isFunc ? originalValue : originalValue.replace(/ !important.*?$/, '');
  var isImportant = !isNum && importantlessValue.length !== originalValue.length;
  var valueConverter = propertyValueConverters[key];
  var newValue;

  if (valueConverter) {
    newValue = valueConverter({
      value: importantlessValue,
      valuesToConvert: valuesToConvert,
      propertiesToConvert: propertiesToConvert,
      isRtl: true,
      bgImgDirectionRegex: bgImgDirectionRegex,
      bgPosDirectionRegex: bgPosDirectionRegex
    });
  } else {
    newValue = valuesToConvert[importantlessValue] || importantlessValue;
  }

  if (isImportant) {
    return newValue + " !important";
  }

  return newValue;
}

exports.arrayToObject = arrayToObject;
exports.calculateNewBackgroundPosition = calculateNewBackgroundPosition;
exports.convert = convert;
exports.convertProperty = convertProperty;
exports.flipSign = flipSign;
exports.flipTransformSign = flipTransformSign;
exports.getPropertyDoppelganger = getPropertyDoppelganger;
exports.getValueDoppelganger = getValueDoppelganger;
exports.getValuesAsList = getValuesAsList;
exports.handleQuartetValues = handleQuartetValues;
exports.includes = includes;
exports.isBoolean = isBoolean;
exports.isFunction = isFunction;
exports.isNullOrUndefined = isNullOrUndefined;
exports.isNumber = isNumber;
exports.isObject = isObject;
exports.isString = isString;
exports.propertiesToConvert = propertiesToConvert;
exports.propertyValueConverters = propertyValueConverters;
exports.propsToIgnore = propsToIgnore;
exports.valuesToConvert = valuesToConvert;
