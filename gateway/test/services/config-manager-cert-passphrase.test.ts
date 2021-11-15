import fs from 'fs';
import { ConfigManagerCertPassphrase } from '../../src/services/config-manager-cert-passphrase';
import 'jest-extended';

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
    expect(ConfigManagerCertPassphrase.readPassphrase()).toEqual('TEST');
    fs.rmSync(passphraseFile, { force: true });
  });
});
