"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = suggestionList;

/**
 * Given an invalid input string and a list of valid options, returns a filtered
 * list of valid options sorted based on their similarity with the input.
 */
function suggestionList(input, options) {
  var optionsByDistance = Object.create(null);
  var inputThreshold = input.length / 2;

  for (var _i2 = 0; _i2 < options.length; _i2++) {
    var option = options[_i2];
    var distance = lexicalDistance(input, option);
    var threshold = Math.max(inputThreshold, option.length / 2, 1);

    if (distance <= threshold) {
      optionsByDistance[option] = distance;
    }
  }

  return Object.keys(optionsByDistance).sort(function (a, b) {
    return optionsByDistance[a] - optionsByDistance[b];
  });
}
/**
 * Computes the lexical distance between strings A and B.
 *
 * The "distance" between two strings is given by counting the minimum number
 * of edits needed to transform string A into string B. An edit can be an
 * insertion, deletion, or substitution of a single character, or a swap of two
 * adjacent characters.
 *
 * Includes a custom alteration from Damerau-Levenshtein to treat case changes
 * as a single edit which helps identify mis-cased values with an edit distance
 * of 1.
 *
 * This distance can be useful for detecting typos in input or sorting
 *
 * @param {string} a
 * @param {string} b
 * @return {int} distance in number of edits
 */


function lexicalDistance(aStr, bStr) {
  if (aStr === bStr) {
    return 0;
  }

  var d = [];
  var a = aStr.toLowerCase();
  var b = bStr.toLowerCase();
  var aLength = a.length;
  var bLength = b.length; // Any case change counts as a single edit

  if (a === b) {
    return 1;
  }

  for (var i = 0; i <= aLength; i++) {
    d[i] = [i];
  }

  for (var j = 1; j <= bLength; j++) {
    d[0][j] = j;
  }

  for (var _i3 = 1; _i3 <= aLength; _i3++) {
    for (var _j = 1; _j <= bLength; _j++) {
      var cost = a[_i3 - 1] === b[_j - 1] ? 0 : 1;
      d[_i3][_j] = Math.min(d[_i3 - 1][_j] + 1, d[_i3][_j - 1] + 1, d[_i3 - 1][_j - 1] + cost);

      if (_i3 > 1 && _j > 1 && a[_i3 - 1] === b[_j - 2] && a[_i3 - 2] === b[_j - 1]) {
        d[_i3][_j] = Math.min(d[_i3][_j], d[_i3 - 2][_j - 2] + cost);
      }
    }
  }

  return d[aLength][bLength];
}
