import { patch, unpatch } from './patch';
import { ConfigManagerCertPassphrase } from '../../src/services/config-manager-cert-passphrase';
import 'jest-extended';

describe('ConfigManagerCertPassphrase.readPassphrase', () => {
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

  it('should get an error if there is no cert phrase', async () => {
    ConfigManagerCertPassphrase.readPassphrase();
    expect(witnessFailure).toEqual(true);
  });

  it('should get the cert phrase from the process args', async () => {
    const passphrase = 'args_passphrase';
    process.argv.push(`--passphrase=${passphrase}`);
    const certPhrase = ConfigManagerCertPassphrase.readPassphrase();
    expect(certPhrase).toEqual(passphrase);
    process.argv.pop();
  });

  it('should get the cert phrase from an env variable', async () => {
    const passphrase = 'env_var_passphrase';
    process.env['GATEWAY_PASSPHRASE'] = passphrase;
    const certPhrase = ConfigManagerCertPassphrase.readPassphrase();
    expect(certPhrase).toEqual(passphrase);
    delete process.env['GATEWAY_PASSPHRASE'];
  });
});
