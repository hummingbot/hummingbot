"use strict";

exports.__esModule = true;
exports.themesReducer = void 0;

const themesReducer = (state = {}, action) => {
  switch (action.type) {
    case `SET_RESOLVED_THEMES`:
      return { ...state,
        themes: action.payload
      };

    default:
      return state;
  }
};

exports.themesReducer = themesReducer;
//# sourceMappingURL=themes.js.map