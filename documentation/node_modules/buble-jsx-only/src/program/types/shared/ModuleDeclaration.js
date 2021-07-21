import Node from '../../Node.js';
import CompileError from '../../../utils/CompileError.js';

export default class ModuleDeclaration extends Node {
	initialise(transforms) {
		if (transforms.moduleImport)
			CompileError.missingTransform('modules', 'moduleImport', this);
		super.initialise(transforms);
	}
}
