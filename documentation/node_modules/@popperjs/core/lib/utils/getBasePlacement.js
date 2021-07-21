import { auto } from "../enums.js";
export default function getBasePlacement(placement) {
  return placement.split('-')[0];
}