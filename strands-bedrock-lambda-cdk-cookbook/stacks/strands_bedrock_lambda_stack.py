from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class StrandsBedrockLambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        honeyhive_project = (
            self.node.try_get_context("honeyhive_project") or "nw-accelerator-demo"
        )
        honeyhive_server_url = self.node.try_get_context("honeyhive_server_url")
        honeyhive_secret_name = (
            self.node.try_get_context("honeyhive_secret_name") or "honeyhive/api-key"
        )
        model_arn = self.node.try_get_context("model_arn") or (
            f"arn:aws:bedrock:{self.region}:{self.account}"
            ":application-inference-profile/REPLACE_WITH_YOUR_PROFILE_ID"
        )
        litellm_base_url = self.node.try_get_context("litellm_base_url")

        honeyhive_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "HoneyHiveApiKey",
            secret_name=honeyhive_secret_name,
        )

        log_group = logs.LogGroup(
            self,
            "HandlerLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        environment = {
            "HONEYHIVE_PROJECT": honeyhive_project,
            "MODEL_ARN": model_arn,
        }
        if honeyhive_server_url:
            environment["HONEYHIVE_SERVER_URL"] = honeyhive_server_url
        if litellm_base_url:
            environment["LITELLM_BASE_URL"] = litellm_base_url

        handler_fn = lambda_.Function(
            self,
            "HandlerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.seconds(60),
            code=lambda_.Code.from_asset(
                "lambda",
                bundling=BundlingOptions(
                    # Docker-based bundling: CDK pulls the matching Lambda Python
                    # image, pip-installs requirements.txt into /asset-output, and
                    # copies the handler alongside. Without this, Code.from_asset
                    # would ship only the source files and Lambda would crash on
                    # import of honeyhive / strands-agents.
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output "
                        "&& cp -au . /asset-output",
                    ],
                ),
            ),
            handler="handler.handler",
            environment=environment,
            log_group=log_group,
        )

        # Secret injected via CloudFormation dynamic reference — never serialized as
        # plaintext into the synthesized template. CFN resolves at deploy-time.
        handler_fn.add_environment(
            "HONEYHIVE_API_KEY",
            SecretValue.secrets_manager(honeyhive_secret_name).unsafe_unwrap(),
        )
        honeyhive_secret.grant_read(handler_fn)

        # application-inference-profile/* is required for chargeback-tagged profiles
        # (e.g. Nationwide); foundation-model/* alone is insufficient.
        handler_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                resources=[
                    "arn:aws:bedrock:*:*:foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*",
                ],
            )
        )

        http_api = apigwv2.HttpApi(
            self,
            "HackathonHttpApi",
            api_name="strands-bedrock-hackathon",
        )
        http_api.add_routes(
            path="/invoke",
            methods=[apigwv2.HttpMethod.POST],
            integration=apigwv2_integrations.HttpLambdaIntegration(
                "HandlerIntegration",
                handler_fn,
            ),
        )

        CfnOutput(self, "ApiUrl", value=http_api.api_endpoint)
        CfnOutput(self, "LambdaArn", value=handler_fn.function_arn)
        CfnOutput(self, "RoleArn", value=handler_fn.role.role_arn)
