Run this script to make sure there is absolutely no RGB: 


gs -o BG-CMYK.pdf -sDEVICE=pdfwrite \
  -dProcessColorModel=/DeviceCMYK \
  -sColorConversionStrategy=CMYK \
  -sColorConversionStrategyForImages=CMYK \
  -dOverrideICC \
  BG.pdf