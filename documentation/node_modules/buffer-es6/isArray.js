var toString = {}.toString;

export default Array.isArray || function (arr) {
  return toString.call(arr) == '[object Array]';
};
