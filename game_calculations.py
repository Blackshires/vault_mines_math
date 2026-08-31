"""Mathematical calculations for Vault Mines."""

from math import comb

from src.executables.executables import Executables


class GameCalculations(Executables):
    """Pure Mines probability and payout helpers."""

    BOARD_SIZE = 25

    @classmethod
    def survival_probability(cls, mines: int, safe_picks: int) -> float:
        """Probability of revealing ``safe_picks`` safe tiles in succession."""

        if mines < 1 or mines >= cls.BOARD_SIZE:
            raise ValueError("mines must be between 1 and 24")
        if safe_picks < 0 or safe_picks > cls.BOARD_SIZE - mines:
            return 0.0
        if safe_picks == 0:
            return 1.0

        safe_tiles = cls.BOARD_SIZE - mines
        return comb(safe_tiles, safe_picks) / comb(cls.BOARD_SIZE, safe_picks)

    def uncapped_cashout_multiplier(self, mines: int, safe_picks: int) -> float:
        """Return the exact RTP-adjusted multiplier before applying the max-win policy."""

        if safe_picks <= 0:
            return 1.0

        probability = self.survival_probability(mines, safe_picks)
        if probability <= 0:
            return 0.0

        return float(self.config.rtp / probability)

    def cashout_multiplier(self, mines: int, safe_picks: int) -> float:
        """Return a legal Vault Mines cashout multiplier.

        Vault Mines does not truncate a mathematically fair multiplier to x5000,
        because doing so would reduce RTP. Instead, continuation is blocked before
        the next successful reveal would require a payout above the cap.
        """

        multiplier = self.uncapped_cashout_multiplier(mines, safe_picks)
        if multiplier > float(self.config.wincap):
            raise ValueError(
                f"cashout state exceeds x{self.config.wincap}: "
                f"mines={mines}, safe_picks={safe_picks}, multiplier={multiplier}"
            )
        return multiplier

    def can_continue(self, mines: int, revealed_safe: int) -> bool:
        """Whether one more unprotected safe reveal remains below the x5000 cap."""

        next_safe = revealed_safe + 1
        if next_safe > self.BOARD_SIZE - mines:
            return False
        return self.uncapped_cashout_multiplier(mines, next_safe) <= float(self.config.wincap)

    def max_legal_safe_picks(self, mines: int) -> int:
        """Largest number of safe reveals allowed without truncating the fair payout."""

        max_safe = self.BOARD_SIZE - mines
        legal = 0
        for safe_picks in range(1, max_safe + 1):
            if self.uncapped_cashout_multiplier(mines, safe_picks) <= float(self.config.wincap):
                legal = safe_picks
            else:
                break
        return legal

    def probability_next_safe(self, mines: int, revealed_safe: int) -> float:
        """Conditional probability that the next hidden tile is safe."""

        remaining_tiles = self.BOARD_SIZE - revealed_safe
        remaining_safe = self.BOARD_SIZE - mines - revealed_safe
        if remaining_tiles <= 0 or remaining_safe <= 0:
            return 0.0
        return remaining_safe / remaining_tiles

    def generate_multiplier_table(self) -> dict[int, list[float]]:
        """Generate all legal payout multipliers for mine counts 1 through 20."""

        table = {}
        for mines in range(1, 21):
            table[mines] = [
                round(self.cashout_multiplier(mines, safe_picks), 8)
                for safe_picks in range(1, self.max_legal_safe_picks(mines) + 1)
            ]
        return table

    def validate_analytic_rtp(self, tolerance: float = 1e-12) -> dict:
        """Verify every legal pure-Mines stopping state returns the configured RTP."""

        worst_error = 0.0
        states_checked = 0
        for mines in range(1, 21):
            for safe_picks in range(1, self.max_legal_safe_picks(mines) + 1):
                probability = self.survival_probability(mines, safe_picks)
                multiplier = self.cashout_multiplier(mines, safe_picks)
                expected_return = probability * multiplier
                error = abs(expected_return - self.config.rtp)
                worst_error = max(worst_error, error)
                states_checked += 1
                if error > tolerance:
                    raise AssertionError(
                        f"RTP mismatch mines={mines}, safe_picks={safe_picks}: "
                        f"{expected_return} != {self.config.rtp}"
                    )

        return {
            "states_checked": states_checked,
            "target_rtp": self.config.rtp,
            "worst_error": worst_error,
        }
