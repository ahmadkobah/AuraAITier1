# Test direct file upload to AI service
param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

if (-not (Test-Path $FilePath)) {
    Write-Host "ERROR: File not found: $FilePath" -ForegroundColor Red
    exit 1
}

$fileInfo = Get-Item $FilePath
Write-Host "Original file:" -ForegroundColor Yellow
Write-Host "  Path: $FilePath"
Write-Host "  Size: $($fileInfo.Length) bytes"
Write-Host "  Hash: $((Get-FileHash $FilePath).Hash)"

Write-Host "`nUploading to AI service..." -ForegroundColor Cyan

$url = "http://localhost:9000/api/v1/upload"
$bytes = [System.IO.File]::ReadAllBytes($FilePath)

# Create multipart form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = @(
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"test_invoice.pdf`"",
    "Content-Type: application/pdf",
    "",
    [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($bytes),
    "--$boundary--"
)

$body = $bodyLines -join $LF

try {
    $response = Invoke-WebRequest -Uri $url -Method POST `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body ([System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes($body))
    
    $result = $response.Content | ConvertFrom-Json
    Write-Host "`n✅ Upload successful!" -ForegroundColor Green
    Write-Host "Document ID: $($result.doc_id)" -ForegroundColor Cyan
    
    # Check the uploaded file
    $uploadDir = "C:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung\uploads"
    $uploadedFiles = Get-ChildItem $uploadDir -Filter "$($result.doc_id)*.pdf"
    
    if ($uploadedFiles) {
        $uploadedFile = $uploadedFiles[0]
        Write-Host "`nUploaded file check:" -ForegroundColor Yellow
        Write-Host "  Path: $($uploadedFile.FullName)"
        Write-Host "  Size: $($uploadedFile.Length) bytes"
        Write-Host "  Hash: $((Get-FileHash $uploadedFile.FullName).Hash)"
        
        if ($uploadedFile.Length -eq $fileInfo.Length) {
            Write-Host "`n✅ File size matches!" -ForegroundColor Green
        } else {
            Write-Host "`n❌ FILE SIZE MISMATCH!" -ForegroundColor Red
            Write-Host "  Original: $($fileInfo.Length) bytes" -ForegroundColor Red
            Write-Host "  Uploaded: $($uploadedFile.Length) bytes" -ForegroundColor Red
        }
        
        $originalHash = (Get-FileHash $FilePath).Hash
        $uploadedHash = (Get-FileHash $uploadedFile.FullName).Hash
        
        if ($originalHash -eq $uploadedHash) {
            Write-Host "✅ File hash matches - upload intact!" -ForegroundColor Green
        } else {
            Write-Host "❌ FILE CORRUPTED DURING UPLOAD!" -ForegroundColor Red
            Write-Host "  Original hash: $originalHash" -ForegroundColor Red
            Write-Host "  Uploaded hash: $uploadedHash" -ForegroundColor Red
        }
    }
    
} catch {
    Write-Host "`n❌ Upload failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host $reader.ReadToEnd()
    }
}
