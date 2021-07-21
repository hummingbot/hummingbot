

import * as Block from "bs-platform/lib/es6/block.js";
import * as Curry from "bs-platform/lib/es6/curry.js";
import * as Caml_option from "bs-platform/lib/es6/caml_option.js";
import * as Wonka_callbag from "./Wonka_callbag.bs.js";
import * as Wonka_operators from "../Wonka_operators.bs.js";
import * as Wonka_observable from "./Wonka_observable.bs.js";

function debounce(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            id: undefined,
            deferredEnded: false,
            ended: false
          };
          var $$clearTimeout$1 = function (param) {
            var timeoutId = state.id;
            if (timeoutId !== undefined) {
              state.id = undefined;
              clearTimeout(Caml_option.valFromOption(timeoutId));
              return ;
            }
            
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          if (state.ended) {
                            return ;
                          }
                          state.ended = true;
                          var match = state.id;
                          if (match !== undefined) {
                            state.deferredEnded = true;
                            return ;
                          } else {
                            return sink(/* End */0);
                          }
                        }
                        if (signal.tag) {
                          if (!state.ended) {
                            $$clearTimeout$1(undefined);
                            state.id = Caml_option.some(setTimeout((function (param) {
                                        state.id = undefined;
                                        sink(signal);
                                        if (state.deferredEnded) {
                                          return sink(/* End */0);
                                        }
                                        
                                      }), f(signal[0])));
                            return ;
                          } else {
                            return ;
                          }
                        }
                        var tb = signal[0];
                        return sink(/* Start */Block.__(0, [(function (signal) {
                                          if (!state.ended) {
                                            if (signal) {
                                              state.ended = true;
                                              state.deferredEnded = false;
                                              $$clearTimeout$1(undefined);
                                              return tb(/* Close */1);
                                            } else {
                                              return tb(/* Pull */0);
                                            }
                                          }
                                          
                                        })]));
                      }));
        });
    });
}

function delay(wait) {
  return (function (source) {
      return (function (sink) {
          var active = {
            contents: 0
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal !== "number" && !signal.tag) {
                          return sink(signal);
                        }
                        active.contents = active.contents + 1 | 0;
                        setTimeout((function (param) {
                                if (active.contents !== 0) {
                                  active.contents = active.contents - 1 | 0;
                                  return sink(signal);
                                }
                                
                              }), wait);
                        
                      }));
        });
    });
}

function throttle(f) {
  return (function (source) {
      return (function (sink) {
          var skip = {
            contents: false
          };
          var id = {
            contents: undefined
          };
          var $$clearTimeout$1 = function (param) {
            var timeoutId = id.contents;
            if (timeoutId !== undefined) {
              clearTimeout(Caml_option.valFromOption(timeoutId));
              return ;
            }
            
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          $$clearTimeout$1(undefined);
                          return sink(/* End */0);
                        }
                        if (signal.tag) {
                          if (!skip.contents) {
                            skip.contents = true;
                            $$clearTimeout$1(undefined);
                            id.contents = Caml_option.some(setTimeout((function (param) {
                                        id.contents = undefined;
                                        skip.contents = false;
                                        
                                      }), f(signal[0])));
                            return sink(signal);
                          } else {
                            return ;
                          }
                        }
                        var tb = signal[0];
                        return sink(/* Start */Block.__(0, [(function (signal) {
                                          if (signal) {
                                            $$clearTimeout$1(undefined);
                                            return tb(/* Close */1);
                                          } else {
                                            return tb(signal);
                                          }
                                        })]));
                      }));
        });
    });
}

function toPromise(source) {
  return new Promise((function (resolve, param) {
                Curry._1(Wonka_operators.takeLast(1)(source), (function (signal) {
                        if (typeof signal === "number") {
                          return ;
                        } else if (signal.tag) {
                          return resolve(signal[0]);
                        } else {
                          return signal[0](/* Pull */0);
                        }
                      }));
                
              }));
}

function interval(p) {
  return (function (sink) {
      var i = {
        contents: 0
      };
      var id = setInterval((function (param) {
              var num = i.contents;
              i.contents = i.contents + 1 | 0;
              return sink(/* Push */Block.__(1, [num]));
            }), p);
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (signal) {
                          clearInterval(id);
                          return ;
                        }
                        
                      })]));
    });
}

function fromDomEvent(element, $$event) {
  return (function (sink) {
      var addEventListener = (function (element, event, handler) {
      element.addEventListener(event, handler);
    });
      var removeEventListener = (function (element, event, handler) {
      element.removeEventListener(event, handler);
    });
      var handler = function ($$event) {
        return sink(/* Push */Block.__(1, [$$event]));
      };
      sink(/* Start */Block.__(0, [(function (signal) {
                  if (signal) {
                    return removeEventListener(element, $$event, handler);
                  }
                  
                })]));
      return addEventListener(element, $$event, handler);
    });
}

function fromPromise(promise) {
  return (function (sink) {
      var ended = {
        contents: false
      };
      promise.then((function (value) {
              if (!ended.contents) {
                sink(/* Push */Block.__(1, [value]));
                sink(/* End */0);
              }
              return Promise.resolve(undefined);
            }));
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (signal) {
                          ended.contents = true;
                          return ;
                        }
                        
                      })]));
    });
}

var fromObservable = Wonka_observable.fromObservable;

var toObservable = Wonka_observable.toObservable;

var fromCallbag = Wonka_callbag.fromCallbag;

var toCallbag = Wonka_callbag.toCallbag;

export {
  fromObservable ,
  toObservable ,
  fromCallbag ,
  toCallbag ,
  debounce ,
  delay ,
  throttle ,
  toPromise ,
  interval ,
  fromDomEvent ,
  fromPromise ,
  
}
/* Wonka_observable Not a pure module */
