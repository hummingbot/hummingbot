'use strict';

exports.isClient = typeof window === 'object';
exports.isServer = typeof window !== 'object';
exports.isProd = process.env.NODE_ENV === 'production';
exports.isDev = process.env.NODE_ENV !== 'production';
