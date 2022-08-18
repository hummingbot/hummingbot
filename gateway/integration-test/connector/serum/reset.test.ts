import { Account, PublicKey } from '@solana/web3.js';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import BN from 'bn.js';
import 'jest-extended';
import { Solana } from '../../../src/chains/solana/solana';
import { Serum } from '../../../src/connectors/serum/serum';
import {
  getNotNullOrThrowError,
  sleep,
} from '../../../src/connectors/serum/serum.helpers';
import { IMap, Market } from '../../../src/connectors/serum/serum.types';
import { default as config } from '../../../test/chains/solana/serum/fixtures/config';
import { getNewCandidateOrdersTemplates } from '../../../test/chains/solana/serum/fixtures/helpers';
import { unpatch } from '../../../test/services/patch';

jest.setTimeout(30 * 60 * 1000);

let solana: Solana;
let serum: Serum;

beforeAll(async () => {
  solana = await Solana.getInstance(config.serum.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  await solana.init();
  await serum.init();
});

afterEach(() => {
  unpatch();
});

const commonParameters = {
  chain: config.serum.chain,
  network: config.serum.network,
  connector: config.serum.connector,
};
const allMarketNames = ['SOL/USDT', 'SOL/USDC', 'SRM/SOL'];
const marketNames = allMarketNames.slice(0, 2);

describe('Reset and Recreate Dummy Orders', () => {
  const delayInMilliseconds = 1000;

  it('Cancel all orders and settle all funds', async () => {
    let attempts = 1;
    let error = false;

    do {
      try {
        const connection = serum.getConnection();
        const markets: IMap<string, Market> = await (
          await Serum.getInstance(
            commonParameters.chain,
            commonParameters.network
          )
        ).getMarkets(marketNames);
        const ownerKeyPair = await solana.getKeypair(
          config.solana.wallet.owner.publicKey
        );
        const owner = new Account(ownerKeyPair.secretKey);

        for (const market of Array.from(markets.values())) {
          console.log(`Resetting market ${market.name}:`);

          const serumMarket = market.market;
          const openOrders = await serumMarket.loadOrdersForOwner(
            connection,
            owner.publicKey
          );

          console.log('Open orders found:', JSON.stringify(openOrders));

          for (const openOrder of openOrders) {
            try {
              const result = await serumMarket.cancelOrder(
                connection,
                owner,
                openOrder
              );
              console.log(
                `Cancelling order ${openOrder.orderId}:`,
                JSON.stringify(result)
              );
            } catch (exception: any) {
              if (
                exception.message.includes(
                  'It is unknown if it succeeded or failed.'
                )
              ) {
                console.log(exception);
              } else {
                throw exception;
              }
            }
          }

          for (const openOrders of await serumMarket.findOpenOrdersAccountsForOwner(
            connection,
            owner.publicKey
          )) {
            console.log(
              `Settling funds for orders:`,
              JSON.stringify(openOrders)
            );

            if (
              openOrders.baseTokenFree.gt(new BN(0)) ||
              openOrders.quoteTokenFree.gt(new BN(0))
            ) {
              const base = await serumMarket.findBaseTokenAccountsForOwner(
                connection,
                owner.publicKey,
                true
              );
              const baseTokenAccount = base[0].pubkey;
              const quote = await serumMarket.findQuoteTokenAccountsForOwner(
                connection,
                owner.publicKey,
                true
              );
              const quoteTokenAccount = quote[0].pubkey;

              try {
                const result = await serumMarket.settleFunds(
                  connection,
                  owner,
                  openOrders,
                  baseTokenAccount,
                  quoteTokenAccount
                );

                console.log(
                  `Result of settling funds:`,
                  JSON.stringify(result)
                );
              } catch (exception: any) {
                if (
                  exception.message.includes(
                    'It is unknown if it succeeded or failed.'
                  )
                ) {
                  console.log(exception);
                } else {
                  throw exception;
                }
              }
            }
          }
        }

        error = false;

        console.log('Reset done.');
      } catch (exception) {
        console.log(
          `Cancel all orders and settle all funds, attempt ${attempts} with error: `,
          exception
        );

        attempts += 1;

        error = true;

        await sleep(delayInMilliseconds);
      }
    } while (error);
  });

  it('Place dummy orders', async () => {
    const ownerKeyPair = await solana.getKeypair(
      config.solana.wallet.owner.publicKey
    );
    const owner = new Account(ownerKeyPair.secretKey);

    const candidateOrders = getNewCandidateOrdersTemplates(8, 0);

    for (const candidateOrder of candidateOrders) {
      const market = (await serum.getMarket(candidateOrder.marketName)).market;

      const payer = new PublicKey(
        getNotNullOrThrowError(candidateOrder.payerAddress)
      );

      let attempts = 1;
      let error = false;
      do {
        try {
          await market.placeOrder((<any>serum).connection, {
            owner,
            payer,
            side: candidateOrder.side.toLowerCase() as 'buy' | 'sell',
            price: candidateOrder.price,
            size: candidateOrder.amount,
            orderType: candidateOrder.type?.toLowerCase() as
              | 'limit'
              | 'ioc'
              | 'postOnly',
            clientId: new BN(candidateOrder.id!),
          });

          error = false;
        } catch (exception: any) {
          if (
            exception.message.includes(
              'It is unknown if it succeeded or failed.'
            )
          )
            break;

          console.log(
            `Place dummy order ${candidateOrder.id}, attempt ${attempts} with error: `,
            exception
          );

          attempts += 1;

          error = true;

          await sleep(delayInMilliseconds);
        }
      } while (error);
    }
  });

  it('List open orders', async () => {
    const connection = serum.getConnection();
    const markets = await (
      await Serum.getInstance(commonParameters.chain, commonParameters.network)
    ).getMarkets(marketNames);
    const ownerKeyPair = await solana.getKeypair(
      config.solana.wallet.owner.publicKey
    );
    const owner = new Account(ownerKeyPair.secretKey);

    for (const market of Array.from(markets.values())) {
      let attempts = 1;
      let error = false;

      do {
        try {
          const serumMarket = market.market;
          const openOrders = await serumMarket.loadOrdersForOwner(
            connection,
            owner.publicKey
          );

          console.log('Open orders found:', JSON.stringify(openOrders));

          error = false;
        } catch (exception) {
          console.log(
            `List open orders for market ${market.name}, attempt ${attempts} with error: `,
            exception
          );

          attempts += 1;

          error = true;

          await sleep(delayInMilliseconds);
        }
      } while (error);
    }
  });
});
