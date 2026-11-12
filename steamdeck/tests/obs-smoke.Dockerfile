FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
RUN --mount=type=secret,id=proxy_ca,required=true apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends ca-certificates obs-studio obs-plugins xvfb xauth libgl1-mesa-dri mesa-utils python3 python3-websockets ffmpeg pulseaudio dbus-x11 libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-plugins-good gstreamer1.0-pipewire libobs-dev gcc pkg-config meson ninja-build && rm -rf /var/lib/apt/lists/*
ENV LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1

RUN --mount=type=secret,id=proxy_ca,required=true apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends pipewire pipewire-bin wireplumber gstreamer1.0-tools && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home deck

# Development headers for the app-filtered PipeWire source and its independent
# native producer fixture. Runtime audio/video libraries remain system packages.
RUN --mount=type=secret,id=proxy_ca,required=true apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends libpipewire-0.3-dev && rm -rf /var/lib/apt/lists/*
