// import { BinanceSmartChain } from '../../../../src/chains/binance-smart-chain/binance-smart-chain';
// import { PancakeSwap } from '../../../../src/connectors/pancakeswap/pancakeswap';
// import { patch, unpatch } from '../../../services/patch';

// let bsc: BinanceSmartChain;
// let pancakeswap: PancakeSwap;

// beforeAll(async () => {
//   bsc = BinanceSmartChain.getInstance('testnet');
//   await bsc.init();
//   pancakeswap = PancakeSwap.getInstance('binance-smart-chain', 'testnet');
//   await pancakeswap.init();
// });

// afterEach(() => {
//   unpatch();
// });

// const address: string = '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD';

// const patchGetWallet = () => {
//   patch(bsc, 'getWallet', () => {
//     return {
//       address: address,
//     };
//   });
// };

// const patchStoredTokenList = () => {
//   patch(bsc, 'tokenList', () => {
//     return [
//       {
//         chainId: 97,
//         address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
//         decimals: 18,
//         name: 'WBNB Token',
//         symbol: 'WBNB',
//       },
//     ];
//   });
// };
