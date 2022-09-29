/**
 * Returns the new address.
 *
 * This function convert xdc address prefix to 0x.
 */
export function convertXdcPublicKey(publicKey: string): string {
  return publicKey.length === 43 && publicKey.slice(0, 3) === 'xdc' ? '0x' + publicKey.slice(3) : publicKey;
}

export function convertXdcPrivateKey(privateKey: string): string {
  return privateKey.length === 67 && privateKey.slice(0, 3) === 'xdc' ? '0x' + privateKey.slice(3) : privateKey;
}
