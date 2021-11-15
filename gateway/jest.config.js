module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  forceExit: true,
  coveragePathIgnorePatterns: [
    'src/app.ts',
    'src/https.ts',
    'src/services/ethereum-base.ts',
    'src/services/config-manager-cert-passphrase.ts',
    'src/chains/ethereum/ethereum.ts',
    'src/chains/ethereum/uniswap/uniswap.ts',
    'src/chains/avalanche/avalanche.ts',
    'src/chains/avalanche/pangolin/pangolin.ts',
  ],
  modulePathIgnorePatterns: ['<rootDir>/dist/'],
};
