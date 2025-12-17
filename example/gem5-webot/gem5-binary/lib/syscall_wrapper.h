#pragma once

#include <stddef.h>     // size_t
#include <sys/types.h>  // ssize_t

#ifdef __cplusplus
extern "C" {
#endif

/* Canonical POSIX-ish prototypes */
int     open(const char *path, int flags, int mode);
int     close(int fd);
ssize_t read(int fd, void *buf, size_t count);
ssize_t write(int fd, const void *buf, size_t count);
void    exit(int status);

/* Optional helpers */
int     isatty(int fd);
int     lseek_set(int fd, int pos); /* SEEK_SET only, minimal */
int     flen(int fd);

#ifdef __cplusplus
}
#endif

/* If you aren't including the usual headers, provide minimal flag/seek defs */
#ifndef O_RDONLY
#define O_RDONLY 0
#endif
#ifndef O_WRONLY
#define O_WRONLY 1
#endif
#ifndef O_RDWR
#define O_RDWR   2
#endif
#ifndef O_CREAT
#define O_CREAT  0100
#endif
#ifndef O_TRUNC
#define O_TRUNC  01000
#endif
#ifndef O_APPEND
#define O_APPEND 02000
#endif

#ifndef SEEK_SET
#define SEEK_SET 0
#endif
#ifndef SEEK_CUR
#define SEEK_CUR 1
#endif
#ifndef SEEK_END
#define SEEK_END 2
#endif
