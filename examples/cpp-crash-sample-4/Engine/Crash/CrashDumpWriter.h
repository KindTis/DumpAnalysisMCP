#pragma once

#include <Windows.h>

class CrashDumpWriter
{
public:
    static void Install();

private:
    static LONG WINAPI HandleUnhandledException(EXCEPTION_POINTERS* exceptionPointers);
};
