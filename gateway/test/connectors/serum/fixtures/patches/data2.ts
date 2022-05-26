import { Orderbook } from '@project-serum/serum/lib/market';
import { Slab } from '@project-serum/serum/lib/slab';
import { PublicKey } from '@solana/web3.js';
import BN from 'bn.js';
import { SerumMarket } from '../../../../../src/connectors/serum/serum.types';

const info = {
  'SOL/USDC': {
    address: '9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT',
  },
  'SOL/USDT': {
    address: 'HWHvQhFmJB3NUcu1aihKmrKegfVxBEHzwVX6yZCKEsi1',
  },
  'SRM/SOL': {
    address: 'jyei9Fpj2GtHLDDGgcuhDacxYLLiSyxU4TY7KxB2xai',
  },
};

const data = new Map<string, any>();

const slab = Slab.decode(
  Buffer.from(
    '0900000000000000020000000000000008000000000000000400000000000000010000001e00000000000040952fe4da5c1f3c860200000004000000030000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b0000000000000000000000000000000200000002000000000000a0ca17726dae0f1e43010000001111111111111111111111111111111111111111111111111111111111111111410100000000000000000000000000000200000001000000d20a3f4eeee073c3f60fe98e010000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b000000000000000000000000000000020000000300000000000040952fe4da5c1f3c8602000000131313131313131313131313131313131313131313131313131313131313131340e20100000000000000000000000000010000001f0000000500000000000000000000000000000005000000060000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b0000000000000000000000000000000200000004000000040000000000000000000000000000001717171717171717171717171717171717171717171717171717171717171717020000000000000000000000000000000100000020000000000000a0ca17726dae0f1e430100000001000000020000000d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d7b000000000000000000000000000000040000000000000004000000000000000000000000000000171717171717171717171717171717171717171717171717171717171717171702000000000000000000000000000000030000000700000005000000000000000000000000000000171717171717171717171717171717171717171717171717171717171717171702000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
    'hex'
  )
);

// Market SOL/USDC
data.set(
  `serum/market/${info['SOL/USDC'].address}`,
  new SerumMarket(
    {
      accountFlags: {
        initialized: true,
        market: true,
        openOrders: false,
        requestQueue: false,
        eventQueue: false,
        bids: false,
        asks: false,
      },
      ownAddress: new PublicKey('9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT'),
      vaultSignerNonce: new BN('01', 'hex'),
      baseMint: new PublicKey('So11111111111111111111111111111111111111112'),
      quoteMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
      baseVault: new PublicKey('36c6YqAwyGKQG66XEp2dJc5JqjaBNv7sVghEtJv4c7u6'),
      baseDepositsTotal: new BN('38ffa8cfb300', 'hex'),
      baseFeesAccrued: new BN('00', 'hex'),
      quoteVault: new PublicKey('8CFo8bL8mZQK8abbFyypFMwEDd8tVJjHTTojMLgQTUSZ'),
      quoteDepositsTotal: new BN('0394280a510a', 'hex'),
      quoteFeesAccrued: new BN('8eefb0a13a', 'hex'),
      quoteDustThreshold: new BN('64', 'hex'),
      requestQueue: new PublicKey(
        'AZG3tFCFtiCqEwyardENBQNpHqxgzbMw8uKeZEw2nRG5'
      ),
      eventQueue: new PublicKey('5KKsLVU6TcbVDK4BS6K1DGDxnh4Q9xjYJ8XaDCG5t8ht'),
      bids: new PublicKey('14ivtgssEBoBjuZJtSAPKYgpUK7DmnSwuPMqJoVTSgKJ'),
      asks: new PublicKey('CEQdAFKdycHugujQg9k2wbmxjcpdYZyVLfV9WerTnafJ'),
      baseLotSize: new BN('05f5e100', 'hex'),
      quoteLotSize: new BN('64', 'hex'),
      feeRateBps: new BN('00', 'hex'),
      referrerRebatesAccrued: new BN('1082ee555a', 'hex'),
    },
    9,
    6,
    {},
    new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin')
  )
);

// OrderBook Asks SOL/USDC
data.set(
  `serum/market/${info['SOL/USDC']}/asks`,
  new Orderbook(
    data.get(`serum/market/${info['SOL/USDC'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: false,
      asks: true,
    },
    slab
  )
);

// OrderBook Bids SOL/USDC
data.set(
  `serum/market/${info['SOL/USDC']}/bids`,
  new Orderbook(
    data.get(`serum/market/${info['SOL/USDC'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: true,
      asks: false,
    },
    slab
  )
);

// Market SOL/USDT
data.set(
  `serum/market/${info['SOL/USDT'].address}`,
  new SerumMarket(
    {
      accountFlags: {
        initialized: true,
        market: true,
        openOrders: false,
        requestQueue: false,
        eventQueue: false,
        bids: false,
        asks: false,
      },
      ownAddress: new PublicKey('HWHvQhFmJB3NUcu1aihKmrKegfVxBEHzwVX6yZCKEsi1'),
      vaultSignerNonce: new BN('01', 'hex'),
      baseMint: new PublicKey('So11111111111111111111111111111111111111112'),
      quoteMint: new PublicKey('Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'),
      baseVault: new PublicKey('29cTsXahEoEBwbHwVc59jToybFpagbBMV6Lh45pWEmiK'),
      baseDepositsTotal: new BN('68d96a437e00', 'hex'),
      baseFeesAccrued: new BN('00', 'hex'),
      quoteVault: new PublicKey('EJwyNJJPbHH4pboWQf1NxegoypuY48umbfkhyfPew4E'),
      quoteDepositsTotal: new BN('05809972e503', 'hex'),
      quoteFeesAccrued: new BN('072ec1dc82', 'hex'),
      quoteDustThreshold: new BN('64', 'hex'),
      requestQueue: new PublicKey(
        'GKrA1P2XVfpfZbpXaFcd2LNp7PfpnXZCbUusuFXQjfE9'
      ),
      eventQueue: new PublicKey('GR363LDmwe25NZQMGtD2uvsiX66FzYByeQLcNFr596FK'),
      bids: new PublicKey('2juozaawVqhQHfYZ9HNcs66sPatFHSHeKG5LsTbrS2Dn'),
      asks: new PublicKey('ANXcuziKhxusxtthGxPxywY7FLRtmmCwFWDmU5eBDLdH'),
      baseLotSize: new BN('05f5e100', 'hex'),
      quoteLotSize: new BN('64', 'hex'),
      feeRateBps: new BN('00', 'hex'),
      referrerRebatesAccrued: new BN('0458e87c90', 'hex'),
    },
    9,
    6,
    {},
    new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin')
  )
);

// OrderBook Asks SOL/USDT
data.set(
  `serum/market/${info['SOL/USDT']}/asks`,
  new Orderbook(
    data.get(`serum/market/${info['SOL/USDT'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: false,
      asks: true,
    },
    slab
  )
);

// OrderBook Bids SOL/USDT
data.set(
  `serum/market/${info['SOL/USDT']}/bids`,
  new Orderbook(
    data.get(`serum/market/${info['SOL/USDT'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: true,
      asks: false,
    },
    slab
  )
);

// Market SRM/SOL
data.set(
  `serum/market/${info['SRM/SOL'].address}`,
  new SerumMarket(
    {
      accountFlags: {
        initialized: true,
        market: true,
        openOrders: false,
        requestQueue: false,
        eventQueue: false,
        bids: false,
        asks: false,
      },
      ownAddress: new PublicKey('jyei9Fpj2GtHLDDGgcuhDacxYLLiSyxU4TY7KxB2xai'),
      vaultSignerNonce: new BN('00', 'hex'),
      baseMint: new PublicKey('SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt'),
      quoteMint: new PublicKey('So11111111111111111111111111111111111111112'),
      baseVault: new PublicKey('EhAJTsW745jiWjViB7Q4xXcgKf6tMF7RcMX9cbTuXVBk'),
      baseDepositsTotal: new BN('16f61d5d00', 'hex'),
      baseFeesAccrued: new BN('00', 'hex'),
      quoteVault: new PublicKey('HFSNnAxfhDt4DnmY9yVs2HNFnEMaDJ7RxMVNB9Y5Hgjr'),
      quoteDepositsTotal: new BN('d772f76602', 'hex'),
      quoteFeesAccrued: new BN('2dcab54b', 'hex'),
      quoteDustThreshold: new BN('64', 'hex'),
      requestQueue: new PublicKey(
        'Fx15MivJTQokQZKazxGCsbWxRsx3uGrawkTidoBDrHv8'
      ),
      eventQueue: new PublicKey('nyZdeD16L5GxJq7Pso8R6KFfLA8R9v7c5A2qNaGWR44'),
      bids: new PublicKey('4ZTJfhgKPizbkFXNvTRNLEncqg85yJ6pyT7NVHBAgvGw'),
      asks: new PublicKey('7hLgwZhHD1MRNyiF1qfAjfkMzwvP3VxQMLLTJmKSp4Y3'),
      baseLotSize: new BN('0186a0', 'hex'),
      quoteLotSize: new BN('0186a0', 'hex'),
      feeRateBps: new BN('00', 'hex'),
      referrerRebatesAccrued: new BN('0584531e3a', 'hex'),
    },
    6,
    9,
    {},
    new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin')
  )
);

// OrderBook Asks SRM/SOL
data.set(
  `serum/market/${info['SRM/SOL']}/asks`,
  new Orderbook(
    data.get(`serum/market/${info['SRM/SOL'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: false,
      asks: true,
    },
    slab
  )
);

// OrderBook Bids SRM/SOL
data.set(
  `serum/market/${info['SRM/SOL']}/bids`,
  new Orderbook(
    data.get(`serum/market/${info['SRM/SOL'].address}`),
    {
      initialized: true,
      market: false,
      openOrders: false,
      requestQueue: false,
      eventQueue: false,
      bids: true,
      asks: false,
    },
    slab
  )
);

export default data;
