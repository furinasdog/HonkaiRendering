#include "MmdViewer.h"
#include "Async/Async.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Texture.h"
#include "Engine/Texture2D.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/Material.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "TimerManager.h"
#include "UnrealClient.h"
#include "Misc/Base64.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "LoaderBPFunctionLibrary.h"
#include "VrmAssetListObject.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SWindow.h"
#include "Input/DragAndDrop.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/CoreStyle.h"
#include "UObject/ConstructorHelpers.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
THIRD_PARTY_INCLUDES_START
#include <shobjidl.h>
THIRD_PARTY_INCLUDES_END
#endif

namespace
{
	FLinearColor Panel(0.045f, 0.057f, 0.075f, 1), Text(0.82f, 0.86f, 0.91f, 1), Muted(0.43f, 0.51f, 0.61f, 1);
	TSharedRef<STextBlock> Label(const FString& Value, int32 Size = 12, FLinearColor Color = Text)
	{
		return SNew(STextBlock).Text(FText::FromString(Value)).Font(FCoreStyle::GetDefaultFontStyle("Regular", Size)).ColorAndOpacity(Color);
	}
}

class SMmdMenu : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SMmdMenu) {} SLATE_END_ARGS()
    TFunction<void()> Escape;
    void Construct(const FArguments&, TFunction<void()> InEscape, TSharedRef<SWidget> Content)
    {
        Escape = MoveTemp(InEscape);
        ChildSlot[Content];
    }
    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnKeyDown(const FGeometry&, const FKeyEvent& Event) override
    {
        if (Event.GetKey() == EKeys::Escape) { Escape(); return FReply::Handled(); }
        return FReply::Unhandled();
    }
};

class SMmdViewer : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SMmdViewer) {} SLATE_END_ARGS()
    TWeakObjectPtr<AMmdViewerController> Controller;
    TSharedPtr<SWindow> MenuWindow;
    bool bDragging = false;

    void Construct(const FArguments&, AMmdViewerController* InController)
    {
        Controller = InController;
        ChildSlot
        [
            SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor::Transparent)
        ];
    }
    void CloseWindow()
    {
        if (MenuWindow) MenuWindow->RequestDestroyWindow();
        MenuWindow.Reset();
        if (FSlateApplication::IsInitialized()) FSlateApplication::Get().SetKeyboardFocus(SharedThis(this));
    }
    TSharedRef<SButton> Button(const FString& Caption, TFunction<void()> Action)
    {
        return SNew(SButton).ContentPadding(FMargin(16, 12))
            .IsEnabled_Lambda([this] { return Controller.IsValid() && !Controller->bBusy; })
            .OnClicked_Lambda([Action] { Action(); return FReply::Handled(); })[Label(Caption, 13)];
    }
    void OpenPage(FName Page = "Main")
    {
        TSharedRef<SVerticalBox> Body = SNew(SVerticalBox);
        auto Add = [&](TSharedRef<SWidget> Widget) { Body->AddSlot().AutoHeight().Padding(0, 0, 0, 10)[Widget]; };
        FString Title = TEXT("菜单");
        if (Page == "Main")
        {
            Add(Button(TEXT("模型"), [this] { OpenPage("Model"); }));
            Add(Button(TEXT("视角"), [this] { OpenPage("View"); }));
            Add(Button(TEXT("返回角色"), [this] { CloseWindow(); }));
        }
        else if (Page == "Model")
        {
            Title = TEXT("模型");
            Add(Button(TEXT("导入 ZIP 压缩包"), [this] { Controller->ImportArchive(); }));
            Add(Label(TEXT("也可以直接将 ZIP 拖入角色窗口。"), 12, Muted));
            if (!Controller->ModelName.IsEmpty())
            {
                Add(Label(Controller->ModelName, 14));
                Add(Label(Controller->ModelInfo, 12, Muted));
            }
            Add(Button(TEXT("返回"), [this] { OpenPage(); }));
        }
        else if (Page == "View")
        {
            Title = TEXT("视角");
            Add(Button(TEXT("聚焦模型"), [this] { Controller->FocusModel(); CloseWindow(); }));
            Add(Button(TEXT("正交 / 透视"), [this] { Controller->ToggleProjection(); CloseWindow(); }));
            Add(Label(TEXT("中键拖动：旋转\nShift + 中键：平移\nCtrl + 中键或滚轮：缩放\n\n小键盘 1 / 3 / 7：正 / 右 / 顶视图\nCtrl + 小键盘：反向视图\n小键盘 5：正交 / 透视\n小键盘 . 或 Home：聚焦"), 12, Muted));
            Add(Button(TEXT("返回"), [this] { OpenPage(); }));
        }
        else if (Page == "Choose")
        {
            Title = TEXT("选择 PMX 文件");
            Add(Label(TEXT("选择压缩包中的角色模型。"), 12, Muted));
            TSharedRef<SVerticalBox> Choices = SNew(SVerticalBox);
            for (const FString& Path : Controller->ModelChoices)
                Choices->AddSlot().AutoHeight().Padding(0, 0, 0, 8)[Button(Path, [this, Path] { Controller->LoadModel(Path); })];
            Add(SNew(SBox).HeightOverride(280)[SNew(SScrollBox) + SScrollBox::Slot()[Choices]]);
            Add(Button(TEXT("取消"), [this] { Controller->bChoosing = false; CloseWindow(); }));
        }
        else
        {
            Title = Controller->bBusy ? TEXT("正在加载") : TEXT("导入结果");
            Add(SNew(STextBlock).Text_Lambda([this] { return FText::FromString(Controller->Status); }).AutoWrapText(true).ColorAndOpacity(Text));
            if (!Controller->bBusy) Add(Button(TEXT("关闭"), [this] { CloseWindow(); }));
        }
        TWeakPtr<SMmdViewer> Weak = SharedThis(this);
        TSharedRef<SMmdMenu> Content = SNew(SMmdMenu, [Weak]
        {
            if (auto Self = Weak.Pin()) { Self->Controller->bChoosing = false; Self->CloseWindow(); }
        }, SNew(SBox).WidthOverride(410)
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(24)[Body]]);
        if (!MenuWindow)
        {
            MenuWindow = SNew(SWindow).Title(FText::FromString(Title)).SizingRule(ESizingRule::Autosized)
                .SupportsMinimize(false).SupportsMaximize(false).AutoCenter(EAutoCenter::PreferredWorkArea);
            MenuWindow->SetOnWindowClosed(FOnWindowClosed::CreateLambda([Weak](const TSharedRef<SWindow>& Closed)
            {
                if (auto Self = Weak.Pin(); Self && Self->MenuWindow == Closed)
                {
                    Self->MenuWindow.Reset(); Self->Controller->bChoosing = false;
                    FSlateApplication::Get().SetKeyboardFocus(Self);
                }
            }));
            MenuWindow->SetContent(Content);
            auto Parent = FSlateApplication::Get().FindWidgetWindow(SharedThis(this));
            if (Parent) FSlateApplication::Get().AddWindowAsNativeChild(MenuWindow.ToSharedRef(), Parent.ToSharedRef());
            else FSlateApplication::Get().AddWindow(MenuWindow.ToSharedRef());
        }
        else { MenuWindow->SetTitle(FText::FromString(Title)); MenuWindow->SetContent(Content); }
        FSlateApplication::Get().SetKeyboardFocus(Content);
    }
    void RefreshChoices() { OpenPage("Choose"); }
    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnDragOver(const FGeometry&, const FDragDropEvent& Event) override
    {
        auto Files = Event.GetOperationAs<FExternalDragOperation>();
        return Files && Files->HasFiles() ? FReply::Handled() : FReply::Unhandled();
    }
    virtual FReply OnDrop(const FGeometry&, const FDragDropEvent& Event) override
    {
        auto Files = Event.GetOperationAs<FExternalDragOperation>();
        if (!Files || !Files->HasFiles()) return FReply::Unhandled();
        if (!Controller->bBusy)
        {
            if (Files->GetFiles().Num() == 1 && FPaths::GetExtension(Files->GetFiles()[0]).Equals(TEXT("zip"), ESearchCase::IgnoreCase))
                Controller->LoadArchive(Files->GetFiles()[0]);
            else { Controller->Status = TEXT("请一次拖入一个包含 PMX 和贴图的 ZIP 压缩包。"); OpenPage("Status"); }
        }
        return FReply::Handled();
    }
    virtual FReply OnMouseButtonDown(const FGeometry&, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton() == EKeys::MiddleMouseButton && !MenuWindow)
        {
            bDragging = true;
            return FReply::Handled().CaptureMouse(SharedThis(this)).UseHighPrecisionMouseMovement(SharedThis(this)).SetUserFocus(SharedThis(this));
        }
        return FReply::Handled().SetUserFocus(SharedThis(this));
    }
    virtual FReply OnMouseButtonUp(const FGeometry&, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton() == EKeys::MiddleMouseButton) { bDragging = false; return FReply::Handled().ReleaseMouseCapture(); }
        return FReply::Unhandled();
    }
    virtual void OnMouseCaptureLost(const FCaptureLostEvent&) override { bDragging = false; }
    virtual FReply OnMouseMove(const FGeometry&, const FPointerEvent& Event) override
    {
        if (bDragging) { Controller->Orbit(Event.GetCursorDelta(), Event.IsShiftDown(), Event.IsControlDown()); return FReply::Handled(); }
        return FReply::Unhandled();
    }
    virtual FReply OnMouseWheel(const FGeometry&, const FPointerEvent& Event) override
    {
        if (!MenuWindow) Controller->Zoom(Event.GetWheelDelta());
        return FReply::Handled();
    }
    virtual FReply OnKeyDown(const FGeometry&, const FKeyEvent& Event) override
    {
        if (Event.GetKey() == EKeys::Escape) { if (MenuWindow) CloseWindow(); else OpenPage(); return FReply::Handled(); }
        if (MenuWindow) return FReply::Handled();
        if (Event.GetKey() == EKeys::NumPadOne) Controller->SetView(1, Event.IsControlDown());
        else if (Event.GetKey() == EKeys::NumPadThree) Controller->SetView(3, Event.IsControlDown());
        else if (Event.GetKey() == EKeys::NumPadSeven) Controller->SetView(7, Event.IsControlDown());
        else if (Event.GetKey() == EKeys::NumPadFive) Controller->ToggleProjection();
        else if (Event.GetKey() == EKeys::Decimal || Event.GetKey() == EKeys::Home) Controller->FocusModel();
        else return FReply::Unhandled();
        return FReply::Handled();
    }
};

AMmdViewerGameMode::AMmdViewerGameMode()
{
	PlayerControllerClass = AMmdViewerController::StaticClass(); DefaultPawnClass = nullptr;
}

void AMmdViewerController::BeginPlay()
{
	Super::BeginPlay(); bShowMouseCursor = true;
	ToonMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/MmdViewer/M_Toon.M_Toon"));
	ToonTwoSidedMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/MmdViewer/M_ToonTwoSided.M_ToonTwoSided"));
	OutlineMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/MmdViewer/M_Outline.M_Outline"));
	TranslucentMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/MmdViewer/M_ToonTranslucent.M_ToonTranslucent"));
	TranslucentTwoSidedMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/MmdViewer/M_ToonTranslucentTwoSided.M_ToonTranslucentTwoSided"));
    ImportTemplate = NewObject<UVrmAssetListObject>(this);
    ImportTemplate->MtoonUnlitSet = LoadObject<UVrmImportMaterialSet>(nullptr, TEXT("/VRM4U/ImportDataSet/UE5/DS_VRM_UE5_MToonUnLit.DS_VRM_UE5_MToonUnLit"));
	ViewerCamera = GetWorld()->SpawnActor<ACameraActor>(); SetViewTarget(ViewerCamera);
	UCameraComponent* C = ViewerCamera->GetCameraComponent(); C->FieldOfView = 35; C->bConstrainAspectRatio = false;
	C->PostProcessSettings.bOverride_AutoExposureMethod = true; C->PostProcessSettings.AutoExposureMethod = AEM_Manual;
	C->PostProcessSettings.bOverride_AutoExposureBias = true; C->PostProcessSettings.AutoExposureBias = 0;
	C->PostProcessSettings.bOverride_AutoExposureApplyPhysicalCameraExposure = true; C->PostProcessSettings.AutoExposureApplyPhysicalCameraExposure = false;
	C->PostProcessSettings.bOverride_BloomIntensity = true; C->PostProcessSettings.BloomIntensity = 0.08f;
	C->PostProcessSettings.bOverride_VignetteIntensity = true; C->PostProcessSettings.VignetteIntensity = 0;
	UpdateCamera();
	Widget = SNew(SMmdViewer, this); GEngine->GameViewport->AddViewportWidgetContent(Widget.ToSharedRef());
	FInputModeUIOnly Input; Input.SetWidgetToFocus(Widget); Input.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock); SetInputMode(Input);
	FString AutoImport;
	if (FParse::Value(FCommandLine::Get(), TEXT("MmdArchive="), AutoImport)) LoadArchive(AutoImport);
}

void AMmdViewerController::EndPlay(const EEndPlayReason::Type Reason)
{
	if (Widget) Widget->CloseWindow();
	if (Widget && GEngine && GEngine->GameViewport) GEngine->GameViewport->RemoveViewportWidgetContent(Widget.ToSharedRef());
	Widget.Reset(); Super::EndPlay(Reason);
}

void AMmdViewerController::ImportArchive()
{
    Widget->CloseWindow();
#if PLATFORM_WINDOWS
	IFileOpenDialog* Dialog = nullptr;
	HRESULT Init = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
	if (SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&Dialog))))
	{
		COMDLG_FILTERSPEC Filter{L"MMD ZIP 压缩包", L"*.zip"}; Dialog->SetFileTypes(1, &Filter); Dialog->SetTitle(L"导入 MMD 模型压缩包");
		Dialog->SetOptions(FOS_FILEMUSTEXIST | FOS_PATHMUSTEXIST | FOS_FORCEFILESYSTEM | FOS_NOCHANGEDIR);
		const void* Parent = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(Widget);
		if (SUCCEEDED(Dialog->Show(static_cast<HWND>(const_cast<void*>(Parent)))))
		{
			IShellItem* Item = nullptr;
			if (SUCCEEDED(Dialog->GetResult(&Item)))
			{
				PWSTR File = nullptr;
				if (SUCCEEDED(Item->GetDisplayName(SIGDN_FILESYSPATH, &File))) { FString Path(File); CoTaskMemFree(File); LoadArchive(Path); }
				Item->Release();
			}
		}
		Dialog->Release();
	}
	else Status = TEXT("无法打开系统文件选择器。");
	if (SUCCEEDED(Init)) CoUninitialize();
#else
	Status = TEXT("当前导入文件选择器仅支持 Windows。");
#endif
}

void AMmdViewerController::LoadArchive(const FString& Path)
{
    if (bBusy) return;
    bBusy = true; Status = TEXT("正在展开压缩包…"); Widget->OpenPage("Status");
    const FString Destination = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("MmdImports") / FGuid::NewGuid().ToString(EGuidFormats::Digits));
    const FString Script = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("Scripts/Expand-MmdArchive.ps1"));
    TWeakObjectPtr<AMmdViewerController> Weak(this);
    Async(EAsyncExecution::ThreadPool, [Weak, Path, Destination, Script]
    {
        auto Quote = [](FString S) { return TEXT("'") + S.Replace(TEXT("'"), TEXT("''")) + TEXT("'"); };
        FString Command = TEXT("& ([ScriptBlock]::Create([IO.File]::ReadAllText(") + Quote(Script) + TEXT("))) -ArchivePath ") + Quote(Path) + TEXT(" -Destination ") + Quote(Destination);
        auto Utf16 = StringCast<UTF16CHAR>(*Command);
        FString Args = TEXT("-NoProfile -NonInteractive -EncodedCommand ") + FBase64::Encode(reinterpret_cast<const uint8*>(Utf16.Get()), Utf16.Length() * 2);
        FString StdOut, StdErr; int32 Code = -1;
        FPlatformProcess::ExecProcess(TEXT("powershell.exe"), *Args, &Code, &StdOut, &StdErr);
        TArray<FString> Choices;
        if (Code == 0) IFileManager::Get().FindFilesRecursive(Choices, *Destination, TEXT("*.pmx"), true, false);
        AsyncTask(ENamedThreads::GameThread, [Weak, Destination, Choices = MoveTemp(Choices), Code, StdErr]() mutable
        {
            if (!Weak.IsValid()) return;
            auto* Self = Weak.Get(); Self->bBusy = false;
            if (Code != 0) { Self->Status = TEXT("无法展开 ZIP：文件损坏、加密、路径不安全或大小超限。详情见日志。"); UE_LOG(LogTemp, Warning, TEXT("MMD ZIP: %s"), *StdErr); Self->Widget->OpenPage("Status"); return; }
            if (Choices.IsEmpty()) { Self->Status = TEXT("压缩包中没有 PMX 文件。"); Self->Widget->OpenPage("Status"); return; }
            Self->ImportDirectory = Destination; Self->ModelChoices.Reset();
            for (FString& Choice : Choices) { FPaths::MakePathRelativeTo(Choice, *(Destination + TEXT("/"))); Self->ModelChoices.Add(Choice); }
            Self->ModelChoices.Sort(); Self->bChoosing = true; Self->Widget->RefreshChoices(); Self->Status = TEXT("请选择要加载的 PMX 文件。");
            FString AutoModel;
            if (FParse::Value(FCommandLine::Get(), TEXT("MmdModel="), AutoModel)) Self->LoadModel(AutoModel);
        });
    });
}

void AMmdViewerController::LoadModel(const FString& Path)
{
    if (bBusy || !ModelChoices.Contains(Path)) return;
    if (!ImportTemplate || !ImportTemplate->MtoonUnlitSet) { Status = TEXT("缺少 VRM4U 默认导入资源。"); return; }
    PendingPath = Path; bBusy = true; bChoosing = false; Status = TEXT("正在加载模型与贴图…"); Widget->OpenPage("Status");
    FImportOptionData Options;
    Options.ModelScale = 0.1f;
    Options.MaterialType = EVRMImportMaterialType::VRMIMT_MToonUnlit;
    Options.bSkipPhysics = true; Options.bSkipRetargeter = true; Options.bSkipMorphTarget = true;
    Options.bGenerateOutlineMaterial = false;
    // VRM4U's async prepass assumes VRM; its generic loader handles PMX.
    FTimerHandle Handle;
    GetWorldTimerManager().SetTimer(Handle, [this, Path, Options]
    {
        ULoaderBPFunctionLibrary::LoadVRMFile(ImportTemplate, PendingAsset, ImportDirectory / Path, Options);
        OnModelLoaded();
    }, 0.1f, false);
}

void AMmdViewerController::OnModelLoaded()
{
    bBusy = false;
    if (!PendingAsset || !PendingAsset->SkeletalMesh) { Status = TEXT("VRM4U 无法读取此 PMX，详见输出日志。"); UE_LOG(LogTemp, Error, TEXT("MMD_LOAD_FAILED %s"), *PendingPath); Widget->OpenPage("Status"); return; }
    if (!ToonMaterial || !ToonTwoSidedMaterial || !TranslucentMaterial || !TranslucentTwoSidedMaterial || !OutlineMaterial) { Status = TEXT("缺少卡通材质，请运行 Scripts/setup_viewer.py。"); PendingAsset = nullptr; Widget->OpenPage("Status"); return; }
    PendingAsset->SkeletalMesh->CalculateExtendedBounds();
    // The plugin leaves PMX textures in CPU memory for the runtime caller to upload.
    for (UTexture2D* Texture : PendingAsset->Textures) if (Texture && !Texture->GetResource()) Texture->UpdateResource();
    auto* NewActor = GetWorld()->SpawnActor<AActor>();
    auto* Mesh = NewObject<USkeletalMeshComponent>(NewActor); NewActor->SetRootComponent(Mesh); Mesh->RegisterComponent();
    Mesh->SetSkeletalMesh(PendingAsset->SkeletalMesh); Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision); Mesh->SetSimulatePhysics(false); Mesh->SetCastShadow(false);
    Mesh->bPauseAnims = true;
    auto* Outline = NewObject<USkeletalMeshComponent>(NewActor);
    Outline->SetupAttachment(Mesh); Outline->RegisterComponent(); Outline->SetSkeletalMesh(PendingAsset->SkeletalMesh);
    Outline->SetCollisionEnabled(ECollisionEnabled::NoCollision); Outline->SetCastShadow(false); Outline->bPauseAnims = true;
    const bool bBaseColorOnly = FParse::Param(FCommandLine::Get(), TEXT("MmdBaseColor"));
    Outline->SetVisibility(!bBaseColorOnly);
    int32 Missing = 0;
    for (int32 I = 0; I < Mesh->GetNumMaterials(); ++I)
    {
        UMaterialInterface* Source = Mesh->GetMaterial(I);
        UTexture* Texture = nullptr; FLinearColor Tint = FLinearColor::White;
        if (Source)
        {
            if (!Source->GetTextureParameterValue(TEXT("mtoon_tex_MainTex"), Texture)) Source->GetTextureParameterValue(TEXT("gltf_tex_diffuse"), Texture);
            if (!Source->GetVectorParameterValue(TEXT("mtoon_Color"), Tint)) Source->GetVectorParameterValue(TEXT("gltf_basecolor"), Tint);
        }
        bool Transparent = Source && IsTranslucentBlendMode(Source->GetBlendMode());
        const bool TwoSided = Source && Source->IsTwoSided();
        UMaterialInterface* Parent = Transparent
            ? (TwoSided ? TranslucentTwoSidedMaterial : TranslucentMaterial)
            : (TwoSided ? ToonTwoSidedMaterial : ToonMaterial);
        auto* Mat = UMaterialInstanceDynamic::Create(Parent, Mesh);
        Mat->SetScalarParameterValue(TEXT("ToonStrength"), bBaseColorOnly ? 0.f : 1.f);
        Mat->SetVectorParameterValue(TEXT("Tint"), Tint); Mat->SetScalarParameterValue(TEXT("Opacity"), Tint.A);
        FString SlotName = PendingAsset->SkeletalMesh->GetMaterials()[I].MaterialSlotName.ToString() + (Texture ? Texture->GetName() : TEXT(""));
        float Region = 0;
        if (SlotName.Contains(TEXT("顏")) || SlotName.Contains(TEXT("顔")) || SlotName.Contains(TEXT("颜")) || SlotName.Contains(TEXT("脸")) || SlotName.Contains(TEXT("face"), ESearchCase::IgnoreCase)) Region = 1;
        else if (SlotName.Contains(TEXT("髪")) || SlotName.Contains(TEXT("发")) || SlotName.Contains(TEXT("hair"), ESearchCase::IgnoreCase)) Region = 2;
        else if (SlotName.Contains(TEXT("肌")) || SlotName.Contains(TEXT("skin"), ESearchCase::IgnoreCase)) Region = 3;
        Mat->SetScalarParameterValue(TEXT("Region"), Region);
        if (Texture) Mat->SetTextureParameterValue(TEXT("BaseTexture"), Texture); else ++Missing;
        float EdgeEnabled = 0.f, EdgeSize = 0.f;
        FLinearColor EdgeColor = FLinearColor::Black;
        if (Source)
        {
            Source->GetScalarParameterValue(TEXT("mmd_EdgeEnabled"), EdgeEnabled);
            Source->GetScalarParameterValue(TEXT("mmd_EdgeSize"), EdgeSize);
            Source->GetVectorParameterValue(TEXT("mmd_EdgeColor"), EdgeColor);
        }
        UE_LOG(LogTemp, Display, TEXT("MMD_MATERIAL slot=%s texture=%s tint=%s translucent=%d two_sided=%d edge=%.0f edge_size=%.3f region=%.0f"), *SlotName, *GetNameSafe(Texture), *Tint.ToString(), Transparent, TwoSided, EdgeEnabled, EdgeSize, Region);
        Mesh->SetMaterial(I, Mat);
        auto* Ink = UMaterialInstanceDynamic::Create(OutlineMaterial, Outline);
        Ink->SetVectorParameterValue(TEXT("Tint"), EdgeColor);
        Ink->SetScalarParameterValue(TEXT("Opacity"), Transparent || EdgeEnabled < 0.5f ? 0.f : Tint.A * EdgeColor.A);
        Ink->SetScalarParameterValue(TEXT("OutlineWidth"), EdgeSize * (Region == 1 ? 0.05f : 0.12f));
        if (Texture) Ink->SetTextureParameterValue(TEXT("BaseTexture"), Texture);
        Outline->SetMaterial(I, Ink);
    }
    // The plugin owns geometry, skinning and texture decoding; this layer only sets the display material.
    if (ModelActor) ModelActor->Destroy(); ModelActor = NewActor; LoadedAsset = PendingAsset; PendingAsset = nullptr;
    FBoxSphereBounds Bounds = LoadedAsset->SkeletalMesh->GetBounds();
    if (auto* Render = LoadedAsset->SkeletalMesh->GetResourceForRendering(); Render && Render->LODRenderData.Num())
    {
        const auto& Positions = Render->LODRenderData[0].StaticVertexBuffers.PositionVertexBuffer;
        if (Positions.GetVertexData() && Positions.GetNumVertices())
        {
            FBox VertexBounds(ForceInit);
            for (uint32 I = 0; I < Positions.GetNumVertices(); ++I) VertexBounds += FVector(Positions.VertexPosition(I));
            Bounds = FBoxSphereBounds(VertexBounds);
            LoadedAsset->SkeletalMesh->SetImportedBounds(Bounds);
            LoadedAsset->SkeletalMesh->CalculateExtendedBounds();
            Mesh->UpdateBounds(); Outline->UpdateBounds();
        }
    }
    FRotator ModelRotation(0, -90, 0);
    Mesh->SetWorldRotation(ModelRotation);
    Mesh->SetRelativeLocation(ModelRotation.RotateVector(FVector(-Bounds.Origin.X, -Bounds.Origin.Y, Bounds.BoxExtent.Z - Bounds.Origin.Z)));
    ModelCenter = FVector(0, 0, Bounds.BoxExtent.Z); ModelRadius = Bounds.SphereRadius;
    UE_LOG(LogTemp, Display, TEXT("MMD_BOUNDS origin=%s extent=%s radius=%.2f"), *Bounds.Origin.ToString(), *Bounds.BoxExtent.ToString(), ModelRadius);
    ModelName = FPaths::GetBaseFilename(PendingPath);
    int32 Vertices = 0, Triangles = 0;
    if (auto* Render = LoadedAsset->SkeletalMesh->GetResourceForRendering(); Render && Render->LODRenderData.Num())
    {
        Vertices = Render->LODRenderData[0].GetNumVertices();
        for (const auto& Section : Render->LODRenderData[0].RenderSections) Triangles += Section.NumTriangles;
    }
    ModelInfo = FString::Printf(TEXT("%s 个顶点\n%s 个三角形\n%d 个材质\n\nVRM4U"), *FText::AsNumber(Vertices).ToString(), *FText::AsNumber(Triangles).ToString(), Mesh->GetNumMaterials());
    Rotation = FRotator(-5, 180, 0); FocusModel();
    Status = Missing ? FString::Printf(TEXT("已加载。%d 个材质未匹配到基础贴图，使用材质颜色。"), Missing) : TEXT("已加载。中键旋转，Shift + 中键平移，滚轮缩放。");
    UE_LOG(LogTemp, Display, TEXT("MMD_LOADED plugin=VRM4U name=%s vertices=%d triangles=%d missing=%d textures=%d"), *ModelName, Vertices, Triangles, Missing, LoadedAsset->Textures.Num());
    Widget->CloseWindow();
    FString Capture;
    if (FParse::Value(FCommandLine::Get(), TEXT("MmdCapture="), Capture))
    {
        FTimerHandle Handle;
        GetWorldTimerManager().SetTimer(Handle, [Capture] { FScreenshotRequest::RequestScreenshot(Capture, true, false); }, 8.f, false);
        if (FParse::Param(FCommandLine::Get(), TEXT("MmdTestExit")))
        {
            FTimerHandle ExitHandle;
            GetWorldTimerManager().SetTimer(ExitHandle, [] { FGenericPlatformMisc::RequestExit(false); }, 12.f, false);
        }
    }
}

void AMmdViewerController::UpdateCamera()
{
	if (!ViewerCamera) return;
	ViewerCamera->SetActorLocationAndRotation(Target - Rotation.Vector() * Distance, Rotation);
	ViewerCamera->GetCameraComponent()->ProjectionMode = bOrthographic ? ECameraProjectionMode::Orthographic : ECameraProjectionMode::Perspective;
	ViewerCamera->GetCameraComponent()->OrthoWidth = Distance * 0.65f;
}
void AMmdViewerController::Orbit(FVector2D Delta, bool Pan, bool Dolly)
{
	if (Dolly) { Zoom(-Delta.Y * 0.03f); return; }
	if (Pan) { Target += (FRotationMatrix(Rotation).GetUnitAxis(EAxis::Y) * -Delta.X + FRotationMatrix(Rotation).GetUnitAxis(EAxis::Z) * Delta.Y) * Distance * 0.0008f; }
	else { Rotation.Yaw += Delta.X * 0.3f; Rotation.Pitch = FMath::Clamp(Rotation.Pitch + Delta.Y * 0.3f, -89.9f, 89.9f); }
	UpdateCamera();
}
void AMmdViewerController::Zoom(float Delta) { Distance = FMath::Clamp(Distance * FMath::Exp(-Delta * 0.12f), FMath::Max(1.f, ModelRadius * 0.08f), FMath::Max(1000.f, ModelRadius * 30)); UpdateCamera(); }
void AMmdViewerController::FocusModel() { Target = ModelCenter; Distance = FMath::Max(10.f, ModelRadius * 5.4f); UpdateCamera(); }
void AMmdViewerController::SetView(int32 View, bool Reverse)
{
	if (View == 1) Rotation = FRotator(0, Reverse ? 0 : 180, 0);
	if (View == 3) Rotation = FRotator(0, Reverse ? 90 : -90, 0);
	if (View == 7) Rotation = FRotator(Reverse ? 90 : -90, 180, 0);
	bOrthographic = true; UpdateCamera();
}
void AMmdViewerController::ToggleProjection() { bOrthographic = !bOrthographic; UpdateCamera(); }
