import fs from 'fs';
import yaml from 'js-yaml';
import { logger } from './logger';

export namespace ConfigManagerCertPassphrase {
  export const passphraseFliePath: string = './conf/gateway-passphrase.yml';

  export interface PassphraseConfig {
    CERT_PASSPHRASE: string;
  }

  // this adds a level of indirection so we can test the code
  export const bindings = {
    _exit: process.exit,
  };

  export function readPassphrase(): string | undefined {
    if (fs.existsSync(passphraseFliePath)) {
      const mode = fs.lstatSync(passphraseFliePath).mode;
      // check and make sure the passphrase file is a regular file, and is only accessible by the user.
      if (
        mode ===
        (fs.constants.S_IFREG | fs.constants.S_IWUSR | fs.constants.S_IRUSR)
      ) {
        const x = yaml.load(
          fs.readFileSync(passphraseFliePath, 'utf8')
        ) as PassphraseConfig;
        if ('CERT_PASSPHRASE' in x) {
          return x.CERT_PASSPHRASE;
        } else {
          logger.error(
            passphraseFliePath + ' does not have CERT_PASSPHRASE set.'
          );
          bindings._exit(1);
        }
      } else {
        logger.error(
          passphraseFliePath +
            ' file does not strictly have mode set to user READ_WRITE only.'
        );
        bindings._exit(1);
      }
    }

    // the compiler does not know that bindings._exit(1) will end the function
    // so we need a return to satisfy the compiler checks
    logger.error(
      passphraseFliePath +
        ' does not exist. It should contain a password and have mode set to user READ_WRITE only.'
    );
    bindings._exit(1);
    return;
  }
}
