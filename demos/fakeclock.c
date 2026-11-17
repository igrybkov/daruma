/*
 * A clock and a random seed that a test runner controls, for the Daruma
 * host build. Loaded into the program with DYLD_INSERT_LIBRARIES (macOS) or
 * LD_PRELOAD (Linux). It changes nothing unless DARUMA_CLOCK names a file.
 *
 * The file (see harness.py, Clock) holds three 64-bit values:
 *   [0] monotonic time in ns. Only the runner moves it.
 *   [1] the wall clock in seconds since the epoch at monotonic 0.
 *   [2] the seed for /dev/urandom reads.
 *
 * With the file set:
 *   - clock_gettime, gettimeofday and time() read the file's clock. So
 *     millis(), the scheduler and the wall clock all stop between steps;
 *   - a new time takes effect only when the program calls
 *     daruma_clock_latch(). The desktop component (daruma_desktop) calls it at
 *     the start of each turn of the main loop, so the clock never changes
 *     halfway through one;
 *   - settimeofday does nothing (the time component may call it);
 *   - select() and nanosleep() wait at most 2 ms of real time, so the main
 *     loop keeps turning while the clock stands still;
 *   - /dev/urandom gives a fixed stream from the seed, which seeds
 *     random_uint32().
 * The same steps then give the same frames, run after run.
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#ifndef __APPLE__
#include <dlfcn.h>
#endif

static volatile uint64_t *clock_map = NULL;
static int clock_tried = 0;
static uint64_t latched_ns = 0; /* The time the program sees. */

static volatile uint64_t *shared(void) {
  if (clock_tried)
    return clock_map;
  clock_tried = 1;
  const char *path = getenv("DARUMA_CLOCK");
  if (path == NULL || path[0] == '\0')
    return NULL;
  int fd = open(path, O_RDWR);
  if (fd < 0)
    return NULL;
  void *p = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  close(fd);
  if (p == MAP_FAILED)
    return NULL;
  clock_map = (volatile uint64_t *) p;
  latched_ns = clock_map[0];
  return clock_map;
}

/* Take the runner's latest time. Exported: the program finds it with dlsym. */
__attribute__((visibility("default"))) void daruma_clock_latch(void) {
  volatile uint64_t *m = shared();
  if (m != NULL)
    latched_ns = m[0];
}

static const long MAX_WAIT_NS = 2000000;  // 2 ms

/* ---- The originals ------------------------------------------------------ */

#ifdef __APPLE__
#define REAL(name) name
#else
static int (*real_clock_gettime)(clockid_t, struct timespec *);
static int (*real_gettimeofday)(struct timeval *, void *);
static int (*real_select)(int, fd_set *, fd_set *, fd_set *, struct timeval *);
static int (*real_nanosleep)(const struct timespec *, struct timespec *);
static FILE *(*real_fopen)(const char *, const char *);
static void resolve(void) {
  if (real_clock_gettime != NULL)
    return;
  real_clock_gettime = dlsym(RTLD_NEXT, "clock_gettime");
  real_gettimeofday = dlsym(RTLD_NEXT, "gettimeofday");
  real_select = dlsym(RTLD_NEXT, "select");
  real_nanosleep = dlsym(RTLD_NEXT, "nanosleep");
  real_fopen = dlsym(RTLD_NEXT, "fopen");
}
#endif

static int orig_clock_gettime(clockid_t c, struct timespec *ts) {
#ifdef __APPLE__
  return clock_gettime(c, ts);
#else
  resolve();
  return real_clock_gettime(c, ts);
#endif
}
static int orig_gettimeofday(struct timeval *tv, void *tz) {
#ifdef __APPLE__
  return gettimeofday(tv, tz);
#else
  resolve();
  return real_gettimeofday(tv, tz);
#endif
}
static int orig_select(int n, fd_set *r, fd_set *w, fd_set *e, struct timeval *tv) {
#ifdef __APPLE__
  return select(n, r, w, e, tv);
#else
  resolve();
  return real_select(n, r, w, e, tv);
#endif
}
static int orig_nanosleep(const struct timespec *req, struct timespec *rem) {
#ifdef __APPLE__
  return nanosleep(req, rem);
#else
  resolve();
  return real_nanosleep(req, rem);
#endif
}
static FILE *orig_fopen(const char *path, const char *mode) {
#ifdef __APPLE__
  return fopen(path, mode);
#else
  resolve();
  return real_fopen(path, mode);
#endif
}

/* ---- Replacements ------------------------------------------------------- */

static int fake_clock_gettime(clockid_t c, struct timespec *ts) {
  volatile uint64_t *m = shared();
  if (m == NULL || ts == NULL)
    return orig_clock_gettime(c, ts);
  uint64_t ns = latched_ns;
  if (c == CLOCK_REALTIME) {
    ts->tv_sec = (time_t) m[1] + (time_t) (ns / 1000000000ULL);
  } else {
    ts->tv_sec = (time_t) (ns / 1000000000ULL);
  }
  ts->tv_nsec = (long) (ns % 1000000000ULL);
  return 0;
}

static int fake_gettimeofday(struct timeval *tv, void *tz) {
  volatile uint64_t *m = shared();
  if (m == NULL)
    return orig_gettimeofday(tv, tz);
  if (tv != NULL) {
    uint64_t ns = latched_ns;
    tv->tv_sec = (time_t) m[1] + (time_t) (ns / 1000000000ULL);
    tv->tv_usec = (int) ((ns % 1000000000ULL) / 1000);
  }
  return 0;
}

static time_t fake_time(time_t *out) {
  volatile uint64_t *m = shared();
  time_t t;
  if (m == NULL) {
    struct timeval tv;
    orig_gettimeofday(&tv, NULL);
    t = tv.tv_sec;
  } else {
    t = (time_t) m[1] + (time_t) (latched_ns / 1000000000ULL);
  }
  if (out != NULL)
    *out = t;
  return t;
}

static int fake_settimeofday(const struct timeval *tv, const void *tz) {
  (void) tv;
  (void) tz;
  return 0;
}

static int fake_select(int n, fd_set *r, fd_set *w, fd_set *e, struct timeval *tv) {
  if (shared() != NULL && tv != NULL && (tv->tv_sec > 0 || tv->tv_usec > MAX_WAIT_NS / 1000)) {
    struct timeval capped = {0, MAX_WAIT_NS / 1000};
    return orig_select(n, r, w, e, &capped);
  }
  return orig_select(n, r, w, e, tv);
}

static int fake_nanosleep(const struct timespec *req, struct timespec *rem) {
  if (shared() != NULL && req != NULL && (req->tv_sec > 0 || req->tv_nsec > MAX_WAIT_NS)) {
    struct timespec capped = {0, MAX_WAIT_NS};
    return orig_nanosleep(&capped, NULL);
  }
  return orig_nanosleep(req, rem);
}

/* /dev/urandom from the seed: splitmix64. */
static uint64_t seed_state;
static uint64_t next_random(void) {
  uint64_t z = (seed_state += 0x9E3779B97F4A7C15ULL);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}

#ifdef __APPLE__
static int seeded_read(void *cookie, char *buf, int len) {
#else
static ssize_t seeded_read(void *cookie, char *buf, size_t len) {
#endif
  (void) cookie;
  for (int i = 0; i < (int) len; i += 8) {
    uint64_t v = next_random();
    int n = (int) len - i < 8 ? (int) len - i : 8;
    memcpy(buf + i, &v, n);
  }
  return len;
}

static FILE *fake_fopen(const char *path, const char *mode) {
  volatile uint64_t *m = shared();
  if (m != NULL && path != NULL && strcmp(path, "/dev/urandom") == 0) {
    seed_state = m[2];
#ifdef __APPLE__
    return funopen(NULL, seeded_read, NULL, NULL, NULL);
#else
    cookie_io_functions_t io = {seeded_read, NULL, NULL, NULL};
    return fopencookie(NULL, mode, io);
#endif
  }
  return orig_fopen(path, mode);
}

/* ---- Hooking ------------------------------------------------------------ */

#ifdef __APPLE__
#define INTERPOSE(replacement, original) \
  __attribute__((used)) static struct { \
    const void *replacement; \
    const void *original; \
  } interpose_##original __attribute__((section("__DATA,__interpose"))) = { \
      (const void *) (unsigned long) &replacement, (const void *) (unsigned long) &original}

INTERPOSE(fake_clock_gettime, clock_gettime);
INTERPOSE(fake_gettimeofday, gettimeofday);
INTERPOSE(fake_time, time);
INTERPOSE(fake_settimeofday, settimeofday);
INTERPOSE(fake_select, select);
INTERPOSE(fake_nanosleep, nanosleep);
INTERPOSE(fake_fopen, fopen);
#else
int clock_gettime(clockid_t c, struct timespec *ts) { return fake_clock_gettime(c, ts); }
int gettimeofday(struct timeval *tv, void *tz) { return fake_gettimeofday(tv, tz); }
time_t time(time_t *t) { return fake_time(t); }
int settimeofday(const struct timeval *tv, const struct timezone *tz) { return fake_settimeofday(tv, tz); }
int select(int n, fd_set *r, fd_set *w, fd_set *e, struct timeval *tv) { return fake_select(n, r, w, e, tv); }
int nanosleep(const struct timespec *req, struct timespec *rem) { return fake_nanosleep(req, rem); }
FILE *fopen(const char *path, const char *mode) { return fake_fopen(path, mode); }
#endif
