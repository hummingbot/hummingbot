import { PriceRequest, PriceResponse } from './amm.requests';

export const price = (req: PriceRequest): PriceResponse => {
  console.log(req);
  throw new Error('unimplemented');
};
