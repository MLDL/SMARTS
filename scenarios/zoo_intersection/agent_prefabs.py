from smarts.zoo.registry import register
from smarts.core.agent_interface import AgentInterface, AgentType
from smarts.core.agent import AgentPolicy, AgentSpec


class Policy(AgentPolicy):
    def act(self, obs):
        return "keep_lane"


# You can register a callable that will build your AgentSpec
def demo_agent_callable(target_prefix=None, interface=None):
    if interface is None:
        interface = AgentInterface.from_type(AgentType.Laner)
    return AgentSpec(interface=interface, policy_builder=Policy)


register(
    locator="zoo-agent1-v0",
    entry_point="smarts.core.agent:AgentSpec",
    # Also works:
    # entry_point=smarts.core.agent.AgentSpec
    interface=AgentInterface.from_type(AgentType.Laner, max_episode_steps=20000),
)

register(
    locator="zoo-agent2-v0",
    entry_point=demo_agent_callable,
    # Also works:
    # entry_point="scenarios.zoo_intersection:demo_agent_callable",
)
