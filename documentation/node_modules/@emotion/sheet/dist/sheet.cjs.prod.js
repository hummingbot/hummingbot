"use strict";

function sheetForTag(tag) {
  if (tag.sheet) return tag.sheet;
  for (var i = 0; i < document.styleSheets.length; i++) if (document.styleSheets[i].ownerNode === tag) return document.styleSheets[i];
}

function createStyleElement(options) {
  var tag = document.createElement("style");
  return tag.setAttribute("data-emotion", options.key), void 0 !== options.nonce && tag.setAttribute("nonce", options.nonce), 
  tag.appendChild(document.createTextNode("")), tag;
}

Object.defineProperty(exports, "__esModule", {
  value: !0
});

var StyleSheet = function() {
  function StyleSheet(options) {
    this.isSpeedy = void 0 === options.speedy || options.speedy, this.tags = [], this.ctr = 0, 
    this.nonce = options.nonce, this.key = options.key, this.container = options.container, 
    this.before = null;
  }
  var _proto = StyleSheet.prototype;
  return _proto.insert = function(rule) {
    if (this.ctr % (this.isSpeedy ? 65e3 : 1) == 0) {
      var before, _tag = createStyleElement(this);
      before = 0 === this.tags.length ? this.before : this.tags[this.tags.length - 1].nextSibling, 
      this.container.insertBefore(_tag, before), this.tags.push(_tag);
    }
    var tag = this.tags[this.tags.length - 1];
    if (this.isSpeedy) {
      var sheet = sheetForTag(tag);
      try {
        var isImportRule = 105 === rule.charCodeAt(1) && 64 === rule.charCodeAt(0);
        sheet.insertRule(rule, isImportRule ? 0 : sheet.cssRules.length);
      } catch (e) {}
    } else tag.appendChild(document.createTextNode(rule));
    this.ctr++;
  }, _proto.flush = function() {
    this.tags.forEach(function(tag) {
      return tag.parentNode.removeChild(tag);
    }), this.tags = [], this.ctr = 0;
  }, StyleSheet;
}();

exports.StyleSheet = StyleSheet;
