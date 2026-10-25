# Third-party licenses

A game built on pygamine ships pygame-ce, and pygame-ce bundles the native
libraries below. Their licenses ask for their copyright notices and license
texts to travel with binary copies, so every game's build puts this folder
next to its executable.

The texts come from pygame-ce's own `docs/licenses/` at the release the
games use (2.5.7), or from each library's own repository where pygame-ce has
none. PortMidi's text also comes from its own repository, because pygame-ce's
copy holds the Apache 2.0 license instead of PortMidi's.

| Library | License | File | Shipped on |
|---|---|---|---|
| pygame-ce | LGPL 2.1 | `pygame-ce.txt` | all |
| pygamine | MIT | `pygamine.txt` | all |
| SDL2 | zlib | `sdl2.txt` | all |
| SDL2_image | zlib | `sdl2_image.txt` | all |
| SDL2_mixer | zlib | `sdl2_mixer.txt` | all |
| SDL2_ttf | zlib | `sdl2_ttf.txt` | all |
| SDL_gfx (compiled into pygame-ce) | zlib | `sdl_gfx.txt` | all |
| FreeType | FreeType License (FTL) | `freetype.txt` | all |
| libpng | libpng License | `png.txt` | all |
| libjpeg | IJG License | `jpeg.txt` | all |
| libtiff | libtiff License | `tiff.txt` | all |
| libwebp, libsharpyuv | BSD 3-Clause | `webp.txt` | all |
| zlib | zlib | `zlib.txt` | all |
| libogg, libvorbis | BSD 3-Clause | `ogg-vorbis.txt` | all |
| Opus | BSD 3-Clause | `opus.txt` | all |
| opusfile | BSD 3-Clause | `opusfile.txt` | all |
| WavPack | BSD 3-Clause | `wavpack.txt` | all |
| libxmp | MIT | `libxmp.txt` | all |
| PortMidi | MIT-style | `portmidi.txt` | all |
| FLAC | BSD 3-Clause | `FLAC.txt` | macOS, Linux |
| HarfBuzz | Old MIT | `harfbuzz.txt` | macOS, Linux |
| Brotli | MIT | `brotli.txt` | macOS, Linux |
| mpg123 | LGPL 2.1 | `mpg123.txt` | macOS, Linux |
| libsndfile | LGPL 2.1 | `libsndfile.txt` | macOS, Linux |
| FluidSynth | LGPL 2.1 | `fluidsynth.txt` | macOS, Linux |
| sse2neon (compiled into pygame-ce on ARM) | MIT | `sse2neon-h.txt` | macOS |
| zlib-ng | zlib | `zlib-ng.txt` | macOS |
| alsa-lib | LGPL 2.1 | `alsa-lib.txt` | Linux |

The LGPL libraries are dynamically linked (separate `.dll` / `.so` / `.dylib`
files in the build), so a player can swap in their own builds of them.

When pygame-ce is upgraded, compare this list with the libraries its wheels
bundle (the `.dll` files in `pygame/` on Windows, `pygame_ce.libs/` on Linux
and `pygame/.dylibs/` on macOS) and refresh the texts.
