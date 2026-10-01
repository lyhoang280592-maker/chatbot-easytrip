Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcDir = "c:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip\temp_build_mau01"
$dstZip = "c:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip\Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"
$dskZip = "C:\Users\PC\Desktop\Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"

if (Test-Path $dstZip) {
    Remove-Item $dstZip -Force
}

$zip = [System.IO.Compression.ZipFile]::Open($dstZip, [System.IO.Compression.ZipArchiveMode]::Create)

$files = Get-ChildItem -Path $srcDir -Recurse -File
foreach ($file in $files) {
    $relPath = $file.FullName.Substring($srcDir.Length + 1).Replace("\", "/")
    Write-Host "Adding entry: $relPath"
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $relPath, [System.IO.Compression.CompressionLevel]::Optimal)
}

$zip.Dispose()

Copy-Item $dstZip -Destination $dskZip -Force

Write-Host "Zipped and copied successfully with forward-slash entry names!"
