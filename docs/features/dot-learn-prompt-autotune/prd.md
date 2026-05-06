# Product Requirements Document (PRD): Project "AutoTune" (Dot-Learn Optimization Engine)

## 1. Executive Summary
**Project Name:** AutoTune (Internal Codename: Dot-Learn Optimization Engine)  
**Status:** Draft  
**Owner:** Product Engineering  
**Date:** May 22, 2024

### 1.1 Vision
To transform the current static RAG (Retrieval-Augmented Generation) pipeline into a self-optimizing system that autonomously discovers the most effective prompts, retrieval parameters, and generation strategies using the "Derivative of Truth" (DoT) metric as a reward signal.

### 1.2 Problem Statement
Currently, optimizing the RAG pipeline (prompt engineering, retrieval tuning, and model parameters) is a manual, iterative, and human-intensive process. This leads to:
*   **Suboptimal Performance:** Human engineers cannot exhaustively test the combinatorial space of prompts and retrieval settings.
*   **High Operational Cost:** Significant engineering time is spent on manual "vibes-based" evaluation.
  
### 1.3 Solution
An automated "Online Optimization" engine that uses the existing `score_truth_derivative` metric to evaluate candidates. The system will autonomously iterate through variations of prompts and retrieval configurations, selecting the "winners" that maximize truthfulness and groundedness.

---

## 2. Target Audience & User Personas
| Persona | Needs |
| :--- | :--- |
| **AI Engineer** | Needs a way to improve system accuracy without manual prompt tweaking or constant manual testing. |
| **Product Manager** | Needs measurable improvements in system reliability and truthfulness (DoT score) to justify deployment. |
| **System Administrator** | Needs a low-overhead way to maintain high-quality outputs as new data/sources are added to the system. |

---

## 3. Functional Requirements

### 3.1 Core Engine (The "Optimizer")
* **FR1: Candidate Generation:** The system must be able to generate variations of prompts (e.g., via template swapping or LLM-based rewriting) and retrieval parameters (e.g., top-k, similarity thresholds).
* **FR2: Automated Execution:** The system must execute a "batch" of candidates against a fixed set of test queries.
* **FB3: Scoring Integration:** The system must use the existing `score_truth_derivative` (or similar DoT metrics) to evaluate the output of every candidate.
* **FR4: Selection Logic:** The system must implement a selection algorithm (e.g., Bandit-based or simple Tournament) to identify the highest-performing configuration.

### 3.2 The "Dot-Learn" Loop (The Workflow)
* **FR5: Iterative Loop:** The system must support a multi-step loop: 
    1.  Generate $\rightarrow$ 2. Execute $\rightarrow$ 3. Score $\rightarrow$ 4. Update Strategy.
* **FR6: Configuration Persistence:** Once a "winning" configuration is identified, the system must be able to save it as the new "Production" configuration.

### 3.3 Monitoring & Observability
* **FR7: Performance Dashboard:** A view showing the DoT score trends over different optimization iterations.
* **FR8: Audit Logs:** A record of which prompt/parameter set was active during which time period and why it was selected.

---

## 4. Non-Functional Requirements

### 4.1 Performance & Scalability
* **NFR1: Latency:** The optimization process itself can be high-latency (asynchronous), but the *production* inference must not be slowed down by the presence of the optimizer.
* **NFR2: Cost Control:** The system must include "budget caps" (e.g., max number of iterations or max tokens per optimization run) to prevent runaway LLM costs.

### 4.2 Reliability
* **NFR3: Determinism:** The evaluation set (the "Golden Dataset") must remain static during an optimization run to ensure fair comparison.
* **NFR4: Fallback:** If the optimization engine fails, the system must default to the last known "Stable" configuration.

---

## 5. User Flow (The "AutoTune" Workflow)

1.  **Trigger:** An engineer triggers an `autotune --mode [prompt|retrieval|full] --dataset [golden_set_v1]` command.
2.  **Exploration:** The engine generates $N$ variations of the target component.
3.  **Execution:** The engine runs the RAG pipeline for all $N$ variations against the `golden_set_v1`.
4.  **Evaluation:** The `score_truth_derivative` metric is calculated for every output.
5.  **Comparison:** The engine compares the mean DoT scores.
6.  **Deployment:** The engine prompts the user: *"Configuration B outperformed Configuration A by 12%. Apply to production? (Y/n)"*.

---
