# TASF

**Timing-Aware Fuzzing for Stateful FPGA Soft IP Cores**

## Project Overview

TASF tests how a soft IP core responds to the order and timing of its inputs while the core configuration stays fixed. A stateful core retains information from earlier inputs or control operations. Consider an accumulator starting at zero. When it accepts two inputs of `1`, it produces `1` and then `2`. In the included Python testbench, a one-cycle pause just before the second result is due delays its delivery by one cycle. The expected value is still `2`.

A TASF test case describes both the input transactions and the control operations applied during simulation. Each transaction carries a value and a wait time. Each control specifies which accepted transaction triggers it, how long to wait after that transaction, and how many cycles the control stays active.

## Method

1. **Component for generating valid timing test cases.** Starting from a previously tested case, a combinatorial multi-armed bandit (CMAB) selects edit templates using their past rewards and how often they were selected together. A generative flow network (GFN) then chooses a specific edit, such as extending the pause after the second input. Several edits can accumulate before simulation. Each edit must satisfy the core's constraints and preserve the input history and timing conditions protected by earlier edits.

2. **Execution monitoring and feedback extraction component.** The testbench records when inputs and outputs are accepted and when controls start and end. TASF extracts timing features from this trace, such as the number of cycles between a pause ending and the next output transfer. An independent reference model checks the observed results against the expected values and order.

3. **Feedback-guided decision-making and anomaly analysis component.** A completed run earns a reward of one if it adds any previously unseen coverage feature, and zero otherwise. Distinct cases that add coverage can become seeds for later rounds. Training rounds update the GFN, while evaluation rounds provide observations for the CMAB. If the reference check finds a discrepancy, TASF repeats the case with a fresh testbench and reference model to see whether the same discrepancy recurs.

## Timing Edits

The framework groups 24 edit templates into six families.

| Family | Templates | What changes |
| --- | ---: | --- |
| Input spacing | 2 | Shorten or lengthen the wait between transactions. |
| Control duration | 3 | Add a control operation, or shorten or extend an existing one. |
| Control placement | 3 | Move a control earlier or later, or change which accepted transaction triggers it. |
| Relations between controls | 10 | Change the relative timing of two controls, including their order, overlap, containment, or shared boundaries. |
| Transaction suffix | 3 | Duplicate, insert, or delete a complete transaction while preserving the required prefix. |
| Control sequence structure | 3 | Repeat a control, split it into two intervals, or merge two intervals. |

## Testbench Interfaces

The study evaluated TASF on soft IP cores in AMD Vivado. This repository includes the Python framework and an in-memory accumulator testbench. A core-specific testbench receives a timing test case and a cycle budget, then returns a trace of observed events and a completion flag. The adapters support a Python callback or an exchange of JSON-compatible records. Each core can supply its own control types, validity checks, and reference model.

## Baseline Methods

The [Baseline](Baseline/) directory implements the four comparison strategies described in Section 4.2 of the paper. All four use the same testbench, cycle limit, coverage extractor, and reference model as TASF. Greedy, SA, and SD-SAC also share the six edit families, protected history, and seed retention rules.

| Method | How it generates the next case |
| --- | --- |
| [Random](Baseline/Random.py) | Draws a fresh case from the configured input and timing domains. Coverage is recorded after execution. These observations do not affect the next draw. |
| [Greedy](Baseline/Greedy.py) | Tries unseen legal templates first, then chooses a template with the highest mean reward. Each template retained in a case receives the reward from the completed run. |
| [SA](Baseline/SA.py) | Builds a candidate from its current case. A lower reward can be accepted with a probability that decreases as the temperature falls. The search periodically restarts from the seed corpus. |
| [SD-SAC](Baseline/SD_SAC.py) | Uses a tabular policy to choose a legal template and target together. The critics use double-Q averaging and Q clipping, and the actor penalizes changes in policy entropy. Only the final edit receives the case reward. |

The SA acceptance rule follows Kirkpatrick et al. The SD-SAC update adapts the discrete actor-critic method of Zhou et al. to the legal edits available at each step. [Optimization by Simulated Annealing](https://doi.org/10.1126/science.220.4598.671) and [Revisiting Discrete Soft Actor-Critic](https://openreview.net/forum?id=EUF2R6VBeU).

## Main Files

| Source | Role |
| --- | --- |
| [main.py](main.py) | Connects the selected method to the accumulator testbench, reference model, and common initial seeds. |
| [model.py](tasf/model.py) | Defines the transactions, controls, test cases, and traces shared by the components. |
| [seeding](tasf/seeding/) and [generation](tasf/generation/) | Generate initial cases, define the 24 edit templates, and check candidate edits. |
| [cmab.py](tasf/learning/cmab.py) and [flow.py](tasf/learning/flow.py) | Implement template selection and the tabular GFN policy for choosing edits. |
| [benches](tasf/benches/) | Provides the testbench interface, adapters, registry, and accumulator implementation. |
| [observation](tasf/observation/) | Extracts coverage from traces and checks outputs against the reference model. |
| [feedback](tasf/feedback/) | Maintains the seed corpus, cumulative coverage, and training replay buffer. |
| [campaign](tasf/campaign/) | Coordinates cumulative edits, training and evaluation rounds, and discrepancy replay. |
