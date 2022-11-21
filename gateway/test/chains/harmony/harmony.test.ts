import { Harmony } from '../../../src/chains/harmony/harmony';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
import { SushiswapConfig } from '../../../src/connectors/sushiswap/sushiswap.config';
import { DefikingdomsConfig } from '../../../src/connectors/defikingdoms/defikingdoms.config';
import { DefiraConfig } from '../../../src/connectors/defira/defira.config';

let harmony: Harmony;

beforeAll(async () => {
  harmony = Harmony.getInstance('mainnet');
  patchEVMNonceManager(harmony.nonceManager);
  await harmony.init();
});

afterAll(async () => {
  await harmony.close();
});

describe('getSpender', () => {
  describe('get defira', () => {
    it('returns defira mainnet router address', () => {
      const dfkAddress = harmony.getSpender('defira');
      expect(dfkAddress.toLowerCase()).toEqual(
        DefiraConfig.config.routerAddress('mainnet').toLowerCase()
      );
    });
  });
  describe('get viperswap', () => {
    it('returns viperswap mainnet address', () => {
      const viperswapAddress = harmony.getSpender('viperswap');
      expect(viperswapAddress.toLowerCase()).toEqual(
        '0xf012702a5f0e54015362cbca26a26fc90aa832a3'
      );
    });
  });
  describe('get sushiswap', () => {
    it('returns sushiswap kovan address', () => {
      const sushiswapAddress = harmony.getSpender('sushiswap');
      expect(sushiswapAddress.toLowerCase()).toEqual(
        SushiswapConfig.config
          .sushiswapRouterAddress('ethereum', 'kovan')
          .toLowerCase()
      );
    });
  });
  describe('get defikingdoms', () => {
    it('returns defikingdoms mainnet router address', () => {
      const dfkAddress = harmony.getSpender('defikingdoms');
      expect(dfkAddress.toLowerCase()).toEqual(
        DefikingdomsConfig.config.routerAddress('mainnet').toLowerCase()
      );
    });
  });
  describe('get defira', () => {
    it('returns defira mainnet router address', () => {
      const dfkAddress = harmony.getSpender('defira');
      expect(dfkAddress.toLowerCase()).toEqual(
        DefiraConfig.config.routerAddress('mainnet').toLowerCase()
      );
    });
  });
});
