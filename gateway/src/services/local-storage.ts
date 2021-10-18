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

export async function dbGetNonce(
  chain: string,
  chainId: number,
  address: string
): Promise<number | null> {
  const val = await db.get(chain + '/' + String(chainId) + '/' + address);
  if (typeof val === 'number') {
    return val;
  }
  return null;
}

export async function getChainNonces(
  chain: string,
  chainId: number
): Promise<Record<string, number>> {
  const results: Record<string, number> = {};
  // await db.open();
  await db.createReadStream().on('data', (data) => {
    const key = data.split('/');
    if (key.length === 3 && key[0] === chain && key[1] === String(chainId)) {
      results[key[2]] = data.value;
    }
  });

  return results;
}
