import Ajv from 'ajv';
import { ValidateFunction } from 'ajv';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';

type Configuration = { [key: string]: any };
type ConfigurationDefaults = { [namespaceId: string]: Configuration };
interface _ConfigurationNamespaceDefinition {
  configurationPath: string;
  schemaPath: string;
}
type ConfigurationNamespaceDefinition = _ConfigurationNamespaceDefinition & {
  [key: string]: string;
};
type ConfigurationRoot = {
  [namespaceId: string]: ConfigurationNamespaceDefinition;
};
const NamespaceTag: string = '$namespace ';
const ConfigRootSchemaPath: string = path.join(
  __dirname,
  'schema/configuration-root-schema.json'
);
interface UnpackedConfigNamespace {
  namespace: ConfigurationNamespace;
  configPath: string;
}

const ajv: Ajv = new Ajv();

export class ConfigurationNamespace {
  /**
   * This class encapsulates a namespace under the configuration tree.
   * A namespace represents the top-level component of a configuration path.
   * e.g. if the config path is "ssl.certificatePath", then "ssl" is the
   * namespace.
   *
   * Each namespace contains a JSON schema and a YAML configuration file.
   *
   * The JSON schema specifies the properties and data types allowed within the
   * namespace. e.g. you may specify that the "ssl" namespace has a few
   * mandatory properties dealing with certificates and private keys. This means
   * any missing properties or any properties outsides of the JSON schema would
   * cause a failure to initialize the namespace, and also cannot be set into
   * the namespace.
   *
   * The YAML configuration file is where the actual configuration tree goes
   * to. It is automatically validated against the JSON schema at namespace
   * initiation. It is automatically saved to and validated against JSON schema
   * again at every set() call.
   *
   * Note that configuration paths may have multiple levels. What it implies
   * is those configurations are stored in nested dictionaries - aka. a tree.
   * e.g. if the config path is "ethereum.networks.kovan.networkID", then,
   * what it means you're accessing ["networks"]["kovan"]["networkID"] under
   * the "ethereum" namespace.
   */
  readonly #namespaceId: string;
  readonly #schemaPath: string;
  readonly #configurationPath: string;
  readonly #validator: ValidateFunction;
  #configuration: Configuration;

  constructor(id: string, schemaPath: string, configurationPath: string) {
    this.#namespaceId = id;
    this.#schemaPath = schemaPath;
    this.#configurationPath = configurationPath;
    this.#configuration = {};
    if (!fs.existsSync(schemaPath)) {
      throw new Error(
        `The JSON schema for namespace ${id} (${schemaPath}) does not exist.`
      );
    }

    this.#validator = ajv.compile(
      JSON.parse(fs.readFileSync(schemaPath).toString())
    );

    if (fs.existsSync(configurationPath)) {
      this.loadConfig();
    }
  }

  get id(): string {
    return this.#namespaceId;
  }

  get schemaPath(): string {
    return this.#schemaPath;
  }

  get configurationPath(): string {
    return this.#configurationPath;
  }

  loadConfig() {
    const configCandidate: Configuration = yaml.load(
      fs.readFileSync(this.#configurationPath, 'utf8')
    ) as Configuration;
    if (!this.#validator(configCandidate)) {
      throw new Error(`Invalid configuration for namespace ${this.id}.`);
    }
    this.#configuration = configCandidate;
  }

  saveConfig() {
    fs.writeFileSync(this.#configurationPath, yaml.dump(this.#configuration));
  }

  get(configPath: string): any {
    const pathComponents: Array<string> = configPath.split('.');
    let cursor: Configuration | any = this.#configuration;

    for (const component of pathComponents) {
      cursor = cursor[component];
      if (cursor === undefined) {
        return cursor;
      }
    }

    return cursor;
  }

  set(configPath: string, value: any): void {
    const pathComponents: Array<string> = configPath.split('.');
    const configClone: Configuration = JSON.parse(
      JSON.stringify(this.#configuration)
    );
    let cursor: Configuration | any = configClone;
    let parent: Configuration = configClone;

    for (const component of pathComponents.slice(0, -1)) {
      parent = cursor;
      cursor = cursor[component];
      if (cursor === undefined) {
        parent[component] = {};
        cursor = parent[component];
      }
    }

    const lastComponent: string = pathComponents[pathComponents.length - 1];
    cursor[lastComponent] = value;

    if (!this.#validator(configClone)) {
      throw new Error(
        `Cannot set ${this.id}.${configPath} to ${value}: ` +
          'JSON schema violation.'
      );
    }

    this.#configuration = configClone;
    this.saveConfig();
  }
}

export class ConfigManagerV2 {
  /**
   * This class encapsulates the configuration tree and all the contained
   * namespaces and files for Hummingbot Gateway. It also contains a defaults
   * mechanism for modules to set default configurations under their namespaces.
   *
   * The configuration manager starts by loading the root configuration file,
   * which defines all the configuration namespaces. The root configuration file
   * has a fixed JSON schema, that only allows namespaces to be defined there.
   *
   * After the namespaces are loaded into the configuration manager during
   * initiation, the get() and set() functions will map configuration keys and
   * values to the appropriate namespaces.
   *
   * e.g. get('ethereum.networks.kovan.networkID') will be mapped to
   *      ethereumNamespace.get('networks.kovan.networkID')
   * e.g. set('ethereum.networks.kovan.networkID', 42) will be mapped to
   *      ethereumNamespace.set('networks.kovan.networkID', 42)
   *
   * File paths in the root configuration file may be defined as absolute paths
   * or relative paths. Any relative paths would be rebased to the root
   * configuration file's parent directory.
   *
   * The static function `setDefaults()` is expected to be called by gateway
   * modules, to set default configurations under their own namespaces. Default
   * configurations are used in the `get()` function if the corresponding config
   * key is not found in its configuration namespace.
   */
  readonly #namespaces: { [key: string]: ConfigurationNamespace };

  private static _instance: ConfigManagerV2;

  public static getInstance(): ConfigManagerV2 {
    if (!ConfigManagerV2._instance) {
      ConfigManagerV2._instance = new ConfigManagerV2(
        './conf/samples/root.yml'
      );
    }

    return ConfigManagerV2._instance;
  }

  static defaults: ConfigurationDefaults = {};

  constructor(configRootPath: string) {
    this.#namespaces = {};
    this.loadConfigRoot(configRootPath);
  }

  static setDefaults(namespaceId: string, defaultTree: Configuration) {
    ConfigManagerV2.defaults[namespaceId] = defaultTree;
  }

  static getFromDefaults(namespaceId: string, configPath: string): any {
    if (!(namespaceId in ConfigManagerV2.defaults)) {
      return undefined;
    }

    const pathComponents: Array<string> = configPath.split('.');
    const defaultConfig: Configuration = ConfigManagerV2.defaults[namespaceId];
    let cursor: Configuration | any = defaultConfig;
    for (const pathComponent of pathComponents) {
      cursor = cursor[pathComponent];
      if (cursor === undefined) {
        return cursor;
      }
    }

    return cursor;
  }

  getNamespace(id: string): ConfigurationNamespace | undefined {
    return this.#namespaces[id];
  }

  addNamespace(
    id: string,
    schemaPath: string,
    configurationPath: string
  ): void {
    this.#namespaces[id] = new ConfigurationNamespace(
      id,
      schemaPath,
      configurationPath
    );
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

  get(fullConfigPath: string): any {
    const { namespace, configPath } = this.unpackFullConfigPath(fullConfigPath);
    const configValue: any = namespace.get(configPath);
    if (configValue === undefined) {
      return ConfigManagerV2.getFromDefaults(namespace.id, configPath);
    }
    return configValue;
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

    // Validate the config root file.
    const validator: ValidateFunction = ajv.compile(
      JSON.parse(fs.readFileSync(ConfigRootSchemaPath).toString())
    );
    if (!validator(configRoot)) {
      throw new Error('Configuration root file is invalid.');
    }

    // Extract the namespace ids.
    const namespaceMap: ConfigurationRoot = {};
    for (const namespaceKey of Object.keys(configRoot)) {
      namespaceMap[namespaceKey.slice(NamespaceTag.length)] =
        configRoot[namespaceKey];
    }

    // Rebase the file paths in config root if they're relative paths.
    for (const namespaceDefinition of Object.values(namespaceMap)) {
      for (const [key, filePath] of Object.entries(namespaceDefinition)) {
        if (filePath.charAt(0) !== '/') {
          namespaceDefinition[key] = path.join(configRootDir, filePath);
        }
      }
    }

    // Add the namespaces according to config root.
    for (const [namespaceId, namespaceDefinition] of Object.entries(
      namespaceMap
    )) {
      this.addNamespace(
        namespaceId,
        namespaceDefinition.schemaPath,
        namespaceDefinition.configurationPath
      );
    }
  }
}
