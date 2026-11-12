/* SPDX-License-Identifier: MIT
 * App-scoped Gamescope PipeWire capture. See README.md for the private SPA
 * extension and its limitations. Unknown/unsupported selection never becomes
 * an unrestricted capture stream.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <gst/base/gstpushsrc.h>
#include <gst/video/video.h>
#include <pipewire/pipewire.h>
#include <spa/buffer/meta.h>
#include <spa/param/video/format-utils.h>
#include <spa/pod/builder.h>
#include <spa/pod/parser.h>
#include <errno.h>
#include <string.h>

#ifndef PACKAGE
#define PACKAGE "obsgod"
#endif

#define GAME_SCOPE_APP_ID 0x70001u
#define GAME_SCOPE_REQUESTED_SIZE 0x70000u
#define FRAME_RATE 30u
#define MAX_DIMENSION 4096u
#define MAX_FRAME_BYTES (64u * 1024u * 1024u)

typedef struct _GstObsGodCapture {
  GstPushSrc parent;
  GMutex mutex;
  GCond changed;
  guint64 app_id;
  gchar *target;
  gchar *producer_serial;
  guint stale_ms;
  struct pw_thread_loop *loop;
  struct pw_context *context;
  struct pw_core *core;
  struct pw_registry *registry;
  struct pw_node *producer;
  struct spa_hook registry_hook;
  struct spa_hook core_hook;
  struct spa_hook node_hook;
  struct spa_hook stream_hook;
  uint32_t producer_id;
  uint32_t producer_version;
  int registry_sync;
  int probe_sync;
  gboolean registry_done;
  gboolean probe_done;
  gboolean advertised;
  gboolean ambiguous;
  struct pw_stream *stream;
  gboolean stopping;
  gboolean flushing;
  gboolean negotiated;
  gboolean failed;
  GstVideoInfo info;
  GstBuffer *latest;
  gint64 received_us;
  gint64 next_us;
  guint64 sequence;
} GstObsGodCapture;

typedef struct _GstObsGodCaptureClass { GstPushSrcClass parent_class; } GstObsGodCaptureClass;

G_DEFINE_TYPE(GstObsGodCapture, gst_obsgod_capture, GST_TYPE_PUSH_SRC)

enum { PROP_NONE, PROP_APP_ID, PROP_TARGET, PROP_STALE_MS };

static GstStaticPadTemplate source_template = GST_STATIC_PAD_TEMPLATE(
  "src", GST_PAD_SRC, GST_PAD_ALWAYS,
  GST_STATIC_CAPS("video/x-raw, format=(string)BGRx, width=(int)[1,4096], "
                  "height=(int)[1,4096], framerate=(fraction)30/1, "
                  "pixel-aspect-ratio=(fraction)1/1"));

static void fail_locked(GstObsGodCapture *self)
{
  self->failed = TRUE;
  self->negotiated = FALSE;
  gst_clear_buffer(&self->latest);
  self->received_us = 0;
  g_cond_broadcast(&self->changed);
}

/* PipeWire can propagate an unknown consumer Format key into the negotiated
 * result. An echo alone therefore does not prove that the producer implements
 * Gamescope's app filter. Inspect its own EnumFormat BEFORE creating a stream. */
static gboolean selection_allows(const struct spa_pod *value, guint64 app_id)
{
  int64_t scalar;
  if (spa_pod_get_long(value, &scalar) == 0)
    return scalar > 0 && (guint64)scalar == app_id;
  if (value->type != SPA_TYPE_Choice || value->size < sizeof(struct spa_pod_choice_body))
    return FALSE;
  const struct spa_pod_choice *choice = (const struct spa_pod_choice *)value;
  if (choice->body.child.type != SPA_TYPE_Long || choice->body.child.size != sizeof(int64_t))
    return FALSE;
  uint32_t count = SPA_POD_CHOICE_N_VALUES(choice);
  const int64_t *values = SPA_POD_CHOICE_VALUES(choice);
  if (choice->body.type == SPA_CHOICE_Range && count >= 3)
    return values[1] <= (int64_t)app_id && values[2] >= (int64_t)app_id;
  if (choice->body.type == SPA_CHOICE_Enum || choice->body.type == SPA_CHOICE_None) {
    for (uint32_t i = 0; i < count; i++)
      if (values[i] > 0 && (guint64)values[i] == app_id)
        return TRUE;
  }
  return FALSE;
}

static gboolean selected_id(const struct spa_pod *value, int64_t *id)
{
  if (spa_pod_get_long(value, id) == 0)
    return TRUE;
  if (value->type != SPA_TYPE_Choice || value->size < sizeof(struct spa_pod_choice_body))
    return FALSE;
  const struct spa_pod_choice *choice = (const struct spa_pod_choice *)value;
  if (choice->body.type != SPA_CHOICE_None ||
      choice->body.child.type != SPA_TYPE_Long ||
      choice->body.child.size != sizeof(int64_t))
    return FALSE;
  uint32_t count = SPA_POD_CHOICE_N_VALUES(choice);
  if (count == 0 || count > 8)
    return FALSE;
  const int64_t *values = SPA_POD_CHOICE_VALUES(choice);
  memcpy(id, &values[0], sizeof(*id));
  /* PipeWire fixation can retain duplicate None values. All must agree;
   * accepting only the first would hide an ambiguous unrestricted value. */
  for (uint32_t i = 1; i < count; i++)
    if (values[i] != *id)
      return FALSE;
  return TRUE;
}

static void node_param(void *data, int seq, uint32_t id, uint32_t index,
                        uint32_t next, const struct spa_pod *param)
{
  GstObsGodCapture *self = data;
  (void)seq;
  (void)index;
  (void)next;
  if (id != SPA_PARAM_EnumFormat || !param)
    return;
  const struct spa_pod_prop *selection = spa_pod_find_prop(param, NULL, GAME_SCOPE_APP_ID);
  const struct spa_pod_prop *format = spa_pod_find_prop(param, NULL, SPA_FORMAT_VIDEO_format);
  uint32_t media_type = 0, subtype = 0, pixel_format = 0;
  if (!selection || !format ||
      spa_pod_find_prop(param, NULL, SPA_FORMAT_VIDEO_modifier) != NULL ||
      spa_format_parse(param, &media_type, &subtype) < 0 ||
      media_type != SPA_MEDIA_TYPE_video || subtype != SPA_MEDIA_SUBTYPE_raw ||
      spa_pod_get_id(&format->value, &pixel_format) < 0 ||
      pixel_format != SPA_VIDEO_FORMAT_BGRx || !selection_allows(&selection->value, self->app_id))
    return;
  g_mutex_lock(&self->mutex);
  self->advertised = TRUE;
  g_mutex_unlock(&self->mutex);
}

static const struct pw_node_events node_events = {
  PW_VERSION_NODE_EVENTS,
  .param = node_param
};

static void registry_global(void *data, uint32_t id, uint32_t permissions,
                             const char *type, uint32_t version, const struct spa_dict *props)
{
  GstObsGodCapture *self = data;
  (void)permissions;
  if (strcmp(type, PW_TYPE_INTERFACE_Node) || !props)
    return;
  const char *name = spa_dict_lookup(props, PW_KEY_NODE_NAME);
  const char *serial = spa_dict_lookup(props, PW_KEY_OBJECT_SERIAL);
  const char *media_class = spa_dict_lookup(props, PW_KEY_MEDIA_CLASS);
  if ((!name || strcmp(name, self->target)) && (!serial || strcmp(serial, self->target)))
    return;
  if (!media_class || strcmp(media_class, "Video/Source"))
    return;
  g_mutex_lock(&self->mutex);
  if (self->producer_id != PW_ID_ANY && self->producer_id != id) {
    self->ambiguous = TRUE;
    fail_locked(self);
  } else if (self->producer_id == PW_ID_ANY) {
    gboolean numeric = serial && *serial && strlen(serial) <= 20;
    for (const char *p = serial; numeric && *p; p++)
      numeric = g_ascii_isdigit(*p);
    errno = 0;
    guint64 number = numeric ? g_ascii_strtoull(serial, NULL, 10) : 0;
    if (!numeric || number == 0 || errno == ERANGE) {
      fail_locked(self);
    } else {
      self->producer_id = id;
      self->producer_version = MIN(version, PW_VERSION_NODE);
      self->producer_serial = g_strdup(serial);
    }
  }
  g_mutex_unlock(&self->mutex);
}

static void registry_remove(void *data, uint32_t id)
{
  GstObsGodCapture *self = data;
  g_mutex_lock(&self->mutex);
  if (!self->stopping && id == self->producer_id)
    fail_locked(self);
  g_mutex_unlock(&self->mutex);
}

static const struct pw_registry_events registry_events = {
  PW_VERSION_REGISTRY_EVENTS,
  .global = registry_global,
  .global_remove = registry_remove
};

static void core_done(void *data, uint32_t id, int seq)
{
  GstObsGodCapture *self = data;
  (void)id;
  g_mutex_lock(&self->mutex);
  if (seq == self->registry_sync)
    self->registry_done = TRUE;
  if (seq == self->probe_sync)
    self->probe_done = TRUE;
  g_cond_broadcast(&self->changed);
  g_mutex_unlock(&self->mutex);
}

static void core_error(void *data, uint32_t id, int seq, int result, const char *message)
{
  GstObsGodCapture *self = data;
  (void)id;
  (void)seq;
  (void)result;
  (void)message;
  g_mutex_lock(&self->mutex);
  if (!self->stopping)
    fail_locked(self);
  g_mutex_unlock(&self->mutex);
}

static const struct pw_core_events core_events = {
  PW_VERSION_CORE_EVENTS,
  .done = core_done,
  .error = core_error
};

static void stream_state(void *data, enum pw_stream_state old,
                         enum pw_stream_state state, const char *error)
{
  GstObsGodCapture *self = data;
  (void)old;
  (void)error; /* Never export server-supplied text. */
  if (state == PW_STREAM_STATE_ERROR || state == PW_STREAM_STATE_UNCONNECTED) {
    g_mutex_lock(&self->mutex);
    if (!self->stopping)
      fail_locked(self);
    g_mutex_unlock(&self->mutex);
  }
}

static void stream_format(void *data, uint32_t id, const struct spa_pod *param)
{
  GstObsGodCapture *self = data;
  struct spa_video_info_raw video = {0};
  const struct spa_pod_prop *selection;
  int64_t echoed = 0;
  gboolean valid;
  if (id != SPA_PARAM_Format)
    return;
  selection = param ? spa_pod_find_prop(param, NULL, GAME_SCOPE_APP_ID) : NULL;
  valid = param && selection &&
    selected_id(&selection->value, &echoed) &&
    echoed > 0 && echoed != 769 && (guint64)echoed == self->app_id &&
    spa_format_video_raw_parse(param, &video) >= 0 &&
    video.format == SPA_VIDEO_FORMAT_BGRx &&
    video.size.width > 0 && video.size.width <= MAX_DIMENSION &&
    video.size.height > 0 && video.size.height <= MAX_DIMENSION &&
    (guint64)video.size.width * video.size.height * 4 <= MAX_FRAME_BYTES;

  g_mutex_lock(&self->mutex);
  if (self->stopping) {
    g_mutex_unlock(&self->mutex);
    return;
  }
  /* Format changes restart the element instead of exposing old-sized frames.
   * An OBS source supervisor can reconnect while its background remains live. */
  if (!valid || (self->negotiated &&
      (GST_VIDEO_INFO_WIDTH(&self->info) != (gint)video.size.width ||
       GST_VIDEO_INFO_HEIGHT(&self->info) != (gint)video.size.height))) {
    fail_locked(self);
    g_mutex_unlock(&self->mutex);
    return;
  }
  gst_video_info_set_format(&self->info, GST_VIDEO_FORMAT_BGRx,
                            video.size.width, video.size.height);
  self->negotiated = TRUE;
  g_cond_broadcast(&self->changed);
  g_mutex_unlock(&self->mutex);

  uint8_t storage[512];
  struct spa_pod_builder builder = SPA_POD_BUILDER_INIT(storage, sizeof(storage));
  const struct spa_pod *params[] = {
    spa_pod_builder_add_object(&builder, SPA_TYPE_OBJECT_ParamBuffers,
      SPA_PARAM_Buffers,
      SPA_PARAM_BUFFERS_buffers, SPA_POD_CHOICE_RANGE_Int(4, 2, 8),
      SPA_PARAM_BUFFERS_blocks, SPA_POD_Int(1),
      SPA_PARAM_BUFFERS_size, SPA_POD_Int((int)(video.size.width * video.size.height * 4)),
      SPA_PARAM_BUFFERS_stride, SPA_POD_Int((int)(video.size.width * 4)),
      SPA_PARAM_BUFFERS_dataType, SPA_POD_CHOICE_FLAGS_Int(
        (1u << SPA_DATA_MemFd) | (1u << SPA_DATA_MemPtr)))
  };
  if (pw_stream_update_params(self->stream, params, G_N_ELEMENTS(params)) < 0) {
    g_mutex_lock(&self->mutex);
    fail_locked(self);
    g_mutex_unlock(&self->mutex);
  }
}

static void stream_process(void *data)
{
  GstObsGodCapture *self = data;
  struct pw_buffer *received;
  /* Bound work per callback even if another thread continually supplies data. */
  for (guint count = 0; count < 8 &&
       (received = pw_stream_dequeue_buffer(self->stream)) != NULL; count++) {
    struct spa_buffer *buffer = received->buffer;
    GstBuffer *copy = NULL;
    GstMapInfo mapped;
    gboolean malformed = FALSE;
    g_mutex_lock(&self->mutex);
    if (!self->stopping && !self->failed && self->negotiated &&
        buffer && buffer->n_datas == 1) {
      struct spa_data *plane = &buffer->datas[0];
      struct spa_chunk *chunk = plane->chunk;
      struct spa_meta_header *header = spa_buffer_find_meta_data(
        buffer, SPA_META_Header, sizeof(struct spa_meta_header));
      guint width = GST_VIDEO_INFO_WIDTH(&self->info);
      guint height = GST_VIDEO_INFO_HEIGHT(&self->info);
      guint64 row = (guint64)width * 4;
      gboolean corrupted = chunk &&
        ((chunk->flags & (SPA_CHUNK_FLAG_CORRUPTED | SPA_CHUNK_FLAG_EMPTY)) ||
         (header && (header->flags & SPA_META_HEADER_FLAG_CORRUPTED)));
      if (!corrupted && chunk && chunk->size > 0) {
        guint64 extent = chunk->stride > 0
          ? (guint64)(height - 1) * (guint64)chunk->stride + row : 0;
        if (!plane->data ||
            (plane->type != SPA_DATA_MemFd && plane->type != SPA_DATA_MemPtr) ||
            chunk->stride < (gint32)row || extent == 0 ||
            extent > chunk->size || chunk->offset > plane->maxsize ||
            chunk->size > plane->maxsize - chunk->offset ||
            plane->maxsize > MAX_FRAME_BYTES) {
          malformed = TRUE;
        } else {
          copy = gst_buffer_new_allocate(NULL, (gsize)row * height, NULL);
          if (!copy || !gst_buffer_map(copy, &mapped, GST_MAP_WRITE)) {
            malformed = TRUE;
            gst_clear_buffer(&copy);
          } else {
            const guint8 *pixels = (const guint8 *)plane->data + chunk->offset;
            for (guint y = 0; y < height; y++)
              memcpy(mapped.data + (gsize)y * row,
                     pixels + (gsize)y * chunk->stride, (gsize)row);
            gst_buffer_unmap(copy, &mapped);
          }
        }
      }
    } else if (!self->stopping && !self->failed && self->negotiated) {
      malformed = TRUE;
    }
    if (malformed)
      fail_locked(self);
    if (copy) {
      gst_clear_buffer(&self->latest);
      self->latest = copy;
      self->received_us = g_get_monotonic_time();
      g_cond_broadcast(&self->changed);
    }
    g_mutex_unlock(&self->mutex);
    pw_stream_queue_buffer(self->stream, received);
  }
}

static const struct pw_stream_events stream_events = {
  PW_VERSION_STREAM_EVENTS,
  .state_changed = stream_state,
  .param_changed = stream_format,
  .process = stream_process
};

static void disconnect_capture(GstObsGodCapture *self)
{
  g_mutex_lock(&self->mutex);
  self->stopping = TRUE;
  self->flushing = TRUE;
  g_cond_broadcast(&self->changed);
  g_mutex_unlock(&self->mutex);
  if (self->loop) {
    pw_thread_loop_lock(self->loop);
    if (self->stream) {
      pw_stream_destroy(self->stream);
      self->stream = NULL;
    }
    if (self->producer) {
      pw_proxy_destroy((struct pw_proxy *)self->producer);
      self->producer = NULL;
    }
    if (self->registry) {
      pw_proxy_destroy((struct pw_proxy *)self->registry);
      self->registry = NULL;
    }
    if (self->core) {
      pw_core_disconnect(self->core);
      self->core = NULL;
    }
    if (self->context) {
      pw_context_destroy(self->context);
      self->context = NULL;
    }
    pw_thread_loop_unlock(self->loop);
    pw_thread_loop_stop(self->loop);
    pw_thread_loop_destroy(self->loop);
    self->loop = NULL;
  }
  g_mutex_lock(&self->mutex);
  gst_clear_buffer(&self->latest);
  self->negotiated = FALSE;
  self->received_us = 0;
  g_clear_pointer(&self->producer_serial, g_free);
  g_mutex_unlock(&self->mutex);
}

static gboolean capture_start(GstBaseSrc *base)
{
  GstObsGodCapture *self = (GstObsGodCapture *)base;
  static gsize initialized;
  const char *stage = "loop";
  if (self->app_id == 0 || self->app_id == 769 || self->app_id > G_MAXUINT32 ||
      !self->target || !*self->target) {
    GST_ELEMENT_ERROR(self, RESOURCE, SETTINGS,
      ("Game-only capture requires a nonzero game app ID; Steam UI is excluded"), (NULL));
    return FALSE;
  }
  if (g_once_init_enter(&initialized)) {
    pw_init(NULL, NULL);
    g_once_init_leave(&initialized, 1);
  }
  g_mutex_lock(&self->mutex);
  self->stopping = self->flushing = self->failed = self->negotiated = FALSE;
  self->received_us = self->next_us = 0;
  self->sequence = 0;
  self->producer_id = PW_ID_ANY;
  self->registry_done = self->probe_done = self->advertised = self->ambiguous = FALSE;
  self->registry_sync = self->probe_sync = -1;
  g_mutex_unlock(&self->mutex);
  gint64 deadline = g_get_monotonic_time() + 5 * G_TIME_SPAN_SECOND;
  self->loop = pw_thread_loop_new("obsgod-game-capture", NULL);
  if (!self->loop || pw_thread_loop_start(self->loop) < 0)
    goto failed;
  pw_thread_loop_lock(self->loop);
  stage = "core-connection";
  self->context = pw_context_new(pw_thread_loop_get_loop(self->loop), NULL, 0);
  self->core = self->context ? pw_context_connect(self->context, NULL, 0) : NULL;
  if (!self->core) {
    pw_thread_loop_unlock(self->loop);
    goto failed;
  }
  pw_core_add_listener(self->core, &self->core_hook, &core_events, self);
  stage = "source-discovery";
  self->registry = pw_core_get_registry(self->core, PW_VERSION_REGISTRY, 0);
  if (!self->registry) {
    pw_thread_loop_unlock(self->loop);
    goto failed;
  }
  pw_registry_add_listener(self->registry, &self->registry_hook, &registry_events, self);
  self->registry_sync = pw_core_sync(self->core, PW_ID_CORE, 0);
  pw_thread_loop_unlock(self->loop);
  g_mutex_lock(&self->mutex);
  while (!self->registry_done && !self->failed && !self->flushing)
    if (!g_cond_wait_until(&self->changed, &self->mutex, deadline))
      break;
  gboolean found = self->registry_done && self->producer_id != PW_ID_ANY &&
                   self->producer_serial != NULL &&
                   !self->ambiguous && !self->failed && !self->flushing;
  g_mutex_unlock(&self->mutex);
  if (!found)
    goto failed;
  stage = "source-advertisement";
  pw_thread_loop_lock(self->loop);
  self->producer = pw_registry_bind(self->registry, self->producer_id,
    PW_TYPE_INTERFACE_Node, self->producer_version, 0);
  if (!self->producer) {
    pw_thread_loop_unlock(self->loop);
    goto failed;
  }
  pw_node_add_listener(self->producer, &self->node_hook, &node_events, self);
  pw_node_enum_params(self->producer, 1, SPA_PARAM_EnumFormat, 0, UINT32_MAX, NULL);
  self->probe_sync = pw_core_sync(self->core, PW_ID_CORE, 0);
  pw_thread_loop_unlock(self->loop);
  g_mutex_lock(&self->mutex);
  while (!self->probe_done && !self->failed && !self->flushing)
    if (!g_cond_wait_until(&self->changed, &self->mutex, deadline))
      break;
  gboolean supported = self->probe_done && self->advertised && !self->failed && !self->flushing;
  g_mutex_unlock(&self->mutex);
  if (!supported)
    goto failed;
  stage = "format-negotiation";
  pw_thread_loop_lock(self->loop);
  self->stream = pw_stream_new(self->core, "OBSGod app-scoped capture",
    pw_properties_new(PW_KEY_MEDIA_TYPE, "Video", PW_KEY_MEDIA_CATEGORY, "Capture",
      PW_KEY_MEDIA_ROLE, "Screen", PW_KEY_TARGET_OBJECT, self->producer_serial, NULL));
  if (!self->stream) {
    pw_thread_loop_unlock(self->loop);
    goto failed;
  }
  pw_stream_add_listener(self->stream, &self->stream_hook, &stream_events, self);
  uint8_t storage[1024];
  struct spa_pod_builder builder = SPA_POD_BUILDER_INIT(storage, sizeof(storage));
  struct spa_rectangle requested = SPA_RECTANGLE(1280, 720);
  struct spa_rectangle preferred = SPA_RECTANGLE(1280, 720);
  struct spa_rectangle minimum = SPA_RECTANGLE(1, 1);
  struct spa_rectangle maximum = SPA_RECTANGLE(MAX_DIMENSION, MAX_DIMENSION);
  const struct spa_pod *params[] = {
    spa_pod_builder_add_object(&builder, SPA_TYPE_OBJECT_Format, SPA_PARAM_EnumFormat,
      SPA_FORMAT_mediaType, SPA_POD_Id(SPA_MEDIA_TYPE_video),
      SPA_FORMAT_mediaSubtype, SPA_POD_Id(SPA_MEDIA_SUBTYPE_raw),
      SPA_FORMAT_VIDEO_format, SPA_POD_Id(SPA_VIDEO_FORMAT_BGRx),
      SPA_FORMAT_VIDEO_size, SPA_POD_CHOICE_RANGE_Rectangle(&preferred, &minimum, &maximum),
      GAME_SCOPE_REQUESTED_SIZE, SPA_POD_Rectangle(&requested),
      GAME_SCOPE_APP_ID, SPA_POD_Long((int64_t)self->app_id))
  };
  int result = pw_stream_connect(self->stream, PW_DIRECTION_INPUT, PW_ID_ANY,
    PW_STREAM_FLAG_AUTOCONNECT | PW_STREAM_FLAG_MAP_BUFFERS, params, G_N_ELEMENTS(params));
  pw_thread_loop_unlock(self->loop);
  if (result < 0)
    goto failed;
  g_mutex_lock(&self->mutex);
  while (!self->negotiated && !self->failed && !self->flushing)
    if (!g_cond_wait_until(&self->changed, &self->mutex, deadline))
      break;
  gboolean ready = self->negotiated && !self->failed && !self->flushing;
  g_mutex_unlock(&self->mutex);
  if (ready)
    return TRUE;
failed:
  disconnect_capture(self);
  GST_ELEMENT_ERROR(self, RESOURCE, SETTINGS,
    ("Gamescope did not confirm app-only capture; unrestricted capture is refused"),
    ("Capture validation stage: %s", stage));
  return FALSE;
}

static gboolean capture_stop(GstBaseSrc *base)
{
  disconnect_capture((GstObsGodCapture *)base);
  return TRUE;
}

static gboolean capture_unlock(GstBaseSrc *base)
{
  GstObsGodCapture *self = (GstObsGodCapture *)base;
  g_mutex_lock(&self->mutex);
  self->flushing = TRUE;
  g_cond_broadcast(&self->changed);
  g_mutex_unlock(&self->mutex);
  return TRUE;
}

static gboolean capture_unlock_stop(GstBaseSrc *base)
{
  GstObsGodCapture *self = (GstObsGodCapture *)base;
  g_mutex_lock(&self->mutex);
  self->flushing = FALSE;
  g_mutex_unlock(&self->mutex);
  return TRUE;
}

static GstCaps *capture_caps(GstBaseSrc *base, GstCaps *filter)
{
  GstObsGodCapture *self = (GstObsGodCapture *)base;
  GstCaps *caps;
  g_mutex_lock(&self->mutex);
  if (self->negotiated)
    caps = gst_caps_new_simple("video/x-raw", "format", G_TYPE_STRING, "BGRx",
      "width", G_TYPE_INT, GST_VIDEO_INFO_WIDTH(&self->info),
      "height", G_TYPE_INT, GST_VIDEO_INFO_HEIGHT(&self->info),
      "framerate", GST_TYPE_FRACTION, FRAME_RATE, 1,
      "pixel-aspect-ratio", GST_TYPE_FRACTION, 1, 1, NULL);
  else
    caps = gst_static_pad_template_get_caps(&source_template);
  g_mutex_unlock(&self->mutex);
  if (filter) {
    GstCaps *intersection = gst_caps_intersect_full(filter, caps, GST_CAPS_INTERSECT_FIRST);
    gst_caps_unref(caps);
    caps = intersection;
  }
  return caps;
}

static GstFlowReturn capture_create(GstPushSrc *push, GstBuffer **output)
{
  GstObsGodCapture *self = (GstObsGodCapture *)push;
  GstBuffer *buffer = NULL;
  gsize bytes;
  g_mutex_lock(&self->mutex);
  if (!self->next_us)
    self->next_us = g_get_monotonic_time();
  while (!self->flushing && !self->stopping && !self->failed &&
         g_get_monotonic_time() < self->next_us)
    g_cond_wait_until(&self->changed, &self->mutex, self->next_us);
  if (self->flushing || self->stopping) {
    g_mutex_unlock(&self->mutex);
    return GST_FLOW_FLUSHING;
  }
  if (self->failed || !self->negotiated) {
    g_mutex_unlock(&self->mutex);
    GST_ELEMENT_ERROR(self, RESOURCE, READ,
      ("App-only capture lost its confirmed format or valid buffer; background required"), (NULL));
    return GST_FLOW_ERROR;
  }
  gint64 now = g_get_monotonic_time();
  if (self->latest && now - self->received_us <= (gint64)self->stale_ms * 1000)
    buffer = gst_buffer_copy(self->latest);
  bytes = GST_VIDEO_INFO_SIZE(&self->info);
  guint64 sequence = self->sequence++;
  self->next_us = MAX(self->next_us + G_TIME_SPAN_SECOND / FRAME_RATE,
                     now - G_TIME_SPAN_SECOND / FRAME_RATE);
  g_mutex_unlock(&self->mutex);
  if (!buffer) {
    buffer = gst_buffer_new_allocate(NULL, bytes, NULL);
    if (buffer)
      gst_buffer_memset(buffer, 0, 0, bytes);
  }
  if (!buffer)
    return GST_FLOW_ERROR;
  GST_BUFFER_PTS(buffer) = GST_CLOCK_TIME_NONE;
  GST_BUFFER_DTS(buffer) = GST_CLOCK_TIME_NONE;
  GST_BUFFER_DURATION(buffer) = GST_SECOND / FRAME_RATE;
  GST_BUFFER_OFFSET(buffer) = sequence;
  *output = buffer;
  return GST_FLOW_OK;
}

static void set_property(GObject *object, guint property, const GValue *value,
                         GParamSpec *spec)
{
  GstObsGodCapture *self = (GstObsGodCapture *)object;
  if (GST_STATE(self) > GST_STATE_READY) {
    GST_WARNING_OBJECT(self, "Capture properties are immutable while active");
    return;
  }
  switch (property) {
  case PROP_APP_ID: self->app_id = g_value_get_uint64(value); break;
  case PROP_TARGET: g_free(self->target); self->target = g_value_dup_string(value); break;
  case PROP_STALE_MS: self->stale_ms = g_value_get_uint(value); break;
  default: G_OBJECT_WARN_INVALID_PROPERTY_ID(object, property, spec); break;
  }
}

static void get_property(GObject *object, guint property, GValue *value, GParamSpec *spec)
{
  GstObsGodCapture *self = (GstObsGodCapture *)object;
  switch (property) {
  case PROP_APP_ID: g_value_set_uint64(value, self->app_id); break;
  case PROP_TARGET: g_value_set_string(value, self->target); break;
  case PROP_STALE_MS: g_value_set_uint(value, self->stale_ms); break;
  default: G_OBJECT_WARN_INVALID_PROPERTY_ID(object, property, spec); break;
  }
}

static void finalize(GObject *object)
{
  GstObsGodCapture *self = (GstObsGodCapture *)object;
  disconnect_capture(self);
  g_free(self->target);
  g_cond_clear(&self->changed);
  g_mutex_clear(&self->mutex);
  G_OBJECT_CLASS(gst_obsgod_capture_parent_class)->finalize(object);
}

static void gst_obsgod_capture_class_init(GstObsGodCaptureClass *klass)
{
  GObjectClass *object = G_OBJECT_CLASS(klass);
  GstElementClass *element = GST_ELEMENT_CLASS(klass);
  GstBaseSrcClass *base = GST_BASE_SRC_CLASS(klass);
  object->set_property = set_property;
  object->get_property = get_property;
  object->finalize = finalize;
  g_object_class_install_property(object, PROP_APP_ID,
    g_param_spec_uint64("app-id", "Game app ID", "Nonzero game app ID; Steam UI769 is refused",
      0, G_MAXUINT32, 0, G_PARAM_READWRITE | GST_PARAM_MUTABLE_READY | G_PARAM_STATIC_STRINGS));
  g_object_class_install_property(object, PROP_TARGET,
    g_param_spec_string("target-object", "PipeWire source", "Gamescope PipeWire node name/serial",
      "gamescope", G_PARAM_READWRITE | GST_PARAM_MUTABLE_READY | G_PARAM_STATIC_STRINGS));
  g_object_class_install_property(object, PROP_STALE_MS,
    g_param_spec_uint("stale-ms", "Stale-frame limit", "Render black after this many milliseconds without a valid source frame",
      250, 10000, 2000, G_PARAM_READWRITE | GST_PARAM_MUTABLE_READY | G_PARAM_STATIC_STRINGS));
  gst_element_class_add_static_pad_template(element, &source_template);
  gst_element_class_set_static_metadata(element, "OBSGod app-only Gamescope capture",
    "Source/Video", "Validated game-scoped PipeWire capture; unsupported selection fails closed",
    "OBSGod contributors");
  base->start = capture_start;
  base->stop = capture_stop;
  base->unlock = capture_unlock;
  base->unlock_stop = capture_unlock_stop;
  base->get_caps = capture_caps;
  GST_PUSH_SRC_CLASS(klass)->create = capture_create;
}

static void gst_obsgod_capture_init(GstObsGodCapture *self)
{
  g_mutex_init(&self->mutex);
  g_cond_init(&self->changed);
  gst_video_info_init(&self->info);
  self->target = g_strdup("gamescope");
  self->stale_ms = 2000;
  gst_base_src_set_live(GST_BASE_SRC(self), TRUE);
  gst_base_src_set_format(GST_BASE_SRC(self), GST_FORMAT_TIME);
  gst_base_src_set_do_timestamp(GST_BASE_SRC(self), TRUE);
}

static gboolean plugin_init(GstPlugin *plugin)
{
  return gst_element_register(plugin, "obsgodgamescopesrc", GST_RANK_NONE,
                              gst_obsgod_capture_get_type());
}

GST_PLUGIN_DEFINE(GST_VERSION_MAJOR, GST_VERSION_MINOR, obsgodcapture,
  "App-scoped Gamescope PipeWire capture", plugin_init, "1.0.0", "MIT/X11",
  "OBSGod", "https://github.com/szmyty/obsgod")
