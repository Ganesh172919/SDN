"""The live console engine must replay exactly what the v4 benchmark measured."""
import csv
import tkinter as tk

import pytest

import config
from live.engine import Session, CONTROLLERS


def saved_rows(scenario, seed):
    path = config.PROJECT_ROOT / "output" / "benchmarks" / "v4" / "metrics.csv"
    with path.open(encoding="utf-8") as handle:
        return {(r["condition"], int(r["cycle"])): r for r in csv.DictReader(handle)
                if r["scenario"] == scenario and int(r["seed"]) == seed}


@pytest.mark.parametrize("scenario", ["mixed", "alternate"])
def test_engine_reproduces_saved_benchmark_windows(scenario):
    saved = saved_rows(scenario, 1900)
    for controller in CONTROLLERS:
        session = Session(controller, scenario, 1900)
        while not session.done:
            w = session.step()
            row = saved[(controller, w.cycle)]
            assert w.installed.action == row["installed_action"]
            assert w.latency_ms == pytest.approx(float(row["latency_ms"]), abs=1e-9)
            assert w.loss_pct == pytest.approx(float(row["loss_pct"]), abs=1e-9)
            assert w.reward == pytest.approx(float(row["reward"]), abs=1e-7)
        session.close()


def test_per_path_split_conserves_traffic():
    session = Session("A4", "mixed", 1901)
    while not session.done:
        w = session.step()
        drops = sum(p.overflow_mbit for p in w.paths) + w.meter_drop_mbit
        assert drops == pytest.approx(w.dropped_mbit, abs=1e-9)
        for p in w.paths:  # old queue + arrivals = delivered + overflow + new queue
            assert p.queue_before + p.arrival_mbps * 5 == pytest.approx(p.delivered_mbit + p.overflow_mbit + p.queue_after, abs=1e-9)
    session.close()


def test_console_steps_without_a_display_error():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    from live.console import Console
    app = Console(root)
    for _ in range(5):
        app.step()
    root.update()
    assert app.session.cycle == 5 and len(app.shadow.history) == 5
    root.destroy()
