"""Mathematical calculations for Vault Mines."""

from math import comb

from src.executables.executables import Executables


class GameCalculations(Executables):
    """Pure Mines and feature-state probability/payout helpers."""

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
        """Return a legal pure-Mines cashout multiplier."""

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
        """Largest pure-Mines safe-reveal count allowed without payout truncation."""

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

    # ------------------------------------------------------------------
    # V1 interactive feature account
    # ------------------------------------------------------------------

    def cashout_from_account(self, account: float) -> float:
        """Convert the fair-state account into the RTP-adjusted cashout value."""

        payout = float(self.config.rtp) * float(account)
        if payout > float(self.config.wincap) + 1e-12:
            raise ValueError(f"feature cashout exceeds x{self.config.wincap}: {payout}")
        return payout

    @staticmethod
    def next_unprotected_safe_account(account: float, hidden: int, mines: int) -> float:
        """Update the fair account after an unprotected safe reveal.

        If h cells remain and m are mines, the safe probability is (h-m)/h.
        Dividing the account by that probability makes the account a martingale.
        """

        if hidden <= 0 or mines < 0 or mines >= hidden:
            raise ValueError("unprotected safe transition requires 0 <= mines < hidden")
        return float(account) * hidden / (hidden - mines)

    def can_continue_feature_state(
        self,
        account: float,
        hidden: int,
        mines: int,
        shield_charges: int,
    ) -> bool:
        """Check whether the next interactive reveal is legal under x5000.

        A protected click cannot terminally lose and does not increase the fair
        account, so it cannot cross the cap.  Without a shield, the next safe
        branch must itself remain at or below x5000.
        """

        if hidden <= 0:
            return False
        if mines < 0 or mines > hidden:
            raise ValueError("invalid hidden/mines state")
        if shield_charges > 0:
            return True
        if mines >= hidden:
            return False

        next_account = self.next_unprotected_safe_account(account, hidden, mines)
        return self.cashout_from_account(next_account) <= float(self.config.wincap)

    @staticmethod
    def depth_label(successful_reveals: int) -> str:
        """Presentation-only Depth tier."""

        if successful_reveals <= 2:
            return "I"
        if successful_reveals <= 5:
            return "II"
        if successful_reveals <= 9:
            return "III"
        return "VAULT"

    def validate_feature_martingale(self, tolerance: float = 1e-12) -> dict:
        """Prove the local Keys/Shield state transition preserves fair account EV.

        Payload type does not alter the current-click payout account. Keys and
        Shields only modify future risk. With no shield, a mine terminates at 0
        and a safe branch divides the account by P(safe). With a shield, both
        mine and safe branches survive with the same account.
        """

        states_checked = 0
        worst_error = 0.0
        sample_accounts = (1.0, 1.37, 17.25, 499.0)

        for hidden in range(1, self.BOARD_SIZE + 1):
            for mines in range(0, min(20, hidden) + 1):
                for shield_charges in range(0, self.config.max_shield_charges + 1):
                    for account in sample_accounts:
                        if shield_charges > 0:
                            expected_after = account
                        elif mines >= hidden:
                            # No safe branch exists; continuation is illegal.
                            continue
                        else:
                            p_safe = (hidden - mines) / hidden
                            safe_account = self.next_unprotected_safe_account(
                                account, hidden, mines
                            )
                            expected_after = p_safe * safe_account

                        error = abs(expected_after - account)
                        worst_error = max(worst_error, error)
                        states_checked += 1
                        if error > tolerance:
                            raise AssertionError(
                                "Feature martingale mismatch: "
                                f"h={hidden}, m={mines}, q={shield_charges}, "
                                f"account={account}, expected={expected_after}"
                            )

        return {
            "states_checked": states_checked,
            "worst_error": worst_error,
        }

    def generate_multiplier_table(self) -> dict[int, list[float]]:
        """Generate all legal pure-Mines payout multipliers for mine counts 1-20."""

        table = {}
        for mines in range(1, 21):
            table[mines] = [
                round(self.cashout_multiplier(mines, safe_picks), 8)
                for safe_picks in range(1, self.max_legal_safe_picks(mines) + 1)
            ]
        return table

    def validate_analytic_rtp(self, tolerance: float = 1e-12) -> dict:
        """Verify every legal pure-Mines stopping state returns configured RTP."""

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
