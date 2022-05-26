import { ConfigManagerV2 } from '../src/services/config-manager-v2';
import fse from 'fs-extra';
import fsp from 'fs/promises';
import os from 'os';
import path from 'path';

export class OverrideConfigs {
  public nonceDbPath: string;
  public transactionDbPath: string;
  #tempNonceDbPath: string = '';
  #tempTransactionDbPath: string = '';
  #initialized: boolean = false;

  public constructor() {
    this.nonceDbPath = ConfigManagerV2.getInstance().get(
      'database.nonceDbPath'
    );
    this.transactionDbPath = ConfigManagerV2.getInstance().get(
      'database.transactionDbPath'
    );
  }

  async init(): Promise<void> {
    if (!this.#initialized) {
      this.#tempNonceDbPath = await fsp.mkdtemp(
        path.join(os.tmpdir(), '/nonce.test.level')
      );
      this.#tempTransactionDbPath = await fsp.mkdtemp(
        path.join(os.tmpdir(), '/transaction.test.level')
      );
    }
  }

  updateConfigs(): void {
    ConfigManagerV2.getInstance().set(
      'database.nonceDbPath',
      this.#tempNonceDbPath
    );
    ConfigManagerV2.getInstance().set(
      'database.transactionDbPath',
      this.#tempTransactionDbPath
    );
  }

  async resetConfigs(): Promise<void> {
    await fse.emptyDir(this.#tempNonceDbPath);
    fse.rmSync(this.#tempNonceDbPath, { force: true, recursive: true });

    await fse.emptyDir(this.#tempTransactionDbPath);
    fse.rmSync(this.#tempTransactionDbPath, { force: true, recursive: true });

    ConfigManagerV2.getInstance().set('database.nonceDbPath', this.nonceDbPath);
    ConfigManagerV2.getInstance().set(
      'database.transactionDbPath',
      this.transactionDbPath
    );
  }
}
