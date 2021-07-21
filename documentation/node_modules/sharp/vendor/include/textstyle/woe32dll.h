/* Support for variables in shared libraries on Windows platforms.
   Copyright (C) 2009, 2019 Free Software Foundation, Inc.

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

/* Written by Bruno Haible <bruno@clisp.org>, 2009.  */

#ifndef _TEXTSTYLE_WOE32DLL_H
#define _TEXTSTYLE_WOE32DLL_H

#ifdef IN_LIBTEXTSTYLE
/* All code is collected in a single library,  */
# define LIBTEXTSTYLE_DLL_VARIABLE
#else
/* References from outside of libtextstyle.  */
# define LIBTEXTSTYLE_DLL_VARIABLE 
#endif

#endif /* _TEXTSTYLE_WOE32DLL_H */
