import { ConfigManagerV2 } from '../src/services/config-manager-v2';

export class OverrideConfigs {
  public nonceDbPath: string;
  public transactionDbPath: string;
  #testNonceDbPath: string = '';
  #testTransactionDbPath: string = '';
  #initialized: boolean = false;

  public constructor() {
    this.nonceDbPath = ConfigManagerV2.getInstance().get(
      'database.nonceDbPath'
    );
    this.transactionDbPath = ConfigManagerV2.getInstance().get(
      'database.transactionDbPath'
    );
  }

  init(): void {
    if (!this.#initialized) {
      this.#testNonceDbPath = this.nonceDbPath + '.test';
      this.#testTransactionDbPath = this.transactionDbPath + '.test';
      this.#initialized = true;
    }
  }

  updateConfigs(): void {
    ConfigManagerV2.getInstance().set(
      'database.nonceDbPath',
      this.#testNonceDbPath
    );
    ConfigManagerV2.getInstance().set(
      'database.transactionDbPath',
      this.#testTransactionDbPath
    );
  }

  resetConfigs(): void {
    ConfigManagerV2.getInstance().set('database.nonceDbPath', this.nonceDbPath);
    ConfigManagerV2.getInstance().set(
      'database.transactionDbPath',
      this.transactionDbPath
    );
  }
}

export const DBPathOverride = new OverrideConfigs();
