export const BTC_COINS_POLYGON: { [index: string]: string } = {
    wbtc: "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",   // WBTC
    renbtc: "0xDBf31dF14B66535aF65AaC99C32e9eA844e14501", // renBTC
    amwbtc: "0x5c2ed810328349100A66B82b78a1791B101C9D61",  // amWBTC
}
// @ts-ignore
export const BTC_COINS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(BTC_COINS_POLYGON).map((entry) => [entry[0], entry[1].toLowerCase()]));

export const ETH_COINS_POLYGON: { [index: string]: string } = {
    weth: "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",  // WETH
    amweth: "0x28424507fefb6f7f8E9D3860F56504E4e5f5f390", // amWETH
}
// @ts-ignore
export const ETH_COINS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(ETH_COINS_POLYGON).map((entry) => [entry[0], entry[1].toLowerCase()]));

export const LINK_COINS_POLYGON: { [index: string]: string } = {}
// @ts-ignore
export const LINK_COINS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(LINK_COINS_POLYGON).map((entry) => [entry[0], entry[1].toLowerCase()]));

export const EUR_COINS_POLYGON: { [index: string]: string } = {
    eurt: "0x7BDF330f423Ea880FF95fC41A280fD5eCFD3D09f",  // EURT
}
// @ts-ignore
export const EUR_COINS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(EUR_COINS_POLYGON).map((entry) => [entry[0], entry[1].toLowerCase()]));

export const USD_COINS_POLYGON: { [index: string]: string } = {
    dai: "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063",   // DAI
    usdc: "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  // USDC
    usdt: "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",  // USDT

    amdai: "0x27F8D03b3a2196956ED754baDc28D73be8830A6e",  // amDAI
    amusdc: "0x1a13F4Ca1d028320A707D99520AbFefca3998b7F", // amUSDC
    amusdt: "0x60D55F02A771d515e077c9C2403a1ef324885CeC", // amUSDT

    am3crv: "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD7D171", // am3CRV
}

// @ts-ignore
export const USD_COINS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(USD_COINS_POLYGON).map((entry) => [entry[0], entry[1].toLowerCase()]));

export const COINS_POLYGON: { [index: string]: string } = {
    ...BTC_COINS_POLYGON,
    ...ETH_COINS_POLYGON,
    ...LINK_COINS_POLYGON,
    ...EUR_COINS_POLYGON,
    ...USD_COINS_POLYGON,
    crv: "0x172370d5cd63279efa6d502dab29171933a610af",    // CRV
    matic: "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  // MATIC
}

export const DECIMALS_POLYGON: { [index: string]: number } = {
    "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063": 18, // DAI
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": 6,  // USDC
    "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": 6,  // USDT

    "0x27F8D03b3a2196956ED754baDc28D73be8830A6e": 18, // amDAI
    "0x1a13F4Ca1d028320A707D99520AbFefca3998b7F": 6,  // amUSDC
    "0x60D55F02A771d515e077c9C2403a1ef324885CeC": 6,  // amUSDT
    "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD7D171": 18,  // am3CRV

    "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6": 8,  // WBTC
    "0xDBf31dF14B66535aF65AaC99C32e9eA844e14501": 8,  // renBTC
    "0x5c2ed810328349100A66B82b78a1791B101C9D61": 8,  // amWBTC

    "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619": 18, // WETH
    "0x28424507fefb6f7f8E9D3860F56504E4e5f5f390": 18, // amWETH

    "0x7BDF330f423Ea880FF95fC41A280fD5eCFD3D09f": 6,  // EURT

    "0x172370d5cd63279efa6d502dab29171933a610af": 18,  // CRV
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": 18,  // MATIC
}

// @ts-ignore
export const DECIMALS_LOWER_CASE_POLYGON = Object.fromEntries(Object.entries(DECIMALS_POLYGON).map((entry) => [entry[0].toLowerCase(), entry[1]]));

export const cTokensPolygon = []
export const yTokensPolygon = []
export const ycTokensPolygon = []

export const aTokensPolygon = [
    "0x27F8D03b3a2196956ED754baDc28D73be8830A6e",  // amDAI
    "0x1a13F4Ca1d028320A707D99520AbFefca3998b7F",  // amUSDC
    "0x60D55F02A771d515e077c9C2403a1ef324885CeC",  // amUSDT
    "0x5c2ed810328349100A66B82b78a1791B101C9D61",  // amWBTC
    "0x28424507fefb6f7f8E9D3860F56504E4e5f5f390",  // amWETH
]
