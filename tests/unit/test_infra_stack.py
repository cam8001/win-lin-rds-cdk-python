import aws_cdk as cdk
from aws_cdk import assertions
from infra.infra_stack import PrivateWindowsLinuxSQLStack


def test_vpc_created():
    app = cdk.App()
    stack = PrivateWindowsLinuxSQLStack(app, "TestStack",
        env=cdk.Environment(account="123456789012", region="ap-southeast-6"),
    )
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::EC2::VPC", 1)
