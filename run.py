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
        # increments. Vault Mines uses exact state-dependent cashout multipliers.
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

    feature_math = gamestate.validate_feature_martingale()
    print(
        "Feature martingale validation: "
        f"{feature_math['states_checked']} local states, "
        f"worst_error={feature_math['worst_error']:.3e}"
    )

    print("Max legal safe reveals before x5000 cap:")
    print(
        ", ".join(
            f"{mines}m:{gamestate.max_legal_safe_picks(mines)}"
            for mines in range(1, 21)
        )
    )

    feature_sim = gamestate.simulate_feature_strategy(
        rounds=100000,
        target_safe_reveals=5,
    )
    print(
        "V1 Keys/Shield Monte Carlo: "
        f"rounds={feature_sim['rounds']}, "
        f"RTP={feature_sim['rtp']:.6f} "
        f"(target={feature_sim['target_rtp']:.6f}), "
        f"winRate={feature_sim['winning_round_rate']:.4f}, "
        f"naturalShields={feature_sim['natural_shield_awards']}, "
        f"vaultProtections={feature_sim['vault_protection_awards']}, "
        f"defusedMines={feature_sim['defused_mines']}"
    )
    print(
        "V1 provisional feature frequencies: "
        f"naturalShieldRound={config.natural_shield_round_probability:.3f}, "
        f"keyPerEligibleSafeCell={config.key_cell_probability:.3f}"
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
