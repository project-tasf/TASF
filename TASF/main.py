from collections import Counter
from json import dumps
from random import Random

from tasf.benches import default_registry
from tasf.campaign import Campaign, RoundResult, Settings
from tasf.model import Profile
from tasf.observation import AccumulatorReference
from tasf.seeding import sample_seeds


def accumulator_campaign(settings: Settings = Settings()) -> tuple[RoundResult, ...]:
    registry = default_registry()
    profile = Profile()
    campaign = Campaign(
        lambda: registry.create("accumulator", latency=1),
        AccumulatorReference,
        settings=settings,
        profile=profile,
    )
    seeds = sample_seeds(profile, Random(settings.random_seed), count=4)
    campaign.calibrate(seeds)
    return campaign.run()


if __name__ == "__main__":
    rounds = accumulator_campaign()
    print(dumps({
        "rounds": len(rounds),
        "status": dict(Counter(result.status for result in rounds)),
        "new_features": sum(result.new_features for result in rounds),
        "retained_cases": sum(result.added for result in rounds),
    }))
