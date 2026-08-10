# Rune Coordination

Rune coordinates durable plans across short-lived agents. Its language distinguishes the
historical contract that was planned from the current work that may still execute.

## Language

**Task specification**:
An immutable contract for one self-contained piece of work. It remains historical evidence
even when the plan that created it is later found to be wrong.
_Avoid_: Mutable task, amended task

**Retired task**:
A terminal, unfinished task whose specification no longer belongs to the current plan. It
remains visible but can never be resumed or dispatched.
_Avoid_: Deleted task, overwritten task

**Replacement task**:
A newly specified task that takes over some or all of the planned outcome of a retired task.
It has its own identity and contract rather than modifying the retired task.
_Avoid_: Revised task, patched task
