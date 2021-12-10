import * as utils from '../config-manager-v2';

/*
 * This file defines migration functions for each version.
 * Note: type utils.Migration = (configRootFullPath: string,
 *                         configRootTemplateFullPath: string) => void;
 */

export const updateToVersion1: utils.Migration = (
  configRootFullPath,
  configRootTemplateFullPath
) => {
  // just dummy calls
  configRootFullPath;
  configRootTemplateFullPath;
  return;
};
