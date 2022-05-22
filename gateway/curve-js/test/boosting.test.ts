import { assert } from "chai";
import { BN } from "../src/utils";
import { getCrv, createLock, increaseAmount, increaseUnlockTime, getLockedAmountAndUnlockTime } from '../src/boosting';
import { curve } from "../src/curve";

describe('Boosting', function() {
    this.timeout(120000);
    let address = '';

    before(async function() {
        await curve.init('JsonRpc', {}, { gasPrice: 0 });
        address = curve.signerAddress;
    });

    it('Creates lock in Voting Escrow contract', async function () {
        const lockAmount = '1000';

        const initialCrvBalance: string = await getCrv() as string;
        const lockTime = Date.now();
        await createLock(lockAmount, 365);
        const crvBalance = await getCrv() as string;
        const { lockedAmount, unlockTime } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };

        assert.deepEqual(BN(lockedAmount), BN(initialCrvBalance).minus(BN(crvBalance)));
        assert.isAtLeast(unlockTime + (7 * 86400 * 1000), lockTime + (365 * 86400 * 1000));
    });

    it('Increases amount locked in Voting Escrow contract', async function () {
        const increaseLockAmount = '1000';

        const initialCrvBalance: string = await getCrv() as string;
        const { lockedAmount: initialLockedAmount } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };
        await increaseAmount(increaseLockAmount);
        const crvBalance = await getCrv() as string;
        const { lockedAmount } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };

        assert.deepEqual(BN(lockedAmount).minus(BN(initialLockedAmount)), BN(initialCrvBalance).minus(BN(crvBalance)));
    });

    it('Extends lock time', async function () {
        const { unlockTime: initialUnlockTime } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };
        await increaseUnlockTime(120);
        const { unlockTime } = await getLockedAmountAndUnlockTime(address) as { lockedAmount: string, unlockTime: number };

        assert.isAtLeast(unlockTime + (7 * 86400 * 1000), initialUnlockTime + (120 * 86400 * 1000));
    });
});
