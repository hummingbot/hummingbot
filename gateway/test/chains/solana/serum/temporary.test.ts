// TODO remove this file!!!

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import 'jest-extended';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Orderbook } from '@project-serum/serum/lib/market';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Slab } from '@project-serum/serum/lib/slab';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Connection, PublicKey } from '@solana/web3.js';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Solana } from '../../../../src/chains/solana/solana';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { Serum } from '../../../../src/connectors/serum/serum';
import { SerumMarket } from '../../../../src/connectors/serum/serum.types';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import { unpatch } from '../../../services/patch';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { default as config } from './fixtures/config.backup';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { default as data } from './fixtures/patches/data';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { default as patchesCreator } from './fixtures/patches/patches.backup';

jest.setTimeout(5 * 60 * 1000);

// let solana: Solana;
// let serum: Serum;

// let patches: Map<string, any>;

beforeAll(async () => {
  // solana = await Solana.getInstance(config.serum.network);
  //
  // serum = await Serum.getInstance(config.serum.chain, config.serum.network);
  // patches = await patchesCreator(solana, serum);
  //
  // patches.get('solana/loadTokens')();
  //
  // patches.get('serum/serumGetMarketsInformation')();
  // await solana.init();
  // await serum.init();
});

afterEach(() => {
  unpatch();
});

it.skip('001', async () => {
  const connection = new Connection('');

  const market: SerumMarket = data.get(
    'serum/market/9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT'
  );

  const result = await market.loadAsks(connection);

  // const buffer = Buffer.from(
  //   '0900000000000000020000000000000008000000000000000400000000000000010000001e00000000000040952fe4da5c1f3c860200000004000000030000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b0000000000000000000000000000000200000002000000000000a0ca17726dae0f1e43010000001111111111111111111111111111111111111111111111111111111111111111410100000000000000000000000000000200000001000000d20a3f4eeee073c3f60fe98e010000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b000000000000000000000000000000020000000300000000000040952fe4da5c1f3c8602000000131313131313131313131313131313131313131313131313131313131313131340e20100000000000000000000000000010000001f0000000500000000000000000000000000000005000000060000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b0000000000000000000000000000000200000004000000040000000000000000000000000000001717171717171717171717171717171717171717171717171717171717171717020000000000000000000000000000000100000020000000000000a0ca17726dae0f1e430100000001000000020000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b000000000000000000000000000000040000000000000004000000000000000000000000000000171717171717171717171717171717171717171717171717171717171717171702000000000000000000000000000000030000000700000005000000000000000000000000000000171717171717171717171717171717171717171717171717171717171717171702000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
  //   'hex'
  // );
  //
  // const slab = Slab.decode(buffer);
  //
  // // const result = await market.loadBids(connection);
  //
  // const result = new Orderbook(
  //   market,
  //   {
  //     initialized: true,
  //     market: false,
  //     openOrders: false,
  //     requestQueue: false,
  //     eventQueue: false,
  //     bids: true,
  //     asks: false,
  //   },
  //   slab
  // );
  //
  console.log(result !== undefined);
});
