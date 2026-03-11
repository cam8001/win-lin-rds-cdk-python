# Infrastructure Deployment Plan

## Overview

Python CDK stack deploying a secure, private infrastructure environment in **ap-southeast-6** (Asia Pacific — New Zealand). The environment consists of Linux and Windows EC2 instances in a private subnet, an RDS SQL Server database in an isolated subnet, and supporting services.

## Decisions Log

| # | Decision | Detail |
|---|----------|--------|
| 1 | CDK Language | Python |
| 2 | Region | ap-southeast-6 (core infra) |
| 3 | VPC CIDR | 10.55.0.0/16 |
| 4 | NAT Gateway | Single (non-HA) |
| 5 | RDS Engine | SQL Server 2022 Standard, single node |
| 6 | Identity | IAM Identity Center, built-in directory, MFA required |
| 7 | Secure Browser | Deferred — only available in ap-southeast-2 (Sydney) |
| 8 | Location Service | Deferred — only available in ap-southeast-2 (Sydney) |
| 9 | Customer-facing | Yes — all code and docs kept fully generic |

## EC2 Instance Sizing

| Host | OS | Instance Type | vCPU | RAM | Storage | Notes |
|------|----|---------------|------|-----|---------|-------|
| Linux Large | Rocky Linux 9.6 | m7i.8xlarge | 32 | 128 GiB | 2 TB EBS | Kubernetes host (Docker 29.1.3, RKE2 v1.33.6-rke2r1) |
| Linux Small | Rocky Linux 9.6 | c7i.xlarge | 4 | 8 GiB | 400 GB EBS | General purpose |
| Windows 1 | Windows Server 2022 | c7i.2xlarge | 8 | 16 GiB | 120 GB EBS | |
| Windows 2 | Windows Server 2022 | c7i.2xlarge | 8 | 16 GiB | 120 GB EBS | |

## RDS Sizing

| Engine | Edition | Instance Type | vCPU | RAM | Notes |
|--------|---------|---------------|------|-----|-------|
| SQL Server 2022 | Standard | db.m6i.xlarge | 4 | 16 GiB | Single node, isolated subnet |

---

## Phased Build Plan

### Phase 1 — VPC & Network Foundation

- [ ] VPC (10.55.0.0/16)
- [ ] Private subnet (EC2 workloads)
- [ ] Isolated subnet (RDS — no internet route)
- [ ] Public subnet (NAT Gateway)
- [ ] Single NAT Gateway
- [ ] VPC Endpoints: SSM, SSM Messages, EC2 Messages, S3 (Gateway), CloudWatch Logs
- [ ] Security groups:
  - EC2 instances (inter-host communication, SSM)
  - RDS (SQL Server port 1433, from EC2 SG only)

### Phase 2 — EC2 Compute

- [ ] Rocky Linux 9.6 large instance (m7i.8xlarge, 2 TB EBS)
- [ ] Rocky Linux 9.6 small instance (c7i.xlarge, 400 GB EBS)
- [ ] Windows Server 2022 × 2 (c7i.2xlarge, 120 GB EBS each)
- [ ] IAM instance role with SSM and S3 access
- [ ] S3 bucket for file drops (EC2 read/write access)

### Phase 3 — RDS SQL Server

- [ ] RDS SQL Server 2022 Standard (db.m6i.xlarge)
- [ ] Single node in isolated subnet
- [ ] DB subnet group
- [ ] Security group (port 1433 from EC2 SG)

### Phase 4 — Systems Manager

- [ ] Session Manager configuration
- [ ] Patch baselines (Windows + Linux)
- [ ] Maintenance windows

### Phase 5 — IAM Identity Center

- [ ] Enable IAM Identity Center (built-in directory)
- [ ] MFA required for all sign-ins
- [ ] Permission sets for infrastructure access

### Phase 6 — Deferred (ap-southeast-2 only)

- [ ] WorkSpaces Secure Browser (ENI into VPC)
- [ ] Amazon Location Service

> **Note:** Both Secure Browser and Location Service are only available in ap-southeast-2 (Sydney) as of March 2026. These will require either a separate stack in Sydney or cross-region networking.

---

## Future Considerations

- **Self-service sign-up:** If self-registration is needed in future, migrate identity to Amazon Cognito with a pre-sign-up Lambda trigger to restrict email domains (e.g., allow only `mil.nz` and approved partner domains).
- **Rocky Linux AMIs:** Official Rocky Linux Foundation AMIs (owner `792107900819`) are not published in ap-southeast-6 as of March 2026. Currently using RHEL 9.6 (binary-compatible). To switch to Rocky, either copy the official AMI from ap-southeast-2 or use a Marketplace reseller image in ap-southeast-6.
- **EC2 Messages VPC Endpoint:** The `ec2messages` VPC endpoint is not available in ap-southeast-6 as of March 2026. SSM RunCommand/SendCommand traffic routes via the NAT Gateway instead. SSM Session Manager is unaffected (uses `ssm` + `ssmmessages` endpoints which are available).
- **NAT Gateway HA:** Currently single NAT GW. For production resilience, consider one per AZ.
- **Secure Browser cross-region:** Will need VPC peering or Transit Gateway between ap-southeast-6 and ap-southeast-2 for the Secure Browser ENI.
