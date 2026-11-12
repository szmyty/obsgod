/* SPDX-License-Identifier: MIT
 * Synthetic PipeWire video source for OBSGod capture tests, not Gamescope.
 * The pw_stream lifecycle follows PipeWire's MIT-licensed video-src example:
 * https://github.com/PipeWire/pipewire/blob/1.4.2/src/examples/video-src.c
 * Copyright (c) 2018 Wim Taymans; test patterns and protocol cases are original.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is furnished to do
 * so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pipewire/pipewire.h>
#include <spa/param/video/format-utils.h>

#define FOCUS_APPID 0x70001
#define REQUESTED_SIZE 0x70000
#define WIDTH 320
#define HEIGHT 180
#define FRAME_BYTES (WIDTH * HEIGHT * 4)

struct fixture {
    struct pw_main_loop *loop;
    struct pw_context *context;
    struct pw_core *core;
    struct pw_stream *stream;
    struct spa_hook listener;
    struct spa_source *timer;
    const char *mode;
    int64_t appid;
    uint32_t frames;
    bool negotiated;
    int result;
};

static void process(void *opaque)
{
    struct fixture *f = opaque;
    struct pw_buffer *pwbuf;
    struct spa_data *data;
    if (!f->negotiated || (!strcmp(f->mode, "stale") && f->frames >= 5))
        return;
    pwbuf = pw_stream_dequeue_buffer(f->stream);
    if (!pwbuf)
        return;
    if (pwbuf->buffer->n_datas != 1) {
        pw_stream_queue_buffer(f->stream, pwbuf);
        return;
    }
    data = &pwbuf->buffer->datas[0];
    if (!data->data || data->maxsize < FRAME_BYTES || !data->chunk) {
        pw_stream_queue_buffer(f->stream, pwbuf);
        return;
    }
    /* Whole-compositor marker is blue. A and B game-only frames are red and
     * green. Any source accidentally defaulting to appid=0 is distinguishable.
     */
    uint8_t b = f->appid == 0 || !strcmp(f->mode, "empty") ? 220 : 10;
    uint8_t g = f->appid == 4243 ? 210 : 20;
    uint8_t r = f->appid == 4242 ? 210 : 10;
    for (unsigned y = 0; y < HEIGHT; ++y) {
        for (unsigned x = 0; x < WIDTH; ++x) {
            uint8_t *p = (uint8_t *)data->data + (y * WIDTH + x) * 4;
            bool marker = x >= (f->frames * 7) % (WIDTH - 20) &&
                          x < (f->frames * 7) % (WIDTH - 20) + 20 &&
                          y >= 30 && y < 50;
            p[0] = marker ? 250 : b;
            p[1] = marker ? 250 : g;
            p[2] = marker ? 250 : r;
            p[3] = 255;
        }
    }
    data->chunk->offset = 0;
    data->chunk->size = !strcmp(f->mode, "short") ? 1 : FRAME_BYTES;
    data->chunk->stride = WIDTH * 4;
    data->chunk->flags = !strcmp(f->mode, "corrupt") ? SPA_CHUNK_FLAG_CORRUPTED :
        !strcmp(f->mode, "empty") ? SPA_CHUNK_FLAG_EMPTY : 0;
    struct spa_meta_header *header = spa_buffer_find_meta_data(
        pwbuf->buffer, SPA_META_Header, sizeof(*header));
    if (header) {
        header->pts = -1;
        header->seq = f->frames;
        header->dts_offset = 0;
        header->flags = !strcmp(f->mode, "corrupt") ? SPA_META_HEADER_FLAG_CORRUPTED : 0;
    }
    ++f->frames;
    pw_stream_queue_buffer(f->stream, pwbuf);
}

static void timer_tick(void *opaque, uint64_t count)
{
    struct fixture *f = opaque;
    (void)count;
    pw_stream_trigger_process(f->stream);
}

static void state_changed(void *opaque, enum pw_stream_state old,
                          enum pw_stream_state state, const char *error)
{
    struct fixture *f = opaque;
    (void)old;
    (void)error;
    fprintf(stderr, "{\"fixture\":\"state\",\"state\":\"%s\"}\n", pw_stream_state_as_string(state));
    fflush(stderr);
    if (state == PW_STREAM_STATE_ERROR) {
        f->result = 1;
        pw_main_loop_quit(f->loop);
    } else if (state == PW_STREAM_STATE_STREAMING) {
        struct timespec initial = {0, 1}, period = {0, 33333333};
        pw_loop_update_timer(pw_main_loop_get_loop(f->loop), f->timer,
                             &initial, &period, false);
    } else if (state == PW_STREAM_STATE_PAUSED) {
        pw_loop_update_timer(pw_main_loop_get_loop(f->loop), f->timer,
                             NULL, NULL, false);
    }
}

static void format_changed(void *opaque, uint32_t id, const struct spa_pod *format)
{
    struct fixture *f = opaque;
    struct spa_video_info_raw info = {0};
    struct spa_pod_builder b;
    const struct spa_pod *params[2];
    uint8_t storage[1024];
    int64_t appid = 0;
    if (id != SPA_PARAM_Format || !format)
        return;
    fprintf(stderr, "{\"fixture\":\"format-received\"}\n");
    fflush(stderr);
    f->negotiated = false;
    if (spa_format_video_raw_parse(format, &info) < 0 ||
        info.format != SPA_VIDEO_FORMAT_BGRx ||
        info.size.width != WIDTH || info.size.height != HEIGHT) {
        f->result = 1;
        pw_main_loop_quit(f->loop);
        return;
    }
    const struct spa_pod_prop *prop = spa_pod_find_prop(format, NULL, FOCUS_APPID);
    if (prop) {
        const struct spa_pod *value = &prop->value;
        fprintf(stderr, "{\"fixture\":\"selection-type\",\"type\":%u,\"choice\":%u,\"choice_values\":%u}\n",
                SPA_POD_TYPE(value), spa_pod_is_choice(value) ? SPA_POD_CHOICE_TYPE(value) : 0,
                spa_pod_is_choice(value) ? (unsigned)SPA_POD_CHOICE_N_VALUES(value) : 0);
        if (spa_pod_is_choice(value) && SPA_POD_CHOICE_VALUE_TYPE(value) == SPA_TYPE_Long) {
            const int64_t *choices = SPA_POD_CHOICE_VALUES(value);
            for (unsigned i = 0; i < SPA_POD_CHOICE_N_VALUES(value) && i < 8; ++i)
                fprintf(stderr, "{\"fixture\":\"choice-value\",\"value\":%" PRId64 "}\n", choices[i]);
        }
        if (spa_pod_is_choice(value))
            value = SPA_POD_CHOICE_CHILD(value);
        if (spa_pod_get_long(value, &appid) < 0)
            return;
    }
    /* An old compositor does not understand a custom key even if a graph's
     * format intersection happens to retain it from the consumer. Deliberately
     * ignore it in this mode, then emit the blue whole-compositor marker.
     */
    f->appid = !strcmp(f->mode, "missing") || !strcmp(f->mode, "mixed-dma") ? 0 : appid;
    fprintf(stderr, "{\"fixture\":\"negotiated\",\"appid\":%" PRId64
                    ",\"effective_appid\":%" PRId64 "}\n", appid, f->appid);
    fflush(stderr);
    spa_pod_builder_init(&b, storage, sizeof(storage));
    params[0] = spa_pod_builder_add_object(&b,
        SPA_TYPE_OBJECT_ParamBuffers, SPA_PARAM_Buffers,
        SPA_PARAM_BUFFERS_buffers, SPA_POD_CHOICE_RANGE_Int(4, 2, 8),
        SPA_PARAM_BUFFERS_blocks, SPA_POD_Int(1),
        SPA_PARAM_BUFFERS_size, SPA_POD_Int(FRAME_BYTES),
        SPA_PARAM_BUFFERS_stride, SPA_POD_Int(WIDTH * 4));
    params[1] = spa_pod_builder_add_object(&b,
        SPA_TYPE_OBJECT_ParamMeta, SPA_PARAM_Meta,
        SPA_PARAM_META_type, SPA_POD_Id(SPA_META_Header),
        SPA_PARAM_META_size, SPA_POD_Int(sizeof(struct spa_meta_header)));
    pw_stream_update_params(f->stream, params, 2);
    f->negotiated = true;
}

static const struct pw_stream_events events = {
    PW_VERSION_STREAM_EVENTS,
    .state_changed = state_changed,
    .param_changed = format_changed,
    .process = process,
};

static void quit(void *opaque, int signo)
{
    struct fixture *f = opaque;
    (void)signo;
    pw_main_loop_quit(f->loop);
}

int main(int argc, char **argv)
{
    struct fixture f = {0};
    uint8_t storage[1024];
    struct spa_pod_builder b = SPA_POD_BUILDER_INIT(storage, sizeof(storage));
    struct spa_pod_frame object;
    const struct spa_pod *formats[2];
    unsigned n_formats = 1;
    if (argc != 3) {
        fprintf(stderr, "usage: capture-fixture NODE good|missing|wrong|zero|corrupt|empty|mixed-dma|short|stale\n");
        return 2;
    }
    f.mode = argv[2];
    if (strcmp(f.mode, "good") && strcmp(f.mode, "missing") &&
        strcmp(f.mode, "wrong") && strcmp(f.mode, "zero") &&
        strcmp(f.mode, "corrupt") && strcmp(f.mode, "empty") && strcmp(f.mode, "mixed-dma") && strcmp(f.mode, "short") && strcmp(f.mode, "stale"))
        return 2;
    pw_init(NULL, NULL);
    f.loop = pw_main_loop_new(NULL);
    if (!f.loop)
        return 1;
    f.context = pw_context_new(pw_main_loop_get_loop(f.loop), NULL, 0);
    f.core = f.context ? pw_context_connect(f.context, NULL, 0) : NULL;
    if (!f.core) {
        fprintf(stderr, "fixture PipeWire connection failed\n");
        f.result = 1;
        goto done;
    }
    f.stream = pw_stream_new(f.core, "OBSGod protocol fixture",
        pw_properties_new(PW_KEY_NODE_NAME, argv[1],
            PW_KEY_MEDIA_CLASS, "Video/Source",
            PW_KEY_NODE_SUPPORTS_REQUEST, "1", NULL));
    if (!f.stream) {
        f.result = 1;
        goto done;
    }
    f.timer = pw_loop_add_timer(pw_main_loop_get_loop(f.loop), timer_tick, &f);
    pw_loop_add_signal(pw_main_loop_get_loop(f.loop), SIGINT, quit, &f);
    pw_loop_add_signal(pw_main_loop_get_loop(f.loop), SIGTERM, quit, &f);
    pw_stream_add_listener(f.stream, &f.listener, &events, &f);
    spa_pod_builder_push_object(&b, &object, SPA_TYPE_OBJECT_Format, SPA_PARAM_EnumFormat);
    spa_pod_builder_add(&b,
        SPA_FORMAT_mediaType, SPA_POD_Id(SPA_MEDIA_TYPE_video),
        SPA_FORMAT_mediaSubtype, SPA_POD_Id(SPA_MEDIA_SUBTYPE_raw),
        SPA_FORMAT_VIDEO_format, SPA_POD_Id(SPA_VIDEO_FORMAT_BGRx),
        SPA_FORMAT_VIDEO_size, SPA_POD_Rectangle(&SPA_RECTANGLE(WIDTH, HEIGHT)),
        SPA_FORMAT_VIDEO_framerate, SPA_POD_Fraction(&SPA_FRACTION(30, 1)),
        REQUESTED_SIZE, SPA_POD_CHOICE_RANGE_Rectangle(
            &SPA_RECTANGLE(0, 0), &SPA_RECTANGLE(0, 0),
            &SPA_RECTANGLE(UINT32_MAX, UINT32_MAX)), 0);
    if (!strcmp(f.mode, "wrong")) {
        spa_pod_builder_add(&b, FOCUS_APPID, SPA_POD_Long((int64_t)4243), 0);
    } else if (!strcmp(f.mode, "zero")) {
        spa_pod_builder_add(&b, FOCUS_APPID, SPA_POD_Long((int64_t)0), 0);
    } else if (strcmp(f.mode, "missing") && strcmp(f.mode, "mixed-dma")) {
        spa_pod_builder_add(&b, FOCUS_APPID,
            SPA_POD_CHOICE_RANGE_Long((int64_t)0, (int64_t)0, (int64_t)UINT32_MAX), 0);
    }
    formats[0] = spa_pod_builder_pop(&b, &object);
    if (!strcmp(f.mode, "mixed-dma")) {
        /* Only the DMA format supports the app selector. The non-modifier CPU
         * format deliberately does not. A per-node-any-format capability check
         * would be insufficient and could capture its blue compositor feed.
         */
        spa_pod_builder_push_object(&b, &object, SPA_TYPE_OBJECT_Format, SPA_PARAM_EnumFormat);
        spa_pod_builder_add(&b,
            SPA_FORMAT_mediaType, SPA_POD_Id(SPA_MEDIA_TYPE_video),
            SPA_FORMAT_mediaSubtype, SPA_POD_Id(SPA_MEDIA_SUBTYPE_raw),
            SPA_FORMAT_VIDEO_format, SPA_POD_Id(SPA_VIDEO_FORMAT_BGRx),
            SPA_FORMAT_VIDEO_size, SPA_POD_Rectangle(&SPA_RECTANGLE(WIDTH, HEIGHT)),
            SPA_FORMAT_VIDEO_framerate, SPA_POD_Fraction(&SPA_FRACTION(30, 1)),
            SPA_FORMAT_VIDEO_modifier, SPA_POD_Long((int64_t)0),
            REQUESTED_SIZE, SPA_POD_CHOICE_RANGE_Rectangle(
                &SPA_RECTANGLE(0, 0), &SPA_RECTANGLE(0, 0), &SPA_RECTANGLE(UINT32_MAX, UINT32_MAX)),
            FOCUS_APPID, SPA_POD_CHOICE_RANGE_Long((int64_t)0, (int64_t)0, (int64_t)UINT32_MAX), 0);
        formats[1] = spa_pod_builder_pop(&b, &object);
        n_formats = 2;
    }
    int result = pw_stream_connect(f.stream, PW_DIRECTION_OUTPUT, PW_ID_ANY,
        PW_STREAM_FLAG_DRIVER | PW_STREAM_FLAG_MAP_BUFFERS, formats, n_formats);
    if (result < 0) {
        fprintf(stderr, "fixture connect failed\n");
        f.result = 1;
        goto done;
    }
    pw_main_loop_run(f.loop);
done:
    if (f.stream)
        pw_stream_destroy(f.stream);
    if (f.context)
        pw_context_destroy(f.context);
    pw_main_loop_destroy(f.loop);
    pw_deinit();
    return f.result;
}
