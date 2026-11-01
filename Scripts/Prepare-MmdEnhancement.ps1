param([string]$RequestPath, [switch]$FunctionsOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Full-Path([string]$Value) { [IO.Path]::GetFullPath($Value).TrimEnd('\','/') }
function Is-Inside([string]$Value,[string]$Root) {
    (Full-Path $Value).StartsWith((Full-Path $Root)+'\',[StringComparison]::OrdinalIgnoreCase)
}
function Write-Json([string]$Path,$Value) {
    $temporary=$Path+'.tmp'
    [IO.File]::WriteAllText($temporary,($Value | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
    if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary,$Path,$Path+'.bak',$true); [IO.File]::Delete($Path+'.bak') }
    else { [IO.File]::Move($temporary,$Path) }
}
function Read-Json([string]$Path) {
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8)
    try {$reader.ReadToEnd() | ConvertFrom-Json} finally {$reader.Dispose()}
}
function Status([string]$Stage,[double]$Progress,[string]$Message,[string]$State='running',$Extra=@{}) {
    $value=@{version=1;stage=$Stage;progress=$Progress;message=$Message;state=$State}
    foreach($key in $Extra.Keys){$value[$key]=$Extra[$key]}
    Write-Json (Join-Path $script:Job 'status.json') $value
}
function Safe-Remove([string]$Path,[string]$Root) {
    if (-not (Is-Inside $Path $Root)) { throw 'Refusing cleanup outside the task data directory.' }
    if(Test-Path -LiteralPath $Path){Remove-Item -LiteralPath $Path -Recurse -Force}
}
function Hash-File([string]$Path,[string]$Algorithm) {
    $hash=[Security.Cryptography.HashAlgorithm]::Create($Algorithm)
    $stream=[IO.File]::OpenRead($Path)
    try { ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally {$stream.Dispose();$hash.Dispose()}
}
function Hash-Text([string]$Text) {
    $hash=[Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant() }
    finally {$hash.Dispose()}
}
function Resource-Manifest([string]$Root,[string]$Model,[string]$Scripts,[int]$Material,$Parameters) {
    if(-not (Is-Inside $Model $Root)){throw 'Model must be inside its imported resource directory.'}
    $pending=[Collections.Generic.Stack[string]]::new();$pending.Push($Root);$count=0
    while($pending.Count -gt 0){
        $entry=$pending.Pop();$attributes=[IO.File]::GetAttributes($entry);$count++
        if(($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $count -gt 40000){throw 'Linked or oversized resource directory is unsupported.'}
        if(($attributes -band [IO.FileAttributes]::Directory) -ne 0){foreach($child in [IO.Directory]::EnumerateFileSystemEntries($entry)){$pending.Push($child)}}
    }
    $files=@(Get-ChildItem -LiteralPath $Root -File -Recurse | Sort-Object FullName | ForEach-Object {
        if(($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Linked resource files are unsupported.'}
        [ordered]@{path=$_.FullName.Substring($Root.Length+1).Replace('\','/');sha1=(Hash-File $_.FullName 'SHA1')}
    })
    if($files.Count -gt 20000){throw 'Too many imported resource files.'}
    $scriptsList=@('generate_enhancement.py','bake_face_coordinates.py','enhancement-tools.json') | ForEach-Object {
        [ordered]@{path=$_;sha1=(Hash-File (Join-Path $Scripts $_) 'SHA1')}
    }
    [ordered]@{algorithm='face-v2';model_relative=$Model.Substring($Root.Length+1).Replace('\','/');material_index=$Material;parameters=$Parameters;files=$files;scripts=@($scriptsList)}
}
function Valid-Result([string]$Directory,[string]$ModelHash) {
    try {
        $profile=Read-Json (Join-Path $Directory 'profile.json')
        $result=Read-Json (Join-Path $Directory 'result.json')
        if($result.source_sha1 -ne $ModelHash -or $result.algorithm -ne 'face-v2'){return $false}
        foreach($name in @('profile.json','face.png','coordinates.png')){
            if((Hash-File (Join-Path $Directory $name) 'SHA256') -ne $result.files.$name){return $false}
        }
        if($profile.version -ne 1 -or $profile.source_sha1 -ne $ModelHash -or $profile.algorithm -ne 'face-v2' -or @($profile.materials).Count -eq 0){return $false}
        foreach($material in $profile.materials){
            $name=[string]$material.texture
            if($name -ne [IO.Path]::GetFileName($name) -or $name.Contains(':') -or $name.Contains('..') -or -not $name.EndsWith('.png')){return $false}
            $bytes=[IO.File]::ReadAllBytes((Join-Path $Directory $name))
            if($bytes.Length -lt 24 -or $bytes.Length -gt 4MB -or [BitConverter]::ToString($bytes[0..7]) -ne '89-50-4E-47-0D-0A-1A-0A'){return $false}
            $width=([int]$bytes[16] -shl 24)+([int]$bytes[17] -shl 16)+([int]$bytes[18] -shl 8)+$bytes[19]
            $height=([int]$bytes[20] -shl 24)+([int]$bytes[21] -shl 16)+([int]$bytes[22] -shl 8)+$bytes[23]
            if($width -lt 1 -or $height -lt 1 -or $width -gt 2048 -or $height -gt 2048){return $false}
        }
        return $true
    } catch { return $false }
}
function Download-Verified([string]$Url,[string]$Expected,[string]$Destination) {
    $uri=[Uri]$Url
    if($uri.Scheme -ne 'https' -or $uri.Host -notin @('download.blender.org','extensions.blender.org')){throw 'Only pinned official Blender sources are allowed.'}
    if($Expected -notmatch '^[a-f0-9]{64}$'){throw 'Invalid pinned SHA256.'}
    if((Test-Path -LiteralPath $Destination) -and (Hash-File $Destination 'SHA256') -eq $Expected){return}
    $part=Join-Path $script:Job 'download.part'
    $request=[Net.HttpWebRequest]::Create($uri)
    $request.Timeout=30000; $request.ReadWriteTimeout=30000
    $response=$null;$input=$null;$output=$null
    try {
        $response=$request.GetResponse();$input=$response.GetResponseStream();$output=[IO.File]::Create($part)
        $buffer=New-Object byte[] 1048576; $received=0L
        while(($count=$input.Read($buffer,0,$buffer.Length)) -gt 0){
            $output.Write($buffer,0,$count);$received+=$count
            if($received -gt 1GB){throw 'Tool download exceeds the allowed size.'}
            $fraction=if($response.ContentLength -gt 0){$received/[double]$response.ContentLength}else{0}
            Status '下载' (0.1+0.15*$fraction) ('下载生成工具：{0:N0} MiB' -f ($received/1MB))
        }
    } finally {if($output){$output.Dispose()};if($input){$input.Dispose()};if($response){$response.Dispose()}}
    if((Hash-File $part 'SHA256') -ne $Expected){throw 'Downloaded tool SHA256 does not match the pinned official release.'}
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Destination)) | Out-Null
    if(Test-Path -LiteralPath $Destination){[IO.File]::Delete($Destination)}
    [IO.File]::Move($part,$Destination)
}
function Expand-VerifiedTool([string]$Zip,[string]$Destination) {
    if(Test-Path -LiteralPath $Destination){throw 'Tool staging directory already exists.'}
    $archive=[IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        if($archive.Entries.Count -gt 100000){throw 'Too many tool archive entries.'}
        $total=0L;$names=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach($entry in $archive.Entries){
            $name=$entry.FullName.Replace('/','\');$target=Join-Path $Destination $name
            if([IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or -not (Is-Inside $target $Destination) -or -not $names.Add((Full-Path $target))){throw 'Unsafe tool archive path.'}
            if(($entry.ExternalAttributes -band 0xF0000000L) -eq 0xA0000000L){throw 'Tool archive links are unsupported.'}
            $total+=$entry.Length;if($total -gt 4GB){throw 'Expanded tool package exceeds limit.'}
        }
    } finally {$archive.Dispose()}
    [IO.Compression.ZipFile]::ExtractToDirectory($Zip,$Destination)
}
function Find-Blender {
    $candidates=[Collections.Generic.List[string]]::new()
    if($env:HONKAI_BLENDER){$candidates.Add($env:HONKAI_BLENDER)}
    $command=Get-Command blender.exe -ErrorAction SilentlyContinue
    if($command){$candidates.Add($command.Source)}
    foreach($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe')){
        if(Test-Path $key){$value=(Get-ItemProperty $key).'(default)';if($value){$candidates.Add($value)}}
    }
    foreach($drive in Get-PSDrive -PSProvider FileSystem){
        foreach($relative in @('Program Files\Blender Foundation','Blender Foundation')){
            $base=Join-Path $drive.Root $relative
            if(Test-Path -LiteralPath $base){Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue | ForEach-Object {$candidates.Add((Join-Path $_.FullName 'blender.exe'))}}
        }
    }
    foreach($candidate in $candidates | Select-Object -Unique){
        if(Test-Path -LiteralPath $candidate){
            $version=& $candidate --version 2>$null | Select-Object -First 1
            if($version -match '^Blender 5\.0\.[0-9]+'){return $candidate}
        }
    }
    return $null
}
function Find-MmdTools {
    $candidates=@()
    if($env:HONKAI_MMD_TOOLS){$candidates+=$env:HONKAI_MMD_TOOLS}
    $base=Join-Path $env:APPDATA 'Blender Foundation\Blender'
    if(Test-Path -LiteralPath $base){
        foreach($version in Get-ChildItem -LiteralPath $base -Directory){
            $candidates+=(Join-Path $version.FullName 'extensions\blender_org')
            $candidates+=(Join-Path $version.FullName 'scripts\addons')
        }
    }
    foreach($candidate in $candidates){
        $manifest=Join-Path $candidate 'mmd_tools\blender_manifest.toml'
        if((Test-Path -LiteralPath $manifest) -and ((Get-Content -LiteralPath $manifest -Raw) -match '(?m)^version\s*=\s*"4\.5\.3"')){return $candidate}
    }
    return $null
}

if($FunctionsOnly){return}
try {
    $request=Read-Json $RequestPath
    $script:Job=Full-Path ([IO.Path]::GetDirectoryName($RequestPath))
    $root=Full-Path $request.data_root;$scripts=Full-Path $request.scripts
    $resourceRoot=Full-Path $request.resource_root;$model=Full-Path $request.model
    if(-not (Is-Inside $script:Job (Join-Path $root 'Jobs'))){throw 'Invalid job directory.'}
    Status '检查缓存' 0.02 '检查模型、依赖贴图、参数与算法版本…'
    $parameters=$request.parameters | ConvertFrom-Json
    if(-not $parameters){$parameters=[pscustomobject]@{resolution=512}}
    foreach($property in $parameters.PSObject.Properties){if($property.Name -ne 'resolution'){throw 'Unknown generation parameter.'}}
    $resolution=if($null -eq $parameters.resolution){512}else{[int]$parameters.resolution}
    if($resolution -notin @(256,512,1024)){throw 'Resolution must be 256, 512 or 1024.'}
    $parameters=[ordered]@{resolution=$resolution}
    $manifest=Resource-Manifest $resourceRoot $model $scripts ([int]$request.material_index) $parameters
    $cacheKey=Hash-Text ($manifest | ConvertTo-Json -Depth 12 -Compress)
    $cacheRoot=Join-Path $root 'Enhancements';$cache=Join-Path $cacheRoot $cacheKey
    $indexPath=Join-Path $cacheRoot ('Index\'+$cacheKey+'.json')
    if(Test-Path -LiteralPath $indexPath){
        $cachedIndex=Read-Json $indexPath
        if((Is-Inside $cachedIndex.directory $cacheRoot)){$cache=Full-Path $cachedIndex.directory}
    }
    $sourceHash=(Hash-File $model 'SHA1')
    $installedManifest=$null
    if(Test-Path -LiteralPath (Join-Path $cache 'manifest.json')){
        $installedManifest=Read-Json (Join-Path $cache 'manifest.json')
    }
    if(-not $request.force -and $installedManifest.cache_key -eq $cacheKey -and @($installedManifest.outputs).Count -eq 3 -and (Valid-Result $cache $sourceHash)){
        Status '完成' 1 '已复用有效增强数据。' 'succeeded' @{cache_hit=$true;result_directory=$cache};exit 0
    }
    Status '准备' 0.08 '检查兼容的 Blender 与 MMD Tools…'
    $tools=Read-Json (Join-Path $scripts 'enhancement-tools.json')
    $toolRoot=Join-Path $root 'Tools';[IO.Directory]::CreateDirectory($toolRoot)|Out-Null
    $blender=Find-Blender
    if(-not $blender){
        $destination=Join-Path $toolRoot $tools.blender.directory
        $executable=Join-Path $destination $tools.blender.executable
        if(-not (Test-Path -LiteralPath $executable)){
            $zip=Join-Path $toolRoot 'Downloads\blender-5.0.0.zip'
            Download-Verified $tools.blender.url $tools.blender.sha256 $zip
            Status '准备' 0.28 '校验成功，解压独立 Blender 便携包…'
            $staging=Join-Path $script:Job 'blender-package';Expand-VerifiedTool $zip $staging
            if(Test-Path -LiteralPath $destination){throw 'Incomplete Blender tool directory; clear it manually before retrying.'}
            [IO.Directory]::Move($staging,$destination)
        }
        $blender=$executable
    }
    $mmd=Find-MmdTools
    if(-not $mmd){
        $mmd=Join-Path $toolRoot $tools.mmd_tools.directory
        if(-not (Test-Path -LiteralPath (Join-Path $mmd 'mmd_tools\blender_manifest.toml'))){
            $zip=Join-Path $toolRoot 'Downloads\mmd-tools-4.5.3.zip'
            Download-Verified $tools.mmd_tools.url $tools.mmd_tools.sha256 $zip
            Status '准备' 0.30 '准备独立 MMD Tools，不修改本机插件设置…'
            $staging=Join-Path $script:Job 'mmd-package';[IO.Directory]::CreateDirectory($staging)|Out-Null
            Expand-VerifiedTool $zip (Join-Path $staging 'mmd_tools')
            if(Test-Path -LiteralPath $mmd){throw 'Incomplete MMD Tools directory; clear it manually before retrying.'}
            [IO.Directory]::Move($staging,$mmd)
        }
    }
    $output=Join-Path $script:Job 'output';[IO.Directory]::CreateDirectory($output)|Out-Null
    $parametersPath=Join-Path $script:Job 'parameters.json';Write-Json $parametersPath $parameters
    $quote={param($value) '"'+([string]$value).Replace('"','\"')+'"'}
    $arguments=@('--background','--factory-startup','--python-exit-code','1','--python',(& $quote (Join-Path $scripts 'generate_enhancement.py')),'--','--pmx',(& $quote $model),'--output',(& $quote $output),'--mmd-tools',(& $quote $mmd),'--parameters-json',(& $quote $parametersPath))
    if([int]$request.material_index -ge 0){$arguments+=@('--material-index',[string]$request.material_index)}
    Status '生成' 0.35 '后台生成面部增强数据，当前模型保持可查看。'
    $process=Start-Process -FilePath $blender -ArgumentList $arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $script:Job 'blender.log') -RedirectStandardError (Join-Path $script:Job 'blender-errors.log')
    $processHandle=$process.Handle
    while(-not $process.HasExited){
        $childStatus=Join-Path $output 'status.json'
        if(Test-Path -LiteralPath $childStatus){
            try{$child=Read-Json $childStatus
                Status '生成' (0.35+0.6*[Math]::Min(1,[Math]::Max(0,[double]$child.progress))) ([string]$child.message)
            }catch{}
        }
        Start-Sleep -Milliseconds 150
        $process.Refresh()
    }
    $process.WaitForExit()
    $child=Read-Json (Join-Path $output 'status.json')
    if($child.state -eq 'needs_material'){
        Status '选择面部材质' 0 '无法可靠识别面部，请在模型预览中选择材质。' 'needs_material' @{candidates=@($child.candidates)};exit 0
    }
    if($process.ExitCode -ne 0 -or $child.state -eq 'failed' -or -not (Valid-Result $output $sourceHash)){throw ('Generation failed or returned invalid data: '+[string]$child.message)}
    $currentManifest=Resource-Manifest $resourceRoot $model $scripts ([int]$request.material_index) $parameters
    if((Hash-Text ($currentManifest | ConvertTo-Json -Depth 12 -Compress)) -ne $cacheKey){throw 'Model dependencies or generation scripts changed during the job; retry.'}
    Status '应用' 0.97 '检查完成，保留旧缓存并安装新的增强数据…'
    $manifest.cache_key=$cacheKey
    $manifest.outputs=@('profile.json','face.png','coordinates.png') | ForEach-Object {
        [ordered]@{path=$_;sha1=(Hash-File (Join-Path $output $_) 'SHA1')}
    }
    Write-Json (Join-Path $output 'manifest.json') $manifest
    [IO.Directory]::CreateDirectory($cacheRoot)|Out-Null
    if(Test-Path -LiteralPath $cache){$cache=Join-Path $cacheRoot ($cacheKey+'-'+[Guid]::NewGuid().ToString('N'))}
    [IO.Directory]::Move($output,$cache)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($indexPath))|Out-Null
    Write-Json $indexPath @{directory=$cache}
    Status '完成' 1 '增强数据已生成。' 'succeeded' @{cache_hit=$false;result_directory=$cache}
    exit 0
} catch {
    if($script:Job){Status '失败' 0 ('生成失败：'+$_.Exception.Message) 'failed'}
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
