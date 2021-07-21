// VIPS connection wrapper

/*

    This file is part of VIPS.
    
    VIPS is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
    02110-1301  USA

 */

/*

    These files are distributed with VIPS - http://www.vips.ecs.soton.ac.uk

 */

#ifndef VIPS_VCONNECTION_H
#define VIPS_VCONNECTION_H

#include <vips/vips.h>

VIPS_NAMESPACE_START

class VSource : VObject
{
public:
	VSource( VipsSource *input, VSteal steal = STEAL ) : 
		VObject( (VipsObject *) input, steal )
	{
	}

	static 
	VSource new_from_descriptor( int descriptor );

	static 
	VSource new_from_file( const char *filename );

	static 
	VSource new_from_blob( VipsBlob *blob );

	static 
	VSource new_from_memory( const void *data, 
		size_t size );

	static 
	VSource new_from_options( const char *options );

	VipsSource *
	get_source() const
	{
		return( (VipsSource *) VObject::get_object() );
	}

};

class VTarget : VObject
{
public:
	VTarget( VipsTarget *output, VSteal steal = STEAL ) : 
		VObject( (VipsObject *) output, steal )
	{
	}

	static 
	VTarget new_to_descriptor( int descriptor );

	static 
	VTarget new_to_file( const char *filename );

	static 
	VTarget new_to_memory();

	VipsTarget *
	get_target() const
	{
		return( (VipsTarget *) VObject::get_object() );
	}

};

VIPS_NAMESPACE_END

#endif /*VIPS_VCONNECTION_H*/
