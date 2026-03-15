#pragma once

#include <atomic>
#include <memory>
#include <thread>

class Character;
class AIController;

class GameWorld
{
public:
    GameWorld();
    ~GameWorld();

    void StartAIThread();
    void StopAIThread();
    void UnloadStreamingLevel();

private:
    std::unique_ptr<Character> enemy_;
    std::unique_ptr<AIController> aiController_;
    std::thread aiThread_;
    std::atomic<bool> running_{ false };
};
