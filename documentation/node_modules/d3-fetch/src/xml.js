import text from "./text.js";

function parser(type) {
  return function(input, init)  {
    return text(input, init).then(function(text) {
      return (new DOMParser).parseFromString(text, type);
    });
  };
}

export default parser("application/xml");

export var html = parser("text/html");

export var svg = parser("image/svg+xml");
