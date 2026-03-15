#include "CrashDumpWriter.h"

#include <Windows.h>
#include <DbgHelp.h>

#include <iomanip>
#include <sstream>

#pragma comment(lib, "Dbghelp.lib")

void CrashDumpWriter::Install()
{
    SetUnhandledExceptionFilter(&CrashDumpWriter::HandleUnhandledException);
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
}

LONG WINAPI CrashDumpWriter::HandleUnhandledException(EXCEPTION_POINTERS* exceptionPointers)
{
    SYSTEMTIME st{};
    GetLocalTime(&st);

    std::ostringstream fileName;
    fileName << "CrashSample_"
             << st.wYear
             << std::setw(2) << std::setfill('0') << st.wMonth
             << std::setw(2) << std::setfill('0') << st.wDay
             << "_"
             << std::setw(2) << std::setfill('0') << st.wHour
             << std::setw(2) << std::setfill('0') << st.wMinute
             << std::setw(2) << std::setfill('0') << st.wSecond
             << ".dmp";

    HANDLE dumpFile = CreateFileA(
        fileName.str().c_str(),
        GENERIC_WRITE,
        0,
        nullptr,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);

    if (dumpFile != INVALID_HANDLE_VALUE)
    {
        MINIDUMP_EXCEPTION_INFORMATION dumpInfo{};
        dumpInfo.ThreadId = GetCurrentThreadId();
        dumpInfo.ExceptionPointers = exceptionPointers;
        dumpInfo.ClientPointers = FALSE;

        MiniDumpWriteDump(
            GetCurrentProcess(),
            GetCurrentProcessId(),
            dumpFile,
            static_cast<MINIDUMP_TYPE>(MiniDumpWithThreadInfo | MiniDumpWithIndirectlyReferencedMemory),
            &dumpInfo,
            nullptr,
            nullptr);

        CloseHandle(dumpFile);
    }

    return EXCEPTION_EXECUTE_HANDLER;
}
