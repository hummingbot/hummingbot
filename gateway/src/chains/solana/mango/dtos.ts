export interface BadRequestError {
  value: string;
  msg: string;
  param: string;
  location: string;
}

export interface RequestErrorCustom {
  msg: string;
}
