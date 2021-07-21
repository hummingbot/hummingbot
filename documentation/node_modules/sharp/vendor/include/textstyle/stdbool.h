/* DO NOT EDIT! GENERATED AUTOMATICALLY! */
#if !defined _GL_STDBOOL_H
#if (__GNUC__ > 2 || (__GNUC__ == 2 && __GNUC_MINOR__ >= 95))
#include <stdbool.h>
#else
/* Copyright (C) 2001-2003, 2006-2017, 2019 Free Software Foundation, Inc.
   Written by Bruno Haible <haible@clisp.cons.org>, 2001.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU Lesser General Public License as published by
   the Free Software Foundation; either version 2, or (at your option)
   any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public License
   along with this program; if not, see <https://www.gnu.org/licenses/>.  */

#ifndef _TEXTSTYLE_STDBOOL_H
#define _TEXTSTYLE_STDBOOL_H

/* ISO C 99 <stdbool.h> for platforms that lack it.  */

/* Usage suggestions:

   Programs that use <stdbool.h> should be aware of some limitations
   and standards compliance issues.

   Standards compliance:

       - <stdbool.h> must be #included before 'bool', 'false', 'true'
         can be used.

       - You cannot assume that sizeof (bool) == 1.

       - Programs should not undefine the macros bool, true, and false,
         as C99 lists that as an "obsolescent feature".

   Limitations of this substitute, when used in a C89 environment:

       - <stdbool.h> must be #included before the '_Bool' type can be used.

       - You cannot assume that _Bool is a typedef; it might be a macro.

       - Bit-fields of type 'bool' are not supported.  Portable code
         should use 'unsigned int foo : 1;' rather than 'bool foo : 1;'.

       - In C99, casts and automatic conversions to '_Bool' or 'bool' are
         performed in such a way that every nonzero value gets converted
         to 'true', and zero gets converted to 'false'.  This doesn't work
         with this substitute.  With this substitute, only the values 0 and 1
         give the expected result when converted to _Bool' or 'bool'.

       - C99 allows the use of (_Bool)0.0 in constant expressions, but
         this substitute cannot always provide this property.

   Also, it is suggested that programs use 'bool' rather than '_Bool';
   this isn't required, but 'bool' is more common.  */


/* 7.16. Boolean type and values */

#ifdef __cplusplus
  /* Assume the compiler has 'bool' and '_Bool'.  */
#else
  /* <stdbool.h> is known to exist and work with the following compilers:
       - GNU C 3.0 or newer, on any platform,
       - Intel C,
       - MSVC 12 (Visual Studio 2013) or newer,
       - Sun C, on Solaris, if _STDC_C99 is defined,
       - AIX xlc, if _ANSI_C_SOURCE is defined,
       - HP C, on HP-UX 11.31 or newer.
     It is know not to work with:
       - Sun C, on Solaris, if __C99FEATURES__ is defined but _STDC_C99 is not,
       - MIPSpro C 7.30, on IRIX.  */
# if (__GNUC__ >= 3) \
     || defined __INTEL_COMPILER \
     || (_MSC_VER >= 1800) \
     || (defined __SUNPRO_C && defined _STDC_C99) \
     || (defined _AIX && !defined __GNUC__ && defined _ANSI_C_SOURCE) \
     || defined __HP_cc
   /* Assume the compiler has <stdbool.h>.  */
#  include <stdbool.h>
# else
   /* Need to define _Bool ourselves. As 'signed char' or as an enum type?
      Use of a typedef, with SunPRO C, leads to a stupid
        "warning: _Bool is a keyword in ISO C99".
      Use of an enum type, with IRIX cc, leads to a stupid
        "warning(1185): enumerated type mixed with another type".
      Even the existence of an enum type, without a typedef,
        "Invalid enumerator. (badenum)" with HP-UX cc on Tru64.
      The only benefit of the enum, debuggability, is not important
      with these compilers.  So use 'signed char' and no enum.  */
#  define _Bool signed char
#  define bool _Bool
# endif
#endif

/* The other macros must be usable in preprocessor directives.  */
#ifdef __cplusplus
# define false false
# define true true
#else
# undef false
# define false 0
# undef true
# define true 1
#endif

#define __bool_true_false_are_defined 1

#endif /* _TEXTSTYLE_STDBOOL_H */
#endif
#endif
