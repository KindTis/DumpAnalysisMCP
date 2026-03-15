#pragma once

#include "Core/Math/Vector3.h"

class Character;

class CombatSystem
{
public:
    static void UpdateCombat(const Character* target);

private:
    static Vector3 ComputeShotOrigin(const Character* target);
};
