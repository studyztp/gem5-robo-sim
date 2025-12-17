#include "syscall_wrapper.h"

#include <sys/types.h>
#include <stdint.h>
#include <sys/stat.h>
#include <errno.h>

/* ================= ARM AArch32 (Thumb) Semihosting opcodes ================= */
enum {
  SYS_OPEN      = 0x01,
  SYS_CLOSE     = 0x02,
  SYS_WRITEC    = 0x03,
  SYS_WRITE0    = 0x04,
  SYS_WRITE     = 0x05,
  SYS_READ      = 0x06,
  SYS_READC     = 0x07,
  SYS_ISERROR   = 0x08,
  SYS_ISTTY     = 0x09,
  SYS_SEEK      = 0x0A,
  SYS_FLEN      = 0x0C,
  SYS_ERRNO     = 0x13,
  SYS_EXIT      = 0x18,   /* legacy */
  SYS_EXIT_EXT  = 0x20    /* preferred */
};

/* Semihosting OPEN modes (not POSIX) */
#define SH_OPEN_R   0
#define SH_OPEN_B   1
#define SH_OPEN_W   4
#define SH_OPEN_A   8

/* ================= Core semihosting trap (Cortex-M uses svc 0xAB) ================= */
static inline int sh_call(int reason, void *arg)
{
  /* Ensure the argument passed to r1 is a 32-bit guest address. On the
   * build host the C pointer type may be 64-bit; casting to uint32_t
   * (via uintptr_t) truncates to the guest-sized address. Gem5 expects
   * a 32-bit guest pointer in r1 for AArch32 semihosting; passing a
   * 64-bit value can lead to invalid memory accesses in the simulator.
   */
  uint32_t a = (uint32_t)(uintptr_t)arg;
  int ret;
  asm volatile (
      "mov r0, %1\n"
      "mov r1, %2\n"
      "svc #0xAB\n"
      "mov %0, r0\n"
      : "=r" (ret)
      : "r" (reason), "r" (a)
      : "r0", "r1", "memory"
  );
  return ret;
}

static inline int sh_errno(void)
{
  return sh_call(SYS_ERRNO, NULL);
}

/* Map POSIX open flags to semihosting mode */
static int map_open_mode(int flags)
{
  int m = SH_OPEN_R;
  if (flags & O_APPEND) {
    m = SH_OPEN_A;
  } else if ((flags & O_WRONLY) || (flags & O_RDWR) || (flags & O_TRUNC) || (flags & O_CREAT)) {
    m = SH_OPEN_W;
  }
  return m | SH_OPEN_B; /* binary */
}

/* ================= Canonical API (your call sites) ================= */

int open(const char *path, int flags, int mode)
{
  (void)mode; /* semihosting ignores permissions */
  size_t n = 0; while (path[n]) ++n;
  struct { const char *name; int mode; size_t len; } args = { path, map_open_mode(flags), n };
  int ret = sh_call(SYS_OPEN, &args);
  if (ret < 0) errno = sh_errno();
  return ret; /* >=0 host fd, <0 error */
}

int close(int fd)
{
  /* SYS_CLOSE expects the handle value in r1 (not a pointer). Pass the
   * integer handle as a 32-bit guest value by casting through uintptr_t.
   */
  int ret = sh_call(SYS_CLOSE, (void *)(uintptr_t)fd);
  if (ret < 0) { errno = sh_errno(); return -1; }
  return 0;
}

ssize_t write(int fd, const void *buf, size_t count)
{
  /* Prefer simple semihosting ops for stdout/stderr to avoid file-handle
   * bookkeeping in the host which has triggered crashes in some runs.
   * Use SYS_WRITEC for single-byte writes (fast and simple) by pointing
   * r1 at each byte in the guest buffer. For other fds, fall back to
   * SYS_WRITE using the parameter block.
   */
  if (fd == 1 || fd == 2) {
    const unsigned char *p = (const unsigned char *)buf;
    for (size_t i = 0; i < count; ++i) {
      /* SYS_WRITEC expects r1 to point at the character to write. */
      int r = sh_call(SYS_WRITEC, (void *)(p + i));
      if (r < 0) { errno = sh_errno(); return -1; }
    }
    return (ssize_t)count;
  }

  /* Non-stdout/stderr: use the regular write param block */
  struct { int fd; const void *buf; size_t len; } args = { fd, buf, count };
  int not_written = sh_call(SYS_WRITE, &args);
  if (not_written < 0) { errno = sh_errno(); return -1; }
  return (ssize_t)(count - (size_t)not_written);
}

ssize_t read(int fd, void *buf, size_t count)
{
  /* Semihosting returns #bytes NOT read */
  struct { int fd; void *buf; size_t len; } args = { fd, buf, count };
  int not_read = sh_call(SYS_READ, &args);
  if (not_read < 0) { errno = sh_errno(); return -1; }
  return (ssize_t)(count - (size_t)not_read);
}

int isatty(int fd)
{
  /* SYS_ISTTY expects the handle value in r1. Pass the integer directly. */
  int r = sh_call(SYS_ISTTY, (void *)(uintptr_t)fd);
  if (r < 0) { errno = sh_errno(); return 0; }
  return r != 0;
}

int flen(int fd)
{
  /* SYS_FLEN expects the handle value in r1. Pass the integer directly. */
  int r = sh_call(SYS_FLEN, (void *)(uintptr_t)fd);
  if (r < 0) errno = sh_errno();
  return r;
}

int lseek_set(int fd, int pos)
{
  struct { int fd; int pos; } args = { fd, pos };
  int r = sh_call(SYS_SEEK, &args);
  if (r < 0) { errno = sh_errno(); return -1; }
  return 0;
}

void exit(int status)
{
  /* ADP_Stopped_ApplicationExit = 0x20026 */
  struct { int reason; int value; } args = { 0x20026, status };
  sh_call(SYS_EXIT_EXT, &args);
  /* Fallback if EXT not handled */
  sh_call(SYS_EXIT, &status);
  for(;;) { /* halt */ }
}

/* ================= Newlib hooks (so printf/scanf work) ================= */
/* Non-reentrant */
int     _open(const char *path, int flags, int mode)          { return open(path, flags, mode); }
int     _close(int fd)                                        { return close(fd); }
ssize_t _write(int fd, const void *buf, size_t count)         { return write(fd, buf, count); }
ssize_t _read(int fd, void *buf, size_t count)                { return read(fd, buf, count); }
void    _exit(int status)                                     { exit(status); for(;;){} }

/* Minimal lseek: only SEEK_SET is implemented here */
int _lseek(int fd, int pos, int whence)
{
  if (whence == SEEK_SET) return lseek_set(fd, pos);
  errno = 29; /* ESPIPE-ish */
  return -1;
}

/* Minimal fstat: classify as char device unless we can get a length */
/* If S_IFCHR isn't defined for some minimal toolchains, provide a fallback
 * value. POSIX commonly defines S_IFCHR as 0020000 (octal). This fallback
 * is only used to avoid compile errors on tiny toolchains used for embedded
 * development.
 */
#ifndef S_IFCHR
#define S_IFCHR 0020000
#endif

int _fstat(int fd, struct stat *st)
{
  /* Return a minimal, non-error fstat without invoking semihosting
   * queries. This avoids extra semihosting traffic and possible host
   * side heap corruption during flen handling.
   */
  (void)fd;
  if (!st) return -1;
  st->st_mode = S_IFCHR;
  st->st_size = 0;
  return 0;
}

int _isatty(int fd)
{
  return isatty(fd);
}

/* Reentrant (_r) wrappers ignore the reent* and forward */
struct _reent;
int     _open_r(struct _reent *r, const char *p, int f, int m)  { (void)r; return _open(p,f,m); }
int     _close_r(struct _reent *r, int fd)                       { (void)r; return _close(fd); }
int     _isatty_r(struct _reent *r, int fd)                      { (void)r; return _isatty(fd); }
int     _lseek_r(struct _reent *r, int fd, int pos, int whence)  { (void)r; return _lseek(fd,pos,whence); }
int     _fstat_r(struct _reent *r, int fd, struct stat *st)      { (void)r; return _fstat(fd,st); }
ssize_t _write_r(struct _reent *r, int fd, const void *b, size_t n){ (void)r; return _write(fd,b,n); }
ssize_t _read_r(struct _reent *r, int fd, void *b, size_t n)     { (void)r; return _read(fd,b,n); }

/* ================= Optional heap (uncomment if you use malloc) ================= */
/*
#include <stddef.h>
void* _sbrk(ptrdiff_t inc)
{
  extern char _end;       // Provided by your linker script
  static char *brk = &_end;
  char *prev = brk;
  brk += inc;
  return prev;
}
*/
