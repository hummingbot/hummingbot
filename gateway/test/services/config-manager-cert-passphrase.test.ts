import { patch, unpatch } from './patch';
import fs from 'fs';
import { ConfigManagerCertPassphrase } from '../../src/services/config-manager-cert-passphrase';
import 'jest-extended';

describe('ConfigManagerCertPassphrase.readPassphrase', () => {
  const passphraseFile = 'conf/gateway-passphrase.yml';
  const passExists = fs.existsSync(passphraseFile);
  let witnessFailure = false;

  afterEach(() => {
    unpatch();
    witnessFailure = false;
  });

  beforeEach(() => {
    patch(ConfigManagerCertPassphrase.bindings, '_exit', () => {
      witnessFailure = true;
    });
  });

  const backupAndRemove = () => {
    // backup passphrase file if it exits
    if (passExists) {
      fs.copyFileSync(passphraseFile, passphraseFile + '.backup');
      fs.rmSync(passphraseFile, { force: true });
    }
  };

  beforeAll(() => {
    backupAndRemove();
  });

  const restore = () => {
    // restore original passphrase file
    if (passExists) {
      fs.copyFileSync(passphraseFile + '.backup', passphraseFile);
      fs.rmSync(passphraseFile + '.backup', { force: true });
    }
  };

  afterAll(() => {
    restore();
  });

  it('returns correct passphrase with right permision', () => {
    fs.writeFileSync(passphraseFile, "CERT_PASSPHRASE: 'TEST'", {
      mode: 0o600,
    });
    expect(ConfigManagerCertPassphrase.readPassphrase()).toEqual('TEST');
    fs.rmSync(passphraseFile, { force: true });
  });

  it('fails if the file contents are incorrect', () => {
    fs.rmSync(passphraseFile, { force: true });

    fs.writeFileSync(passphraseFile, "PASSPHRASE: 'TEST'", {
      mode: 0o600,
    });
    ConfigManagerCertPassphrase.readPassphrase();
    expect(witnessFailure).toEqual(true);
  });

  it('fails without the right permision', () => {
    fs.rmSync(passphraseFile, { force: true });
    fs.writeFileSync(passphraseFile, "CERT_PASSPHRASE: 'TEST'", {
      mode: 0o660,
    });
    ConfigManagerCertPassphrase.readPassphrase();
    expect(witnessFailure).toEqual(true);
    fs.rmSync(passphraseFile, { force: true });
  });

  it('fails if the file does not exist', () => {
    fs.rmSync(passphraseFile, { force: true });

    ConfigManagerCertPassphrase.readPassphrase();
    expect(witnessFailure).toEqual(true);
  });
});
