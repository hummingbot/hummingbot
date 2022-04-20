import { Application } from 'express';
import fs from 'fs';
import https from 'https';
import { ConfigManagerCertPassphrase } from './services/config-manager-cert-passphrase';
import { ConfigManagerV2 } from './services/config-manager-v2';

export const addHttps = (app: Application) => {
  const serverKey = fs.readFileSync(
    ConfigManagerV2.getInstance().get('ssl.keyPath'),
    {
      encoding: 'utf-8',
    }
  );
  const serverCert = fs.readFileSync(
    ConfigManagerV2.getInstance().get('ssl.certificatePath'),
    {
      encoding: 'utf-8',
    }
  );
  const caCert = fs.readFileSync(
    ConfigManagerV2.getInstance().get('ssl.caCertificatePath'),
    {
      encoding: 'utf-8',
    }
  );

  return https.createServer(
    {
      key: serverKey,
      cert: serverCert,
      // request client certificate from user
      requestCert: true,
      // reject requests with no valid certificate
      rejectUnauthorized: true,
      // use ca cert created with own key for self-signed
      ca: [caCert],
      passphrase: ConfigManagerCertPassphrase.readPassphrase(),
    },
    app
  );
};
