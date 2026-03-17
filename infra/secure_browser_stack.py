from aws_cdk import Stack
from constructs import Construct
from infra.secure_browser_construct import SecureBrowserConstruct


class SecureBrowserStack(Stack):
    """
    WorkSpaces Secure Browser stack — deployed in ap-southeast-2 (Sydney).
    Secure Browser is not available in ap-southeast-6 (New Zealand).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        SecureBrowserConstruct(self, "SecureBrowser")
