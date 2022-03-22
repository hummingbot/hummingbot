import {} from '@solana/web3.js';
import {} from '@solana/spl-token';
import {} from '@project-serum/serum';

export class Serum {
  private static _instance: Serum;
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  private _tokens: string[] = ['ABC', 'SOL'];

  public static getInstance(): Serum {
    if (!Serum._instance) {
      Serum._instance = new Serum();
    }

    return Serum._instance;
  }

  public static reload(): Serum {
    Serum._instance = new Serum();
    return Serum._instance;
  }

  ready(): boolean {
    return this._ready;
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._initPromise = this.loadTokens().then(() => {
        this._ready = true;
        this._initializing = false;
      });
    }
    return this._initPromise;
  }

  private async loadTokens() {
    return this._tokens;
  }
}
