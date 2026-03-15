#include "NavigationSystem.h"

#include "Game/Actors/Character.h"

Vector3 NavigationSystem::BuildAimingSolution(const Character* target)
{
    return target->GetHeadSocketPosition();
}
