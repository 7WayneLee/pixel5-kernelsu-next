// SPDX-License-Identifier: GPL-2.0-only
/* Disposable, offline SUSFS smoke tests. Never grants root or changes profiles. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MAGIC 0xDEADBEEF
#define VERSION 0x555e1
#define FEATURES 0x555e2
#define VARIANT 0x555e3
#define SENTINEL (-12345)

static long control(unsigned long cmd, void *data, int *status)
{
    return syscall(SYS_prctl, MAGIC, cmd, data, 0UL, status);
}

static void fatal(const char *message)
{
    perror(message);
    exit(2);
}

static void isolate_mounts(void)
{
    if (unshare(CLONE_NEWNS) || mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL))
        fatal("private mount namespace");
}

static int gate_test(void)
{
    char version[32] = {0};
    int status = SENTINEL;
    errno = 0;
    long result = control(VERSION, version, &status);
    int denied = result == -1 && (errno == EINVAL || errno == EPERM) &&
        status == SENTINEL && version[0] == 0;
    printf("{\"uid\":%u,\"control_denied\":%s,\"errno\":%d,\"status\":%d}\n",
           getuid(), denied ? "true" : "false", errno, status);
    return denied ? 0 : 1;
}

static int root_control(void)
{
    char version[32] = {0}, variant[32] = {0};
    unsigned long long features = 0;
    int status = SENTINEL;
    if (control(VERSION, version, &status) || status)
        return 2;
    if (control(VARIANT, variant, &status) || status)
        return 2;
    if (control(FEATURES, &features, &status) || status)
        return 2;
    int null_payload = control(VERSION, NULL, &status) == 0 && status == -EFAULT;
    errno = 0;
    int null_reply = control(VERSION, version, NULL) == -1 && errno == EFAULT;
    printf("{\"uid\":%u,\"version\":\"%s\",\"variant\":\"%s\","
           "\"features\":%llu,\"null_payload_rejected\":%s,\"null_reply_rejected\":%s}\n",
           getuid(), version, variant, features,
           null_payload ? "true" : "false", null_reply ? "true" : "false");
    return strcmp(version, "v1.5.5") || strcmp(variant, "NON-GKI") ||
        features != 8159 || !null_payload || !null_reply;
}

static void app_credentials(void)
{
    const char *context = "u:r:zygote:s0";
    isolate_mounts();
    int fd = open("/proc/self/attr/current", O_WRONLY);
    if (fd < 0 || write(fd, context, strlen(context)) != (ssize_t)strlen(context))
        fatal("zygote test domain");
    close(fd);
    /* An otherwise unused application UID; no real application's files read. */
    if (setgroups(0, NULL) || setresgid(19990, 19990, 19990) ||
        setresuid(19990, 19990, 19990))
        fatal("drop test credentials");
}

static int visibility(const char *fixture, int expect_hidden)
{
    char visible[512], hidden[512];
    struct stat a, b;
    snprintf(visible, sizeof(visible), "%s/visible", fixture);
    snprintf(hidden, sizeof(hidden), "%s/hidden", fixture);
    app_credentials();
    errno = 0;
    int see_visible = stat(visible, &a) == 0;
    int visible_error = errno;
    errno = 0;
    int see_hidden = stat(hidden, &b) == 0;
    int hidden_error = errno;
    printf("{\"uid\":%u,\"visible_exists\":%s,\"visible_errno\":%d,"
           "\"hidden_exists\":%s,\"hidden_errno\":%d,\"expected_hidden\":%s}\n",
           getuid(), see_visible ? "true" : "false", visible_error,
           see_hidden ? "true" : "false", hidden_error,
           expect_hidden ? "true" : "false");
    int denied = gate_test();
    return !see_visible || (expect_hidden ? (see_hidden || hidden_error != ENOENT) : !see_hidden) || denied;
}

static int mount_hidden(const char *fixture)
{
    char source[512], target[512], line[4096], item[1024];
    struct stat st;
    snprintf(source, sizeof(source), "%s/visible", fixture);
    snprintf(target, sizeof(target), "%s/mounted", fixture);
    snprintf(item, sizeof(item), " %s ", target);
    isolate_mounts();
    if (mount(source, target, NULL, MS_BIND, NULL))
        fatal("fixture bind mount");
    FILE *stream = fopen("/proc/self/mountinfo", "r");
    if (!stream)
        fatal("mountinfo");
    int found = 0;
    while (fgets(line, sizeof(line), stream))
        if (strstr(line, item))
            found = 1;
    fclose(stream);
    int accessible = stat(target, &st) == 0;
    int cleanup = umount2(target, MNT_DETACH) == 0;
    printf("{\"mount_entry_hidden\":%s,\"mounted_file_accessible\":%s,\"cleanup\":%s}\n",
           found ? "false" : "true", accessible ? "true" : "false",
           cleanup ? "true" : "false");
    return found || !accessible || !cleanup;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "denied"))
        return gate_test();
    if (getuid() != 0) {
        fprintf(stderr, "The controlled tests require an already granted root shell.\n");
        return 2;
    }
    if (argc == 2 && !strcmp(argv[1], "control"))
        return root_control();
    const char *prefix = "/data/local/tmp/pixel5-susfs-test-";
    int valid_fixture = argc == 3 && strlen(argv[2]) < 256 &&
        !strncmp(argv[2], prefix, strlen(prefix)) &&
        argv[2][strlen(prefix)] != 0;
    if (valid_fixture) {
        for (const char *p = argv[2] + strlen(prefix); *p; ++p)
            if ((*p < 'a' || *p > 'z') && (*p < '0' || *p > '9') && *p != '-')
                valid_fixture = 0;
    }
    if (valid_fixture) {
        if (!strcmp(argv[1], "app-visible"))
            return visibility(argv[2], 0);
        if (!strcmp(argv[1], "app-hidden"))
            return visibility(argv[2], 1);
        if (!strcmp(argv[1], "mount-hidden"))
            return mount_hidden(argv[2]);
    }
    fprintf(stderr, "Usage: probe control|denied; probe app-visible|app-hidden|mount-hidden /data/local/tmp/pixel5-susfs-test-ID\n");
    return 2;
}
