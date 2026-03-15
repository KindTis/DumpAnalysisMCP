#include <chrono>
#include <iostream>
#include <thread>
#include "Engine/Crash/CrashDumpWriter.h"
#include "Game/World/GameWorld.h"

int main()
{
	CrashDumpWriter::Install();

	std::cout << "Crash sample started."
		<< "\nScenario: AI worker thread reads actor mesh data while level streaming unload invalidates transform."
		<< "\nExpected: Access violation on worker thread + CrashSample_*.dmp created in executable folder."
		<< std::endl;

	GameWorld world;
	world.StartAIThread();

	std::this_thread::sleep_for(std::chrono::milliseconds(300));
	world.UnloadStreamingLevel();

	std::this_thread::sleep_for(std::chrono::seconds(2));
	world.StopAIThread();

	return 0;
}