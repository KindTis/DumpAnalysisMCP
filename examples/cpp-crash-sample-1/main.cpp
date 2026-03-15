#include <chrono>
#include <iostream>
#include <thread>

namespace
{
void TriggerAccessViolation()
{
    volatile int* ptr = nullptr;
    *ptr = 42;
}
} // namespace

int main()
{
    std::cout << "[cpp_crash_sample] process started." << std::endl;
    std::cout << "[cpp_crash_sample] crashing in 2 seconds..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(2));

    TriggerAccessViolation();
    return 0;
}

