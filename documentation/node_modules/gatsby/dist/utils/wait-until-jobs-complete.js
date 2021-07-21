"use strict";

exports.__esModule = true;
exports.waitUntilAllJobsComplete = void 0;

var _redux = require("../redux");

var _jobsManager = require("./jobs-manager");

const waitUntilAllJobsComplete = () => {
  const jobsV1Promise = new Promise(resolve => {
    const onEndJob = () => {
      if (_redux.store.getState().jobs.active.length === 0) {
        resolve();

        _redux.emitter.off(`END_JOB`, onEndJob);
      }
    };

    _redux.emitter.on(`END_JOB`, onEndJob);

    onEndJob();
  });
  return Promise.all([jobsV1Promise, (0, _jobsManager.waitUntilAllJobsComplete)()]);
};

exports.waitUntilAllJobsComplete = waitUntilAllJobsComplete;
//# sourceMappingURL=wait-until-jobs-complete.js.map