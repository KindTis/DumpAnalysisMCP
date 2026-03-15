#pragma once

class Character;

class AIController
{
public:
    explicit AIController(Character* target);

    void Tick() const;

private:
    Character* target_ = nullptr;
};
