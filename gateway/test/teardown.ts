import { DBPathOverride } from './config.util';

export default (_globalConfig: any, _projectConfig: any) => {
  // revert change to db paths
  DBPathOverride.resetConfigs();
};
