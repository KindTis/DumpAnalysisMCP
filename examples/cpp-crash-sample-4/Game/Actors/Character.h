#pragma once

#include <memory>

#include "Core/Math/Vector3.h"
#include "Game/Components/SkeletalMeshComponent.h"
#include "Game/Components/TransformComponent.h"

class Character
{
public:
    explicit Character(Vector3 startPosition);
    ~Character();

    void DestroyForLevelStreaming();
    Vector3 GetHeadSocketPosition() const;

private:
    std::unique_ptr<TransformComponent> transform_;
    std::unique_ptr<SkeletalMeshComponent> mesh_;
};
