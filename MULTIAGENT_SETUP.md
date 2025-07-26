# Multiagent AWS Bedrock Example Setup Guide

This guide helps you set up and run the multiagent workflow example using Strands Agents with AWS Bedrock.

## Prerequisites

1. **Python 3.10 or higher**
2. **AWS Account with Bedrock access**
3. **AWS credentials configured**

## Installation

1. Install required dependencies:
```bash
pip install -r requirements_multiagent.txt
```

2. Ensure AWS Bedrock access is enabled in your AWS account for Claude models.

## AWS Configuration

### Option 1: Environment Variables
Set your AWS credentials as environment variables:

```bash
export AWS_ACCESS_KEY_ID="your_access_key_id"
export AWS_SECRET_ACCESS_KEY="your_secret_access_key"
export AWS_SESSION_TOKEN="your_session_token"  # Only if using temporary credentials
export AWS_DEFAULT_REGION="us-west-2"
```

### Option 2: AWS CLI Configuration
Configure using AWS CLI:
```bash
aws configure
```

### Option 3: IAM Roles (Recommended for EC2/ECS)
If running on AWS infrastructure, use IAM roles instead of hardcoded credentials.

## Required AWS Permissions

Your AWS credentials need the following permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
            ]
        }
    ]
}
```

## Running the Example

1. **Basic execution:**
```bash
python multiagent_bedrock_example.py
```

2. **With custom session key:**
Modify the `session_key` variable in the script or set it as an environment variable:
```bash
export MULTIAGENT_SESSION_KEY="your_custom_session_key"
python multiagent_bedrock_example.py
```

## Example Features

### 1. Sequential Workflow
- Agents work in sequence, passing context between each other
- Each agent builds upon the previous agent's work
- Demonstrates: Research → Planning → Implementation → Quality Assurance

### 2. Parallel Workflow  
- Multiple agents work independently on different tasks
- Faster execution for unrelated tasks
- Demonstrates concurrent agent execution

### 3. Session Management
- Each agent maintains its own session with the session key
- Context is shared between agents in sequential workflows
- Results are tracked and can be accessed across the workflow

## Agent Roles

1. **Researcher**: Gathers information and provides comprehensive analysis
2. **Planner**: Creates strategic plans based on research and requirements
3. **Implementer**: Focuses on practical implementation and solutions
4. **QA Agent**: Reviews work and provides quality assessments

## Customization

### Adding New Agents
```python
workflow.create_agent(
    name="your_agent_name",
    role="Your Agent Role",
    instructions="Detailed instructions for your agent..."
)
```

### Changing Models
Modify the `model_id` in the `BedrockModelProvider`:
```python
self.model_provider = BedrockModelProvider(
    region_name=aws_region,
    model_id="anthropic.claude-3-haiku-20240307-v1:0"  # Different model
)
```

### Custom Tasks
Add your own tasks to the workflow:
```python
custom_tasks = [
    ("agent_name", "Your custom task description"),
    # Add more tasks...
]

results = await workflow.run_sequential_workflow(custom_tasks)
```

## Troubleshooting

### Common Issues

1. **AWS Credentials Error**
   - Ensure AWS credentials are properly configured
   - Check that your credentials have Bedrock permissions

2. **Model Access Error**
   - Verify Bedrock access is enabled in your AWS account
   - Check that the specific model is available in your region

3. **Session Errors**
   - Ensure session keys are unique and valid
   - Check that sessions are properly initialized

### Debug Mode
Add logging to debug issues:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Best Practices

1. **Never hardcode AWS credentials** in your code
2. **Use IAM roles** when running on AWS infrastructure
3. **Rotate credentials** regularly
4. **Use least privilege** principle for IAM permissions
5. **Monitor usage** through AWS CloudTrail

## Cost Considerations

- AWS Bedrock charges per token processed
- Monitor your usage through AWS Cost Explorer
- Consider using smaller models (like Claude Haiku) for development
- Implement rate limiting for production use

## Next Steps

1. Explore the Strands Agents documentation for advanced features
2. Implement custom tools for your agents
3. Add error handling and retry logic for production use
4. Consider implementing agent memory persistence
5. Explore other multiagent patterns like swarm or graph-based workflows
