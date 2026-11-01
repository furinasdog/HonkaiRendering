#pragma once

#include "CoreMinimal.h"
#include "HAL/PlatformProcess.h"

struct FMmdMaterialCandidate
{
    int32 Index = INDEX_NONE;
    FString Name;
};

struct FMmdEnhancementRequest
{
    FString ModelPath;
    FString ResourceRoot;
    int32 MaterialIndex = INDEX_NONE;
    FString ParametersJson = TEXT("{\"resolution\":512}");
    bool bForce = false;
};

struct FMmdModelState
{
    bool bEnhanced = false;
    int32 MaterialIndex = INDEX_NONE;
    FString ParametersJson = TEXT("{\"resolution\":512}");
    FString ProfileDirectory;
};

enum class EMmdEnhancementState : uint8 { Idle, Running, NeedsMaterial, Succeeded, Failed, Cancelled };

struct FMmdEnhancementStatus
{
    EMmdEnhancementState State = EMmdEnhancementState::Idle;
    FString Stage;
    FString Message;
    float Progress = 0;
    bool bCacheHit = false;
    FString ResultDirectory;
    TArray<FMmdMaterialCandidate> Candidates;
};

// Owned by the viewer. All methods are called on the game thread; work runs in an isolated child process.
class FMmdEnhancement
{
public:
    ~FMmdEnhancement();
    static FString UserDataDir();
    static FString ImportsDir();
    static FMmdModelState ReadModelState(const FString& ModelPath);
    static bool SaveModelState(const FString& ModelPath, const FMmdModelState& State, FString& Error);

    bool Start(const FMmdEnhancementRequest& Request);
    void Tick();
    void Cancel();
    bool IsRunning() const { return Status.State == EMmdEnhancementState::Running; }
    const FMmdEnhancementStatus& GetStatus() const { return Status; }
    static bool Export(const FString& ModelPath, const FString& ProfileDirectory, const FString& Destination, FString& Error);
    static bool ClearCache(FString& Error);

private:
    void ReadStatus();
    FProcHandle Process;
    FString JobDirectory;
    FMmdEnhancementStatus Status;
    double NextPoll = 0;
};
