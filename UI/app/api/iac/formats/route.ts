/**
 * GET /api/iac/formats — Return supported IaC formats per cloud provider.
 *
 * Used by the IaCGenerationPanel to populate the format selector dropdown
 * based on the currently selected cloud provider.
 */
import { NextResponse } from 'next/server';

const SUPPORTED_FORMATS: Record<string, { value: string; label: string; extension: string }[]> = {
  aws: [
    { value: 'terraform', label: 'Terraform (HCL)', extension: '.tf' },
    { value: 'cloudformation', label: 'CloudFormation (YAML)', extension: '.yaml' },
  ],
  azure: [
    { value: 'terraform', label: 'Terraform (HCL)', extension: '.tf' },
    { value: 'bicep', label: 'Bicep', extension: '.bicep' },
  ],
};

export async function GET() {
  return NextResponse.json(SUPPORTED_FORMATS);
}
