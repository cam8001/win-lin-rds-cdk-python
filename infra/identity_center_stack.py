from aws_cdk import CfnParameter, Stack
from constructs import Construct
from infra.identity_center_construct import IdentityCenterConstruct


class IdentityCenterStack(Stack):
    """
    IAM Identity Center stack — deploy separately from the main infra stack.

    IMPORTANT: This stack cannot be deployed from an AWS Organizations management
    account. If this account is an org management account, either:
      1. Deploy from a delegated administrator account, or
      2. Skip this stack and configure IAM Identity Center manually in the console.

    Deploy with:
      npx cdk deploy IdentityCenterStack --parameters InstanceArn=<arn>
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        instance_arn_param = CfnParameter(self, "InstanceArn",
            type="String",
            description="Existing IAM Identity Center instance ARN (from: aws sso-admin list-instances --region ap-southeast-2)",
        )

        IdentityCenterConstruct(self, "IdentityCenter",
            instance_arn=instance_arn_param.value_as_string,
        )
