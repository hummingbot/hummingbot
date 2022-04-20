export namespace BalancerConfig {
  export interface NetworkConfig {
    balancerAddress: string;
  }

  export interface Config {
    mainnet: NetworkConfig;
    kovan: NetworkConfig;
  }

  export const config: Config = {
    mainnet: {
      balancerAddress: '0x3E66B66Fd1d0b02fDa6C811Da9E0547970DB2f21',
    },
    kovan: {
      balancerAddress: '0x4e67bf5bD28Dd4b570FBAFe11D0633eCbA2754Ec',
    },
  };
}
