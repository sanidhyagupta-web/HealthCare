---
paths:
  - "your-ops-repo/**" # <!-- CUSTOMIZE: glob pattern for your infrastructure/ops repo, or remove this file if no ops repo -->
---

# Ops / Infrastructure Rules

## OPS-01: Helm chart validity <!-- severity: blocker -->
Modified Helm charts must pass `helm lint`. Template syntax must be valid. Values files must define all required values referenced in templates. Check that `{{ }}` expressions reference existing values and have appropriate defaults.

## OPS-02: Environment consistency <!-- severity: suggestion -->
If a new value is added to one environment's values file (e.g., `dev.yml`), verify it is also added to all other environment files (`qa.yml`, `uat.yml`, `prod.yml`) with appropriate values.

## OPS-03: Terraform state safety <!-- severity: blocker -->
Terraform changes should not destroy or replace resources that contain data (RDS instances, S3 buckets, EBS volumes) without explicit confirmation. Check for `force_new` or resource type changes that trigger replacement. Verify `prevent_destroy` lifecycle rules are in place for stateful resources.

## OPS-04: Secret management <!-- severity: blocker -->
Secrets must not be hardcoded in Helm values, Terraform configs, or Kubernetes manifests. They should reference Kubernetes secrets, a secrets manager, or environment variable injection.

## OPS-05: Resource limits <!-- severity: suggestion -->
Kubernetes deployments should have CPU and memory requests and limits defined. Limits should be consistent with similar existing services — not unreasonably high (wasting resources) or low (causing OOM kills).

## OPS-06: Health checks <!-- severity: suggestion -->
New Kubernetes deployments should have liveness and readiness probes configured. Probes should point to actual health check endpoints, not just the root path. Probe timing should be appropriate for the service's startup time.

## OPS-07: Ingress and networking <!-- severity: blocker -->
New ingress rules should have appropriate TLS configuration. Path-based routing should not conflict with existing rules. New services should not be accidentally exposed publicly when they should be internal-only.

## OPS-08: Docker image tags <!-- severity: suggestion -->
Kubernetes deployments should not use `latest` tag for container images. Use specific version tags or SHA digests for reproducibility. Image pull policies should be appropriate (`IfNotPresent` for tagged images).

## OPS-09: Monitoring and alerting <!-- severity: suggestion -->
New services or significant infrastructure changes should have corresponding monitoring (dashboards, alerts). Check that existing monitoring is not broken by the changes.

## OPS-10: YAML validity <!-- severity: blocker -->
All YAML files must be syntactically valid. Check for: incorrect indentation, missing colons, tabs instead of spaces, unquoted special characters. Kubernetes manifests should have correct `apiVersion`, `kind`, and required metadata.
