#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.strands_bedrock_lambda_stack import StrandsBedrockLambdaStack


app = cdk.App()
StrandsBedrockLambdaStack(
    app,
    "StrandsBedrockLambdaStack",
)

app.synth()
