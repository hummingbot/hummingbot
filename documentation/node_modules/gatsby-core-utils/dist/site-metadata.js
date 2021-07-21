"use strict";

exports.__esModule = true;
exports.getSiteMetadata = getSiteMetadata;
exports.updateSiteMetadata = updateSiteMetadata;

var _serviceLock = require("./service-lock");

async function getSiteMetadata(sitePath) {
  return (0, _serviceLock.getService)(sitePath, `metadata`, true);
}

async function updateSiteMetadata(metadata, merge = true) {
  if (merge) {
    const oldMetadata = await getSiteMetadata(metadata.sitePath);

    if (oldMetadata) {
      metadata = { ...oldMetadata,
        ...metadata
      };
    }
  }

  return (0, _serviceLock.createServiceLock)(metadata.sitePath, `metadata`, metadata).then(unlock => unlock === null || unlock === void 0 ? void 0 : unlock());
}