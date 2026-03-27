/*
 * PrintFlow UV Injection DLL — single-shot, thread-based
 *
 * Target: UV PrintExp v5.7.9.4.5008 (64-bit)
 * Key differences from DTF:
 *   - Device object global at EXE+0x1D2F10 (not app object)
 *   - CTaskManager via dev_obj+0x70 (not vtable call)
 *   - AddFile = vtable[9] (not [7])
 *   - File vector at TM+0x08 (not +0x28)
 *   - AddFile PREPENDS at index 0 — diff-based detection required
 *   - Copy to +0x28 display vector ONLY (NOT +0x48 print vector — crashes)
 *
 * Compile: tcc printflow-bridge-uv.c -shared -o printflow-bridge-uv.dll -luser32 -lkernel32
 */
#include <windows.h>
#include <stdio.h>

#define RVA_DEVICE_OBJECT 0x1D2F10
#define TASKMGR_OFFSET    0x70

static char g_dll_dir[MAX_PATH] = {0};

typedef long long (__fastcall *FN_AddFile)(void*, const char*, void*);

static void write_log(const char *msg) {
    char path[MAX_PATH]; FILE *f;
    wsprintfA(path, "%sinject_log.txt", g_dll_dir);
    f = fopen(path, "w");
    if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}

static void write_log2(const char *fmt, const char *arg) {
    char buf[512]; char path[MAX_PATH]; FILE *f;
    wsprintfA(buf, fmt, arg);
    wsprintfA(path, "%sinject_log.txt", g_dll_dir);
    f = fopen(path, "a");
    if (f) { fprintf(f, "%s\n", buf); fclose(f); }
}

static DWORD WINAPI inject_thread(LPVOID param) {
    char config_path[MAX_PATH];
    char prn_path[MAX_PATH] = {0};
    char msg[512];
    FILE *f;
    int len, i;
    HMODULE hExe;
    char *base;
    void *pDevObj, *pTaskMgr;
    void **tmVt;
    long long ret;
    HWND hwnd;

    /* Snapshot variables for diff-based detection */
    void **fb_before, **fe_before;
    void **fb_after, **fe_after;
    int count_before, count_after;
    void *newTask = NULL;

    Sleep(300);

    /* Read config */
    wsprintfA(config_path, "%sinject_config.txt", g_dll_dir);
    f = fopen(config_path, "r");
    if (!f) { write_log("ERR: no config"); return 1; }
    if (fgets(prn_path, MAX_PATH, f)) {
        len = lstrlenA(prn_path);
        while (len > 0 && (prn_path[len-1] == 10 || prn_path[len-1] == 13))
            prn_path[--len] = 0;
    }
    fclose(f);
    if (!prn_path[0]) { write_log("ERR: empty config"); return 1; }

    /* Get CTaskManager via device object */
    hExe = GetModuleHandleA("PrintExp_X64.exe");
    if (!hExe) hExe = GetModuleHandleA(NULL);
    base = (char*)hExe;

    pDevObj = *(void**)(base + RVA_DEVICE_OBJECT);
    if (!pDevObj) { write_log("ERR: null device object"); return 1; }

    pTaskMgr = *(void**)((char*)pDevObj + TASKMGR_OFFSET);
    if (!pTaskMgr) { write_log("ERR: null task manager"); return 1; }
    tmVt = *(void***)pTaskMgr;

    /* Snapshot file vector BEFORE AddFile (at TM+0x08/0x10) */
    fb_before = *(void***)((char*)pTaskMgr + 0x08);
    fe_before = *(void***)((char*)pTaskMgr + 0x10);
    count_before = (fb_before && fe_before && fe_before > fb_before)
                   ? (int)(fe_before - fb_before) : 0;

    /* Call AddFile via vtable[9] */
    ret = ((FN_AddFile)tmVt[9])(pTaskMgr, prn_path, NULL);
    if (!ret) {
        wsprintfA(msg, "ERR: AddFile(vt[9]) failed for %s", prn_path);
        write_log(msg);
        return 1;
    }

    /* Snapshot file vector AFTER AddFile */
    fb_after = *(void***)((char*)pTaskMgr + 0x08);
    fe_after = *(void***)((char*)pTaskMgr + 0x10);
    count_after = (fb_after && fe_after && fe_after > fb_after)
                  ? (int)(fe_after - fb_after) : 0;

    /* Diff-based detection: AddFile PREPENDS at index 0 */
    if (count_after > count_before && count_after > 0) {
        /* New entry is at index 0 (prepended) */
        newTask = fb_after[0];
    } else if (count_after == count_before && count_after > 0) {
        /* Replaced existing — check index 0 */
        newTask = fb_after[0];
    }

    if (!newTask) {
        write_log("ERR: could not find new task after AddFile");
        return 1;
    }

    /* Copy new task to +0x28 display vector ONLY (NOT +0x48 — that crashes!) */
    {
        void **pb = *(void***)((char*)pTaskMgr + 0x28);
        void **pe = *(void***)((char*)pTaskMgr + 0x30);
        void **pc = *(void***)((char*)pTaskMgr + 0x38);
        int pcount = (pb && pe && pe >= pb) ? (int)(pe - pb) : 0;

        if (pe && pe < pc) {
            *pe = newTask;
            *(void***)((char*)pTaskMgr + 0x30) = pe + 1;
        } else {
            int nc = (pcount + 1) * 2;
            typedef void* (*PFN_m)(size_t);
            HMODULE hCrt = GetModuleHandleA("msvcr100.dll");
            PFN_m m = hCrt ? (PFN_m)GetProcAddress(hCrt, "malloc") : NULL;
            void **nv = m ? (void**)m(8 * nc)
                         : (void**)HeapAlloc(GetProcessHeap(), 8, 8 * nc);
            if (!nv) { write_log("ERR: malloc for display vec"); return 1; }
            for (i = 0; i < pcount; i++) nv[i] = pb[i];
            nv[pcount] = newTask;
            *(void***)((char*)pTaskMgr + 0x28) = nv;
            *(void***)((char*)pTaskMgr + 0x30) = nv + pcount + 1;
            *(void***)((char*)pTaskMgr + 0x38) = nv + nc;
        }
    }

    /* Post 0x7F4 UI refresh */
    hwnd = FindWindowA("#32770", "PrintExp");
    if (hwnd) {
        HWND child;
        PostMessageA(hwnd, 0x7F4, 1, 0);
        child = GetWindow(hwnd, 5);
        while (child) {
            char cls[32] = {0};
            GetClassNameA(child, cls, 32);
            if (cls[0] == '#') PostMessageA(child, 0x7F4, 1, 0);
            {
                HWND gc = GetWindow(child, 5);
                while (gc) {
                    GetClassNameA(gc, cls, 32);
                    if (cls[0] == '#') PostMessageA(gc, 0x7F4, 1, 0);
                    gc = GetWindow(gc, 2);
                }
            }
            child = GetWindow(child, 2);
        }
    }

    write_log("=== done ===");
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        char *p, *last;
        GetModuleFileNameA(hinstDLL, g_dll_dir, MAX_PATH);
        last = g_dll_dir;
        for (p = g_dll_dir; *p; p++)
            if (*p == 0x5C) last = p + 1;
        *last = 0;
        CreateThread(NULL, 0, inject_thread, NULL, 0, NULL);
    }
    return TRUE;
}
