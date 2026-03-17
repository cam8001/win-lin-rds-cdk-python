from aws_cdk import (
    CfnOutput,
    Stack,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    aws_s3 as s3,
    aws_ssm as ssm,
)
from constructs import Construct


class PrivateWindowsLinuxSQLStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------
        # VPC
        # -----------------------------------------------------------
        vpc = ec2.Vpc(self, "Vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.55.0.0/16"),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                # Public subnet - hosts the NAT Gateway
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                # Private subnet - EC2 workloads, outbound via NAT
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20,
                ),
                # Isolated subnet - RDS, no internet route
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # -----------------------------------------------------------
        # VPC Endpoints - allow private subnet access to AWS services
        # -----------------------------------------------------------

        # Gateway endpoint for S3 (free, no ENI needed)
        vpc.add_gateway_endpoint("S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # Interface endpoints for Systems Manager and CloudWatch
        for svc_name, svc in [
            ("Ssm", ec2.InterfaceVpcEndpointAwsService.SSM),
            ("SsmMessages", ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES),
            ("CwLogs", ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS),
        ]:
            vpc.add_interface_endpoint(svc_name,
                service=svc,
                subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
            )

        # -----------------------------------------------------------
        # Security Groups
        # -----------------------------------------------------------

        # EC2 security group - allows inter-host communication
        ec2_sg = ec2.SecurityGroup(self, "Ec2Sg",
            vpc=vpc,
            description="EC2 instances - inter-host and SSM access",
            allow_all_outbound=True,
        )
        ec2_sg.add_ingress_rule(
            peer=ec2_sg,
            connection=ec2.Port.all_traffic(),
            description="Allow all traffic between EC2 instances",
        )

        # RDS security group - SQL Server from EC2 only
        rds_sg = ec2.SecurityGroup(self, "RdsSg",
            vpc=vpc,
            description="RDS SQL Server - access from EC2 only",
            allow_all_outbound=False,
        )
        rds_sg.add_ingress_rule(
            peer=ec2_sg,
            connection=ec2.Port.tcp(1433),
            description="SQL Server from EC2 instances",
        )

        # -----------------------------------------------------------
        # IAM Role for EC2 - SSM + S3 access
        # -----------------------------------------------------------
        instance_role = iam.Role(self, "Ec2InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="EC2 instance role - SSM managed instance and S3 file drop access",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # -----------------------------------------------------------
        # S3 File Drop Bucket
        # -----------------------------------------------------------
        file_drop_bucket = s3.Bucket(self, "FileDropBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Grant EC2 role read/write to the bucket
        file_drop_bucket.grant_read_write(instance_role)

        # -----------------------------------------------------------
        # Machine Images
        # Note: AMI lookups require valid AWS credentials at synth
        # time. Once resolved, the AMI IDs are cached in
        # cdk.context.json and credentials are no longer needed.
        # -----------------------------------------------------------

        # RHEL 9.6 - official Red Hat AMIs (owner 309956199498)
        # Note: Rocky Linux 9.6 official AMIs are not published in
        # ap-southeast-6. Using RHEL 9.6 (binary-compatible). If
        # Rocky is required, copy the official AMI from ap-southeast-2
        # (owner 792107900819) or use a Marketplace reseller image.
        rhel_ami = ec2.MachineImage.lookup(
            name="RHEL-9.6*_HVM-*-x86_64-*",
            owners=["309956199498"],
        )

        # Windows Server 2022
        windows_ami = ec2.MachineImage.latest_windows(
            ec2.WindowsVersion.WINDOWS_SERVER_2022_ENGLISH_FULL_BASE,
        )

        # -----------------------------------------------------------
        # EC2 Instances
        # -----------------------------------------------------------

        private_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        )

        # RHEL 9.6 - Large (Kubernetes / RKE2 host)
        # m7i.8xlarge: 32 vCPU, 128 GiB RAM
        linux_large = ec2.Instance(self, "LinuxLarge",
            instance_type=ec2.InstanceType("m7i.8xlarge"),
            machine_image=rhel_ami,
            vpc=vpc,
            vpc_subnets=private_subnets,
            security_group=ec2_sg,
            role=instance_role,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=2048,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                    ),
                ),
            ],
        )

        # RHEL 9.6 - Small
        # c7i.xlarge: 4 vCPU, 8 GiB RAM
        linux_small = ec2.Instance(self, "LinuxSmall",
            instance_type=ec2.InstanceType("c7i.xlarge"),
            machine_image=rhel_ami,
            vpc=vpc,
            vpc_subnets=private_subnets,
            security_group=ec2_sg,
            role=instance_role,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=400,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                    ),
                ),
            ],
        )

        # Windows Server 2022 - Instance 1
        # c7i.2xlarge: 8 vCPU, 16 GiB RAM
        windows_1 = ec2.Instance(self, "Windows1",
            instance_type=ec2.InstanceType("c7i.2xlarge"),
            machine_image=windows_ami,
            vpc=vpc,
            vpc_subnets=private_subnets,
            security_group=ec2_sg,
            role=instance_role,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=120,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                    ),
                ),
            ],
        )

        # Windows Server 2022 - Instance 2
        # c7i.2xlarge: 8 vCPU, 16 GiB RAM
        windows_2 = ec2.Instance(self, "Windows2",
            instance_type=ec2.InstanceType("c7i.2xlarge"),
            machine_image=windows_ami,
            vpc=vpc,
            vpc_subnets=private_subnets,
            security_group=ec2_sg,
            role=instance_role,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=120,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                    ),
                ),
            ],
        )

        # -----------------------------------------------------------
        # RDS - SQL Server 2022 Standard (single node, isolated subnet)
        # db.m6i.xlarge: 4 vCPU, 16 GiB RAM
        # -----------------------------------------------------------
        sql_server = rds.DatabaseInstance(self, "SqlServer",
            engine=rds.DatabaseInstanceEngine.sql_server_se(
                version=rds.SqlServerEngineVersion.VER_16,
            ),
            instance_type=ec2.InstanceType("m6i.xlarge"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            ),
            security_groups=[rds_sg],
            multi_az=False,
            storage_encrypted=True,
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
            credentials=rds.Credentials.from_generated_secret(
                "admin",
                secret_name="rds-sql-server-credentials",
            ),
        )

        # -----------------------------------------------------------
        # Systems Manager - Patch Baselines
        # -----------------------------------------------------------

        # Linux (RHEL) - Critical and Important security patches,
        # auto-approve after 7 days
        linux_baseline = ssm.CfnPatchBaseline(self, "LinuxPatchBaseline",
            name="LinuxPatchBaseline",
            operating_system="REDHAT_ENTERPRISE_LINUX",
            description="RHEL 9 - Critical and Important security patches",
            patch_groups=["Linux"],
            approval_rules=ssm.CfnPatchBaseline.RuleGroupProperty(
                patch_rules=[
                    ssm.CfnPatchBaseline.RuleProperty(
                        approve_after_days=7,
                        compliance_level="CRITICAL",
                        patch_filter_group=ssm.CfnPatchBaseline.PatchFilterGroupProperty(
                            patch_filters=[
                                ssm.CfnPatchBaseline.PatchFilterProperty(
                                    key="CLASSIFICATION",
                                    values=["Security"],
                                ),
                                ssm.CfnPatchBaseline.PatchFilterProperty(
                                    key="SEVERITY",
                                    values=["Critical", "Important"],
                                ),
                            ]
                        ),
                    )
                ]
            ),
        )

        # Windows - Critical and Important security patches,
        # auto-approve after 7 days
        windows_baseline = ssm.CfnPatchBaseline(self, "WindowsPatchBaseline",
            name="WindowsPatchBaseline",
            operating_system="WINDOWS",
            description="Windows Server 2022 - Critical and Important security patches",
            patch_groups=["Windows"],
            approval_rules=ssm.CfnPatchBaseline.RuleGroupProperty(
                patch_rules=[
                    ssm.CfnPatchBaseline.RuleProperty(
                        approve_after_days=7,
                        compliance_level="CRITICAL",
                        patch_filter_group=ssm.CfnPatchBaseline.PatchFilterGroupProperty(
                            patch_filters=[
                                ssm.CfnPatchBaseline.PatchFilterProperty(
                                    key="CLASSIFICATION",
                                    values=["SecurityUpdates", "CriticalUpdates"],
                                ),
                                ssm.CfnPatchBaseline.PatchFilterProperty(
                                    key="MSRC_SEVERITY",
                                    values=["Critical", "Important"],
                                ),
                            ]
                        ),
                    )
                ]
            ),
        )

        # -----------------------------------------------------------
        # Systems Manager - Maintenance Window
        # Weekly Sunday 02:00 NZST (13:00 UTC Saturday), 4h window,
        # 1h cutoff
        # -----------------------------------------------------------
        maintenance_window = ssm.CfnMaintenanceWindow(self, "PatchMaintenanceWindow",
            name="WeeklyPatchWindow",
            description="Weekly patching - Sunday 02:00 NZST",
            schedule="cron(0 13 ? * SAT *)",
            schedule_timezone="Pacific/Auckland",
            duration=4,
            cutoff=1,
            allow_unassociated_targets=False,
        )

        # Target: all instances tagged with Patch=Linux
        linux_target = ssm.CfnMaintenanceWindowTarget(self, "LinuxPatchTarget",
            window_id=maintenance_window.ref,
            resource_type="INSTANCE",
            targets=[ssm.CfnMaintenanceWindowTarget.TargetsProperty(
                key="tag:Patch",
                values=["Linux"],
            )],
            name="LinuxInstances",
        )

        # Target: all instances tagged with Patch=Windows
        windows_target = ssm.CfnMaintenanceWindowTarget(self, "WindowsPatchTarget",
            window_id=maintenance_window.ref,
            resource_type="INSTANCE",
            targets=[ssm.CfnMaintenanceWindowTarget.TargetsProperty(
                key="tag:Patch",
                values=["Windows"],
            )],
            name="WindowsInstances",
        )

        # Task: run AWS-RunPatchBaseline on Linux instances
        ssm.CfnMaintenanceWindowTask(self, "LinuxPatchTask",
            window_id=maintenance_window.ref,
            task_arn="AWS-RunPatchBaseline",
            task_type="RUN_COMMAND",
            priority=1,
            max_concurrency="1",
            max_errors="1",
            name="PatchLinuxInstances",
            targets=[ssm.CfnMaintenanceWindowTask.TargetProperty(
                key="WindowTargetIds",
                values=[linux_target.ref],
            )],
            task_invocation_parameters=ssm.CfnMaintenanceWindowTask.TaskInvocationParametersProperty(
                maintenance_window_run_command_parameters=ssm.CfnMaintenanceWindowTask.MaintenanceWindowRunCommandParametersProperty(
                    parameters={"Operation": ["Install"]},
                )
            ),
        )

        # Task: run AWS-RunPatchBaseline on Windows instances
        ssm.CfnMaintenanceWindowTask(self, "WindowsPatchTask",
            window_id=maintenance_window.ref,
            task_arn="AWS-RunPatchBaseline",
            task_type="RUN_COMMAND",
            priority=1,
            max_concurrency="1",
            max_errors="1",
            name="PatchWindowsInstances",
            targets=[ssm.CfnMaintenanceWindowTask.TargetProperty(
                key="WindowTargetIds",
                values=[windows_target.ref],
            )],
            task_invocation_parameters=ssm.CfnMaintenanceWindowTask.TaskInvocationParametersProperty(
                maintenance_window_run_command_parameters=ssm.CfnMaintenanceWindowTask.MaintenanceWindowRunCommandParametersProperty(
                    parameters={"Operation": ["Install"]},
                )
            ),
        )

        # Tag EC2 instances for patch group targeting
        for instance in [linux_large, linux_small]:
            instance.instance.add_property_override(
                "Tags",
                [{"Key": "Patch", "Value": "Linux"}],
            )
        for instance in [windows_1, windows_2]:
            instance.instance.add_property_override(
                "Tags",
                [{"Key": "Patch", "Value": "Windows"}],
            )

        # -----------------------------------------------------------
        # IAM Identity Center — deployed as a separate stack (IdentityCenterStack)
        # See infra/identity_center_stack.py
        # -----------------------------------------------------------

        # -----------------------------------------------------------
        # CloudFormation Outputs
        # -----------------------------------------------------------
        instances = {
            "LinuxLarge": linux_large,
            "LinuxSmall": linux_small,
            "Windows1": windows_1,
            "Windows2": windows_2,
        }

        for name, instance in instances.items():
            CfnOutput(self, f"{name}InstanceId",
                value=instance.instance_id,
                description=f"{name} - Instance ID",
            )
            CfnOutput(self, f"{name}PrivateIp",
                value=instance.instance_private_ip,
                description=f"{name} - Private IP",
            )

        CfnOutput(self, "SqlServerEndpoint",
            value=sql_server.db_instance_endpoint_address,
            description="RDS SQL Server - Endpoint",
        )
        CfnOutput(self, "FileDropBucketName",
            value=file_drop_bucket.bucket_name,
            description="S3 File Drop Bucket",
        )
