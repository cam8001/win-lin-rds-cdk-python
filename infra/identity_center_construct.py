from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Fn,
    aws_sso as sso,
)
from constructs import Construct


class IdentityCenterConstruct(Construct):
    """
    IAM Identity Center permission sets using an existing IIC instance.

    The instance ARN must be passed in as a CloudFormation parameter at deploy time:
      npx cdk deploy IdentityCenterStack --parameters IdentityCenterStack:InstanceArn=<arn>

    To find your instance ARN:
      aws sso-admin list-instances --region ap-southeast-6

    Permission sets created:
      - InfrastructureAdmin  : AdministratorAccess (full infra access)
      - InfrastructureViewer : ReadOnlyAccess      (read-only)

    NOTE: MFA enforcement cannot be configured via CloudFormation/CDK.
    After deployment, enable MFA in the IAM Identity Center console:
      Settings → Authentication → MFA → Require MFA for all sign-ins
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        instance_arn_param = CfnParameter(self, "InstanceArn",
            type="String",
            description="Existing IAM Identity Center instance ARN (from: aws sso-admin list-instances --region ap-southeast-6)",
        )

        instance_arn = instance_arn_param.value_as_string

        # Permission set: full infrastructure admin access, 8h session
        admin_ps = sso.CfnPermissionSet(self, "AdminPermissionSet",
            instance_arn=instance_arn,
            name="InfrastructureAdmin",
            description="Full administrative access to infrastructure resources",
            managed_policies=[
                "arn:aws:iam::aws:policy/AdministratorAccess",
            ],
            session_duration="PT8H",
        )

        # Permission set: read-only access, 8h session
        viewer_ps = sso.CfnPermissionSet(self, "ViewerPermissionSet",
            instance_arn=instance_arn,
            name="InfrastructureViewer",
            description="Read-only access to infrastructure resources",
            managed_policies=[
                "arn:aws:iam::aws:policy/ReadOnlyAccess",
            ],
            session_duration="PT8H",
        )

        # Derive portal URL from instance ARN.
        # ARN format: arn:aws:sso:::instance/ssoins-<id>
        # Portal URL:  https://ssoins-<id>.awsapps.com/start
        instance_id = Fn.select(1, Fn.split("/", instance_arn))
        portal_url = Fn.join("", [
            "https://", instance_id, ".awsapps.com/start"
        ])

        CfnOutput(self, "IdentityCenterInstanceArn",
            value=instance_arn,
            description="IAM Identity Center - Instance ARN",
        )
        CfnOutput(self, "IdentityCenterAccessPortalUrl",
            value=portal_url,
            description="IAM Identity Center - Access portal URL (share with users to sign in)",
        )
        CfnOutput(self, "AdminPermissionSetArn",
            value=admin_ps.attr_permission_set_arn,
            description="IAM Identity Center - InfrastructureAdmin permission set ARN",
        )
        CfnOutput(self, "ViewerPermissionSetArn",
            value=viewer_ps.attr_permission_set_arn,
            description="IAM Identity Center - InfrastructureViewer permission set ARN",
        )
