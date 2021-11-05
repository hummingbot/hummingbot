export namespace PangolinConfig {
  export interface AvalancheNetworkConfig {
    routerAddress: string;
  }

  export interface PanConfig {
    fuji: AvalancheNetworkConfig;
    avalanche: AvalancheNetworkConfig;
  }

  export const config: PanConfig = {
    fuji: {
      routerAddress: '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
    },
    avalanche: {
      routerAddress: '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
    },
  };
}
