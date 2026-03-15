#include "SkeletalMeshComponent.h"

#include "Game/Components/TransformComponent.h"

SkeletalMeshComponent::SkeletalMeshComponent(TransformComponent* ownerTransform)
    : ownerTransform_(ownerTransform)
{
}

void SkeletalMeshComponent::InvalidateOwnerTransform()
{
    ownerTransform_ = nullptr;
}

Vector3 SkeletalMeshComponent::GetSocketWorldPosition(const std::string&) const
{
    const Vector3 socketOffset{ 5.0f, 0.0f, 170.0f };
    return ownerTransform_->GetWorldPosition() + socketOffset;
}
