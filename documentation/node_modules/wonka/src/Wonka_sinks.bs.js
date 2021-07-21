

import * as Curry from "bs-platform/lib/es6/curry.js";
import * as Wonka_helpers from "./helpers/Wonka_helpers.bs.js";

function subscribe(f) {
  return (function (source) {
      var state = {
        talkback: Wonka_helpers.talkbackPlaceholder,
        ended: false
      };
      Curry._1(source, (function (signal) {
              if (typeof signal === "number") {
                state.ended = true;
                return ;
              }
              if (signal.tag) {
                if (!state.ended) {
                  f(signal[0]);
                  return state.talkback(/* Pull */0);
                } else {
                  return ;
                }
              }
              var x = signal[0];
              state.talkback = x;
              return x(/* Pull */0);
            }));
      return {
              unsubscribe: (function (param) {
                  if (!state.ended) {
                    state.ended = true;
                    return state.talkback(/* Close */1);
                  }
                  
                })
            };
    });
}

function forEach(f) {
  return (function (source) {
      subscribe(f)(source);
      
    });
}

function publish(source) {
  return subscribe((function (param) {
                  
                }))(source);
}

function toArray(source) {
  var state = {
    values: new Array(),
    talkback: Wonka_helpers.talkbackPlaceholder,
    value: undefined,
    ended: false
  };
  Curry._1(source, (function (signal) {
          if (typeof signal === "number") {
            state.ended = true;
            return ;
          }
          if (signal.tag) {
            state.values.push(signal[0]);
            return state.talkback(/* Pull */0);
          }
          var x = signal[0];
          state.talkback = x;
          return x(/* Pull */0);
        }));
  if (!state.ended) {
    state.talkback(/* Close */1);
  }
  return state.values;
}

export {
  subscribe ,
  forEach ,
  publish ,
  toArray ,
  
}
/* No side effect */
