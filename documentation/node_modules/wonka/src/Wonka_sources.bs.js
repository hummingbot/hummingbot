

import * as Block from "bs-platform/lib/es6/block.js";
import * as Wonka_helpers from "./helpers/Wonka_helpers.bs.js";

function fromArray(arr) {
  return (function (sink) {
      var size = arr.length;
      var state = {
        ended: false,
        looping: false,
        pulled: false,
        current: 0
      };
      return sink(/* Start */Block.__(0, [(function (signal) {
                        var match = state.looping;
                        if (signal) {
                          state.ended = true;
                          return ;
                        }
                        if (match) {
                          state.pulled = true;
                          return ;
                        }
                        state.pulled = true;
                        state.looping = true;
                        while(state.pulled && !state.ended) {
                          if (state.current < size) {
                            var x = arr[state.current];
                            state.current = state.current + 1 | 0;
                            state.pulled = false;
                            sink(/* Push */Block.__(1, [x]));
                          } else {
                            state.ended = true;
                            sink(/* End */0);
                          }
                        };
                        state.looping = false;
                        
                      })]));
    });
}

function fromList(ls) {
  return (function (sink) {
      var state = {
        ended: false,
        looping: false,
        pulled: false,
        current: ls
      };
      return sink(/* Start */Block.__(0, [(function (signal) {
                        var match = state.looping;
                        if (signal) {
                          state.ended = true;
                          return ;
                        }
                        if (match) {
                          state.pulled = true;
                          return ;
                        }
                        state.pulled = true;
                        state.looping = true;
                        while(state.pulled && !state.ended) {
                          var match$1 = state.current;
                          if (match$1) {
                            state.current = match$1[1];
                            state.pulled = false;
                            sink(/* Push */Block.__(1, [match$1[0]]));
                          } else {
                            state.ended = true;
                            sink(/* End */0);
                          }
                        };
                        state.looping = false;
                        
                      })]));
    });
}

function fromValue(x) {
  return (function (sink) {
      var ended = {
        contents: false
      };
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (signal) {
                          ended.contents = true;
                          return ;
                        } else if (!ended.contents) {
                          ended.contents = true;
                          sink(/* Push */Block.__(1, [x]));
                          return sink(/* End */0);
                        } else {
                          return ;
                        }
                      })]));
    });
}

function make(f) {
  return (function (sink) {
      var state = {
        teardown: (function () {
            
          }),
        ended: false
      };
      state.teardown = f({
            next: (function (value) {
                if (!state.ended) {
                  return sink(/* Push */Block.__(1, [value]));
                }
                
              }),
            complete: (function (param) {
                if (!state.ended) {
                  state.ended = true;
                  return sink(/* End */0);
                }
                
              })
          });
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (signal && !state.ended) {
                          state.ended = true;
                          return state.teardown();
                        }
                        
                      })]));
    });
}

function makeSubject(param) {
  var state = {
    sinks: new Array(),
    ended: false
  };
  var source = function (sink) {
    state.sinks = state.sinks.concat(sink);
    return sink(/* Start */Block.__(0, [(function (signal) {
                      if (signal) {
                        state.sinks = state.sinks.filter((function (x) {
                                return x !== sink;
                              }));
                        return ;
                      }
                      
                    })]));
  };
  var next = function (value) {
    if (!state.ended) {
      state.sinks.forEach((function (sink) {
              return sink(/* Push */Block.__(1, [value]));
            }));
      return ;
    }
    
  };
  var complete = function (param) {
    if (!state.ended) {
      state.ended = true;
      state.sinks.forEach((function (sink) {
              return sink(/* End */0);
            }));
      return ;
    }
    
  };
  return {
          source: source,
          next: next,
          complete: complete
        };
}

function empty(sink) {
  var ended = {
    contents: false
  };
  return sink(/* Start */Block.__(0, [(function (signal) {
                    if (signal) {
                      ended.contents = true;
                      return ;
                    } else if (!ended.contents) {
                      return sink(/* End */0);
                    } else {
                      return ;
                    }
                  })]));
}

function never(sink) {
  return sink(/* Start */Block.__(0, [Wonka_helpers.talkbackPlaceholder]));
}

export {
  fromArray ,
  fromList ,
  fromValue ,
  make ,
  makeSubject ,
  empty ,
  never ,
  
}
/* No side effect */
