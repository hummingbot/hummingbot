import {
  providers,
  transactions as nearTransactions,
  utils,
  Account,
} from 'near-api-js';
import BN from 'bn.js';
import { AccessKeyView } from 'near-api-js/lib/providers/provider';
import {
  Transaction,
  transformTransactions,
  TransformedTransaction,
} from 'coinalpha-ref-sdk';

const validateAccessKey = (
  transaction: TransformedTransaction,
  accessKey: AccessKeyView
) => {
  if (accessKey.permission === 'FullAccess') {
    return accessKey;
  }

  // eslint-disable-next-line @typescript-eslint/naming-convention
  const { receiver_id, method_names } = accessKey.permission.FunctionCall;

  if (transaction.receiverId !== receiver_id) {
    return null;
  }

  return transaction.actions.every(
    (action: { type: string; params: { methodName: any; deposit: any } }) => {
      if (action.type !== 'FunctionCall') {
        return false;
      }

      const { methodName, deposit } = action.params;

      if (method_names.length && method_names.includes(methodName)) {
        return false;
      }

      return parseFloat(deposit) <= 0;
    }
  );
};

export const getSignedTransactions = async ({
  transactionsRef,
  account,
}: {
  transactionsRef: Transaction[];
  account: Account;
}) => {
  const AccountId: string = account.accountId;
  const networkId: string = account.connection.networkId;
  const transactions = transformTransactions(transactionsRef, AccountId);

  const block = await account.connection.provider.block({ finality: 'final' });

  const signedTransactions: Array<nearTransactions.SignedTransaction> = [];

  const publicKey = await account.connection.signer.getPublicKey(
    account.accountId,
    account.connection.networkId
  );
  if (!publicKey) {
    throw 'Wallet not properly initialized.';
  }

  const accessKey = await account.connection.provider.query<AccessKeyView>({
    request_type: 'view_access_key',
    finality: 'final',
    account_id: AccountId,
    public_key: publicKey.toString(),
  });

  for (let i = 0; i < transactions.length; i += 1) {
    const transaction = transactions[i];

    if (!validateAccessKey(transaction, accessKey)) {
      throw 'Account does not have access.';
    }

    const tx = nearTransactions.createTransaction(
      AccountId,
      utils.PublicKey.from(publicKey.toString()),
      transactions[i].receiverId,
      accessKey.nonce + i + 1,
      transaction.actions.map(
        (action: {
          params: { methodName: any; args: any; gas: any; deposit: any };
        }) => {
          const { methodName, args, gas, deposit } = action.params;
          return nearTransactions.functionCall(
            methodName,
            args,
            new BN(gas),
            new BN(deposit)
          );
        }
      ),
      utils.serialize.base_decode(block.header.hash)
    );

    const [, signedTx] = await nearTransactions.signTransaction(
      tx,
      account.connection.signer,
      transactions[i].signerId,
      networkId
    );
    signedTransactions.push(signedTx);
  }

  return signedTransactions;
};

export const sendTransactions = async ({
  signedTransactions,
  provider,
}: {
  signedTransactions: nearTransactions.SignedTransaction[];
  provider: providers.Provider;
}) => {
  const results: Array<providers.FinalExecutionOutcome> = [];

  for (const signedTransaction of signedTransactions) {
    results.push(await provider.sendTransactionAsync(signedTransaction));
  }

  return results;
};
