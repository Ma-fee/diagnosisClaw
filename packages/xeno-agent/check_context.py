import inspect

from agentpool.agents.context import AgentContext

print("Methods of AgentContext:")
for name, _ in inspect.getmembers(AgentContext, predicate=inspect.isfunction):
    print(name)

print("\nAttributes of AgentContext:")
for name, _ in inspect.getmembers(AgentContext):
    if not name.startswith("__"):
        print(name)
