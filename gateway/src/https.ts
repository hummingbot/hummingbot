import { Application } from 'express';
import fs from 'fs';
import https from 'https';
import { ConfigManager } from './services/config-manager';

const certPath = ConfigManager.config.CERT_PATH.replace(/\/$/, '');

export const addHttps = (app: Application) => {
  const serverKey = fs.readFileSync(certPath.concat('/server_key.pem'), {
    encoding: 'utf-8',
  });
  const serverCert = fs.readFileSync(certPath.concat('/server_cert.pem'), {
    encoding: 'utf-8',
  });
  const caCert = fs.readFileSync(certPath.concat('/ca_cert.pem'), {
    encoding: 'utf-8',
  });

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
      passphrase: ConfigManager.config.CERT_PASSPHRASE,
    },
    app
  );
};
