/* -*- Mode: C; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/* vim: set sw=4 sts=4 expandtab: */
/*
   rsvg.h: SAX-based renderer for SVG files into a GdkPixbuf.

   Copyright (C) 2000 Eazel, Inc.

   This library is free software; you can redistribute it and/or
   modify it under the terms of the GNU Lesser General Public
   License as published by the Free Software Foundation; either
   version 2.1 of the License, or (at your option) any later version.

   This library is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public
   License along with this library; if not, write to the Free Software
   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

   Author: Raph Levien <raph@artofcode.com>
*/

#ifndef RSVG_H
#define RSVG_H

#define __RSVG_RSVG_H_INSIDE__

#include <glib-object.h>
#include <gio/gio.h>

#include <cairo.h>
#include <gdk-pixbuf/gdk-pixbuf.h>

G_BEGIN_DECLS

#ifndef __GTK_DOC_IGNORE__

/* Override to export public/semi-public APIs */
#ifndef RSVG_API
# define RSVG_API
#endif

#if defined(RSVG_DISABLE_DEPRECATION_WARNINGS) || !GLIB_CHECK_VERSION (2, 31, 0)
#define RSVG_DEPRECATED RSVG_API
#define RSVG_DEPRECATED_FOR(f) RSVG_API
#else
#define RSVG_DEPRECATED G_DEPRECATED RSVG_API
#define RSVG_DEPRECATED_FOR(f) G_DEPRECATED_FOR(f) RSVG_API
#endif

#endif /* __GTK_DOC_IGNORE__ */

#define RSVG_TYPE_HANDLE                  (rsvg_handle_get_type ())
#define RSVG_HANDLE(obj)                  (G_TYPE_CHECK_INSTANCE_CAST ((obj), RSVG_TYPE_HANDLE, RsvgHandle))
#define RSVG_HANDLE_CLASS(klass)          (G_TYPE_CHECK_CLASS_CAST ((klass), RSVG_TYPE_HANDLE, RsvgHandleClass))
#define RSVG_IS_HANDLE(obj)               (G_TYPE_CHECK_INSTANCE_TYPE ((obj), RSVG_TYPE_HANDLE))
#define RSVG_IS_HANDLE_CLASS(klass)       (G_TYPE_CHECK_CLASS_TYPE ((klass), RSVG_TYPE_HANDLE))
#define RSVG_HANDLE_GET_CLASS(obj)        (G_TYPE_INSTANCE_GET_CLASS ((obj), RSVG_TYPE_HANDLE, RsvgHandleClass))

RSVG_API
GType rsvg_handle_get_type (void);

/**
 * RsvgError:
 * @RSVG_ERROR_FAILED: the request failed
 *
 * An enumeration representing possible errors
 */
typedef enum {
    RSVG_ERROR_FAILED
} RsvgError;

#define RSVG_ERROR (rsvg_error_quark ())
RSVG_API
GQuark rsvg_error_quark (void) G_GNUC_CONST;

RSVG_API
GType rsvg_error_get_type (void);
#define RSVG_TYPE_ERROR (rsvg_error_get_type())

typedef struct _RsvgHandle RsvgHandle;
typedef struct _RsvgHandleClass RsvgHandleClass;
typedef struct _RsvgDimensionData RsvgDimensionData;
typedef struct _RsvgPositionData RsvgPositionData;
typedef struct _RsvgRectangle RsvgRectangle;

/**
 * RsvgHandleClass:
 * @parent: parent class
 *
 * Class structure for #RsvgHandle.
 */
struct _RsvgHandleClass {
    GObjectClass parent;

    /*< private >*/
    gpointer _abi_padding[15];
};

/**
 * RsvgHandle:
 *
 * Lets you load SVG data and render it.
 */
struct _RsvgHandle {
    GObject parent;

    /*< private >*/

    gpointer _abi_padding[16];
};

/**
 * RsvgDimensionData:
 * @width: SVG's width, in pixels
 * @height: SVG's height, in pixels
 * @em: SVG's original width, unmodified by #RsvgSizeFunc
 * @ex: SVG's original height, unmodified by #RsvgSizeFunc
 *
 * Dimensions of an SVG image from rsvg_handle_get_dimensions(), or an
 * individual element from rsvg_handle_get_dimensions_sub().  Please see
 * the deprecation documentation for those functions.
 *
 * Deprecated: 2.46.  FIXME: point to deprecation documentation.
 */
struct _RsvgDimensionData {
    int width;
    int height;
    gdouble em;
    gdouble ex;
};

/**
 * RsvgPositionData:
 * @x: position on the x axis
 * @y: position on the y axis
 *
 * Position of an SVG fragment from rsvg_handle_get_position_sub().  Please
 * the deprecation documentation for that function.
 *
 * Deprecated: 2.46.  FIXME: point to deprecation documentation.
 */
struct _RsvgPositionData {
    int x;
    int y;
};

/**
 * RsvgRectangle:
 * @x: X coordinate of the left side of the rectangle
 * @y: Y coordinate of the the top side of the rectangle
 * @width: width of the rectangle
 * @height: height of the rectangle
 *
 * A data structure for holding a rectangle.
 *
 * Since: 2.46
 */
struct _RsvgRectangle {
    double x;
    double y;
    double width;
    double height;
};


RSVG_DEPRECATED
void rsvg_cleanup (void);

RSVG_DEPRECATED
void rsvg_set_default_dpi	(double dpi);

RSVG_DEPRECATED
void rsvg_set_default_dpi_x_y	(double dpi_x, double dpi_y);

RSVG_API
void rsvg_handle_set_dpi	(RsvgHandle *handle, double dpi);
RSVG_API
void rsvg_handle_set_dpi_x_y	(RsvgHandle *handle, double dpi_x, double dpi_y);

RSVG_API
RsvgHandle  *rsvg_handle_new		(void);

RSVG_DEPRECATED_FOR(rsvg_handle_read_stream_sync)
gboolean     rsvg_handle_write		(RsvgHandle   *handle,
                                         const guchar *buf,
                                         gsize         count,
                                         GError      **error);
RSVG_DEPRECATED_FOR(rsvg_handle_read_stream_sync)
gboolean     rsvg_handle_close		(RsvgHandle *handle, GError **error);

RSVG_API
GdkPixbuf   *rsvg_handle_get_pixbuf	(RsvgHandle *handle);
RSVG_API
GdkPixbuf   *rsvg_handle_get_pixbuf_sub (RsvgHandle *handle, const char *id);

RSVG_API
const char  *rsvg_handle_get_base_uri (RsvgHandle *handle);
RSVG_API
void         rsvg_handle_set_base_uri (RsvgHandle *handle, const char *base_uri);

RSVG_API
void rsvg_handle_get_dimensions (RsvgHandle *handle, RsvgDimensionData *dimension_data);

RSVG_DEPRECATED_FOR(rsvg_handle_get_geometry_for_layer)
gboolean rsvg_handle_get_dimensions_sub (RsvgHandle        *handle,
                                         RsvgDimensionData *dimension_data,
                                         const char        *id);

RSVG_DEPRECATED_FOR(rsvg_handle_get_geometry_for_layer)
gboolean rsvg_handle_get_position_sub (RsvgHandle       *handle,
                                       RsvgPositionData *position_data,
                                       const char       *id);

RSVG_API
gboolean rsvg_handle_has_sub (RsvgHandle *handle, const char *id);

/**
 * RsvgUnit:
 * @RSVG_UNIT_PERCENT: percentage values; where <literal>1.0</literal> means 100%.
 * @RSVG_UNIT_PX: pixels
 * @RSVG_UNIT_EM: em, or the current font size
 * @RSVG_UNIT_EX: x-height of the current font
 * @RSVG_UNIT_IN: inches
 * @RSVG_UNIT_CM: centimeters
 * @RSVG_UNIT_MM: millimeters
 * @RSVG_UNIT_PT: points, or 1/72 inch
 * @RSVG_UNIT_PC: picas, or 1/6 inch (12 points)
 *
 * Units for the #RsvgLength struct.  These have the same meaning as <ulink
 * url="https://www.w3.org/TR/CSS21/syndata.html#length-units">CSS length
 * units</ulink>.
 */
typedef enum {
    RSVG_UNIT_PERCENT,
    RSVG_UNIT_PX,
    RSVG_UNIT_EM,
    RSVG_UNIT_EX,
    RSVG_UNIT_IN,
    RSVG_UNIT_CM,
    RSVG_UNIT_MM,
    RSVG_UNIT_PT,
    RSVG_UNIT_PC
} RsvgUnit;

/**
 * RsvgLength:
 * @length: numeric part of the length
 * @unit: unit part of the length
 *
 * #RsvgLength values are used in rsvg_handle_get_intrinsic_dimensions(), for
 * example, to return the CSS length values of the <literal>width</literal> and
 * <literal>height</literal> attributes of an <literal>&lt;svg&gt;</literal>
 * element.
 *
 * This is equivalent to <ulink
 * url="https://www.w3.org/TR/CSS21/syndata.html#length-units">CSS lengths</ulink>.
 *
 * It is up to the calling application to convert lengths in non-pixel units
 * (i.e. those where the @unit field is not #RSVG_UNIT_PX) into something
 * meaningful to the application.  For example, if your application knows the
 * dots-per-inch (DPI) it is using, it can convert lengths with @unit in
 * #RSVG_UNIT_IN or other physical units.
 */
typedef struct {
    double   length;
    RsvgUnit unit;
} RsvgLength;

RSVG_API
void rsvg_handle_get_intrinsic_dimensions (RsvgHandle *handle,
                                           gboolean   *out_has_width,
                                           RsvgLength *out_width,
                                           gboolean   *out_has_height,
                                           RsvgLength *out_height,
                                           gboolean   *out_has_viewbox,
                                           RsvgRectangle *out_viewbox);

/* GIO APIs */

/**
 * RsvgHandleFlags:
 * @RSVG_HANDLE_FLAGS_NONE: No flags are set.
 * @RSVG_HANDLE_FLAG_UNLIMITED: Disable safety limits in the XML parser.
 *   Libxml2 has <ulink
 *   url="https://gitlab.gnome.org/GNOME/libxml2/blob/master/include/libxml/parserInternals.h">several
 *   limits</ulink> designed to keep malicious XML content from consuming too
 *   much memory while parsing.  For security reasons, this should only be used
 *   for trusted input!
 *   Since: 2.40.3
 * @RSVG_HANDLE_FLAG_KEEP_IMAGE_DATA: Use this if the Cairo surface to which you
 *  are rendering is a PDF, PostScript, SVG, or Win32 Printing surface.  This
 *  will make librsvg and Cairo use the original, compressed data for images in
 *  the final output, instead of passing uncompressed images.  This will make a
 *  Keeps the image data when loading images, for use by cairo when painting to
 *  e.g. a PDF surface.  For example, this will make the a resulting PDF file
 *  smaller and faster.  Please see <ulink
 *  url="https://www.cairographics.org/manual/cairo-cairo-surface-t.html#cairo-surface-set-mime-data">the
 *  Cairo documentation</ulink> for details.
 *  Since: 2.40.3
 */
typedef enum /*< flags >*/
{
    RSVG_HANDLE_FLAGS_NONE           = 0,
    RSVG_HANDLE_FLAG_UNLIMITED       = 1 << 0,
    RSVG_HANDLE_FLAG_KEEP_IMAGE_DATA = 1 << 1
} RsvgHandleFlags;

RSVG_API
GType rsvg_handle_flags_get_type (void);
#define RSVG_TYPE_HANDLE_FLAGS (rsvg_handle_flags_get_type())

RSVG_API
RsvgHandle *rsvg_handle_new_with_flags (RsvgHandleFlags flags);

RSVG_API
void        rsvg_handle_set_base_gfile (RsvgHandle *handle,
                                        GFile      *base_file);

RSVG_API
gboolean    rsvg_handle_read_stream_sync (RsvgHandle   *handle,
                                          GInputStream *stream,
                                          GCancellable *cancellable,
                                          GError      **error);

RSVG_API
RsvgHandle *rsvg_handle_new_from_gfile_sync (GFile          *file,
                                             RsvgHandleFlags flags,
                                             GCancellable   *cancellable,
                                             GError        **error);

RSVG_API
RsvgHandle *rsvg_handle_new_from_stream_sync (GInputStream   *input_stream,
                                              GFile          *base_file,
                                              RsvgHandleFlags flags,
                                              GCancellable   *cancellable,
                                              GError        **error);

RSVG_API
RsvgHandle *rsvg_handle_new_from_data (const guint8 *data, gsize data_len, GError **error);
RSVG_API
RsvgHandle *rsvg_handle_new_from_file (const gchar *filename, GError **error);

#ifndef __GTK_DOC_IGNORE__
RSVG_API
void rsvg_handle_internal_set_testing (RsvgHandle *handle, gboolean testing);
#endif /* __GTK_DOC_IGNORE__ */

/* BEGIN deprecated APIs. Do not use! */

#ifndef __GI_SCANNER__

RSVG_DEPRECATED_FOR(g_type_init)
void rsvg_init (void);
RSVG_DEPRECATED
void rsvg_term (void);

RSVG_DEPRECATED_FOR(g_object_unref)
void rsvg_handle_free (RsvgHandle *handle);

/**
 * RsvgSizeFunc:
 * @width: (out): the width of the SVG
 * @height: (out): the height of the SVG
 * @user_data: user data
 *
 * Function to let a user of the library specify the SVG's dimensions
 *
 * Deprecated: 2.14.  Set up a cairo matrix and use rsvg_handle_render_cairo() instead.
 * See the documentation for rsvg_handle_set_size_callback() for an example, and
 * for the reasons for deprecation.
 */
typedef void (*RsvgSizeFunc) (gint * width, gint * height, gpointer user_data);

RSVG_DEPRECATED
void rsvg_handle_set_size_callback (RsvgHandle    *handle,
                                    RsvgSizeFunc   size_func,
                                    gpointer       user_data,
                                    GDestroyNotify user_data_destroy);

/* GdkPixbuf convenience API */

RSVG_DEPRECATED
GdkPixbuf *rsvg_pixbuf_from_file            (const gchar *filename,
                                             GError     **error);
RSVG_DEPRECATED
GdkPixbuf *rsvg_pixbuf_from_file_at_zoom    (const gchar *filename,
                                             double       x_zoom,
                                             double       y_zoom,
                                             GError     **error);
RSVG_DEPRECATED
GdkPixbuf *rsvg_pixbuf_from_file_at_size    (const gchar *filename,
                                             gint         width,
                                             gint         height,
                                             GError     **error);
RSVG_DEPRECATED
GdkPixbuf *rsvg_pixbuf_from_file_at_max_size    (const gchar *filename,
                                                 gint         max_width,
                                                 gint         max_height,
                                                 GError     **error);
RSVG_DEPRECATED
GdkPixbuf *rsvg_pixbuf_from_file_at_zoom_with_max (const gchar *filename,
                                                   double       x_zoom,
                                                   double       y_zoom,
                                                   gint         max_width,
                                                   gint         max_height,
                                                   GError     **error);

RSVG_DEPRECATED
const char *rsvg_handle_get_title       (RsvgHandle *handle);
RSVG_DEPRECATED
const char *rsvg_handle_get_desc        (RsvgHandle *handle);
RSVG_DEPRECATED
const char *rsvg_handle_get_metadata    (RsvgHandle *handle);

#endif /* !__GI_SCANNER__ */

/* END deprecated APIs. */

G_END_DECLS

#include "librsvg-features.h"
#include "rsvg-cairo.h"

#undef __RSVG_RSVG_H_INSIDE__

#endif                          /* RSVG_H */
