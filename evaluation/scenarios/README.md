# Evaluation Scenarios

Place ground-truth scenario JSON files in this directory.

## Schema

Each file must follow this structure:

```json
{
  "id": "unique_scenario_id",
  "name": "Human-readable Scenario Name",
  "description": "Brief description of the scenario for documentation.",
  "user_problem": "Exact prompt text fed to all three system versions.",
  "reference_architecture": {
    "full_text": "Complete reference architecture text from official cloud provider documentation. This is the ground truth compared against generated outputs using METEOR and BERTScore.",
    "services_expected": ["EC2", "ALB", "RDS", "S3", "CloudFront"],
    "domains_covered": ["compute", "network", "storage", "database"]
  },
  "source": "URL or citation for the reference architecture (e.g., AWS Well-Architected Framework)"
}
```

## Guidelines

- `user_problem` must be identical across all system versions for controlled comparison.
- `reference_architecture.full_text` should be sourced from official AWS documentation (Well-Architected Framework, reference architectures, solution guides).
- `services_expected` lists the AWS services that a correct architecture should mention.
- Keep 3–5 scenario files for statistical coverage.

## Naming Convention

`scenario_01_<short_name>.json`, `scenario_02_<short_name>.json`, etc.
