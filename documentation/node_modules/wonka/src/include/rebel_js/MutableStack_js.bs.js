


var Helpers = { };

function isEmpty(stack) {
  return stack.length === 0;
}

function top(stack) {
  return stack[stack.length - 1 | 0];
}

export {
  Helpers ,
  isEmpty ,
  top ,
  
}
/* No side effect */
