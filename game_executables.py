"""Vault Mines execution helpers."""

import random

from game_calculations import GameCalculations
from round_state import VaultMinesRound


class GameExecutables(GameCalculations):
    """Execution layer for the live interactive Vault Mines round."""

    def create_round(self, mines: int, rng: random.Random | None = None) -> VaultMinesRound:
        """Pre-generate a deterministic hidden board for one round.

        Mine positions are chosen first. A round may then receive at most one
        natural Shield payload on a safe cell, and every other safe cell may be
        a Key according to the configured provisional key probability.
        """

        if mines < 1 or mines > 20:
            raise ValueError("Vault Mines supports 1 to 20 mines")

        rng = rng or random.Random()
        cells = list(range(self.BOARD_SIZE))
        mine_cells = set(rng.sample(cells, mines))
        safe_cells = [cell for cell in cells if cell not in mine_cells]

        board = ["gem"] * self.BOARD_SIZE
        for cell in mine_cells:
            board[cell] = "mine"

        natural_shield_cell = None
        if safe_cells and rng.random() < self.config.natural_shield_round_probability:
            natural_shield_cell = rng.choice(safe_cells)
            board[natural_shield_cell] = "shield"

        for cell in safe_cells:
            if cell == natural_shield_cell:
                continue
            if rng.random() < self.config.key_cell_probability:
                board[cell] = "key"

        return VaultMinesRound(mine_count=mines, board=board)

    def can_continue_round(self, state: VaultMinesRound) -> bool:
        """Return whether another reveal is legal for this exact round state."""

        if state.finished:
            return False
        return self.can_continue_feature_state(
            state.account,
            state.hidden_count,
            int(state.remaining_mines),
            state.shield_charges,
        )

    def current_cashout(self, state: VaultMinesRound) -> float:
        """Return the live cashout multiplier without ending the round."""

        if not state.alive:
            return 0.0
        if state.successful_reveals <= 0:
            return 0.0
        return self.cashout_from_account(state.account)

    def reveal_cell(self, state: VaultMinesRound, cell: int) -> dict:
        """Reveal one requested cell and apply exact Keys/Shield state math.

        Important invariant: while a shield charge exists, the reveal cannot
        terminally lose and the payout account does not increase. A mine consumes
        one charge and is removed from the remaining mine count. A safe reveal
        while protected also leaves the account unchanged.
        """

        if state.finished:
            raise RuntimeError("round is already finished")
        if cell not in state.hidden_cells:
            raise ValueError("cell has already been revealed or is invalid")
        if not self.can_continue_round(state):
            raise RuntimeError("max-win gate requires cashout before another reveal")

        hidden_before = state.hidden_count
        mines_before = int(state.remaining_mines)
        shields_before = state.shield_charges
        account_before = state.account
        tile = state.board[cell]

        state.hidden_cells.remove(cell)
        terminal_loss = False
        mine_defused = False
        key_awarded = False
        natural_shield_awarded = False
        vault_protection_awarded = False

        if tile == "mine":
            if shields_before > 0:
                state.shield_charges -= 1
                state.remaining_mines = mines_before - 1
                mine_defused = True
            else:
                state.alive = False
                terminal_loss = True
        else:
            if shields_before == 0:
                state.account = self.next_unprotected_safe_account(
                    state.account, hidden_before, mines_before
                )

            state.successful_reveals += 1

            if tile == "key" and state.keys_found < self.config.keys_for_vault_protection:
                state.keys_found += 1
                key_awarded = True
                if (
                    state.keys_found == self.config.keys_for_vault_protection
                    and not state.vault_protection_awarded
                ):
                    state.shield_charges = min(
                        self.config.max_shield_charges,
                        state.shield_charges + 1,
                    )
                    state.vault_protection_awarded = True
                    vault_protection_awarded = True

            elif tile == "shield" and not state.natural_shield_awarded:
                state.shield_charges = min(
                    self.config.max_shield_charges,
                    state.shield_charges + 1,
                )
                state.natural_shield_awarded = True
                natural_shield_awarded = True

        result = {
            "cell": cell,
            "tile": tile,
            "terminalLoss": terminal_loss,
            "mineDefused": mine_defused,
            "keyAwarded": key_awarded,
            "naturalShieldAwarded": natural_shield_awarded,
            "vaultProtectionAwarded": vault_protection_awarded,
            "keysFound": state.keys_found,
            "shieldCharges": state.shield_charges,
            "remainingMines": int(state.remaining_mines),
            "successfulReveals": state.successful_reveals,
            "depth": self.depth_label(state.successful_reveals),
            "accountBefore": account_before,
            "accountAfter": state.account if state.alive else 0.0,
            "cashoutMultiplier": self.current_cashout(state),
            "canContinue": self.can_continue_round(state) if state.alive else False,
        }
        state.history.append(result)
        return result

    def cashout_round(self, state: VaultMinesRound) -> float:
        """End a live round and return its multiplier."""

        if not state.alive:
            return 0.0
        if state.cashed_out:
            raise RuntimeError("round has already been cashed out")
        if state.successful_reveals <= 0:
            raise RuntimeError("cashout requires at least one successful reveal")

        payout = self.cashout_from_account(state.account)
        state.cashed_out = True
        return payout

    def simulate_feature_strategy(
        self,
        rounds: int = 100000,
        target_safe_reveals: int = 5,
        seed: int = 20260831,
    ) -> dict:
        """Monte-Carlo smoke test for the V1 feature state engine.

        Mine count cycles 1..20. The strategy reveals fixed cell indices until
        target_safe_reveals, a terminal mine, or the cap gate, then cashes out.
        Fixed indices are intentional: the hidden board is uniformly generated,
        so no player selection bias is introduced.
        """

        rng = random.Random(seed)
        total_return = 0.0
        natural_shields = 0
        vault_protections = 0
        defused_mines = 0
        winning_rounds = 0

        for i in range(rounds):
            mines = (i % 20) + 1
            state = self.create_round(mines, rng)

            for cell in range(self.BOARD_SIZE):
                if not state.alive or state.successful_reveals >= target_safe_reveals:
                    break
                if not self.can_continue_round(state):
                    break

                result = self.reveal_cell(state, cell)
                natural_shields += int(result["naturalShieldAwarded"])
                vault_protections += int(result["vaultProtectionAwarded"])
                defused_mines += int(result["mineDefused"])

            if state.alive and state.successful_reveals > 0:
                payout = self.cashout_round(state)
                total_return += payout
                winning_rounds += 1

        return {
            "rounds": rounds,
            "rtp": total_return / rounds,
            "target_rtp": self.config.rtp,
            "target_safe_reveals": target_safe_reveals,
            "winning_round_rate": winning_rounds / rounds,
            "natural_shield_awards": natural_shields,
            "vault_protection_awards": vault_protections,
            "defused_mines": defused_mines,
        }

    def simulate_calibration_matrix(
        self,
        rounds_per_case: int = 5000,
        mine_counts: tuple[int, ...] = (1, 3, 5, 10, 15, 20),
        safe_targets: tuple[int, ...] = (1, 3, 5, 10),
        seed: int = 20260901,
    ) -> list[dict]:
        """Measure feature visibility by mine count and intended play depth.

        This is a gameplay calibration diagnostic, not an RTP certification test.
        Each row uses a fixed mine count and keeps revealing deterministic cell
        indices until the requested number of successful safe reveals, a terminal
        mine, or the x5000 continuation gate.
        """

        if rounds_per_case <= 0:
            raise ValueError("rounds_per_case must be positive")

        rng = random.Random(seed)
        rows = []

        for mines in mine_counts:
            if mines < 1 or mines > 20:
                raise ValueError("calibration mine counts must be between 1 and 20")

            for target in safe_targets:
                if target <= 0:
                    raise ValueError("calibration safe targets must be positive")

                total_return = 0.0
                wins = 0
                target_reached = 0
                any_key = 0
                three_keys = 0
                natural_shields = 0
                defused_rounds = 0
                defused_mines = 0
                depth_ii = 0
                depth_iii = 0
                vault = 0
                cap_stops = 0

                for _ in range(rounds_per_case):
                    state = self.create_round(mines, rng)
                    saw_key = False
                    saw_natural_shield = False
                    round_defused = False
                    stopped_by_cap = False

                    for cell in range(self.BOARD_SIZE):
                        if not state.alive or state.successful_reveals >= target:
                            break
                        if not self.can_continue_round(state):
                            stopped_by_cap = True
                            break

                        result = self.reveal_cell(state, cell)
                        saw_key = saw_key or result["keyAwarded"]
                        saw_natural_shield = (
                            saw_natural_shield or result["naturalShieldAwarded"]
                        )
                        if result["mineDefused"]:
                            round_defused = True
                            defused_mines += 1

                    if state.successful_reveals >= target:
                        target_reached += 1
                    if state.successful_reveals >= 3:
                        depth_ii += 1
                    if state.successful_reveals >= 6:
                        depth_iii += 1
                    if state.successful_reveals >= 10:
                        vault += 1
                    if saw_key:
                        any_key += 1
                    if state.keys_found >= self.config.keys_for_vault_protection:
                        three_keys += 1
                    if saw_natural_shield:
                        natural_shields += 1
                    if round_defused:
                        defused_rounds += 1
                    if stopped_by_cap:
                        cap_stops += 1

                    if state.alive and state.successful_reveals > 0:
                        total_return += self.cashout_round(state)
                        wins += 1

                denom = float(rounds_per_case)
                rows.append(
                    {
                        "mines": mines,
                        "target": target,
                        "rounds": rounds_per_case,
                        "sample_rtp": total_return / denom,
                        "win_rate": wins / denom,
                        "target_reach_rate": target_reached / denom,
                        "any_key_rate": any_key / denom,
                        "three_keys_rate": three_keys / denom,
                        "natural_shield_rate": natural_shields / denom,
                        "defused_round_rate": defused_rounds / denom,
                        "defused_mines": defused_mines,
                        "depth_ii_rate": depth_ii / denom,
                        "depth_iii_rate": depth_iii / denom,
                        "vault_rate": vault / denom,
                        "cap_stop_rate": cap_stops / denom,
                    }
                )

        return rows
