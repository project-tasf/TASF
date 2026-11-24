# TASF

## [Timing-Aware Fuzzing for Stateful FPGA Soft IP Cores]

**📢 The 14 issues reported in our study are available with their Vivado projects and links to the original AMD Community discussions.**

### 📄 Project Overview

TASF tests how stateful FPGA soft IP cores respond when the timing of input transactions and control operations changes. It keeps the core configuration fixed and uses simulation feedback to choose which transaction or control to edit next.

### 🛠️ Tools Tested

The study tested 40 types of soft IP core in the AMD Vivado IP catalog. Examples from the reported cases include the following.

1. **Arithmetic and signal-processing cores** include Accumulator, Complex Multiplier, Multiply Adder, FIR Compiler, and Convolutional Encoder.
2. **Interface and system cores** include AXI GPIO, AXI Interrupt Controller, AXI4-Stream Interconnect, AXI AMM Bridge, Mailbox, System Cache, PTP 1588 Timer/Syncer, and TMR Voter.

---

**Env dependencies:**

1. **Python 3.12** was used to check the Python framework and its built-in accumulator testbench. Both use the Python standard library.
2. **AMD Vivado 2026.1 with Vivado Simulator (XSim)** is the environment recorded for the 14 archived case projects.
3. **Windows 11 Pro (64-bit)** was the host operating system for the study.

***

### Our Works

A stateful core retains information across transactions. An accumulator starting at zero, for example, produces `1` and then `2` when it accepts two inputs of `1`. A pause just before the second result is due can delay its delivery. The result should still be `2`. Testing this behavior requires tracking which inputs the core accepted and when the output became available.

TASF has three components. The **component for generating valid timing test cases** uses a combinatorial multi-armed bandit (CMAB) to select edit templates and a generative flow network (GFN) to choose where to apply them. Several edits can accumulate in one case while preserving the input history and timing conditions established by earlier edits. The **execution monitoring and feedback extraction component** records accepted inputs, outputs, and control transitions. It extracts their timing relationships and checks the results against an independent reference model. The **feedback-guided decision-making and anomaly analysis component** rewards previously unseen behavior, retains distinct cases that extend coverage, and repeats a case in a fresh simulation when the reference check finds a discrepancy.

In the study, TASF identified 14 issues across 40 types of core. These comprised three timing faults, six functional faults, two build failures, and three specification discrepancies.

***

### Main File

**1. The [tasf](tasf/) folder** contains the TASF implementation. The main files are listed below.

1. **[main.py](main.py)** connects TASF or a selected baseline to the Python accumulator testbench. The [testbench adapters](tasf/benches/adapters.py) also accept a Python callback or an exchange of JSON-compatible records from another testbench.
2. **[model.py](tasf/model.py)** defines a test case in terms of input values, transaction order, wait times, and control operations. The [seed generator](tasf/seeding/) builds initial cases within the selected core's constraints.
3. **[catalog.py](tasf/generation/catalog.py)** defines 24 timing edits in six families. The [planner](tasf/campaign/planner.py) checks each edit before keeping it in the case.

    - Input spacing
    - Control duration
    - Control placement
    - Timing relationships between controls
    - Transactions following the protected input history
    - Control sequence structure

4. **[cmab.py](tasf/learning/cmab.py)** selects candidate edit templates. **[flow.py](tasf/learning/flow.py)** learns which legal edits to apply to the current case.
5. **[observer.py](tasf/observation/observer.py)** collects the testbench trace and invokes the [reference checker](tasf/observation/reference.py). The [campaign](tasf/campaign/engine.py) uses the resulting coverage to update the learning policies and [seed corpus](tasf/feedback/corpus.py).

**2. The [Baseline](Baseline/) folder**

This directory implements the four comparison strategies described in Section 4.2 of the paper. [Random](Baseline/Random.py) generates fresh cases under the interface constraints. [Greedy](Baseline/Greedy.py) explores untried templates first and then selects by mean reward. [SA](Baseline/SA.py) uses simulated annealing to decide whether to accept an edited case. [SD-SAC](Baseline/SD_SAC.py) uses a tabular discrete actor-critic policy to choose an edit and its target.

**3. The [Faults](Faults/) folder**

Each report has its own directory. It contains `fault_description.pdf` with the original post title and body, `case_project.zip` with the attached Vivado project, and the original text attachment explaining the parameter choices and citing the relevant AMD documentation.

***

### Here are the details of these bugs

The entries follow the order of Table 5 in the paper. Each ID links to the AMD Community discussion. Each report title links to its archived files under [Faults](Faults/).

Fault1 &ensp; Vivado &ensp; [0D5Pd0000249rLVKAY](https://adaptivesupport.amd.com/s/question/0D5Pd0000249rLVKAY) &ensp; [Convolutional Encoder 9.0 Produces Incorrect Data in Single-Output Mode](Faults/vivado_0D5Pd0000249rLVKAY/)

Fault2 &ensp; Vivado &ensp; [0D5Pd000020Dc1mKAC](https://adaptivesupport.amd.com/s/question/0D5Pd000020Dc1mKAC) &ensp; [Rounding Mode Produces Incorrect Results in Complex Multiplier 6.0 IP](Faults/vivado_0D5Pd000020Dc1mKAC/)

Fault3 &ensp; Vivado &ensp; [0D5Pd000023fwgVKAQ](https://adaptivesupport.amd.com/s/question/0D5Pd000023fwgVKAQ) &ensp; [Active-Low IRQ Remains Asserted When the AXI INTC Master Enable Is Cleared](Faults/vivado_0D5Pd000023fwgVKAQ/)

Fault4 &ensp; Vivado &ensp; [0D5Pd0000230olVKAQ](https://adaptivesupport.amd.com/s/question/0D5Pd0000230olVKAQ) &ensp; [Mailbox Fails to Preserve the Final-Word Flag in a Short Packet](Faults/vivado_0D5Pd0000230olVKAQ/)

Fault5 &ensp; Vivado &ensp; [0D5Pd000020ZfKPKA0](https://adaptivesupport.amd.com/s/question/0D5Pd000020ZfKPKA0) &ensp; [From Negative to Positive: A Held Subtraction Result Changes](Faults/vivado_0D5Pd000020ZfKPKA0/)

Fault6 &ensp; Vivado &ensp; [0D5Pd000022B02aKAC](https://adaptivesupport.amd.com/s/question/0D5Pd000022B02aKAC) &ensp; [Unexpected Word Addresses on a 32-Bit Avalon Interface](Faults/vivado_0D5Pd000022B02aKAC/)

Fault7 &ensp; Vivado &ensp; [0D5Pd000021QUtwKAG](https://adaptivesupport.amd.com/s/question/0D5Pd000021QUtwKAG) &ensp; [AXI INTC IVR Changes After Adding a Lower-Priority Software Interrupt](Faults/vivado_0D5Pd000021QUtwKAG/)

Fault8 &ensp; Vivado &ensp; [0D5Pd000024i6hWKAQ](https://adaptivesupport.amd.com/s/question/0D5Pd000024i6hWKAQ) &ensp; [Unexpected PTP Register Values with an 80 MHz AXI Clock](Faults/vivado_0D5Pd000024i6hWKAQ/)

Fault9 &ensp; Vivado &ensp; [0D5Pd000026zmpjKAA](https://adaptivesupport.amd.com/s/question/0D5Pd000026zmpjKAA) &ensp; [Selecting an Output Bit Range Yields an Incorrect Multiply-Add Result](Faults/vivado_0D5Pd000026zmpjKAA/)

Fault10 &ensp; Vivado &ensp; [0D5Pd000021v1slKAA](https://adaptivesupport.amd.com/s/question/0D5Pd000021v1slKAA) &ensp; [System Cache Fails Simulation Elaboration with Exclusive Access Enabled](Faults/vivado_0D5Pd000021v1slKAA/)

Fault11 &ensp; Vivado &ensp; [0D5Pd000020vsM9KAI](https://adaptivesupport.amd.com/s/question/0D5Pd000020vsM9KAI) &ensp; [Port Width Mismatch in the 8-Bit AXI4-Stream Slave Configuration of TMR Voter](Faults/vivado_0D5Pd000020vsM9KAI/)

Fault12 &ensp; Vivado &ensp; [0D5Pd000022kF5PKAU](https://adaptivesupport.amd.com/s/question/0D5Pd000022kF5PKAU) &ensp; [Missing Valid Bytes in Packets with a 32-Bit TID](Faults/vivado_0D5Pd000022kF5PKAU/)

Fault13 &ensp; Vivado &ensp; [0D5Pd000026zfV4KAI](https://adaptivesupport.amd.com/s/question/0D5Pd000026zfV4KAI) &ensp; [FIR Compiler Produces a Negative Full-Precision Result at the Minimum Signed Input](Faults/vivado_0D5Pd000026zfV4KAI/)

Fault14 &ensp; Vivado &ensp; [0D5Pd000023RH6tKAG](https://adaptivesupport.amd.com/s/question/0D5Pd000023RH6tKAG) &ensp; [AXI GPIO Register Readback Anomaly in All-Output Mode](Faults/vivado_0D5Pd000023RH6tKAG/)

***

**We thank the AMD engineers and members of the AMD Community who reviewed our reports and helped clarify the behavior of the affected IP cores.**
