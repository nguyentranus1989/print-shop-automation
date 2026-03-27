/*
 * PrintFlow DTF v5.8.2 Unicode Injection DLL — single-shot, thread-based
 *
 * Target: DTF PrintExp v5.8.2.1.32 Unicode (64-bit)
 * Key differences from DTF v5.7.6:
 *   - EXE name is "PrintExp.exe" (not "PrintExp_X64.exe") but IS x64
 *   - Device object global at EXE+0x31B020
 *   - CTaskInfo vtable at TaskMgr.dll + 0x1F538
 *   - CTaskInfo size: 0x1E80 (vs 0xB08)
 *   - Manual AddFile: find existing task → vt[3](clone) → vt[9](load, WCHAR, 4 args)
 *   - Filenames are Unicode (wchar_t)
 *
 * Compile: tcc printflow-bridge-dtf82.c -shared -o printflow-bridge-dtf82.dll -luser32 -lkernel32
 */
#include <windows.h>
#include <stdio.h>

#ifndef CP_ACP
#define CP_ACP 0
#endif

#define RVA_DEVICE_OBJECT 0x31B020
#define TM_VT_RVA        0x1F538

static char g_dll_dir[MAX_PATH] = {0};

typedef void* (__fastcall *FN_Clone)(void*);
typedef long long (__fastcall *FN_LoadFile)(void*, const wchar_t*, long long, long long);

static void write_log(const char *msg) {
    char path[MAX_PATH]; FILE *f;
    wsprintfA(path, "%sinject_log.txt", g_dll_dir);
    f = fopen(path, "w");
    if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}

static void append_log(const char *msg) {
    char path[MAX_PATH]; FILE *f;
    wsprintfA(path, "%sinject_log.txt", g_dll_dir);
    f = fopen(path, "a");
    if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}

/* Find existing CTaskInfo by scanning device object for vtable match */
static void* find_existing_task(char *exe_base, void *tm_vtable) {
    void *pDev = *(void**)(exe_base + RVA_DEVICE_OBJECT);
    int off;
    if (!pDev) return NULL;

    for (off = 0; off < 0x600; off += 8) {
        void *candidate = *(void**)((char*)pDev + off);
        if (!candidate || (unsigned long long)candidate < 0x10000) continue;
        if (IsBadReadPtr(candidate, 8)) continue;
        void *vt = *(void**)candidate;
        if (vt == tm_vtable) return candidate;
    }
    return NULL;
}

static DWORD WINAPI inject_thread(LPVOID param) {
    char config_path[MAX_PATH];
    char prn_path[MAX_PATH] = {0};
    wchar_t wpath[MAX_PATH] = {0};
    char msg[512];
    FILE *f;
    int len;
    HMODULE hExe, hTM;
    char *base;
    void *tm_vtable;
    void *existing, *newTask;
    void **vt, **newVt;
    long long ret;
    HWND hwnd;

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

    /* Convert to wide string */
    MultiByteToWideChar(CP_ACP, 0, prn_path, -1, wpath, MAX_PATH);

    /* Get TaskMgr vtable address */
    hExe = GetModuleHandleA("PrintExp.exe");
    if (!hExe) hExe = GetModuleHandleA(NULL);
    base = (char*)hExe;

    hTM = GetModuleHandleA("TaskMgr.dll");
    if (!hTM) { write_log("ERR: TaskMgr.dll not loaded"); return 1; }
    tm_vtable = (char*)hTM + TM_VT_RVA;

    /* Step 1: Find existing CTaskInfo with valid reader */
    existing = find_existing_task(base, tm_vtable);
    if (!existing) { write_log("ERR: no existing CTaskInfo found"); return 1; }

    vt = *(void***)existing;

    /* Verify reader at +0xE50 */
    {
        void *reader = *(void**)((char*)existing + 0xE50);
        if (!reader) { write_log("ERR: no reader in existing task"); return 1; }
    }

    /* Step 2: Clone via vt[3] */
    newTask = ((FN_Clone)vt[3])(existing);
    if (!newTask) { write_log("ERR: vt[3] clone returned NULL"); return 1; }

    /* Step 3: Load file via vt[9] on new task (4 args: this, wpath, 0, 0) */
    newVt = *(void***)newTask;
    ret = ((FN_LoadFile)newVt[9])(newTask, wpath, 0, 0);
    if (!ret) {
        wsprintfA(msg, "ERR: vt[9] LoadFile failed for %s", prn_path);
        write_log(msg);
        return 1;
    }

    /* Step 4: Post 0x7F4 for UI refresh */
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
