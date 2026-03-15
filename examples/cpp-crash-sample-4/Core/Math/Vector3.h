#pragma once

struct Vector3
{
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    Vector3 operator+(const Vector3& rhs) const
    {
        return { x + rhs.x, y + rhs.y, z + rhs.z };
    }
};
