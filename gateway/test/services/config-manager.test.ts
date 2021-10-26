import fs from 'fs';
import { ConfigManager } from '../../src/services/config-manager';
import 'jest-extended';
import yaml from 'js-yaml';

test('validateConfig', () => {
  expect(
    ConfigManager.validateConfig(
      yaml.load(fs.readFileSync('conf/gateway-config-example.yml', 'utf8'))
    )
  ).toEqual(true);
});

describe('Test passphrase reader', () => {
  const passphraseFile = 'conf/gateway-passphrase.yml';
  const passExists = fs.existsSync(passphraseFile);
  beforeAll(() => {
    // backup passphrase file if it exits
    if (passExists) {
      fs.copyFileSync(passphraseFile, passphraseFile + '.backup');
      fs.rmSync(passphraseFile, { force: true });
    }
  });

  afterAll(() => {
    // restore original passphrase file
    if (passExists) {
      fs.copyFileSync(passphraseFile + '.backup', passphraseFile);
      fs.rmSync(passphraseFile + '.backup', { force: true });
    }
  });

  it('returns correct passphrase with right permision', () => {
    fs.writeFileSync(passphraseFile, "CERT_PASSPHRASE: 'TEST'", {
      mode: 0o600,
    });
    expect(ConfigManager.readPassphrase()).toEqual('TEST');
    fs.rmSync(passphraseFile, { force: true });
  });

  it('throws error with right permision', () => {
    fs.writeFileSync(passphraseFile, "CERT_PASSPHRASE: 'TEST'", {
      mode: 0o660,
    });
    expect(() => {
      ConfigManager.readPassphrase();
    }).toThrowError();
    fs.rmSync(passphraseFile, { force: true });
  });
});
