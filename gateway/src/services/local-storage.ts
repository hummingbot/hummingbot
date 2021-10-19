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

export async function dbDeleteNonce(
  chain: string,
  chainId: number,
  address: string
): Promise<void> {
  return db.del(chain + '/' + String(chainId) + '/' + address);
}

export async function dbGetChainNonces(
  chain: string,
  chainId: number
): Promise<Record<string, number>> {
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
            results[splitKey[2]] = parseInt(value);
          }
        })
        .on('error', (err) => {
          reject(err);
        })
        .on('end', () => {
          resolve(results);
        });
    }
  );

  return result;
}
