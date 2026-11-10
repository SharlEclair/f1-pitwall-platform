<#
.SYNOPSIS
  Remove the AWS side of the F1 Pitwall platform. Dry run by default: it only lists what would go.

.DESCRIPTION
  Deletes, in order: every object in the raw S3 bucket, the SAM stack (Lambda functions, schedules,
  SNS topic, IAM roles, the bucket), and optionally SAM's own managed artifacts stack.
  A real run needs -Execute AND you typing the confirmation phrase yourself.
  Snowflake objects are not touched here: run warehouse/99_teardown.sql as ACCOUNTADMIN.

.EXAMPLE
  .\scripts\teardown.ps1                      # dry run
  .\scripts\teardown.ps1 -Execute             # asks you to type DELETE
  .\scripts\teardown.ps1 -Execute -IncludeSamManagedStack
#>
param(
    [string]$Profile = "f1-pitwall",
    [string]$Region = "ap-southeast-2",
    [string]$StackName = "f1-pitwall-ingest",
    [switch]$Execute,
    [switch]$IncludeSamManagedStack
)

$ErrorActionPreference = "Stop"
$aws = if (Get-Command aws -ErrorAction SilentlyContinue) { "aws" } else { "C:\Program Files\Amazon\AWSCLIV2\aws.exe" }
$sam = if (Get-Command sam -ErrorAction SilentlyContinue) { "sam" } else { "C:\Program Files\Amazon\AWSSAMCLI\bin\sam.cmd" }
$common = @("--profile", $Profile, "--region", $Region)

function Get-StackBucket([string]$stack) {
    $out = & $aws cloudformation describe-stacks --stack-name $stack @common `
        --query "Stacks[0].Outputs[?OutputKey=='RawBucketName'].OutputValue" --output text 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out -or $out -eq "None") { return $null }
    return $out.Trim()
}

function Get-ObjectSummary([string]$bucket) {
    $lines = & $aws s3 ls "s3://$bucket" --recursive --summarize @common 2>$null | Select-Object -Last 2
    return ($lines -join "; ").Trim()
}

$bucket = Get-StackBucket $StackName
Write-Host "Stack:  $StackName ($Region)"
if (-not $bucket) {
    Write-Host "Stack not found or has no RawBucketName output: nothing to delete on the AWS side."
} else {
    Write-Host "Bucket: $bucket"
    Write-Host ("Contents: " + (Get-ObjectSummary $bucket))
    Write-Host "Resources that would be deleted with the stack:"
    & $aws cloudformation list-stack-resources --stack-name $StackName @common `
        --query "StackResourceSummaries[].[ResourceType,LogicalResourceId]" --output text |
        ForEach-Object { "  " + $_ }
}
$managed = "aws-sam-cli-managed-default"
if ($IncludeSamManagedStack) {
    Write-Host "SAM managed artifacts stack that would also be deleted: $managed"
}
Write-Host "Snowflake is not touched: run warehouse/99_teardown.sql as ACCOUNTADMIN."

if (-not $Execute) {
    Write-Host "`nDRY RUN: nothing was deleted. Re-run with -Execute to delete."
    return
}

$answer = Read-Host "`nType DELETE to permanently remove the resources listed above"
if ($answer -ne "DELETE") { Write-Host "Cancelled."; return }

if ($bucket) {
    Write-Host "Emptying s3://$bucket ..."
    & $aws s3 rm "s3://$bucket" --recursive @common --only-show-errors
    Write-Host "Deleting stack $StackName ..."
    & $sam delete --stack-name $StackName @common --no-prompts
}
if ($IncludeSamManagedStack) {
    $samBucket = & $aws cloudformation describe-stack-resources --stack-name $managed @common `
        --query "StackResources[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId" --output text 2>$null
    if ($samBucket) {
        Write-Host "Emptying s3://$samBucket ..."
        & $aws s3 rm "s3://$samBucket" --recursive @common --only-show-errors
    }
    Write-Host "Deleting stack $managed ..."
    & $aws cloudformation delete-stack --stack-name $managed @common
    & $aws cloudformation wait stack-delete-complete --stack-name $managed @common
}
Write-Host "Done. Verify in the AWS console that nothing is left, then run warehouse/99_teardown.sql."
