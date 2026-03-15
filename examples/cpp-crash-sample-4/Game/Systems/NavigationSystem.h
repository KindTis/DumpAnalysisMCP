#pragma once

#include "Core/Math/Vector3.h"

class Character;

class NavigationSystem
{
public:
    static Vector3 BuildAimingSolution(const Character* target);
};
