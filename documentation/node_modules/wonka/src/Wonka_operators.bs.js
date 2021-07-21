

import * as Block from "bs-platform/lib/es6/block.js";
import * as Curry from "bs-platform/lib/es6/curry.js";
import * as Caml_option from "bs-platform/lib/es6/caml_option.js";
import * as Wonka_helpers from "./helpers/Wonka_helpers.bs.js";
import * as Wonka_sources from "./Wonka_sources.bs.js";
import * as MutableQueue_js from "./include/rebel_js/MutableQueue_js.bs.js";

function buffer(notifier) {
  return (function (source) {
      return (function (sink) {
          var state = {
            buffer: new Array(),
            sourceTalkback: Wonka_helpers.talkbackPlaceholder,
            notifierTalkback: Wonka_helpers.talkbackPlaceholder,
            pulled: false,
            ended: false
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      state.notifierTalkback(/* Close */1);
                      if (state.buffer.length > 0) {
                        sink(/* Push */Block.__(1, [state.buffer]));
                      }
                      sink(/* End */0);
                    }
                    
                  } else if (signal.tag) {
                    if (!state.ended) {
                      state.buffer.push(signal[0]);
                      if (state.pulled) {
                        state.pulled = false;
                      } else {
                        state.pulled = true;
                        state.sourceTalkback(/* Pull */0);
                        state.notifierTalkback(/* Pull */0);
                      }
                    }
                    
                  } else {
                    state.sourceTalkback = signal[0];
                    Curry._1(notifier, (function (signal) {
                            if (typeof signal === "number") {
                              if (!state.ended) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                if (state.buffer.length > 0) {
                                  sink(/* Push */Block.__(1, [state.buffer]));
                                }
                                sink(/* End */0);
                              }
                              
                            } else if (signal.tag) {
                              if (!state.ended && state.buffer.length > 0) {
                                var buffer = state.buffer;
                                state.buffer = new Array();
                                sink(/* Push */Block.__(1, [buffer]));
                              }
                              
                            } else {
                              state.notifierTalkback = signal[0];
                            }
                            
                          }));
                  }
                  
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (!state.ended) {
                              if (signal) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                return state.notifierTalkback(/* Close */1);
                              } else if (!state.pulled) {
                                state.pulled = true;
                                state.sourceTalkback(/* Pull */0);
                                return state.notifierTalkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                            
                          })]));
        });
    });
}

function combine(sourceA, sourceB) {
  return (function (sink) {
      var state = {
        talkbackA: Wonka_helpers.talkbackPlaceholder,
        talkbackB: Wonka_helpers.talkbackPlaceholder,
        lastValA: undefined,
        lastValB: undefined,
        gotSignal: false,
        endCounter: 0,
        ended: false
      };
      Curry._1(sourceA, (function (signal) {
              var match = state.lastValB;
              if (typeof signal === "number") {
                if (state.endCounter < 1) {
                  state.endCounter = state.endCounter + 1 | 0;
                  return ;
                } else if (!state.ended) {
                  state.ended = true;
                  return sink(/* End */0);
                } else {
                  return ;
                }
              }
              if (!signal.tag) {
                state.talkbackA = signal[0];
                return ;
              }
              var a = signal[0];
              if (match !== undefined) {
                if (!state.ended) {
                  state.lastValA = Caml_option.some(a);
                  state.gotSignal = false;
                  return sink(/* Push */Block.__(1, [/* tuple */[
                                  a,
                                  Caml_option.valFromOption(match)
                                ]]));
                } else {
                  return ;
                }
              } else {
                state.lastValA = Caml_option.some(a);
                if (state.gotSignal) {
                  state.gotSignal = false;
                  return ;
                } else {
                  return state.talkbackB(/* Pull */0);
                }
              }
            }));
      Curry._1(sourceB, (function (signal) {
              var match = state.lastValA;
              if (typeof signal === "number") {
                if (state.endCounter < 1) {
                  state.endCounter = state.endCounter + 1 | 0;
                  return ;
                } else if (!state.ended) {
                  state.ended = true;
                  return sink(/* End */0);
                } else {
                  return ;
                }
              }
              if (!signal.tag) {
                state.talkbackB = signal[0];
                return ;
              }
              var b = signal[0];
              if (match !== undefined) {
                if (!state.ended) {
                  state.lastValB = Caml_option.some(b);
                  state.gotSignal = false;
                  return sink(/* Push */Block.__(1, [/* tuple */[
                                  Caml_option.valFromOption(match),
                                  b
                                ]]));
                } else {
                  return ;
                }
              } else {
                state.lastValB = Caml_option.some(b);
                if (state.gotSignal) {
                  state.gotSignal = false;
                  return ;
                } else {
                  return state.talkbackA(/* Pull */0);
                }
              }
            }));
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (!state.ended) {
                          if (signal) {
                            state.ended = true;
                            state.talkbackA(/* Close */1);
                            return state.talkbackB(/* Close */1);
                          } else if (!state.gotSignal) {
                            state.gotSignal = true;
                            state.talkbackA(signal);
                            return state.talkbackB(signal);
                          } else {
                            return ;
                          }
                        }
                        
                      })]));
    });
}

function concatMap(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            inputQueue: new Array(),
            outerTalkback: Wonka_helpers.talkbackPlaceholder,
            outerPulled: false,
            innerTalkback: Wonka_helpers.talkbackPlaceholder,
            innerActive: false,
            innerPulled: false,
            ended: false
          };
          var applyInnerSource = function (innerSource) {
            state.innerActive = true;
            Curry._1(innerSource, (function (signal) {
                    if (typeof signal === "number") {
                      if (state.innerActive) {
                        state.innerActive = false;
                        var input = state.inputQueue.shift();
                        if (input !== undefined) {
                          applyInnerSource(f(Caml_option.valFromOption(input)));
                        } else if (state.ended) {
                          sink(/* End */0);
                        } else if (!state.outerPulled) {
                          state.outerPulled = true;
                          state.outerTalkback(/* Pull */0);
                        }
                        
                      }
                      
                    } else if (signal.tag) {
                      if (state.innerActive) {
                        sink(signal);
                        if (state.innerPulled) {
                          state.innerPulled = false;
                        } else {
                          state.innerTalkback(/* Pull */0);
                        }
                      }
                      
                    } else {
                      var tb = signal[0];
                      state.innerTalkback = tb;
                      state.innerPulled = false;
                      tb(/* Pull */0);
                    }
                    
                  }));
            
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      if (!state.innerActive && MutableQueue_js.isEmpty(state.inputQueue)) {
                        sink(/* End */0);
                      }
                      
                    }
                    
                  } else if (signal.tag) {
                    if (!state.ended) {
                      var x = signal[0];
                      state.outerPulled = false;
                      if (state.innerActive) {
                        state.inputQueue.push(x);
                      } else {
                        applyInnerSource(f(x));
                      }
                    }
                    
                  } else {
                    state.outerTalkback = signal[0];
                  }
                  
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (signal) {
                              if (!state.ended) {
                                state.ended = true;
                                state.outerTalkback(/* Close */1);
                              }
                              if (state.innerActive) {
                                state.innerActive = false;
                                return state.innerTalkback(/* Close */1);
                              } else {
                                return ;
                              }
                            } else {
                              if (!state.ended && !state.outerPulled) {
                                state.outerPulled = true;
                                state.outerTalkback(/* Pull */0);
                              }
                              if (state.innerActive && !state.innerPulled) {
                                state.innerPulled = true;
                                return state.innerTalkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                          })]));
        });
    });
}

function concatAll(source) {
  return concatMap((function (x) {
                  return x;
                }))(source);
}

function concat(sources) {
  return concatMap((function (x) {
                  return x;
                }))(Wonka_sources.fromArray(sources));
}

function filter(f) {
  return (function (source) {
      return (function (sink) {
          var talkback = {
            contents: Wonka_helpers.talkbackPlaceholder
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          sink(signal);
                        } else if (signal.tag) {
                          if (f(signal[0])) {
                            sink(signal);
                          } else {
                            talkback.contents(/* Pull */0);
                          }
                        } else {
                          talkback.contents = signal[0];
                          sink(signal);
                        }
                        
                      }));
        });
    });
}

function map(f) {
  return (function (source) {
      return (function (sink) {
          return Curry._1(source, (function (signal) {
                        var tmp;
                        tmp = typeof signal === "number" ? /* End */0 : (
                            signal.tag ? /* Push */Block.__(1, [f(signal[0])]) : /* Start */Block.__(0, [signal[0]])
                          );
                        return sink(tmp);
                      }));
        });
    });
}

function mergeMap(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            outerTalkback: Wonka_helpers.talkbackPlaceholder,
            outerPulled: false,
            innerTalkbacks: new Array(),
            ended: false
          };
          var applyInnerSource = function (innerSource) {
            var talkback = {
              contents: Wonka_helpers.talkbackPlaceholder
            };
            return Curry._1(innerSource, (function (signal) {
                          if (typeof signal === "number") {
                            if (state.innerTalkbacks.length === 0) {
                              return ;
                            }
                            state.innerTalkbacks = state.innerTalkbacks.filter((function (x) {
                                    return x !== talkback.contents;
                                  }));
                            var exhausted = state.innerTalkbacks.length === 0;
                            if (state.ended && exhausted) {
                              return sink(/* End */0);
                            } else if (!state.outerPulled && exhausted) {
                              state.outerPulled = true;
                              return state.outerTalkback(/* Pull */0);
                            } else {
                              return ;
                            }
                          }
                          if (signal.tag) {
                            if (state.innerTalkbacks.length !== 0) {
                              sink(/* Push */Block.__(1, [signal[0]]));
                              return talkback.contents(/* Pull */0);
                            } else {
                              return ;
                            }
                          }
                          var tb = signal[0];
                          talkback.contents = tb;
                          state.innerTalkbacks = state.innerTalkbacks.concat(tb);
                          return tb(/* Pull */0);
                        }));
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      if (state.innerTalkbacks.length === 0) {
                        return sink(/* End */0);
                      } else {
                        return ;
                      }
                    } else {
                      return ;
                    }
                  } else if (signal.tag) {
                    if (!state.ended) {
                      state.outerPulled = false;
                      applyInnerSource(f(signal[0]));
                      if (!state.outerPulled) {
                        state.outerPulled = true;
                        return state.outerTalkback(/* Pull */0);
                      } else {
                        return ;
                      }
                    } else {
                      return ;
                    }
                  } else {
                    state.outerTalkback = signal[0];
                    return ;
                  }
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (signal) {
                              if (!state.ended) {
                                state.ended = true;
                                state.outerTalkback(signal);
                              }
                              state.innerTalkbacks.forEach((function (tb) {
                                      return tb(signal);
                                    }));
                              state.innerTalkbacks = new Array();
                              return ;
                            } else {
                              if (!state.outerPulled && !state.ended) {
                                state.outerPulled = true;
                                state.outerTalkback(/* Pull */0);
                              } else {
                                state.outerPulled = false;
                              }
                              state.innerTalkbacks.forEach((function (tb) {
                                      return tb(/* Pull */0);
                                    }));
                              return ;
                            }
                          })]));
        });
    });
}

function merge(sources) {
  return mergeMap((function (x) {
                  return x;
                }))(Wonka_sources.fromArray(sources));
}

function mergeAll(source) {
  return mergeMap((function (x) {
                  return x;
                }))(source);
}

function onEnd(f) {
  return (function (source) {
      return (function (sink) {
          var ended = {
            contents: false
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          if (!ended.contents) {
                            ended.contents = true;
                            sink(signal);
                            return f();
                          } else {
                            return ;
                          }
                        }
                        if (signal.tag) {
                          if (!ended.contents) {
                            return sink(signal);
                          } else {
                            return ;
                          }
                        }
                        var talkback = signal[0];
                        return sink(/* Start */Block.__(0, [(function (signal) {
                                          if (!ended.contents) {
                                            if (signal) {
                                              ended.contents = true;
                                              talkback(signal);
                                              return f();
                                            } else {
                                              return talkback(signal);
                                            }
                                          }
                                          
                                        })]));
                      }));
        });
    });
}

function onPush(f) {
  return (function (source) {
      return (function (sink) {
          var ended = {
            contents: false
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          if (!ended.contents) {
                            ended.contents = true;
                            sink(signal);
                          }
                          
                        } else if (signal.tag) {
                          if (!ended.contents) {
                            f(signal[0]);
                            sink(signal);
                          }
                          
                        } else {
                          var talkback = signal[0];
                          sink(/* Start */Block.__(0, [(function (signal) {
                                      if (!ended.contents) {
                                        if (signal) {
                                          ended.contents = true;
                                          return talkback(signal);
                                        } else {
                                          return talkback(signal);
                                        }
                                      }
                                      
                                    })]));
                        }
                        
                      }));
        });
    });
}

function onStart(f) {
  return (function (source) {
      return (function (sink) {
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          return sink(signal);
                        }
                        if (signal.tag) {
                          return sink(signal);
                        }
                        sink(signal);
                        return f();
                      }));
        });
    });
}

function sample(notifier) {
  return (function (source) {
      return (function (sink) {
          var state = {
            sourceTalkback: Wonka_helpers.talkbackPlaceholder,
            notifierTalkback: Wonka_helpers.talkbackPlaceholder,
            value: undefined,
            pulled: false,
            ended: false
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      state.notifierTalkback(/* Close */1);
                      return sink(/* End */0);
                    } else {
                      return ;
                    }
                  }
                  if (!signal.tag) {
                    state.sourceTalkback = signal[0];
                    return ;
                  }
                  state.value = Caml_option.some(signal[0]);
                  if (state.pulled) {
                    state.pulled = false;
                    return ;
                  } else {
                    state.pulled = true;
                    state.notifierTalkback(/* Pull */0);
                    return state.sourceTalkback(/* Pull */0);
                  }
                }));
          Curry._1(notifier, (function (signal) {
                  var match = state.value;
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      state.sourceTalkback(/* Close */1);
                      return sink(/* End */0);
                    } else {
                      return ;
                    }
                  } else if (signal.tag) {
                    if (match !== undefined && !state.ended) {
                      state.value = undefined;
                      return sink(/* Push */Block.__(1, [Caml_option.valFromOption(match)]));
                    } else {
                      return ;
                    }
                  } else {
                    state.notifierTalkback = signal[0];
                    return ;
                  }
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (!state.ended) {
                              if (signal) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                return state.notifierTalkback(/* Close */1);
                              } else if (!state.pulled) {
                                state.pulled = true;
                                state.sourceTalkback(/* Pull */0);
                                return state.notifierTalkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                            
                          })]));
        });
    });
}

function scan(f, seed) {
  return (function (source) {
      return (function (sink) {
          var acc = {
            contents: seed
          };
          return Curry._1(source, (function (signal) {
                        var tmp;
                        if (typeof signal === "number") {
                          tmp = /* End */0;
                        } else if (signal.tag) {
                          acc.contents = f(acc.contents, signal[0]);
                          tmp = /* Push */Block.__(1, [acc.contents]);
                        } else {
                          tmp = /* Start */Block.__(0, [signal[0]]);
                        }
                        return sink(tmp);
                      }));
        });
    });
}

function share(source) {
  var state = {
    sinks: new Array(),
    talkback: Wonka_helpers.talkbackPlaceholder,
    gotSignal: false
  };
  return (function (sink) {
      state.sinks = state.sinks.concat(sink);
      if (state.sinks.length === 1) {
        Curry._1(source, (function (signal) {
                if (typeof signal === "number") {
                  state.sinks.forEach((function (sink) {
                          return sink(/* End */0);
                        }));
                  state.sinks = new Array();
                  return ;
                }
                if (!signal.tag) {
                  state.talkback = signal[0];
                  return ;
                }
                state.gotSignal = false;
                state.sinks.forEach((function (sink) {
                        return sink(signal);
                      }));
                
              }));
      }
      return sink(/* Start */Block.__(0, [(function (signal) {
                        if (signal) {
                          state.sinks = state.sinks.filter((function (x) {
                                  return x !== sink;
                                }));
                          if (state.sinks.length === 0) {
                            return state.talkback(/* Close */1);
                          } else {
                            return ;
                          }
                        } else if (!state.gotSignal) {
                          state.gotSignal = true;
                          return state.talkback(signal);
                        } else {
                          return ;
                        }
                      })]));
    });
}

function skip(wait) {
  return (function (source) {
      return (function (sink) {
          var state = {
            talkback: Wonka_helpers.talkbackPlaceholder,
            rest: wait
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          return sink(signal);
                        }
                        if (signal.tag) {
                          if (state.rest > 0) {
                            state.rest = state.rest - 1 | 0;
                            return state.talkback(/* Pull */0);
                          } else {
                            return sink(signal);
                          }
                        }
                        state.talkback = signal[0];
                        return sink(signal);
                      }));
        });
    });
}

function skipUntil(notifier) {
  return (function (source) {
      return (function (sink) {
          var state = {
            sourceTalkback: Wonka_helpers.talkbackPlaceholder,
            notifierTalkback: Wonka_helpers.talkbackPlaceholder,
            skip: true,
            pulled: false,
            ended: false
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (state.skip) {
                      state.notifierTalkback(/* Close */1);
                    }
                    state.ended = true;
                    sink(/* End */0);
                  } else if (signal.tag) {
                    if (!state.skip && !state.ended) {
                      state.pulled = false;
                      sink(signal);
                    } else if (state.pulled) {
                      state.pulled = false;
                    } else {
                      state.pulled = true;
                      state.sourceTalkback(/* Pull */0);
                      state.notifierTalkback(/* Pull */0);
                    }
                  } else {
                    state.sourceTalkback = signal[0];
                    Curry._1(notifier, (function (signal) {
                            if (typeof signal === "number") {
                              if (state.skip) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                              }
                              
                            } else if (signal.tag) {
                              state.skip = false;
                              state.notifierTalkback(/* Close */1);
                            } else {
                              var innerTb = signal[0];
                              state.notifierTalkback = innerTb;
                              innerTb(/* Pull */0);
                            }
                            
                          }));
                  }
                  
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (!state.ended) {
                              if (signal) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                if (state.skip) {
                                  return state.notifierTalkback(/* Close */1);
                                } else {
                                  return ;
                                }
                              } else if (!state.pulled) {
                                state.pulled = true;
                                if (state.skip) {
                                  state.notifierTalkback(/* Pull */0);
                                }
                                return state.sourceTalkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                            
                          })]));
        });
    });
}

function skipWhile(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            talkback: Wonka_helpers.talkbackPlaceholder,
            skip: true
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          return sink(signal);
                        }
                        if (signal.tag) {
                          if (state.skip) {
                            if (f(signal[0])) {
                              return state.talkback(/* Pull */0);
                            } else {
                              state.skip = false;
                              return sink(signal);
                            }
                          } else {
                            return sink(signal);
                          }
                        }
                        state.talkback = signal[0];
                        return sink(signal);
                      }));
        });
    });
}

function switchMap(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            outerTalkback: Wonka_helpers.talkbackPlaceholder,
            outerPulled: false,
            innerTalkback: Wonka_helpers.talkbackPlaceholder,
            innerActive: false,
            innerPulled: false,
            ended: false
          };
          var applyInnerSource = function (innerSource) {
            state.innerActive = true;
            Curry._1(innerSource, (function (signal) {
                    if (!state.innerActive) {
                      return ;
                    }
                    if (typeof signal === "number") {
                      state.innerActive = false;
                      if (state.ended) {
                        return sink(signal);
                      } else if (!state.outerPulled) {
                        state.outerPulled = true;
                        return state.outerTalkback(/* Pull */0);
                      } else {
                        return ;
                      }
                    }
                    if (signal.tag) {
                      sink(signal);
                      if (state.innerPulled) {
                        state.innerPulled = false;
                        return ;
                      } else {
                        return state.innerTalkback(/* Pull */0);
                      }
                    }
                    var tb = signal[0];
                    state.innerTalkback = tb;
                    state.innerPulled = false;
                    return tb(/* Pull */0);
                  }));
            
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      if (!state.innerActive) {
                        sink(/* End */0);
                      }
                      
                    }
                    
                  } else if (signal.tag) {
                    if (!state.ended) {
                      if (state.innerActive) {
                        state.innerTalkback(/* Close */1);
                        state.innerTalkback = Wonka_helpers.talkbackPlaceholder;
                      }
                      if (state.outerPulled) {
                        state.outerPulled = false;
                      } else {
                        state.outerPulled = true;
                        state.outerTalkback(/* Pull */0);
                      }
                      applyInnerSource(f(signal[0]));
                    }
                    
                  } else {
                    state.outerTalkback = signal[0];
                  }
                  
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (signal) {
                              if (!state.ended) {
                                state.ended = true;
                                state.outerTalkback(/* Close */1);
                              }
                              if (state.innerActive) {
                                state.innerActive = false;
                                return state.innerTalkback(/* Close */1);
                              } else {
                                return ;
                              }
                            } else {
                              if (!state.ended && !state.outerPulled) {
                                state.outerPulled = true;
                                state.outerTalkback(/* Pull */0);
                              }
                              if (state.innerActive && !state.innerPulled) {
                                state.innerPulled = true;
                                return state.innerTalkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                          })]));
        });
    });
}

function switchAll(source) {
  return switchMap((function (x) {
                  return x;
                }))(source);
}

function take(max) {
  return (function (source) {
      return (function (sink) {
          var state = {
            ended: false,
            taken: 0,
            talkback: Wonka_helpers.talkbackPlaceholder
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      return sink(/* End */0);
                    } else {
                      return ;
                    }
                  }
                  if (signal.tag) {
                    if (state.taken < max && !state.ended) {
                      state.taken = state.taken + 1 | 0;
                      sink(signal);
                      if (!state.ended && state.taken >= max) {
                        state.ended = true;
                        sink(/* End */0);
                        return state.talkback(/* Close */1);
                      } else {
                        return ;
                      }
                    } else {
                      return ;
                    }
                  }
                  var tb = signal[0];
                  if (max <= 0) {
                    state.ended = true;
                    sink(/* End */0);
                    return tb(/* Close */1);
                  } else {
                    state.talkback = tb;
                    return ;
                  }
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (!state.ended) {
                              if (signal) {
                                state.ended = true;
                                return state.talkback(/* Close */1);
                              } else if (state.taken < max) {
                                return state.talkback(/* Pull */0);
                              } else {
                                return ;
                              }
                            }
                            
                          })]));
        });
    });
}

function takeLast(max) {
  return (function (source) {
      return (function (sink) {
          var state = {
            queue: new Array(),
            talkback: Wonka_helpers.talkbackPlaceholder
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          Wonka_sources.fromArray(state.queue)(sink);
                        } else if (signal.tag) {
                          var size = state.queue.length;
                          if (size >= max && max > 0) {
                            state.queue.shift();
                          }
                          state.queue.push(signal[0]);
                          state.talkback(/* Pull */0);
                        } else {
                          var talkback = signal[0];
                          if (max <= 0) {
                            talkback(/* Close */1);
                            Wonka_sources.empty(sink);
                          } else {
                            state.talkback = talkback;
                            talkback(/* Pull */0);
                          }
                        }
                        
                      }));
        });
    });
}

function takeUntil(notifier) {
  return (function (source) {
      return (function (sink) {
          var state = {
            ended: false,
            sourceTalkback: Wonka_helpers.talkbackPlaceholder,
            notifierTalkback: Wonka_helpers.talkbackPlaceholder
          };
          Curry._1(source, (function (signal) {
                  if (typeof signal === "number") {
                    if (!state.ended) {
                      state.ended = true;
                      state.notifierTalkback(/* Close */1);
                      sink(/* End */0);
                    }
                    
                  } else if (signal.tag) {
                    if (!state.ended) {
                      sink(signal);
                    }
                    
                  } else {
                    state.sourceTalkback = signal[0];
                    Curry._1(notifier, (function (signal) {
                            if (typeof signal !== "number") {
                              if (signal.tag) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                sink(/* End */0);
                              } else {
                                var innerTb = signal[0];
                                state.notifierTalkback = innerTb;
                                innerTb(/* Pull */0);
                              }
                            }
                            
                          }));
                  }
                  
                }));
          return sink(/* Start */Block.__(0, [(function (signal) {
                            if (!state.ended) {
                              if (signal) {
                                state.ended = true;
                                state.sourceTalkback(/* Close */1);
                                return state.notifierTalkback(/* Close */1);
                              } else {
                                return state.sourceTalkback(/* Pull */0);
                              }
                            }
                            
                          })]));
        });
    });
}

function takeWhile(f) {
  return (function (source) {
      return (function (sink) {
          var state = {
            talkback: Wonka_helpers.talkbackPlaceholder,
            ended: false
          };
          return Curry._1(source, (function (signal) {
                        if (typeof signal === "number") {
                          if (!state.ended) {
                            state.ended = true;
                            return sink(/* End */0);
                          } else {
                            return ;
                          }
                        }
                        if (signal.tag) {
                          if (!state.ended) {
                            if (f(signal[0])) {
                              return sink(signal);
                            } else {
                              state.ended = true;
                              sink(/* End */0);
                              return state.talkback(/* Close */1);
                            }
                          } else {
                            return ;
                          }
                        }
                        state.talkback = signal[0];
                        return sink(signal);
                      }));
        });
    });
}

var flatten = mergeAll;

var tap = onPush;

export {
  buffer ,
  combine ,
  concatMap ,
  concatAll ,
  concat ,
  filter ,
  map ,
  mergeMap ,
  merge ,
  mergeAll ,
  flatten ,
  onEnd ,
  onPush ,
  tap ,
  onStart ,
  sample ,
  scan ,
  share ,
  skip ,
  skipUntil ,
  skipWhile ,
  switchMap ,
  switchAll ,
  take ,
  takeLast ,
  takeUntil ,
  takeWhile ,
  
}
/* No side effect */
