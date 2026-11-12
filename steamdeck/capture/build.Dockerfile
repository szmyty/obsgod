# The release plugin targets glibc 2.36 and stable GStreamer/PipeWire ABIs so it
# can load in newer OBS Flatpak runtimes without requiring the cloud host ABI.
FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN --mount=type=secret,id=proxy_ca,required=true apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends gcc make pkg-config binutils libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libpipewire-0.3-dev && rm -rf /var/lib/apt/lists/*
