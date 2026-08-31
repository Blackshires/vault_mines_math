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

    # Low-variance RTP smoke test. Cashing out after the first safe reveal avoids
    # the huge Monte-Carlo variance created by high-mine deep cashouts.
    shallow_sim = gamestate.simulate_feature_strategy(
        rounds=100000,
        target_safe_reveals=1,
        seed=20260831,
    )
    print(
        "V1 low-variance RTP Monte Carlo: "
        f"rounds={shallow_sim['rounds']}, "
        f"RTP={shallow_sim['rtp']:.6f} "
        f"(target={shallow_sim['target_rtp']:.6f}), "
        f"winRate={shallow_sim['winning_round_rate']:.4f}"
    )

    # Deeper feature-behaviour diagnostic. This intentionally has high variance:
    # with 19-20 mines, rare surviving paths can pay thousands of times the bet.
    # Its purpose at 100k rounds is feature incidence/transition coverage, not a
    # precise RTP estimate; the analytic martingale validation above is the RTP proof.
    feature_sim = gamestate.simulate_feature_strategy(
        rounds=100000,
        target_safe_reveals=5,
        seed=20260832,
    )
    print(
        "V1 deep Keys/Shield diagnostic: "
        f"rounds={feature_sim['rounds']}, "
        f"sampleRTP={feature_sim['rtp']:.6f}, "
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

    calibration = gamestate.simulate_calibration_matrix(
        rounds_per_case=5000,
        mine_counts=(1, 3, 5, 10, 15, 20),
        safe_targets=(1, 3, 5, 10),
        seed=20260901,
    )
    print("\nV1 feature calibration matrix (5000 rounds/case):")
    print(
        "mines target reach% win% key% 3keys% natShield% defuse% "
        "DII% DIII% VAULT% capStop% sampleRTP"
    )
    for row in calibration:
        print(
            f"{row['mines']:>5} {row['target']:>6} "
            f"{100 * row['target_reach_rate']:>6.2f} "
            f"{100 * row['win_rate']:>5.2f} "
            f"{100 * row['any_key_rate']:>5.2f} "
            f"{100 * row['three_keys_rate']:>6.2f} "
            f"{100 * row['natural_shield_rate']:>10.2f} "
            f"{100 * row['defused_round_rate']:>7.2f} "
            f"{100 * row['depth_ii_rate']:>5.2f} "
            f"{100 * row['depth_iii_rate']:>6.2f} "
            f"{100 * row['vault_rate']:>6.2f} "
            f"{100 * row['cap_stop_rate']:>8.2f} "
            f"{row['sample_rtp']:>9.4f}"
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
