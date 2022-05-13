import { Keypair } from '@solana/web3.js';
import bs58 from 'bs58';
import { Solana } from '../../../../src/chains/solana/solana';
import { Serum } from '../../../../src/connectors/serum/serum';
import { patch } from '../../../services/patch';
import { default as config } from './serumConfig';

const patches = (solana: Solana, serum: Serum) => {
  return {
    solana: {
      getKeypair: () => {
        patch(solana, 'getKeypair', (address: string) => {
          if (address === config.solana.wallet.owner.publicKey)
            return Keypair.fromSecretKey(
              bs58.decode(config.solana.wallet.owner.privateKey)
            );

          if (address === config.solana.wallet.payer.publicKey)
            return Keypair.fromSecretKey(
              bs58.decode(config.solana.wallet.payer.privateKey)
            );

          return null;
        });
      },
    },
    serum: {
      serumGetMarketsInformation: () => {
        patch(serum, 'serumGetMarketsInformation', () => {
        });
      },
      serumLoadMarket: () => {
        patch(serum, 'serumLoadMarket', () => {
        });
      },
      serumMarketLoadBids: () => {
        patch(serum, 'serumMarketLoadBids', () => {
        });
      },
      serumMarketLoadAsks: () => {
        patch(serum, 'serumMarketLoadAsks', () => {
        });
      },
      serumMarketLoadFills: () => {
        patch(serum, 'serumMarketLoadFills', () => {
        });
      },
      serumMarketLoadOrdersForOwner: () => {
        patch(serum, 'serumMarketLoadOrdersForOwner', () => {
        });
      },
      serumMarketPlaceOrders: () => {
        patch(serum, 'serumMarketPlaceOrders', () => {
        });
      },
      serumMarketCancelOrdersAndSettleFunds: () => {
        patch(serum, 'serumMarketCancelOrdersAndSettleFunds', () => {
        });
      },
      serumFindOpenOrdersAccountsForOwner: () => {
        patch(serum, 'serumFindOpenOrdersAccountsForOwner', () => {
        });
      },
      serumFindBaseTokenAccountsForOwner: () => {
        patch(serum, 'serumFindBaseTokenAccountsForOwner', () => {
        });
      },
      serumFindQuoteTokenAccountsForOwner: () => {
        patch(serum, 'serumFindQuoteTokenAccountsForOwner', () => {
        });
      },
      serumSettleFunds: () => {
        patch(serum, 'serumSettleFunds', () => {
        });
      },
      serumSettleSeveralFunds: () => {
        patch(serum, 'serumSettleSeveralFunds', () => {
        });
      },
      getTicker: () => {
        patch(serum, 'getTicker', () => {
        });
      },
    },
  };
};

export default patches;
