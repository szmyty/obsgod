CC ?= cc
PKG_CONFIG ?= pkg-config
SRC ?= gstobsgodcapture.c
OUTPUT ?= libgstobsgodcapture.so
PACKAGES = gstreamer-1.0 gstreamer-base-1.0 gstreamer-video-1.0 libpipewire-0.3
CFLAGS ?= -O2

.PHONY: all clean
all: $(OUTPUT)

$(OUTPUT): $(SRC)
	$(CC) $(CFLAGS) -std=c11 -Wall -Wextra -Werror -fPIC -shared -Wl,--build-id=none \
	  -ffile-prefix-map=$(CURDIR)=. -fmacro-prefix-map=$(CURDIR)=. \
	  $$($(PKG_CONFIG) --cflags $(PACKAGES)) $(SRC) -o $(OUTPUT) \
	  $$($(PKG_CONFIG) --libs $(PACKAGES))

clean:
	rm -f $(OUTPUT)
