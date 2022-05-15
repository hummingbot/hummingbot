import { AccountInfo, Commitment, Connection, PublicKey } from '@solana/web3.js';
// eslint-disable-next-line
// @ts-ignore
import { Buffer } from 'buffer';

// eslint-disable-next-line
// @ts-ignore
Connection.originalGetAccountInfo = Connection.getAccountInfo;

// eslint-disable-next-line
// @ts-ignore
Connection.getAccountInfo = async (
  publicKey: PublicKey,
  commitment?: Commitment,
): Promise<AccountInfo<Buffer> | null> => {
  // eslint-disable-next-line
  // @ts-ignore
  const result = await this.getAccountInfo(publicKey, commitment);

  console.log('getAccountInfo:\npublicKey:\n', publicKey.toString(), '\ncommitment:\n', commitment, '\nresult:\n', JSON.stringify(result), '\n');

  return result;
}
