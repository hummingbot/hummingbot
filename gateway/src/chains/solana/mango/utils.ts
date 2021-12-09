import { Config, GroupConfig } from "@blockworks-foundation/mango-client";
import { I80F48 } from "@blockworks-foundation/mango-client/lib/src/fixednum";
import { CustomValidator } from "express-validator";
import pino from "pino";
import { Transaction, Connection, Account } from "@solana/web3.js";

/// solana related

export async function transactionSize(
  connection: Connection,
  singleTransaction: Transaction,
  owner: Account
) {
  singleTransaction.recentBlockhash = (
    await connection.getRecentBlockhash()
  ).blockhash;
  singleTransaction.setSigners(owner.publicKey);
  singleTransaction.sign(this.owner);
  return singleTransaction.serialize().length;
}

/// mango related

export const i80f48ToPercent = (value: I80F48) =>
  value.mul(I80F48.fromNumber(100));

const groupName = process.env.GROUP || "mainnet.1";
const mangoGroupConfig: GroupConfig = Config.ids().groups.filter(
  (group) => group.name === groupName
)[0];

const allMarketNames = mangoGroupConfig.spotMarkets
  .map((spotMarketConfig) => spotMarketConfig.baseSymbol + "-SPOT")
  .concat(
    mangoGroupConfig.perpMarkets.map(
      (perpMarketConfig) => perpMarketConfig.name
    )
  );

const allCoins = mangoGroupConfig.tokens.map(
  (tokenConfig) => tokenConfig.symbol
);

export function patchExternalMarketName(marketName: string) {
  if (marketName.includes("-SPOT")) {
    marketName = marketName.replace("-SPOT", "/USDC");
  }
  return marketName;
}

export function patchInternalMarketName(marketName: string) {
  if (marketName.includes("/USDC")) {
    marketName = marketName.replace("/USDC", "-SPOT");
  }
  return marketName;
}

/// general

export function zipDict<K extends string | number | symbol, V>(
  keys: K[],
  values: V[]
): Partial<Record<K, V>> {
  const result: Partial<Record<K, V>> = {};
  keys.forEach((key, index) => {
    result[key] = values[index];
  });
  return result;
}

export const logger = pino({
  prettyPrint: { translateTime: true },
});

/// expressjs related

export const isValidMarket: CustomValidator = (marketName) => {
  if (allMarketNames.indexOf(marketName) === -1) {
    return Promise.reject(`Market ${marketName} not supported!`);
  }
  return Promise.resolve();
};

export const isValidCoin: CustomValidator = (coin) => {
  if (allCoins.indexOf(coin) === -1) {
    return Promise.reject(`Coin ${coin} not supported!`);
  }
  return Promise.resolve();
};
