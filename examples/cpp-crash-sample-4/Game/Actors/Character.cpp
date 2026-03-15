#include "Character.h"

#include "Game/Components/SkeletalMeshComponent.h"
#include "Game/Components/TransformComponent.h"

Character::Character(Vector3 startPosition)
    : transform_(std::make_unique<TransformComponent>(startPosition)),
      mesh_(std::make_unique<SkeletalMeshComponent>(transform_.get()))
{
}

Character::~Character() = default;

void Character::DestroyForLevelStreaming()
{
    transform_.reset();
    mesh_->InvalidateOwnerTransform();
}

Vector3 Character::GetHeadSocketPosition() const
{
    return mesh_->GetSocketWorldPosition("head");
}
