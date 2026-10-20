# Understanding SELF X

## Purpose

SELF-X is a research demonstrator for an SDN administrator or evaluator. It asks whether a controller can reuse earlier decisions and explanations to manage repeated congestion. The local website displays evidence, explains each action or veto, replays traffic and provides submission documents.

The research question is whether memory improves outcomes over the same controller without memory. A working demo, a valid API response and a performance improvement are separate achievements. The evaluation preserves failures and unfavorable results.

## Demonstration

1. Run `run.ps1 dashboard` and open `http://127.0.0.1:8765`.
2. Review all controllers on the saved portable experiment.
3. Select an API pilot to inspect real model decisions applied to simulated demand.
4. Move the decision slider to inspect traffic, action, safety, reflection and source.
5. Replay a seed offline without API use.
6. Open the editable report or presentation under Submission.

## Contribution

A typed decision contract and deterministic gate protect the network adapter. A normalized state embedding retrieves episodes linking state and action to measured outcome and reflection. The numerical representation is inspectable and needs no embedding service. This is in-context adaptation, not fine-tuning.

The supplied control loop, reward, safety and memory form the foundation. The extension adds a portable two-path fluid model, numeric retrieval, native Gemini/free OpenRouter support, an availability sweep, dashboard and reproducible documents. Test imports work from selfx. The recorder stays inside selfx. Metered flows preserve a forwarding output, while rerouting requires a validated alternate path.

## Submission scope

Use the report and presentation with the experimental protocol and raw results. Windows validates the simulation and controller logic. Linux Mininet/Ryu installation, real packet capture, endpoint goodput and sustained physical-network performance remain separate deployment experiments. The old testbed sums switch-port transmissions across hops, so those values must not be compared with simulated endpoint goodput.

Published measurements keep their original task and units. They are not portrayed as local benchmark results. API pilots include their actual success/fallback coverage. The result section evaluates whether memory helped; improvement is never assumed.

## Revision 4 entry points

See [the current README](../README.md), [benchmark protocol](BENCHMARKS_V4.md), [complete rule replay](RULE_DEMO.md) and [architecture/R Markdown](ARCHITECTURE.Rmd). The current A4 uses parameter-conditioned memory and bounded pooled provider calls. The original sections below describe the project motivation; current measurements are in BENCHMARKS_V4.md.
