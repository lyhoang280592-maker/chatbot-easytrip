Add-Type -AssemblyName System.IO.Compression.FileSystem

$src = "c:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip\temp_build_mau01"
$dst = "c:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip\Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"
$dsk = "C:\Users\PC\Desktop\Mau_so_01_PLI_Giai_trinh_Lao_dong_nuoc_ngoai.docx"

if (Test-Path $dst) {
    Remove-Item $dst -Force
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($src, $dst)
Copy-Item $dst -Destination $dsk -Force

if (Test-Path $src) {
    Remove-Item $src -Recurse -Force
}

Write-Host "REPACKED_DOCX_SUCCESS"
