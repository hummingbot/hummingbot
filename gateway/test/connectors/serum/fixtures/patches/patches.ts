/* eslint-disable */
import { MarketOptions, Orderbook } from '@project-serum/serum/lib/market';
import { AccountInfo, Commitment, Keypair, PublicKey } from '@solana/web3.js';
import BN from 'bn.js';
import bs58 from 'bs58';
import { Buffer } from 'buffer';
import { plainToClassFromExist, plainToInstance } from 'class-transformer';
import { Solana } from '../../../../../src/chains/solana/solana';
import { Serum } from '../../../../../src/connectors/serum/serum';
import { OriginalSerumMarket, SerumMarket } from '../../../../../src/connectors/serum/serum.types';
import { patch } from '../../../../services/patch';
import { default as config } from '../serumConfig';

const disablePatches = false;

const patches = (solana: Solana, serum: Serum) => {
  const patches = new Map();

  patches.set('solana.init', () => {
    if (disablePatches) return;

    patch(solana, 'init', () => {
    });
  });

  patches.set('solana.ready', () => {
    if (disablePatches) return;

    patch(solana, 'ready', () => {
      return true;
    });
  });

  patches.set('solana.getKeyPair', () => {
    if (disablePatches) return;

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
  });

  patches.set('serum.ready', () => {
    if (disablePatches) return;

    patch(serum, 'ready', () => {
      return true;
    });
  });

  patches.set('serum.init', () => {
    if (disablePatches) return;

    const connection = serum.getConnection();
    // eslint-disable-next-line
      // @ts-ignore
    connection.originalGetAccountInfo = connection.getAccountInfo;

    patch(connection, 'getAccountInfo', async (
      publicKey: PublicKey,
      commitment?: Commitment,
    ): Promise<AccountInfo<Buffer> | null> => {
      // eslint-disable-next-line
      // @ts-ignore
      const result = await connection.originalGetAccountInfo(publicKey, commitment);

      console.log('getAccountInfo:\npublicKey:\n', publicKey.toString(), '\ncommitment:\n', commitment, '\nresult:\n', JSON.stringify(result), '\n');

      return result;
    });

    patch(serum, 'init', () => {
    });
  });

  patches.set('serum.serumGetMarketsInformation', () => {
    if (disablePatches) return;

    patch(serum, 'serumGetMarketsInformation', () => {
      return [
        {
          'address': 'B37pZmwrwXHjpgvd9hHDAx1yeDsNevTnbbrN9W12BoGK',
          'deprecated': true,
          'name': 'soALEPH/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'CAgAeMD7quTdnr6RPa7JySQpjf3irAmefYNdTb6anemq',
          'deprecated': true,
          'name': 'BTC/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'ASKiV944nKg1W9vsf7hf3fTsjawK6DwLwrnB2LH9n61c',
          'deprecated': true,
          'name': 'soETH/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'Cdp72gDcYMCLLk3aDkPxjeiirKoFqK38ECm8Ywvk94Wi',
          'deprecated': true,
          'name': 'SOL/soUSDC',
          'programId': 'BJ3jrUzddfuSrZHXSCxMUUQsjKEyLmuuyZebkcaFp2fg'
        },
        {
          'address': '68J6nkWToik6oM9rTatKSR5ibVSykAtzftBUEAvpRsys',
          'deprecated': true,
          'name': 'SRM/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '8Jzed8Fafu1RU1CQDWdiETSrqAJy1ukZ5JL6Pma3p3a2',
          'deprecated': true,
          'name': 'SRM/SOL',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '9wDmxsfwaDb2ysmZpBLzxKzoWrF1zHzBN7PV5EmJe19R',
          'deprecated': true,
          'name': 'soSUSHI/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'GbQSffne1NcJbS4jsewZEpRGYVR4RNnuVUN8Ht6vAGb6',
          'deprecated': true,
          'name': 'soSXP/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '7kgkDyW7dmyMeP8KFXzbcUZz1R2WHsovDZ7n3ihZuNDS',
          'deprecated': true,
          'name': 'MSRM/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'FZqrBXz7ADGsmDf1TM9YgysPUfvtG8rJiNUrqDpHc9Au',
          'deprecated': true,
          'name': 'soFTT/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'FJg9FUtbN3fg3YFbMCFiZKjGh5Bn4gtzxZmtxFzmz9kT',
          'deprecated': true,
          'name': 'soYFI/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '7GZ59DMgJ7D6dfoJTpszPayTRyua9jwcaGJXaRMMF1my',
          'deprecated': true,
          'name': 'soLINK/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'uPNcBgFhrLW3FtvyYYbBUi53BBEQf9e4NPgwxaLu5Hn',
          'deprecated': true,
          'name': 'soHGET/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '3puWJFZyCso14EdxhywjD7xqyTarpsULx483mzvqxQRW',
          'deprecated': true,
          'name': 'soCREAM/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '8Ae7Uhigx8k4fKdJG7irdPCVDZLvWsJfeTH2t5fr3TVD',
          'deprecated': true,
          'name': 'soUBXT/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'Hze5AUX4Qp1cTujiJ4CsAMRGn4g6ZpgXsmptFn3xxhWg',
          'deprecated': true,
          'name': 'soHNT/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'FJq4HX3bUSgF3yQZ8ADALtJYfAyr9fz36SNG18hc3dgF',
          'deprecated': true,
          'name': 'soFRONT/soUSDC',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'BZMuoQ2i2noNUXMdrRDivc7MwjGspNJTCfZkdHMwK18T',
          'deprecated': true,
          'name': 'soALEPH/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '5LgJphS6D5zXwUVPU7eCryDBkyta3AidrJ5vjNU6BcGW',
          'deprecated': true,
          'name': 'BTC/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'DmEDKZPXXkWgaYiKgWws2ZXWWKCh41eryDPRVD4zKnD9',
          'deprecated': true,
          'name': 'soETH/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'EBFTQNg2QjyxV7WDDenoLbfLLXLcbSz6w1YrdTCGPWT5',
          'deprecated': true,
          'name': 'SOL/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '8YmQZRXGizZXYPCDmxgjwB8X8XN4PZG7MMwNg76iAmPZ',
          'deprecated': true,
          'name': 'SRM/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '9vFuX2BizwinWjkZLQTmThDcNMFEcY3wVXYuqnRQtcD',
          'deprecated': true,
          'name': 'soSUSHI/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'C5NReXAeQhfjiDCGPFj1UUmDxDqF8v2CUVKoYuQqb4eW',
          'deprecated': true,
          'name': 'soSXP/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '58H7ZRmiyWtsrz2sQGz1qQCMW6n7447xhNNehUSQGPj5',
          'deprecated': true,
          'name': 'MSRM/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'ES8skmkEeyH1BYFThd2FtyaFKhkqtwH7XWp8mXptv3vg',
          'deprecated': true,
          'name': 'soFTT/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'Gw78CYLLFbgmmn4rps9KoPAnNtBQ2S1foL2Mn6Z5ZHYB',
          'deprecated': true,
          'name': 'soYFI/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'WjfsTPyrvUUrhGJ9hVQFubMnKDcnQS8VxSXU7L2gLcA',
          'deprecated': true,
          'name': 'soLINK/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '2ZmB255T4FVUugpeXTFxD6Yz5GE47yTByYvqSTDUbk3G',
          'deprecated': true,
          'name': 'soHGET/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FGJtCDXoHLHjagP5Ht6xcUFt2rW3z8MJPe87rFKP2ZW6',
          'deprecated': true,
          'name': 'soCREAM/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7K6MPog6LskZmyaYwqtLvRUuedoiE68nirbQ9tK3LasE',
          'deprecated': true,
          'name': 'soUBXT/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '9RyozJe3bkAFfH3jmoiKHjkWCoLTxn7aBQSi6YfaV6ab',
          'deprecated': true,
          'name': 'soHNT/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'AGtBbGuJZiv3Ko3dfT4v6g4kCqnNc9DXfoGLe5HpjmWx',
          'deprecated': true,
          'name': 'soFRONT/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'AA1HSrsMcRNzjaQfRMTNarHR9B7e4U79LJ2319UtiqPF',
          'deprecated': true,
          'name': 'soAKRO/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'AUAobJdffexcoJBMeyLorpShu3ZtG9VvPEPjoeTN4u5Z',
          'deprecated': true,
          'name': 'soHXRO/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'GpdYLFbKHeSeDGqsnQ4jnP7D1294iBpQcsN1VPwhoaFS',
          'deprecated': true,
          'name': 'soUNI/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'sxS9EdTx1UPe4j2c6Au9f1GKZXrFj5pTgNKgjGGtGdY',
          'deprecated': true,
          'name': 'soKEEP/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'CfnnU38ACScF6pcurxSB3FLXeZmfFYunVKExeUyosu5P',
          'deprecated': true,
          'name': 'soMATH/soUSDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7NR5GDouQYkkfppVkNhpa4HfJ2LwqUQymE3b4CYQiYHa',
          'deprecated': true,
          'name': 'soALEPH/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'CVfYa8RGXnuDBeGmniCcdkBwoLqVxh92xB1JqgRQx3F',
          'deprecated': true,
          'name': 'BTC/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'H5uzEytiByuXt964KampmuNCurNDwkVVypkym75J2DQW',
          'deprecated': true,
          'name': 'soETH/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7xMDbYTCqQEcK2aM9LbetGtNFJpzKdfXzLL5juaLh4GJ',
          'deprecated': true,
          'name': 'SOL/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'CDdR97S8y96v3To93aKvi3nCnjUrbuVSuumw8FLvbVeg',
          'deprecated': true,
          'name': 'SRM/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7LVJtqSrF6RudMaz5rKGTmR3F3V5TKoDcN6bnk68biYZ',
          'deprecated': true,
          'name': 'soSUSHI/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '13vjJ8pxDMmzen26bQ5UrouX8dkXYPW1p3VLVDjxXrKR',
          'deprecated': true,
          'name': 'soSXP/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'AwvPwwSprfDZ86beBJDNH5vocFvuw4ZbVQ6upJDbSCXZ',
          'deprecated': true,
          'name': 'MSRM/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FfDb3QZUdMW2R2aqJQgzeieys4ETb3rPrFFfPSemzq7R',
          'deprecated': true,
          'name': 'soFTT/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '4QL5AQvXdMSCVZmnKXiuMMU83Kq3LCwVfU8CyznqZELG',
          'deprecated': true,
          'name': 'soYFI/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7JCG9TsCx3AErSV3pvhxiW4AbkKRcJ6ZAveRmJwrgQ16',
          'deprecated': true,
          'name': 'soLINK/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '3otQFkeQ7GNUKT3i2p3aGTQKS2SAw6NLYPE5qxh3PoqZ',
          'deprecated': true,
          'name': 'soHGET/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '2M8EBxFbLANnCoHydypL1jupnRHG782RofnvkatuKyLL',
          'deprecated': true,
          'name': 'soCREAM/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '3UqXdFtNBZsFrFtRGAWGvy9R8H6GJR2hAyGRdYT9BgG3',
          'deprecated': true,
          'name': 'soUBXT/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '9jiasgdYGGh34fAbBQSwkKe1dYSapXbjy2sLsYpetqFp',
          'deprecated': true,
          'name': 'soHNT/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7oKqJhnz9b8af8Mw47dieTiuxeaHnRYYGBiqCrRpzTRD',
          'deprecated': true,
          'name': 'soFRONT/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'F1rxD8Ns5w4WzVcTRdaJ96LG7YKaA5a25BBmM32yFP4b',
          'deprecated': true,
          'name': 'soAKRO/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '6ToedDwjRCvrcKX7fnHSTA9uABQe1dcLK6YgS5B9M3wo',
          'deprecated': true,
          'name': 'soHXRO/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FURvCsDUiuUaxZ13pZqQbbfktFGWmQVTHz7tL992LQVZ',
          'deprecated': true,
          'name': 'soUNI/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'EcfDRMrEJ3yW4SgrRyyxTPoKqAZDNSBV8EerigT7BNSS',
          'deprecated': true,
          'name': 'soKEEP/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '2bPsJ6bZ9KDLfJ8QgSN1Eb4mRsbAiaGyHN6cJkoVLpwd',
          'deprecated': true,
          'name': 'soMATH/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'B1GypajMh7S8zJVp6M1xMfu6zGsMgvYrt3cSn9wG7Dd6',
          'deprecated': true,
          'name': 'soTOMO/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'rPTGvVrNFYzBeTEcYnHiaWGNnkSXsWNNjUgk771LkwJ',
          'deprecated': true,
          'name': 'soLUA/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FrDavxi4QawYnQY259PVfYUjUvuyPNfqSXbLBqMnbfWJ',
          'deprecated': true,
          'name': 'FIDA/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'CVn1nJ5Utuseyy2qqwrpYoJz9Y7jjYonVL4UYvcCepDH',
          'deprecated': true,
          'name': 'KIN/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'BqjGW7ousAizgs8VrHo5SR1LxTksAQPtb8cKZZiNvX5D',
          'deprecated': true,
          'name': 'MAPS/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'GcoKtAmTy5QyuijXSmJKBtFdt99e6Buza18Js7j9AJ6e',
          'deprecated': false,
          'name': 'soALEPH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'A8YFbxQYFVqKZaoYJLLUVcQiWP7G2MeEgW5wsAQgMvFw',
          'deprecated': false,
          'name': 'BTC/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4tSvZvnbyzHXLMTiFonMyxZoHmFqau1XArcRCVHLZ5gX',
          'deprecated': false,
          'name': 'soETH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'ByRys5tuUWDgL73G8JBAEfkdFf8JWBzPBDHsBVQ5vbQA',
          'deprecated': false,
          'name': 'SRM/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'A1Q9iJDVVS8Wsswr9ajeZugmj64bQVCYLZQLra2TMBMo',
          'deprecated': false,
          'name': 'soSUSHI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4LUro5jaPaTurXK737QAxgJywdhABnFAMQkXX4ZyqqaZ',
          'deprecated': false,
          'name': 'soSXP/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4VKLSYdvrQ5ngQrt1d2VS8o4ewvb2MMUZLiejbnGPV33',
          'deprecated': false,
          'name': 'MSRM/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2Pbh1CvRVku1TgewMfycemghf6sU9EyuFDcNXqvRmSxc',
          'deprecated': false,
          'name': 'soFTT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7qcCo8jqepnjjvB5swP4Afsr3keVBs6gNpBTNubd1Kr2',
          'deprecated': false,
          'name': 'soYFI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3hwH1txjJVS8qv588tWrjHfRxdqNjBykM1kMcit484up',
          'deprecated': false,
          'name': 'soLINK/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '88vztw7RTN6yJQchVvxrs6oXUDryvpv9iJaFa1EEmg87',
          'deprecated': false,
          'name': 'soHGET/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7nZP6feE94eAz9jmfakNJWPwEKaeezuKKC5D1vrnqyo2',
          'deprecated': false,
          'name': 'soCREAM/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2wr3Ab29KNwGhtzr5HaPCyfU1qGJzTUAN4amCLZWaD1H',
          'deprecated': false,
          'name': 'soUBXT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'CnUV42ZykoKUnMDdyefv5kP6nDSJf7jFd7WXAecC6LYr',
          'deprecated': false,
          'name': 'soHNT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '9Zx1CvxSVdroKMMWf2z8RwrnrLiQZ9VkQ7Ex3syQqdSH',
          'deprecated': false,
          'name': 'soFRONT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5CZXTTgVZKSzgSA3AFMN5a2f3hmwmmJ6hU8BHTEJ3PX8',
          'deprecated': false,
          'name': 'soAKRO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '6Pn1cSiRos3qhBf54uBP9ZQg8x3JTardm1dL3n4p29tA',
          'deprecated': false,
          'name': 'soHXRO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '6JYHjaQBx6AtKSSsizDMwozAEDEZ5KBsSUzH7kRjGJon',
          'deprecated': false,
          'name': 'soUNI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'J7cPYBrXVy8Qeki2crZkZavcojf2sMRyQU7nx438Mf8t',
          'deprecated': false,
          'name': 'soMATH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '8BdpjpSD5n3nk8DQLqPUyTZvVqFu6kcff5bzUX5dqDpy',
          'deprecated': false,
          'name': 'soTOMO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4xyWjQ74Eifq17vbue5Ut9xfFNfuVB116tZLEpiZuAn8',
          'deprecated': false,
          'name': 'soLUA/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'jyei9Fpj2GtHLDDGgcuhDacxYLLiSyxU4TY7KxB2xai',
          'deprecated': false,
          'name': 'SRM/SOL',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT',
          'deprecated': false,
          'name': 'SOL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'E14BKBhDWD4EuTkWj1ooZezesGxMW8LPCps4W5PuzZJo',
          'deprecated': false,
          'name': 'FIDA/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'Bn6NPyr6UzrFAwC4WmvPvDr2Vm8XSUnFykM2aQroedgn',
          'deprecated': false,
          'name': 'KIN/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3A8XQRWXC7BjLpgLDDBhQJLT5yPCzS16cGYRKHkKxvYo',
          'deprecated': false,
          'name': 'MAPS/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3rgacody9SvM88QR83GHaNdEEx4Fe2V2ed5GJp2oeKDr',
          'deprecated': false,
          'name': 'soKEEP/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'EmCzMQfXMgNHcnRoFwAdPe1i2SuiSzMj1mx6wu3KN2uA',
          'deprecated': true,
          'name': 'soALEPH/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '8AcVjMG2LTbpkjNoyq8RwysokqZunkjy3d5JDzxC6BJa',
          'deprecated': true,
          'name': 'BTC/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'HfCZdJ1wfsWKfYP2qyWdXTT5PWAGWFctzFjLH48U1Hsd',
          'deprecated': true,
          'name': 'soETH/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '8mDuvJJSgoodovMRYArtVVYBbixWYdGzR47GPrRT65YJ',
          'deprecated': true,
          'name': 'SOL/soUSDT',
          'programId': 'BJ3jrUzddfuSrZHXSCxMUUQsjKEyLmuuyZebkcaFp2fg'
        },
        {
          'address': 'HARFLhSq8nECZk4DVFKvzqXMNMA9a3hjvridGMFizeLa',
          'deprecated': true,
          'name': 'SRM/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'DzFjazak6EKHnaB2w6qSsArnj28CV1TKd2Smcj9fqtHW',
          'deprecated': true,
          'name': 'soSUSHI/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'GuvWMATdEV6DExWnXncPYEzn4ePWYkvGdC8pu8gsn7m7',
          'deprecated': true,
          'name': 'soSXP/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'H4snTKK9adiU15gP22ErfZYtro3aqR9BTMXiH3AwiUTQ',
          'deprecated': true,
          'name': 'MSRM/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'DHDdghmkBhEpReno3tbzBPtsxCt6P3KrMzZvxavTktJt',
          'deprecated': true,
          'name': 'soFTT/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '5zu5bTZZvqESAAgFsr12CUMxdQvMrvU9CgvC1GW8vJdf',
          'deprecated': true,
          'name': 'soYFI/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'F5xschQBMpu1gD2q1babYEAVJHR1buj1YazLiXyQNqSW',
          'deprecated': true,
          'name': 'soLINK/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'BAbc9baz4hV1hnYjWSJ6cZDRjfvziWbYGQu9UFkcdUmx',
          'deprecated': true,
          'name': 'soHGET/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'EBxJWA2nLV57ZntbjizxH527ZjPNLT5cpUHMnY5k3oq',
          'deprecated': true,
          'name': 'soCREAM/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '46VdEkj4MJwZinwVb3Y7DUDpVXLNb9YW7P2waKU3vCqr',
          'deprecated': true,
          'name': 'soUBXT/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'Hc22rHKrhbrZBaQMmhJvPTkp1yDr31PDusU8wKoqFSZV',
          'deprecated': true,
          'name': 'soHNT/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': 'HFoca5HKwiTPpw9iUY5iXWqzkXdu88dS7YrpSvt2uhyF',
          'deprecated': true,
          'name': 'soFRONT/soUSDT',
          'programId': '4ckmDgGdxQoPDLUkDT3vHgSAkzA3QRdNq5ywwY4sUSJn'
        },
        {
          'address': '5xnYnWca2bFwC6cPufpdsCbDJhMjYCC59YgwoZHEfiee',
          'deprecated': true,
          'name': 'soALEPH/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'EXnGBBSamqzd3uxEdRLUiYzjJkTwQyorAaFXdfteuGXe',
          'deprecated': true,
          'name': 'BTC/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '5abZGhrELnUnfM9ZUnvK6XJPoBU5eShZwfFPkdhAC7o',
          'deprecated': true,
          'name': 'soETH/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7xLk17EQQ5KLDLDe44wCmupJKJjTGd8hs3eSVVhCx932',
          'deprecated': true,
          'name': 'SOL/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'H3APNWA8bZW2gLMSq5sRL41JSMmEJ648AqoEdDgLcdvB',
          'deprecated': true,
          'name': 'SRM/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '4uZTPc72sCDcVRfKKii67dTPm2Xe4ri3TYnGcUQrtnU9',
          'deprecated': true,
          'name': 'soSUSHI/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '33GHmwG9woY95JuWNi74Aa8uKvysSXxif9P1EwwkrCRz',
          'deprecated': true,
          'name': 'soSXP/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FUaF58sDrgbqakHTR8RUwRLauSofRTjqyCsqThFPh6YM',
          'deprecated': true,
          'name': 'MSRM/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '5NqjQVXLuLSDnsnQMfWp3rF9gbWDusWG4B1Xwtk3rZ5S',
          'deprecated': true,
          'name': 'soFTT/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '97NiXHUNkpYd1eb2HthSDGhaPfepuqMAV3QsZhAgb1wm',
          'deprecated': true,
          'name': 'soYFI/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'hBswhpNyz4m5nt4KwtCA7jYXvh7VmyZ4TuuPmpaKQb1',
          'deprecated': true,
          'name': 'soLINK/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'GaeUpY7CT8rjoeVGjY1t3mJJDd1bdXxYWtrGSpsVFors',
          'deprecated': true,
          'name': 'soHGET/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7qq9BABQvTWKZuJ5fX2PeTKX6XVtduEs9zW9WS21fSzN',
          'deprecated': true,
          'name': 'soCREAM/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'DCHvVahuLTNWBGUtEzF5GrTdx5FRpxqEJiS6Ru1hrDfD',
          'deprecated': true,
          'name': 'soUBXT/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'DWjJ8VHdGYBxDQYdrRBVDWkHswrgjuBFEv5pBhiRoPBz',
          'deprecated': true,
          'name': 'soHNT/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '56eqxJYzPigm4FkigiBdsfebjMgAbKNh24E7oiKLBtye',
          'deprecated': true,
          'name': 'soFRONT/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FQbCNSVH3RgosCPB4CJRstkLh5hXkvuXzAjQzT11oMYo',
          'deprecated': true,
          'name': 'soAKRO/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'Fs5xtGUmJTYo8Ao75M3R3m3mVX53KMUhzfXCmyRLnp2P',
          'deprecated': true,
          'name': 'soHXRO/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'ChKV7mxecPqFPGYJjhzowPHDiLKFWXXVujUiE3EWxFcg',
          'deprecated': true,
          'name': 'soUNI/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '6N3oU7ALvn2RPwdpYVzPBgQJ8njT29inBbS2tSrwx8fh',
          'deprecated': true,
          'name': 'soKEEP/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '5P6dJbyKySFXMYNWiEcNQu8xPRYsehYzCeVpae9Ueqrg',
          'deprecated': true,
          'name': 'soMATH/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'H7c8FcQPJ2E5tJmpWBPSi7xCAbk8immdtUxKFRUyE4Ro',
          'deprecated': true,
          'name': 'soTOMO/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '7PSeX1AEtBY9KvgegF5rUh452VemMh7oDzFtJgH7sxMG',
          'deprecated': true,
          'name': 'soLUA/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'AF2oQQaLtcrTnQyVs3EPTdyw57TPaK6njKYDq2Qw7LqP',
          'deprecated': true,
          'name': 'soSWAG/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '9TE15E5h61zJ5VmQAAHkGrAuQdFTth33aBbKdcrppZBp',
          'deprecated': true,
          'name': 'FIDA/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '8HEaA1vSA5mGQoHcvRPNibnuZvnUpSjJJru9HJNH3SqM',
          'deprecated': true,
          'name': 'KIN/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '8EuuEwULFM7n7zthPjC7kA64LPRzYkpAyuLFiLuVg7D4',
          'deprecated': true,
          'name': 'soUSDT/USDC',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': '8grUs4WZoTs4KJ8LfRNUBs6SNkMTp5BnVRzJgQ2ranDT',
          'deprecated': true,
          'name': 'MAPS/soUSDT',
          'programId': 'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o'
        },
        {
          'address': 'FoCuWt4KboucUg2PwmQ3dbkvLqYPLnAo1Rsm8p7QPyf',
          'deprecated': true,
          'name': 'soALEPH/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5r8FfnbNYcQbS1m4CYmoHYGjBtu6bxfo6UJHNRfzPiYH',
          'deprecated': true,
          'name': 'BTC/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '71CtEComq2XdhGNbXBuYPmosAjMCPSedcgbNi5jDaGbR',
          'deprecated': true,
          'name': 'soETH/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'EZyQ9zyqQsw3QcsLksoWyd1UFVjHZkzRx8N4ZMnZQrS2',
          'deprecated': true,
          'name': 'SRM/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '6ERBjj692XHLWwWSRAUpiKenXshcwmPqhMy7RMapeoKa',
          'deprecated': true,
          'name': 'soSUSHI/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'CQ3kAGxPmpBbak2RSHWyMeRhyLYbH6oVZHJxgjzDLpLW',
          'deprecated': true,
          'name': 'soSXP/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2Hqn46jhwaQMQ3zEnHtxrWxQZom6qwLXAgdsFJM1Srwh',
          'deprecated': true,
          'name': 'MSRM/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'G5jqZNo2UVCTnJxgEhKCYvqFRs3MxsnH8Bervq3rfLoL',
          'deprecated': true,
          'name': 'soFTT/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'CbwtTHEpfTnCyLw4GoTbKk7WyrXkuATLfLadY2odBSsY',
          'deprecated': true,
          'name': 'soYFI/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5GjhBAYx8pYeCeUQt7rt93KQZnoQFuDq9Jx4iqq97Mip',
          'deprecated': true,
          'name': 'soLINK/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '9jMPV9E23pTirMjC7vz5suRNkd25311G3Httg7jTib8R',
          'deprecated': true,
          'name': 'soCREAM/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'DsSz9KWT97T4RewRTqTNDpNFQyxMPcuYNAJw2xHAzSiZ',
          'deprecated': true,
          'name': 'soUBXT/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3k1sURztjxhjYczjyioQ7y2UkMB6K5Ksi3SWvLeLx6Ex',
          'deprecated': true,
          'name': 'soHNT/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'B791G8UCahfmABVcR2wPAMK6LJnuqxSAqiG6wX3mmVVM',
          'deprecated': true,
          'name': 'soFRONT/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '95f7fxfUh8WqUTrdjorHRXm6rTfkWqr23ioGMmKMjedP',
          'deprecated': true,
          'name': 'soAKRO/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'H4RxtmQ4P3TYPt78G3DuHgaGzyFct6MfaeYneLB5PyeG',
          'deprecated': true,
          'name': 'soHXRO/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7myaZEGZf9m72T1Mqm8GTx5MnmSFS5NCXSwRP18W4EA3',
          'deprecated': true,
          'name': 'soUNI/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7cRKzNoqjF9VtzvdnP129VYP3izivk9iY3jMJBMzREVT',
          'deprecated': true,
          'name': 'soHGET/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'GV9fYzdwipoaagXFxe5tzDMPcmSVQati5CUvBPsEZThH',
          'deprecated': true,
          'name': 'soMATH/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'AaMLXcwYYi5fA41JNCB2ukAmQyKHitYx5NnpsiWWev6R',
          'deprecated': true,
          'name': 'soTOMO/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5ZeNLrduGi3WkH9CPwv2Zpbkh38MH8v63aSi2aBUW23g',
          'deprecated': true,
          'name': 'soLUA/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'Ec1aq54XKH9o5fe169cU2sCcxxTP54eeQCe77SpizKuc',
          'deprecated': true,
          'name': 'soUSDT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'G3uhFg2rBFunHUXtCera13vyQ5KCS8Hx3d4HohLoZbT5',
          'deprecated': true,
          'name': 'SOL/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2NMTG7tFZidRpQk9Sf4dgQyJb9HxKCyXjQdiuXww3sKm',
          'deprecated': true,
          'name': 'soSWAG/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7QpJAiwGmqY1SiucjfPXvgeWwCobyV6hZSgzMysZX6Ww',
          'deprecated': true,
          'name': 'FIDA/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'CmLhvXARncLncE1949XBfQWeJh6Zvw3FE5A3Z5ecPYQH',
          'deprecated': true,
          'name': 'KIN/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'FhP3X2ptdi7L1RtWK9Vfow5dyzD92gfXiA57e8eqxvka',
          'deprecated': true,
          'name': 'MAPS/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'DE7xJE2EkaV81wLabDMuhBzUwFhhwfURLdz1aXBBQZQ1',
          'deprecated': true,
          'name': 'soKEEP/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5nLJ22h1DUfeCfwbFxPYK8zbfbri7nA9bXoDcR8AcJjs',
          'deprecated': false,
          'name': 'MSRM/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7dLVkUfBVfCGkFhSXDCq1ukM9usathSgS716t643iFGF',
          'deprecated': false,
          'name': 'soETH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '8afKwzHR3wJE7W7Y5hvQkngXh6iTepSZuutRMMy96MjR',
          'deprecated': false,
          'name': 'soSXP/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'cgani53cMZgYfRMgSrNekJTMaLmccRfspsfTbXWRg7u',
          'deprecated': false,
          'name': 'soCEL/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'Gyp1UGRgbrb6z8t7fpssxEKQgEmcJ4pVnWW3ds2p6ZPY',
          'deprecated': false,
          'name': 'soALEPH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4ztJEvQyryoYagj2uieep3dyPwG2pyEwb2dKXTwmXe82',
          'deprecated': false,
          'name': 'soCREAM/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'HEGnaVL5i48ubPBqWAhodnZo8VsSLzEM3Gfc451DnFj9',
          'deprecated': false,
          'name': 'soKEEP/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '8FpuMGLtMZ7Wt9ZvyTGuTVwTwwzLYfS5NZWcHxbP1Wuh',
          'deprecated': false,
          'name': 'soHNT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '5GAPymgnnWieGcRrcghZdA3aanefqa4cZx1ZSE8UTyMV',
          'deprecated': false,
          'name': 'soMAPS/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'AADohBGxvf7bvixs2HKC3dG2RuU3xpZDwaTzYFJThM8U',
          'deprecated': false,
          'name': 'TRYB/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'EbV7pPpEvheLizuYX3gUCvWM8iySbSRAhu2mQ5Vz2Mxf',
          'deprecated': false,
          'name': 'FIDA/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'FcPet5fz9NLdbXwVM6kw2WTHzRAD7mT78UjwTpawd7hJ',
          'deprecated': false,
          'name': 'soRSR/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'AtNnsY1AyRERWJ8xCskfz38YdvruWVJQUVXgScC1iPb',
          'deprecated': false,
          'name': 'SRM/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'teE55QrL4a4QSfydR9dnHF97jgCfptpuigbb53Lo95g',
          'deprecated': false,
          'name': 'RAY/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'C1EuT9VokAKLiW7i2ASnZUvxDoKuKkCpDDeNxAptuNe4',
          'deprecated': false,
          'name': 'BTC/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'Hr3wzG8mZXNHV7TuL6YqtgfVUesCqMxGYCEyP3otywZE',
          'deprecated': false,
          'name': 'soFTT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'HLvRdctRB48F9yLnu9E24LUTRt89D48Z35yi1HcxayDf',
          'deprecated': false,
          'name': 'soAKRO/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2SSnWNrc83otLpfRo792P6P3PESZpdr8cu2r8zCE6bMD',
          'deprecated': false,
          'name': 'soUNI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'F1T7b6pnR8Pge3qmfNUfW6ZipRDiGpMww6TKTrRU4NiL',
          'deprecated': false,
          'name': 'soUBXT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'HWHvQhFmJB3NUcu1aihKmrKegfVxBEHzwVX6yZCKEsi1',
          'deprecated': false,
          'name': 'SOL/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '35tV8UsHH8FnSAi3YFRrgCu4K9tb883wKnAXpnihot5r',
          'deprecated': false,
          'name': 'soLUA/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '6DgQRTpJTnAYBSShngAVZZDq7j9ogRN1GfSQ3cq9tubW',
          'deprecated': false,
          'name': 'soSUSHI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '2WghiBkDL2yRhHdvm8CpprrkmfguuQGJTCDfPSudKBAZ',
          'deprecated': false,
          'name': 'soMATH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'ErQXxiNfJgd4fqQ58PuEw5xY35TZG84tHT6FXf5s4UxY',
          'deprecated': false,
          'name': 'soHGET/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'CGC4UgWwqA9PET6Tfx6o6dLv94EK2coVkPtxgNHuBtxj',
          'deprecated': false,
          'name': 'soFRONT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'GnKPri4thaGipzTbp8hhSGSrHgG4F8MFiZVrbRn16iG2',
          'deprecated': false,
          'name': 'soTOMO/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '6bxuB5N3bt3qW8UnPNLgMMzDq5sEH8pFmYJYGgzvE11V',
          'deprecated': false,
          'name': 'soAAVE/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '7cknqHAuGpfVXPtFoJpFvUjJ8wkmyEfbFusmwMfNy3FE',
          'deprecated': false,
          'name': 'MAPS/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4absuMsgemvdjfkgdLQq1zKEjw3dHBoCWkzKoctndyqd',
          'deprecated': false,
          'name': 'soHXRO/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '4nCFQr8sahhhL4XJ7kngGFBmpkmyf3xLzemuMhn6mWTm',
          'deprecated': false,
          'name': 'KIN/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3Xg9Q4VtZhD4bVYJbTfgGWFV5zjE3U7ztSHa938zizte',
          'deprecated': false,
          'name': 'soYFI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '3yEZ9ZpXSQapmKjLAGKZEzUNA1rcupJtsDp5mPBWmGZR',
          'deprecated': false,
          'name': 'soLINK/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'J2XSt77XWim5HwtUM8RUwQvmRXNZsbMKpp5GTKpHafvf',
          'deprecated': false,
          'name': 'soSWAG/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': '77quYg4MGneUdjgXCunt9GgM1usmrxKY31twEy3WHwcS',
          'deprecated': false,
          'name': 'USDT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'GKLev6UHeX1KSDCyo2bzyG6wqhByEzDBkmYTxEdmYJgB',
          'deprecated': false,
          'name': 'OXY/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'address': 'HdBhZrnrxpje39ggXnTb6WuTWVvj5YKcSHwYGQCRsVj',
          'deprecated': false,
          'name': 'OXY/soUSDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'OXY/USDC',
          'address': 'GZ3WBFsqntmERPwumFEYgrX2B7J7G11MzNZAy7Hje27X',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'xCOPE/USDC',
          'address': '7MpMwArporUHEGW7quUpkPZp5L5cHPs9eKUfKCdaPHq2',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'COPE/USDC',
          'address': '6fc7v3PmjZG9Lk2XTot6BywGyYLkBQuzuFKd4FpCsPxk',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'MER/USDC',
          'address': 'HhvDWug3ftYNx5148ZmrQxzvEmohN2pKVNiRT4TVoekF',
          'deprecated': true,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'MER/USDT',
          'address': '6HwcY27nbeb933UkEcxqJejtjWLfNQFWkGCjAVNes6g7',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'MER/USDC',
          'address': 'G4LcexdCzzJUKZfqyVDQFzpkjhB1JoCNL8Kooxi9nJz5',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'SNY/USDC',
          'address': 'DPfj2jYwPaezkCmUNm5SSYfkrkz8WFqwGLcxDDUsN3gA',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'SLRS/USDC',
          'address': '2Gx3UfV831BAh8uQv1FKSPKS9yajfeeD8GJ4ZNb2o2YP',
          'deprecated': false,
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin'
        },
        {
          'name': 'ETHV/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'HrgkuJryyKRserkoz7LBFYkASzhXHWp9XA6fRYCA6PHb'
        },
        {
          'name': 'IETHV/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5aoLj1bySDhhWjo7cLfT3pF2gqNGd63uEJ9HMSfASESL'
        },
        {
          'name': 'SBR/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'HXBi8YBwbh4TXF6PjVw81m8Z3Cc4WBofvauj5SBFdgUs'
        },
        {
          'name': 'renBTC/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '74Ciu5yRzhe8TFTHvQuEVbFZJrbnCMRoohBK33NNiPtv'
        },
        {
          'name': 'renDOGE/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5FpKCWYXgHWZ9CdDMHjwxAfqxJLdw2PRXuAmtECkzADk'
        },
        {
          'name': 'DXL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'DYfigimKWc5VhavR4moPBibx9sMcWYVSjVdWvPztBPTa'
        },
        {
          'name': 'MNGO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '3d4rzwpy9iGdCZvgxcu7B1YocYffVLsQXPXkBZKt2zLc'
        },
        {
          'name': 'CYS/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '6V6y6QFi17QZC9qNRpVp7SaPiHpCTp2skbRQkUyZZXPW'
        },
        {
          'name': 'POLIS/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'HxFLKUAmAMLz1jtT3hbvCMELwH5H9tpM2QugP8sKyfhW'
        },
        {
          'name': 'ATLAS/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Di66GTLsV64JgCCYGVcY21RZ173BHkjJVgPyezNN7P1K'
        },
        {
          'name': 'LIKE/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '3WptgZZu34aiDrLMUiPntTYZGNZ72yT1yxHYxSdbTArX'
        },
        {
          'name': 'MSOL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '6oGsL2puUgySccKzn9XA9afqF217LfxP5ocq4B3LWsjy'
        },
        {
          'name': 'MSOL/SOL',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5cLrMai1DsLRYc1Nio9qMTicsWtvzjzZfJPXyAoF4t1Z'
        },
        {
          'name': 'AAVE/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '8WZrmdpLckptiVKd2fPHPjewRVYQGQkjxi9vzRYG1sfs'
        },
        {
          'name': 'AAVE/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'LghsMERQWQFK3zWMTrUkoyAJARQw2wSmcYZjexeN3zy'
        },
        {
          'name': 'AKRO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'G3h8NZgJozk9crme2me6sKDJuSQ12mNCtvC9NbSWqGuk'
        },
        {
          'name': 'AKRO/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'DvbiPxKzuXZPcmUcYDqBz1tvUrXYPsNrRAjSeuwHtmEA'
        },
        {
          'name': 'ALEPH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Fw4mvuE7KZmTjQPxP2sRpHwPDfRMWnKBupFZGyW9CAQH'
        },
        {
          'name': 'ALEPH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'GZeHR8uCTVoHVDZFRVXTgm386DK1EKehy9yMS3BFChcL'
        },
        {
          'name': 'CEL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '79ESpYSb2hM14KTRXPZUwDkxUGC5irE2esd1vxdXfnZz'
        },
        {
          'name': 'CEL/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'J9ww1yufRNDDbUbDXmew2mW2ozkx7cme7dMvKjMQVHrL'
        },
        {
          'name': 'CREAM/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '4pdQ2D4gehMhGu4z9jeQbEPUFbTxB5qcPr3zCynjJGyp'
        },
        {
          'name': 'CREAM/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '6fspxMfBmYFTGFBDN5MU33A55i2MkGr7eSjBLPCAU6y9'
        },
        {
          'name': 'ETH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '8Gmi2HhZmwQPVdCwzS7CM66MGstMXPcTVHA7jF19cLZz'
        },
        {
          'name': 'ETH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'ch7kmPrtoQUSEPBggcNAvLGiMQkJagVwd3gDYfd8m7Q'
        },
        {
          'name': 'FRONT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'B95oZN5HCLGmFAhbzReWBA9cuSGPFQAXeuhm2FfpdrML'
        },
        {
          'name': 'FRONT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'DZTYyy1L5Pr6DmTtYY5bEuU9g3LQ4XGvuYiN3zS25yG7'
        },
        {
          'name': 'FTT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '2wteg25ch227n4Rh1CN4WNrDZXBpRBpWJ48mEC2K7f4r'
        },
        {
          'name': 'FTT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'BoHojHESAv4McZx9gXd1bWTZMq25JYyGz4qL1m5C3nvk'
        },
        {
          'name': 'HGET/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '27e1mB6UoPohbc3MmwMXu5QM7b2E3k5Mbhwv6JguwyXg'
        },
        {
          'name': 'HGET/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'BdRzTEKb7Qdu4tWts5zXjwcpQErZxEzvShKZ5QcthMag'
        },
        {
          'name': 'HXRO/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'CBb5zXwNRB73WVjs2m21P5prcEZa6SWmej74Vzxh8dRm'
        },
        {
          'name': 'HXRO/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '3BScwNxtMrEcQ5VTHyXHYQR98dTaxfyXGaLkuSjBY1dW'
        },
        {
          'name': 'LINK/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'FJMjxMCiDKn16TLhXUdEbVDH5wC6k9EHYJTcrH6NcbDE'
        },
        {
          'name': 'LINK/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Gr2KmhK7Upr4uW56B1QQrJuhhgmot6zAHJeZALTMStiX'
        },
        {
          'name': 'LUA/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'J9imTcEeahZqKuaoQaPcCeSGCMWL8qSACpK4B7bC8NN4'
        },
        {
          'name': 'LUA/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'BMJ3CvQZ57cNnuc3Lz5Pb6cW6Sr9kZGz3qz2bJQTE24A'
        },
        {
          'name': 'MATH/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'G8L1YLrktaG1t8YBMJs3CwV96nExvJJCSpw3DARPDjE2'
        },
        {
          'name': 'MATH/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'CkvNfATB7nky8zPLuwS9bgcFbVRkQdkd5zuKEovyo9rs'
        },
        {
          'name': 'RAY/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '2xiv8A5xrJ7RnGdxXB42uFEkYHJjszEhaJyKKt4WaLep'
        },
        {
          'name': 'RSR/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'GqgkxEswUwHBntmzb5GpUhKrVpJhzreSruZycuJwdNwB'
        },
        {
          'name': 'RSR/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '2j2or38X2FUbpkK4gkgvjDtqN3ibkKw3v5yn7o2gHqPc'
        },
        {
          'name': 'SUSHI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '3uWVMWu7cwMnYMAAdtsZNwaaqeeeZHARGZwcExnQiFay'
        },
        {
          'name': 'SUSHI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'T3aC6qcPAJtX1gqkckfSxBPdPWziz5fLYRt5Dz3Nafq'
        },
        {
          'name': 'SWAG/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'wSkeLMv3ktJyLm51bvQWxY2saGKqGxbnUFimPxbgEvQ'
        },
        {
          'name': 'SWAG/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '6URQ4zFWvPm1fhJCKKWorrh8X3mmTFiDDyXEUmSf8Rb2'
        },
        {
          'name': 'SXP/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'G5F84rfqmWqzZv5GBpSn8mMwW8zJ2B4Y1GpGupiwjHNM'
        },
        {
          'name': 'SXP/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '2FQbPW1ticJz2SMMbEXxbKWJKmw1wLc6ggSP2HyzdMen'
        },
        {
          'name': 'UBXT/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Hh4p7tJpqkGW6xsHM2LiPPMpJg43fwn5TbmVmfrURdLY'
        },
        {
          'name': 'UBXT/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5xhjc3ZtAwnBK3qsaro28VChL7WrxY9N4SG6UZpYxpGc'
        },
        {
          'name': 'UNI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'B7b5rjQuqQCuGqmUBWmcCTqaL3Z1462mo4NArqty6QFR'
        },
        {
          'name': 'UNI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'FrKM6kJtAjXknHPEpkrQtJSXZwUxV5dq26wDpc4YjQST'
        },
        {
          'name': 'YFI/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'BiJXGFc1c4gyPpv9HLRJoKbZewWQrTCHGuxYKjYMQJpC'
        },
        {
          'name': 'YFI/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '9sue9TZAeUhNtNAPPGb9dke7rkJeXktGD3u8ZC37GWnQ'
        },
        {
          'name': 'AVAX/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'E8JQstcwjuqN5kdMyUJLNuaectymnhffkvfg1j286UCr'
        },
        {
          'name': 'AXSet/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'HZCheduA4nsSuQpVww1TiyKZpXSAitqaXxjBD2ymg22X'
        },
        {
          'name': 'BNB/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '4UPUurKveNEJgBqJzqHPyi8DhedvpYsMXi7d43CjAg2f'
        },
        {
          'name': 'BNB/USDT',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'FjbKNZME5yVSC1R3HJM99kB3yir3q3frS5MteMFD72sV'
        },
        {
          'name': 'GALA/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'F7WJsoxTWQRmAwAyFe9APmuVv4HqmhchFtdbR9dvAUDm'
        },
        {
          'name': 'MATICpo/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5WRoQxE59966N2XfD2wYy1uhuyKeoVJ9NBMH6r6RNYEF'
        },
        {
          'name': 'ROSE/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'EybAYkmRKCyD4w8AErTG1bqmnvT85LFuPQPMCc8J3yD'
        },
        {
          'name': 'SAND/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '3FE2g3cadTJjN3C7gNRavwnv7Yh9Midq7h9KgTVUE7tR'
        },
        {
          'name': 'LUNA/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'HBTu8hNaoT3VyiSSzJYa8jwt9sDGKtJviSwFa11iXdmE'
        },
        {
          'name': 'SHIB/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Er7Jp4PADPVHifykFwbVoHdkL1RtZSsx9zGJrPJTrCgW'
        },
        {
          'name': 'UST/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '8WmckvEoVGZvtN8knjdzFGbWJ3Sr4BcWdyzSYuCrD4YK'
        },
        {
          'name': 'FAB/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'Cud48DK2qoxsWNzQeTL5D8sAiHsGwG8Ev1VMNcYLayxt'
        },
        {
          'name': 'JET/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '6pQMoHDC2o8eeFxyTKtfnsr8d48hKFWsRpLHAqVHH2ZP'
        },
        {
          'name': 'scnSOL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': 'D52sefGCWho2nd5UGxWd7wCftAzeNEMNYZkdEPGEdQTb'
        },
        {
          'name': 'stSOL/USDC',
          'programId': '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin',
          'deprecated': false,
          'address': '5F7LGsP1LPtaRV7vVKgxwNYX4Vf22xvuzyXjyar7jJqp'
        }
      ];
    });
  });

  patches.set('serum.serumLoadMarket', (marketName: string) => {
    if (disablePatches) return;

    let decoded: any;
    let baseMintDecimals: number;
    let quoteMintDecimals: number;
    let options: MarketOptions = {};
    let programId: PublicKey;
    let layoutOverride: any = undefined;

    if (marketName == 'SOL/USDT')
      return patch(serum, 'serumLoadMarket', () => {
        decoded = {
          'accountFlags': {
            'initialized': true,
            'market': true,
            'openOrders': false,
            'requestQueue': false,
            'eventQueue': false,
            'bids': false,
            'asks': false
          },
          'ownAddress': {
            '_bn': {
              'negative': 0,
              'words': [
                49577050,
                60793582,
                51820691,
                45396522,
                52226207,
                40900766,
                63799177,
                20257679,
                58457337,
                4017917,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'vaultSignerNonce': {
            'negative': 0,
            'words': [
              1,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'baseMint': {
            '_bn': {
              'negative': 0,
              'words': [
                1,
                3932160,
                62216586,
                57699244,
                31114297,
                25571341,
                42464820,
                33952749,
                5766827,
                108258,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteMint': {
            '_bn': {
              'negative': 0,
              'words': [
                35684964,
                61649799,
                19689513,
                13561355,
                37721690,
                64292118,
                64369042,
                46701662,
                39890925,
                3375171,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseVault': {
            '_bn': {
              'negative': 0,
              'words': [
                60904772,
                29754738,
                17932130,
                24223565,
                51268627,
                56302869,
                2046986,
                5118171,
                42951444,
                279579,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseDepositsTotal': {
            'negative': 0,
            'words': [
              5204224,
              1462759,
              0
            ],
            'length': 2,
            'red': null
          },
          'baseFeesAccrued': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'quoteVault': {
            '_bn': {
              'negative': 0,
              'words': [
                21460027,
                61712920,
                25749427,
                59011742,
                35698260,
                29026051,
                30498439,
                37601488,
                1715327,
                55862,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteDepositsTotal': {
            'negative': 0,
            'words': [
              6034189,
              80084,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteFeesAccrued': {
            'negative': 0,
            'words': [
              19119230,
              366,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteDustThreshold': {
            'negative': 0,
            'words': [
              100,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'requestQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                49157522,
                10493457,
                41296620,
                25907589,
                39255403,
                48251996,
                390619,
                53117193,
                44632965,
                3730645,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'eventQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                4568850,
                41018851,
                9203239,
                8520744,
                62298682,
                25391152,
                23643000,
                1610287,
                39635533,
                3752422,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'bids': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                47760321,
                26508842,
                20289,
                62018210,
                26171811,
                45078285,
                50059994,
                5997225,
                53099886,
                423538,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'asks': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                37960452,
                40718140,
                34798621,
                49563771,
                46815935,
                52121654,
                2802817,
                63769111,
                2446669,
                2281280,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'baseLotSize': plainToInstance(BN, {
            'negative': 0,
            'words': [
              32891136,
              1,
              0
            ],
            'length': 2,
            'red': null
          }),
          'quoteLotSize': {
            'negative': 0,
            'words': [
              100,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'feeRateBps': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'referrerRebatesAccrued': {
            'negative': 0,
            'words': [
              16916234,
              277,
              0
            ],
            'length': 2,
            'red': null
          }
        };
        baseMintDecimals = 9;
        quoteMintDecimals = 6;
        programId = new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin');

        const result: SerumMarket = new SerumMarket(
          decoded,
          baseMintDecimals,
          quoteMintDecimals,
          options,
          programId,
          layoutOverride,
        );

        return result;
      });

    if (marketName == 'SOL/USDC')
      return patch(serum, 'serumLoadMarket', () => {
        decoded = {
          'accountFlags': {
            'initialized': true,
            'market': true,
            'openOrders': false,
            'requestQueue': false,
            'eventQueue': false,
            'bids': false,
            'asks': false
          },
          'ownAddress': {
            '_bn': {
              'negative': 0,
              'words': [
                26018567,
                14776919,
                28034075,
                59284737,
                51262457,
                65625083,
                1152255,
                55801679,
                47341921,
                180380,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'vaultSignerNonce': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'baseMint': {
            '_bn': {
              'negative': 0,
              'words': [
                45234311,
                5550907,
                66944856,
                21722793,
                48303155,
                17851049,
                17134808,
                13235221,
                8788632,
                106692,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteMint': {
            '_bn': {
              'negative': 0,
              'words': [
                1,
                3932160,
                62216586,
                57699244,
                31114297,
                25571341,
                42464820,
                33952749,
                5766827,
                108258,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseVault': {
            '_bn': {
              'negative': 0,
              'words': [
                17964175,
                20159379,
                67006066,
                24327066,
                56860329,
                50206077,
                50351354,
                12249716,
                31387212,
                3333227,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseDepositsTotal': {
            'negative': 0,
            'words': [
              15680480,
              555,
              0
            ],
            'length': 2,
            'red': null
          },
          'baseFeesAccrued': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'quoteVault': {
            '_bn': {
              'negative': 0,
              'words': [
                31141713,
                46416027,
                15635641,
                27806531,
                29606409,
                20628033,
                47019912,
                42709131,
                7793456,
                3955572,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteDepositsTotal': {
            'negative': 0,
            'words': [
              25646722,
              12132,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteFeesAccrued': {
            'negative': 0,
            'words': [
              55978082,
              10,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteDustThreshold': {
            'negative': 0,
            'words': [
              100,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'requestQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                28927857,
                21778013,
                37524426,
                7502414,
                52827466,
                414353,
                30011115,
                5243382,
                24858936,
                3638953,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'eventQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                1846889,
                31243600,
                29215629,
                7402331,
                61309385,
                65352562,
                5646493,
                65245983,
                59432082,
                192965,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'bids': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                36428024,
                57444340,
                56001551,
                45405055,
                3192719,
                10052171,
                59765612,
                23150980,
                61781196,
                866520,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'asks': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                55718172,
                6493555,
                25447133,
                58488966,
                7711860,
                42812444,
                52647533,
                37555581,
                28154325,
                1629927,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'baseLotSize': plainToInstance(BN, {
            'negative': 0,
            'words': [
              100000,
              0,
              0
            ],
            'length': 1,
            'red': null
          }),
          'quoteLotSize': {
            'negative': 0,
            'words': [
              100000,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'feeRateBps': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'referrerRebatesAccrued': {
            'negative': 0,
            'words': [
              3340330,
              353,
              0
            ],
            'length': 2,
            'red': null
          }
        };
        baseMintDecimals = 6;
        quoteMintDecimals = 9;
        programId = new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin');

        const result: SerumMarket = new SerumMarket(
          decoded,
          baseMintDecimals,
          quoteMintDecimals,
          options,
          programId,
          layoutOverride,
        );

        return result;
      });

    if (marketName == 'SRM/SOL')
      return patch(serum, 'serumLoadMarket', () => {
        decoded = {
          'accountFlags': {
            'initialized': true,
            'market': true,
            'openOrders': false,
            'requestQueue': false,
            'eventQueue': false,
            'bids': false,
            'asks': false
          },
          'ownAddress': {
            '_bn': {
              'negative': 0,
              'words': [
                49577050,
                60793582,
                51820691,
                45396522,
                52226207,
                40900766,
                63799177,
                20257679,
                58457337,
                4017917,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'vaultSignerNonce': {
            'negative': 0,
            'words': [
              1,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'baseMint': {
            '_bn': {
              'negative': 0,
              'words': [
                1,
                3932160,
                62216586,
                57699244,
                31114297,
                25571341,
                42464820,
                33952749,
                5766827,
                108258,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteMint': {
            '_bn': {
              'negative': 0,
              'words': [
                35684964,
                61649799,
                19689513,
                13561355,
                37721690,
                64292118,
                64369042,
                46701662,
                39890925,
                3375171,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseVault': {
            '_bn': {
              'negative': 0,
              'words': [
                60904772,
                29754738,
                17932130,
                24223565,
                51268627,
                56302869,
                2046986,
                5118171,
                42951444,
                279579,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'baseDepositsTotal': {
            'negative': 0,
            'words': [
              60703744,
              1476579,
              0
            ],
            'length': 2,
            'red': null
          },
          'baseFeesAccrued': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'quoteVault': {
            '_bn': {
              'negative': 0,
              'words': [
                21460027,
                61712920,
                25749427,
                59011742,
                35698260,
                29026051,
                30498439,
                37601488,
                1715327,
                55862,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'quoteDepositsTotal': {
            'negative': 0,
            'words': [
              52892785,
              80845,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteFeesAccrued': {
            'negative': 0,
            'words': [
              19119230,
              366,
              0
            ],
            'length': 2,
            'red': null
          },
          'quoteDustThreshold': {
            'negative': 0,
            'words': [
              100,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'requestQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                49157522,
                10493457,
                41296620,
                25907589,
                39255403,
                48251996,
                390619,
                53117193,
                44632965,
                3730645,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'eventQueue': {
            '_bn': {
              'negative': 0,
              'words': [
                4568850,
                41018851,
                9203239,
                8520744,
                62298682,
                25391152,
                23643000,
                1610287,
                39635533,
                3752422,
                0
              ],
              'length': 10,
              'red': null
            }
          },
          'bids': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                47760321,
                26508842,
                20289,
                62018210,
                26171811,
                45078285,
                50059994,
                5997225,
                53099886,
                423538,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'asks': plainToClassFromExist(new PublicKey(PublicKey.default), {
            '_bn': {
              'negative': 0,
              'words': [
                37960452,
                40718140,
                34798621,
                49563771,
                46815935,
                52121654,
                2802817,
                63769111,
                2446669,
                2281280,
                0
              ],
              'length': 10,
              'red': null
            }
          }),
          'baseLotSize': plainToInstance(BN, {
            'negative': 0,
            'words': [
              32891136,
              1,
              0
            ],
            'length': 2,
            'red': null
          }),
          'quoteLotSize': {
            'negative': 0,
            'words': [
              100,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'feeRateBps': {
            'negative': 0,
            'words': [
              0,
              0,
              0
            ],
            'length': 1,
            'red': null
          },
          'referrerRebatesAccrued': {
            'negative': 0,
            'words': [
              16916234,
              277,
              0
            ],
            'length': 2,
            'red': null
          }
        };
        baseMintDecimals = 9;
        quoteMintDecimals = 6;
        programId = new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin');

        const result: SerumMarket = new SerumMarket(
          decoded,
          baseMintDecimals,
          quoteMintDecimals,
          options,
          programId,
          layoutOverride,
        );

        return result;
      });

    throw new Error('Unrecognized option.');
  });

  patches.set('serum.serumMarketLoadAsks', async (marketName: string) => {
    if (disablePatches) return;

    let market: SerumMarket = (await serum.getMarket(marketName)).market;

    if (marketName == 'SOL/USDT') {
       return patch(market, 'loadAsks', () => {
          const parsed: Record<number, number> = JSON.parse("");

          const data = Buffer.from(Object.values(parsed));

          return Orderbook.decode(market as unknown as OriginalSerumMarket, data);
        })
    }
  });

  patches.set('serum.serumMarketLoadBids', async (marketName: string) => {
    if (disablePatches) return;

    let market: SerumMarket = (await serum.getMarket(marketName)).market;

    if (marketName == 'SOL/USDT') {
       return patch(market, 'loadBids', () => {
          const parsed: Record<number, number> = JSON.parse("");

          const data = Buffer.from(Object.values(parsed));

          return Orderbook.decode(market as unknown as OriginalSerumMarket, data);
        })
    }
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
