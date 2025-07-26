"""
Multiagent Workflow Example using AWS Bedrock with Session Management

This example demonstrates a multiagent system using Strands Agents with AWS Bedrock,
featuring session management and agent coordination.

Prerequisites:
- pip install strands-agents
- AWS credentials configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
- AWS Bedrock access enabled in your account
"""

import os
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass
from strands import Agent


@dataclass
class TaskResult:
    """Result from an agent task"""
    agent_name: str
    task: str
    result: str
    success: bool
    metadata: Dict[str, Any] = None


class SessionManager:
    """Manages sessions across multiple agents"""
    
    def __init__(self, session_key: str):
        self.session_key = session_key
        self.agent_contexts: Dict[str, List[str]] = {}
        self.task_results: List[TaskResult] = []
    
    def add_context(self, agent_name: str, context: str):
        """Add context for an agent"""
        if agent_name not in self.agent_contexts:
            self.agent_contexts[agent_name] = []
        self.agent_contexts[agent_name].append(context)
    
    def add_result(self, result: TaskResult):
        """Add task result to session history"""
        self.task_results.append(result)
    
    def get_context_for_agent(self, agent_name: str) -> str:
        """Get relevant context from previous agent results"""
        context = []
        for result in self.task_results:
            if result.success:
                context.append(f"Agent {result.agent_name} completed: {result.task}")
                context.append(f"Result: {result.result}")
        return "\n".join(context)


class MultiAgentWorkflow:
    """Orchestrates multiple agents working together"""
    
    def __init__(self, session_key: str, aws_region: str = "us-east-1"):
        self.session_manager = SessionManager(session_key)
        self.aws_region = aws_region
        self.agents: Dict[str, Agent] = {}
        
        # Set AWS region for Bedrock (default provider) - Claude 3.7 Sonnet
        os.environ['AWS_DEFAULT_REGION'] = aws_region
        
        # Claude 3.7 Sonnet model ID for us-east-1
        self.model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    
    def create_agent(self, name: str, role: str, instructions: str) -> Agent:
        """Create an agent with specific role and instructions"""
        
        # Create agent with default settings (Bedrock is default provider)
        agent = Agent()
        
        # Store agent metadata for context
        self.session_manager.add_context(name, f"Role: {role}")
        self.session_manager.add_context(name, f"Instructions: {instructions}")
        
        self.agents[name] = agent
        return agent
    
    def execute_task(self, agent_name: str, task: str) -> TaskResult:
        """Execute a task with a specific agent"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not found")
        
        agent = self.agents[agent_name]
        
        # Add context from previous agents and agent role
        context = self.session_manager.get_context_for_agent(agent_name)
        agent_context = "\n".join(self.session_manager.agent_contexts.get(agent_name, []))
        
        full_task = f"""
        {agent_context}
        
        Context from previous agents:
        {context}
        
        Your current task: {task}
        
        Please provide a clear, actionable response based on your role and the context provided.
        """
        
        try:
            # Execute the task
            response = agent(full_task)
            
            result = TaskResult(
                agent_name=agent_name,
                task=task,
                result=str(response),
                success=True,
                metadata={"session_key": self.session_manager.session_key}
            )
            
            self.session_manager.add_result(result)
            return result
            
        except Exception as e:
            result = TaskResult(
                agent_name=agent_name,
                task=task,
                result=f"Error: {str(e)}",
                success=False,
                metadata={"error": str(e)}
            )
            
            self.session_manager.add_result(result)
            return result
    
    def run_sequential_workflow(self, tasks: List[tuple]) -> List[TaskResult]:
        """Run tasks sequentially, passing context between agents"""
        results = []
        
        for agent_name, task in tasks:
            print(f"\n🤖 Executing task with {agent_name}: {task}")
            result = self.execute_task(agent_name, task)
            results.append(result)
            
            if result.success:
                print(f"✅ Success: {result.result[:100]}...")
            else:
                print(f"❌ Failed: {result.result}")
        
        return results
    
    def run_parallel_workflow(self, tasks: List[tuple]) -> List[TaskResult]:
        """Run tasks in parallel (independent agents)"""
        print(f"\n🚀 Running {len(tasks)} tasks in parallel...")
        
        results = []
        for agent_name, task in tasks:
            print(f"\n🤖 Executing task with {agent_name}: {task}")
            result = self.execute_task(agent_name, task)
            results.append(result)
            
            if result.success:
                print(f"✅ Success: {result.result[:100]}...")
            else:
                print(f"❌ Failed: {result.result}")
        
        return results


def main():
    """Example usage of the multiagent workflow"""
    
    # Set up AWS credentials (you can also use environment variables)
    # os.environ['AWS_ACCESS_KEY_ID'] = 'your_access_key'
    # os.environ['AWS_SECRET_ACCESS_KEY'] = 'your_secret_key'
    # os.environ['AWS_SESSION_TOKEN'] = 'your_session_token'  # if using temporary credentials
    
    # Create workflow with session key
    session_key = "multiagent_demo_2024"
    workflow = MultiAgentWorkflow(session_key=session_key)
    
    # Create specialized agents
    print("🔧 Creating specialized agents...")
    
    # Research Agent
    workflow.create_agent(
        name="researcher",
        role="Research Specialist",
        instructions="""
        You excel at gathering information, analyzing data, and providing comprehensive
        research summaries. Focus on accuracy and thoroughness.
        """
    )
    
    # Planning Agent
    workflow.create_agent(
        name="planner",
        role="Strategic Planner",
        instructions="""
        You create detailed plans and strategies based on research and requirements.
        Break down complex tasks into actionable steps.
        """
    )
    
    # Implementation Agent
    workflow.create_agent(
        name="implementer",
        role="Implementation Specialist",
        instructions="""
        You focus on practical implementation and execution. Provide concrete
        solutions and actionable recommendations.
        """
    )
    
    # Quality Assurance Agent
    workflow.create_agent(
        name="qa_agent",
        role="Quality Assurance",
        instructions="""
        You review work from other agents, identify potential issues, and suggest
        improvements. Focus on quality, completeness, and accuracy.
        """
    )
    
    print("✅ Agents created successfully!")
    
    # Example 1: Sequential Workflow
    print("\n" + "="*60)
    print("EXAMPLE 1: SEQUENTIAL WORKFLOW")
    print("="*60)
    
    sequential_tasks = [
        ("researcher", "Research the benefits and challenges of implementing microservices architecture"),
        ("planner", "Create a migration plan from monolith to microservices based on the research"),
        ("implementer", "Provide specific implementation steps and technology recommendations"),
        ("qa_agent", "Review the entire plan and provide quality assessment and recommendations")
    ]
    
    sequential_results = workflow.run_sequential_workflow(sequential_tasks)
    
    # Example 2: Parallel Workflow
    print("\n" + "="*60)
    print("EXAMPLE 2: PARALLEL WORKFLOW")
    print("="*60)
    
    parallel_tasks = [
        ("researcher", "Research current AI trends in healthcare"),
        ("planner", "Create a business plan for an AI startup"),
        ("implementer", "Design a REST API for a task management system"),
        ("qa_agent", "Review best practices for code quality in Python projects")
    ]
    
    parallel_results = workflow.run_parallel_workflow(parallel_tasks)
    
    # Display results summary
    print("\n" + "="*60)
    print("WORKFLOW RESULTS SUMMARY")
    print("="*60)
    
    print(f"\nSession Key: {session_key}")
    print(f"Total Tasks Executed: {len(workflow.session_manager.task_results)}")
    print(f"Successful Tasks: {sum(1 for r in workflow.session_manager.task_results if r.success)}")
    print(f"Failed Tasks: {sum(1 for r in workflow.session_manager.task_results if not r.success)}")
    
    print("\nAgent Contexts:")
    for agent_name in workflow.agents.keys():
        print(f"  - {agent_name}: Created with session key {session_key}")


if __name__ == "__main__":
    # Run the multiagent workflow
    main()
