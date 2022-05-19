/* eslint-disable */
import { OpenOrders } from '@project-serum/serum/lib/market';
import { sleep } from '../../../../../src/connectors/serum/serum.helpers';
import { Account, AccountInfo, Commitment, Connection, Keypair, PublicKey, Transaction } from '@solana/web3.js';
import bs58 from 'bs58';
import { Solana } from '../../../../../src/chains/solana/solana';
import { Serum } from '../../../../../src/connectors/serum/serum';
import {
  SerumMarket,
  SerumOpenOrders,
  SerumOrder,
  SerumOrderParams
} from '../../../../../src/connectors/serum/serum.types';
import { patch } from '../../../../services/patch';
import { default as config } from '../serum-config';
import data from './data';

const disablePatches = false;

const delayInMilliseconds = 10 * 1000;

const patches = (solana: Solana, serum: Serum) => {
  const patches = new Map();

  patches.set('solana/loadTokens', () => {
    if (disablePatches) return;

    patch(solana, 'loadTokens', () => {
    });
  });

  patches.set('solana/getKeyPair', () => {
    if (disablePatches) return;

    patch(solana, 'getKeypair', (address: string) => {
      if (address === config.solana.wallet.owner.publicKey)
        return Keypair.fromSecretKey(
          bs58.decode(config.solana.wallet.owner.privateKey)
        );

      throw new Error(`Cannot mock unrecognized address "${address}".`);
    });
  });

  patches.set('serum/connection/getAccountInfo', () => {
    if (disablePatches) return;

    const connection = serum.getConnection();

    // eslint-disable-next-line
    // @ts-ignore
    connection.originalGetAccountInfo = (<any>connection).getAccountInfo;

    patch(connection, 'getAccountInfo', async (
      publicKey: PublicKey,
      commitment: Commitment,
    ): Promise<AccountInfo<Buffer> | null> => {
      const key = `@solana/web3.js/Connection/getAccountInfo/${publicKey.toString()}`;

      if (data.has(key)) {
        const raw = data.get(key);

        return {
          executable: raw.executable,
          owner: new PublicKey(raw.owner),
          lamports: raw.lamports,
          data: Buffer.from(raw.data),
          rentEpoch: raw.rentEpoch,
        } as AccountInfo<Buffer>;
      }

      let result: any;

      let attempts = 1;
      let error = false;
      do {
        try {
          // eslint-disable-next-line
          // @ts-ignore
          const result = await connection.originalGetAccountInfo(publicKey, commitment);

          const raw = {
            executable: result.executable,
            owner: result.owner.toString(),
            lamports: result.lamports,
            data: Object.values(result.data),
            rentEpoch: result.rentEpoch,
          };

          // TODO remove!!!
          const fs = require('fs');
          fs.appendFileSync(
            '/Volumes/Data/important/work/robotter.ai/hummingbot/gateway/test/connectors/serum/fixtures/patches/raw.ts',
            `data.set('${key}', ${JSON.stringify(raw)});\n`, {
          });

          error = false;
        } catch (exception) {
          error = false;
          console.log(`${key}, attempt ${attempts}:`, exception);
          attempts++;
          if (attempts > 3) break;
          await sleep(delayInMilliseconds);
        }
      } while (error);

      return result;
    });
  });

  patches.set('serum/market/findOpenOrdersAccountsForOwner', async (marketName: string, returnValue?: OpenOrders[]) => {
    if (disablePatches) return;

    const market = (await serum.getMarket(marketName)).market;

    patch(market, 'findOpenOrdersAccountsForOwner', (
      _connection: Connection,
      ownerAddress: PublicKey,
      _cacheDurationMs = 0
    ) => {
      if (returnValue !== undefined && returnValue != null) return returnValue;

      throw new Error(`Cannot mock, unrecognized address "${ownerAddress.toString()}".`);
    });
  });

  // // TODO remove!!!
  // patches.set('serum/connection/_rpcRequest/getProgramAccounts', (returnValue?: any) => {
  //   if (disablePatches) return;
  //
  //   const connection = serum.getConnection();
  //
  //   // eslint-disable-next-line
  //   // @ts-ignore
  //   connection.originalRpcRequest = (<any>connection)._rpcRequest;
  //
  //   patch(connection, '_rpcRequest', async (methodName: string, args: Array<any>): Promise<any> => {
  //     if (returnValue) return returnValue;
  //
  //     const key = `@solana/web3.js/Connection/_rpcRequest/${methodName}/${JSON.stringify(args)}`;
  //
  //     if (methodName == 'getProgramAccounts') {
  //       if (data.has(key)) {
  //         return data.get(key);
  //       }
  //
  //       let attempts = 1;
  //       let error = false;
  //       do {
  //         try {
  //           // eslint-disable-next-line
  //           // @ts-ignore
  //           const result = await connection.originalRpcRequest(methodName, args);
  //
  //           const raw = {
  //             result: result.result,
  //           };
  //
  //           // TODO remove!!!
  //           const fs = require('fs');
  //           fs.appendFileSync(
  //             '/Volumes/Data/important/work/robotter.ai/hummingbot/gateway/test/connectors/serum/fixtures/patches/raw.ts',
  //             `data.set('${key}', ${JSON.stringify(raw)});\n`, {
  //           });
  //
  //           error = false;
  //
  //           return result;
  //         } catch (exception) {
  //           error = false;
  //           console.log(`${key}, attempt ${attempts}:`, exception);
  //           attempts++;
  //           if (attempts > 3) break;
  //           await sleep(delayInMilliseconds);
  //         }
  //       } while (error);
  //     }
  //   });
  // });

  // patches.set('serum/connection/_wsOnError', () => {
  //   if (disablePatches) return;
  //
  //   const connection = serum.getConnection();
  //   (<any>connection)._wsOnError = (err: Error) => {
  //     if (err.message.startsWith('getaddrinfo ENOTFOUND')) return;
  //
  //     console.error('ws error:', err.message);
  //   };
  // });

  patches.set('serum/serumGetMarketsInformation', () => {
    if (disablePatches) return;

    patch(serum, 'serumGetMarketsInformation', () => {
      return data.get('serum/serumGetMarketsInformation');
    });
  });

  patches.set('serum/getTicker', (marketName: string) => {
    if (disablePatches) return;

    patch(serum, 'getTicker', async () => {
      const market = await serum.getMarket(marketName);

      const raw = data.get(`serum/getTicker/${market.address.toString()}`);

      return {
        price: parseFloat(raw.price),
        timestamp: new Date(raw.last_updated).getTime()
      }
    });
  });

  patches.set('serum/serumMarketPlaceOrders', () => {
    if (disablePatches) return;

    return patch(serum, 'serumMarketPlaceOrders', (
      _market: SerumMarket,
      _connection: Connection,
      orders: SerumOrderParams<Account>[]
    ) => {
      const shuffle = (target: string) => [...target].sort(()=>Math.random()-.5).join('');

      const example = 'AyZgLRoT78G3KUxPiMTWF84MTQam1eL3bwuWBguufqSBU1JKVcrmGJe6XztLKJ4DfzQ8k1NQsLQnxFT4mB5F9yE0';

      return shuffle(example).repeat(orders.length);
    });
  });

  patches.set('serum/serumMarketCancelOrdersAndSettleFunds', () => {
    if (disablePatches) return;

    return patch(serum, 'serumMarketCancelOrdersAndSettleFunds', (
      _market: SerumMarket,
      _connection: Connection,
      _owner: Account,
      orders: SerumOrder[]
    ) => {
      const shuffle = (target: string) => [...target].sort(()=>Math.random()-.5).join('');

      const example = 'AyZgLRoT78G3KUxPiMTWF84MTQam1eL3bwuWBguufqSBU1JKVcrmGJe6XztLKJ4DfzQ8k1NQsLQnxFT4mB5F9yE0';

      return {
        cancelation: shuffle(example).repeat(orders.length),
        fundsSettlement: shuffle(example).repeat(orders.length),
      };
    });
  });

  patches.set('serum/serumSettleFunds', () => {
    if (disablePatches) return;

    return patch(serum, 'serumSettleFunds', () => {
      const shuffle = (target: string) => [...target].sort(()=>Math.random()-.5).join('');

      const example = 'AyZgLRoT78G3KUxPiMTWF84MTQam1eL3bwuWBguufqSBU1JKVcrmGJe6XztLKJ4DfzQ8k1NQsLQnxFT4mB5F9yE0';

      return shuffle(example);
    });
  });

  patches.set('serum/serumSettleSeveralFunds', (
    _market: SerumMarket,
    _connection: Connection,
    settlements: {
      owner: Account;
      openOrders: SerumOpenOrders;
      baseWallet: PublicKey;
      quoteWallet: PublicKey;
      referrerQuoteWallet: PublicKey | null;
    }[],
    _transaction: Transaction = new Transaction()
  ) => {
    if (disablePatches) return;

    return patch(serum, 'serumSettleSeveralFunds', () => {
      const shuffle = (target: string) => [...target].sort(()=>Math.random()-.5).join('');

      const example = 'AyZgLRoT78G3KUxPiMTWF84MTQam1eL3bwuWBguufqSBU1JKVcrmGJe6XztLKJ4DfzQ8k1NQsLQnxFT4mB5F9yE0';

      return shuffle(example).repeat(settlements.length);
    });
  });

  return patches;
};

export default patches;
