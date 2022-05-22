import { ethers } from "ethers";
import BigNumber from "bignumber.js";
import {_getBalances, _prepareAddresses, ensureAllowance, ensureAllowanceEstimateGas, hasAllowance} from "./utils";
import { _ensureAllowance, toBN, toStringFromBN } from './utils';
import { curve, ALIASES } from "./curve";
import { DictInterface } from "./interfaces";


export const getCrv = async (...addresses: string[] | string[][]): Promise<DictInterface<string> | string> => {
    addresses = _prepareAddresses(addresses);
    const rawBalances = (await _getBalances([ALIASES.crv], addresses));

    const balances: DictInterface<string> = {};
    for (const address of addresses) {
        balances[address] = rawBalances[address].shift() as string;
    }

    return addresses.length === 1 ? balances[addresses[0]] : balances
}

export const getLockedAmountAndUnlockTime = async (...addresses: string[] | string[][]):
    Promise<DictInterface<{ lockedAmount: string, unlockTime: number }> | { lockedAmount: string, unlockTime: number }> => {
    addresses = _prepareAddresses(addresses);
    const veContract = curve.contracts[ALIASES.voting_escrow].multicallContract;
    const contractCalls = addresses.map((address: string) => veContract.locked(address));

    const response: (string | number)[][] = (await curve.multicallProvider.all(contractCalls) as ethers.BigNumber[][]).map(
        (value: ethers.BigNumber[]) => [ethers.utils.formatUnits(value[0]), Number(ethers.utils.formatUnits(value[1], 0)) * 1000]);

    const result: DictInterface<{ lockedAmount: string, unlockTime: number }> = {};
    addresses.forEach((addr: string, i: number) => {
        result[addr] = { lockedAmount: response[i][0] as string, unlockTime: response[i][1] as number};
    });

    return addresses.length === 1 ? result[addresses[0]] : result
}

export const getVeCrv = async (...addresses: string[] | string[][]): Promise<DictInterface<string> | string> => {
    addresses = _prepareAddresses(addresses);

    const veContract = curve.contracts[ALIASES.voting_escrow].multicallContract;
    const contractCalls = addresses.map((address: string) => veContract.balanceOf(address));
    const response: string[] = (await curve.multicallProvider.all(contractCalls) as ethers.BigNumber[]).map(
        (value: ethers.BigNumber) => ethers.utils.formatUnits(value));

    const result: DictInterface<string> = {};
    addresses.forEach((addr: string, i: number) => {
        result[addr] = response[i];
    });

    return addresses.length === 1 ? result[addresses[0]] : result
}

export const getVeCrvPct = async (...addresses: string[] | string[][]): Promise<DictInterface<string> | string> => {
    addresses = _prepareAddresses(addresses);

    const veContract = curve.contracts[ALIASES.voting_escrow].multicallContract;
    const contractCalls = [veContract.totalSupply()];
    addresses.forEach((address: string) => {
        contractCalls.push(veContract.balanceOf(address));
    });
    const response: BigNumber[] = (await curve.multicallProvider.all(contractCalls) as ethers.BigNumber[]).map(
        (value: ethers.BigNumber) => toBN(value));

    const [veTotalSupply] = response.splice(0, 1);

    const resultBN: DictInterface<BigNumber> = {};
    addresses.forEach((acct: string, i: number) => {
        resultBN[acct] = response[i].div(veTotalSupply).times(100);
    });

    const result: DictInterface<string> = {};
    for (const entry of Object.entries(resultBN)) {
        result[entry[0]] = toStringFromBN(entry[1]);
    }

    return addresses.length === 1 ? result[addresses[0]] : result
}

export const isApproved = async (amount: string): Promise<boolean> => {
    return await hasAllowance([ALIASES.crv], [amount], curve.signerAddress, ALIASES.voting_escrow);
}

export const approveEstimateGas = async (amount: string): Promise<number> => {
    return await ensureAllowanceEstimateGas([ALIASES.crv], [amount], ALIASES.voting_escrow);
}

export const approve = async (amount: string): Promise<string[]> => {
    return await ensureAllowance([ALIASES.crv], [amount], ALIASES.voting_escrow);
}

export const createLockEstimateGas = async (amount: string, days: number): Promise<number> => {
    const crvBalance = await getCrv() as string;

    if (Number(crvBalance) < Number(amount)) {
        throw Error(`Not enough . Actual: ${crvBalance}, required: ${amount}`);
    }

    if (!(await hasAllowance([ALIASES.crv], [amount], curve.signerAddress, ALIASES.voting_escrow))) {
        throw Error("Token allowance is needed to estimate gas")
    }

    const _amount = ethers.utils.parseUnits(amount);
    const unlockTime = Math.floor(Date.now() / 1000) + (days * 86400);

    return (await curve.contracts[ALIASES.voting_escrow].contract.estimateGas.create_lock(_amount, unlockTime, curve.constantOptions)).toNumber()
}

export const createLock = async (amount: string, days: number): Promise<string> => {
    const _amount = ethers.utils.parseUnits(amount);
    const unlockTime = Math.floor(Date.now() / 1000) + (days * 86400);
    await _ensureAllowance([ALIASES.crv], [_amount], ALIASES.voting_escrow);
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    await curve.updateFeeData();
    const gasLimit = (await contract.estimateGas.create_lock(_amount, unlockTime, curve.constantOptions)).mul(130).div(100);
    return (await contract.create_lock(_amount, unlockTime, { ...curve.options, gasLimit })).hash
}

export const increaseAmountEstimateGas = async (amount: string): Promise<number> => {
    const crvBalance = await getCrv() as string;

    if (Number(crvBalance) < Number(amount)) {
        throw Error(`Not enough. Actual: ${crvBalance}, required: ${amount}`);
    }

    if (!(await hasAllowance([ALIASES.crv], [amount], curve.signerAddress, ALIASES.voting_escrow))) {
        throw Error("Token allowance is needed to estimate gas")
    }

    const _amount = ethers.utils.parseUnits(amount);
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    return (await contract.estimateGas.increase_amount(_amount, curve.constantOptions)).toNumber()
}

export const increaseAmount = async (amount: string): Promise<string> => {
    const _amount = ethers.utils.parseUnits(amount);
    await _ensureAllowance([ALIASES.crv], [_amount], ALIASES.voting_escrow);
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    await curve.updateFeeData();
    const gasLimit = (await contract.estimateGas.increase_amount(_amount, curve.constantOptions)).mul(130).div(100);
    return (await contract.increase_amount(_amount, { ...curve.options, gasLimit })).hash
}

export const increaseUnlockTimeEstimateGas = async (days: number): Promise<number> => {
    const { unlockTime } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };
    const newUnlockTime = Math.floor(unlockTime / 1000) + (days * 86400);
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    return (await contract.estimateGas.increase_unlock_time(newUnlockTime, curve.constantOptions)).toNumber()
}

export const increaseUnlockTime = async (days: number): Promise<string> => {
    const { unlockTime } = await getLockedAmountAndUnlockTime() as { lockedAmount: string, unlockTime: number };
    const newUnlockTime = Math.floor(unlockTime / 1000) + (days * 86400);
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    await curve.updateFeeData();
    const gasLimit = (await contract.estimateGas.increase_unlock_time(newUnlockTime, curve.constantOptions)).mul(130).div(100);
    return (await contract.increase_unlock_time(newUnlockTime, { ...curve.options, gasLimit })).hash
}

export const withdrawLockedCrvEstimateGas = async (): Promise<number> => {
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    return (await contract.estimateGas.withdraw(curve.constantOptions)).toNumber()
}

export const withdrawLockedCrv = async (): Promise<string> => {
    const contract = curve.contracts[ALIASES.voting_escrow].contract;

    await curve.updateFeeData();
    const gasLimit = (await contract.estimateGas.withdraw(curve.constantOptions)).mul(130).div(100);
    return (await contract.withdraw({ ...curve.options, gasLimit })).hash
}
