/* eslint-disable */
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
import { default as config } from '../serumConfig';
import data from './data';

const disablePatches = false;

const patches = (solana: Solana, serum: Serum) => {
  const patches = new Map();

  patches.set('solana/init', () => {
    if (disablePatches) return;

    patch(solana, 'init', () => {
      patch(solana, 'loadTokens', () => {
      });
    });
  });

  patches.set('solana/ready', () => {
    if (disablePatches) return;

    patch(solana, 'ready', () => {
      return true;
    });
  });

  patches.set('solana/getKeyPair', () => {
    if (disablePatches) return;

    patch(solana, 'getKeypair', (address: string) => {
      if (address === config.solana.wallet.owner.publicKey)
        return Keypair.fromSecretKey(
          bs58.decode(config.solana.wallet.owner.privateKey)
        );

      return null;
    });
  });

  patches.set('serum/ready', () => {
    if (disablePatches) return;

    patch(serum, 'ready', () => {
      return true;
    });
  });

  patches.set('serum/init', () => {
    if (disablePatches) return;

    const connection = serum.getConnection();
    // eslint-disable-next-line
      // @ts-ignore
    connection.originalGetAccountInfo = connection.getAccountInfo;

    patch(connection, 'getAccountInfo', async (
      publicKey: PublicKey,
      commitment?: Commitment,
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

      const fs = require('fs');
      fs.writeFileSync(
        '/Volumes/Data/important/work/robotter.ai/hummingbot/gateway/test/connectors/serum/fixtures/patches/raw.ts',
        `data.set('${key}', ${JSON.stringify(raw)});`, {
        flag: 'a',
      });

      return result;
    });
  });

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

      return data.get(`serum/getTicker/${market.address.toString()}`);
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

  // patches.set('', () => {
  //   if (disablePatches) return;
  //
  //   return patch(, '', () => {
  //   });
  // });

  return patches;
};

export default patches;
