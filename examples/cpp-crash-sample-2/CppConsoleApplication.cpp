// CppConsoleApplication.cpp : 크래시 덤프 샘플
// 목적: 여러 클래스 계층과 깊은 콜스택을 가진 크래시 상황을 재현합니다.
//       null 포인터 역참조로 인한 ACCESS VIOLATION 크래시가 발생합니다.

#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <stdexcept>

// -----------------------------------------------------------------------
// 데이터 모델 클래스
// -----------------------------------------------------------------------

struct PlayerStats
{
    int  level    = 1;
    int  hp       = 100;
    int  maxHp    = 100;
    int  attack   = 10;
    std::string name;
};

class Item
{
public:
    explicit Item(const std::string& name, int power)
        : m_name(name), m_power(power) {}

    const std::string& GetName()  const { return m_name; }
    int                GetPower() const { return m_power; }

private:
    std::string m_name;
    int         m_power;
};

class Inventory
{
public:
    void AddItem(std::shared_ptr<Item> item)
    {
        m_items.push_back(item);
    }

    // 의도적으로 범위 체크 없이 접근 → 크래시 원인 중 하나
    std::shared_ptr<Item> GetItem(size_t index) const
    {
        return m_items[index];   // out-of-range 가능
    }

    size_t Count() const { return m_items.size(); }

private:
    std::vector<std::shared_ptr<Item>> m_items;
};

// -----------------------------------------------------------------------
// 캐릭터 클래스 계층
// -----------------------------------------------------------------------

class Character
{
public:
    explicit Character(const std::string& name)
    {
        m_stats.name = name;
    }

    virtual ~Character() = default;

    virtual void PrintInfo() const
    {
        std::cout << "[Character] " << m_stats.name
                  << "  Lv." << m_stats.level
                  << "  HP " << m_stats.hp << "/" << m_stats.maxHp << "\n";
    }

    void EquipItem(std::shared_ptr<Item> item)
    {
        m_inventory.AddItem(item);
        std::cout << m_stats.name << " equipped: " << item->GetName() << "\n";
    }

    // 장착된 아이템 중 첫 번째를 사용
    virtual void UseFirstItem();

    PlayerStats& GetStats() { return m_stats; }

protected:
    PlayerStats m_stats;
    Inventory   m_inventory;
};

class Warrior : public Character
{
public:
    explicit Warrior(const std::string& name) : Character(name)
    {
        m_stats.hp    = 200;
        m_stats.maxHp = 200;
        m_stats.attack = 20;
    }

    void PrintInfo() const override
    {
        std::cout << "[Warrior] ";
        Character::PrintInfo();
    }

    void Charge()
    {
        std::cout << m_stats.name << " charges!\n";
        UseFirstItem();   // 콜스택 깊이 추가
    }
};

class Mage : public Character
{
public:
    explicit Mage(const std::string& name) : Character(name)
    {
        m_stats.hp    = 80;
        m_stats.maxHp = 80;
        m_stats.attack = 50;
    }

    void PrintInfo() const override
    {
        std::cout << "[Mage] ";
        Character::PrintInfo();
    }

    void CastSpell()
    {
        std::cout << m_stats.name << " casts a spell!\n";
        UseFirstItem();   // 콜스택 깊이 추가
    }
};

// -----------------------------------------------------------------------
// Character::UseFirstItem 구현
// -----------------------------------------------------------------------

void Character::UseFirstItem()
{
    // 인벤토리가 비어 있을 때도 GetItem(0) 을 호출 → out-of-range → 크래시
    std::shared_ptr<Item> item = m_inventory.GetItem(0);

    // item 이 nullptr 인 경우도 처리하지 않음 → null 역참조 가능
    int power = item->GetPower();
    std::cout << "Used item power: " << power << "\n";
}

// -----------------------------------------------------------------------
// 배틀 시스템 클래스 (깊은 콜스택을 만들기 위한 래퍼 레이어)
// -----------------------------------------------------------------------

class BattleManager
{
public:
    void StartBattle(Warrior& warrior, Mage& mage)
    {
        std::cout << "\n=== Battle Start ===\n";
        warrior.PrintInfo();
        mage.PrintInfo();

        ExecutePlayerTurn(warrior);
    }

private:
    void ExecutePlayerTurn(Warrior& warrior)
    {
        std::cout << "\n[BattleManager] Player turn begins.\n";
        ApplyBattleEffect(warrior);
    }

    void ApplyBattleEffect(Warrior& warrior)
    {
        std::cout << "[BattleManager] Applying battle effect...\n";
        TriggerChargeAbility(warrior);
    }

    void TriggerChargeAbility(Warrior& warrior)
    {
        std::cout << "[BattleManager] Triggering charge ability...\n";
        warrior.Charge();          // → Warrior::Charge → Character::UseFirstItem → CRASH
    }
};

// -----------------------------------------------------------------------
// GameSession: 최상위 게임 세션 관리
// -----------------------------------------------------------------------

class GameSession
{
public:
    void Initialize()
    {
        std::cout << "Initializing game session...\n";
        m_warrior = std::make_unique<Warrior>("Arthur");
        m_mage    = std::make_unique<Mage>("Merlin");

        // Mage 에게만 아이템을 줌 → Warrior 인벤토리는 비어 있음
        m_mage->EquipItem(std::make_shared<Item>("Magic Staff", 80));
    }

    void Run()
    {
        m_warrior->PrintInfo();
        m_mage->PrintInfo();

        BattleManager battle;
        battle.StartBattle(*m_warrior, *m_mage);
    }

private:
    std::unique_ptr<Warrior> m_warrior;
    std::unique_ptr<Mage>    m_mage;
};

// -----------------------------------------------------------------------
// 크래시 덤프 생성 헬퍼 (MiniDumpWriteDump 사용)
// -----------------------------------------------------------------------

#include <windows.h>
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")

static std::wstring g_dumpPath;

LONG WINAPI MyCrashHandler(EXCEPTION_POINTERS* exceptionInfo)
{
    std::wcout << L"\n[CRASH] Unhandled exception! Writing dump to: " << g_dumpPath << L"\n";

    HANDLE hFile = CreateFileW(
        g_dumpPath.c_str(),
        GENERIC_WRITE, 0, nullptr,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);

    if (hFile != INVALID_HANDLE_VALUE)
    {
        MINIDUMP_EXCEPTION_INFORMATION mei{};
        mei.ThreadId          = GetCurrentThreadId();
        mei.ExceptionPointers = exceptionInfo;
        mei.ClientPointers    = FALSE;

        MINIDUMP_TYPE dumpType = static_cast<MINIDUMP_TYPE>(
            MiniDumpWithDataSegs          |
            MiniDumpWithFullMemoryInfo    |
            MiniDumpWithHandleData        |
            MiniDumpWithThreadInfo        |
            MiniDumpWithUnloadedModules);

        BOOL ok = MiniDumpWriteDump(
            GetCurrentProcess(),
            GetCurrentProcessId(),
            hFile,
            dumpType,
            &mei,
            nullptr,
            nullptr);

        CloseHandle(hFile);

        if (ok)
            std::wcout << L"[CRASH] Dump written successfully.\n";
        else
            std::wcout << L"[CRASH] MiniDumpWriteDump failed: " << GetLastError() << L"\n";
    }
    else
    {
        std::wcout << L"[CRASH] Failed to create dump file: " << GetLastError() << L"\n";
    }

    return EXCEPTION_EXECUTE_HANDLER;
}

// -----------------------------------------------------------------------
// main
// -----------------------------------------------------------------------

int main()
{
    // 실행 파일과 같은 디렉터리에 덤프 파일 생성
    wchar_t exePath[MAX_PATH]{};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);

    g_dumpPath = exePath;
    size_t lastSlash = g_dumpPath.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos)
        g_dumpPath = g_dumpPath.substr(0, lastSlash + 1);
    g_dumpPath += L"CrashSample.dmp";

    SetUnhandledExceptionFilter(MyCrashHandler);

    std::cout << "=== Crash Dump Sample ===\n";
    std::cout << "Dump will be written to: ";
    std::wcout << g_dumpPath << L"\n\n";

    GameSession session;
    session.Initialize();   // Warrior 에게는 아이템을 주지 않음
    session.Run();           // → 깊은 콜스택 후 out-of-range 크래시

    std::cout << "This line is never reached.\n";
    return 0;
}
