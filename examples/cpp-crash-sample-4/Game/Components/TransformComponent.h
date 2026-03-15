#pragma once

#include "Core/Math/Vector3.h"

class TransformComponent
{
public:
    explicit TransformComponent(Vector3 worldPosition);

    Vector3 GetWorldPosition() const;

private:
    Vector3 worldPosition_;
};
