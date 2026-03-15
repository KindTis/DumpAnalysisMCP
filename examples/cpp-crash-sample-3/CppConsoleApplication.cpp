// CppConsoleApplication.cpp : 멀티스레드 크래시 덤프 샘플
// 목적: 메인 스레드는 정상 루프를 실행하고,
//       서브 스레드에서 잘못된 메모리 접근으로 크래시가 발생하는 상황을 재현합니다.

#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <thread>
#include <atomic>
#include <chrono>
#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")

// ==========================================================================
// 공유 데이터 버퍼 (스레드 간 공유)
// ==========================================================================

struct SharedBuffer
{
    std::vector<int> data;
    std::atomic<bool> ready{ false };

    void Populate()
    {
        data = { 10, 20, 30, 40, 50 };
        ready.store(true);
    }
};

// ==========================================================================
// 게임 오브젝트 계층
// ==========================================================================

class GameObject
{
public:
    explicit GameObject(const std::string& tag) : m_tag(tag) {}
    virtual ~GameObject() = default;

    virtual void Update() = 0;
    const std::string& Tag() const { return m_tag; }

protected:
    std::string m_tag;
};

class Sensor : public GameObject
{
public:
    explicit Sensor(const std::string& tag) : GameObject(tag) {}

    void Update() override
    {
        std::cout << "  [Sensor:" << m_tag << "] tick\n";
    }
};

class DataProcessor : public GameObject
{
public:
    // 외부 버퍼 포인터를 받아 처리 — 수명 관리는 호출자 책임
    DataProcessor(const std::string& tag, SharedBuffer* buffer)
        : GameObject(tag), m_buffer(buffer) {}

    void Update() override
    {
        ProcessBuffer();
    }

private:
    void ProcessBuffer()
    {
        FetchData();
    }

    void FetchData()
    {
        ParseData();
    }

    void ParseData()
    {
        ConsumeData();
    }

    // 버퍼가 해제된 뒤에도 호출 → 댕글링 포인터 역참조 → ACCESS VIOLATION
    void ConsumeData()
    {
        // m_buffer 는 이미 해제된 메모리를 가리킴 (댕글링 포인터)
        // Debug 빌드에서 해제된 메모리는 0xDD로 채워져 data() 내부 포인터도 무효
        // → 그 주소에 쓰기 시도 = 보장된 ACCESS VIOLATION (SEH 예외)
        int* badPtr = m_buffer->data.data();  // 해제된 벡터의 내부 포인터 (쓰레기값)
        *badPtr = 0xDEAD;                     // 쓰레기 주소에 쓰기 → AV
        std::cout << "  [DataProcessor:" << m_tag << "] value=" << *badPtr << "\n";
    }

    SharedBuffer* m_buffer;  // non-owning raw pointer (위험)
};

// ==========================================================================
// 워커 스레드 파이프라인
// ==========================================================================

class WorkerPipeline
{
public:
    WorkerPipeline(const std::string& name, SharedBuffer* buffer)
        : m_name(name)
    {
        // Sensor 두 개 + DataProcessor 하나로 파이프라인 구성
        m_objects.emplace_back(std::make_unique<Sensor>("MotionSensor"));
        m_objects.emplace_back(std::make_unique<Sensor>("TempSensor"));
        m_objects.emplace_back(std::make_unique<DataProcessor>("NetProcessor", buffer));
    }

    // 매 사이클마다 모든 오브젝트 Update 호출
    void RunCycle(int cycle)
    {
        std::cout << "[" << m_name << "] cycle " << cycle << " start\n";
        DispatchUpdates();
        std::cout << "[" << m_name << "] cycle " << cycle << " end\n";
    }

private:
    void DispatchUpdates()
    {
        for (auto& obj : m_objects)
            TickObject(*obj);
    }

    void TickObject(GameObject& obj)
    {
        obj.Update();   // DataProcessor::Update → … → ConsumeData → CRASH
    }

    std::string m_name;
    std::vector<std::unique_ptr<GameObject>> m_objects;
};

// ==========================================================================
// 크래시 덤프 핸들러
// ==========================================================================

static std::wstring           g_dumpPath;
static std::atomic<bool>      g_dumpWritten{ false };

// 덤프 쓰기 공통 함수 (스레드 안전, 한 번만 실행)
static void WriteDump(EXCEPTION_POINTERS* exceptionInfo)
{
    bool expected = false;
    if (!g_dumpWritten.compare_exchange_strong(expected, true))
        return;  // 이미 다른 스레드가 덤프를 쓰는 중

    wprintf(L"\n[CRASH] Exception 0x%08X on thread %lu. Writing dump: %s\n",
            exceptionInfo->ExceptionRecord->ExceptionCode,
            GetCurrentThreadId(),
            g_dumpPath.c_str());

    HANDLE hFile = CreateFileW(g_dumpPath.c_str(), GENERIC_WRITE, 0, nullptr,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile == INVALID_HANDLE_VALUE)
    {
        wprintf(L"[CRASH] CreateFile failed: %lu\n", GetLastError());
        return;
    }

    MINIDUMP_EXCEPTION_INFORMATION mei{};
    mei.ThreadId          = GetCurrentThreadId();
    mei.ExceptionPointers = exceptionInfo;
    mei.ClientPointers    = FALSE;

    MINIDUMP_TYPE dumpType = static_cast<MINIDUMP_TYPE>(
        MiniDumpWithDataSegs        |
        MiniDumpWithFullMemoryInfo  |
        MiniDumpWithHandleData      |
        MiniDumpWithThreadInfo      |
        MiniDumpWithUnloadedModules);

    BOOL ok = MiniDumpWriteDump(GetCurrentProcess(), GetCurrentProcessId(),
                                hFile, dumpType, &mei, nullptr, nullptr);
    CloseHandle(hFile);
    wprintf(ok ? L"[CRASH] Dump written successfully.\n"
               : L"[CRASH] MiniDumpWriteDump failed: %lu\n",
            ok ? 0UL : GetLastError());
}

// VEH (Vectored Exception Handler): SetUnhandledExceptionFilter 및 CRT 핸들러보다
// 먼저 실행되므로 CRT 다이얼로그가 뜨기 전에 덤프를 확보할 수 있음
static LONG WINAPI VectoredCrashHandler(EXCEPTION_POINTERS* exceptionInfo)
{
    DWORD code = exceptionInfo->ExceptionRecord->ExceptionCode;

    // 실제 크래시성 예외만 처리 (C++ 예외 코드 0xE06D7363 는 제외)
    if (code == EXCEPTION_ACCESS_VIOLATION    ||
        code == EXCEPTION_ILLEGAL_INSTRUCTION ||
        code == EXCEPTION_STACK_OVERFLOW      ||
        code == EXCEPTION_INT_DIVIDE_BY_ZERO)
    {
        WriteDump(exceptionInfo);
        // 덤프 확보 후 팝업 없이 즉시 종료
        TerminateProcess(GetCurrentProcess(), code);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

// ==========================================================================
// 서브 스레드 엔트리 — 버퍼 해제 후 접근하여 크래시 유발
// ==========================================================================

// WorkerPipeline(소멸자 있음)과 __try를 같은 함수에 둘 수 없으므로 분리
static void RunPipelineLoop(SharedBuffer* buffer)
{
    WorkerPipeline pipeline("SubPipeline", buffer);

    // 사이클 반복 중 버퍼가 이미 delete 된 상태이므로 크래시 발생
    for (int cycle = 1; ; ++cycle)
    {
        pipeline.RunCycle(cycle);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

static void SubThreadEntry(SharedBuffer* buffer)
{
    // 잠시 대기해 메인 스레드가 먼저 버퍼를 해제하도록 함
    std::cout << "[SubThread] started, waiting for buffer to be freed...\n";
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    // __try/__except 로 SEH 예외를 직접 처리 (VEH 백업)
    // ※ __try 와 소멸자 있는 객체는 같은 함수에 불가 → RunPipelineLoop 로 분리
    __try
    {
        RunPipelineLoop(buffer);
    }
    __except(WriteDump(GetExceptionInformation()),
             TerminateProcess(GetCurrentProcess(), GetExceptionCode()),
             EXCEPTION_EXECUTE_HANDLER)
    {
        // 덤프 쓰기 및 종료는 필터 식에서 이미 처리됨
    }
}

// ==========================================================================
// main
// ==========================================================================

int main()
{
    // 덤프 경로 설정
    wchar_t exePath[MAX_PATH]{};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    g_dumpPath = exePath;
    size_t lastSlash = g_dumpPath.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos)
        g_dumpPath = g_dumpPath.substr(0, lastSlash + 1);
    g_dumpPath += L"CrashSample.dmp";

    // ---------------------------------------------------------------
    // 팝업 다이얼로그 억제
    // ---------------------------------------------------------------
    // Windows 오류 보고(WER) 팝업 비활성화
    SetErrorMode(SEM_NOGPFAULTERRORBOX | SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX);

#ifdef _DEBUG
    // CRT 어설션/오류 다이얼로그를 stderr 출력으로 전환
    _CrtSetReportMode(_CRT_ASSERT, _CRTDBG_MODE_FILE);
    _CrtSetReportFile(_CRT_ASSERT, _CRTDBG_FILE_STDERR);
    _CrtSetReportMode(_CRT_ERROR,  _CRTDBG_MODE_FILE);
    _CrtSetReportFile(_CRT_ERROR,  _CRTDBG_FILE_STDERR);
    _CrtSetReportMode(_CRT_WARN,   _CRTDBG_MODE_FILE);
    _CrtSetReportFile(_CRT_WARN,   _CRTDBG_FILE_STDERR);
#endif

    // VEH: CRT 핸들러보다 먼저 실행됨 (1 = 체인 맨 앞에 등록)
    AddVectoredExceptionHandler(1, VectoredCrashHandler);

    std::wcout << L"=== Multi-Thread Crash Dump Sample ===\n";
    std::wcout << L"Dump path: " << g_dumpPath << L"\n\n";

    // ---------------------------------------------------------------
    // 공유 버퍼 생성 및 초기화
    // ---------------------------------------------------------------
    auto* buffer = new SharedBuffer();
    buffer->Populate();
    std::cout << "[MainThread] SharedBuffer populated.\n";

    // ---------------------------------------------------------------
    // 서브 스레드 시작 (버퍼 raw 포인터 전달)
    // ---------------------------------------------------------------
    std::thread subThread(SubThreadEntry, buffer);

    // ---------------------------------------------------------------
    // 메인 스레드: 정상 루프 실행
    // ---------------------------------------------------------------
    std::cout << "[MainThread] Starting normal loop...\n";
    for (int i = 1; i <= 5; ++i)
    {
        std::cout << "[MainThread] loop tick " << i << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // ---------------------------------------------------------------
    // 메인 스레드: 버퍼 해제 → 서브 스레드의 포인터가 댕글링됨
    // ---------------------------------------------------------------
    std::cout << "[MainThread] Deleting SharedBuffer (sub-thread still holds pointer!)...\n";
    delete buffer;
    buffer = nullptr;

    // 메인 스레드는 계속 정상 동작
    std::cout << "[MainThread] Buffer deleted. Continuing normal loop...\n";
    for (int i = 6; ; ++i)
    {
        std::cout << "[MainThread] loop tick " << i << " (sub-thread may crash any moment)\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    subThread.join();   // 실제로는 도달하지 않음
    return 0;
}

