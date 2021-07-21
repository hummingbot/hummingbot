{
  'target_defaults': { 'includes': ['../common.gypi'] },
  'targets': [
    {
      'target_name': 'function_args',
      'sources': [ 'function_args.cc' ],
      'includes': [ '../except.gypi' ],
    },
    {
      'target_name': 'function_args_noexcept',
      'sources': [ 'function_args.cc' ],
      'includes': [ '../noexcept.gypi' ],
    },
    {
      'target_name': 'property_descriptor',
      'sources': [ 'property_descriptor.cc' ],
      'includes': [ '../except.gypi' ],
    },
    {
      'target_name': 'property_descriptor_noexcept',
      'sources': [ 'property_descriptor.cc' ],
      'includes': [ '../noexcept.gypi' ],
    },
  ]
}
