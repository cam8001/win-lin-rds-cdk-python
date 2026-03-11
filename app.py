#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.infra_stack import PrivateWindowsLinuxSQLStack

app = cdk.App()

PrivateWindowsLinuxSQLStack(app, "PrivateWindowsLinuxSQLStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region="ap-southeast-6",
    ),
)

app.synth()
