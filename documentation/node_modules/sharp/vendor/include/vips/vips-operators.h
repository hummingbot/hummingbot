// headers for vips operations
// Wed 01 Jan 2020 12:22:11 PM CET
// this file is generated automatically, do not edit!

/**
 * Transform lch to cmc.
 * @param options Optional options.
 * @return Output image.
 */
VImage CMC2LCh( VOption *options = 0 ) const;

/**
 * Transform cmyk to xyz.
 * @param options Optional options.
 * @return Output image.
 */
VImage CMYK2XYZ( VOption *options = 0 ) const;

/**
 * Transform hsv to srgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage HSV2sRGB( VOption *options = 0 ) const;

/**
 * Transform lch to cmc.
 * @param options Optional options.
 * @return Output image.
 */
VImage LCh2CMC( VOption *options = 0 ) const;

/**
 * Transform lch to lab.
 * @param options Optional options.
 * @return Output image.
 */
VImage LCh2Lab( VOption *options = 0 ) const;

/**
 * Transform lab to lch.
 * @param options Optional options.
 * @return Output image.
 */
VImage Lab2LCh( VOption *options = 0 ) const;

/**
 * Transform float lab to labq coding.
 * @param options Optional options.
 * @return Output image.
 */
VImage Lab2LabQ( VOption *options = 0 ) const;

/**
 * Transform float lab to signed short.
 * @param options Optional options.
 * @return Output image.
 */
VImage Lab2LabS( VOption *options = 0 ) const;

/**
 * Transform cielab to xyz.
 * @param options Optional options.
 * @return Output image.
 */
VImage Lab2XYZ( VOption *options = 0 ) const;

/**
 * Unpack a labq image to float lab.
 * @param options Optional options.
 * @return Output image.
 */
VImage LabQ2Lab( VOption *options = 0 ) const;

/**
 * Unpack a labq image to short lab.
 * @param options Optional options.
 * @return Output image.
 */
VImage LabQ2LabS( VOption *options = 0 ) const;

/**
 * Convert a labq image to srgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage LabQ2sRGB( VOption *options = 0 ) const;

/**
 * Transform signed short lab to float.
 * @param options Optional options.
 * @return Output image.
 */
VImage LabS2Lab( VOption *options = 0 ) const;

/**
 * Transform short lab to labq coding.
 * @param options Optional options.
 * @return Output image.
 */
VImage LabS2LabQ( VOption *options = 0 ) const;

/**
 * Transform xyz to cmyk.
 * @param options Optional options.
 * @return Output image.
 */
VImage XYZ2CMYK( VOption *options = 0 ) const;

/**
 * Transform xyz to lab.
 * @param options Optional options.
 * @return Output image.
 */
VImage XYZ2Lab( VOption *options = 0 ) const;

/**
 * Transform xyz to yxy.
 * @param options Optional options.
 * @return Output image.
 */
VImage XYZ2Yxy( VOption *options = 0 ) const;

/**
 * Transform xyz to scrgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage XYZ2scRGB( VOption *options = 0 ) const;

/**
 * Transform yxy to xyz.
 * @param options Optional options.
 * @return Output image.
 */
VImage Yxy2XYZ( VOption *options = 0 ) const;

/**
 * Absolute value of an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage abs( VOption *options = 0 ) const;

/**
 * Add two images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage add( VImage right, VOption *options = 0 ) const;

/**
 * Affine transform of an image.
 * @param matrix Transformation matrix.
 * @param options Optional options.
 * @return Output image.
 */
VImage affine( std::vector<double> matrix, VOption *options = 0 ) const;

/**
 * Load an analyze6 image.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage analyzeload( const char *filename, VOption *options = 0 );

/**
 * Join an array of images.
 * @param in Array of input images.
 * @param options Optional options.
 * @return Output image.
 */
static VImage arrayjoin( std::vector<VImage> in, VOption *options = 0 );

/**
 * Autorotate image by exif tag.
 * @param options Optional options.
 * @return Output image.
 */
VImage autorot( VOption *options = 0 ) const;

/**
 * Find image average.
 * @param options Optional options.
 * @return Output value.
 */
double avg( VOption *options = 0 ) const;

/**
 * Boolean operation across image bands.
 * @param boolean boolean to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage bandbool( VipsOperationBoolean boolean, VOption *options = 0 ) const;

/**
 * Fold up x axis into bands.
 * @param options Optional options.
 * @return Output image.
 */
VImage bandfold( VOption *options = 0 ) const;

/**
 * Bandwise join a set of images.
 * @param in Array of input images.
 * @param options Optional options.
 * @return Output image.
 */
static VImage bandjoin( std::vector<VImage> in, VOption *options = 0 );

/**
 * Append a constant band to an image.
 * @param c Array of constants to add.
 * @param options Optional options.
 * @return Output image.
 */
VImage bandjoin_const( std::vector<double> c, VOption *options = 0 ) const;

/**
 * Band-wise average.
 * @param options Optional options.
 * @return Output image.
 */
VImage bandmean( VOption *options = 0 ) const;

/**
 * Band-wise rank of a set of images.
 * @param in Array of input images.
 * @param options Optional options.
 * @return Output image.
 */
static VImage bandrank( std::vector<VImage> in, VOption *options = 0 );

/**
 * Unfold image bands into x axis.
 * @param options Optional options.
 * @return Output image.
 */
VImage bandunfold( VOption *options = 0 ) const;

/**
 * Make a black image.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage black( int width, int height, VOption *options = 0 );

/**
 * Boolean operation on two images.
 * @param right Right-hand image argument.
 * @param boolean boolean to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage boolean( VImage right, VipsOperationBoolean boolean, VOption *options = 0 ) const;

/**
 * Boolean operations against a constant.
 * @param boolean boolean to perform.
 * @param c Array of constants.
 * @param options Optional options.
 * @return Output image.
 */
VImage boolean_const( VipsOperationBoolean boolean, std::vector<double> c, VOption *options = 0 ) const;

/**
 * Build a look-up table.
 * @param options Optional options.
 * @return Output image.
 */
VImage buildlut( VOption *options = 0 ) const;

/**
 * Byteswap an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage byteswap( VOption *options = 0 ) const;

/**
 * Cache an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage cache( VOption *options = 0 ) const;

/**
 * Canny edge detector.
 * @param options Optional options.
 * @return Output image.
 */
VImage canny( VOption *options = 0 ) const;

/**
 * Use pixel values to pick cases from an array of images.
 * @param cases Array of case images.
 * @param options Optional options.
 * @return Output image.
 */
VImage case_image( std::vector<VImage> cases, VOption *options = 0 ) const;

/**
 * Cast an image.
 * @param format Format to cast to.
 * @param options Optional options.
 * @return Output image.
 */
VImage cast( VipsBandFormat format, VOption *options = 0 ) const;

/**
 * Convert to a new colorspace.
 * @param space Destination color space.
 * @param options Optional options.
 * @return Output image.
 */
VImage colourspace( VipsInterpretation space, VOption *options = 0 ) const;

/**
 * Convolve with rotating mask.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage compass( VImage mask, VOption *options = 0 ) const;

/**
 * Perform a complex operation on an image.
 * @param cmplx complex to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage complex( VipsOperationComplex cmplx, VOption *options = 0 ) const;

/**
 * Complex binary operations on two images.
 * @param right Right-hand image argument.
 * @param cmplx binary complex operation to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage complex2( VImage right, VipsOperationComplex2 cmplx, VOption *options = 0 ) const;

/**
 * Form a complex image from two real images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage complexform( VImage right, VOption *options = 0 ) const;

/**
 * Get a component from a complex image.
 * @param get complex to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage complexget( VipsOperationComplexget get, VOption *options = 0 ) const;

/**
 * Blend an array of images with an array of blend modes.
 * @param in Array of input images.
 * @param mode Array of VipsBlendMode to join with.
 * @param options Optional options.
 * @return Output image.
 */
static VImage composite( std::vector<VImage> in, std::vector<int> mode, VOption *options = 0 );

/**
 * Blend a pair of images with a blend mode.
 * @param overlay Overlay image.
 * @param mode VipsBlendMode to join with.
 * @param options Optional options.
 * @return Output image.
 */
VImage composite2( VImage overlay, VipsBlendMode mode, VOption *options = 0 ) const;

/**
 * Convolution operation.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage conv( VImage mask, VOption *options = 0 ) const;

/**
 * Approximate integer convolution.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage conva( VImage mask, VOption *options = 0 ) const;

/**
 * Approximate separable integer convolution.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage convasep( VImage mask, VOption *options = 0 ) const;

/**
 * Float convolution operation.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage convf( VImage mask, VOption *options = 0 ) const;

/**
 * Int convolution operation.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage convi( VImage mask, VOption *options = 0 ) const;

/**
 * Seperable convolution operation.
 * @param mask Input matrix image.
 * @param options Optional options.
 * @return Output image.
 */
VImage convsep( VImage mask, VOption *options = 0 ) const;

/**
 * Copy an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage copy( VOption *options = 0 ) const;

/**
 * Count lines in an image.
 * @param direction Countlines left-right or up-down.
 * @param options Optional options.
 * @return Number of lines.
 */
double countlines( VipsDirection direction, VOption *options = 0 ) const;

/**
 * Extract an area from an image.
 * @param left Left edge of extract area.
 * @param top Top edge of extract area.
 * @param width Width of extract area.
 * @param height Height of extract area.
 * @param options Optional options.
 * @return Output image.
 */
VImage crop( int left, int top, int width, int height, VOption *options = 0 ) const;

/**
 * Load csv from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage csvload( const char *filename, VOption *options = 0 );

/**
 * Save image to csv file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void csvsave( const char *filename, VOption *options = 0 ) const;

/**
 * Calculate de00.
 * @param right Right-hand input image.
 * @param options Optional options.
 * @return Output image.
 */
VImage dE00( VImage right, VOption *options = 0 ) const;

/**
 * Calculate de76.
 * @param right Right-hand input image.
 * @param options Optional options.
 * @return Output image.
 */
VImage dE76( VImage right, VOption *options = 0 ) const;

/**
 * Calculate decmc.
 * @param right Right-hand input image.
 * @param options Optional options.
 * @return Output image.
 */
VImage dECMC( VImage right, VOption *options = 0 ) const;

/**
 * Find image standard deviation.
 * @param options Optional options.
 * @return Output value.
 */
double deviate( VOption *options = 0 ) const;

/**
 * Divide two images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage divide( VImage right, VOption *options = 0 ) const;

/**
 * Draw a circle on an image.
 * @param ink Color for pixels.
 * @param cx Centre of draw_circle.
 * @param cy Centre of draw_circle.
 * @param radius Radius in pixels.
 * @param options Optional options.
 */
void draw_circle( std::vector<double> ink, int cx, int cy, int radius, VOption *options = 0 ) const;

/**
 * Flood-fill an area.
 * @param ink Color for pixels.
 * @param x DrawFlood start point.
 * @param y DrawFlood start point.
 * @param options Optional options.
 */
void draw_flood( std::vector<double> ink, int x, int y, VOption *options = 0 ) const;

/**
 * Paint an image into another image.
 * @param sub Sub-image to insert into main image.
 * @param x Draw image here.
 * @param y Draw image here.
 * @param options Optional options.
 */
void draw_image( VImage sub, int x, int y, VOption *options = 0 ) const;

/**
 * Draw a line on an image.
 * @param ink Color for pixels.
 * @param x1 Start of draw_line.
 * @param y1 Start of draw_line.
 * @param x2 End of draw_line.
 * @param y2 End of draw_line.
 * @param options Optional options.
 */
void draw_line( std::vector<double> ink, int x1, int y1, int x2, int y2, VOption *options = 0 ) const;

/**
 * Draw a mask on an image.
 * @param ink Color for pixels.
 * @param mask Mask of pixels to draw.
 * @param x Draw mask here.
 * @param y Draw mask here.
 * @param options Optional options.
 */
void draw_mask( std::vector<double> ink, VImage mask, int x, int y, VOption *options = 0 ) const;

/**
 * Paint a rectangle on an image.
 * @param ink Color for pixels.
 * @param left Rect to fill.
 * @param top Rect to fill.
 * @param width Rect to fill.
 * @param height Rect to fill.
 * @param options Optional options.
 */
void draw_rect( std::vector<double> ink, int left, int top, int width, int height, VOption *options = 0 ) const;

/**
 * Blur a rectangle on an image.
 * @param left Rect to fill.
 * @param top Rect to fill.
 * @param width Rect to fill.
 * @param height Rect to fill.
 * @param options Optional options.
 */
void draw_smudge( int left, int top, int width, int height, VOption *options = 0 ) const;

/**
 * Save image to deepzoom file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void dzsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to dz buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *dzsave_buffer( VOption *options = 0 ) const;

/**
 * Embed an image in a larger image.
 * @param x Left edge of input in output.
 * @param y Top edge of input in output.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
VImage embed( int x, int y, int width, int height, VOption *options = 0 ) const;

/**
 * Extract an area from an image.
 * @param left Left edge of extract area.
 * @param top Top edge of extract area.
 * @param width Width of extract area.
 * @param height Height of extract area.
 * @param options Optional options.
 * @return Output image.
 */
VImage extract_area( int left, int top, int width, int height, VOption *options = 0 ) const;

/**
 * Extract band from an image.
 * @param band Band to extract.
 * @param options Optional options.
 * @return Output image.
 */
VImage extract_band( int band, VOption *options = 0 ) const;

/**
 * Make an image showing the eye's spatial response.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage eye( int width, int height, VOption *options = 0 );

/**
 * False-color an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage falsecolour( VOption *options = 0 ) const;

/**
 * Fast correlation.
 * @param ref Input reference image.
 * @param options Optional options.
 * @return Output image.
 */
VImage fastcor( VImage ref, VOption *options = 0 ) const;

/**
 * Fill image zeros with nearest non-zero pixel.
 * @param options Optional options.
 * @return Value of nearest non-zero pixel.
 */
VImage fill_nearest( VOption *options = 0 ) const;

/**
 * Search an image for non-edge areas.
 * @param top Top edge of extract area.
 * @param width Width of extract area.
 * @param height Height of extract area.
 * @param options Optional options.
 * @return Left edge of image.
 */
int find_trim( int *top, int *width, int *height, VOption *options = 0 ) const;

/**
 * Load a fits image.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage fitsload( const char *filename, VOption *options = 0 );

/**
 * Save image to fits file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void fitssave( const char *filename, VOption *options = 0 ) const;

/**
 * Flatten alpha out of an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage flatten( VOption *options = 0 ) const;

/**
 * Flip an image.
 * @param direction Direction to flip image.
 * @param options Optional options.
 * @return Output image.
 */
VImage flip( VipsDirection direction, VOption *options = 0 ) const;

/**
 * Transform float rgb to radiance coding.
 * @param options Optional options.
 * @return Output image.
 */
VImage float2rad( VOption *options = 0 ) const;

/**
 * Make a fractal surface.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param fractal_dimension Fractal dimension.
 * @param options Optional options.
 * @return Output image.
 */
static VImage fractsurf( int width, int height, double fractal_dimension, VOption *options = 0 );

/**
 * Frequency-domain filtering.
 * @param mask Input mask image.
 * @param options Optional options.
 * @return Output image.
 */
VImage freqmult( VImage mask, VOption *options = 0 ) const;

/**
 * Forward fft.
 * @param options Optional options.
 * @return Output image.
 */
VImage fwfft( VOption *options = 0 ) const;

/**
 * Gamma an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage gamma( VOption *options = 0 ) const;

/**
 * Gaussian blur.
 * @param sigma Sigma of Gaussian.
 * @param options Optional options.
 * @return Output image.
 */
VImage gaussblur( double sigma, VOption *options = 0 ) const;

/**
 * Make a gaussian image.
 * @param sigma Sigma of Gaussian.
 * @param min_ampl Minimum amplitude of Gaussian.
 * @param options Optional options.
 * @return Output image.
 */
static VImage gaussmat( double sigma, double min_ampl, VOption *options = 0 );

/**
 * Make a gaussnoise image.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage gaussnoise( int width, int height, VOption *options = 0 );

/**
 * Read a point from an image.
 * @param x Point to read.
 * @param y Point to read.
 * @param options Optional options.
 * @return Array of output values.
 */
std::vector<double> getpoint( int x, int y, VOption *options = 0 ) const;

/**
 * Load gif with giflib.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage gifload( const char *filename, VOption *options = 0 );

/**
 * Load gif with giflib.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage gifload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Global balance an image mosaic.
 * @param options Optional options.
 * @return Output image.
 */
VImage globalbalance( VOption *options = 0 ) const;

/**
 * Place an image within a larger image with a certain gravity.
 * @param direction direction to place image within width/height.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
VImage gravity( VipsCompassDirection direction, int width, int height, VOption *options = 0 ) const;

/**
 * Make a grey ramp image.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage grey( int width, int height, VOption *options = 0 );

/**
 * Grid an image.
 * @param tile_height chop into tiles this high.
 * @param across number of tiles across.
 * @param down number of tiles down.
 * @param options Optional options.
 * @return Output image.
 */
VImage grid( int tile_height, int across, int down, VOption *options = 0 ) const;

/**
 * Load a heif image.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage heifload( const char *filename, VOption *options = 0 );

/**
 * Load a heif image.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage heifload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Save image in heif format.
 * @param filename Filename to load from.
 * @param options Optional options.
 */
void heifsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image in heif format.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *heifsave_buffer( VOption *options = 0 ) const;

/**
 * Form cumulative histogram.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_cum( VOption *options = 0 ) const;

/**
 * Estimate image entropy.
 * @param options Optional options.
 * @return Output value.
 */
double hist_entropy( VOption *options = 0 ) const;

/**
 * Histogram equalisation.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_equal( VOption *options = 0 ) const;

/**
 * Find image histogram.
 * @param options Optional options.
 * @return Output histogram.
 */
VImage hist_find( VOption *options = 0 ) const;

/**
 * Find indexed image histogram.
 * @param index Index image.
 * @param options Optional options.
 * @return Output histogram.
 */
VImage hist_find_indexed( VImage index, VOption *options = 0 ) const;

/**
 * Find n-dimensional image histogram.
 * @param options Optional options.
 * @return Output histogram.
 */
VImage hist_find_ndim( VOption *options = 0 ) const;

/**
 * Test for monotonicity.
 * @param options Optional options.
 * @return true if in is monotonic.
 */
bool hist_ismonotonic( VOption *options = 0 ) const;

/**
 * Local histogram equalisation.
 * @param width Window width in pixels.
 * @param height Window height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_local( int width, int height, VOption *options = 0 ) const;

/**
 * Match two histograms.
 * @param ref Reference histogram.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_match( VImage ref, VOption *options = 0 ) const;

/**
 * Normalise histogram.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_norm( VOption *options = 0 ) const;

/**
 * Plot histogram.
 * @param options Optional options.
 * @return Output image.
 */
VImage hist_plot( VOption *options = 0 ) const;

/**
 * Find hough circle transform.
 * @param options Optional options.
 * @return Output image.
 */
VImage hough_circle( VOption *options = 0 ) const;

/**
 * Find hough line transform.
 * @param options Optional options.
 * @return Output image.
 */
VImage hough_line( VOption *options = 0 ) const;

/**
 * Output to device with icc profile.
 * @param options Optional options.
 * @return Output image.
 */
VImage icc_export( VOption *options = 0 ) const;

/**
 * Import from device with icc profile.
 * @param options Optional options.
 * @return Output image.
 */
VImage icc_import( VOption *options = 0 ) const;

/**
 * Transform between devices with icc profiles.
 * @param output_profile Filename to load output profile from.
 * @param options Optional options.
 * @return Output image.
 */
VImage icc_transform( const char *output_profile, VOption *options = 0 ) const;

/**
 * Make a 1d image where pixel values are indexes.
 * @param options Optional options.
 * @return Output image.
 */
static VImage identity( VOption *options = 0 );

/**
 * Ifthenelse an image.
 * @param in1 Source for TRUE pixels.
 * @param in2 Source for FALSE pixels.
 * @param options Optional options.
 * @return Output image.
 */
VImage ifthenelse( VImage in1, VImage in2, VOption *options = 0 ) const;

/**
 * Insert image @sub into @main at @x, @y.
 * @param sub Sub-image to insert into main image.
 * @param x Left edge of sub in main.
 * @param y Top edge of sub in main.
 * @param options Optional options.
 * @return Output image.
 */
VImage insert( VImage sub, int x, int y, VOption *options = 0 ) const;

/**
 * Invert an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage invert( VOption *options = 0 ) const;

/**
 * Build an inverted look-up table.
 * @param options Optional options.
 * @return Output image.
 */
VImage invertlut( VOption *options = 0 ) const;

/**
 * Inverse fft.
 * @param options Optional options.
 * @return Output image.
 */
VImage invfft( VOption *options = 0 ) const;

/**
 * Join a pair of images.
 * @param in2 Second input image.
 * @param direction Join left-right or up-down.
 * @param options Optional options.
 * @return Output image.
 */
VImage join( VImage in2, VipsDirection direction, VOption *options = 0 ) const;

/**
 * Load jpeg from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage jpegload( const char *filename, VOption *options = 0 );

/**
 * Load jpeg from buffer.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage jpegload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load image from jpeg source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage jpegload_source( VSource source, VOption *options = 0 );

/**
 * Save image to jpeg file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void jpegsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to jpeg buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *jpegsave_buffer( VOption *options = 0 ) const;

/**
 * Save image to jpeg mime.
 * @param options Optional options.
 */
void jpegsave_mime( VOption *options = 0 ) const;

/**
 * Save image to jpeg target.
 * @param target Target to save to.
 * @param options Optional options.
 */
void jpegsave_target( VTarget target, VOption *options = 0 ) const;

/**
 * Label regions in an image.
 * @param options Optional options.
 * @return Mask of region labels.
 */
VImage labelregions( VOption *options = 0 ) const;

/**
 * Calculate (a * in + b).
 * @param a Multiply by this.
 * @param b Add this.
 * @param options Optional options.
 * @return Output image.
 */
VImage linear( std::vector<double> a, std::vector<double> b, VOption *options = 0 ) const;

/**
 * Cache an image as a set of lines.
 * @param options Optional options.
 * @return Output image.
 */
VImage linecache( VOption *options = 0 ) const;

/**
 * Make a laplacian of gaussian image.
 * @param sigma Radius of Logmatian.
 * @param min_ampl Minimum amplitude of Logmatian.
 * @param options Optional options.
 * @return Output image.
 */
static VImage logmat( double sigma, double min_ampl, VOption *options = 0 );

/**
 * Load file with imagemagick.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage magickload( const char *filename, VOption *options = 0 );

/**
 * Load buffer with imagemagick.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage magickload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Save file with imagemagick.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void magicksave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to magick buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *magicksave_buffer( VOption *options = 0 ) const;

/**
 * Resample with a map image.
 * @param index Index pixels with this.
 * @param options Optional options.
 * @return Output image.
 */
VImage mapim( VImage index, VOption *options = 0 ) const;

/**
 * Map an image though a lut.
 * @param lut Look-up table image.
 * @param options Optional options.
 * @return Output image.
 */
VImage maplut( VImage lut, VOption *options = 0 ) const;

/**
 * Make a butterworth filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param order Filter order.
 * @param frequency_cutoff Frequency cutoff.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_butterworth( int width, int height, double order, double frequency_cutoff, double amplitude_cutoff, VOption *options = 0 );

/**
 * Make a butterworth_band filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param order Filter order.
 * @param frequency_cutoff_x Frequency cutoff x.
 * @param frequency_cutoff_y Frequency cutoff y.
 * @param radius radius of circle.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_butterworth_band( int width, int height, double order, double frequency_cutoff_x, double frequency_cutoff_y, double radius, double amplitude_cutoff, VOption *options = 0 );

/**
 * Make a butterworth ring filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param order Filter order.
 * @param frequency_cutoff Frequency cutoff.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param ringwidth Ringwidth.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_butterworth_ring( int width, int height, double order, double frequency_cutoff, double amplitude_cutoff, double ringwidth, VOption *options = 0 );

/**
 * Make fractal filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param fractal_dimension Fractal dimension.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_fractal( int width, int height, double fractal_dimension, VOption *options = 0 );

/**
 * Make a gaussian filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff Frequency cutoff.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_gaussian( int width, int height, double frequency_cutoff, double amplitude_cutoff, VOption *options = 0 );

/**
 * Make a gaussian filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff_x Frequency cutoff x.
 * @param frequency_cutoff_y Frequency cutoff y.
 * @param radius radius of circle.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_gaussian_band( int width, int height, double frequency_cutoff_x, double frequency_cutoff_y, double radius, double amplitude_cutoff, VOption *options = 0 );

/**
 * Make a gaussian ring filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff Frequency cutoff.
 * @param amplitude_cutoff Amplitude cutoff.
 * @param ringwidth Ringwidth.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_gaussian_ring( int width, int height, double frequency_cutoff, double amplitude_cutoff, double ringwidth, VOption *options = 0 );

/**
 * Make an ideal filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff Frequency cutoff.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_ideal( int width, int height, double frequency_cutoff, VOption *options = 0 );

/**
 * Make an ideal band filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff_x Frequency cutoff x.
 * @param frequency_cutoff_y Frequency cutoff y.
 * @param radius radius of circle.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_ideal_band( int width, int height, double frequency_cutoff_x, double frequency_cutoff_y, double radius, VOption *options = 0 );

/**
 * Make an ideal ring filter.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param frequency_cutoff Frequency cutoff.
 * @param ringwidth Ringwidth.
 * @param options Optional options.
 * @return Output image.
 */
static VImage mask_ideal_ring( int width, int height, double frequency_cutoff, double ringwidth, VOption *options = 0 );

/**
 * First-order match of two images.
 * @param sec Secondary image.
 * @param xr1 Position of first reference tie-point.
 * @param yr1 Position of first reference tie-point.
 * @param xs1 Position of first secondary tie-point.
 * @param ys1 Position of first secondary tie-point.
 * @param xr2 Position of second reference tie-point.
 * @param yr2 Position of second reference tie-point.
 * @param xs2 Position of second secondary tie-point.
 * @param ys2 Position of second secondary tie-point.
 * @param options Optional options.
 * @return Output image.
 */
VImage match( VImage sec, int xr1, int yr1, int xs1, int ys1, int xr2, int yr2, int xs2, int ys2, VOption *options = 0 ) const;

/**
 * Apply a math operation to an image.
 * @param math math to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage math( VipsOperationMath math, VOption *options = 0 ) const;

/**
 * Binary math operations.
 * @param right Right-hand image argument.
 * @param math2 math to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage math2( VImage right, VipsOperationMath2 math2, VOption *options = 0 ) const;

/**
 * Binary math operations with a constant.
 * @param math2 math to perform.
 * @param c Array of constants.
 * @param options Optional options.
 * @return Output image.
 */
VImage math2_const( VipsOperationMath2 math2, std::vector<double> c, VOption *options = 0 ) const;

/**
 * Load mat from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage matload( const char *filename, VOption *options = 0 );

/**
 * Load matrix from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage matrixload( const char *filename, VOption *options = 0 );

/**
 * Print matrix.
 * @param options Optional options.
 */
void matrixprint( VOption *options = 0 ) const;

/**
 * Save image to matrix file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void matrixsave( const char *filename, VOption *options = 0 ) const;

/**
 * Find image maximum.
 * @param options Optional options.
 * @return Output value.
 */
double max( VOption *options = 0 ) const;

/**
 * Measure a set of patches on a color chart.
 * @param h Number of patches across chart.
 * @param v Number of patches down chart.
 * @param options Optional options.
 * @return Output array of statistics.
 */
VImage measure( int h, int v, VOption *options = 0 ) const;

/**
 * Merge two images.
 * @param sec Secondary image.
 * @param direction Horizontal or vertcial merge.
 * @param dx Horizontal displacement from sec to ref.
 * @param dy Vertical displacement from sec to ref.
 * @param options Optional options.
 * @return Output image.
 */
VImage merge( VImage sec, VipsDirection direction, int dx, int dy, VOption *options = 0 ) const;

/**
 * Find image minimum.
 * @param options Optional options.
 * @return Output value.
 */
double min( VOption *options = 0 ) const;

/**
 * Morphology operation.
 * @param mask Input matrix image.
 * @param morph Morphological operation to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage morph( VImage mask, VipsOperationMorphology morph, VOption *options = 0 ) const;

/**
 * Mosaic two images.
 * @param sec Secondary image.
 * @param direction Horizontal or vertcial mosaic.
 * @param xref Position of reference tie-point.
 * @param yref Position of reference tie-point.
 * @param xsec Position of secondary tie-point.
 * @param ysec Position of secondary tie-point.
 * @param options Optional options.
 * @return Output image.
 */
VImage mosaic( VImage sec, VipsDirection direction, int xref, int yref, int xsec, int ysec, VOption *options = 0 ) const;

/**
 * First-order mosaic of two images.
 * @param sec Secondary image.
 * @param direction Horizontal or vertcial mosaic.
 * @param xr1 Position of first reference tie-point.
 * @param yr1 Position of first reference tie-point.
 * @param xs1 Position of first secondary tie-point.
 * @param ys1 Position of first secondary tie-point.
 * @param xr2 Position of second reference tie-point.
 * @param yr2 Position of second reference tie-point.
 * @param xs2 Position of second secondary tie-point.
 * @param ys2 Position of second secondary tie-point.
 * @param options Optional options.
 * @return Output image.
 */
VImage mosaic1( VImage sec, VipsDirection direction, int xr1, int yr1, int xs1, int ys1, int xr2, int yr2, int xs2, int ys2, VOption *options = 0 ) const;

/**
 * Pick most-significant byte from an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage msb( VOption *options = 0 ) const;

/**
 * Multiply two images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage multiply( VImage right, VOption *options = 0 ) const;

/**
 * Load a nifti image.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage niftiload( const char *filename, VOption *options = 0 );

/**
 * Save image to nifti file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void niftisave( const char *filename, VOption *options = 0 ) const;

/**
 * Load an openexr image.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage openexrload( const char *filename, VOption *options = 0 );

/**
 * Load file with openslide.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage openslideload( const char *filename, VOption *options = 0 );

/**
 * Load pdf with libpoppler.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage pdfload( const char *filename, VOption *options = 0 );

/**
 * Load pdf with libpoppler.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage pdfload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Find threshold for percent of pixels.
 * @param percent Percent of pixels.
 * @param options Optional options.
 * @return Threshold above which lie percent of pixels.
 */
int percent( double percent, VOption *options = 0 ) const;

/**
 * Make a perlin noise image.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage perlin( int width, int height, VOption *options = 0 );

/**
 * Calculate phase correlation.
 * @param in2 Second input image.
 * @param options Optional options.
 * @return Output image.
 */
VImage phasecor( VImage in2, VOption *options = 0 ) const;

/**
 * Load png from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage pngload( const char *filename, VOption *options = 0 );

/**
 * Load png from buffer.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage pngload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load png from source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage pngload_source( VSource source, VOption *options = 0 );

/**
 * Save image to png file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void pngsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to png buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *pngsave_buffer( VOption *options = 0 ) const;

/**
 * Save image to target as png.
 * @param target Target to save to.
 * @param options Optional options.
 */
void pngsave_target( VTarget target, VOption *options = 0 ) const;

/**
 * Load ppm from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage ppmload( const char *filename, VOption *options = 0 );

/**
 * Save image to ppm file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void ppmsave( const char *filename, VOption *options = 0 ) const;

/**
 * Premultiply image alpha.
 * @param options Optional options.
 * @return Output image.
 */
VImage premultiply( VOption *options = 0 ) const;

/**
 * Find image profiles.
 * @param rows First non-zero pixel in row.
 * @param options Optional options.
 * @return First non-zero pixel in column.
 */
VImage profile( VImage *rows, VOption *options = 0 ) const;

/**
 * Load named icc profile.
 * @param name Profile name.
 * @param options Optional options.
 * @return Loaded profile.
 */
static VipsBlob *profile_load( const char *name, VOption *options = 0 );

/**
 * Find image projections.
 * @param rows Sums of rows.
 * @param options Optional options.
 * @return Sums of columns.
 */
VImage project( VImage *rows, VOption *options = 0 ) const;

/**
 * Resample an image with a quadratic transform.
 * @param coeff Coefficient matrix.
 * @param options Optional options.
 * @return Output image.
 */
VImage quadratic( VImage coeff, VOption *options = 0 ) const;

/**
 * Unpack radiance coding to float rgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage rad2float( VOption *options = 0 ) const;

/**
 * Load a radiance image from a file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage radload( const char *filename, VOption *options = 0 );

/**
 * Load rad from buffer.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage radload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load rad from source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage radload_source( VSource source, VOption *options = 0 );

/**
 * Save image to radiance file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void radsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to radiance buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *radsave_buffer( VOption *options = 0 ) const;

/**
 * Save image to radiance target.
 * @param target Target to save to.
 * @param options Optional options.
 */
void radsave_target( VTarget target, VOption *options = 0 ) const;

/**
 * Rank filter.
 * @param width Window width in pixels.
 * @param height Window height in pixels.
 * @param index Select pixel at index.
 * @param options Optional options.
 * @return Output image.
 */
VImage rank( int width, int height, int index, VOption *options = 0 ) const;

/**
 * Load raw data from a file.
 * @param filename Filename to load from.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param bands Number of bands in image.
 * @param options Optional options.
 * @return Output image.
 */
static VImage rawload( const char *filename, int width, int height, int bands, VOption *options = 0 );

/**
 * Save image to raw file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void rawsave( const char *filename, VOption *options = 0 ) const;

/**
 * Write raw image to file descriptor.
 * @param fd File descriptor to write to.
 * @param options Optional options.
 */
void rawsave_fd( int fd, VOption *options = 0 ) const;

/**
 * Linear recombination with matrix.
 * @param m matrix of coefficients.
 * @param options Optional options.
 * @return Output image.
 */
VImage recomb( VImage m, VOption *options = 0 ) const;

/**
 * Reduce an image.
 * @param hshrink Horizontal shrink factor.
 * @param vshrink Vertical shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage reduce( double hshrink, double vshrink, VOption *options = 0 ) const;

/**
 * Shrink an image horizontally.
 * @param hshrink Horizontal shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage reduceh( double hshrink, VOption *options = 0 ) const;

/**
 * Shrink an image vertically.
 * @param vshrink Vertical shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage reducev( double vshrink, VOption *options = 0 ) const;

/**
 * Relational operation on two images.
 * @param right Right-hand image argument.
 * @param relational relational to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage relational( VImage right, VipsOperationRelational relational, VOption *options = 0 ) const;

/**
 * Relational operations against a constant.
 * @param relational relational to perform.
 * @param c Array of constants.
 * @param options Optional options.
 * @return Output image.
 */
VImage relational_const( VipsOperationRelational relational, std::vector<double> c, VOption *options = 0 ) const;

/**
 * Remainder after integer division of two images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage remainder( VImage right, VOption *options = 0 ) const;

/**
 * Remainder after integer division of an image and a constant.
 * @param c Array of constants.
 * @param options Optional options.
 * @return Output image.
 */
VImage remainder_const( std::vector<double> c, VOption *options = 0 ) const;

/**
 * Replicate an image.
 * @param across Repeat this many times horizontally.
 * @param down Repeat this many times vertically.
 * @param options Optional options.
 * @return Output image.
 */
VImage replicate( int across, int down, VOption *options = 0 ) const;

/**
 * Resize an image.
 * @param scale Scale image by this factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage resize( double scale, VOption *options = 0 ) const;

/**
 * Rotate an image.
 * @param angle Angle to rotate image.
 * @param options Optional options.
 * @return Output image.
 */
VImage rot( VipsAngle angle, VOption *options = 0 ) const;

/**
 * Rotate an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage rot45( VOption *options = 0 ) const;

/**
 * Rotate an image by a number of degrees.
 * @param angle Rotate anticlockwise by this many degrees.
 * @param options Optional options.
 * @return Output image.
 */
VImage rotate( double angle, VOption *options = 0 ) const;

/**
 * Perform a round function on an image.
 * @param round rounding operation to perform.
 * @param options Optional options.
 * @return Output image.
 */
VImage round( VipsOperationRound round, VOption *options = 0 ) const;

/**
 * Transform srgb to hsv.
 * @param options Optional options.
 * @return Output image.
 */
VImage sRGB2HSV( VOption *options = 0 ) const;

/**
 * Convert an srgb image to scrgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage sRGB2scRGB( VOption *options = 0 ) const;

/**
 * Convert scrgb to bw.
 * @param options Optional options.
 * @return Output image.
 */
VImage scRGB2BW( VOption *options = 0 ) const;

/**
 * Transform scrgb to xyz.
 * @param options Optional options.
 * @return Output image.
 */
VImage scRGB2XYZ( VOption *options = 0 ) const;

/**
 * Convert an scrgb image to srgb.
 * @param options Optional options.
 * @return Output image.
 */
VImage scRGB2sRGB( VOption *options = 0 ) const;

/**
 * Scale an image to uchar.
 * @param options Optional options.
 * @return Output image.
 */
VImage scale( VOption *options = 0 ) const;

/**
 * Check sequential access.
 * @param options Optional options.
 * @return Output image.
 */
VImage sequential( VOption *options = 0 ) const;

/**
 * Unsharp masking for print.
 * @param options Optional options.
 * @return Output image.
 */
VImage sharpen( VOption *options = 0 ) const;

/**
 * Shrink an image.
 * @param hshrink Horizontal shrink factor.
 * @param vshrink Vertical shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage shrink( double hshrink, double vshrink, VOption *options = 0 ) const;

/**
 * Shrink an image horizontally.
 * @param hshrink Horizontal shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage shrinkh( int hshrink, VOption *options = 0 ) const;

/**
 * Shrink an image vertically.
 * @param vshrink Vertical shrink factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage shrinkv( int vshrink, VOption *options = 0 ) const;

/**
 * Unit vector of pixel.
 * @param options Optional options.
 * @return Output image.
 */
VImage sign( VOption *options = 0 ) const;

/**
 * Similarity transform of an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage similarity( VOption *options = 0 ) const;

/**
 * Make a 2d sine wave.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage sines( int width, int height, VOption *options = 0 );

/**
 * Extract an area from an image.
 * @param width Width of extract area.
 * @param height Height of extract area.
 * @param options Optional options.
 * @return Output image.
 */
VImage smartcrop( int width, int height, VOption *options = 0 ) const;

/**
 * Sobel edge detector.
 * @param options Optional options.
 * @return Output image.
 */
VImage sobel( VOption *options = 0 ) const;

/**
 * Spatial correlation.
 * @param ref Input reference image.
 * @param options Optional options.
 * @return Output image.
 */
VImage spcor( VImage ref, VOption *options = 0 ) const;

/**
 * Make displayable power spectrum.
 * @param options Optional options.
 * @return Output image.
 */
VImage spectrum( VOption *options = 0 ) const;

/**
 * Find many image stats.
 * @param options Optional options.
 * @return Output array of statistics.
 */
VImage stats( VOption *options = 0 ) const;

/**
 * Statistical difference.
 * @param width Window width in pixels.
 * @param height Window height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
VImage stdif( int width, int height, VOption *options = 0 ) const;

/**
 * Subsample an image.
 * @param xfac Horizontal subsample factor.
 * @param yfac Vertical subsample factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage subsample( int xfac, int yfac, VOption *options = 0 ) const;

/**
 * Subtract two images.
 * @param right Right-hand image argument.
 * @param options Optional options.
 * @return Output image.
 */
VImage subtract( VImage right, VOption *options = 0 ) const;

/**
 * Sum an array of images.
 * @param in Array of input images.
 * @param options Optional options.
 * @return Output image.
 */
static VImage sum( std::vector<VImage> in, VOption *options = 0 );

/**
 * Load svg with rsvg.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage svgload( const char *filename, VOption *options = 0 );

/**
 * Load svg with rsvg.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage svgload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load svg from source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage svgload_source( VSource source, VOption *options = 0 );

/**
 * Find the index of the first non-zero pixel in tests.
 * @param tests Table of images to test.
 * @param options Optional options.
 * @return Output image.
 */
static VImage switch_image( std::vector<VImage> tests, VOption *options = 0 );

/**
 * Run an external command.
 * @param cmd_format Command to run.
 * @param options Optional options.
 */
static void system( const char *cmd_format, VOption *options = 0 );

/**
 * Make a text image.
 * @param text Text to render.
 * @param options Optional options.
 * @return Output image.
 */
static VImage text( const char *text, VOption *options = 0 );

/**
 * Generate thumbnail from file.
 * @param filename Filename to read from.
 * @param width Size to this width.
 * @param options Optional options.
 * @return Output image.
 */
static VImage thumbnail( const char *filename, int width, VOption *options = 0 );

/**
 * Generate thumbnail from buffer.
 * @param buffer Buffer to load from.
 * @param width Size to this width.
 * @param options Optional options.
 * @return Output image.
 */
static VImage thumbnail_buffer( VipsBlob *buffer, int width, VOption *options = 0 );

/**
 * Generate thumbnail from image.
 * @param width Size to this width.
 * @param options Optional options.
 * @return Output image.
 */
VImage thumbnail_image( int width, VOption *options = 0 ) const;

/**
 * Generate thumbnail from source.
 * @param source Source to load from.
 * @param width Size to this width.
 * @param options Optional options.
 * @return Output image.
 */
static VImage thumbnail_source( VSource source, int width, VOption *options = 0 );

/**
 * Load tiff from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage tiffload( const char *filename, VOption *options = 0 );

/**
 * Load tiff from buffer.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage tiffload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load tiff from source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage tiffload_source( VSource source, VOption *options = 0 );

/**
 * Save image to tiff file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void tiffsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to tiff buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *tiffsave_buffer( VOption *options = 0 ) const;

/**
 * Cache an image as a set of tiles.
 * @param options Optional options.
 * @return Output image.
 */
VImage tilecache( VOption *options = 0 ) const;

/**
 * Build a look-up table.
 * @param options Optional options.
 * @return Output image.
 */
static VImage tonelut( VOption *options = 0 );

/**
 * Transpose3d an image.
 * @param options Optional options.
 * @return Output image.
 */
VImage transpose3d( VOption *options = 0 ) const;

/**
 * Unpremultiply image alpha.
 * @param options Optional options.
 * @return Output image.
 */
VImage unpremultiply( VOption *options = 0 ) const;

/**
 * Load vips from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage vipsload( const char *filename, VOption *options = 0 );

/**
 * Save image to vips file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void vipssave( const char *filename, VOption *options = 0 ) const;

/**
 * Load webp from file.
 * @param filename Filename to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage webpload( const char *filename, VOption *options = 0 );

/**
 * Load webp from buffer.
 * @param buffer Buffer to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage webpload_buffer( VipsBlob *buffer, VOption *options = 0 );

/**
 * Load webp from source.
 * @param source Source to load from.
 * @param options Optional options.
 * @return Output image.
 */
static VImage webpload_source( VSource source, VOption *options = 0 );

/**
 * Save image to webp file.
 * @param filename Filename to save to.
 * @param options Optional options.
 */
void webpsave( const char *filename, VOption *options = 0 ) const;

/**
 * Save image to webp buffer.
 * @param options Optional options.
 * @return Buffer to save to.
 */
VipsBlob *webpsave_buffer( VOption *options = 0 ) const;

/**
 * Save image to webp target.
 * @param target Target to save to.
 * @param options Optional options.
 */
void webpsave_target( VTarget target, VOption *options = 0 ) const;

/**
 * Make a worley noise image.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage worley( int width, int height, VOption *options = 0 );

/**
 * Wrap image origin.
 * @param options Optional options.
 * @return Output image.
 */
VImage wrap( VOption *options = 0 ) const;

/**
 * Make an image where pixel values are coordinates.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage xyz( int width, int height, VOption *options = 0 );

/**
 * Make a zone plate.
 * @param width Image width in pixels.
 * @param height Image height in pixels.
 * @param options Optional options.
 * @return Output image.
 */
static VImage zone( int width, int height, VOption *options = 0 );

/**
 * Zoom an image.
 * @param xfac Horizontal zoom factor.
 * @param yfac Vertical zoom factor.
 * @param options Optional options.
 * @return Output image.
 */
VImage zoom( int xfac, int yfac, VOption *options = 0 ) const;
