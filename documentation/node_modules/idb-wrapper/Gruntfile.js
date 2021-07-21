/*global module,require */
module.exports = function (grunt) {

  'use strict';

  var fs = require('fs');

  var pkg = grunt.file.readJSON('package.json');

  var additionalCSS = [
    '.navbar { display: none; }',
    '#toc { top: 0; }'
  ];

  grunt.initConfig({

    pkg: pkg,

    jshint: {
      all: ['Gruntfile.js', pkg.main],
      options: {
        jshintrc: '.jshintrc'
      }
    },

    jsdoc: {
      dist: {
        src: [pkg.main],
        options: {
          destination: 'doc/' + pkg.version,
          private: false,
          template: './node_modules/jsdoc-oblivion/template',
          configure: 'conf.json'
        }
      }
    },

    closurecompiler: {
      minify: {
        files: {
          'idbstore.min.js': [pkg.main]
        },
        options: {
          'compilation_level': 'SIMPLE_OPTIMIZATIONS'
        }
      }
    },

    karma: {
      postbuild: {
        configFile: 'karma.conf.js',
        files: {
          src: [
            'idbstore.min.js',
            'test/**/*spec.js'
          ]
        }
      },
      dev: {
        configFile: 'karma.conf.js'
      }
    }
  });

  grunt.loadNpmTasks('grunt-contrib-jshint');
  grunt.loadNpmTasks('grunt-jsdoc');
  grunt.loadNpmTasks('grunt-closurecompiler');
  grunt.loadNpmTasks('grunt-karma');
  grunt.loadNpmTasks('grunt-contrib-copy');

  /* doc related code */

  var indexTemplate = '<!DOCTYPE html>' +
    '<html>' +
      '<title>Available IDBWrapper Documentation</title>' +
      '<p>Available IDBWrapper documentation:</p>' +
      '<ul>{{list}}</ul>' +
    '</html>';

  grunt.registerTask('modifyDocs', function () {
    var docPath = 'doc/' + pkg.version,
      styleSheet = docPath + '/styles/site.oblivion.css',
      css = grunt.file.read(styleSheet);

    css += additionalCSS.join('\n') + '\n';
    grunt.file.write(styleSheet, css);
  });

  grunt.registerTask('copyLatestDocs', function () {
    grunt.config.set('copy.docs', {
      cwd: 'doc/' + pkg.version,
      src: '**/*',
      dest: 'doc/latest/',
      expand: true
    });
    grunt.task.run('copy:docs');
  });

  grunt.registerTask('writeDocIndex', function () {
    var list = fs.readdirSync('doc').filter(function (entry) {
      return grunt.file.isDir('doc/' + entry);
    }).map(function (entry) {
      return '<li><a href="' + entry + '/IDBStore.html">' + entry + '</a></li>';
    }).join('');

    var index = indexTemplate.replace('{{list}}', list);
    grunt.file.write('doc/index.html', index);
  });


  //################//
  //   Main Tasks   //
  //################//

  grunt.registerTask('test', [
    'karma:dev'
  ]);

  grunt.registerTask('docs', [
    'jsdoc:dist',
    'modifyDocs',
    'copyLatestDocs',
    'writeDocIndex'
  ]);

  grunt.registerTask('build', [
    'jshint',
    'karma:dev',
    'closurecompiler',
    'karma:postbuild'
  ]);
};
