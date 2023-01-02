module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  forceExit: true,
  coveragePathIgnorePatterns: [
    'src/app.ts',
    'src/https.ts',
    'src/paths.ts',
    'src/services/ethereum-base.ts',
    'src/services/cosmos-base.ts',
    'src/services/telemetry-transport.ts',
    'src/chains/cronos/cronos.ts',
    'src/chains/binance-smart-chain/binance-smart-chain.ts',
    'src/chains/ethereum/ethereum.ts',
    'src/chains/avalanche/avalanche.ts',
    'src/chains/avalanche/pangolin/pangolin.ts',
    'src/chains/solana/solana.ts',
    'src/chains/cosmos/cosmos.ts',
    'src/chains/near/near.ts',
    'src/chains/near/near.base.ts',
    'src/connectors/uniswap/uniswap.config.ts',
    'src/connectors/uniswap/uniswap.ts',
    'src/connectors/uniswap/uniswap.lp.helper.ts',
    'src/connectors/defikingdoms/defikingdoms.ts',
    'src/connectors/defira/defira.ts',
    'src/connectors/openocean/openocean.ts',
    'src/connectors/pangolin/pangolin.ts',
    'src/connectors/quickswap/quickswap.ts',
    'src/connectors/sushiswap/sushiswap.ts',
    'src/connectors/traderjoe/traderjoe.ts',
    'src/connectors/serum/serum.config.ts',
    'src/connectors/serum/extensions/*',
    'src/network/network.controllers.ts',
    'src/services/ethereum-base.ts',
    'src/services/telemetry-transport.ts',
    'test/*',
  ],
  modulePathIgnorePatterns: ['<rootDir>/dist/'],
  setupFilesAfterEnv: ['<rootDir>/test/setupTests.js'],
  globalSetup: '<rootDir>/test/setup.ts',
  globalTeardown: '<rootDir>/test/teardown.ts',
};
