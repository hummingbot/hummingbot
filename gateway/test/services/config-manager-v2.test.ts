import fsp from 'fs/promises';
import fse from 'fs-extra';
import os from 'os';
import path from 'path';
import {
  ConfigManagerV2,
  ConfigurationNamespace,
} from '../../src/services/config-manager-v2';

describe('Configuration manager v2 tests', () => {
  const testDataSourcePath: string = fse.realpathSync(
    path.join(__dirname, 'data/config-manager-v2')
  );
  let tempDirPath: string = '';
  let configManager: ConfigManagerV2;

  beforeEach(async () => {
    // Create a temp dir.
    tempDirPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), 'config-manager-v2-unit-test')
    );

    // Copy the test data into a temp dir.
    await fse.copy(testDataSourcePath, tempDirPath);

    // Create a valid configuration manager from the temp dir.
    configManager = new ConfigManagerV2(
      path.join(tempDirPath, 'test1/root.yml')
    );
  });

  afterEach(async () => {
    // Delete the temp dir.
    await fse.remove(tempDirPath);
    tempDirPath = '';

    // Delete any default configs.
    ConfigManagerV2.setDefaults('ethereum', {});
  });

  it('loading a valid configuration root', (done) => {
    expect(configManager.get('ssl.caCertificatePath')).toBeDefined();
    expect(configManager.get('ethereum.networks')).toBeDefined();
    done();
  });

  it('loading an invalid configuration root', (done) => {
    expect(() => {
      new ConfigManagerV2(path.join(tempDirPath, 'test1/invalid-root.yml'));
    }).toThrow();
    expect(() => {
      new ConfigManagerV2(path.join(tempDirPath, 'test1/invalid-root-3.yml'));
    }).toThrow();
    done();
  });

  it('loading an invalid config file', (done) => {
    expect(() => {
      new ConfigManagerV2(path.join(tempDirPath, 'test1/invalid-root-2.yml'));
    }).toThrow();
    done();
  });

  it('reading from config file', (done) => {
    expect(configManager.get('ssl.keyPath')).toEqual('gateway.key');
    expect(configManager.get('ssl.passPhrasePath')).toEqual('gateway.passwd');
    expect(configManager.get('ethereum.networks.kovan.chainID')).toEqual(42);
    expect(
      configManager.get('ethereum.networks.bsc.nativeCurrencySymbol')
    ).toEqual('BNB');
    done();
  });

  it('reading a non-existent config entry', (done) => {
    expect(configManager.get('ethereum.kovan.chainID')).toBeUndefined();
    expect(configManager.get('ssl.keyPath.keyPath')).toBeUndefined();
    done();
  });

  it('reading invalid config keys', (done) => {
    expect(() => {
      configManager.get('ssl');
    }).toThrow();
    done();
    expect(() => {
      configManager.get('noSuchNamespace.networks');
    }).toThrow();
  });

  it('writing a valid configuration', (done) => {
    const newKeyPath: string = 'new-gateway.key';
    configManager.set('ssl.keyPath', newKeyPath);
    configManager.set('ethereum.networks.bsc.chainID', 970);
    configManager.set('ethereum.networks.etc', {
      chainID: 61,
      nodeURL: 'http://localhost:8561',
    });
    expect(configManager.get('ssl.keyPath')).toEqual(newKeyPath);

    const verifyConfigManager: ConfigManagerV2 = new ConfigManagerV2(
      path.join(tempDirPath, 'test1/root.yml')
    );
    expect(verifyConfigManager.get('ssl.keyPath')).toEqual(newKeyPath);
    expect(verifyConfigManager.get('ethereum.networks.bsc.chainID')).toEqual(
      970
    );
    expect(verifyConfigManager.get('ethereum.networks.etc.chainID')).toEqual(
      61
    );
    done();
  });

  it('writing an invalid configuration', (done) => {
    expect(() => {
      configManager.set('ssl.nonKeyPath', 'noSuchFile.txt');
    }).toThrow();
    expect(() => {
      configManager.set('ethereum', {});
    }).toThrow();
    done();
  });

  it('using default configurations', (done) => {
    ConfigManagerV2.setDefaults('ethereum', {
      networks: {
        rinkeby: {
          chainID: 4,
          nodeURL: 'http://localhost:8504',
        },
      },
    });
    expect(configManager.get('ethereum.networks.rinkeby.chainID')).toEqual(4);
    done();
  });

  it('getting namespace objects', (done) => {
    const sslNamespace: ConfigurationNamespace = configManager.getNamespace(
      'ssl'
    ) as ConfigurationNamespace;
    expect(sslNamespace.schemaPath).toEqual(
      path.join(tempDirPath, 'test1/schema-ssl.json')
    );
    expect(sslNamespace.configurationPath).toEqual(
      path.join(tempDirPath, 'test1/ssl.yml')
    );
    done();
  });
});

describe('Sample configurations', () => {
  it('Read sample schemas', (done) => {
    const sampleConfigManager = new ConfigManagerV2(
      './conf/templates/root.yml'
    );
    expect(sampleConfigManager.get('ssl.caCertificatePath')).toBeDefined();
    done();
  });
});
