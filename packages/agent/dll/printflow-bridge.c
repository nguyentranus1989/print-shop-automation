/*
 * PrintFlow Injection DLL — single-shot, thread-based (no window subclass)
 *
 * Safe for repeated injection: uses a thread instead of window subclassing.
 * Each injection: read config → AddFile → 0x7F4 refresh → write log → exit thread.
 *
 * Target: DTF PrintExp v5.7.6.5.103 (64-bit)
 * Compile: tcc printflow-bridge.c -shared -o printflow-bridge.dll -luser32 -lkernel32
 */
#include <windows.h>
#include <stdio.h>

#define RVA_APP_OBJECT 0x176B98

static char g_dll_dir[MAX_PATH] = {0};

typedef long long (__fastcall *VFN_0)(void*);
typedef int (__fastcall *VFN_2)(void*, const char*, void*);

static void write_log(const char *msg) {
    char path[MAX_PATH]; FILE *f;
    wsprintfA(path, "%sinject_log.txt", g_dll_dir);
    f = fopen(path, "w");
    if (f) { fprintf(f, "%s\n", msg); fclose(f); }
}

static DWORD WINAPI inject_thread(LPVOID param) {
    char config_path[MAX_PATH];
    char prn_path[MAX_PATH] = {0};
    char msg[512];
    FILE *f;
    int len;
    HMODULE hExe;
    char *base;
    void *pAppObj, *pTaskMgr;
    void **appVt, **tmVt;
    int result;
    HWND hwnd;

    /* Wait for PrintExp to settle after DLL load */
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

    /* Get CTaskManager */
    hExe = GetModuleHandleA("PrintExp_X64.exe");
    if (!hExe) hExe = GetModuleHandleA(NULL);
    base = (char*)hExe;

    pAppObj = *(void**)(base + RVA_APP_OBJECT);
    if (!pAppObj) { write_log("ERR: no app object"); return 1; }
    appVt = *(void***)pAppObj;
    pTaskMgr = ((VFN_0)appVt[22])(pAppObj);
    if (!pTaskMgr) { write_log("ERR: no task manager"); return 1; }
    tmVt = *(void***)pTaskMgr;

    /* AddFile via vtable[7] */
    result = ((VFN_2)tmVt[7])(pTaskMgr, prn_path, NULL);
    if (!result) {
        wsprintfA(msg, "ERR: AddFile failed for %s", prn_path);
        write_log(msg);
        return 1;
    }

    /* Copy to print vector */
    {
        void **fb = *(void***)((char*)pTaskMgr + 0x28);
        void **fe = *(void***)((char*)pTaskMgr + 0x30);
        void **pb = *(void***)((char*)pTaskMgr + 0x48);
        void **pe = *(void***)((char*)pTaskMgr + 0x50);
        void **pc = *(void***)((char*)pTaskMgr + 0x58);
        int fc = (fb && fe) ? (int)(fe - fb) : 0;
        int pcount = (pb && pe) ? (int)(pe - pb) : 0;
        void *newTask;

        if (fc <= 0) { write_log("ERR: empty file vec"); return 1; }
        newTask = fb[fc - 1];

        if (pe && pe < pc) {
            *pe = newTask;
            *(void***)((char*)pTaskMgr + 0x50) = pe + 1;
        } else {
            int nc = (pcount + 1) * 2; int i;
            typedef void* (*PFN_m)(size_t);
            HMODULE hCrt = GetModuleHandleA("msvcr100.dll");
            PFN_m m = hCrt ? (PFN_m)GetProcAddress(hCrt, "malloc") : NULL;
            void **nv = m ? (void**)m(8 * nc) : (void**)HeapAlloc(GetProcessHeap(), 8, 8 * nc);
            if (!nv) { write_log("ERR: malloc"); return 1; }
            for (i = 0; i < pcount; i++) nv[i] = pb[i];
            nv[pcount] = newTask;
            *(void***)((char*)pTaskMgr + 0x48) = nv;
            *(void***)((char*)pTaskMgr + 0x50) = nv + pcount + 1;
            *(void***)((char*)pTaskMgr + 0x58) = nv + nc;
        }
    }

    /* Post 0x7F4 UI refresh — must be on the UI thread, so use PostMessage */
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

        /* Launch injection in a separate thread — no window subclass needed */
        CreateThread(NULL, 0, inject_thread, NULL, 0, NULL);
    }
    return TRUE;
}
