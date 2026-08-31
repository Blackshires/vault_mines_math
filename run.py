"""Run Vault Mines simulations and SDK validation."""

from gamestate import GameState
from game_config import GameConfig
from src.state.run_sims import create_books
from src.write_data.write_configs import generate_configs


if __name__ == "__main__":
    num_threads = 4
    batching_size = 5000
    compression = True
    profiling = False

    num_sim_args = {
        "base": 100000,
    }

    run_conditions = {
        "run_sims": True,
        # Stock XLSX analytics assumes slot-style symbol/game-type columns.
        "run_analysis": False,
        # Stock RGS LUT verification requires payoutMultiplier values in 0.10x
        # increments. Vault Mines uses exact state-dependent cashout multipliers
        # (typically 2 decimal places), so that generic LUT rule is not a valid
        # verifier for this interactive game model.
        "run_format_checks": False,
    }

    config = GameConfig()
    gamestate = GameState(config)

    analytic = gamestate.validate_analytic_rtp()
    print(
        "Analytic RTP validation: "
        f"{analytic['states_checked']} legal stopping states, "
        f"target={analytic['target_rtp']:.6f}, "
        f"worst_error={analytic['worst_error']:.3e}"
    )

    print("Max legal safe reveals before x5000 cap:")
    print(
        ", ".join(
            f"{mines}m:{gamestate.max_legal_safe_picks(mines)}"
            for mines in range(1, 21)
        )
    )

    if run_conditions["run_sims"]:
        create_books(
            gamestate,
            config,
            num_sim_args,
            batching_size,
            num_threads,
            compression,
            profiling,
        )

    generate_configs(gamestate)

    if not run_conditions["run_format_checks"]:
        print(
            "Generic RGS LUT format checks skipped: they require 0.10x payout "
            "increments, while Vault Mines uses exact interactive cashout multipliers."
        )
