"use strict";

exports.__esModule = true;
exports.removeStaleJobs = void 0;

var _jobsManager = require("../utils/jobs-manager");

var _actions = require("../redux/actions");

const removeStaleJobs = state => {
  const actions = []; // If any of our finished jobs are stale we remove them to keep our cache small

  state.jobsV2.complete.forEach((job, contentDigest) => {
    if ((0, _jobsManager.isJobStale)(job)) {
      actions.push(_actions.internalActions.removeStaleJob(contentDigest));
    }
  }); // If any of our pending jobs do not have an existing inputPath or the inputPath changed
  // we remove it from the queue as they would fail anyway

  state.jobsV2.incomplete.forEach(({
    job,
    plugin
  }) => {
    if ((0, _jobsManager.isJobStale)(job)) {
      actions.push(_actions.internalActions.removeStaleJob(job.contentDigest));
    } else {
      actions.push(_actions.publicActions.createJobV2(job, plugin));
    }
  });
  return actions;
};

exports.removeStaleJobs = removeStaleJobs;
//# sourceMappingURL=remove-stale-jobs.js.map