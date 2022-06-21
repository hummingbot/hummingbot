import { DBPathOverride } from './config.util';

module.exports = (_globalConfig: any, _projectConfig: any) => {
  // override db paths
  DBPathOverride.init();
  DBPathOverride.updateConfigs();
};
