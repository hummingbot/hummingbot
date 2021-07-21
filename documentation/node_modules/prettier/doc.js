(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() :
  typeof define === 'function' && define.amd ? define(factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.doc = factory());
}(this, (function () { 'use strict';

  /**
   * @param {Doc[]} parts
   * @returns Doc
   */


  function concat(parts) {
    // access the internals of a document directly.
    // if(parts.length === 1) {
    //   // If it's a single document, no need to concat it.
    //   return parts[0];
    // }


    return {
      type: "concat",
      parts
    };
  }
  /**
   * @param {Doc} contents
   * @returns Doc
   */


  function indent(contents) {

    return {
      type: "indent",
      contents
    };
  }
  /**
   * @param {number | string} n
   * @param {Doc} contents
   * @returns Doc
   */


  function align(n, contents) {

    return {
      type: "align",
      contents,
      n
    };
  }
  /**
   * @param {Doc} contents
   * @param {object} [opts] - TBD ???
   * @returns Doc
   */


  function group(contents, opts) {
    opts = opts || {};

    return {
      type: "group",
      id: opts.id,
      contents,
      break: !!opts.shouldBreak,
      expandedStates: opts.expandedStates
    };
  }
  /**
   * @param {Doc} contents
   * @returns Doc
   */


  function dedentToRoot(contents) {
    return align(-Infinity, contents);
  }
  /**
   * @param {Doc} contents
   * @returns Doc
   */


  function markAsRoot(contents) {
    // @ts-ignore - TBD ???:
    return align({
      type: "root"
    }, contents);
  }
  /**
   * @param {Doc} contents
   * @returns Doc
   */


  function dedent(contents) {
    return align(-1, contents);
  }
  /**
   * @param {Doc[]} states
   * @param {object} [opts] - TBD ???
   * @returns Doc
   */


  function conditionalGroup(states, opts) {
    return group(states[0], Object.assign({}, opts, {
      expandedStates: states
    }));
  }
  /**
   * @param {Doc[]} parts
   * @returns Doc
   */


  function fill(parts) {

    return {
      type: "fill",
      parts
    };
  }
  /**
   * @param {Doc} [breakContents]
   * @param {Doc} [flatContents]
   * @param {object} [opts] - TBD ???
   * @returns Doc
   */


  function ifBreak(breakContents, flatContents, opts) {
    opts = opts || {};

    return {
      type: "if-break",
      breakContents,
      flatContents,
      groupId: opts.groupId
    };
  }
  /**
   * @param {Doc} contents
   * @returns Doc
   */


  function lineSuffix(contents) {

    return {
      type: "line-suffix",
      contents
    };
  }

  const lineSuffixBoundary = {
    type: "line-suffix-boundary"
  };
  const breakParent = {
    type: "break-parent"
  };
  const trim = {
    type: "trim"
  };
  const line = {
    type: "line"
  };
  const softline = {
    type: "line",
    soft: true
  };
  const hardline = concat([{
    type: "line",
    hard: true
  }, breakParent]);
  const literalline = concat([{
    type: "line",
    hard: true,
    literal: true
  }, breakParent]);
  const cursor = {
    type: "cursor",
    placeholder: Symbol("cursor")
  };
  /**
   * @param {Doc} sep
   * @param {Doc[]} arr
   * @returns Doc
   */

  function join(sep, arr) {
    const res = [];

    for (let i = 0; i < arr.length; i++) {
      if (i !== 0) {
        res.push(sep);
      }

      res.push(arr[i]);
    }

    return concat(res);
  }
  /**
   * @param {Doc} doc
   * @param {number} size
   * @param {number} tabWidth
   */


  function addAlignmentToDoc(doc, size, tabWidth) {
    let aligned = doc;

    if (size > 0) {
      // Use indent to add tabs for all the levels of tabs we need
      for (let i = 0; i < Math.floor(size / tabWidth); ++i) {
        aligned = indent(aligned);
      } // Use align for all the spaces that are needed


      aligned = align(size % tabWidth, aligned); // size is absolute from 0 and not relative to the current
      // indentation, so we use -Infinity to reset the indentation to 0

      aligned = align(-Infinity, aligned);
    }

    return aligned;
  }

  var docBuilders = {
    concat,
    join,
    line,
    softline,
    hardline,
    literalline,
    group,
    conditionalGroup,
    fill,
    lineSuffix,
    lineSuffixBoundary,
    cursor,
    breakParent,
    ifBreak,
    trim,
    indent,
    align,
    addAlignmentToDoc,
    markAsRoot,
    dedentToRoot,
    dedent
  };

  var ansiRegex = ({
    onlyFirst = false
  } = {}) => {
    const pattern = ['[\\u001B\\u009B][[\\]()#;?]*(?:(?:(?:[a-zA-Z\\d]*(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]*)*)?\\u0007)', '(?:(?:\\d{1,4}(?:;\\d{0,4})*)?[\\dA-PR-TZcf-ntqry=><~]))'].join('|');
    return new RegExp(pattern, onlyFirst ? undefined : 'g');
  };

  var stripAnsi = string => typeof string === 'string' ? string.replace(ansiRegex(), '') : string;

  /* eslint-disable yoda */

  const isFullwidthCodePoint = codePoint => {
    if (Number.isNaN(codePoint)) {
      return false;
    } // Code points are derived from:
    // http://www.unix.org/Public/UNIDATA/EastAsianWidth.txt


    if (codePoint >= 0x1100 && (codePoint <= 0x115F || // Hangul Jamo
    codePoint === 0x2329 || // LEFT-POINTING ANGLE BRACKET
    codePoint === 0x232A || // RIGHT-POINTING ANGLE BRACKET
    // CJK Radicals Supplement .. Enclosed CJK Letters and Months
    0x2E80 <= codePoint && codePoint <= 0x3247 && codePoint !== 0x303F || // Enclosed CJK Letters and Months .. CJK Unified Ideographs Extension A
    0x3250 <= codePoint && codePoint <= 0x4DBF || // CJK Unified Ideographs .. Yi Radicals
    0x4E00 <= codePoint && codePoint <= 0xA4C6 || // Hangul Jamo Extended-A
    0xA960 <= codePoint && codePoint <= 0xA97C || // Hangul Syllables
    0xAC00 <= codePoint && codePoint <= 0xD7A3 || // CJK Compatibility Ideographs
    0xF900 <= codePoint && codePoint <= 0xFAFF || // Vertical Forms
    0xFE10 <= codePoint && codePoint <= 0xFE19 || // CJK Compatibility Forms .. Small Form Variants
    0xFE30 <= codePoint && codePoint <= 0xFE6B || // Halfwidth and Fullwidth Forms
    0xFF01 <= codePoint && codePoint <= 0xFF60 || 0xFFE0 <= codePoint && codePoint <= 0xFFE6 || // Kana Supplement
    0x1B000 <= codePoint && codePoint <= 0x1B001 || // Enclosed Ideographic Supplement
    0x1F200 <= codePoint && codePoint <= 0x1F251 || // CJK Unified Ideographs Extension B .. Tertiary Ideographic Plane
    0x20000 <= codePoint && codePoint <= 0x3FFFD)) {
      return true;
    }

    return false;
  };

  var isFullwidthCodePoint_1 = isFullwidthCodePoint;
  var _default = isFullwidthCodePoint;
  isFullwidthCodePoint_1.default = _default;

  var emojiRegex = function emojiRegex() {
    // https://mths.be/emoji
    return /\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62(?:\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67|\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74|\uDB40\uDC77\uDB40\uDC6C\uDB40\uDC73)\uDB40\uDC7F|\uD83D\uDC68(?:\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68\uD83C\uDFFB|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFE])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83D\uDC68|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D[\uDC66\uDC67])|[\u2695\u2696\u2708]\uFE0F|\uD83D[\uDC66\uDC67]|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|(?:\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708])\uFE0F|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C[\uDFFB-\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFB\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)\uD83C\uDFFB|\uD83E\uDDD1(?:\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])|\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1)|(?:\uD83E\uDDD1\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFE])|(?:\uD83E\uDDD1\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)(?:\uD83C[\uDFFB\uDFFC])|\uD83D\uDC69(?:\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFC-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|(?:\uD83E\uDDD1\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)(?:\uD83C[\uDFFB-\uDFFD])|\uD83D\uDC69\u200D\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D\uDC41\uFE0F\u200D\uD83D\uDDE8|\uD83D\uDC69(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|(?:(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)\uFE0F|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF])\u200D[\u2640\u2642]|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD6-\uDDDD])(?:(?:\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|\u200D[\u2640\u2642])|\uD83C\uDFF4\u200D\u2620)\uFE0F|\uD83D\uDC69\u200D\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|\uD83C\uDFF3\uFE0F\u200D\uD83C\uDF08|\uD83D\uDC15\u200D\uD83E\uDDBA|\uD83D\uDC69\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC67|\uD83C\uDDFD\uD83C\uDDF0|\uD83C\uDDF4\uD83C\uDDF2|\uD83C\uDDF6\uD83C\uDDE6|[#\*0-9]\uFE0F\u20E3|\uD83C\uDDE7(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEF\uDDF1-\uDDF4\uDDF6-\uDDF9\uDDFB\uDDFC\uDDFE\uDDFF])|\uD83C\uDDF9(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDED\uDDEF-\uDDF4\uDDF7\uDDF9\uDDFB\uDDFC\uDDFF])|\uD83C\uDDEA(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDED\uDDF7-\uDDFA])|\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])|\uD83C\uDDF7(?:\uD83C[\uDDEA\uDDF4\uDDF8\uDDFA\uDDFC])|\uD83D\uDC69(?:\uD83C[\uDFFB-\uDFFF])|\uD83C\uDDF2(?:\uD83C[\uDDE6\uDDE8-\uDDED\uDDF0-\uDDFF])|\uD83C\uDDE6(?:\uD83C[\uDDE8-\uDDEC\uDDEE\uDDF1\uDDF2\uDDF4\uDDF6-\uDDFA\uDDFC\uDDFD\uDDFF])|\uD83C\uDDF0(?:\uD83C[\uDDEA\uDDEC-\uDDEE\uDDF2\uDDF3\uDDF5\uDDF7\uDDFC\uDDFE\uDDFF])|\uD83C\uDDED(?:\uD83C[\uDDF0\uDDF2\uDDF3\uDDF7\uDDF9\uDDFA])|\uD83C\uDDE9(?:\uD83C[\uDDEA\uDDEC\uDDEF\uDDF0\uDDF2\uDDF4\uDDFF])|\uD83C\uDDFE(?:\uD83C[\uDDEA\uDDF9])|\uD83C\uDDEC(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEE\uDDF1-\uDDF3\uDDF5-\uDDFA\uDDFC\uDDFE])|\uD83C\uDDF8(?:\uD83C[\uDDE6-\uDDEA\uDDEC-\uDDF4\uDDF7-\uDDF9\uDDFB\uDDFD-\uDDFF])|\uD83C\uDDEB(?:\uD83C[\uDDEE-\uDDF0\uDDF2\uDDF4\uDDF7])|\uD83C\uDDF5(?:\uD83C[\uDDE6\uDDEA-\uDDED\uDDF0-\uDDF3\uDDF7-\uDDF9\uDDFC\uDDFE])|\uD83C\uDDFB(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDEE\uDDF3\uDDFA])|\uD83C\uDDF3(?:\uD83C[\uDDE6\uDDE8\uDDEA-\uDDEC\uDDEE\uDDF1\uDDF4\uDDF5\uDDF7\uDDFA\uDDFF])|\uD83C\uDDE8(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDEE\uDDF0-\uDDF5\uDDF7\uDDFA-\uDDFF])|\uD83C\uDDF1(?:\uD83C[\uDDE6-\uDDE8\uDDEE\uDDF0\uDDF7-\uDDFB\uDDFE])|\uD83C\uDDFF(?:\uD83C[\uDDE6\uDDF2\uDDFC])|\uD83C\uDDFC(?:\uD83C[\uDDEB\uDDF8])|\uD83C\uDDFA(?:\uD83C[\uDDE6\uDDEC\uDDF2\uDDF3\uDDF8\uDDFE\uDDFF])|\uD83C\uDDEE(?:\uD83C[\uDDE8-\uDDEA\uDDF1-\uDDF4\uDDF6-\uDDF9])|\uD83C\uDDEF(?:\uD83C[\uDDEA\uDDF2\uDDF4\uDDF5])|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u261D\u270A-\u270D]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC70\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDCAA\uDD74\uDD7A\uDD90\uDD95\uDD96\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD36\uDDB5\uDDB6\uDDBB\uDDD2-\uDDD5])(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u270A\u270B\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF93\uDFA0-\uDFCA\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF4\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC3E\uDC40\uDC42-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDD7A\uDD95\uDD96\uDDA4\uDDFB-\uDE4F\uDE80-\uDEC5\uDECC\uDED0-\uDED2\uDED5\uDEEB\uDEEC\uDEF4-\uDEFA\uDFE0-\uDFEB]|\uD83E[\uDD0D-\uDD3A\uDD3C-\uDD45\uDD47-\uDD71\uDD73-\uDD76\uDD7A-\uDDA2\uDDA5-\uDDAA\uDDAE-\uDDCA\uDDCD-\uDDFF\uDE70-\uDE73\uDE78-\uDE7A\uDE80-\uDE82\uDE90-\uDE95])|(?:[#\*0-9\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]|\uD83C[\uDC04\uDCCF\uDD70\uDD71\uDD7E\uDD7F\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE02\uDE1A\uDE2F\uDE32-\uDE3A\uDE50\uDE51\uDF00-\uDF21\uDF24-\uDF93\uDF96\uDF97\uDF99-\uDF9B\uDF9E-\uDFF0\uDFF3-\uDFF5\uDFF7-\uDFFF]|\uD83D[\uDC00-\uDCFD\uDCFF-\uDD3D\uDD49-\uDD4E\uDD50-\uDD67\uDD6F\uDD70\uDD73-\uDD7A\uDD87\uDD8A-\uDD8D\uDD90\uDD95\uDD96\uDDA4\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA-\uDE4F\uDE80-\uDEC5\uDECB-\uDED2\uDED5\uDEE0-\uDEE5\uDEE9\uDEEB\uDEEC\uDEF0\uDEF3-\uDEFA\uDFE0-\uDFEB]|\uD83E[\uDD0D-\uDD3A\uDD3C-\uDD45\uDD47-\uDD71\uDD73-\uDD76\uDD7A-\uDDA2\uDDA5-\uDDAA\uDDAE-\uDDCA\uDDCD-\uDDFF\uDE70-\uDE73\uDE78-\uDE7A\uDE80-\uDE82\uDE90-\uDE95])\uFE0F|(?:[\u261D\u26F9\u270A-\u270D]|\uD83C[\uDF85\uDFC2-\uDFC4\uDFC7\uDFCA-\uDFCC]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66-\uDC78\uDC7C\uDC81-\uDC83\uDC85-\uDC87\uDC8F\uDC91\uDCAA\uDD74\uDD75\uDD7A\uDD90\uDD95\uDD96\uDE45-\uDE47\uDE4B-\uDE4F\uDEA3\uDEB4-\uDEB6\uDEC0\uDECC]|\uD83E[\uDD0F\uDD18-\uDD1F\uDD26\uDD30-\uDD39\uDD3C-\uDD3E\uDDB5\uDDB6\uDDB8\uDDB9\uDDBB\uDDCD-\uDDCF\uDDD1-\uDDDD])/g;
  };

  const stringWidth = string => {
    string = string.replace(emojiRegex(), '  ');

    if (typeof string !== 'string' || string.length === 0) {
      return 0;
    }

    string = stripAnsi(string);
    let width = 0;

    for (let i = 0; i < string.length; i++) {
      const code = string.codePointAt(i); // Ignore control characters

      if (code <= 0x1F || code >= 0x7F && code <= 0x9F) {
        continue;
      } // Ignore combining characters


      if (code >= 0x300 && code <= 0x36F) {
        continue;
      } // Surrogates


      if (code > 0xFFFF) {
        i++;
      }

      width += isFullwidthCodePoint_1(code) ? 2 : 1;
    }

    return width;
  };

  var stringWidth_1 = stringWidth; // TODO: remove this in the next major version

  var _default$1 = stringWidth;
  stringWidth_1.default = _default$1;

  var escapeStringRegexp = string => {
    if (typeof string !== 'string') {
      throw new TypeError('Expected a string');
    } // Escape characters with special meaning either inside or outside character sets.
    // Use a simple backslash escape when it’s always valid, and a \unnnn escape when the simpler form would be disallowed by Unicode patterns’ stricter grammar.


    return string.replace(/[|\\{}()[\]^$+*?.]/g, '\\$&').replace(/-/g, '\\x2d');
  };

  var getLast = arr => arr[arr.length - 1];

  function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    var sourceKeys = Object.keys(source);
    var key, i;

    for (i = 0; i < sourceKeys.length; i++) {
      key = sourceKeys[i];
      if (excluded.indexOf(key) >= 0) continue;
      target[key] = source[key];
    }

    return target;
  }

  function _taggedTemplateLiteral(strings, raw) {
    if (!raw) {
      raw = strings.slice(0);
    }

    return Object.freeze(Object.defineProperties(strings, {
      raw: {
        value: Object.freeze(raw)
      }
    }));
  }

  var global$1 = typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {};

  // based off https://github.com/defunctzombie/node-process/blob/master/browser.js

  function defaultSetTimout() {
    throw new Error('setTimeout has not been defined');
  }

  function defaultClearTimeout() {
    throw new Error('clearTimeout has not been defined');
  }

  var cachedSetTimeout = defaultSetTimout;
  var cachedClearTimeout = defaultClearTimeout;

  if (typeof global$1.setTimeout === 'function') {
    cachedSetTimeout = setTimeout;
  }

  if (typeof global$1.clearTimeout === 'function') {
    cachedClearTimeout = clearTimeout;
  }

  function runTimeout(fun) {
    if (cachedSetTimeout === setTimeout) {
      //normal enviroments in sane situations
      return setTimeout(fun, 0);
    } // if setTimeout wasn't available but was latter defined


    if ((cachedSetTimeout === defaultSetTimout || !cachedSetTimeout) && setTimeout) {
      cachedSetTimeout = setTimeout;
      return setTimeout(fun, 0);
    }

    try {
      // when when somebody has screwed with setTimeout but no I.E. maddness
      return cachedSetTimeout(fun, 0);
    } catch (e) {
      try {
        // When we are in I.E. but the script has been evaled so I.E. doesn't trust the global object when called normally
        return cachedSetTimeout.call(null, fun, 0);
      } catch (e) {
        // same as above but when it's a version of I.E. that must have the global object for 'this', hopfully our context correct otherwise it will throw a global error
        return cachedSetTimeout.call(this, fun, 0);
      }
    }
  }

  function runClearTimeout(marker) {
    if (cachedClearTimeout === clearTimeout) {
      //normal enviroments in sane situations
      return clearTimeout(marker);
    } // if clearTimeout wasn't available but was latter defined


    if ((cachedClearTimeout === defaultClearTimeout || !cachedClearTimeout) && clearTimeout) {
      cachedClearTimeout = clearTimeout;
      return clearTimeout(marker);
    }

    try {
      // when when somebody has screwed with setTimeout but no I.E. maddness
      return cachedClearTimeout(marker);
    } catch (e) {
      try {
        // When we are in I.E. but the script has been evaled so I.E. doesn't  trust the global object when called normally
        return cachedClearTimeout.call(null, marker);
      } catch (e) {
        // same as above but when it's a version of I.E. that must have the global object for 'this', hopfully our context correct otherwise it will throw a global error.
        // Some versions of I.E. have different rules for clearTimeout vs setTimeout
        return cachedClearTimeout.call(this, marker);
      }
    }
  }

  var queue = [];
  var draining = false;
  var currentQueue;
  var queueIndex = -1;

  function cleanUpNextTick() {
    if (!draining || !currentQueue) {
      return;
    }

    draining = false;

    if (currentQueue.length) {
      queue = currentQueue.concat(queue);
    } else {
      queueIndex = -1;
    }

    if (queue.length) {
      drainQueue();
    }
  }

  function drainQueue() {
    if (draining) {
      return;
    }

    var timeout = runTimeout(cleanUpNextTick);
    draining = true;
    var len = queue.length;

    while (len) {
      currentQueue = queue;
      queue = [];

      while (++queueIndex < len) {
        if (currentQueue) {
          currentQueue[queueIndex].run();
        }
      }

      queueIndex = -1;
      len = queue.length;
    }

    currentQueue = null;
    draining = false;
    runClearTimeout(timeout);
  }

  function nextTick(fun) {
    var args = new Array(arguments.length - 1);

    if (arguments.length > 1) {
      for (var i = 1; i < arguments.length; i++) {
        args[i - 1] = arguments[i];
      }
    }

    queue.push(new Item(fun, args));

    if (queue.length === 1 && !draining) {
      runTimeout(drainQueue);
    }
  } // v8 likes predictible objects

  function Item(fun, array) {
    this.fun = fun;
    this.array = array;
  }

  Item.prototype.run = function () {
    this.fun.apply(null, this.array);
  };

  var title = 'browser';
  var platform = 'browser';
  var browser = true;
  var env = {};
  var argv = [];
  var version = ''; // empty string to avoid regexp issues

  var versions = {};
  var release = {};
  var config = {};

  function noop() {}

  var on = noop;
  var addListener = noop;
  var once = noop;
  var off = noop;
  var removeListener = noop;
  var removeAllListeners = noop;
  var emit = noop;
  function binding(name) {
    throw new Error('process.binding is not supported');
  }
  function cwd() {
    return '/';
  }
  function chdir(dir) {
    throw new Error('process.chdir is not supported');
  }
  function umask() {
    return 0;
  } // from https://github.com/kumavis/browser-process-hrtime/blob/master/index.js

  var performance = global$1.performance || {};

  var performanceNow = performance.now || performance.mozNow || performance.msNow || performance.oNow || performance.webkitNow || function () {
    return new Date().getTime();
  }; // generate timestamp or delta
  // see http://nodejs.org/api/process.html#process_process_hrtime


  function hrtime(previousTimestamp) {
    var clocktime = performanceNow.call(performance) * 1e-3;
    var seconds = Math.floor(clocktime);
    var nanoseconds = Math.floor(clocktime % 1 * 1e9);

    if (previousTimestamp) {
      seconds = seconds - previousTimestamp[0];
      nanoseconds = nanoseconds - previousTimestamp[1];

      if (nanoseconds < 0) {
        seconds--;
        nanoseconds += 1e9;
      }
    }

    return [seconds, nanoseconds];
  }
  var startTime = new Date();
  function uptime() {
    var currentTime = new Date();
    var dif = currentTime - startTime;
    return dif / 1000;
  }
  var process = {
    nextTick: nextTick,
    title: title,
    browser: browser,
    env: env,
    argv: argv,
    version: version,
    versions: versions,
    on: on,
    addListener: addListener,
    once: once,
    off: off,
    removeListener: removeListener,
    removeAllListeners: removeAllListeners,
    emit: emit,
    binding: binding,
    cwd: cwd,
    chdir: chdir,
    umask: umask,
    hrtime: hrtime,
    platform: platform,
    release: release,
    config: config,
    uptime: uptime
  };

  const debug = typeof process === 'object' && process.env && process.env.NODE_DEBUG && /\bsemver\b/i.test(process.env.NODE_DEBUG) ? (...args) => console.error('SEMVER', ...args) : () => {};
  var debug_1 = debug;

  // Note: this is the semver.org version of the spec that it implements
  // Not necessarily the package version of this code.
  const SEMVER_SPEC_VERSION = '2.0.0';
  const MAX_LENGTH = 256;
  const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER ||
  /* istanbul ignore next */
  9007199254740991; // Max safe segment length for coercion.

  const MAX_SAFE_COMPONENT_LENGTH = 16;
  var constants = {
    SEMVER_SPEC_VERSION,
    MAX_LENGTH,
    MAX_SAFE_INTEGER,
    MAX_SAFE_COMPONENT_LENGTH
  };

  function createCommonjsModule(fn, basedir, module) {
  	return module = {
  	  path: basedir,
  	  exports: {},
  	  require: function (path, base) {
        return commonjsRequire(path, (base === undefined || base === null) ? module.path : base);
      }
  	}, fn(module, module.exports), module.exports;
  }

  function getCjsExportFromNamespace (n) {
  	return n && n['default'] || n;
  }

  function commonjsRequire () {
  	throw new Error('Dynamic requires are not currently supported by @rollup/plugin-commonjs');
  }

  var re_1 = createCommonjsModule(function (module, exports) {
    const {
      MAX_SAFE_COMPONENT_LENGTH
    } = constants;
    exports = module.exports = {}; // The actual regexps go on exports.re

    const re = exports.re = [];
    const src = exports.src = [];
    const t = exports.t = {};
    let R = 0;

    const createToken = (name, value, isGlobal) => {
      const index = R++;
      debug_1(index, value);
      t[name] = index;
      src[index] = value;
      re[index] = new RegExp(value, isGlobal ? 'g' : undefined);
    }; // The following Regular Expressions can be used for tokenizing,
    // validating, and parsing SemVer version strings.
    // ## Numeric Identifier
    // A single `0`, or a non-zero digit followed by zero or more digits.


    createToken('NUMERICIDENTIFIER', '0|[1-9]\\d*');
    createToken('NUMERICIDENTIFIERLOOSE', '[0-9]+'); // ## Non-numeric Identifier
    // Zero or more digits, followed by a letter or hyphen, and then zero or
    // more letters, digits, or hyphens.

    createToken('NONNUMERICIDENTIFIER', '\\d*[a-zA-Z-][a-zA-Z0-9-]*'); // ## Main Version
    // Three dot-separated numeric identifiers.

    createToken('MAINVERSION', "(".concat(src[t.NUMERICIDENTIFIER], ")\\.") + "(".concat(src[t.NUMERICIDENTIFIER], ")\\.") + "(".concat(src[t.NUMERICIDENTIFIER], ")"));
    createToken('MAINVERSIONLOOSE', "(".concat(src[t.NUMERICIDENTIFIERLOOSE], ")\\.") + "(".concat(src[t.NUMERICIDENTIFIERLOOSE], ")\\.") + "(".concat(src[t.NUMERICIDENTIFIERLOOSE], ")")); // ## Pre-release Version Identifier
    // A numeric identifier, or a non-numeric identifier.

    createToken('PRERELEASEIDENTIFIER', "(?:".concat(src[t.NUMERICIDENTIFIER], "|").concat(src[t.NONNUMERICIDENTIFIER], ")"));
    createToken('PRERELEASEIDENTIFIERLOOSE', "(?:".concat(src[t.NUMERICIDENTIFIERLOOSE], "|").concat(src[t.NONNUMERICIDENTIFIER], ")")); // ## Pre-release Version
    // Hyphen, followed by one or more dot-separated pre-release version
    // identifiers.

    createToken('PRERELEASE', "(?:-(".concat(src[t.PRERELEASEIDENTIFIER], "(?:\\.").concat(src[t.PRERELEASEIDENTIFIER], ")*))"));
    createToken('PRERELEASELOOSE', "(?:-?(".concat(src[t.PRERELEASEIDENTIFIERLOOSE], "(?:\\.").concat(src[t.PRERELEASEIDENTIFIERLOOSE], ")*))")); // ## Build Metadata Identifier
    // Any combination of digits, letters, or hyphens.

    createToken('BUILDIDENTIFIER', '[0-9A-Za-z-]+'); // ## Build Metadata
    // Plus sign, followed by one or more period-separated build metadata
    // identifiers.

    createToken('BUILD', "(?:\\+(".concat(src[t.BUILDIDENTIFIER], "(?:\\.").concat(src[t.BUILDIDENTIFIER], ")*))")); // ## Full Version String
    // A main version, followed optionally by a pre-release version and
    // build metadata.
    // Note that the only major, minor, patch, and pre-release sections of
    // the version string are capturing groups.  The build metadata is not a
    // capturing group, because it should not ever be used in version
    // comparison.

    createToken('FULLPLAIN', "v?".concat(src[t.MAINVERSION]).concat(src[t.PRERELEASE], "?").concat(src[t.BUILD], "?"));
    createToken('FULL', "^".concat(src[t.FULLPLAIN], "$")); // like full, but allows v1.2.3 and =1.2.3, which people do sometimes.
    // also, 1.0.0alpha1 (prerelease without the hyphen) which is pretty
    // common in the npm registry.

    createToken('LOOSEPLAIN', "[v=\\s]*".concat(src[t.MAINVERSIONLOOSE]).concat(src[t.PRERELEASELOOSE], "?").concat(src[t.BUILD], "?"));
    createToken('LOOSE', "^".concat(src[t.LOOSEPLAIN], "$"));
    createToken('GTLT', '((?:<|>)?=?)'); // Something like "2.*" or "1.2.x".
    // Note that "x.x" is a valid xRange identifer, meaning "any version"
    // Only the first item is strictly required.

    createToken('XRANGEIDENTIFIERLOOSE', "".concat(src[t.NUMERICIDENTIFIERLOOSE], "|x|X|\\*"));
    createToken('XRANGEIDENTIFIER', "".concat(src[t.NUMERICIDENTIFIER], "|x|X|\\*"));
    createToken('XRANGEPLAIN', "[v=\\s]*(".concat(src[t.XRANGEIDENTIFIER], ")") + "(?:\\.(".concat(src[t.XRANGEIDENTIFIER], ")") + "(?:\\.(".concat(src[t.XRANGEIDENTIFIER], ")") + "(?:".concat(src[t.PRERELEASE], ")?").concat(src[t.BUILD], "?") + ")?)?");
    createToken('XRANGEPLAINLOOSE', "[v=\\s]*(".concat(src[t.XRANGEIDENTIFIERLOOSE], ")") + "(?:\\.(".concat(src[t.XRANGEIDENTIFIERLOOSE], ")") + "(?:\\.(".concat(src[t.XRANGEIDENTIFIERLOOSE], ")") + "(?:".concat(src[t.PRERELEASELOOSE], ")?").concat(src[t.BUILD], "?") + ")?)?");
    createToken('XRANGE', "^".concat(src[t.GTLT], "\\s*").concat(src[t.XRANGEPLAIN], "$"));
    createToken('XRANGELOOSE', "^".concat(src[t.GTLT], "\\s*").concat(src[t.XRANGEPLAINLOOSE], "$")); // Coercion.
    // Extract anything that could conceivably be a part of a valid semver

    createToken('COERCE', "".concat('(^|[^\\d])' + '(\\d{1,').concat(MAX_SAFE_COMPONENT_LENGTH, "})") + "(?:\\.(\\d{1,".concat(MAX_SAFE_COMPONENT_LENGTH, "}))?") + "(?:\\.(\\d{1,".concat(MAX_SAFE_COMPONENT_LENGTH, "}))?") + "(?:$|[^\\d])");
    createToken('COERCERTL', src[t.COERCE], true); // Tilde ranges.
    // Meaning is "reasonably at or greater than"

    createToken('LONETILDE', '(?:~>?)');
    createToken('TILDETRIM', "(\\s*)".concat(src[t.LONETILDE], "\\s+"), true);
    exports.tildeTrimReplace = '$1~';
    createToken('TILDE', "^".concat(src[t.LONETILDE]).concat(src[t.XRANGEPLAIN], "$"));
    createToken('TILDELOOSE', "^".concat(src[t.LONETILDE]).concat(src[t.XRANGEPLAINLOOSE], "$")); // Caret ranges.
    // Meaning is "at least and backwards compatible with"

    createToken('LONECARET', '(?:\\^)');
    createToken('CARETTRIM', "(\\s*)".concat(src[t.LONECARET], "\\s+"), true);
    exports.caretTrimReplace = '$1^';
    createToken('CARET', "^".concat(src[t.LONECARET]).concat(src[t.XRANGEPLAIN], "$"));
    createToken('CARETLOOSE', "^".concat(src[t.LONECARET]).concat(src[t.XRANGEPLAINLOOSE], "$")); // A simple gt/lt/eq thing, or just "" to indicate "any version"

    createToken('COMPARATORLOOSE', "^".concat(src[t.GTLT], "\\s*(").concat(src[t.LOOSEPLAIN], ")$|^$"));
    createToken('COMPARATOR', "^".concat(src[t.GTLT], "\\s*(").concat(src[t.FULLPLAIN], ")$|^$")); // An expression to strip any whitespace between the gtlt and the thing
    // it modifies, so that `> 1.2.3` ==> `>1.2.3`

    createToken('COMPARATORTRIM', "(\\s*)".concat(src[t.GTLT], "\\s*(").concat(src[t.LOOSEPLAIN], "|").concat(src[t.XRANGEPLAIN], ")"), true);
    exports.comparatorTrimReplace = '$1$2$3'; // Something like `1.2.3 - 1.2.4`
    // Note that these all use the loose form, because they'll be
    // checked against either the strict or loose comparator form
    // later.

    createToken('HYPHENRANGE', "^\\s*(".concat(src[t.XRANGEPLAIN], ")") + "\\s+-\\s+" + "(".concat(src[t.XRANGEPLAIN], ")") + "\\s*$");
    createToken('HYPHENRANGELOOSE', "^\\s*(".concat(src[t.XRANGEPLAINLOOSE], ")") + "\\s+-\\s+" + "(".concat(src[t.XRANGEPLAINLOOSE], ")") + "\\s*$"); // Star ranges basically just allow anything at all.

    createToken('STAR', '(<|>)?=?\\s*\\*'); // >=0.0.0 is like a star

    createToken('GTE0', '^\\s*>=\\s*0\.0\.0\\s*$');
    createToken('GTE0PRE', '^\\s*>=\\s*0\.0\.0-0\\s*$');
  });

  const numeric = /^[0-9]+$/;

  const compareIdentifiers = (a, b) => {
    const anum = numeric.test(a);
    const bnum = numeric.test(b);

    if (anum && bnum) {
      a = +a;
      b = +b;
    }

    return a === b ? 0 : anum && !bnum ? -1 : bnum && !anum ? 1 : a < b ? -1 : 1;
  };

  const rcompareIdentifiers = (a, b) => compareIdentifiers(b, a);

  var identifiers = {
    compareIdentifiers,
    rcompareIdentifiers
  };

  const {
    MAX_LENGTH: MAX_LENGTH$1,
    MAX_SAFE_INTEGER: MAX_SAFE_INTEGER$1
  } = constants;
  const {
    re,
    t
  } = re_1;
  const {
    compareIdentifiers: compareIdentifiers$1
  } = identifiers;

  class SemVer {
    constructor(version, options) {
      if (!options || typeof options !== 'object') {
        options = {
          loose: !!options,
          includePrerelease: false
        };
      }

      if (version instanceof SemVer) {
        if (version.loose === !!options.loose && version.includePrerelease === !!options.includePrerelease) {
          return version;
        } else {
          version = version.version;
        }
      } else if (typeof version !== 'string') {
        throw new TypeError("Invalid Version: ".concat(version));
      }

      if (version.length > MAX_LENGTH$1) {
        throw new TypeError("version is longer than ".concat(MAX_LENGTH$1, " characters"));
      }

      debug_1('SemVer', version, options);
      this.options = options;
      this.loose = !!options.loose; // this isn't actually relevant for versions, but keep it so that we
      // don't run into trouble passing this.options around.

      this.includePrerelease = !!options.includePrerelease;
      const m = version.trim().match(options.loose ? re[t.LOOSE] : re[t.FULL]);

      if (!m) {
        throw new TypeError("Invalid Version: ".concat(version));
      }

      this.raw = version; // these are actually numbers

      this.major = +m[1];
      this.minor = +m[2];
      this.patch = +m[3];

      if (this.major > MAX_SAFE_INTEGER$1 || this.major < 0) {
        throw new TypeError('Invalid major version');
      }

      if (this.minor > MAX_SAFE_INTEGER$1 || this.minor < 0) {
        throw new TypeError('Invalid minor version');
      }

      if (this.patch > MAX_SAFE_INTEGER$1 || this.patch < 0) {
        throw new TypeError('Invalid patch version');
      } // numberify any prerelease numeric ids


      if (!m[4]) {
        this.prerelease = [];
      } else {
        this.prerelease = m[4].split('.').map(id => {
          if (/^[0-9]+$/.test(id)) {
            const num = +id;

            if (num >= 0 && num < MAX_SAFE_INTEGER$1) {
              return num;
            }
          }

          return id;
        });
      }

      this.build = m[5] ? m[5].split('.') : [];
      this.format();
    }

    format() {
      this.version = "".concat(this.major, ".").concat(this.minor, ".").concat(this.patch);

      if (this.prerelease.length) {
        this.version += "-".concat(this.prerelease.join('.'));
      }

      return this.version;
    }

    toString() {
      return this.version;
    }

    compare(other) {
      debug_1('SemVer.compare', this.version, this.options, other);

      if (!(other instanceof SemVer)) {
        if (typeof other === 'string' && other === this.version) {
          return 0;
        }

        other = new SemVer(other, this.options);
      }

      if (other.version === this.version) {
        return 0;
      }

      return this.compareMain(other) || this.comparePre(other);
    }

    compareMain(other) {
      if (!(other instanceof SemVer)) {
        other = new SemVer(other, this.options);
      }

      return compareIdentifiers$1(this.major, other.major) || compareIdentifiers$1(this.minor, other.minor) || compareIdentifiers$1(this.patch, other.patch);
    }

    comparePre(other) {
      if (!(other instanceof SemVer)) {
        other = new SemVer(other, this.options);
      } // NOT having a prerelease is > having one


      if (this.prerelease.length && !other.prerelease.length) {
        return -1;
      } else if (!this.prerelease.length && other.prerelease.length) {
        return 1;
      } else if (!this.prerelease.length && !other.prerelease.length) {
        return 0;
      }

      let i = 0;

      do {
        const a = this.prerelease[i];
        const b = other.prerelease[i];
        debug_1('prerelease compare', i, a, b);

        if (a === undefined && b === undefined) {
          return 0;
        } else if (b === undefined) {
          return 1;
        } else if (a === undefined) {
          return -1;
        } else if (a === b) {
          continue;
        } else {
          return compareIdentifiers$1(a, b);
        }
      } while (++i);
    }

    compareBuild(other) {
      if (!(other instanceof SemVer)) {
        other = new SemVer(other, this.options);
      }

      let i = 0;

      do {
        const a = this.build[i];
        const b = other.build[i];
        debug_1('prerelease compare', i, a, b);

        if (a === undefined && b === undefined) {
          return 0;
        } else if (b === undefined) {
          return 1;
        } else if (a === undefined) {
          return -1;
        } else if (a === b) {
          continue;
        } else {
          return compareIdentifiers$1(a, b);
        }
      } while (++i);
    } // preminor will bump the version up to the next minor release, and immediately
    // down to pre-release. premajor and prepatch work the same way.


    inc(release, identifier) {
      switch (release) {
        case 'premajor':
          this.prerelease.length = 0;
          this.patch = 0;
          this.minor = 0;
          this.major++;
          this.inc('pre', identifier);
          break;

        case 'preminor':
          this.prerelease.length = 0;
          this.patch = 0;
          this.minor++;
          this.inc('pre', identifier);
          break;

        case 'prepatch':
          // If this is already a prerelease, it will bump to the next version
          // drop any prereleases that might already exist, since they are not
          // relevant at this point.
          this.prerelease.length = 0;
          this.inc('patch', identifier);
          this.inc('pre', identifier);
          break;
        // If the input is a non-prerelease version, this acts the same as
        // prepatch.

        case 'prerelease':
          if (this.prerelease.length === 0) {
            this.inc('patch', identifier);
          }

          this.inc('pre', identifier);
          break;

        case 'major':
          // If this is a pre-major version, bump up to the same major version.
          // Otherwise increment major.
          // 1.0.0-5 bumps to 1.0.0
          // 1.1.0 bumps to 2.0.0
          if (this.minor !== 0 || this.patch !== 0 || this.prerelease.length === 0) {
            this.major++;
          }

          this.minor = 0;
          this.patch = 0;
          this.prerelease = [];
          break;

        case 'minor':
          // If this is a pre-minor version, bump up to the same minor version.
          // Otherwise increment minor.
          // 1.2.0-5 bumps to 1.2.0
          // 1.2.1 bumps to 1.3.0
          if (this.patch !== 0 || this.prerelease.length === 0) {
            this.minor++;
          }

          this.patch = 0;
          this.prerelease = [];
          break;

        case 'patch':
          // If this is not a pre-release version, it will increment the patch.
          // If it is a pre-release it will bump up to the same patch version.
          // 1.2.0-5 patches to 1.2.0
          // 1.2.0 patches to 1.2.1
          if (this.prerelease.length === 0) {
            this.patch++;
          }

          this.prerelease = [];
          break;
        // This probably shouldn't be used publicly.
        // 1.0.0 'pre' would become 1.0.0-0 which is the wrong direction.

        case 'pre':
          if (this.prerelease.length === 0) {
            this.prerelease = [0];
          } else {
            let i = this.prerelease.length;

            while (--i >= 0) {
              if (typeof this.prerelease[i] === 'number') {
                this.prerelease[i]++;
                i = -2;
              }
            }

            if (i === -1) {
              // didn't increment anything
              this.prerelease.push(0);
            }
          }

          if (identifier) {
            // 1.2.0-beta.1 bumps to 1.2.0-beta.2,
            // 1.2.0-beta.fooblz or 1.2.0-beta bumps to 1.2.0-beta.0
            if (this.prerelease[0] === identifier) {
              if (isNaN(this.prerelease[1])) {
                this.prerelease = [identifier, 0];
              }
            } else {
              this.prerelease = [identifier, 0];
            }
          }

          break;

        default:
          throw new Error("invalid increment argument: ".concat(release));
      }

      this.format();
      this.raw = this.version;
      return this;
    }

  }

  var semver = SemVer;

  const compare = (a, b, loose) => new semver(a, loose).compare(new semver(b, loose));

  var compare_1 = compare;

  const lt = (a, b, loose) => compare_1(a, b, loose) < 0;

  var lt_1 = lt;

  const gte = (a, b, loose) => compare_1(a, b, loose) >= 0;

  var gte_1 = gte;

  var arrayify = (object, keyName) => Object.entries(object).map(([key, value]) => Object.assign({
    [keyName]: key
  }, value));

  var name = "prettier";
  var version$1 = "2.1.2";
  var description = "Prettier is an opinionated code formatter";
  var bin = "./bin/prettier.js";
  var repository = "prettier/prettier";
  var homepage = "https://prettier.io";
  var author = "James Long";
  var license = "MIT";
  var main = "./index.js";
  var browser$1 = "./standalone.js";
  var unpkg = "./standalone.js";
  var engines = {
  	node: ">=10.13.0"
  };
  var files = [
  	"index.js",
  	"standalone.js",
  	"src",
  	"bin"
  ];
  var dependencies = {
  	"@angular/compiler": "10.0.12",
  	"@babel/code-frame": "7.10.4",
  	"@babel/parser": "7.11.2",
  	"@glimmer/syntax": "0.59.0",
  	"@iarna/toml": "2.2.5",
  	"@typescript-eslint/typescript-estree": "3.10.0",
  	"angular-estree-parser": "2.2.0",
  	"angular-html-parser": "1.7.1",
  	camelcase: "6.0.0",
  	chalk: "4.1.0",
  	"ci-info": "watson/ci-info#f43f6a1cefff47fb361c88cf4b943fdbcaafe540",
  	"cjk-regex": "2.0.0",
  	cosmiconfig: "7.0.0",
  	dashify: "2.0.0",
  	diff: "4.0.2",
  	editorconfig: "0.15.3",
  	"editorconfig-to-prettier": "0.1.1",
  	"escape-string-regexp": "4.0.0",
  	esutils: "2.0.3",
  	"fast-glob": "3.2.4",
  	"fast-json-stable-stringify": "2.1.0",
  	"find-parent-dir": "0.3.0",
  	"flow-parser": "0.132.0",
  	"get-stream": "6.0.0",
  	globby: "11.0.1",
  	graphql: "15.3.0",
  	"html-element-attributes": "2.2.1",
  	"html-styles": "1.0.0",
  	"html-tag-names": "1.1.5",
  	"html-void-elements": "1.0.5",
  	ignore: "4.0.6",
  	"jest-docblock": "26.0.0",
  	json5: "2.1.3",
  	leven: "3.1.0",
  	"lines-and-columns": "1.1.6",
  	"linguist-languages": "7.10.0",
  	lodash: "4.17.20",
  	mem: "6.1.0",
  	minimatch: "3.0.4",
  	minimist: "1.2.5",
  	"n-readlines": "1.0.0",
  	outdent: "0.7.1",
  	"parse-srcset": "ikatyang/parse-srcset#54eb9c1cb21db5c62b4d0e275d7249516df6f0ee",
  	"please-upgrade-node": "3.2.0",
  	"postcss-less": "3.1.4",
  	"postcss-media-query-parser": "0.2.3",
  	"postcss-scss": "2.1.1",
  	"postcss-selector-parser": "2.2.3",
  	"postcss-values-parser": "2.0.1",
  	"regexp-util": "1.2.2",
  	"remark-footnotes": "2.0.0",
  	"remark-math": "1.0.6",
  	"remark-parse": "8.0.3",
  	resolve: "1.17.0",
  	semver: "7.3.2",
  	"string-width": "4.2.0",
  	typescript: "4.0.2",
  	"unicode-regex": "3.0.0",
  	unified: "9.2.0",
  	vnopts: "1.0.2",
  	"yaml-unist-parser": "1.3.1"
  };
  var devDependencies = {
  	"@babel/core": "7.11.4",
  	"@babel/preset-env": "7.11.0",
  	"@babel/types": "7.11.0",
  	"@glimmer/reference": "0.59.0",
  	"@rollup/plugin-alias": "3.1.1",
  	"@rollup/plugin-babel": "5.2.0",
  	"@rollup/plugin-commonjs": "14.0.0",
  	"@rollup/plugin-json": "4.1.0",
  	"@rollup/plugin-node-resolve": "9.0.0",
  	"@rollup/plugin-replace": "2.3.3",
  	"@types/estree": "0.0.45",
  	"@types/node": "14.6.0",
  	"@typescript-eslint/types": "3.10.0",
  	"babel-loader": "8.1.0",
  	benchmark: "2.1.4",
  	"builtin-modules": "3.1.0",
  	"cross-env": "7.0.2",
  	cspell: "4.1.0",
  	eslint: "7.7.0",
  	"eslint-config-prettier": "6.11.0",
  	"eslint-formatter-friendly": "7.0.0",
  	"eslint-plugin-import": "2.22.0",
  	"eslint-plugin-jest": "23.20.0",
  	"eslint-plugin-prettier-internal-rules": "file:scripts/tools/eslint-plugin-prettier-internal-rules",
  	"eslint-plugin-react": "7.20.6",
  	"eslint-plugin-unicorn": "21.0.0",
  	execa: "4.0.3",
  	jest: "26.4.2",
  	"jest-snapshot-serializer-ansi": "1.0.0",
  	"jest-snapshot-serializer-raw": "1.1.0",
  	"jest-watch-typeahead": "0.6.0",
  	"npm-run-all": "4.1.5",
  	prettier: "2.1.1",
  	rimraf: "3.0.2",
  	rollup: "2.26.5",
  	"rollup-plugin-node-globals": "1.4.0",
  	"rollup-plugin-terser": "7.0.0",
  	shelljs: "0.8.4",
  	"snapshot-diff": "0.8.1",
  	"strip-ansi": "6.0.0",
  	"synchronous-promise": "2.0.13",
  	tempy: "0.6.0",
  	"terser-webpack-plugin": "4.1.0",
  	webpack: "4.44.1"
  };
  var scripts = {
  	prepublishOnly: "echo \"Error: must publish from dist/\" && exit 1",
  	"prepare-release": "yarn && yarn build && yarn test:dist",
  	test: "jest",
  	"test:dev-package": "cross-env INSTALL_PACKAGE=1 jest",
  	"test:dist": "cross-env NODE_ENV=production jest",
  	"test:dist-standalone": "cross-env NODE_ENV=production TEST_STANDALONE=1 jest",
  	"test:integration": "jest tests_integration",
  	"perf:repeat": "yarn && yarn build && cross-env NODE_ENV=production node ./dist/bin-prettier.js --debug-repeat ${PERF_REPEAT:-1000} --loglevel debug ${PERF_FILE:-./index.js} > /dev/null",
  	"perf:repeat-inspect": "yarn && yarn build && cross-env NODE_ENV=production node --inspect-brk ./dist/bin-prettier.js --debug-repeat ${PERF_REPEAT:-1000} --loglevel debug ${PERF_FILE:-./index.js} > /dev/null",
  	"perf:benchmark": "yarn && yarn build && cross-env NODE_ENV=production node ./dist/bin-prettier.js --debug-benchmark --loglevel debug ${PERF_FILE:-./index.js} > /dev/null",
  	lint: "run-p lint:*",
  	"lint:typecheck": "tsc",
  	"lint:eslint": "cross-env EFF_NO_LINK_RULES=true eslint . --format friendly",
  	"lint:changelog": "node ./scripts/lint-changelog.js",
  	"lint:prettier": "prettier . \"!test*\" --check",
  	"lint:dist": "eslint --no-eslintrc --no-ignore --env=es6,browser --parser-options=ecmaVersion:2016 \"dist/!(bin-prettier|index|third-party).js\"",
  	"lint:spellcheck": "cspell \"**/*\" \".github/**/*\"",
  	"lint:deps": "node ./scripts/check-deps.js",
  	fix: "run-s fix:eslint fix:prettier",
  	"fix:eslint": "yarn lint:eslint --fix",
  	"fix:prettier": "yarn lint:prettier --write",
  	build: "node ./scripts/build/build.js",
  	"build-docs": "node ./scripts/build-docs.js"
  };
  var _package = {
  	name: name,
  	version: version$1,
  	description: description,
  	bin: bin,
  	repository: repository,
  	homepage: homepage,
  	author: author,
  	license: license,
  	main: main,
  	browser: browser$1,
  	unpkg: unpkg,
  	engines: engines,
  	files: files,
  	dependencies: dependencies,
  	devDependencies: devDependencies,
  	scripts: scripts
  };

  var _package$1 = /*#__PURE__*/Object.freeze({
    __proto__: null,
    name: name,
    version: version$1,
    description: description,
    bin: bin,
    repository: repository,
    homepage: homepage,
    author: author,
    license: license,
    main: main,
    browser: browser$1,
    unpkg: unpkg,
    engines: engines,
    files: files,
    dependencies: dependencies,
    devDependencies: devDependencies,
    scripts: scripts,
    'default': _package
  });

  var lib = createCommonjsModule(function (module, exports) {

    Object.defineProperty(exports, "__esModule", {
      value: true
    }); // In the absence of a WeakSet or WeakMap implementation, don't break, but don't cache either.

    function noop() {
      var args = [];

      for (var _i = 0; _i < arguments.length; _i++) {
        args[_i] = arguments[_i];
      }
    }

    function createWeakMap() {
      if (typeof WeakMap !== 'undefined') {
        return new WeakMap();
      } else {
        return fakeSetOrMap();
      }
    }
    /**
     * Creates and returns a no-op implementation of a WeakMap / WeakSet that never stores anything.
     */


    function fakeSetOrMap() {
      return {
        add: noop,
        delete: noop,
        get: noop,
        set: noop,
        has: function has(k) {
          return false;
        }
      };
    } // Safe hasOwnProperty


    var hop = Object.prototype.hasOwnProperty;

    var has = function has(obj, prop) {
      return hop.call(obj, prop);
    }; // Copy all own enumerable properties from source to target


    function extend(target, source) {
      for (var prop in source) {
        if (has(source, prop)) {
          target[prop] = source[prop];
        }
      }

      return target;
    }

    var reLeadingNewline = /^[ \t]*(?:\r\n|\r|\n)/;
    var reTrailingNewline = /(?:\r\n|\r|\n)[ \t]*$/;
    var reStartsWithNewlineOrIsEmpty = /^(?:[\r\n]|$)/;
    var reDetectIndentation = /(?:\r\n|\r|\n)([ \t]*)(?:[^ \t\r\n]|$)/;
    var reOnlyWhitespaceWithAtLeastOneNewline = /^[ \t]*[\r\n][ \t\r\n]*$/;

    function _outdentArray(strings, firstInterpolatedValueSetsIndentationLevel, options) {
      // If first interpolated value is a reference to outdent,
      // determine indentation level from the indentation of the interpolated value.
      var indentationLevel = 0;
      var match = strings[0].match(reDetectIndentation);

      if (match) {
        indentationLevel = match[1].length;
      }

      var reSource = "(\\r\\n|\\r|\\n).{0," + indentationLevel + "}";
      var reMatchIndent = new RegExp(reSource, 'g');

      if (firstInterpolatedValueSetsIndentationLevel) {
        strings = strings.slice(1);
      }

      var newline = options.newline,
          trimLeadingNewline = options.trimLeadingNewline,
          trimTrailingNewline = options.trimTrailingNewline;
      var normalizeNewlines = typeof newline === 'string';
      var l = strings.length;
      var outdentedStrings = strings.map(function (v, i) {
        // Remove leading indentation from all lines
        v = v.replace(reMatchIndent, '$1'); // Trim a leading newline from the first string

        if (i === 0 && trimLeadingNewline) {
          v = v.replace(reLeadingNewline, '');
        } // Trim a trailing newline from the last string


        if (i === l - 1 && trimTrailingNewline) {
          v = v.replace(reTrailingNewline, '');
        } // Normalize newlines


        if (normalizeNewlines) {
          v = v.replace(/\r\n|\n|\r/g, function (_) {
            return newline;
          });
        }

        return v;
      });
      return outdentedStrings;
    }

    function concatStringsAndValues(strings, values) {
      var ret = '';

      for (var i = 0, l = strings.length; i < l; i++) {
        ret += strings[i];

        if (i < l - 1) {
          ret += values[i];
        }
      }

      return ret;
    }

    function isTemplateStringsArray(v) {
      return has(v, 'raw') && has(v, 'length');
    }
    /**
     * It is assumed that opts will not change.  If this is a problem, clone your options object and pass the clone to
     * makeInstance
     * @param options
     * @return {outdent}
     */


    function createInstance(options) {
      /** Cache of pre-processed template literal arrays */
      var arrayAutoIndentCache = createWeakMap();
      /**
       * Cache of pre-processed template literal arrays, where first interpolated value is a reference to outdent,
       * before interpolated values are injected.
       */

      var arrayFirstInterpSetsIndentCache = createWeakMap();

      function outdent(stringsOrOptions) {
        var values = [];

        for (var _i = 1; _i < arguments.length; _i++) {
          values[_i - 1] = arguments[_i];
        }
        /* tslint:enable:no-shadowed-variable */


        if (isTemplateStringsArray(stringsOrOptions)) {
          var strings = stringsOrOptions; // Is first interpolated value a reference to outdent, alone on its own line, without any preceding non-whitespace?

          var firstInterpolatedValueSetsIndentationLevel = (values[0] === outdent || values[0] === defaultOutdent) && reOnlyWhitespaceWithAtLeastOneNewline.test(strings[0]) && reStartsWithNewlineOrIsEmpty.test(strings[1]); // Perform outdentation

          var cache = firstInterpolatedValueSetsIndentationLevel ? arrayFirstInterpSetsIndentCache : arrayAutoIndentCache;
          var renderedArray = cache.get(strings);

          if (!renderedArray) {
            renderedArray = _outdentArray(strings, firstInterpolatedValueSetsIndentationLevel, options);
            cache.set(strings, renderedArray);
          }
          /** If no interpolated values, skip concatenation step */


          if (values.length === 0) {
            return renderedArray[0];
          }
          /** Concatenate string literals with interpolated values */


          var rendered = concatStringsAndValues(renderedArray, firstInterpolatedValueSetsIndentationLevel ? values.slice(1) : values);
          return rendered;
        } else {
          // Create and return a new instance of outdent with the given options
          return createInstance(extend(extend({}, options), stringsOrOptions || {}));
        }
      }

      var fullOutdent = extend(outdent, {
        string: function string(str) {
          return _outdentArray([str], false, options)[0];
        }
      });
      return fullOutdent;
    }

    var defaultOutdent = createInstance({
      trimLeadingNewline: true,
      trimTrailingNewline: true
    });
    exports.outdent = defaultOutdent; // Named exports.  Simple and preferred.
    // import outdent from 'outdent';

    exports.default = defaultOutdent;

    {
      // In webpack harmony-modules environments, module.exports is read-only,
      // so we fail gracefully.
      try {
        module.exports = defaultOutdent;
        Object.defineProperty(defaultOutdent, '__esModule', {
          value: true
        });
        defaultOutdent.default = defaultOutdent;
        defaultOutdent.outdent = defaultOutdent;
      } catch (e) {}
    }
  });

  function _templateObject6() {
    const data = _taggedTemplateLiteral(["\n      Require either '@prettier' or '@format' to be present in the file's first docblock comment\n      in order for it to be formatted.\n    "]);

    _templateObject6 = function _templateObject6() {
      return data;
    };

    return data;
  }

  function _templateObject5() {
    const data = _taggedTemplateLiteral(["\n      Format code starting at a given character offset.\n      The range will extend backwards to the start of the first line containing the selected statement.\n      This option cannot be used with --cursor-offset.\n    "]);

    _templateObject5 = function _templateObject5() {
      return data;
    };

    return data;
  }

  function _templateObject4() {
    const data = _taggedTemplateLiteral(["\n      Format code ending at a given character offset (exclusive).\n      The range will extend forwards to the end of the selected statement.\n      This option cannot be used with --cursor-offset.\n    "]);

    _templateObject4 = function _templateObject4() {
      return data;
    };

    return data;
  }

  function _templateObject3() {
    const data = _taggedTemplateLiteral(["\n      Custom directory that contains prettier plugins in node_modules subdirectory.\n      Overrides default behavior when plugins are searched relatively to the location of Prettier.\n      Multiple values are accepted.\n    "]);

    _templateObject3 = function _templateObject3() {
      return data;
    };

    return data;
  }

  function _templateObject2() {
    const data = _taggedTemplateLiteral(["\n          Maintain existing\n          (mixed values within one file are normalised by looking at what's used after the first line)\n        "]);

    _templateObject2 = function _templateObject2() {
      return data;
    };

    return data;
  }

  function _templateObject() {
    const data = _taggedTemplateLiteral(["\n      Print (to stderr) where a cursor at the given position would move to after formatting.\n      This option cannot be used with --range-start and --range-end.\n    "]);

    _templateObject = function _templateObject() {
      return data;
    };

    return data;
  }

  const {
    outdent
  } = lib;
  const CATEGORY_CONFIG = "Config";
  const CATEGORY_EDITOR = "Editor";
  const CATEGORY_FORMAT = "Format";
  const CATEGORY_OTHER = "Other";
  const CATEGORY_OUTPUT = "Output";
  const CATEGORY_GLOBAL = "Global";
  const CATEGORY_SPECIAL = "Special";
  /**
   * @typedef {Object} OptionInfo
   * @property {string} [since] - available since version
   * @property {string} category
   * @property {'int' | 'boolean' | 'choice' | 'path'} type
   * @property {boolean} [array] - indicate it's an array of the specified type
   * @property {OptionValueInfo} [default]
   * @property {OptionRangeInfo} [range] - for type int
   * @property {string} description
   * @property {string} [deprecated] - deprecated since version
   * @property {OptionRedirectInfo} [redirect] - redirect deprecated option
   * @property {(value: any) => boolean} [exception]
   * @property {OptionChoiceInfo[]} [choices] - for type choice
   * @property {string} [cliName]
   * @property {string} [cliCategory]
   * @property {string} [cliDescription]
   *
   * @typedef {number | boolean | string} OptionValue
   * @typedef {OptionValue | [{ value: OptionValue[] }] | Array<{ since: string, value: OptionValue}>} OptionValueInfo
   *
   * @typedef {Object} OptionRedirectInfo
   * @property {string} option
   * @property {OptionValue} value
   *
   * @typedef {Object} OptionRangeInfo
   * @property {number} start - recommended range start
   * @property {number} end - recommended range end
   * @property {number} step - recommended range step
   *
   * @typedef {Object} OptionChoiceInfo
   * @property {boolean | string} value - boolean for the option that is originally boolean type
   * @property {string} description
   * @property {string} [since] - undefined if available since the first version of the option
   * @property {string} [deprecated] - deprecated since version
   * @property {OptionValueInfo} [redirect] - redirect deprecated value
   */

  /** @type {{ [name: string]: OptionInfo }} */

  const options = {
    cursorOffset: {
      since: "1.4.0",
      category: CATEGORY_SPECIAL,
      type: "int",
      default: -1,
      range: {
        start: -1,
        end: Infinity,
        step: 1
      },
      description: outdent(_templateObject()),
      cliCategory: CATEGORY_EDITOR
    },
    endOfLine: {
      since: "1.15.0",
      category: CATEGORY_GLOBAL,
      type: "choice",
      default: [{
        since: "1.15.0",
        value: "auto"
      }, {
        since: "2.0.0",
        value: "lf"
      }],
      description: "Which end of line characters to apply.",
      choices: [{
        value: "lf",
        description: "Line Feed only (\\n), common on Linux and macOS as well as inside git repos"
      }, {
        value: "crlf",
        description: "Carriage Return + Line Feed characters (\\r\\n), common on Windows"
      }, {
        value: "cr",
        description: "Carriage Return character only (\\r), used very rarely"
      }, {
        value: "auto",
        description: outdent(_templateObject2())
      }]
    },
    filepath: {
      since: "1.4.0",
      category: CATEGORY_SPECIAL,
      type: "path",
      description: "Specify the input filepath. This will be used to do parser inference.",
      cliName: "stdin-filepath",
      cliCategory: CATEGORY_OTHER,
      cliDescription: "Path to the file to pretend that stdin comes from."
    },
    insertPragma: {
      since: "1.8.0",
      category: CATEGORY_SPECIAL,
      type: "boolean",
      default: false,
      description: "Insert @format pragma into file's first docblock comment.",
      cliCategory: CATEGORY_OTHER
    },
    parser: {
      since: "0.0.10",
      category: CATEGORY_GLOBAL,
      type: "choice",
      default: [{
        since: "0.0.10",
        value: "babylon"
      }, {
        since: "1.13.0",
        value: undefined
      }],
      description: "Which parser to use.",
      exception: value => typeof value === "string" || typeof value === "function",
      choices: [{
        value: "flow",
        description: "Flow"
      }, {
        value: "babel",
        since: "1.16.0",
        description: "JavaScript"
      }, {
        value: "babel-flow",
        since: "1.16.0",
        description: "Flow"
      }, {
        value: "babel-ts",
        since: "2.0.0",
        description: "TypeScript"
      }, {
        value: "typescript",
        since: "1.4.0",
        description: "TypeScript"
      }, {
        value: "css",
        since: "1.7.1",
        description: "CSS"
      }, {
        value: "less",
        since: "1.7.1",
        description: "Less"
      }, {
        value: "scss",
        since: "1.7.1",
        description: "SCSS"
      }, {
        value: "json",
        since: "1.5.0",
        description: "JSON"
      }, {
        value: "json5",
        since: "1.13.0",
        description: "JSON5"
      }, {
        value: "json-stringify",
        since: "1.13.0",
        description: "JSON.stringify"
      }, {
        value: "graphql",
        since: "1.5.0",
        description: "GraphQL"
      }, {
        value: "markdown",
        since: "1.8.0",
        description: "Markdown"
      }, {
        value: "mdx",
        since: "1.15.0",
        description: "MDX"
      }, {
        value: "vue",
        since: "1.10.0",
        description: "Vue"
      }, {
        value: "yaml",
        since: "1.14.0",
        description: "YAML"
      }, {
        value: "glimmer",
        since: null,
        description: "Handlebars"
      }, {
        value: "html",
        since: "1.15.0",
        description: "HTML"
      }, {
        value: "angular",
        since: "1.15.0",
        description: "Angular"
      }, {
        value: "lwc",
        since: "1.17.0",
        description: "Lightning Web Components"
      }]
    },
    plugins: {
      since: "1.10.0",
      type: "path",
      array: true,
      default: [{
        value: []
      }],
      category: CATEGORY_GLOBAL,
      description: "Add a plugin. Multiple plugins can be passed as separate `--plugin`s.",
      exception: value => typeof value === "string" || typeof value === "object",
      cliName: "plugin",
      cliCategory: CATEGORY_CONFIG
    },
    pluginSearchDirs: {
      since: "1.13.0",
      type: "path",
      array: true,
      default: [{
        value: []
      }],
      category: CATEGORY_GLOBAL,
      description: outdent(_templateObject3()),
      exception: value => typeof value === "string" || typeof value === "object",
      cliName: "plugin-search-dir",
      cliCategory: CATEGORY_CONFIG
    },
    printWidth: {
      since: "0.0.0",
      category: CATEGORY_GLOBAL,
      type: "int",
      default: 80,
      description: "The line length where Prettier will try wrap.",
      range: {
        start: 0,
        end: Infinity,
        step: 1
      }
    },
    rangeEnd: {
      since: "1.4.0",
      category: CATEGORY_SPECIAL,
      type: "int",
      default: Infinity,
      range: {
        start: 0,
        end: Infinity,
        step: 1
      },
      description: outdent(_templateObject4()),
      cliCategory: CATEGORY_EDITOR
    },
    rangeStart: {
      since: "1.4.0",
      category: CATEGORY_SPECIAL,
      type: "int",
      default: 0,
      range: {
        start: 0,
        end: Infinity,
        step: 1
      },
      description: outdent(_templateObject5()),
      cliCategory: CATEGORY_EDITOR
    },
    requirePragma: {
      since: "1.7.0",
      category: CATEGORY_SPECIAL,
      type: "boolean",
      default: false,
      description: outdent(_templateObject6()),
      cliCategory: CATEGORY_OTHER
    },
    tabWidth: {
      type: "int",
      category: CATEGORY_GLOBAL,
      default: 2,
      description: "Number of spaces per indentation level.",
      range: {
        start: 0,
        end: Infinity,
        step: 1
      }
    },
    useTabs: {
      since: "1.0.0",
      category: CATEGORY_GLOBAL,
      type: "boolean",
      default: false,
      description: "Indent with tabs instead of spaces."
    },
    embeddedLanguageFormatting: {
      since: "2.1.0",
      category: CATEGORY_GLOBAL,
      type: "choice",
      default: [{
        since: "2.1.0",
        value: "auto"
      }],
      description: "Control how Prettier formats quoted code embedded in the file.",
      choices: [{
        value: "auto",
        description: "Format embedded code if Prettier can automatically identify it."
      }, {
        value: "off",
        description: "Never automatically format embedded code."
      }]
    }
  };
  var coreOptions = {
    CATEGORY_CONFIG,
    CATEGORY_EDITOR,
    CATEGORY_FORMAT,
    CATEGORY_OTHER,
    CATEGORY_OUTPUT,
    CATEGORY_GLOBAL,
    CATEGORY_SPECIAL,
    options
  };

  var require$$3 = getCjsExportFromNamespace(_package$1);

  const semver$1 = {
    compare: compare_1,
    lt: lt_1,
    gte: gte_1
  };
  const currentVersion = require$$3.version;
  const coreOptions$1 = coreOptions.options;
  /**
   * Strings in `plugins` and `pluginSearchDirs` are handled by a wrapped version
   * of this function created by `withPlugins`. Don't pass them here directly.
   * @param {object} param0
   * @param {(string | object)[]=} param0.plugins Strings are resolved by `withPlugins`.
   * @param {string[]=} param0.pluginSearchDirs Added by `withPlugins`.
   * @param {boolean=} param0.showUnreleased
   * @param {boolean=} param0.showDeprecated
   * @param {boolean=} param0.showInternal
   */

  function getSupportInfo({
    plugins = [],
    showUnreleased = false,
    showDeprecated = false,
    showInternal = false
  } = {}) {
    // pre-release version is smaller than the normal version in semver,
    // we need to treat it as the normal one so as to test new features.
    const version = currentVersion.split("-", 1)[0];
    const languages = plugins.reduce((all, plugin) => all.concat(plugin.languages || []), []).filter(filterSince);
    const options = arrayify(Object.assign({}, ...plugins.map(({
      options
    }) => options), coreOptions$1), "name").filter(option => filterSince(option) && filterDeprecated(option)).sort((a, b) => a.name === b.name ? 0 : a.name < b.name ? -1 : 1).map(mapInternal).map(option => {
      option = Object.assign({}, option);

      if (Array.isArray(option.default)) {
        option.default = option.default.length === 1 ? option.default[0].value : option.default.filter(filterSince).sort((info1, info2) => semver$1.compare(info2.since, info1.since))[0].value;
      }

      if (Array.isArray(option.choices)) {
        option.choices = option.choices.filter(option => filterSince(option) && filterDeprecated(option));

        if (option.name === "parser") {
          collectParsersFromLanguages(option, languages, plugins);
        }
      }

      const pluginDefaults = plugins.filter(plugin => plugin.defaultOptions && plugin.defaultOptions[option.name] !== undefined).reduce((reduced, plugin) => {
        reduced[plugin.name] = plugin.defaultOptions[option.name];
        return reduced;
      }, {});
      return Object.assign({}, option, {
        pluginDefaults
      });
    });
    return {
      languages,
      options
    };

    function filterSince(object) {
      return showUnreleased || !("since" in object) || object.since && semver$1.gte(version, object.since);
    }

    function filterDeprecated(object) {
      return showDeprecated || !("deprecated" in object) || object.deprecated && semver$1.lt(version, object.deprecated);
    }

    function mapInternal(object) {
      if (showInternal) {
        return object;
      }

      const newObject = _objectWithoutPropertiesLoose(object, ["cliName", "cliCategory", "cliDescription"]);

      return newObject;
    }
  }

  function collectParsersFromLanguages(option, languages, plugins) {
    const existingValues = new Set(option.choices.map(choice => choice.value));

    for (const language of languages) {
      if (language.parsers) {
        for (const value of language.parsers) {
          if (!existingValues.has(value)) {
            existingValues.add(value);
            const plugin = plugins.find(plugin => plugin.parsers && plugin.parsers[value]);
            let description = language.name;

            if (plugin && plugin.name) {
              description += " (plugin: ".concat(plugin.name, ")");
            }

            option.choices.push({
              value,
              description
            });
          }
        }
      }
    }
  }

  var support = {
    getSupportInfo
  };

  const notAsciiRegex = /[^\x20-\x7F]/;

  const getPenultimate = arr => arr[arr.length - 2];
  /**
   * @typedef {{backwards?: boolean}} SkipOptions
   */

  /**
   * @param {string | RegExp} chars
   * @returns {(text: string, index: number | false, opts?: SkipOptions) => number | false}
   */


  function skip(chars) {
    return (text, index, opts) => {
      const backwards = opts && opts.backwards; // Allow `skip` functions to be threaded together without having
      // to check for failures (did someone say monads?).

      /* istanbul ignore next */

      if (index === false) {
        return false;
      }

      const {
        length
      } = text;
      let cursor = index;

      while (cursor >= 0 && cursor < length) {
        const c = text.charAt(cursor);

        if (chars instanceof RegExp) {
          if (!chars.test(c)) {
            return cursor;
          }
        } else if (!chars.includes(c)) {
          return cursor;
        }

        backwards ? cursor-- : cursor++;
      }

      if (cursor === -1 || cursor === length) {
        // If we reached the beginning or end of the file, return the
        // out-of-bounds cursor. It's up to the caller to handle this
        // correctly. We don't want to indicate `false` though if it
        // actually skipped valid characters.
        return cursor;
      }

      return false;
    };
  }
  /**
   * @type {(text: string, index: number | false, opts?: SkipOptions) => number | false}
   */


  const skipWhitespace = skip(/\s/);
  /**
   * @type {(text: string, index: number | false, opts?: SkipOptions) => number | false}
   */

  const skipSpaces = skip(" \t");
  /**
   * @type {(text: string, index: number | false, opts?: SkipOptions) => number | false}
   */

  const skipToLineEnd = skip(",; \t");
  /**
   * @type {(text: string, index: number | false, opts?: SkipOptions) => number | false}
   */

  const skipEverythingButNewLine = skip(/[^\n\r]/);
  /**
   * @param {string} text
   * @param {number | false} index
   * @returns {number | false}
   */

  function skipInlineComment(text, index) {
    /* istanbul ignore next */
    if (index === false) {
      return false;
    }

    if (text.charAt(index) === "/" && text.charAt(index + 1) === "*") {
      for (let i = index + 2; i < text.length; ++i) {
        if (text.charAt(i) === "*" && text.charAt(i + 1) === "/") {
          return i + 2;
        }
      }
    }

    return index;
  }
  /**
   * @param {string} text
   * @param {number | false} index
   * @returns {number | false}
   */


  function skipTrailingComment(text, index) {
    /* istanbul ignore next */
    if (index === false) {
      return false;
    }

    if (text.charAt(index) === "/" && text.charAt(index + 1) === "/") {
      return skipEverythingButNewLine(text, index);
    }

    return index;
  } // This one doesn't use the above helper function because it wants to
  // test \r\n in order and `skip` doesn't support ordering and we only
  // want to skip one newline. It's simple to implement.

  /**
   * @param {string} text
   * @param {number | false} index
   * @param {SkipOptions=} opts
   * @returns {number | false}
   */


  function skipNewline(text, index, opts) {
    const backwards = opts && opts.backwards;

    if (index === false) {
      return false;
    }

    const atIndex = text.charAt(index);

    if (backwards) {
      // We already replace `\r\n` with `\n` before parsing

      /* istanbul ignore next */
      if (text.charAt(index - 1) === "\r" && atIndex === "\n") {
        return index - 2;
      }

      if (atIndex === "\n" || atIndex === "\r" || atIndex === "\u2028" || atIndex === "\u2029") {
        return index - 1;
      }
    } else {
      // We already replace `\r\n` with `\n` before parsing

      /* istanbul ignore next */
      if (atIndex === "\r" && text.charAt(index + 1) === "\n") {
        return index + 2;
      }

      if (atIndex === "\n" || atIndex === "\r" || atIndex === "\u2028" || atIndex === "\u2029") {
        return index + 1;
      }
    }

    return index;
  }
  /**
   * @param {string} text
   * @param {number} index
   * @param {SkipOptions=} opts
   * @returns {boolean}
   */


  function hasNewline(text, index, opts) {
    opts = opts || {};
    const idx = skipSpaces(text, opts.backwards ? index - 1 : index, opts);
    const idx2 = skipNewline(text, idx, opts);
    return idx !== idx2;
  }
  /**
   * @param {string} text
   * @param {number} start
   * @param {number} end
   * @returns {boolean}
   */


  function hasNewlineInRange(text, start, end) {
    for (let i = start; i < end; ++i) {
      if (text.charAt(i) === "\n") {
        return true;
      }
    }

    return false;
  } // Note: this function doesn't ignore leading comments unlike isNextLineEmpty

  /**
   * @template N
   * @param {string} text
   * @param {N} node
   * @param {(node: N) => number} locStart
   */


  function isPreviousLineEmpty(text, node, locStart) {
    /** @type {number | false} */
    let idx = locStart(node) - 1;
    idx = skipSpaces(text, idx, {
      backwards: true
    });
    idx = skipNewline(text, idx, {
      backwards: true
    });
    idx = skipSpaces(text, idx, {
      backwards: true
    });
    const idx2 = skipNewline(text, idx, {
      backwards: true
    });
    return idx !== idx2;
  }
  /**
   * @param {string} text
   * @param {number} index
   * @returns {boolean}
   */


  function isNextLineEmptyAfterIndex(text, index) {
    /** @type {number | false} */
    let oldIdx = null;
    /** @type {number | false} */

    let idx = index;

    while (idx !== oldIdx) {
      // We need to skip all the potential trailing inline comments
      oldIdx = idx;
      idx = skipToLineEnd(text, idx);
      idx = skipInlineComment(text, idx);
      idx = skipSpaces(text, idx);
    }

    idx = skipTrailingComment(text, idx);
    idx = skipNewline(text, idx);
    return idx !== false && hasNewline(text, idx);
  }
  /**
   * @template N
   * @param {string} text
   * @param {N} node
   * @param {(node: N) => number} locEnd
   * @returns {boolean}
   */


  function isNextLineEmpty(text, node, locEnd) {
    return isNextLineEmptyAfterIndex(text, locEnd(node));
  }
  /**
   * @param {string} text
   * @param {number} idx
   * @returns {number | false}
   */


  function getNextNonSpaceNonCommentCharacterIndexWithStartIndex(text, idx) {
    /** @type {number | false} */
    let oldIdx = null;
    /** @type {number | false} */

    let nextIdx = idx;

    while (nextIdx !== oldIdx) {
      oldIdx = nextIdx;
      nextIdx = skipSpaces(text, nextIdx);
      nextIdx = skipInlineComment(text, nextIdx);
      nextIdx = skipTrailingComment(text, nextIdx);
      nextIdx = skipNewline(text, nextIdx);
    }

    return nextIdx;
  }
  /**
   * @template N
   * @param {string} text
   * @param {N} node
   * @param {(node: N) => number} locEnd
   * @returns {number | false}
   */


  function getNextNonSpaceNonCommentCharacterIndex(text, node, locEnd) {
    return getNextNonSpaceNonCommentCharacterIndexWithStartIndex(text, locEnd(node));
  }
  /**
   * @template N
   * @param {string} text
   * @param {N} node
   * @param {(node: N) => number} locEnd
   * @returns {string}
   */


  function getNextNonSpaceNonCommentCharacter(text, node, locEnd) {
    return text.charAt( // @ts-ignore => TBD: can return false, should we define a fallback?
    getNextNonSpaceNonCommentCharacterIndex(text, node, locEnd));
  } // Not using, but it's public utils

  /* istanbul ignore next */

  /**
   * @param {string} text
   * @param {number} index
   * @param {SkipOptions=} opts
   * @returns {boolean}
   */


  function hasSpaces(text, index, opts) {
    opts = opts || {};
    const idx = skipSpaces(text, opts.backwards ? index - 1 : index, opts);
    return idx !== index;
  }
  /**
   * @param {string} value
   * @param {number} tabWidth
   * @param {number=} startIndex
   * @returns {number}
   */


  function getAlignmentSize(value, tabWidth, startIndex) {
    startIndex = startIndex || 0;
    let size = 0;

    for (let i = startIndex; i < value.length; ++i) {
      if (value[i] === "\t") {
        // Tabs behave in a way that they are aligned to the nearest
        // multiple of tabWidth:
        // 0 -> 4, 1 -> 4, 2 -> 4, 3 -> 4
        // 4 -> 8, 5 -> 8, 6 -> 8, 7 -> 8 ...
        size = size + tabWidth - size % tabWidth;
      } else {
        size++;
      }
    }

    return size;
  }
  /**
   * @param {string} value
   * @param {number} tabWidth
   * @returns {number}
   */


  function getIndentSize(value, tabWidth) {
    const lastNewlineIndex = value.lastIndexOf("\n");

    if (lastNewlineIndex === -1) {
      return 0;
    }

    return getAlignmentSize( // All the leading whitespaces
    value.slice(lastNewlineIndex + 1).match(/^[\t ]*/)[0], tabWidth);
  }
  /**
   * @typedef {'"' | "'"} Quote
   */

  /**
   *
   * @param {string} raw
   * @param {Quote} preferredQuote
   * @returns {Quote}
   */


  function getPreferredQuote(raw, preferredQuote) {
    // `rawContent` is the string exactly like it appeared in the input source
    // code, without its enclosing quotes.
    const rawContent = raw.slice(1, -1);
    /** @type {{ quote: '"', regex: RegExp }} */

    const double = {
      quote: '"',
      regex: /"/g
    };
    /** @type {{ quote: "'", regex: RegExp }} */

    const single = {
      quote: "'",
      regex: /'/g
    };
    const preferred = preferredQuote === "'" ? single : double;
    const alternate = preferred === single ? double : single;
    let result = preferred.quote; // If `rawContent` contains at least one of the quote preferred for enclosing
    // the string, we might want to enclose with the alternate quote instead, to
    // minimize the number of escaped quotes.

    if (rawContent.includes(preferred.quote) || rawContent.includes(alternate.quote)) {
      const numPreferredQuotes = (rawContent.match(preferred.regex) || []).length;
      const numAlternateQuotes = (rawContent.match(alternate.regex) || []).length;
      result = numPreferredQuotes > numAlternateQuotes ? alternate.quote : preferred.quote;
    }

    return result;
  }

  function printString(raw, options, isDirectiveLiteral) {
    // `rawContent` is the string exactly like it appeared in the input source
    // code, without its enclosing quotes.
    const rawContent = raw.slice(1, -1); // Check for the alternate quote, to determine if we're allowed to swap
    // the quotes on a DirectiveLiteral.

    const canChangeDirectiveQuotes = !rawContent.includes('"') && !rawContent.includes("'");
    /** @type {Quote} */

    const enclosingQuote = options.parser === "json" ? '"' : options.__isInHtmlAttribute ? "'" : getPreferredQuote(raw, options.singleQuote ? "'" : '"'); // Directives are exact code unit sequences, which means that you can't
    // change the escape sequences they use.
    // See https://github.com/prettier/prettier/issues/1555
    // and https://tc39.github.io/ecma262/#directive-prologue

    if (isDirectiveLiteral) {
      if (canChangeDirectiveQuotes) {
        return enclosingQuote + rawContent + enclosingQuote;
      }

      return raw;
    } // It might sound unnecessary to use `makeString` even if the string already
    // is enclosed with `enclosingQuote`, but it isn't. The string could contain
    // unnecessary escapes (such as in `"\'"`). Always using `makeString` makes
    // sure that we consistently output the minimum amount of escaped quotes.


    return makeString(rawContent, enclosingQuote, !(options.parser === "css" || options.parser === "less" || options.parser === "scss" || options.embeddedInHtml));
  }
  /**
   * @param {string} rawContent
   * @param {Quote} enclosingQuote
   * @param {boolean=} unescapeUnnecessaryEscapes
   * @returns {string}
   */


  function makeString(rawContent, enclosingQuote, unescapeUnnecessaryEscapes) {
    const otherQuote = enclosingQuote === '"' ? "'" : '"'; // Matches _any_ escape and unescaped quotes (both single and double).

    const regex = /\\([\S\s])|(["'])/g; // Escape and unescape single and double quotes as needed to be able to
    // enclose `rawContent` with `enclosingQuote`.

    const newContent = rawContent.replace(regex, (match, escaped, quote) => {
      // If we matched an escape, and the escaped character is a quote of the
      // other type than we intend to enclose the string with, there's no need for
      // it to be escaped, so return it _without_ the backslash.
      if (escaped === otherQuote) {
        return escaped;
      } // If we matched an unescaped quote and it is of the _same_ type as we
      // intend to enclose the string with, it must be escaped, so return it with
      // a backslash.


      if (quote === enclosingQuote) {
        return "\\" + quote;
      }

      if (quote) {
        return quote;
      } // Unescape any unnecessarily escaped character.
      // Adapted from https://github.com/eslint/eslint/blob/de0b4ad7bd820ade41b1f606008bea68683dc11a/lib/rules/no-useless-escape.js#L27


      return unescapeUnnecessaryEscapes && /^[^\n\r"'0-7\\bfnrt-vx\u2028\u2029]$/.test(escaped) ? escaped : "\\" + escaped;
    });
    return enclosingQuote + newContent + enclosingQuote;
  }

  function printNumber(rawNumber) {
    return rawNumber.toLowerCase() // Remove unnecessary plus and zeroes from scientific notation.
    .replace(/^([+-]?[\d.]+e)(?:\+|(-))?0*(\d)/, "$1$2$3") // Remove unnecessary scientific notation (1e0).
    .replace(/^([+-]?[\d.]+)e[+-]?0+$/, "$1") // Make sure numbers always start with a digit.
    .replace(/^([+-])?\./, "$10.") // Remove extraneous trailing decimal zeroes.
    .replace(/(\.\d+?)0+(?=e|$)/, "$1") // Remove trailing dot.
    .replace(/\.(?=e|$)/, "");
  }
  /**
   * @param {string} str
   * @param {string} target
   * @returns {number}
   */


  function getMaxContinuousCount(str, target) {
    const results = str.match(new RegExp("(".concat(escapeStringRegexp(target), ")+"), "g"));

    if (results === null) {
      return 0;
    }

    return results.reduce((maxCount, result) => Math.max(maxCount, result.length / target.length), 0);
  }

  function getMinNotPresentContinuousCount(str, target) {
    const matches = str.match(new RegExp("(".concat(escapeStringRegexp(target), ")+"), "g"));

    if (matches === null) {
      return 0;
    }

    const countPresent = new Map();
    let max = 0;

    for (const match of matches) {
      const count = match.length / target.length;
      countPresent.set(count, true);

      if (count > max) {
        max = count;
      }
    }

    for (let i = 1; i < max; i++) {
      if (!countPresent.get(i)) {
        return i;
      }
    }

    return max + 1;
  }
  /**
   * @param {string} text
   * @returns {number}
   */


  function getStringWidth(text) {
    if (!text) {
      return 0;
    } // shortcut to avoid needless string `RegExp`s, replacements, and allocations within `string-width`


    if (!notAsciiRegex.test(text)) {
      return text.length;
    }

    return stringWidth_1(text);
  }

  function hasIgnoreComment(path) {
    const node = path.getValue();
    return hasNodeIgnoreComment(node);
  }

  function hasNodeIgnoreComment(node) {
    return node && (node.comments && node.comments.length > 0 && node.comments.some(comment => isNodeIgnoreComment(comment) && !comment.unignore) || node.prettierIgnore);
  }

  function isNodeIgnoreComment(comment) {
    return comment.value.trim() === "prettier-ignore";
  }

  function addCommentHelper(node, comment) {
    const comments = node.comments || (node.comments = []);
    comments.push(comment);
    comment.printed = false; // For some reason, TypeScript parses `// x` inside of JSXText as a comment
    // We already "print" it via the raw text, we don't need to re-print it as a
    // comment

    /* istanbul ignore next */

    if (node.type === "JSXText") {
      comment.printed = true;
    }
  }

  function addLeadingComment(node, comment) {
    comment.leading = true;
    comment.trailing = false;
    addCommentHelper(node, comment);
  }

  function addDanglingComment(node, comment, marker) {
    comment.leading = false;
    comment.trailing = false;

    if (marker) {
      comment.marker = marker;
    }

    addCommentHelper(node, comment);
  }

  function addTrailingComment(node, comment) {
    comment.leading = false;
    comment.trailing = true;
    addCommentHelper(node, comment);
  } // Not using

  /* istanbul ignore next */


  function isWithinParentArrayProperty(path, propertyName) {
    const node = path.getValue();
    const parent = path.getParentNode();

    if (parent == null) {
      return false;
    }

    if (!Array.isArray(parent[propertyName])) {
      return false;
    }

    const key = path.getName();
    return parent[propertyName][key] === node;
  }

  function replaceEndOfLineWith(text, replacement) {
    const parts = [];

    for (const part of text.split("\n")) {
      if (parts.length !== 0) {
        parts.push(replacement);
      }

      parts.push(part);
    }

    return parts;
  }

  function getParserName(lang, options) {
    const supportInfo = support.getSupportInfo({
      plugins: options.plugins
    });
    const language = supportInfo.languages.find(language => language.name.toLowerCase() === lang || language.aliases && language.aliases.includes(lang) || language.extensions && language.extensions.some(ext => ext === ".".concat(lang)));

    if (language) {
      return language.parsers[0];
    }

    return null;
  }

  function isFrontMatterNode(node) {
    return node && node.type === "front-matter";
  }

  function getShebang(text) {
    if (!text.startsWith("#!")) {
      return "";
    }

    const index = text.indexOf("\n");

    if (index === -1) {
      return text;
    }

    return text.slice(0, index);
  }

  var util = {
    replaceEndOfLineWith,
    getStringWidth,
    getMaxContinuousCount,
    getMinNotPresentContinuousCount,
    getParserName,
    getPenultimate,
    getLast,
    getNextNonSpaceNonCommentCharacterIndexWithStartIndex,
    getNextNonSpaceNonCommentCharacterIndex,
    getNextNonSpaceNonCommentCharacter,
    skip,
    skipWhitespace,
    skipSpaces,
    skipToLineEnd,
    skipEverythingButNewLine,
    skipInlineComment,
    skipTrailingComment,
    skipNewline,
    isNextLineEmptyAfterIndex,
    isNextLineEmpty,
    isPreviousLineEmpty,
    hasNewline,
    hasNewlineInRange,
    hasSpaces,
    getAlignmentSize,
    getIndentSize,
    getPreferredQuote,
    printString,
    printNumber,
    hasIgnoreComment,
    hasNodeIgnoreComment,
    isNodeIgnoreComment,
    makeString,
    addLeadingComment,
    addDanglingComment,
    addTrailingComment,
    isWithinParentArrayProperty,
    isFrontMatterNode,
    getShebang
  };

  function guessEndOfLine(text) {
    const index = text.indexOf("\r");

    if (index >= 0) {
      return text.charAt(index + 1) === "\n" ? "crlf" : "cr";
    }

    return "lf";
  }

  function convertEndOfLineToChars(value) {
    switch (value) {
      case "cr":
        return "\r";

      case "crlf":
        return "\r\n";

      default:
        return "\n";
    }
  }

  function countEndOfLineChars(text, eol) {
    let regex;
    /* istanbul ignore else */

    if (eol === "\n") {
      regex = /\n/g;
    } else if (eol === "\r") {
      regex = /\r/g;
    } else if (eol === "\r\n") {
      regex = /\r\n/g;
    } else {
      throw new Error("Unexpected \"eol\" ".concat(JSON.stringify(eol), "."));
    }

    const endOfLines = text.match(regex);
    return endOfLines ? endOfLines.length : 0;
  }

  function normalizeEndOfLine(text) {
    return text.replace(/\r\n?/g, "\n");
  }

  var endOfLine = {
    guessEndOfLine,
    convertEndOfLineToChars,
    countEndOfLineChars,
    normalizeEndOfLine
  };

  const {
    getStringWidth: getStringWidth$1
  } = util;
  const {
    convertEndOfLineToChars: convertEndOfLineToChars$1
  } = endOfLine;
  const {
    concat: concat$1,
    fill: fill$1,
    cursor: cursor$1
  } = docBuilders;
  /** @type {Record<symbol, typeof MODE_BREAK | typeof MODE_FLAT>} */

  let groupModeMap;
  const MODE_BREAK = 1;
  const MODE_FLAT = 2;

  function rootIndent() {
    return {
      value: "",
      length: 0,
      queue: []
    };
  }

  function makeIndent(ind, options) {
    return generateInd(ind, {
      type: "indent"
    }, options);
  }

  function makeAlign(indent, n, options) {
    if (n === -Infinity) {
      return indent.root || rootIndent();
    }

    if (n < 0) {
      return generateInd(indent, {
        type: "dedent"
      }, options);
    }

    if (!n) {
      return indent;
    }

    if (n.type === "root") {
      return Object.assign({}, indent, {
        root: indent
      });
    }

    const alignType = typeof n === "string" ? "stringAlign" : "numberAlign";
    return generateInd(indent, {
      type: alignType,
      n
    }, options);
  }

  function generateInd(ind, newPart, options) {
    const queue = newPart.type === "dedent" ? ind.queue.slice(0, -1) : ind.queue.concat(newPart);
    let value = "";
    let length = 0;
    let lastTabs = 0;
    let lastSpaces = 0;

    for (const part of queue) {
      switch (part.type) {
        case "indent":
          flush();

          if (options.useTabs) {
            addTabs(1);
          } else {
            addSpaces(options.tabWidth);
          }

          break;

        case "stringAlign":
          flush();
          value += part.n;
          length += part.n.length;
          break;

        case "numberAlign":
          lastTabs += 1;
          lastSpaces += part.n;
          break;

        /* istanbul ignore next */

        default:
          throw new Error("Unexpected type '".concat(part.type, "'"));
      }
    }

    flushSpaces();
    return Object.assign({}, ind, {
      value,
      length,
      queue
    });

    function addTabs(count) {
      value += "\t".repeat(count);
      length += options.tabWidth * count;
    }

    function addSpaces(count) {
      value += " ".repeat(count);
      length += count;
    }

    function flush() {
      if (options.useTabs) {
        flushTabs();
      } else {
        flushSpaces();
      }
    }

    function flushTabs() {
      if (lastTabs > 0) {
        addTabs(lastTabs);
      }

      resetLast();
    }

    function flushSpaces() {
      if (lastSpaces > 0) {
        addSpaces(lastSpaces);
      }

      resetLast();
    }

    function resetLast() {
      lastTabs = 0;
      lastSpaces = 0;
    }
  }

  function trim$1(out) {
    if (out.length === 0) {
      return 0;
    }

    let trimCount = 0; // Trim whitespace at the end of line

    while (out.length > 0 && typeof out[out.length - 1] === "string" && out[out.length - 1].match(/^[\t ]*$/)) {
      trimCount += out.pop().length;
    }

    if (out.length && typeof out[out.length - 1] === "string") {
      const trimmed = out[out.length - 1].replace(/[\t ]*$/, "");
      trimCount += out[out.length - 1].length - trimmed.length;
      out[out.length - 1] = trimmed;
    }

    return trimCount;
  }

  function fits(next, restCommands, width, options, mustBeFlat) {
    let restIdx = restCommands.length;
    const cmds = [next]; // `out` is only used for width counting because `trim` requires to look
    // backwards for space characters.

    const out = [];

    while (width >= 0) {
      if (cmds.length === 0) {
        if (restIdx === 0) {
          return true;
        }

        cmds.push(restCommands[restIdx - 1]);
        restIdx--;
        continue;
      }

      const [ind, mode, doc] = cmds.pop();

      if (typeof doc === "string") {
        out.push(doc);
        width -= getStringWidth$1(doc);
      } else {
        switch (doc.type) {
          case "concat":
            for (let i = doc.parts.length - 1; i >= 0; i--) {
              cmds.push([ind, mode, doc.parts[i]]);
            }

            break;

          case "indent":
            cmds.push([makeIndent(ind, options), mode, doc.contents]);
            break;

          case "align":
            cmds.push([makeAlign(ind, doc.n, options), mode, doc.contents]);
            break;

          case "trim":
            width += trim$1(out);
            break;

          case "group":
            if (mustBeFlat && doc.break) {
              return false;
            }

            cmds.push([ind, doc.break ? MODE_BREAK : mode, doc.contents]);

            if (doc.id) {
              groupModeMap[doc.id] = cmds[cmds.length - 1][1];
            }

            break;

          case "fill":
            for (let i = doc.parts.length - 1; i >= 0; i--) {
              cmds.push([ind, mode, doc.parts[i]]);
            }

            break;

          case "if-break":
            {
              const groupMode = doc.groupId ? groupModeMap[doc.groupId] : mode;

              if (groupMode === MODE_BREAK) {
                if (doc.breakContents) {
                  cmds.push([ind, mode, doc.breakContents]);
                }
              }

              if (groupMode === MODE_FLAT) {
                if (doc.flatContents) {
                  cmds.push([ind, mode, doc.flatContents]);
                }
              }

              break;
            }

          case "line":
            switch (mode) {
              // fallthrough
              case MODE_FLAT:
                if (!doc.hard) {
                  if (!doc.soft) {
                    out.push(" ");
                    width -= 1;
                  }

                  break;
                }

                return true;

              case MODE_BREAK:
                return true;
            }

            break;
        }
      }
    }

    return false;
  }

  function printDocToString(doc, options) {
    groupModeMap = {};
    const width = options.printWidth;
    const newLine = convertEndOfLineToChars$1(options.endOfLine);
    let pos = 0; // cmds is basically a stack. We've turned a recursive call into a
    // while loop which is much faster. The while loop below adds new
    // cmds to the array instead of recursively calling `print`.

    const cmds = [[rootIndent(), MODE_BREAK, doc]];
    const out = [];
    let shouldRemeasure = false;
    let lineSuffix = [];

    while (cmds.length !== 0) {
      const [ind, mode, doc] = cmds.pop();

      if (typeof doc === "string") {
        const formatted = newLine !== "\n" && doc.includes("\n") ? doc.replace(/\n/g, newLine) : doc;
        out.push(formatted);
        pos += getStringWidth$1(formatted);
      } else {
        switch (doc.type) {
          case "cursor":
            out.push(cursor$1.placeholder);
            break;

          case "concat":
            for (let i = doc.parts.length - 1; i >= 0; i--) {
              cmds.push([ind, mode, doc.parts[i]]);
            }

            break;

          case "indent":
            cmds.push([makeIndent(ind, options), mode, doc.contents]);
            break;

          case "align":
            cmds.push([makeAlign(ind, doc.n, options), mode, doc.contents]);
            break;

          case "trim":
            pos -= trim$1(out);
            break;

          case "group":
            switch (mode) {
              case MODE_FLAT:
                if (!shouldRemeasure) {
                  cmds.push([ind, doc.break ? MODE_BREAK : MODE_FLAT, doc.contents]);
                  break;
                }

              // fallthrough

              case MODE_BREAK:
                {
                  shouldRemeasure = false;
                  const next = [ind, MODE_FLAT, doc.contents];
                  const rem = width - pos;

                  if (!doc.break && fits(next, cmds, rem, options)) {
                    cmds.push(next);
                  } else {
                    // Expanded states are a rare case where a document
                    // can manually provide multiple representations of
                    // itself. It provides an array of documents
                    // going from the least expanded (most flattened)
                    // representation first to the most expanded. If a
                    // group has these, we need to manually go through
                    // these states and find the first one that fits.
                    if (doc.expandedStates) {
                      const mostExpanded = doc.expandedStates[doc.expandedStates.length - 1];

                      if (doc.break) {
                        cmds.push([ind, MODE_BREAK, mostExpanded]);
                        break;
                      } else {
                        for (let i = 1; i < doc.expandedStates.length + 1; i++) {
                          if (i >= doc.expandedStates.length) {
                            cmds.push([ind, MODE_BREAK, mostExpanded]);
                            break;
                          } else {
                            const state = doc.expandedStates[i];
                            const cmd = [ind, MODE_FLAT, state];

                            if (fits(cmd, cmds, rem, options)) {
                              cmds.push(cmd);
                              break;
                            }
                          }
                        }
                      }
                    } else {
                      cmds.push([ind, MODE_BREAK, doc.contents]);
                    }
                  }

                  break;
                }
            }

            if (doc.id) {
              groupModeMap[doc.id] = cmds[cmds.length - 1][1];
            }

            break;
          // Fills each line with as much code as possible before moving to a new
          // line with the same indentation.
          //
          // Expects doc.parts to be an array of alternating content and
          // whitespace. The whitespace contains the linebreaks.
          //
          // For example:
          //   ["I", line, "love", line, "monkeys"]
          // or
          //   [{ type: group, ... }, softline, { type: group, ... }]
          //
          // It uses this parts structure to handle three main layout cases:
          // * The first two content items fit on the same line without
          //   breaking
          //   -> output the first content item and the whitespace "flat".
          // * Only the first content item fits on the line without breaking
          //   -> output the first content item "flat" and the whitespace with
          //   "break".
          // * Neither content item fits on the line without breaking
          //   -> output the first content item and the whitespace with "break".

          case "fill":
            {
              const rem = width - pos;
              const {
                parts
              } = doc;

              if (parts.length === 0) {
                break;
              }

              const [content, whitespace] = parts;
              const contentFlatCmd = [ind, MODE_FLAT, content];
              const contentBreakCmd = [ind, MODE_BREAK, content];
              const contentFits = fits(contentFlatCmd, [], rem, options, true);

              if (parts.length === 1) {
                if (contentFits) {
                  cmds.push(contentFlatCmd);
                } else {
                  cmds.push(contentBreakCmd);
                }

                break;
              }

              const whitespaceFlatCmd = [ind, MODE_FLAT, whitespace];
              const whitespaceBreakCmd = [ind, MODE_BREAK, whitespace];

              if (parts.length === 2) {
                if (contentFits) {
                  cmds.push(whitespaceFlatCmd);
                  cmds.push(contentFlatCmd);
                } else {
                  cmds.push(whitespaceBreakCmd);
                  cmds.push(contentBreakCmd);
                }

                break;
              } // At this point we've handled the first pair (context, separator)
              // and will create a new fill doc for the rest of the content.
              // Ideally we wouldn't mutate the array here but copying all the
              // elements to a new array would make this algorithm quadratic,
              // which is unusable for large arrays (e.g. large texts in JSX).


              parts.splice(0, 2);
              const remainingCmd = [ind, mode, fill$1(parts)];
              const secondContent = parts[0];
              const firstAndSecondContentFlatCmd = [ind, MODE_FLAT, concat$1([content, whitespace, secondContent])];
              const firstAndSecondContentFits = fits(firstAndSecondContentFlatCmd, [], rem, options, true);

              if (firstAndSecondContentFits) {
                cmds.push(remainingCmd);
                cmds.push(whitespaceFlatCmd);
                cmds.push(contentFlatCmd);
              } else if (contentFits) {
                cmds.push(remainingCmd);
                cmds.push(whitespaceBreakCmd);
                cmds.push(contentFlatCmd);
              } else {
                cmds.push(remainingCmd);
                cmds.push(whitespaceBreakCmd);
                cmds.push(contentBreakCmd);
              }

              break;
            }

          case "if-break":
            {
              const groupMode = doc.groupId ? groupModeMap[doc.groupId] : mode;

              if (groupMode === MODE_BREAK) {
                if (doc.breakContents) {
                  cmds.push([ind, mode, doc.breakContents]);
                }
              }

              if (groupMode === MODE_FLAT) {
                if (doc.flatContents) {
                  cmds.push([ind, mode, doc.flatContents]);
                }
              }

              break;
            }

          case "line-suffix":
            lineSuffix.push([ind, mode, doc.contents]);
            break;

          case "line-suffix-boundary":
            if (lineSuffix.length > 0) {
              cmds.push([ind, mode, {
                type: "line",
                hard: true
              }]);
            }

            break;

          case "line":
            switch (mode) {
              case MODE_FLAT:
                if (!doc.hard) {
                  if (!doc.soft) {
                    out.push(" ");
                    pos += 1;
                  }

                  break;
                } else {
                  // This line was forced into the output even if we
                  // were in flattened mode, so we need to tell the next
                  // group that no matter what, it needs to remeasure
                  // because the previous measurement didn't accurately
                  // capture the entire expression (this is necessary
                  // for nested groups)
                  shouldRemeasure = true;
                }

              // fallthrough

              case MODE_BREAK:
                if (lineSuffix.length) {
                  cmds.push([ind, mode, doc]);
                  cmds.push(...lineSuffix.reverse());
                  lineSuffix = [];
                  break;
                }

                if (doc.literal) {
                  if (ind.root) {
                    out.push(newLine, ind.root.value);
                    pos = ind.root.length;
                  } else {
                    out.push(newLine);
                    pos = 0;
                  }
                } else {
                  pos -= trim$1(out);
                  out.push(newLine + ind.value);
                  pos = ind.length;
                }

                break;
            }

            break;
        }
      }
    }

    const cursorPlaceholderIndex = out.indexOf(cursor$1.placeholder);

    if (cursorPlaceholderIndex !== -1) {
      const otherCursorPlaceholderIndex = out.indexOf(cursor$1.placeholder, cursorPlaceholderIndex + 1);
      const beforeCursor = out.slice(0, cursorPlaceholderIndex).join("");
      const aroundCursor = out.slice(cursorPlaceholderIndex + 1, otherCursorPlaceholderIndex).join("");
      const afterCursor = out.slice(otherCursorPlaceholderIndex + 1).join("");
      return {
        formatted: beforeCursor + aroundCursor + afterCursor,
        cursorNodeStart: beforeCursor.length,
        cursorNodeText: aroundCursor
      };
    }

    return {
      formatted: out.join("")
    };
  }

  var docPrinter = {
    printDocToString
  };

  const {
    literalline: literalline$1,
    concat: concat$2
  } = docBuilders; // Using a unique object to compare by reference.

  const traverseDocOnExitStackMarker = {};

  function traverseDoc(doc, onEnter, onExit, shouldTraverseConditionalGroups) {
    const docsStack = [doc];

    while (docsStack.length !== 0) {
      const doc = docsStack.pop();

      if (doc === traverseDocOnExitStackMarker) {
        onExit(docsStack.pop());
        continue;
      }

      if (onExit) {
        docsStack.push(doc, traverseDocOnExitStackMarker);
      }

      if ( // Should Recurse
      !onEnter || onEnter(doc) !== false) {
        // When there are multiple parts to process,
        // the parts need to be pushed onto the stack in reverse order,
        // so that they are processed in the original order
        // when the stack is popped.
        if (doc.type === "concat" || doc.type === "fill") {
          for (let ic = doc.parts.length, i = ic - 1; i >= 0; --i) {
            docsStack.push(doc.parts[i]);
          }
        } else if (doc.type === "if-break") {
          if (doc.flatContents) {
            docsStack.push(doc.flatContents);
          }

          if (doc.breakContents) {
            docsStack.push(doc.breakContents);
          }
        } else if (doc.type === "group" && doc.expandedStates) {
          if (shouldTraverseConditionalGroups) {
            for (let ic = doc.expandedStates.length, i = ic - 1; i >= 0; --i) {
              docsStack.push(doc.expandedStates[i]);
            }
          } else {
            docsStack.push(doc.contents);
          }
        } else if (doc.contents) {
          docsStack.push(doc.contents);
        }
      }
    }
  }

  function mapDoc(doc, cb) {
    if (doc.type === "concat" || doc.type === "fill") {
      const parts = doc.parts.map(part => mapDoc(part, cb));
      return cb(Object.assign({}, doc, {
        parts
      }));
    } else if (doc.type === "if-break") {
      const breakContents = doc.breakContents && mapDoc(doc.breakContents, cb);
      const flatContents = doc.flatContents && mapDoc(doc.flatContents, cb);
      return cb(Object.assign({}, doc, {
        breakContents,
        flatContents
      }));
    } else if (doc.contents) {
      const contents = mapDoc(doc.contents, cb);
      return cb(Object.assign({}, doc, {
        contents
      }));
    }

    return cb(doc);
  }

  function findInDoc(doc, fn, defaultValue) {
    let result = defaultValue;
    let hasStopped = false;

    function findInDocOnEnterFn(doc) {
      const maybeResult = fn(doc);

      if (maybeResult !== undefined) {
        hasStopped = true;
        result = maybeResult;
      }

      if (hasStopped) {
        return false;
      }
    }

    traverseDoc(doc, findInDocOnEnterFn);
    return result;
  }

  function isEmpty(n) {
    return typeof n === "string" && n.length === 0;
  }

  function isLineNextFn(doc) {
    if (typeof doc === "string") {
      return false;
    }

    if (doc.type === "line") {
      return true;
    }
  }

  function isLineNext(doc) {
    return findInDoc(doc, isLineNextFn, false);
  }

  function willBreakFn(doc) {
    if (doc.type === "group" && doc.break) {
      return true;
    }

    if (doc.type === "line" && doc.hard) {
      return true;
    }

    if (doc.type === "break-parent") {
      return true;
    }
  }

  function willBreak(doc) {
    return findInDoc(doc, willBreakFn, false);
  }

  function breakParentGroup(groupStack) {
    if (groupStack.length > 0) {
      const parentGroup = groupStack[groupStack.length - 1]; // Breaks are not propagated through conditional groups because
      // the user is expected to manually handle what breaks.

      if (!parentGroup.expandedStates) {
        parentGroup.break = true;
      }
    }

    return null;
  }

  function propagateBreaks(doc) {
    const alreadyVisitedSet = new Set();
    const groupStack = [];

    function propagateBreaksOnEnterFn(doc) {
      if (doc.type === "break-parent") {
        breakParentGroup(groupStack);
      }

      if (doc.type === "group") {
        groupStack.push(doc);

        if (alreadyVisitedSet.has(doc)) {
          return false;
        }

        alreadyVisitedSet.add(doc);
      }
    }

    function propagateBreaksOnExitFn(doc) {
      if (doc.type === "group") {
        const group = groupStack.pop();

        if (group.break) {
          breakParentGroup(groupStack);
        }
      }
    }

    traverseDoc(doc, propagateBreaksOnEnterFn, propagateBreaksOnExitFn,
    /* shouldTraverseConditionalGroups */
    true);
  }

  function removeLinesFn(doc) {
    // Force this doc into flat mode by statically converting all
    // lines into spaces (or soft lines into nothing). Hard lines
    // should still output because there's too great of a chance
    // of breaking existing assumptions otherwise.
    if (doc.type === "line" && !doc.hard) {
      return doc.soft ? "" : " ";
    } else if (doc.type === "if-break") {
      return doc.flatContents || "";
    }

    return doc;
  }

  function removeLines(doc) {
    return mapDoc(doc, removeLinesFn);
  }

  function getInnerParts(doc) {
    let {
      parts
    } = doc;
    let lastPart; // Avoid a falsy element like ""

    for (let i = doc.parts.length; i > 0 && !lastPart; i--) {
      lastPart = parts[i - 1];
    }

    if (lastPart.type === "group") {
      parts = lastPart.contents.parts;
    }

    return parts;
  }

  function stripTrailingHardline(doc, withInnerParts = false) {
    // HACK remove ending hardline, original PR: #1984
    if (doc.type === "concat" && doc.parts.length !== 0) {
      const parts = withInnerParts ? getInnerParts(doc) : doc.parts;
      const lastPart = parts[parts.length - 1];

      if (lastPart.type === "concat") {
        if (lastPart.parts.length === 2 && lastPart.parts[0].hard && lastPart.parts[1].type === "break-parent") {
          return {
            type: "concat",
            parts: parts.slice(0, -1)
          };
        }

        return {
          type: "concat",
          parts: doc.parts.slice(0, -1).concat(stripTrailingHardline(lastPart))
        };
      }
    }

    return doc;
  }

  function normalizeParts(parts) {
    const newParts = [];
    const restParts = parts.filter(Boolean);

    while (restParts.length !== 0) {
      const part = restParts.shift();

      if (!part) {
        continue;
      }

      if (part.type === "concat") {
        restParts.unshift(...part.parts);
        continue;
      }

      if (newParts.length !== 0 && typeof newParts[newParts.length - 1] === "string" && typeof part === "string") {
        newParts[newParts.length - 1] += part;
        continue;
      }

      newParts.push(part);
    }

    return newParts;
  }

  function normalizeDoc(doc) {
    return mapDoc(doc, currentDoc => {
      if (!currentDoc.parts) {
        return currentDoc;
      }

      return Object.assign({}, currentDoc, {
        parts: normalizeParts(currentDoc.parts)
      });
    });
  }

  function replaceNewlinesWithLiterallines(doc) {
    return mapDoc(doc, currentDoc => typeof currentDoc === "string" && currentDoc.includes("\n") ? concat$2(currentDoc.split(/(\n)/g).map((v, i) => i % 2 === 0 ? v : literalline$1)) : currentDoc);
  }

  var docUtils = {
    isEmpty,
    willBreak,
    isLineNext,
    traverseDoc,
    findInDoc,
    mapDoc,
    propagateBreaks,
    removeLines,
    stripTrailingHardline,
    normalizeParts,
    normalizeDoc,
    replaceNewlinesWithLiterallines
  };

  function flattenDoc(doc) {
    if (doc.type === "concat") {
      const res = [];

      for (let i = 0; i < doc.parts.length; ++i) {
        const doc2 = doc.parts[i];

        if (typeof doc2 !== "string" && doc2.type === "concat") {
          res.push(...flattenDoc(doc2).parts);
        } else {
          const flattened = flattenDoc(doc2);

          if (flattened !== "") {
            res.push(flattened);
          }
        }
      }

      return Object.assign({}, doc, {
        parts: res
      });
    } else if (doc.type === "if-break") {
      return Object.assign({}, doc, {
        breakContents: doc.breakContents != null ? flattenDoc(doc.breakContents) : null,
        flatContents: doc.flatContents != null ? flattenDoc(doc.flatContents) : null
      });
    } else if (doc.type === "group") {
      return Object.assign({}, doc, {
        contents: flattenDoc(doc.contents),
        expandedStates: doc.expandedStates ? doc.expandedStates.map(flattenDoc) : doc.expandedStates
      });
    } else if (doc.contents) {
      return Object.assign({}, doc, {
        contents: flattenDoc(doc.contents)
      });
    }

    return doc;
  }

  function printDoc(doc) {
    if (typeof doc === "string") {
      return JSON.stringify(doc);
    }

    if (doc.type === "line") {
      if (doc.literal) {
        return "literalline";
      }

      if (doc.hard) {
        return "hardline";
      }

      if (doc.soft) {
        return "softline";
      }

      return "line";
    }

    if (doc.type === "break-parent") {
      return "breakParent";
    }

    if (doc.type === "trim") {
      return "trim";
    }

    if (doc.type === "concat") {
      return "[" + doc.parts.map(printDoc).join(", ") + "]";
    }

    if (doc.type === "indent") {
      return "indent(" + printDoc(doc.contents) + ")";
    }

    if (doc.type === "align") {
      return doc.n === -Infinity ? "dedentToRoot(" + printDoc(doc.contents) + ")" : doc.n < 0 ? "dedent(" + printDoc(doc.contents) + ")" : doc.n.type === "root" ? "markAsRoot(" + printDoc(doc.contents) + ")" : "align(" + JSON.stringify(doc.n) + ", " + printDoc(doc.contents) + ")";
    }

    if (doc.type === "if-break") {
      return "ifBreak(" + printDoc(doc.breakContents) + (doc.flatContents ? ", " + printDoc(doc.flatContents) : "") + ")";
    }

    if (doc.type === "group") {
      if (doc.expandedStates) {
        return "conditionalGroup(" + "[" + doc.expandedStates.map(printDoc).join(",") + "])";
      }

      return (doc.break ? "wrappedGroup" : "group") + "(" + printDoc(doc.contents) + ")";
    }

    if (doc.type === "fill") {
      return "fill" + "(" + doc.parts.map(printDoc).join(", ") + ")";
    }

    if (doc.type === "line-suffix") {
      return "lineSuffix(" + printDoc(doc.contents) + ")";
    }

    if (doc.type === "line-suffix-boundary") {
      return "lineSuffixBoundary";
    }

    throw new Error("Unknown doc type " + doc.type);
  }

  var docDebug = {
    printDocToDebug(doc) {
      return printDoc(flattenDoc(doc));
    }

  };

  /**
   * @typedef {import("./doc-builders").Doc} Doc
   */


  var document = {
    builders: docBuilders,
    printer: docPrinter,
    utils: docUtils,
    debug: docDebug
  };

  return document;

})));
