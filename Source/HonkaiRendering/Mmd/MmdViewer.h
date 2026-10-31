#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "Camera/CameraActor.h"
#include "MmdViewer.generated.h"

class UVrmAssetListObject;
class UMaterialInterface;
class SMmdViewer;

UCLASS()
class AMmdViewerController : public APlayerController
{
	GENERATED_BODY()
public:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	void ImportArchive();
	void LoadArchive(const FString& Path);
	void LoadModel(const FString& Path);
	void Orbit(FVector2D Delta, bool Pan, bool Dolly);
	void Zoom(float Delta);
	void FocusModel();
	void SetView(int32 View, bool Reverse);
	void ToggleProjection();
	FString Status = TEXT("导入 ZIP 压缩包以开始。");
	FString ModelName;
	FString ModelInfo;
	TArray<FString> ModelChoices;
	bool bBusy = false;
	bool bChoosing = false;
private:
	void UpdateCamera();
	UFUNCTION() void OnModelLoaded();
	TSharedPtr<SMmdViewer> Widget;
	FString ImportDirectory;
	FString PendingPath;
	UPROPERTY() UVrmAssetListObject* PendingAsset = nullptr;
	UPROPERTY() TObjectPtr<UVrmAssetListObject> LoadedAsset;
	UPROPERTY() TObjectPtr<UVrmAssetListObject> ImportTemplate;
	UPROPERTY() TObjectPtr<AActor> ModelActor;
	UPROPERTY() TObjectPtr<ACameraActor> ViewerCamera;
	UPROPERTY() TObjectPtr<UMaterialInterface> ToonMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> ToonTwoSidedMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> OutlineMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> FaceOutlineMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> TranslucentMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> TranslucentTwoSidedMaterial;
	FVector Target = FVector(0, 0, 80), ModelCenter = FVector(0, 0, 80);
	FVector KeyDirection = FVector::ForwardVector;
	FRotator Rotation = FRotator(-5, 180, 0);
	float Distance = 350, ModelRadius = 100;
	bool bOrthographic = false;
};

UCLASS()
class AMmdViewerGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	AMmdViewerGameMode();
};
