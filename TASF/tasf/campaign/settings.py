from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    random_seed: int = 17
    max_cycles: int = 128
    protected_prefix: int = 0
    warmup_training: int = 2
    warmup_evaluation: int = 2
    cycles: int = 3
    training_rounds: int = 5
    evaluation_rounds: int = 3
    epsilon: float = 0.6
    replay_capacity: int = 64

    def __post_init__(self):
        counts = (self.protected_prefix, self.warmup_training, self.warmup_evaluation,
                  self.cycles, self.training_rounds, self.evaluation_rounds)
        if min(counts) < 0 or self.max_cycles < 1 or self.replay_capacity < 1:
            raise ValueError("Invalid campaign budget")
        if not 0 <= self.epsilon <= 1:
            raise ValueError("Epsilon must be in [0, 1]")
