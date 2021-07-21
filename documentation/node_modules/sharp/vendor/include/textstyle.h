/* Public API of the libtextstyle library.
   Copyright (C) 2006-2007, 2019 Free Software Foundation, Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

/* Written by Bruno Haible <bruno@clisp.org>, 2006, 2019.  */

#ifndef _TEXTSTYLE_H
#define _TEXTSTYLE_H

#include <stddef.h>
#include <stdio.h>
#include <textstyle/stdbool.h>
#include <textstyle/woe32dll.h>

/* Meta information.  */
#include <textstyle/version.h>

/* ----------------------------- From ostream.h ----------------------------- */

/* Describes the scope of a flush operation.  */
typedef enum
{
  /* Flushes buffers in this ostream_t.
     Use this value if you want to write to the underlying ostream_t.  */
  FLUSH_THIS_STREAM = 0,
  /* Flushes all buffers in the current process.
     Use this value if you want to write to the same target through a
     different file descriptor or a FILE stream.  */
  FLUSH_THIS_PROCESS = 1,
  /* Flushes buffers in the current process and attempts to flush the buffers
     in the kernel.
     Use this value so that some other process (or the kernel itself)
     may write to the same target.  */
  FLUSH_ALL = 2
} ostream_flush_scope_t;


/* An output stream is an object to which one can feed a sequence of bytes.  */

struct any_ostream_representation;
typedef struct any_ostream_representation * ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void ostream_write_mem (ostream_t first_arg, const void *data, size_t len);
extern void ostream_flush (ostream_t first_arg, ostream_flush_scope_t scope);
extern void ostream_free (ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Write a string's contents to a stream.  */
extern void ostream_write_str (ostream_t stream, const char *string);

#ifdef __cplusplus
}
#endif

/* ------------------------- From styled-ostream.h ------------------------- */

/* A styled output stream is an object to which one can feed a sequence of
   bytes, marking some runs of text as belonging to specific CSS classes,
   where the rendering of the CSS classes is defined through a CSS (cascading
   style sheet).  */

/* styled_ostream_t is a subtype of ostream_t.  */
typedef ostream_t styled_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void styled_ostream_write_mem (styled_ostream_t first_arg, const void *data, size_t len);
extern void styled_ostream_flush (styled_ostream_t first_arg, ostream_flush_scope_t scope);
extern void styled_ostream_free (styled_ostream_t first_arg);
extern void styled_ostream_begin_use_class (styled_ostream_t first_arg, const char *classname);
extern void styled_ostream_end_use_class (styled_ostream_t first_arg, const char *classname);
/* Like styled_ostream_flush (first_arg, FLUSH_THIS_STREAM), except that it
   leaves the destination with the current text style enabled, instead
   of with the default text style.
   After calling this function, you can output strings without newlines(!)
   to the underlying stream, and they will be rendered like strings passed
   to 'ostream_write_mem' or 'ostream_write_str'.  */
extern void styled_ostream_flush_to_current_style (styled_ostream_t stream);
#ifdef __cplusplus
}
#endif

/* -------------------------- From file-ostream.h -------------------------- */

/* file_ostream_t is a subtype of ostream_t.  */
typedef ostream_t file_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void file_ostream_write_mem (file_ostream_t first_arg, const void *data, size_t len);
extern void file_ostream_flush (file_ostream_t first_arg, ostream_flush_scope_t scope);
extern void file_ostream_free (file_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream referring to FP.
   Note that the resulting stream must be closed before FP can be closed.  */
extern file_ostream_t file_ostream_create (FILE *fp);


#ifdef __cplusplus
}
#endif

/* --------------------------- From fd-ostream.h --------------------------- */

/* fd_ostream_t is a subtype of ostream_t.  */
typedef ostream_t fd_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void fd_ostream_write_mem (fd_ostream_t first_arg, const void *data, size_t len);
extern void fd_ostream_flush (fd_ostream_t first_arg, ostream_flush_scope_t scope);
extern void fd_ostream_free (fd_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream referring to the file descriptor FD.
   FILENAME is used only for error messages.
   Note that the resulting stream must be closed before FD can be closed.  */
extern fd_ostream_t fd_ostream_create (int fd, const char *filename,
                                       bool buffered);


#ifdef __cplusplus
}
#endif

/* -------------------------- From term-ostream.h -------------------------- */

/* Querying and setting of text attributes.
   The stream has a notion of the current text attributes; they apply
   implicitly to all following output.  The attributes are automatically
   reset when the stream is closed.
   Note: Not all terminal types can actually render all attributes adequately.
   For example, xterm cannot render POSTURE_ITALIC nor the combination of
   WEIGHT_BOLD and UNDERLINE_ON.  */

/* Colors are represented by indices >= 0 in a stream dependent format.  */
typedef int term_color_t;
/* The value -1 denotes the default (foreground or background) color.  */
enum
{
  COLOR_DEFAULT = -1  /* unknown */
};

typedef enum
{
  WEIGHT_NORMAL = 0,
  WEIGHT_BOLD,
  WEIGHT_DEFAULT = WEIGHT_NORMAL
} term_weight_t;

typedef enum
{
  POSTURE_NORMAL = 0,
  POSTURE_ITALIC, /* same as oblique */
  POSTURE_DEFAULT = POSTURE_NORMAL
} term_posture_t;

typedef enum
{
  UNDERLINE_OFF = 0,
  UNDERLINE_ON,
  UNDERLINE_DEFAULT = UNDERLINE_OFF
} term_underline_t;

/* term_ostream_t is a subtype of ostream_t.  */
typedef ostream_t term_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void term_ostream_write_mem (term_ostream_t first_arg, const void *data, size_t len);
extern void term_ostream_flush (term_ostream_t first_arg, ostream_flush_scope_t scope);
extern void term_ostream_free (term_ostream_t first_arg);
extern term_color_t term_ostream_rgb_to_color (term_ostream_t first_arg, int red, int green, int blue);
extern term_color_t term_ostream_get_color (term_ostream_t first_arg);
extern void term_ostream_set_color (term_ostream_t first_arg, term_color_t color);
extern term_color_t term_ostream_get_bgcolor (term_ostream_t first_arg);
extern void term_ostream_set_bgcolor (term_ostream_t first_arg, term_color_t color);
extern term_weight_t term_ostream_get_weight (term_ostream_t first_arg);
extern void term_ostream_set_weight (term_ostream_t first_arg, term_weight_t weight);
extern term_posture_t term_ostream_get_posture (term_ostream_t first_arg);
extern void term_ostream_set_posture (term_ostream_t first_arg, term_posture_t posture);
extern term_underline_t term_ostream_get_underline (term_ostream_t first_arg);
extern void term_ostream_set_underline (term_ostream_t first_arg, term_underline_t underline);
/* Like term_ostream_flush (first_arg, FLUSH_THIS_STREAM), except that it
   leaves the terminal with the current text attributes enabled, instead of
   with the default text attributes.
   After calling this function, you can output strings without newlines(!)
   to the underlying file descriptor, and they will be rendered like strings
   passed to 'ostream_write_mem' or 'ostream_write_str'.  */
extern void term_ostream_flush_to_current_style (term_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

/* The amount of control to take over the underlying tty in order to avoid
   garbled output on the screen, due to interleaved output of escape sequences
   and output from the kernel (such as when the kernel echoes user's input
   or when the kernel prints '^C' after the user pressed Ctrl-C).  */
typedef enum
{
  TTYCTL_AUTO = 0,  /* Automatic best-possible choice.  */
  TTYCTL_NONE,      /* No control.
                       Result: Garbled output can occur, and the terminal can
                       be left in any state when the program is interrupted.  */
  TTYCTL_PARTIAL,   /* Signal handling.
                       Result: Garbled output can occur, but the terminal will
                       be left in the default state when the program is
                       interrupted.  */
  TTYCTL_FULL       /* Signal handling and disabling echo and flush-upon-signal.
                       Result: No garbled output, and the the terminal will
                       be left in the default state when the program is
                       interrupted.  */
} ttyctl_t;

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream referring to the file descriptor FD.
   FILENAME is used only for error messages.
   TTY_CONTROL specifies the amount of control to take over the underlying tty.
   The resulting stream will be line-buffered.
   Note that the resulting stream must be closed before FD can be closed.  */
extern term_ostream_t
       term_ostream_create (int fd, const char *filename, ttyctl_t tty_control);


#ifdef __cplusplus
}
#endif

/* ------------------------- From memory-ostream.h ------------------------- */

/* memory_ostream_t is a subtype of ostream_t.  */
typedef ostream_t memory_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void memory_ostream_write_mem (memory_ostream_t first_arg, const void *data, size_t len);
extern void memory_ostream_flush (memory_ostream_t first_arg, ostream_flush_scope_t scope);
extern void memory_ostream_free (memory_ostream_t first_arg);
extern void memory_ostream_contents (memory_ostream_t first_arg, const void **bufp, size_t *buflenp);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream that accumulates the output in a memory buffer.  */
extern memory_ostream_t memory_ostream_create (void);


#ifdef __cplusplus
}
#endif

/* -------------------------- From iconv-ostream.h -------------------------- */

#if LIBTEXTSTYLE_USES_ICONV

/* iconv_ostream_t is a subtype of ostream_t.  */
typedef ostream_t iconv_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void iconv_ostream_write_mem (iconv_ostream_t first_arg, const void *data, size_t len);
extern void iconv_ostream_flush (iconv_ostream_t first_arg, ostream_flush_scope_t scope);
extern void iconv_ostream_free (iconv_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream that converts from FROM_ENCODING to TO_ENCODING,
   writing the result to DESTINATION.  */
extern iconv_ostream_t iconv_ostream_create (const char *from_encoding,
                                             const char *to_encoding,
                                             ostream_t destination);


#ifdef __cplusplus
}
#endif

#endif /* LIBTEXTSTYLE_USES_ICONV */

/* -------------------------- From html-ostream.h -------------------------- */

/* html_ostream_t is a subtype of ostream_t.  */
typedef ostream_t html_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void html_ostream_write_mem (html_ostream_t first_arg, const void *data, size_t len);
extern void html_ostream_flush (html_ostream_t first_arg, ostream_flush_scope_t scope);
extern void html_ostream_free (html_ostream_t first_arg);
extern void html_ostream_begin_span (html_ostream_t first_arg, const char *classname);
extern void html_ostream_end_span (html_ostream_t first_arg, const char *classname);
/* Like html_ostream_flush (first_arg, FLUSH_THIS_STREAM), except that it
   leaves the destination with the current text style enabled, instead
   of with the default text style.
   After calling this function, you can output strings without newlines(!)
   to the underlying stream, and they will be rendered like strings passed
   to 'ostream_write_mem' or 'ostream_write_str'.  */
extern void html_ostream_flush_to_current_style (html_ostream_t stream);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream that takes input in the UTF-8 encoding and
   writes it in HTML form on DESTINATION.
   This stream produces a sequence of lines.  The caller is responsible
   for opening the <body><html> elements before and for closing them after
   the use of this stream.
   Note that the resulting stream must be closed before DESTINATION can be
   closed.  */
extern html_ostream_t html_ostream_create (ostream_t destination);


#ifdef __cplusplus
}
#endif

/* ----------------------- From term-styled-ostream.h ----------------------- */

/* term_styled_ostream_t is a subtype of styled_ostream_t.  */
typedef styled_ostream_t term_styled_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void term_styled_ostream_write_mem (term_styled_ostream_t first_arg, const void *data, size_t len);
extern void term_styled_ostream_flush (term_styled_ostream_t first_arg, ostream_flush_scope_t scope);
extern void term_styled_ostream_free (term_styled_ostream_t first_arg);
extern void term_styled_ostream_begin_use_class (term_styled_ostream_t first_arg, const char *classname);
extern void term_styled_ostream_end_use_class (term_styled_ostream_t first_arg, const char *classname);
extern void term_styled_ostream_flush_to_current_style (term_styled_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream referring to the file descriptor FD, styled with
   the file CSS_FILENAME.
   FILENAME is used only for error messages.
   TTY_CONTROL specifies the amount of control to take over the underlying tty.
   Note that the resulting stream must be closed before FD can be closed.
   Return NULL upon failure.  */
extern term_styled_ostream_t
       term_styled_ostream_create (int fd, const char *filename,
                                   ttyctl_t tty_control,
                                   const char *css_filename);


#ifdef __cplusplus
}
#endif

/* ----------------------- From html-styled-ostream.h ----------------------- */

/* html_styled_ostream_t is a subtype of styled_ostream_t.  */
typedef styled_ostream_t html_styled_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void html_styled_ostream_write_mem (html_styled_ostream_t first_arg, const void *data, size_t len);
extern void html_styled_ostream_flush (html_styled_ostream_t first_arg, ostream_flush_scope_t scope);
extern void html_styled_ostream_free (html_styled_ostream_t first_arg);
extern void html_styled_ostream_begin_use_class (html_styled_ostream_t first_arg, const char *classname);
extern void html_styled_ostream_end_use_class (html_styled_ostream_t first_arg, const char *classname);
extern void html_styled_ostream_flush_to_current_style (html_styled_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream that takes input in the UTF-8 encoding and
   writes it in HTML form on DESTINATION, styled with the file CSS_FILENAME.
   Note that the resulting stream must be closed before DESTINATION can be
   closed.  */
extern html_styled_ostream_t
       html_styled_ostream_create (ostream_t destination,
                                   const char *css_filename);


#ifdef __cplusplus
}
#endif

/* ----------------------- From noop-styled-ostream.h ----------------------- */

/* noop_styled_ostream_t is a subtype of styled_ostream_t.  */
typedef styled_ostream_t noop_styled_ostream_t;

/* Functions that invoke the methods.  */
#ifdef __cplusplus
extern "C" {
#endif
extern void noop_styled_ostream_write_mem (noop_styled_ostream_t first_arg, const void *data, size_t len);
extern void noop_styled_ostream_flush (noop_styled_ostream_t first_arg, ostream_flush_scope_t scope);
extern void noop_styled_ostream_free (noop_styled_ostream_t first_arg);
extern void noop_styled_ostream_begin_use_class (noop_styled_ostream_t first_arg, const char *classname);
extern void noop_styled_ostream_end_use_class (noop_styled_ostream_t first_arg, const char *classname);
extern void noop_styled_ostream_flush_to_current_style (noop_styled_ostream_t first_arg);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif


/* Create an output stream that delegates to DESTINATION and that supports
   the styling operations as no-ops.
   If PASS_OWNERSHIP is true, closing the resulting stream will automatically
   close the DESTINATION.
   Note that if PASS_OWNERSHIP is false, the resulting stream must be closed
   before DESTINATION can be closed.  */
extern noop_styled_ostream_t
       noop_styled_ostream_create (ostream_t destination, bool pass_ownership);


#ifdef __cplusplus
}
#endif

/* ------------------------------ From color.h ------------------------------ */

#ifdef __cplusplus
extern "C" {
#endif


/* Whether to output a test page.  */
extern LIBTEXTSTYLE_DLL_VARIABLE bool color_test_mode;

/* Color option.  */
enum color_option { color_no, color_tty, color_yes, color_html };
extern LIBTEXTSTYLE_DLL_VARIABLE enum color_option color_mode;

/* Style to use when coloring.  */
extern LIBTEXTSTYLE_DLL_VARIABLE const char *style_file_name;

/* --color argument handling.  Return an error indicator.  */
extern bool handle_color_option (const char *option);

/* --style argument handling.  */
extern void handle_style_option (const char *option);

/* Print a color test page.  */
extern void print_color_test (void);

/* Assign a default value to style_file_name if necessary.
   STYLE_FILE_ENVVAR is an environment variable that, when set to a non-empty
   value, specifies the style file to use.  This environment variable is meant
   to be set by the user.
   STYLESDIR_ENVVAR is an environment variable that, when set to a non-empty
   value, specifies the directory with the style files, or NULL.  This is
   necessary for running the testsuite before "make install".
   STYLESDIR_AFTER_INSTALL is the directory with the style files after
   "make install".
   DEFAULT_STYLE_FILE is the file name of the default style file, relative to
   STYLESDIR.  */
extern void style_file_prepare (const char *style_file_envvar,
                                const char *stylesdir_envvar,
                                const char *stylesdir_after_install,
                                const char *default_style_file);


#ifdef __cplusplus
}
#endif

/* ------------------------------ From misc.h ------------------------------ */

#ifdef __cplusplus
extern "C" {
#endif

/* Create an output stream referring to the file descriptor FD, styled with
   the file CSS_FILENAME if possible.
   FILENAME is used only for error messages.
   TTY_CONTROL specifies the amount of control to take over the underlying tty.
   Note that the resulting stream must be closed before FD can be closed.  */
extern styled_ostream_t
       styled_ostream_create (int fd, const char *filename,
                              ttyctl_t tty_control,
                              const char *css_filename);

/* Set the exit value upon failure within libtextstyle.  */
extern void libtextstyle_set_failure_exit_code (int exit_code);

#ifdef __cplusplus
}
#endif

/* ----------------------- Exported gnulib overrides ----------------------- */

#if defined _WIN32 && ! defined __CYGWIN__

# include <io.h>

# ifdef __cplusplus
extern "C" {
# endif

extern int libtextstyle_isatty (int fd);
# undef isatty
# define isatty libtextstyle_isatty

# ifdef __cplusplus
}
# endif

#endif

/* ------------------------------------------------------------------------- */

#endif /* _TEXTSTYLE_H */
