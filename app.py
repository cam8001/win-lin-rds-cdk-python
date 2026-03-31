#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.infra_stack import PrivateWindowsLinuxSQLStack
from infra.identity_center_stack import IdentityCenterStack
from infra.secure_browser_stack import SecureBrowserStack

app = cdk.App()

env_nz = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region="ap-southeast-6",
)

PrivateWindowsLinuxSQLStack(app, "PrivateWindowsLinuxSQLStack", env=env_nz)

# IAM Identity Center — separate stack, cannot deploy from org management account
# See README for details
env_sydney = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region="ap-southeast-2",
)
IdentityCenterStack(app, "IdentityCenterStack", env=env_sydney)

# WorkSpaces Secure Browser — only available in ap-southeast-2 (Sydney)
SecureBrowserStack(app, "SecureBrowserStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region="ap-southeast-2",
    ),
)

app.synth()
