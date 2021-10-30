import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';

type Configuration = { [key: string]: any };
type ConfigurationRoot = { [namespaceId: string]: string };

class ConfigurationNamespace {
  readonly #namespaceId: string;
  readonly #filePath: string;
  #configuration: Configuration;

  constructor(id: string, filePath: string) {
    this.#namespaceId = id;
    this.#filePath = filePath;
    this.#configuration = {};
    if (fs.existsSync(filePath)) {
      this.loadConfig();
    }
  }

  get id(): string {
    return this.#namespaceId;
  }

  get filePath(): string {
    return this.#filePath;
  }

  loadConfig() {
    this.#configuration = yaml.load(
      fs.readFileSync(this.#filePath, 'utf8')
    ) as Configuration;
  }

  saveConfig() {
    fs.writeFileSync(this.#filePath, yaml.dump(this.#configuration));
  }

  get(configPath: string): any {
    const pathComponents: Array<string> = configPath.split('.');
    let cursor: Configuration | any = this.#configuration;

    pathComponents.forEach((component: string) => {
      cursor = cursor[component];
      if (cursor === undefined) {
        return cursor;
      }
    });

    return cursor;
  }

  set(configPath: string, value: any): void {
    const pathComponents: Array<string> = configPath.split('.');
    let cursor: Configuration | any = this.#configuration;
    let parent: Configuration = this.#configuration;

    pathComponents.slice(0, -1).forEach((component: string) => {
      parent = cursor;
      cursor = cursor[component];
      if (cursor === undefined) {
        parent[component] = {};
        cursor = parent[component];
      }
    });

    const lastComponent: string = pathComponents[pathComponents.length - 1];
    cursor[lastComponent] = value;

    this.saveConfig();
  }
}

interface UnpackedConfigNamespace {
  namespace: ConfigurationNamespace;
  configPath: string;
}

export class ConfigManagerV2 {
  readonly #namespaces: { [key: string]: ConfigurationNamespace };

  constructor(configRootPath: string) {
    this.#namespaces = {};
    this.loadConfigRoot(configRootPath);
  }

  getNamespace(id: string): ConfigurationNamespace | undefined {
    return this.#namespaces[id];
  }

  addNamespace(id: string, filePath: string): void {
    this.#namespaces[id] = new ConfigurationNamespace(id, filePath);
  }

  unpackFullConfigPath(fullConfigPath: string): UnpackedConfigNamespace {
    const pathComponents: Array<string> = fullConfigPath.split('.');
    if (pathComponents.length < 2) {
      throw new Error('Configuration paths must have at least two components.');
    }

    const namespaceComponent: string = pathComponents[0];
    const namespace: ConfigurationNamespace | undefined =
      this.#namespaces[namespaceComponent];
    if (namespace === undefined) {
      throw new Error(
        `The configuration namespace ${namespaceComponent} does not exist.`
      );
    }

    const configPath: string = pathComponents.slice(1).join('.');
    return {
      namespace,
      configPath,
    };
  }

  get(fullConfigPath: string) {
    const { namespace, configPath } = this.unpackFullConfigPath(fullConfigPath);
    return namespace.get(configPath);
  }

  set(fullConfigPath: string, value: any) {
    const { namespace, configPath } = this.unpackFullConfigPath(fullConfigPath);
    namespace.set(configPath, value);
  }

  loadConfigRoot(configRootPath: string) {
    // Load the config root file.
    const configRootFullPath: string = fs.realpathSync(configRootPath);
    const configRootDir: string = path.dirname(configRootFullPath);
    const configRoot: ConfigurationRoot = yaml.load(
      fs.readFileSync(configRootFullPath, 'utf8')
    ) as ConfigurationRoot;

    // Rebase the file paths in config root if they're relative paths.
    for (const [namespaceId, filePath] of Object.entries(configRoot)) {
      if (filePath.charAt(0) !== '/') {
        configRoot[namespaceId] = path.join(configRootDir, filePath);
      }
    }

    // Add the namespaces according to config root.
    for (const [namespaceId, filePath] of Object.entries(configRoot)) {
      this.addNamespace(namespaceId, filePath);
    }
  }
}
