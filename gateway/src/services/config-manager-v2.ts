import fs from 'fs';
import yaml from 'js-yaml';

type Configuration = { [key: string]: any };

class ConfigurationNamespace {
  namespaceId: string;
  filePath: string;
  configuration: Configuration;

  constructor(id: string, filePath: string) {
    this.namespaceId = id;
    this.filePath = filePath;
    this.configuration = {};
  }

  loadConfig() {
    this.configuration = yaml.load(
      fs.readFileSync(this.filePath, 'utf8')
    ) as Configuration;
  }

  saveConfig() {
    fs.writeFileSync(this.filePath, yaml.dump(this.configuration));
  }

  /*
  get(configPath: string): any {
    const pathComponents: Array<string> = configPath.split('.');
    let cursor: Configuration | any = this.configuration;
  }

  set(configPath: string, value: any): void {
  }
   */
}

export class ConfigManagerV2 {
  namespaces: { [key: string]: ConfigurationNamespace };

  constructor() {
    this.namespaces = {};
  }

  /*
  get(configPath: string) {
  }

  set(configPath: string, value: any) {
  }

  loadConfigRoot() {
  }
   */
}
