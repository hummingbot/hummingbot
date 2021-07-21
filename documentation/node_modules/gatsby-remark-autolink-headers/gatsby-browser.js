"use strict";

var offsetY = 0;

var getTargetOffset = function getTargetOffset(hash) {
  var id = window.decodeURI(hash.replace("#", ""));

  if (id !== "") {
    var element = document.getElementById(id);

    if (element) {
      var scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
      var clientTop = document.documentElement.clientTop || document.body.clientTop || 0;
      var computedStyles = window.getComputedStyle(element);
      var scrollMarginTop = computedStyles.getPropertyValue("scroll-margin-top") || computedStyles.getPropertyValue("scroll-snap-margin-top") || "0px";
      return element.getBoundingClientRect().top + scrollTop - parseInt(scrollMarginTop, 10) - clientTop - offsetY;
    }
  }

  return null;
};

exports.onInitialClientRender = function (_, pluginOptions) {
  if (pluginOptions.offsetY) {
    offsetY = pluginOptions.offsetY;
  }

  requestAnimationFrame(function () {
    var offset = getTargetOffset(window.location.hash);

    if (offset !== null) {
      window.scrollTo(0, offset);
    }
  });
};

exports.shouldUpdateScroll = function (_ref) {
  var location = _ref.routerProps.location;
  var offset = getTargetOffset(location.hash);
  return offset !== null ? [0, offset] : true;
};