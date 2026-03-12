"""
Hierarchical orchestration pattern.

Manager agent delegates to worker agents, then synthesizes results.
"""

from __future__ import annotations

from ..agent import Agent
from ..context import Context
from ..message import Message, MessageRole
from .base import Pattern, PatternConfig, PatternResult, register_pattern


@register_pattern("hierarchical")
class HierarchicalPattern(Pattern):
    """
    Hierarchical: Manager → Workers → Manager

    A manager agent analyzes the task, delegates subtasks to
    specialized worker agents, then synthesizes their outputs.

    Use when:
    - Tasks can be decomposed into subtasks
    - Different workers have different specializations
    - You need intelligent task routing
    - The manager can coordinate better than a fixed pipeline

    Example: Research task
      Manager: "I need info on X, Y, Z"
      → Worker 1 handles X
      → Worker 2 handles Y
      → Worker 3 handles Z
      Manager: Synthesizes into coherent answer

    The manager decides which workers to use based on the task.
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        max_delegations: int = 5,
    ):
        super().__init__(config)
        self.max_delegations = max_delegations

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        """
        Execute hierarchical pattern.

        First agent is the manager, rest are workers.
        """
        if len(agents) < 2:
            return PatternResult(
                output=Message(
                    content="Hierarchical requires at least 2 agents: manager + workers",
                    role=MessageRole.AGENT,
                ),
                success=False,
                error="Insufficient agents",
            )

        manager = agents[0]
        workers = {agent.name: agent for agent in agents[1:]}
        intermediate_outputs: list[Message] = []

        # Step 1: Manager analyzes task and creates delegation plan
        worker_descriptions = "\n".join([
            f"- {name}: {agent.description}"
            for name, agent in workers.items()
        ])

        planning_prompt = Message(
            content=f"Task: {input_message.content}\n\n"
                    f"Available workers:\n{worker_descriptions}\n\n"
                    "Create a delegation plan. For each subtask, specify:\n"
                    "DELEGATE: <worker_name>\n"
                    "SUBTASK: <what they should do>\n\n"
                    "You can delegate to multiple workers. "
                    "Only use workers from the list above.",
            role=MessageRole.USER,
        )

        plan = await manager(planning_prompt, context)
        intermediate_outputs.append(plan)

        # Step 2: Parse delegations and execute
        delegations = self._parse_delegations(plan.content, workers)
        worker_results: list[dict] = []

        for delegation in delegations[:self.max_delegations]:
            worker_name = delegation["worker"]
            subtask = delegation["subtask"]

            if worker_name not in workers:
                continue

            worker = workers[worker_name]
            worker_prompt = Message(
                content=f"Task: {subtask}\n\n"
                        f"Context from original request: {input_message.content}",
                role=MessageRole.USER,
            )

            try:
                result = await worker(worker_prompt, context)
                intermediate_outputs.append(result)
                worker_results.append({
                    "worker": worker_name,
                    "subtask": subtask,
                    "result": result.content,
                })
            except Exception as e:
                worker_results.append({
                    "worker": worker_name,
                    "subtask": subtask,
                    "result": f"Error: {str(e)}",
                })

        # Step 3: Manager synthesizes results
        results_text = "\n\n".join([
            f"### {r['worker']}\n**Subtask:** {r['subtask']}\n**Result:** {r['result']}"
            for r in worker_results
        ])

        synthesis_prompt = Message(
            content=f"Original task: {input_message.content}\n\n"
                    f"Worker results:\n{results_text}\n\n"
                    "Synthesize these results into a coherent final answer. "
                    "Ensure all aspects of the original task are addressed.",
            role=MessageRole.USER,
        )

        final_output = await manager(synthesis_prompt, context)
        intermediate_outputs.append(final_output)

        return PatternResult(
            output=final_output,
            intermediate_outputs=intermediate_outputs,
            iterations=len(delegations) + 2,  # plan + workers + synthesis
            success=True,
        )

    def _parse_delegations(
        self, plan_text: str, available_workers: dict
    ) -> list[dict]:
        """Parse delegation instructions from manager's plan."""
        import re

        delegations = []
        lines = plan_text.split('\n')

        current_worker = None
        current_subtask = None

        for line in lines:
            line = line.strip()

            # Match DELEGATE: worker_name
            delegate_match = re.match(r'DELEGATE:\s*(\w+)', line, re.IGNORECASE)
            if delegate_match:
                # Save previous delegation if complete
                if current_worker and current_subtask:
                    delegations.append({
                        "worker": current_worker,
                        "subtask": current_subtask,
                    })
                current_worker = delegate_match.group(1)
                current_subtask = None
                continue

            # Match SUBTASK: description
            subtask_match = re.match(r'SUBTASK:\s*(.+)', line, re.IGNORECASE)
            if subtask_match:
                current_subtask = subtask_match.group(1)
                continue

        # Don't forget last delegation
        if current_worker and current_subtask:
            delegations.append({
                "worker": current_worker,
                "subtask": current_subtask,
            })

        return delegations


@register_pattern("map_reduce")
class MapReducePattern(Pattern):
    """
    Map-Reduce: distribute work, then aggregate.

    All workers process the same input (map phase),
    then a reducer combines the results.

    Simpler than hierarchical - no dynamic delegation.
    All workers always run.

    Use when:
    - You want the same task processed by different specialists
    - Results need to be aggregated, not routed
    """

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if len(agents) < 2:
            return PatternResult(
                output=input_message,
                success=False,
                error="MapReduce requires at least 2 agents: workers + reducer",
            )

        workers = agents[:-1]
        reducer = agents[-1]
        intermediate_outputs: list[Message] = []

        # Map phase: all workers process input
        import asyncio
        tasks = [worker(input_message, context.fork()) for worker in workers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        worker_outputs = []
        for worker, result in zip(workers, results):
            if isinstance(result, Exception):
                worker_outputs.append({
                    "worker": worker.name,
                    "result": f"Error: {str(result)}",
                })
            else:
                intermediate_outputs.append(result)
                worker_outputs.append({
                    "worker": worker.name,
                    "result": result.content,
                })

        # Reduce phase: combine results
        outputs_text = "\n\n---\n\n".join([
            f"**{o['worker']}:**\n{o['result']}"
            for o in worker_outputs
        ])

        reduce_prompt = Message(
            content=f"Original input: {input_message.content}\n\n"
                    f"Results from workers:\n{outputs_text}\n\n"
                    "Combine these results into a single coherent output.",
            role=MessageRole.USER,
        )

        final_output = await reducer(reduce_prompt, context)
        intermediate_outputs.append(final_output)

        return PatternResult(
            output=final_output,
            intermediate_outputs=intermediate_outputs,
            iterations=len(workers) + 1,
            success=True,
        )
