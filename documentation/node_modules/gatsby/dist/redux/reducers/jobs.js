"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.jobsReducer = void 0;

var _lodash = _interopRequireDefault(require("lodash"));

var _commonTags = require("common-tags");

var _moment = _interopRequireDefault(require("moment"));

const jobsReducer = (state = {
  active: [],
  done: []
}, action) => {
  switch (action.type) {
    case `CREATE_JOB`:
    case `SET_JOB`:
      {
        if (!action.payload.id) {
          throw new Error(`An ID must be provided when creating or setting job`);
        }

        const index = _lodash.default.findIndex(state.active, j => j.id === action.payload.id);

        if (index !== -1) {
          const mergedJob = _lodash.default.merge(state.active[index], { ...action.payload,
            createdAt: Date.now(),
            plugin: action.plugin
          });

          state.active[index] = mergedJob;
          return state;
        } else {
          state.active.push({ ...action.payload,
            createdAt: Date.now(),
            plugin: action.plugin
          });
          return state;
        }
      }

    case `END_JOB`:
      {
        if (!action.payload.id) {
          throw new Error(`An ID must be provided when ending a job`);
        }

        const completedAt = Date.now();

        const index = _lodash.default.findIndex(state.active, j => j.id === action.payload.id);

        if (index === -1) {
          throw new Error((0, _commonTags.oneLine)`
          The plugin "${_lodash.default.get(action, `plugin.name`, `anonymous`)}"
          tried to end a job with the id "${action.payload.id}"
          that either hasn't yet been created or has already been ended`);
        }

        const job = state.active.splice(index, 1)[0];
        state.done.push({ ...job,
          completedAt,
          runTime: (0, _moment.default)(completedAt).diff((0, _moment.default)(job.createdAt))
        });
        return state;
      }
  }

  return state;
};

exports.jobsReducer = jobsReducer;
//# sourceMappingURL=jobs.js.map