/*
 * PrintFlow Bridge DLL — Persistent resident DLL for PrintExp control
 *
 * Injected once into PrintExp_X64.exe, stays resident.
 * Creates named pipe server for JSON command/response IPC with Python agent.
 *
 * Commands:
 *   add_file      — AddFile via CTaskManager vtable[7] + 0x7F4 UI refresh
 *   get_status    — Read PrintState, CheckReady, ValidateParams, queue counts
 *   get_queue     — Return file/print vector counts
 *   print_start   — Call StartPrint (devVt[129]) [needs hardware]
 *   pause         — Call PausePrint (devVt[73]) [needs hardware]
 *   resume        — Call ResumePrint (devVt[72]) [needs hardware]
 *   cancel        — Call SendCommand (devVt[20]) with cancel [needs hardware]
 *   ping          — Health check, returns "pong"
 *
 * Target: DTF PrintExp v5.7.6.5.103 (64-bit)
 * Compile: tcc printflow-bridge.c -shared -o printflow-bridge.dll -luser32 -lkernel32
 */
#include <windows.h>
#include <stdio.h>

/* ---- PrintExp offsets (v5.7.6.5.103) ---- */
#define RVA_DEVICE_OBJ  0x176B98
#define RVA_EXT_BOARD   0x176BA8

/* Device vtable indices (offset / 8) */
#define VT_SEND_CMD      20   /* +0xA0  SendCommand */
#define VT_GET_TASKMGR   22   /* +0xB0  GetTaskManager */
#define VT_CHECK_READY   61   /* +0x1E8 CheckReady */
#define VT_RESUME_PRINT  72   /* +0x240 ResumePrint */
#define VT_PAUSE_PRINT   73   /* +0x248 PausePrint */
#define VT_GET_STATE    127   /* +0x3F8 GetPrintState */
#define VT_GET_SUBSTATE 128   /* +0x400 GetSubState */
#define VT_START_PRINT  129   /* +0x408 StartPrint */
#define VT_VALID_PARAMS 184   /* +0x5C0 ValidateParams */

/* CTaskManager vtable */
#define TM_VT_ADDFILE     7   /* +0x38 AddFile(this, path, NULL) */

/* Named pipe */
#define PIPE_NAME "\\\\.\\pipe\\PrintFlowBridge"
#define PIPE_BUFSIZE 4096

/* ---- Globals ---- */
static HMODULE g_hExe = NULL;
static char *g_exeBase = NULL;
static HANDLE g_pipeThread = NULL;
static volatile int g_running = 1;

/* ---- Simple JSON helpers (no library, just sprintf) ---- */

/* Find value for a key in a simple JSON string: {"key":"value"} */
static int json_get_string(const char *json, const char *key, char *out, int outsize) {
    char pattern[64];
    char *p;
    int i;
    wsprintfA(pattern, "\"%s\":", key);
    p = strstr(json, pattern);
    if (!p) return 0;
    p += lstrlenA(pattern);
    while (*p == ' ') p++;
    if (*p != '"') return 0;
    p++;
    for (i = 0; i < outsize - 1 && *p && *p != '"'; i++)
        out[i] = *p++;
    out[i] = 0;
    return 1;
}

/* ---- PrintExp access ---- */

static void* get_device(void) {
    if (!g_exeBase) return NULL;
    return *(void**)(g_exeBase + RVA_DEVICE_OBJ);
}

static void* get_ext_board(void) {
    if (!g_exeBase) return NULL;
    return *(void**)(g_exeBase + RVA_EXT_BOARD);
}

typedef long long (__fastcall *VFN0)(void*);
typedef int (__fastcall *VFN_I)(void*);
typedef int (__fastcall *VFN_2)(void*, const char*, void*);

static void* get_task_manager(void) {
    void *dev = get_device();
    void **vt;
    if (!dev) return NULL;
    vt = *(void***)dev;
    return ((VFN0)vt[VT_GET_TASKMGR])(dev);
}

/* ---- Command handlers ---- */

static int cmd_ping(char *response, int rsize) {
    wsprintfA(response, "{\"ok\":true,\"result\":\"pong\"}");
    return 1;
}

static int cmd_get_status(char *response, int rsize) {
    void *dev = get_device();
    void *eb = get_ext_board();
    void **devVt;
    int printState, subState, ready, validParams, isExternal;
    int fileCount, printCount;
    void *tm;

    if (!dev) {
        wsprintfA(response, "{\"ok\":false,\"error\":\"no device object\"}");
        return 0;
    }
    devVt = *(void***)dev;

    printState = ((VFN_I)devVt[VT_GET_STATE])(dev);
    subState = ((VFN_I)devVt[VT_GET_SUBSTATE])(dev);
    ready = ((VFN_I)devVt[VT_CHECK_READY])(dev);
    validParams = ((VFN_I)devVt[VT_VALID_PARAMS])(dev);

    isExternal = 0;
    if (eb && !IsBadReadPtr(eb, 8)) {
        void **ebVt = *(void***)eb;
        isExternal = ((VFN_I)ebVt[0x60/8])(eb);
    }

    /* Queue counts from CTaskManager */
    fileCount = -1; printCount = -1;
    tm = get_task_manager();
    if (tm) {
        void **fb = *(void***)((char*)tm + 0x28);
        void **fe = *(void***)((char*)tm + 0x30);
        void **pb = *(void***)((char*)tm + 0x48);
        void **pe = *(void***)((char*)tm + 0x50);
        fileCount = (fb && fe) ? (int)(fe - fb) : 0;
        printCount = (pb && pe) ? (int)(pe - pb) : 0;
    }

    wsprintfA(response,
        "{\"ok\":true,\"print_state\":%d,\"sub_state\":%d,"
        "\"ready\":%d,\"params_valid\":%d,\"is_external\":%d,"
        "\"file_count\":%d,\"print_count\":%d}",
        printState, subState, ready, validParams, isExternal,
        fileCount, printCount);
    return 1;
}

static int cmd_add_file(const char *path, char *response, int rsize) {
    void *tm = get_task_manager();
    void **tmVt;
    int result;
    HWND hwnd;

    if (!tm) {
        wsprintfA(response, "{\"ok\":false,\"error\":\"no task manager\"}");
        return 0;
    }
    tmVt = *(void***)tm;

    /* AddFile via vtable[7] */
    result = ((VFN_2)tmVt[TM_VT_ADDFILE])(tm, path, NULL);
    if (!result) {
        wsprintfA(response, "{\"ok\":false,\"error\":\"AddFile returned 0\"}");
        return 0;
    }

    /* Copy to print vector */
    {
        void **fb = *(void***)((char*)tm + 0x28);
        void **fe = *(void***)((char*)tm + 0x30);
        void **pb = *(void***)((char*)tm + 0x48);
        void **pe = *(void***)((char*)tm + 0x50);
        void **pc = *(void***)((char*)tm + 0x58);
        int fc = (fb && fe) ? (int)(fe - fb) : 0;
        int pcount = (pb && pe) ? (int)(pe - pb) : 0;
        void *newTask;

        if (fc <= 0) {
            wsprintfA(response, "{\"ok\":false,\"error\":\"empty file vector\"}");
            return 0;
        }
        newTask = fb[fc - 1];

        if (pe && pe < pc) {
            *pe = newTask;
            *(void***)((char*)tm + 0x50) = pe + 1;
        } else {
            int nc = (pcount + 1) * 2; int i;
            typedef void* (*PFN_m)(size_t);
            HMODULE hCrt = GetModuleHandleA("msvcr100.dll");
            PFN_m m = hCrt ? (PFN_m)GetProcAddress(hCrt, "malloc") : NULL;
            void **nv = m ? (void**)m(8 * nc) : (void**)HeapAlloc(GetProcessHeap(), 8, 8 * nc);
            if (!nv) {
                wsprintfA(response, "{\"ok\":false,\"error\":\"malloc failed\"}");
                return 0;
            }
            for (i = 0; i < pcount; i++) nv[i] = pb[i];
            nv[pcount] = newTask;
            *(void***)((char*)tm + 0x48) = nv;
            *(void***)((char*)tm + 0x50) = nv + pcount + 1;
            *(void***)((char*)tm + 0x58) = nv + nc;
        }
    }

    /* Post 0x7F4 UI refresh to main window + child dialogs */
    hwnd = FindWindowA("#32770", "PrintExp");
    if (hwnd) {
        HWND child;
        PostMessageA(hwnd, 0x7F4, 1, 0);
        child = GetWindow(hwnd, 5); /* GW_CHILD */
        while (child) {
            char cls[32] = {0};
            GetClassNameA(child, cls, 32);
            if (cls[0] == '#') PostMessageA(child, 0x7F4, 1, 0);
            /* Grandchildren */
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

    wsprintfA(response, "{\"ok\":true,\"added\":true}");
    return 1;
}

static int cmd_print_control(const char *action, char *response, int rsize) {
    void *dev = get_device();
    void **devVt;

    if (!dev) {
        wsprintfA(response, "{\"ok\":false,\"error\":\"no device\"}");
        return 0;
    }
    devVt = *(void***)dev;

    if (lstrcmpiA(action, "pause") == 0) {
        ((VFN0)devVt[VT_PAUSE_PRINT])(dev);
        wsprintfA(response, "{\"ok\":true,\"action\":\"pause\"}");
    }
    else if (lstrcmpiA(action, "resume") == 0) {
        ((VFN0)devVt[VT_RESUME_PRINT])(dev);
        wsprintfA(response, "{\"ok\":true,\"action\":\"resume\"}");
    }
    else {
        wsprintfA(response, "{\"ok\":false,\"error\":\"unknown action: %s\"}", action);
        return 0;
    }
    return 1;
}

/* ---- Named pipe server ---- */

static void handle_request(const char *request, char *response, int rsize) {
    char cmd[64] = {0};
    char path[MAX_PATH] = {0};
    char action[64] = {0};

    if (!json_get_string(request, "cmd", cmd, 64)) {
        wsprintfA(response, "{\"ok\":false,\"error\":\"missing cmd\"}");
        return;
    }

    if (lstrcmpiA(cmd, "ping") == 0) {
        cmd_ping(response, rsize);
    }
    else if (lstrcmpiA(cmd, "get_status") == 0) {
        cmd_get_status(response, rsize);
    }
    else if (lstrcmpiA(cmd, "add_file") == 0) {
        if (!json_get_string(request, "path", path, MAX_PATH)) {
            wsprintfA(response, "{\"ok\":false,\"error\":\"missing path\"}");
            return;
        }
        cmd_add_file(path, response, rsize);
    }
    else if (lstrcmpiA(cmd, "control") == 0) {
        if (!json_get_string(request, "action", action, 64)) {
            wsprintfA(response, "{\"ok\":false,\"error\":\"missing action\"}");
            return;
        }
        cmd_print_control(action, response, rsize);
    }
    else {
        wsprintfA(response, "{\"ok\":false,\"error\":\"unknown cmd: %s\"}", cmd);
    }
}

static DWORD WINAPI pipe_server_thread(LPVOID param) {
    while (g_running) {
        HANDLE hPipe;
        DWORD bytesRead, bytesWritten;
        char request[PIPE_BUFSIZE] = {0};
        char response[PIPE_BUFSIZE] = {0};
        BOOL connected;

        hPipe = CreateNamedPipeA(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,              /* max instances */
            PIPE_BUFSIZE,
            PIPE_BUFSIZE,
            1000,           /* timeout ms */
            NULL
        );

        if (hPipe == INVALID_HANDLE_VALUE) {
            Sleep(1000);
            continue;
        }

        connected = ConnectNamedPipe(hPipe, NULL) ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);
        if (!connected) {
            CloseHandle(hPipe);
            continue;
        }

        /* Read request */
        if (ReadFile(hPipe, request, PIPE_BUFSIZE - 1, &bytesRead, NULL) && bytesRead > 0) {
            request[bytesRead] = 0;
            handle_request(request, response, PIPE_BUFSIZE);

            /* Write response */
            WriteFile(hPipe, response, lstrlenA(response), &bytesWritten, NULL);
            FlushFileBuffers(hPipe);
        }

        DisconnectNamedPipe(hPipe);
        CloseHandle(hPipe);
    }
    return 0;
}

/* ---- DLL entry ---- */
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_hExe = GetModuleHandleA("PrintExp_X64.exe");
        if (!g_hExe) g_hExe = GetModuleHandleA(NULL);
        g_exeBase = (char*)g_hExe;
        g_running = 1;

        /* Start pipe server in background thread */
        g_pipeThread = CreateThread(NULL, 0, pipe_server_thread, NULL, 0, NULL);
    }
    else if (reason == DLL_PROCESS_DETACH) {
        g_running = 0;
        if (g_pipeThread) {
            /* Signal pipe to unblock by connecting to it */
            HANDLE h = CreateFileA(PIPE_NAME, GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
            if (h != INVALID_HANDLE_VALUE) {
                WriteFile(h, "{\"cmd\":\"shutdown\"}", 18, NULL, NULL);
                CloseHandle(h);
            }
            WaitForSingleObject(g_pipeThread, 3000);
            CloseHandle(g_pipeThread);
        }
    }
    return TRUE;
}
