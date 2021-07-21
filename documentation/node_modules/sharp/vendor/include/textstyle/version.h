/* Meta information about GNU libtextstyle.
   Copyright (C) 2009-2010, 2019 Free Software Foundation, Inc.
   Written by Bruno Haible <bruno@clisp.org>, 2009.

   This program is free software: you can redistribute it and/or modify it
   under the terms of the GNU Lesser General Public License as published
   by the Free Software Foundation; either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

#ifndef _TEXTSTYLE_VERSION_H
#define _TEXTSTYLE_VERSION_H

/* Get LIBTEXTSTYLE_DLL_VARIABLE.  */
#include <textstyle/woe32dll.h>


#ifdef __cplusplus
extern "C" {
#endif


/* Version number: (major<<16) + (minor<<8) + subminor. */
#define _LIBTEXTSTYLE_VERSION 0x001400
extern LIBTEXTSTYLE_DLL_VARIABLE const int _libtextstyle_version; /* Likewise */


/* 1 if libtextstyle was built with iconv support, 0 if not.  */
#define LIBTEXTSTYLE_USES_ICONV 1


#ifdef __cplusplus
}
#endif


#endif /* _TEXTSTYLE_VERSION_H */
