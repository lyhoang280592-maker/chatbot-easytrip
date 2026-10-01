$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$workDir = "C:\Users\PC\Downloads\chatbot-easytrip-main\chatbot-easytrip"
$xmlPath = Join-Path $workDir "sop_document.xml"
$outputDocx = Join-Path $workDir "QUY_TRINH_VAN_HANH_CHUAN_SOP_EASYTRIP.docx"
$desktopDocx = "C:\Users\PC\Desktop\QUY_TRINH_VAN_HANH_CHUAN_SOP_EASYTRIP.docx"

if (Test-Path $outputDocx) {
    Remove-Item $outputDocx -Force
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# Prepare all parts
$contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'@

$rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'@

$docRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
</Relationships>
'@

$fontTable = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:font w:name="Times New Roman">
    <w:panose1 w:val="02020603050405020304"/>
    <w:charset w:val="00"/>
    <w:family w:val="roman"/>
    <w:pitch w:val="variable"/>
  </w:font>
</w:fonts>
'@

$settings = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>
'@

$coreProps = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>QUY TRINH VAN HANH CHUAN SOP EASYTRIP</dc:title>
  <dc:subject>SOP Chuan Van Hanh EasyTrip and Visa</dc:subject>
  <dc:creator>Easy Trip &amp; Visa Co. Ltd</dc:creator>
  <cp:lastModifiedBy>Ban Giam Doc EasyTrip</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-09-28T08:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-28T08:00:00Z</dcterms:modified>
</cp:coreProperties>
'@

$appProps = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Template>Normal.dotm</Template>
  <TotalTime>15</TotalTime>
  <Pages>12</Pages>
  <Words>4500</Words>
  <Characters>25000</Characters>
  <Application>Microsoft Office Word</Application>
  <Company>EASY TRIP &amp; VISA CO. LTD</Company>
</Properties>
'@

$styles = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="26"/>
        <w:szCs w:val="26"/>
        <w:lang w:val="vi-VN"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:line="276" w:lineRule="auto" w:after="120"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>

  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="260" w:after="140"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:b/>
      <w:color w:val="003366"/>
      <w:sz w:val="30"/>
      <w:szCs w:val="30"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="200" w:after="100"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:b/>
      <w:color w:val="B22222"/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="140" w:after="80"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:b/>
      <w:color w:val="2E8B57"/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>
</w:styles>
'@

# Read the document XML directly from binary bytes (clean UTF-8)
$docBytes = [System.IO.File]::ReadAllBytes($xmlPath)

# Create ZIP with forward-slash entry names
$fs = [System.IO.File]::Create($outputDocx)
$zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create)

function Add-TextEntry($zipArchive, $entryName, $textString, $encoding) {
    $entry = $zipArchive.CreateEntry($entryName)
    $stream = $entry.Open()
    $bytes = $encoding.GetBytes($textString)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()
}

function Add-ByteEntry($zipArchive, $entryName, $byteArray) {
    $entry = $zipArchive.CreateEntry($entryName)
    $stream = $entry.Open()
    $stream.Write($byteArray, 0, $byteArray.Length)
    $stream.Close()
}

Add-TextEntry $zip "[Content_Types].xml" $contentTypes $utf8NoBom
Add-TextEntry $zip "_rels/.rels" $rootRels $utf8NoBom
Add-TextEntry $zip "word/_rels/document.xml.rels" $docRels $utf8NoBom
Add-TextEntry $zip "word/fontTable.xml" $fontTable $utf8NoBom
Add-TextEntry $zip "word/settings.xml" $settings $utf8NoBom
Add-TextEntry $zip "word/styles.xml" $styles $utf8NoBom
Add-TextEntry $zip "docProps/core.xml" $coreProps $utf8NoBom
Add-TextEntry $zip "docProps/app.xml" $appProps $utf8NoBom
Add-ByteEntry $zip "word/document.xml" $docBytes

$zip.Dispose()
$fs.Close()

Copy-Item $outputDocx -Destination $desktopDocx -Force

Write-Host "DOCX_CLEAN_BUILD_SUCCESS"
