#include "TransformComponent.h"

TransformComponent::TransformComponent(Vector3 worldPosition)
    : worldPosition_(worldPosition)
{
}

Vector3 TransformComponent::GetWorldPosition() const
{
    return worldPosition_;
}
