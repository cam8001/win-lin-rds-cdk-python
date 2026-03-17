from aws_cdk import (
    CfnOutput,
    aws_ec2 as ec2,
    aws_workspacesweb as workspacesweb,
)
from constructs import Construct


class SecureBrowserConstruct(Construct):
    """
    WorkSpaces Secure Browser portal in ap-southeast-2 (Sydney).

    Deploys a minimal VPC with two private subnets (required by WorkSpaces Web),
    a dedicated security group, and a portal using IAM Identity Center auth.

    The portal ENI is created by the WorkSpaces Web service inside the provided
    subnets — no VPC peering to ap-southeast-6 is required for browser sessions.
    Users access the portal via the public portal URL provided in the stack output.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Minimal VPC for Secure Browser streaming instances.
        # WorkSpaces Web requires at least 2 subnets in different AZs.
        # No NAT Gateway needed — streaming instances don't require internet egress
        # through this VPC (WorkSpaces Web manages that internally).
        vpc = ec2.Vpc(self, "Vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.56.0.0/16"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # Security group for WorkSpaces Web streaming instances
        sg = ec2.SecurityGroup(self, "SecureBrowserSg",
            vpc=vpc,
            description="WorkSpaces Secure Browser - streaming instances",
            allow_all_outbound=True,
        )

        # Network settings — links the portal to our VPC/subnets
        network_settings = workspacesweb.CfnNetworkSettings(self, "NetworkSettings",
            vpc_id=vpc.vpc_id,
            subnet_ids=vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            ).subnet_ids,
            security_group_ids=[sg.security_group_id],
        )

        # Portal — Standard auth type. IAM Identity Center auth requires an IIC
        # instance in the same region as the portal (ap-southeast-2), but our IIC
        # instance is in ap-southeast-6. To use IIC auth, replicate the IIC instance
        # to ap-southeast-2 via the IAM Identity Center console first.
        # With Standard auth, configure a SAML identity provider post-deployment.
        portal = workspacesweb.CfnPortal(self, "Portal",
            display_name="Private Infrastructure Portal",
            authentication_type="Standard",
            network_settings_arn=network_settings.attr_network_settings_arn,
        )

        CfnOutput(self, "SecureBrowserPortalUrl",
            value=portal.attr_portal_endpoint,
            description="WorkSpaces Secure Browser - portal URL",
        )
        CfnOutput(self, "SecureBrowserPortalArn",
            value=portal.attr_portal_arn,
            description="WorkSpaces Secure Browser - portal ARN",
        )
