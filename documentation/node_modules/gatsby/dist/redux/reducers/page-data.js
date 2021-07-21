"use strict";

exports.__esModule = true;
exports.pageDataReducer = void 0;

const pageDataReducer = (state = new Map(), action) => {
  switch (action.type) {
    case `DELETE_CACHE`:
      return new Map();

    case `REMOVE_PAGE_DATA`:
      state.delete(action.payload.id);
      return state;

    case `SET_PAGE_DATA`:
      {
        return state.set(action.payload.id, action.payload.resultHash);
      }

    default:
      return state;
  }
};

exports.pageDataReducer = pageDataReducer;
//# sourceMappingURL=page-data.js.map