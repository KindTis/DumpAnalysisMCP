#include "CombatSystem.h"

#include "Game/Systems/NavigationSystem.h"

void CombatSystem::UpdateCombat(const Character* target)
{
    const Vector3 aimPoint = ComputeShotOrigin(target);
    (void)aimPoint;
}

Vector3 CombatSystem::ComputeShotOrigin(const Character* target)
{
    return NavigationSystem::BuildAimingSolution(target);
}
