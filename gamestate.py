"""Simulation state for Vault Mines pure-Mines validation."""

import random

from game_override import GameStateOverride
from game_events import mines_result_event


class GameState(GameStateOverride):
    """Generate pure-Mines outcomes for SDK validation."""

    def run_spin(self, sim: int, simulation_seed=None) -> None:
        self.reset_seed(sim)
        self.repeat = True

        while self.repeat:
            self.reset_book()

            # SDK smoke simulation: cycle through all 20 selectable mine counts
            # and cash out after the first safe reveal. Every one of these states
            # has exact expected return = configured RTP and moderate variance.
            mines = (sim % 20) + 1
            safe_target = 1

            probability = self.survival_probability(mines, safe_target)
            multiplier = self.cashout_multiplier(mines, safe_target)
            hit = random.random() < probability
            win = multiplier if hit else 0.0

            self.win_manager.update_spinwin(win)
            self.win_manager.update_gametype_wins(self.gametype)

            mines_result_event(
                self,
                mines=mines,
                safe_picks=safe_target,
                multiplier=multiplier,
                hit=hit,
            )

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    def run_freespin(self) -> None:
        pass
