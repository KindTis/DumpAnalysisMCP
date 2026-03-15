#pragma once

#include <string>

#include "Core/Math/Vector3.h"

class TransformComponent;

class SkeletalMeshComponent
{
public:
    explicit SkeletalMeshComponent(TransformComponent* ownerTransform);

    void InvalidateOwnerTransform();
    Vector3 GetSocketWorldPosition(const std::string& socketName) const;

private:
    TransformComponent* ownerTransform_ = nullptr;
};
