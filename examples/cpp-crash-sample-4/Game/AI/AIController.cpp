#include "AIController.h"

#include "Game/Systems/CombatSystem.h"

AIController::AIController(Character* target)
    : target_(target)
{
}

void AIController::Tick() const
{
    CombatSystem::UpdateCombat(target_);
}
