import {NanoOptions, NanoRenderer} from '../types/nano';
import {RuleAddon} from '../addon/rule';
import {SheetAddon} from '../addon/sheet';

type SheetPreset = (options: NanoOptions) => NanoRenderer & RuleAddon & SheetAddon;
