from aws_cdk import Stack
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
      npx cdk deploy IdentityCenterStack
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        IdentityCenterConstruct(self, "IdentityCenter")
