#include "GameWorld.h"

#include <chrono>

#include "Game/AI/AIController.h"
#include "Game/Actors/Character.h"

GameWorld::GameWorld()
    : enemy_(std::make_unique<Character>(Vector3{ 100.0f, 20.0f, 0.0f })),
      aiController_(std::make_unique<AIController>(enemy_.get()))
{
}

GameWorld::~GameWorld()
{
    StopAIThread();
}

void GameWorld::StartAIThread()
{
    running_.store(true);
    aiThread_ = std::thread([this]()
    {
        while (running_.load())
        {
            aiController_->Tick();
            std::this_thread::sleep_for(std::chrono::milliseconds(16));
        }
    });
}

void GameWorld::StopAIThread()
{
    running_.store(false);
    if (aiThread_.joinable())
    {
        aiThread_.join();
    }
}

void GameWorld::UnloadStreamingLevel()
{
    enemy_->DestroyForLevelStreaming();
}
