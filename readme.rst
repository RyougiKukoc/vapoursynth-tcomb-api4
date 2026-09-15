Description
===========

TComb is a temporal comb filter (it reduces rainbowing and dot crawl
artifacts in static areas of the picture). It will ONLY work with NTSC
material, and WILL NOT work with telecined material where the
rainbowing/dotcrawl was introduced prior to the telecine process! It must be
used before ivtc or deinterlace.


Usage
=====
::

   tcomb.TComb(clip clip[, int mode=2, int fthreshl=4, fthreshc=5, othreshl=5, othreshc=6, bint map=False, float scthresh=12.0])

Parameters:
   clip
      Clip to process. Must be 8 bit Gray or YUV with constant format and dimensions.

   mode
      * 0 - process luma only (remove dotcrawl)
      * 1 - process chroma only (remove rainbows)
      * 2 - process both

   fthreshl

   fthreshc
      Filtered pixel correlation thresholds.

      One of the things TComb checks for is correlation between filtered values over the length
      of the filtering window. If all values differ by less than fthreshl (for luma) or fthreshc
      (for chroma) then the filtered values are considered to be correlated. Larger values will
      allow more filtering (will be more effective at removing rainbowing/dot crawl), but will also
      create more artifacts. A good range of values is between 4 and 7.

   othreshl

   othreshc
      Original pixel correlation thresholds.

      One of the things TComb checks for is correlation between original pixel values from every
      other field of the same parity. Due to the oscillation period, these values should be equal
      or very similar in static areas containing dot crawl or rainbowing. If the pixel values
      differ by less than othreshl (for luma) or othreshc (for chroma) then the pixels are considered
      to be correlated. Larger values will allow more filtering (will be more effective at removing
      rainbowing/dotcrawl), but will also create more artifacts. A good range of values
      is between 4 and 8.

   map
      Instead of filtering the image, shows which pixels would get filtered
      and how.

      Each pixel in the output frame will have one of the following values
      indicating how it is being filtered:

      * 0 - not being filtered
      * 85 - [1 2 1] average of (n,n+1,n+2)
      * 170 - [1 2 1] average of (n-2,n-1,n)
      * 255 - [1 2 1] average of (n-1,n,n+1)

      n = current frame

   scthresh
      Scene change threshold.

      Sets the scenechange detection threshold as a percentage of maximum
      change on the luma plane.


Installation
============

Windows and Linux x86_64 users can install the package directly from the Git
repository:

::

   pip install "vapoursynth-tcomb @ git+https://github.com/RyougiKukoc/vapoursynth-tcomb-api4.git"

The source-install wheel build first tries to download the matching GitHub
Release asset for its platform:

::

   https://github.com/RyougiKukoc/vapoursynth-tcomb-api4/releases/download/v4.4/tcomb-msys2-ucrt64.zip
   https://github.com/RyougiKukoc/vapoursynth-tcomb-api4/releases/download/v4.4/tcomb-linux-x86_64.zip

If the matching asset is unavailable, the build hook falls back to a local
Meson build. Set ``TCOMB_FORCE_BUILD=1`` to select that path deliberately.

To force a local build:

::

   set TCOMB_FORCE_BUILD=1
   pip install "vapoursynth-tcomb @ git+https://github.com/RyougiKukoc/vapoursynth-tcomb-api4.git"

To test a local or custom prebuilt zip:

::

   set TCOMB_PREBUILT_URL=C:\path\to\tcomb-msys2-ucrt64.zip
   pip install --force-reinstall --no-deps --no-build-isolation .

The wheel installs the plugin under ``vapoursynth/plugins/tcomb/`` with a
``manifest.vs`` file so VapourSynth can autoload the platform-native plugin.

Linux releases are built in a manylinux2014 container. TComb itself therefore
does not require a newer glibc than the current VapourSynth runtime wheel;
VapourSynth R79 currently requires glibc 2.27 or newer. To build locally,
install a C compiler and ``pkg-config``; the installed VapourSynth pip wheel
supplies the API4 headers and pkg-config metadata automatically:

::

   sudo apt-get install build-essential pkg-config
   pip install "vapoursynth-tcomb @ git+https://github.com/RyougiKukoc/vapoursynth-tcomb-api4.git"

The published Linux wheel is tagged ``manylinux_2_27_x86_64`` to match that
VapourSynth runtime baseline. ``TCOMB_FORCE_BUILD=1`` remains available for
users who provide their own compatible VapourSynth SDK/runtime.


Compilation
===========

::

   meson build
   ninja -C build
   
Or:

::

   ./autogen.sh
   ./configure
   make


License
=======

GPL 2, like the Avisynth filter.
