param([string]$ArchivePath, [string]$Destination)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression

# .NET handles ZIP and Deflate; legacy Chinese ZIP entry names use CP936.
if ((Get-Item -LiteralPath $ArchivePath).Length -gt 512MB) { throw 'ZIP exceeds 512 MiB.' }
if (Test-Path -LiteralPath $Destination) { throw 'Destination already exists.' }
$root = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
$stream = [IO.File]::OpenRead($ArchivePath)
$zip = $null
try {
    $zip = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Read, $false, [Text.Encoding]::GetEncoding(936))
    if ($zip.Entries.Count -gt 20000) { throw 'Too many ZIP entries.' }
    $total = 0L
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName.Replace('/', '\')
        if ([IO.Path]::IsPathRooted($name) -or $name.Contains(':')) { throw 'Unsafe ZIP path.' }
        $target = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $name))
        if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw 'ZIP path escapes destination.' }
        if (-not $names.Add($target)) { throw 'Duplicate ZIP entry.' }
        if (($entry.ExternalAttributes -band 0xF0000000L) -eq 0xA0000000L) { throw 'ZIP symbolic links are unsupported.' }
        $total += $entry.Length
        if ($entry.Length -gt 256MB -or $total -gt 1GB) { throw 'Uncompressed ZIP exceeds limit.' }
    }
    foreach ($entry in $zip.Entries) {
        $target = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $entry.FullName.Replace('/', '\')))
        if (-not $entry.Name) { [IO.Directory]::CreateDirectory($target) | Out-Null; continue }
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
        $input = $entry.Open()
        $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew)
        try {
            $buffer = New-Object byte[] 65536
            $written = 0L
            while (($n = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $written += $n
                if ($written -gt $entry.Length) { throw 'ZIP entry exceeds declared length.' }
                $output.Write($buffer, 0, $n)
            }
            if ($written -ne $entry.Length) { throw 'Truncated ZIP entry.' }
        } finally { $output.Dispose(); $input.Dispose() }
    }
} finally { if ($zip) { $zip.Dispose() }; $stream.Dispose() }
