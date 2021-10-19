import level, { LevelDB } from 'level';

const db: LevelDB = level('gateway.level', { createIfMissing: true });

export async function dbSaveNonce(
  chain: string,
  chainId: number,
  address: string,
  nonce: number
): Promise<void> {
  return db.put(chain + '/' + String(chainId) + '/' + address, nonce);
}

export async function dbGetChainNonces(
  chain: string,
  chainId: number
): Promise<Record<string, number>> {
  // await db.open();
  const stream = db.createReadStream();
  const result = await new Promise<Record<string, number>>(
    (resolve, reject) => {
      const results: Record<string, number> = {};
      stream
        .on('data', ({ key, value }) => {
          const splitKey = key.split('/');
          if (
            splitKey.length === 3 &&
            splitKey[0] === chain &&
            splitKey[1] === String(chainId)
          ) {
            results[splitKey[2]] = value;
          }
        })
        .on('error', (err) => {
          reject(err);
        })
        .on('close', () => {
          resolve(resulsts);
        })
        .on('end', () => {
          resolve(results);
        });
    }
  );

  return result;
}
